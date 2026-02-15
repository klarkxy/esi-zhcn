#!/usr/bin/env python3
"""
AI 翻译模块
提供与 AI API 交互的通用功能，可被多个脚本共享使用
"""

import re
import requests
import concurrent.futures
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


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


class AITranslator:
    """AI 翻译器基类，提供通用的 AI 翻译功能"""

    def __init__(
        self,
        api_key: str,
        api_url: str,
        model_name: str,
        translation_options: Dict[str, Any],
        batch_size: int = 20,
        max_workers: int = 5,
    ):
        """
        初始化 AI 翻译器

        Args:
            api_key: API 密钥
            api_url: API 地址
            model_name: 模型名称
            translation_options: 翻译选项字典
            batch_size: 批量大小
            max_workers: 最大工作线程数
        """
        self.api_key = api_key
        self.api_url = api_url
        self.model_name = model_name
        self.translation_options = translation_options
        self.batch_size = batch_size
        self.max_workers = max_workers

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

        # 检查英文值中是否包含"__xxx__"模式的变量
        # 常见的游戏变量模式：__ENTITY__、__ITEM__、__FLUID__、__1__、__2__、__REMARK_COLOR_BEGIN__、__REMARK_COLOR_END__等
        import re

        # 匹配"__xxx__"模式的变量
        variable_pattern = r"__[A-Za-z0-9_]+__"
        en_variables = re.findall(variable_pattern, en_value)

        if en_variables:
            # 如果英文值包含变量，检查中文值是否也包含这些变量
            if zh_value:
                for var in en_variables:
                    if var not in zh_value:
                        # 中文值缺少英文值中的某个变量，需要重新翻译
                        return True

        return False

    def create_batch_prompt(
        self,
        items: List[TranslationItem],
        game_context: str = "《异星工厂》是一款科幻/工业自动化游戏，主题包括科技、工厂、自动化、神秘、哲学等。",
    ) -> str:
        """
        为批量翻译创建提示词

        Args:
            items: 翻译项列表
            game_context: 游戏背景描述

        Returns:
            格式化后的提示词
        """
        # 构建项目列表
        items_text = ""
        for i, item in enumerate(items, 1):
            items_text += f"{i}. Section: {item.section}, Key: {item.key}\n"
            items_text += f"   英文: {item.en_value}\n\n"

        prompt = f"""请将以下游戏文本从英文翻译成简体中文。要求：

重要规则：
1. 保持准确的技术含义和游戏术语
2. 保持格式标记不变（如[color=red]、[item=...]、[fluid=...]、[entity=...]、[font=...]、[img=...]等）
3. 类似"__xxx__"这样的游戏变量（如__ENTITY__、__ITEM__、__FLUID__、__1__、__2__、__REMARK_COLOR_BEGIN__、__REMARK_COLOR_END__等）不应该被翻译，必须原样保留
4. 在准确的基础上，尽量让翻译有趣、生动、有游戏感
5. 可以适当加入幽默感，但不要过度，以免失去原文的专业和神秘氛围
6. 保持文本的流畅性和可读性

游戏背景：{game_context}

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

    def translate_batch(
        self,
        items: List[TranslationItem],
        game_context: str = "《异星工厂》是一款科幻/工业自动化游戏，主题包括科技、工厂、自动化、神秘、哲学等。",
    ) -> Dict[int, str]:
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
        prompt = self.create_batch_prompt(remaining_items, game_context)

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

    def translate_items(
        self,
        items: List[TranslationItem],
        game_context: str = "《异星工厂》是一款科幻/工业自动化游戏，主题包括科技、工厂、自动化、神秘、哲学等。",
    ) -> List[str]:
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
                future = executor.submit(self.translate_batch, batch, game_context)
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


class BatchTranslator(AITranslator):
    """批量翻译器（兼容旧名称）"""

    def __init__(self, batch_size: int = 20, max_workers: int = 5):
        """
        初始化批量翻译器

        注意：此构造函数从 config.py 加载配置，保持向后兼容性
        """
        import sys
        from pathlib import Path

        # 添加scripts目录到路径，以便导入config
        script_dir = Path(__file__).parent
        if str(script_dir) not in sys.path:
            sys.path.insert(0, str(script_dir))

        try:
            from config import API_KEY, API_URL, MODEL_NAME, TRANSLATION_OPTIONS
        except ImportError:
            print("请复制 scripts/config.py.template 为 scripts/config.py")
            exit(1)

        # 调用父类构造函数
        super().__init__(
            api_key=API_KEY,
            api_url=API_URL,
            model_name=MODEL_NAME,
            translation_options=TRANSLATION_OPTIONS,
            batch_size=batch_size,
            max_workers=max_workers,
        )


# 导出常用类和函数
__all__ = [
    "TranslationItem",
    "AITranslator",
    "BatchTranslator",
    "is_english_text",  # 导出为独立函数
]


# 导出独立函数，方便其他脚本使用
def is_english_text(text: str) -> bool:
    """判断文本是否主要是英文（独立函数版本）"""
    translator = AITranslator(
        api_key="dummy", api_url="", model_name="", translation_options={}
    )
    return translator.is_english_text(text)
