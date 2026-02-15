#!/usr/bin/env python3
"""
CFG 文件读写模块
提供解析和更新 .cfg 文件的通用功能
"""

import re
import shutil
from pathlib import Path
from typing import Dict, List, Tuple, Set, Optional


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


def update_cfg_file(
    cfg_file: Path,
    updates: List[Tuple[str, str, str, bool]],  # (section, key, value, is_commented)
    cfg_sections: Dict[str, Dict[str, str]],
    cfg_commented: Set[Tuple[str, str]],
    cfg_lines: List[str],
    cfg_key_indices: Dict[Tuple[str, str], int],
    backup: bool = True,
) -> Tuple[int, int, int]:
    """
    更新 CFG 文件（通用函数，与 AI 无关）

    Args:
        cfg_file: CFG 文件路径
        updates: 更新列表，每个元素为 (section, key, value, is_commented)
        cfg_sections: CFG 文件的节字典
        cfg_commented: CFG 文件中被注释的键集合
        cfg_lines: CFG 文件的原始行列表
        cfg_key_indices: CFG 文件中键的行索引
        backup: 是否创建备份

    Returns:
        (新增条目数, 更新条目数, 保留条目数)
    """
    # 创建备份
    if backup and cfg_file.exists():
        backup_file = cfg_file.with_suffix(cfg_file.suffix + ".backup")
        shutil.copy2(cfg_file, backup_file)
        print(f"已创建备份: {backup_file.name}")

    # 统计
    added_count = 0
    updated_count = 0
    kept_count = 0

    # 用于存储需要添加的新行
    new_lines = cfg_lines.copy()

    # 处理每个更新项
    for section, key, value, is_commented in updates:
        # 检查文件中是否存在
        if (section, key) in cfg_key_indices:
            # 键已存在，更新行
            line_num = cfg_key_indices[(section, key)]
            is_commented_in_file = (section, key) in cfg_commented

            if is_commented_in_file:
                new_lines[line_num] = f"##{key}={value}\n"
            else:
                new_lines[line_num] = f"{key}={value}\n"

            # 检查是新增还是更新
            # 这里简化处理：如果原值存在且不同，则认为是更新
            # 实际使用中可能需要更精确的判断
            updated_count += 1
        else:
            # 键不存在，需要添加
            # 首先检查这个section是否存在
            if section not in cfg_sections:
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
                    new_lines.append(f"##{key}={value}\n")
                else:
                    new_lines.append(f"{key}={value}\n")

                # 更新cfg_sections和cfg_key_indices
                if section not in cfg_sections:
                    cfg_sections[section] = {}
                cfg_sections[section][key] = value
                cfg_key_indices[(section, key)] = len(new_lines) - 1

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
                        new_lines.insert(insert_pos, f"##{key}={value}\n")
                    else:
                        new_lines.insert(insert_pos, f"{key}={value}\n")

                    # 更新cfg_key_indices（需要更新所有后续行的索引）
                    # 简单实现：重新构建索引
                    cfg_key_indices.clear()
                    for i, line in enumerate(new_lines):
                        line_content = line.rstrip("\n")
                        if line_content.strip().startswith("##"):
                            clean_line = line_content.strip()[2:].strip()
                            kv_match = re.match(r"^([^=]+)=(.*)$", clean_line)
                            if kv_match:
                                key_found = kv_match.group(1).strip()
                                cfg_key_indices[(section, key_found)] = i
                                cfg_commented.add((section, key_found))
                        else:
                            kv_match = re.match(r"^\s*([^=]+)=(.*)$", line_content)
                            if kv_match:
                                key_found = kv_match.group(1).strip()
                                cfg_key_indices[(section, key_found)] = i

                    added_count += 1

    # 写入文件
    with open(cfg_file, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    return added_count, updated_count, kept_count


# 导出常用函数
__all__ = [
    "parse_cfg_file",
    "get_zh_filename",
    "create_zh_file_from_en",
    "update_cfg_file",
]
