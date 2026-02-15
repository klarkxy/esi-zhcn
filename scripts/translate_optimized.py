#!/usr/bin/env python3

import re
from pathlib import Path
from typing import Dict, List, Tuple, Set, Optional, Any
import shutil
import requests
import os
import sys
import concurrent.futures
import time
import json
from dataclasses import dataclass
from collections import defaultdict

# 配置 - 首先尝试从本地配置文件加载
try:
    # 添加scripts目录到路径，以便导入config
    script_dir = Path(__file__).parent
    if str(script_dir) not in sys.path:
        sys.path.insert(0, str(script_dir))

    from config import API_KEY, API_URL, MODEL_NAME, TRANSLATION_OPTIONS

    print(f"已加载本地配置文件，使用模型: {MODEL_NAME}")
except ImportError:
    print("请复制 scripts/config.py.template 为 scripts/config.py")
    exit(1)


@dataclass
class TranslationItem:
    """翻译项数据结构"""

    section: str
    key: str
    en_value: str
    zh_value: Optional[str] = None
    is_commented: bool = False
    line_num: int = -1
    needs_translation: bool = True


class BatchTranslator:
    """批量翻译器"""

    def __init__(self, batch_size: int = 20, max_workers: int = 5):
        self.batch_size = batch_size
        self.max_workers = max_workers
        self.api_key = API_KEY
        self.api_url = API_URL
        self.model_name = MODEL_NAME
        self.translation_options = TRANSLATION_OPTIONS

        # 缓存已翻译的文本
        self.translation_cache: Dict[str, str] = {}

    def is_english_text(self, text: str) -> bool:
        """判断文本是否主要是英文"""
        if not text.strip():
            return False

        # 检查是否包含中文字符
        if re.search(r"[\u4e00-\u9fff]", text):
            return False

        # 检查是否包含拉丁字母（a-zA-Z）
        if not re.search(r"[a-zA-Z]", text):
            return False  # 不包含拉丁字母，不是英文

        # 如果文本只包含拉丁字母、数字、空格和常见标点，假设是英文
        # 允许的字符：字母、数字、空格、. , ! ? : ; - _ ' " ( ) [ ] { } < > / \ | = + & % $ # @
        # 简化：如果文本中超过50%的字符是拉丁字母或常见英文标点，则认为是英文
        import string

        # 计算拉丁字母和常见英文标点的数量
        latin_and_punct = 0
        total_chars = 0

        for char in text:
            if char in string.ascii_letters or char in string.digits:
                latin_and_punct += 1
            elif char in " .,!?:;-_'\"()[]{}<>/\\|=+&%$#@":
                latin_and_punct += 1
            elif char == "\n" or char == "\t" or char == "\r":
                continue  # 忽略控制字符
            else:
                # 其他字符（可能是其他语言的字符）
                pass
            total_chars += 1

        if total_chars == 0:
            return False

        # 如果超过70%的字符是拉丁字母或英文标点，则认为是英文
        if latin_and_punct / total_chars >= 0.7:
            return True

        return False

    def needs_translation(self, en_value: str, zh_value: Optional[str]) -> bool:
        """判断是否需要翻译"""
        if not zh_value:
            return True

        if self.is_english_text(zh_value):
            return True

        return False

    def create_batch_prompt(self, items: List[TranslationItem]) -> str:
        """为批量翻译创建提示词"""

        # 构建项目列表
        items_text = ""
        for i, item in enumerate(items, 1):
            items_text += f"{i}. Section: {item.section}, Key: {item.key}\n"
            items_text += f"   英文: {item.en_value}\n\n"

        prompt = f"""请将以下游戏文本从英文翻译成简体中文。要求：

重要规则：
1. 保持准确的技术含义和游戏术语
2. 保持格式标记不变（如[color=red]、[item=...]、[fluid=...]、[entity=...]、[font=...]、[img=...]等）
3. 在准确的基础上，尽量让翻译有趣、生动、有游戏感
4. 可以适当加入幽默感，但不要过度，以免失去原文的专业和神秘氛围
5. 保持文本的流畅性和可读性

游戏背景：《异星工厂》是一款科幻/工业自动化游戏，主题包括科技、工厂、自动化、神秘、哲学等。

请按以下格式回复，严格保持编号对应：
1. 中文翻译：[翻译结果1]
2. 中文翻译：[翻译结果2]
...

需要翻译的文本：
{items_text}

请开始翻译："""

        return prompt

    def parse_batch_response(
        self, response_text: str, items: List[TranslationItem]
    ) -> Dict[int, str]:
        """解析批量翻译的响应"""
        translations = {}

        # 尝试按编号解析
        lines = response_text.strip().split("\n")
        for line in lines:
            # 匹配 "1. 中文翻译：xxx" 或 "1: xxx" 或 "1. xxx"
            match = re.match(
                r"^\s*(\d+)\.?\s*(?:中文翻译：|翻译：|:)?\s*(.+)$", line.strip()
            )
            if match:
                idx = int(match.group(1)) - 1  # 转换为0-based索引
                if 0 <= idx < len(items):
                    translations[idx] = match.group(2).strip()

        # 如果按编号解析失败，尝试按行顺序解析
        if len(translations) != len(items):
            translations = {}
            for i, line in enumerate(lines):
                if i < len(items):
                    # 清理行
                    line = line.strip()
                    # 移除可能的编号前缀
                    line = re.sub(r"^\d+[\.:]\s*", "", line)
                    # 移除可能的"中文翻译："前缀
                    line = re.sub(r"^中文翻译：", "", line)
                    line = re.sub(r"^翻译：", "", line)
                    translations[i] = line.strip()

        return translations

    def translate_batch(self, items: List[TranslationItem]) -> Dict[int, str]:
        """翻译一批文本"""

        # 检查缓存
        cached_translations = {}
        remaining_items = []
        remaining_indices = []

        for i, item in enumerate(items):
            cache_key = f"{item.section}:{item.key}:{item.en_value}"
            if cache_key in self.translation_cache:
                cached_translations[i] = self.translation_cache[cache_key]
            else:
                remaining_items.append(item)
                remaining_indices.append(i)

        # 如果没有需要翻译的项，直接返回缓存
        if not remaining_items:
            return cached_translations

        # 构建批量提示词
        prompt = self.create_batch_prompt(remaining_items)

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            response = requests.post(
                self.api_url,
                headers=headers,
                json={
                    "model": self.model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "temperature": self.translation_options.get("temperature", 0.1),
                    "top_p": self.translation_options.get("top_p", 0.9),
                    "max_tokens": 4000,  # 增加token限制以容纳批量翻译
                },
                timeout=self.translation_options.get("timeout", 120),  # 增加超时时间
            )

            if response.status_code == 200:
                result = response.json()
                # DeepSeek API返回格式: choices[0].message.content
                if "choices" in result and len(result["choices"]) > 0:
                    translated_text = (
                        result["choices"][0]
                        .get("message", {})
                        .get("content", "")
                        .strip()
                    )
                else:
                    # 备用方案
                    translated_text = result.get("response", "").strip()

                # 解析批量响应
                batch_translations = self.parse_batch_response(
                    translated_text, remaining_items
                )

                # 合并结果并更新缓存
                all_translations = cached_translations.copy()
                for idx_in_remaining, translation in batch_translations.items():
                    if idx_in_remaining < len(remaining_indices):
                        original_idx = remaining_indices[idx_in_remaining]
                        item = remaining_items[idx_in_remaining]

                        if translation:
                            all_translations[original_idx] = translation
                            # 更新缓存
                            cache_key = f"{item.section}:{item.key}:{item.en_value}"
                            self.translation_cache[cache_key] = translation
                        else:
                            # 翻译失败，使用原文
                            print(f"警告：翻译返回为空，使用原文：{item.en_value}")
                            all_translations[original_idx] = item.en_value

                return all_translations
            else:
                print(f"警告：API请求失败 ({response.status_code})")
                # 返回缓存的结果，对于未缓存的项使用原文
                all_translations = cached_translations.copy()
                for i, idx in enumerate(remaining_indices):
                    all_translations[idx] = remaining_items[i].en_value
                return all_translations

        except Exception as e:
            print(f"警告：翻译失败 ({e})")
            # 返回缓存的结果，对于未缓存的项使用原文
            all_translations = cached_translations.copy()
            for i, idx in enumerate(remaining_indices):
                all_translations[idx] = remaining_items[i].en_value
            return all_translations

    def translate_items(self, items: List[TranslationItem]) -> List[str]:
        """翻译所有项目，使用批量处理和并发"""

        if not items:
            return []

        # 按批次分组
        batches = []
        for i in range(0, len(items), self.batch_size):
            batch = items[i : i + self.batch_size]
            batches.append(batch)

        print(f"总共 {len(items)} 个词条，分成 {len(batches)} 个批次")

        # 使用线程池并发处理批次
        all_translations: List[Optional[str]] = [None] * len(items)

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_workers
        ) as executor:
            # 提交所有批次任务
            future_to_batch = {}
            for batch_idx, batch in enumerate(batches):
                start_idx = batch_idx * self.batch_size
                future = executor.submit(self.translate_batch, batch)
                future_to_batch[future] = (batch_idx, start_idx, batch)

            # 处理完成的任务
            for future in concurrent.futures.as_completed(future_to_batch):
                batch_idx, start_idx, batch = future_to_batch[future]
                try:
                    batch_results = future.result()
                    # 将结果放入正确的位置
                    for relative_idx, translation in batch_results.items():
                        absolute_idx = start_idx + relative_idx
                        if absolute_idx < len(all_translations):
                            all_translations[absolute_idx] = translation

                    print(f"批次 {batch_idx + 1}/{len(batches)} 完成")
                except Exception as e:
                    print(f"批次 {batch_idx + 1} 处理失败: {e}")
                    # 对于失败的批次，使用原文
                    for i in range(len(batch)):
                        absolute_idx = start_idx + i
                        if absolute_idx < len(all_translations):
                            all_translations[absolute_idx] = batch[i].en_value

        # 确保所有项都有翻译
        final_translations: List[str] = []
        for i in range(len(all_translations)):
            translation = all_translations[i]
            if translation is None:
                final_translations.append(items[i].en_value)
            else:
                final_translations.append(translation)

        return final_translations


def parse_cfg_file(
    filepath: Path,
) -> Tuple[
    Dict[str, Dict[str, str]],
    Set[Tuple[str, str]],
    List[str],
    Dict[Tuple[str, str], int],
]:
    """
    解析 .cfg 文件，返回：
    1. 字典结构：{section: {key: value}}
    2. 被注释掉的键集合：{(section, key)}
    3. 文件的原始行列表（用于保持格式）
    4. 键值对在文件中的行索引：{(section, key): line_number}
    """
    sections: Dict[str, Dict[str, str]] = {}
    current_section = None
    commented_keys: Set[Tuple[str, str]] = set()
    original_lines: List[str] = []

    # 存储每个键值对在文件中的行索引
    key_line_indices: Dict[Tuple[str, str], int] = {}

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        # 尝试其他编码
        with open(filepath, "r", encoding="latin-1") as f:
            lines = f.readlines()

    for line_num, line in enumerate(lines):
        original_lines.append(line)
        line_content = line.rstrip("\n")

        # 跳过空行
        if not line_content.strip():
            continue

        # 检查是否是节定义 [section-name]
        section_match = re.match(r"^\s*\[([^\]]+)\]\s*$", line_content)
        if section_match:
            current_section = section_match.group(1)
            sections[current_section] = {}
            continue

        # 检查是否是键值对
        if current_section is not None:
            # 检查是否是被注释掉的键值对（以 ## 开头）
            if line_content.strip().startswith("##"):
                # 移除注释符号并尝试解析
                clean_line = line_content.strip()[2:].strip()
                kv_match = re.match(r"^([^=]+)=(.*)$", clean_line)
                if kv_match:
                    key = kv_match.group(1).strip()
                    # 记录这个键是被注释掉的
                    commented_keys.add((current_section, key))
                    # 存储值
                    sections[current_section][key] = kv_match.group(2).strip()
                    key_line_indices[(current_section, key)] = line_num
            else:
                # 检查是否是普通键值对
                kv_match = re.match(r"^\s*([^=]+)=(.*)$", line_content)
                if kv_match:
                    key = kv_match.group(1).strip()
                    value = kv_match.group(2).strip()
                    sections[current_section][key] = value
                    key_line_indices[(current_section, key)] = line_num

    return sections, commented_keys, original_lines, key_line_indices


def get_zh_filename(en_filename: str) -> str:
    """根据英文文件名获取对应的中文文件名"""
    # 特殊文件名映射
    filename_map = {
        "lang_en.cfg": "lang_zh-CN.cfg",
        # 可以添加其他映射
    }
    return filename_map.get(en_filename, en_filename)


def collect_translation_items(
    en_sections: Dict[str, Dict[str, str]],
    en_commented: Set[Tuple[str, str]],
    en_key_indices: Dict[Tuple[str, str], int],
    zh_sections: Dict[str, Dict[str, str]],
    zh_commented: Set[Tuple[str, str]],
    translator: BatchTranslator,
) -> List[TranslationItem]:
    """收集需要翻译的项目"""

    items = []

    # 首先收集所有需要处理的键，按它们在英文文件中的出现顺序排序
    all_keys = []
    for (section, key), line_num in en_key_indices.items():
        all_keys.append((line_num, section, key))

    # 按行号排序
    all_keys.sort()

    # 收集需要翻译的项目
    for line_num, section, key in all_keys:
        en_value = en_sections.get(section, {}).get(key)
        if en_value is None:
            continue

        is_commented_in_en = (section, key) in en_commented

        # 检查中文文件中是否存在
        zh_value = zh_sections.get(section, {}).get(key)
        is_commented_in_zh = (section, key) in zh_commented

        # 判断是否需要翻译
        should_translate = translator.needs_translation(en_value, zh_value)

        if should_translate:
            item = TranslationItem(
                section=section,
                key=key,
                en_value=en_value,
                zh_value=zh_value,
                is_commented=is_commented_in_en,
                line_num=line_num,
                needs_translation=True,
            )
            items.append(item)

    return items


def update_zh_file(
    zh_file: Path,
    items: List[TranslationItem],
    translations: List[str],
    zh_sections: Dict[str, Dict[str, str]],
    zh_commented: Set[Tuple[str, str]],
    zh_lines: List[str],
    zh_key_indices: Dict[Tuple[str, str], int],
    backup: bool = True,
) -> Tuple[int, int, int]:
    """更新中文文件"""

    # 创建备份
    if backup and zh_file.exists():
        backup_file = zh_file.with_suffix(zh_file.suffix + ".backup")
        shutil.copy2(zh_file, backup_file)
        print(f"已创建备份: {backup_file.name}")

    # 统计
    added_count = 0
    updated_count = 0
    kept_count = 0

    # 用于存储需要添加的新行
    new_lines = zh_lines.copy()

    # 处理每个翻译项
    for item, translation in zip(items, translations):
        section = item.section
        key = item.key
        is_commented = item.is_commented

        # 检查中文文件中是否存在
        if (section, key) in zh_key_indices:
            # 键已存在，更新行
            zh_line_num = zh_key_indices[(section, key)]
            is_commented_in_zh = (section, key) in zh_commented

            if is_commented_in_zh:
                new_lines[zh_line_num] = f"##{key}={translation}\n"
            else:
                new_lines[zh_line_num] = f"{key}={translation}\n"

            if item.zh_value is None:
                added_count += 1
            else:
                updated_count += 1
        else:
            # 键不存在，需要添加
            # 找到在中文文件中插入的位置
            # 首先检查这个section是否存在
            if section not in zh_sections:
                # section不存在，需要添加整个section
                # 找到文件末尾或合适的位置插入
                insert_pos = len(new_lines)

                # 尝试在文件末尾添加，但在最后一个section之后
                # 简单实现：添加到文件末尾

                # 添加空行（如果最后一行不是空行）
                if new_lines and new_lines[-1].strip() != "":
                    new_lines.append("\n")

                # 添加section头
                new_lines.append(f"[{section}]\n")

                # 添加键值对
                if is_commented:
                    new_lines.append(f"##{key}={translation}\n")
                else:
                    new_lines.append(f"{key}={translation}\n")

                # 更新zh_sections和zh_key_indices
                if section not in zh_sections:
                    zh_sections[section] = {}
                zh_sections[section][key] = translation
                zh_key_indices[(section, key)] = len(new_lines) - 1

                added_count += 1
            else:
                # section存在，但key不存在
                # 找到section的结束位置（下一个section开始或文件结束）
                section_start = -1
                for i, line in enumerate(new_lines):
                    if re.match(rf"^\s*\[{re.escape(section)}\]\s*$", line.strip()):
                        section_start = i
                        break

                if section_start >= 0:
                    # 找到section开始位置，找到section结束位置
                    section_end = len(new_lines)
                    for i in range(section_start + 1, len(new_lines)):
                        if re.match(r"^\s*\[[^\]]+\]\s*$", new_lines[i].strip()):
                            section_end = i
                            break

                    # 在section结束前插入
                    insert_pos = section_end

                    # 在插入前添加空行（如果前一行不是空行）
                    if insert_pos > 0 and new_lines[insert_pos - 1].strip() != "":
                        new_lines.insert(insert_pos, "\n")
                        insert_pos += 1

                    # 插入键值对
                    if is_commented:
                        new_lines.insert(insert_pos, f"##{key}={translation}\n")
                    else:
                        new_lines.insert(insert_pos, f"{key}={translation}\n")

                    # 更新zh_key_indices（需要更新所有后续行的索引）
                    # 简单实现：重新构建索引
                    zh_key_indices.clear()
                    for i, line in enumerate(new_lines):
                        line_content = line.rstrip("\n")
                        if line_content.strip().startswith("##"):
                            clean_line = line_content.strip()[2:].strip()
                            kv_match = re.match(r"^([^=]+)=(.*)$", clean_line)
                            if kv_match:
                                key_found = kv_match.group(1).strip()
                                zh_key_indices[(section, key_found)] = i
                                zh_commented.add((section, key_found))
                        else:
                            kv_match = re.match(r"^\s*([^=]+)=(.*)$", line_content)
                            if kv_match:
                                key_found = kv_match.group(1).strip()
                                zh_key_indices[(section, key_found)] = i

                    added_count += 1

    # 写入文件
    with open(zh_file, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    return added_count, updated_count, kept_count


def create_zh_file_from_en(en_file: Path, zh_file: Path) -> int:
    """
    从英文文件创建中文文件（如果中文文件不存在）
    返回：添加的词条数
    """
    # 直接复制英文文件，保持完全相同的格式
    try:
        with open(en_file, "r", encoding="utf-8") as f:
            en_content = f.read()
    except UnicodeDecodeError:
        with open(en_file, "r", encoding="latin-1") as f:
            en_content = f.read()

    with open(zh_file, "w", encoding="utf-8") as f:
        f.write(en_content)

    # 统计英文文件中的词条数
    en_sections, _, _, _ = parse_cfg_file(en_file)
    total_keys = 0
    for section in en_sections:
        total_keys += len(en_sections[section])

    return total_keys


def translate_file(
    en_file: Path, zh_file: Path, backup: bool = True
) -> Tuple[int, int, int]:
    """
    翻译英文词条到中文文件中
    返回：(新增翻译数, 更新翻译数, 保留翻译数)
    """
    # 创建批量翻译器
    translator = BatchTranslator(batch_size=20, max_workers=5)

    # 解析文件
    en_sections, en_commented, en_lines, en_key_indices = parse_cfg_file(en_file)
    zh_sections, zh_commented, zh_lines, zh_key_indices = parse_cfg_file(zh_file)

    # 收集需要翻译的项目
    items = collect_translation_items(
        en_sections, en_commented, en_key_indices, zh_sections, zh_commented, translator
    )

    if not items:
        print(f"无需翻译，所有翻译都已是最新")
        return 0, 0, len(en_key_indices)

    print(f"需要翻译 {len(items)} 个词条")

    # 批量翻译
    translations = translator.translate_items(items)

    # 更新中文文件
    added, updated, kept = update_zh_file(
        zh_file,
        items,
        translations,
        zh_sections,
        zh_commented,
        zh_lines,
        zh_key_indices,
        backup,
    )

    # 计算保留的词条数
    total_keys = len(en_key_indices)
    kept_count = total_keys - added - updated

    return added, updated, kept_count


def main():
    """主函数"""

    base_dir = Path(__file__).parent.parent
    en_dir = base_dir / "locale" / "en"
    zh_dir = base_dir / "locale" / "zh-CN"

    if not en_dir.exists():
        print(f"错误: 英文目录不存在: {en_dir}")
        return

    # 如果中文目录不存在，创建它
    zh_dir.mkdir(exist_ok=True)

    # 获取所有英文 .cfg 文件
    en_files = list(en_dir.glob("*.cfg"))

    if not en_files:
        print(f"错误: 在 {en_dir} 中没有找到 .cfg 文件")
        return

    print(f"开始翻译...")
    print(f"英文目录: {en_dir}")
    print(f"中文目录: {zh_dir}")
    print(f"找到 {len(en_files)} 个英文文件")
    print()

    total_added = 0
    total_updated = 0
    total_kept = 0
    total_created = 0

    for en_file in en_files:
        en_filename = en_file.name
        zh_filename = get_zh_filename(en_filename)
        zh_file = zh_dir / zh_filename

        print(f"处理: {en_filename} -> {zh_filename}")
        print("-" * 60)

        if not zh_file.exists():
            # 中文文件不存在，从英文文件创建
            print(f"中文文件不存在，正在创建...")
            added = create_zh_file_from_en(en_file, zh_file)
            total_created += 1
            print(f"已创建文件，添加了 {added} 个词条")
            print(f"现在开始翻译新创建的文件...")

            # 创建文件后立即进行翻译
            added, updated, kept = translate_file(en_file, zh_file)
            total_added += added
            total_updated += updated
            total_kept += kept

            if added > 0 or updated > 0:
                print(
                    f"新增 {added} 个翻译，更新 {updated} 个翻译，保留 {kept} 个现有翻译"
                )
            else:
                print(f"无需更新，所有翻译都已是最新")
        else:
            # 中文文件存在，翻译词条
            added, updated, kept = translate_file(en_file, zh_file)
            total_added += added
            total_updated += updated
            total_kept += kept

            if added > 0 or updated > 0:
                print(
                    f"新增 {added} 个翻译，更新 {updated} 个翻译，保留 {kept} 个现有翻译"
                )
            else:
                print(f"无需更新，所有翻译都已是最新")

        print()

    # 输出汇总信息
    print("=" * 60)
    print("汇总:")
    print("=" * 60)
    print(f"总共处理的文件: {len(en_files)}")
    print(f"新创建的中文文件: {total_created}")
    print(f"新增的翻译总数: {total_added}")
    print(f"更新的翻译总数: {total_updated}")
    print(f"保留的翻译总数: {total_kept}")

    if total_created > 0:
        print(f"\n注意: 新创建的文件已自动翻译完成。")

    print(f"\n完成!")


if __name__ == "__main__":
    main()
