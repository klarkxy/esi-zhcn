#!/usr/bin/env python3
"""
将英文词条合并到中文翻译文件中。
将locale/en/目录下的所有.cfg文件的词条合并到对应的locale/zh-CN/文件中，
如果中文文件中没有对应翻译，则保留英文词条。
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Tuple, Set, Optional
import shutil


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


def merge_translations(
    en_file: Path, zh_file: Path, backup: bool = True
) -> Tuple[int, int]:
    """
    合并英文词条到中文文件中
    返回：(新增词条数, 更新词条数)
    """
    # 解析文件
    en_sections, en_commented, en_lines, en_key_indices = parse_cfg_file(en_file)
    zh_sections, zh_commented, zh_lines, zh_key_indices = parse_cfg_file(zh_file)

    # 创建备份
    if backup and zh_file.exists():
        backup_file = zh_file.with_suffix(zh_file.suffix + ".backup")
        shutil.copy2(zh_file, backup_file)
        print(f"  已创建备份: {backup_file.name}")

    # 统计
    added_count = 0
    updated_count = 0

    # 用于存储需要添加的新行
    new_lines = zh_lines.copy()

    # 按section和key在文件中的出现顺序处理
    # 首先收集所有需要处理的键，按它们在英文文件中的出现顺序排序
    all_keys = []
    for (section, key), line_num in en_key_indices.items():
        all_keys.append((line_num, section, key))

    # 按行号排序
    all_keys.sort()

    # 处理每个键
    for line_num, section, key in all_keys:
        en_value = en_sections.get(section, {}).get(key)
        if en_value is None:
            continue

        is_commented_in_en = (section, key) in en_commented

        # 检查中文文件中是否存在
        zh_value = zh_sections.get(section, {}).get(key)
        is_commented_in_zh = (section, key) in zh_commented

        if zh_value is None:
            # 中文文件中不存在，需要添加
            added_count += 1

            # 找到在中文文件中插入的位置
            # 首先检查这个section是否存在
            if section not in zh_sections:
                # section不存在，需要添加整个section
                # 找到文件末尾或合适的位置插入
                insert_pos = len(new_lines)

                # 尝试在文件末尾添加，但在最后一个section之后
                # 简单实现：添加到文件末尾
                # 更复杂的实现可以尝试保持与英文文件相似的结构

                # 添加空行（如果最后一行不是空行）
                if new_lines and new_lines[-1].strip() != "":
                    new_lines.append("\n")

                # 添加section头
                new_lines.append(f"[{section}]\n")

                # 添加键值对
                if is_commented_in_en:
                    new_lines.append(f"  ##{key}={en_value}\n")
                else:
                    new_lines.append(f"  {key}={en_value}\n")
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
                    if is_commented_in_en:
                        new_lines.insert(insert_pos, f"  ##{key}={en_value}\n")
                    else:
                        new_lines.insert(insert_pos, f"  {key}={en_value}\n")
        else:
            # 中文文件中已存在
            # 根据需求，如果已经有中文翻译，应该保留中文，不更新为英文
            # 所以这里不需要做任何操作
            pass

    # 写入文件
    with open(zh_file, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    return added_count, updated_count


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

    print(f"开始合并翻译...")
    print(f"英文目录: {en_dir}")
    print(f"中文目录: {zh_dir}")
    print(f"找到 {len(en_files)} 个英文文件")
    print()

    total_added = 0
    total_updated = 0
    total_created = 0

    for en_file in en_files:
        en_filename = en_file.name
        zh_filename = get_zh_filename(en_filename)
        zh_file = zh_dir / zh_filename

        print(f"处理: {en_filename} -> {zh_filename}")

        if not zh_file.exists():
            # 中文文件不存在，从英文文件创建
            print(f"  中文文件不存在，正在创建...")
            added = create_zh_file_from_en(en_file, zh_file)
            total_created += 1
            total_added += added
            print(f"  已创建文件，添加了 {added} 个词条")
        else:
            # 中文文件存在，合并词条
            added, updated = merge_translations(en_file, zh_file)
            total_added += added
            total_updated += updated

            if added > 0 or updated > 0:
                print(f"  新增 {added} 个词条，更新 {updated} 个词条")
            else:
                print(f"  无需更新")

        print()

    # 输出汇总信息
    print("=" * 60)
    print("汇总:")
    print("=" * 60)
    print(f"总共处理的文件: {len(en_files)}")
    print(f"新创建的中文文件: {total_created}")
    print(f"新增的词条总数: {total_added}")
    print(f"更新的词条总数: {total_updated}")

    if total_created > 0:
        print(f"\n注意: 新创建的文件包含英文原文作为占位符，需要手动翻译。")

    print(f"\n完成!")


if __name__ == "__main__":
    main()
