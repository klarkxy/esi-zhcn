# -*- coding: utf-8 -*-
"""主翻译脚本：批量翻译游戏本地化文件"""

from pathlib import Path
from typing import Dict, List, Tuple, Set, Optional
import sys
import json
import datetime

# 导入 AI 翻译模块
try:
    # 添加scripts目录到路径，以便导入ai_translator
    script_dir = Path(__file__).parent
    if str(script_dir) not in sys.path:
        sys.path.insert(0, str(script_dir))

    from ai_translator import TranslationItem, BatchTranslator
    from cfg_io import (
        parse_cfg_file,
        get_zh_filename,
        create_zh_file_from_en,
        update_cfg_file,
    )

    print("已加载 AI 翻译模块和 CFG IO 模块")
except ImportError as e:
    print(f"错误: 无法导入模块: {e}")
    print("请确保 scripts/ai_translator.py 和 scripts/cfg_io.py 文件存在")
    sys.exit(1)


def collect_translation_items(
    en_sections: Dict[str, Dict[str, str]],
    en_commented: Set[Tuple[str, str]],
    en_key_indices: Dict[Tuple[str, str], int],
    zh_sections: Dict[str, Dict[str, str]],
    zh_commented: Set[Tuple[str, str]],
    translator,
) -> List[TranslationItem]:
    """
    收集需要翻译的项目

    Args:
        en_sections: 英文文件的节和键值对
        en_commented: 英文文件中被注释的键
        en_key_indices: 英文文件中键的行号索引
        zh_sections: 中文文件的节和键值对
        zh_commented: 中文文件中被注释的键
        translator: 翻译器实例，用于判断是否需要翻译

    Returns:
        需要翻译的项目列表
    """
    items = []

    # 使用集合来跟踪已经处理过的键，避免重复
    processed_keys = set()

    # 首先收集所有需要处理的键，按它们在英文文件中的出现顺序排序
    all_keys = []
    for (section, key), line_num in en_key_indices.items():
        all_keys.append((line_num, section, key))

    # 按行号排序
    all_keys.sort()

    # 收集需要翻译的项目
    for line_num, section, key in all_keys:
        # 检查是否已经处理过这个键（避免重复）
        key_id = (section, key)
        if key_id in processed_keys:
            print(f"警告: 跳过重复的键: {section}.{key} (行号: {line_num})")
            continue

        processed_keys.add(key_id)

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


# update_zh_file 函数已移动到 cfg_io 模块


# create_zh_file_from_en 函数已移动到 cfg_io 模块


def translate_file(
    en_file: Path,
    zh_file: Path,
    backup: bool = True,
    glossary_path: Optional[str] = None,
    whitelist_path: Optional[str] = None,
) -> Tuple[int, int, int]:
    """
    翻译英文词条到中文文件中

    Args:
        en_file: 英文文件路径
        zh_file: 中文文件路径
        backup: 是否创建备份
        glossary_path: 名词表文件路径
        whitelist_path: 白名单文件路径

    Returns:
        (新增翻译数, 更新翻译数, 保留翻译数)
    """
    # 创建批量翻译器（使用配置文件中的BATCH_SIZE、名词表和白名单）
    translator = BatchTranslator(
        max_workers=5, glossary_path=glossary_path, whitelist_path=whitelist_path
    )

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

    # 将 TranslationItem 列表转换为 update_cfg_file 所需的格式
    updates = []
    for item, translation in zip(items, translations):
        updates.append((item.section, item.key, translation, item.is_commented))

    # 更新中文文件
    added, updated, kept = update_cfg_file(
        zh_file,
        updates,
        zh_sections,
        zh_commented,
        zh_lines,
        zh_key_indices,
        backup,
    )

    # 计算保留的词条数
    total_keys = len(en_key_indices)
    kept_count = total_keys - added - updated

    # 记录翻译日志
    log_translation(en_file, zh_file, items, translations, added, updated, kept_count)

    return added, updated, kept_count


def process_single_file(
    en_file: Path,
    zh_file: Path,
    glossary_str: Optional[str],
    whitelist_str: Optional[str],
    stats: Dict[str, int],
) -> None:
    """
    处理单个文件

    Args:
        en_file: 英文文件路径
        zh_file: 中文文件路径
        glossary_str: 名词表路径字符串
        whitelist_str: 白名单路径字符串
        stats: 统计信息字典
    """
    en_filename = en_file.name
    zh_filename = get_zh_filename(en_filename)

    print(f"处理: {en_filename} -> {zh_filename}")
    print("-" * 60)

    if not zh_file.exists():
        # 中文文件不存在，从英文文件创建
        print(f"中文文件不存在，正在创建...")
        added = create_zh_file_from_en(en_file, zh_file)
        stats["created"] += 1
        print(f"已创建文件，添加了 {added} 个词条")
        print(f"现在开始翻译新创建的文件...")
    else:
        print(f"中文文件已存在，开始翻译...")

    # 翻译文件
    added, updated, kept = translate_file(
        en_file, zh_file, glossary_path=glossary_str, whitelist_path=whitelist_str
    )

    stats["added"] += added
    stats["updated"] += updated
    stats["kept"] += kept

    if added > 0 or updated > 0:
        print(f"新增 {added} 个翻译，更新 {updated} 个翻译，保留 {kept} 个现有翻译")
    else:
        print(f"无需更新，所有翻译都已是最新")

    print()


def main():
    """主函数：批量翻译所有游戏本地化文件"""

    base_dir = Path(__file__).parent.parent
    en_dir = base_dir / "locale" / "en"
    zh_dir = base_dir / "locale" / "zh-CN"

    # 名词表路径
    glossary_path = base_dir / "名词表.txt"
    glossary_str = str(glossary_path) if glossary_path.exists() else None

    # 白名单路径
    whitelist_path = base_dir / "whitelist.txt"
    whitelist_str = str(whitelist_path) if whitelist_path.exists() else None

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
    if glossary_str:
        print(f"使用名词表: {glossary_str}")
    else:
        print(f"警告: 名词表文件不存在，将不使用名词表参考")
    if whitelist_str:
        print(f"使用白名单: {whitelist_str}")
    else:
        print(f"警告: 白名单文件不存在，将不使用白名单")
    print(f"找到 {len(en_files)} 个英文文件")
    print()

    # 初始化统计信息
    stats = {
        "added": 0,
        "updated": 0,
        "kept": 0,
        "created": 0,
    }

    # 处理所有文件
    for en_file in en_files:
        zh_filename = get_zh_filename(en_file.name)
        zh_file = zh_dir / zh_filename
        process_single_file(en_file, zh_file, glossary_str, whitelist_str, stats)

    # 输出汇总信息
    print("=" * 60)
    print("汇总:")
    print("=" * 60)
    print(f"总共处理的文件: {len(en_files)}")
    print(f"新创建的中文文件: {stats['created']}")
    print(f"新增的翻译总数: {stats['added']}")
    print(f"更新的翻译总数: {stats['updated']}")
    print(f"保留的翻译总数: {stats['kept']}")

    if stats["created"] > 0:
        print(f"\n注意: 新创建的文件已自动翻译完成。")

    if glossary_str:
        print(f"\n注意: 翻译时已使用名词表参考，确保术语一致性。")

    if whitelist_str:
        print(f"注意: 翻译时已使用白名单，专有名词将不会被翻译。")

    print(f"\n完成!")


def log_translation(
    en_file: Path,
    zh_file: Path,
    items: List[TranslationItem],
    translations: List[str],
    added: int,
    updated: int,
    kept: int,
) -> None:
    """
    记录翻译日志到logs/目录

    Args:
        en_file: 英文文件路径
        zh_file: 中文文件路径
        items: 翻译项目列表
        translations: 翻译结果列表
        added: 新增翻译数
        updated: 更新翻译数
        kept: 保留翻译数
    """
    # 确保logs目录存在
    logs_dir = Path(__file__).parent.parent / "logs"
    logs_dir.mkdir(exist_ok=True)

    # 生成日志文件名
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"translation_{en_file.stem}_{timestamp}.json"
    log_file = logs_dir / log_filename

    # 准备日志数据
    log_data = {
        "timestamp": datetime.datetime.now().isoformat(),
        "en_file": str(en_file),
        "zh_file": str(zh_file),
        "summary": {
            "total_items": len(items),
            "added": added,
            "updated": updated,
            "kept": kept,
        },
        "translations": [],
    }

    # 添加每个翻译项目的详细信息
    for i, (item, translation) in enumerate(zip(items, translations)):
        translation_entry = {
            "index": i,
            "section": item.section,
            "key": item.key,
            "en_value": item.en_value,
            "previous_zh_value": item.zh_value,
            "new_zh_value": translation,
            "is_commented": item.is_commented,
            "line_num": item.line_num,
        }
        log_data["translations"].append(translation_entry)

    # 写入日志文件
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(log_data, f, ensure_ascii=False, indent=2)

    print(f"翻译日志已保存到: {log_file}")


if __name__ == "__main__":
    main()
