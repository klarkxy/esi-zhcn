#!/usr/bin/env python3
"""
带AI翻译功能的高频名词/词组提取工具
从所有en的cfg文件中提取value，分析高频名词/词组，并用AI翻译
"""

import re
import sys
import csv
from pathlib import Path
from typing import Dict, List
from collections import Counter

# 添加scripts目录到路径，以便导入现有模块
script_dir = Path(__file__).parent
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

try:
    from cfg_io import parse_cfg_file
    from ai_translator import BatchTranslator, is_english_text
except ImportError as e:
    print(f"导入模块失败: {e}")
    print("请确保 cfg_io.py 和 ai_translator.py 在 scripts 目录中")
    sys.exit(1)


def extract_values_from_cfg_files(en_dir: Path) -> List[str]:
    """
    从所有en的cfg文件中提取所有value
    """
    all_values = []

    if not en_dir.exists() or not en_dir.is_dir():
        print(f"目录不存在: {en_dir}")
        return all_values

    # 遍历所有.cfg文件
    for cfg_file in en_dir.glob("*.cfg"):
        print(f"处理文件: {cfg_file.name}")

        try:
            sections, commented_keys, original_lines, key_indices = parse_cfg_file(
                cfg_file
            )

            # 提取所有value
            for section in sections:
                for key, value in sections[section].items():
                    if value and value.strip():
                        all_values.append(value.strip())
        except Exception as e:
            print(f"处理文件 {cfg_file.name} 时出错: {e}")

    print(f"总共提取了 {len(all_values)} 个value")
    return all_values


def clean_text(text: str) -> str:
    """
    清理文本：移除游戏标记和特殊字符
    """
    # 移除 [color=...], [item=...], [fluid=...], [entity=...], [font=...], [img=...] 等标记
    cleaned = re.sub(r"\[[^\]]+\]", " ", text)

    # 移除 __xxx__ 模式的变量
    cleaned = re.sub(r"__[A-Za-z0-9_]+__", " ", cleaned)

    # 移除HTML标签
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)

    # 移除特殊字符但保留连字符（用于复合词）
    cleaned = re.sub(r"[^\w\s\-]", " ", cleaned)

    # 将多个空格合并为一个
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return cleaned


def is_common_unambiguous_term(term: str) -> bool:
    """
    判断是否为常见无歧义的术语（不需要翻译）
    这些词在游戏上下文中通常没有歧义，可以直接使用
    """
    # 常见无歧义的游戏术语
    common_unambiguous_terms = {
        # 基础资源
        "energy",
        "power",
        "fuel",
        "water",
        "oil",
        "gas",
        "coal",
        "stone",
        "iron",
        "copper",
        "steel",
        "uranium",
        "gold",
        "lead",
        "carbon",
        "sulfur",
        "lithium",
        "neodymium",
        "aluminum",
        "titanium",
        # 基础概念
        "age",
        "time",
        "speed",
        "heat",
        "cold",
        "light",
        "dark",
        "new",
        "old",
        "big",
        "small",
        "large",
        "heavy",
        "light",
        "fast",
        "slow",
        "high",
        "low",
        "hot",
        "cold",
        "warm",
        "cool",
        "dry",
        "wet",
        "hard",
        "soft",
        "strong",
        "weak",
        # 科技相关
        "tech",
        "science",
        "research",
        "data",
        "technology",
        "advanced",
        "basic",
        "simple",
        "complex",
        "efficient",
        "efficiency",
        "productivity",
        "quality",
        # 游戏机制
        "game",
        "player",
        "level",
        "score",
        "point",
        "value",
        "count",
        "total",
        "amount",
        "number",
        "rate",
        "ratio",
        "percent",
        "percentage",
        "max",
        "min",
        "average",
        "normal",
        "standard",
        "special",
        "unique",
        "rare",
        "common",
        # 物理/化学
        "mass",
        "weight",
        "volume",
        "density",
        "pressure",
        "temperature",
        "energy",
        "power",
        "force",
        "pressure",
        "velocity",
        "acceleration",
        "gravity",
        "chemical",
        "physical",
        "atomic",
        "nuclear",
        "fusion",
        "fission",
        # 数学/逻辑
        "logic",
        "signal",
        "circuit",
        "network",
        "system",
        "matrix",
        "vector",
        "scalar",
        "tensor",
        "function",
        "variable",
        "constant",
        "parameter",
        # 方向/位置
        "north",
        "south",
        "east",
        "west",
        "up",
        "down",
        "left",
        "right",
        "front",
        "back",
        "top",
        "bottom",
        "center",
        "middle",
        "edge",
        "corner",
        # 颜色
        "red",
        "green",
        "blue",
        "yellow",
        "black",
        "white",
        "gray",
        "brown",
        "orange",
        "purple",
        "pink",
        "cyan",
        "magenta",
        # 时间
        "second",
        "minute",
        "hour",
        "day",
        "week",
        "month",
        "year",
        # 单位
        "meter",
        "kilometer",
        "centimeter",
        "millimeter",
        "gram",
        "kilogram",
        "liter",
        "milliliter",
        "watt",
        "kilowatt",
        "megawatt",
        "gigawatt",
        "volt",
        "ampere",
        "ohm",
        "hertz",
        "joule",
        "calorie",
        # 游戏特定但无歧义
        "ore",
        "ingot",
        "plate",
        "rod",
        "wire",
        "cable",
        "pipe",
        "tank",
        "container",
        "belt",
        "inserter",
        "assembler",
        "furnace",
        "reactor",
        "generator",
        "turbine",
        "drill",
        "miner",
        "pump",
        "valve",
        "filter",
        "mixer",
        "separator",
    }

    return term.lower() in common_unambiguous_terms


def is_meaningful_term(term: str) -> bool:
    """
    判断一个术语是否有意义（需要提取和可能翻译）
    """
    # 常见停用词
    stop_words = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "shall",
        "should",
        "may",
        "might",
        "must",
        "can",
        "could",
        "it",
        "its",
        "they",
        "them",
        "their",
        "this",
        "that",
        "these",
        "those",
        "as",
        "from",
        "if",
        "then",
        "than",
        "so",
        "such",
        "here",
        "there",
        "when",
        "where",
        "why",
        "how",
        "all",
        "any",
        "both",
        "each",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "no",
        "nor",
        "not",
        "only",
        "own",
        "same",
        "too",
        "very",
        "s",
        "t",
        "just",
        "also",
        "now",
        "into",
        "out",
        "up",
        "down",
        "over",
        "under",
        "again",
        "further",
        "then",
        "once",
        "more",
        "here",
        "there",
        "why",
        "how",
        "when",
        "where",
        "what",
        "which",
        "who",
        "whom",
        "whose",
        "whether",
        "while",
        "after",
        "before",
        "during",
        "since",
        "until",
        "because",
        "although",
        "though",
        "even",
        "if",
        "unless",
        "while",
        "whereas",
        "although",
        "you",
        "your",
        "me",
        "my",
        "mine",
        "we",
        "us",
        "our",
        "ours",
        "he",
        "him",
        "his",
        "she",
        "her",
        "hers",
        "its",
        "they",
        "them",
        "theirs",
        "this",
        "that",
        "these",
        "those",
        "am",
        "is",
        "are",
        "was",
        "were",
        "be",
        "being",
        "been",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "shall",
        "should",
        "may",
        "might",
        "must",
        "can",
        "could",
        "ought",
        "need",
        "dare",
        "used",
        "through",
        "about",
        "above",
        "across",
        "after",
        "against",
        "along",
        "among",
        "around",
        "before",
        "behind",
        "below",
        "beneath",
        "beside",
        "between",
        "beyond",
        "during",
        "except",
        "inside",
        "outside",
        "since",
        "throughout",
        "toward",
        "underneath",
        "until",
        "upon",
        "within",
        "without",
    }

    # 检查是否为停用词
    if term.lower() in stop_words:
        return False

    # 检查是否为常见无歧义术语
    if is_common_unambiguous_term(term):
        return False

    # 检查是否为纯数字
    if term.isdigit():
        return False

    # 检查是否为单个字符 - 过滤掉所有单个字符
    # 即使是大写字母如"C"（可能表示Celsius），在游戏术语中通常没有独立意义
    # 它们应该与其他词组合才有意义，如"coolant C"或"C type"
    if len(term) == 1:
        return False

    # 检查是否太短（<2个字符）
    if len(term) < 2:
        return False

    # 检查是否包含数字（如"1000C"，但允许"MK3"这样的）
    if any(char.isdigit() for char in term):
        # 允许包含数字的常见模式
        if re.match(r"^[A-Za-z]+\d+$", term) or re.match(r"^\d+[A-Za-z]+$", term):
            return True
        return False

    return True


def extract_meaningful_terms(text: str) -> List[str]:
    """
    提取有意义的术语
    优化：如果单词已经包含在更长的短语中，则过滤掉该单词
    """
    cleaned = clean_text(text)
    if not cleaned:
        return []

    # 按空格分割单词
    words = cleaned.split()

    # 过滤单词
    filtered_words = []
    for word in words:
        if is_meaningful_term(word):
            filtered_words.append(word)

    # 提取短语（2-3个词的组合）
    phrases = []
    for i in range(len(filtered_words) - 1):
        # 两个词的组合
        if i + 1 < len(filtered_words):
            phrase2 = f"{filtered_words[i]} {filtered_words[i+1]}"
            # 检查短语是否有意义
            if is_meaningful_phrase(phrase2):
                phrases.append(phrase2)

        # 三个词的组合
        if i + 2 < len(filtered_words):
            phrase3 = f"{filtered_words[i]} {filtered_words[i+1]} {filtered_words[i+2]}"
            if is_meaningful_phrase(phrase3):
                phrases.append(phrase3)

    # 优化：过滤掉已经包含在更长短语中的单词
    # 例如：如果已有"Liquid coolant"，则不需要单独的"Liquid"
    optimized_terms = []

    # 首先添加所有短语（从长到短排序）
    sorted_phrases = sorted(phrases, key=len, reverse=True)
    for phrase in sorted_phrases:
        # 检查这个短语是否已经被包含在其他更长的短语中
        is_subphrase = False
        for existing_phrase in optimized_terms:
            if phrase in existing_phrase and phrase != existing_phrase:
                is_subphrase = True
                break
        if not is_subphrase:
            optimized_terms.append(phrase)

    # 然后添加单词，但只添加那些没有被任何短语包含的单词
    for word in filtered_words:
        is_contained = False
        for phrase in optimized_terms:
            # 检查单词是否作为独立单词出现在短语中
            # 使用正则表达式确保是完整的单词，而不是部分匹配
            if re.search(rf"\b{re.escape(word)}\b", phrase):
                is_contained = True
                break
        if not is_contained:
            optimized_terms.append(word)

    return optimized_terms


def is_meaningful_phrase(phrase: str) -> bool:
    """
    判断一个短语是否有意义
    """
    words = phrase.split()

    # 检查每个单词是否都有意义
    for word in words:
        if not is_meaningful_term(word):
            return False

    # 检查短语是否包含常见无意义组合
    meaningless_combinations = {
        "new one",
        "one new",
        "you can",
        "can you",
        "you will",
        "will you",
        "you have",
        "have you",
        "you are",
        "are you",
        "you were",
        "were you",
        "you should",
        "should you",
        "you could",
        "could you",
        "you would",
        "would you",
        "you may",
        "may you",
        "you might",
        "might you",
        "you must",
        "must you",
        "you need",
        "need you",
        "you want",
        "want you",
    }

    if phrase.lower() in meaningless_combinations:
        return False

    return True


def analyze_frequent_terms(values: List[str], min_frequency: int = 5) -> Dict[str, int]:
    """
    分析高频术语
    """
    all_terms = []

    print("提取有意义的术语...")
    for i, value in enumerate(values):
        if (i + 1) % 200 == 0:
            print(f"  已处理 {i + 1}/{len(values)} 个value")

        terms = extract_meaningful_terms(value)
        all_terms.extend(terms)

    print(f"总共提取了 {len(all_terms)} 个术语")

    # 统计频率
    term_counter = Counter(all_terms)

    # 过滤出高频词汇
    frequent_terms = {
        term: count for term, count in term_counter.items() if count >= min_frequency
    }

    # 按频率排序
    sorted_terms = dict(
        sorted(frequent_terms.items(), key=lambda x: x[1], reverse=True)
    )

    return sorted_terms


def translate_terms_with_ai(terms: List[str], batch_size: int = 20) -> Dict[str, str]:
    """
    使用AI翻译术语
    """
    if not terms:
        return {}

    print(f"开始使用AI翻译 {len(terms)} 个术语...")

    try:
        # 创建翻译器
        translator = BatchTranslator(batch_size=batch_size, max_workers=3)

        # 准备翻译项
        from ai_translator import TranslationItem

        translation_items = []
        for term in terms:
            item = TranslationItem(
                section="terms",
                key=term,
                en_value=term,
                zh_value=None,
                is_commented=False,
                line_num=-1,
                needs_translation=True,
            )
            translation_items.append(item)

        # 批量翻译
        translations = translator.translate_items(translation_items)

        # 构建结果字典
        result = {}
        for i, term in enumerate(terms):
            if i < len(translations):
                result[term] = translations[i]
            else:
                result[term] = term  # 翻译失败，使用原文

        return result

    except Exception as e:
        print(f"AI翻译失败: {e}")
        print("将使用术语本身作为翻译结果...")
        # 返回术语本身作为翻译结果
        return {term: term for term in terms}


def save_results_csv(
    terms_freq: Dict[str, int], translations: Dict[str, str], output_file: Path
):
    """
    保存结果到CSV文件（包含翻译）
    """
    with open(output_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        # 写入标题行
        writer.writerow(["英文术语", "出现频率", "中文翻译", "备注"])

        # 按频率排序写入数据
        sorted_terms = sorted(terms_freq.items(), key=lambda x: x[1], reverse=True)
        for term, freq in sorted_terms:
            translation = translations.get(term, term)  # 如果没有翻译，使用原文
            writer.writerow([term, freq, translation, ""])

    print(f"CSV文件已保存: {output_file}")
    print(f"总术语数: {len(terms_freq)}")
    print(f"总出现次数: {sum(terms_freq.values())}")


def save_results_txt(
    terms_freq: Dict[str, int],
    translations: Dict[str, str],
    output_file: Path,
    top_n: int = 200,
):
    """
    保存结果到文本文件（包含翻译）
    """
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("高频名词/词组分析结果（带AI翻译）\n")
        f.write("=" * 60 + "\n\n")

        f.write(f"总术语数: {len(terms_freq)}\n")
        f.write(f"总出现次数: {sum(terms_freq.values())}\n")
        f.write(f"最小频率: {min(terms_freq.values()) if terms_freq else 0}\n")
        f.write(f"最大频率: {max(terms_freq.values()) if terms_freq else 0}\n\n")

        # 按频率排序（前top_n个）
        f.write(f"按频率排序（前{top_n}个）:\n")
        f.write("-" * 80 + "\n")
        f.write(f"{'序号':<4} {'英文术语':<40} {'频率':<8} {'中文翻译':<30}\n")
        f.write("-" * 80 + "\n")

        sorted_terms = sorted(terms_freq.items(), key=lambda x: x[1], reverse=True)
        for i, (term, freq) in enumerate(sorted_terms[:top_n]):
            translation = translations.get(term, term)  # 如果没有翻译，使用原文
            f.write(f"{i+1:<4} {term:<40} {freq:<8} {translation:<30}\n")

        # 按字母排序
        f.write(f"\n\n按字母排序（全部{len(terms_freq)}个）:\n")
        f.write("-" * 80 + "\n")
        f.write(f"{'英文术语':<40} {'频率':<8} {'中文翻译':<30}\n")
        f.write("-" * 80 + "\n")

        for term in sorted(terms_freq.keys()):
            freq = terms_freq[term]
            translation = translations.get(term, term)  # 如果没有翻译，使用原文
            f.write(f"{term:<40} {freq:<8} {translation:<30}\n")

        # 频率分布
        f.write("\n\n频率分布:\n")
        f.write("-" * 40 + "\n")
        freq_dist = Counter(terms_freq.values())
        for freq, count in sorted(freq_dist.items(), reverse=True):
            f.write(f"出现{freq}次的术语: {count}个\n")

        # 翻译统计
        f.write("\n\n翻译统计:\n")
        f.write("-" * 40 + "\n")
        # 统计成功翻译的数量（翻译结果不是原文）
        successful_translations = sum(
            1 for term, trans in translations.items() if trans != term
        )
        f.write(f"成功翻译: {successful_translations}/{len(terms_freq)} 个术语\n")
        if len(terms_freq) > 0:
            f.write(f"翻译成功率: {successful_translations/len(terms_freq)*100:.1f}%\n")


def main():
    """主函数"""
    # 设置路径
    base_dir = Path(__file__).parent.parent
    en_dir = base_dir / "locale" / "en"
    output_csv = base_dir / "名词表.csv"

    print("=" * 70)
    print("高频名词/词组提取工具（带AI翻译功能）")
    print("=" * 70)

    # 1. 提取所有value
    print("\n1. 从cfg文件中提取value...")
    values = extract_values_from_cfg_files(en_dir)

    if not values:
        print("未找到任何value，程序退出")
        return

    # 2. 分析高频术语（最小频率5次）
    print("\n2. 分析高频名词/词组（频率≥5）...")
    frequent_terms = analyze_frequent_terms(values, min_frequency=5)

    if not frequent_terms:
        print("未找到高频术语，程序退出")
        return

    print(f"找到 {len(frequent_terms)} 个高频术语（频率≥5）")

    # 显示前30个高频术语
    print("\n前30个高频术语:")
    print("-" * 60)
    for i, (term, freq) in enumerate(list(frequent_terms.items())[:30]):
        print(f"{i+1:2d}. {term:40s} : {freq}次")

    # 3. 使用AI翻译术语
    print("\n3. 使用AI翻译术语...")
    terms_to_translate = list(frequent_terms.keys())

    translations = translate_terms_with_ai(terms_to_translate, batch_size=10)

    # 4. 保存结果
    print("\n4. 保存结果...")
    save_results_csv(frequent_terms, translations, output_csv)

    print(f"\n完成！")

    # 显示翻译示例
    print("\n翻译示例（前10个）:")
    print("-" * 60)
    sorted_terms = sorted(frequent_terms.items(), key=lambda x: x[1], reverse=True)
    for i, (term, freq) in enumerate(sorted_terms[:10]):
        translation = translations.get(term, term)
        print(f"{term:30s} ({freq}次) -> {translation}")


if __name__ == "__main__":
    main()
