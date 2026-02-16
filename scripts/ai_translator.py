#!/usr/bin/env python3
"""
AI 翻译模块 - 重构版
采用回调机制的 AIClient，负责向 API 批量发送和接收请求
"""

import re
import requests
import concurrent.futures
from typing import Dict, List, Optional, Any, Callable, Tuple, Set
from dataclasses import dataclass
import time


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


class AIClient:
    """
    AI 客户端，负责向 API 批量发送和接收请求
    采用回调机制处理提示词生成和结果解析
    """

    def __init__(
        self,
        api_key: str,
        api_url: str,
        model_name: str,
        request_options: Dict[str, Any],
        batch_size: int = 20,
        max_workers: int = 5,
        max_retries: int = 3,
        retry_delay: int = 2,
    ):
        """
        初始化 AI 客户端

        Args:
            api_key: API 密钥
            api_url: API 地址
            model_name: 模型名称
            request_options: 请求选项字典（temperature, top_p, timeout等）
            batch_size: 批量大小
            max_workers: 最大工作线程数
            max_retries: 最大重试次数
            retry_delay: 重试延迟（秒）
        """
        self.api_key = api_key
        self.api_url = api_url
        self.model_name = model_name
        self.request_options = request_options
        self.batch_size = batch_size
        self.max_workers = max_workers
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        # 缓存
        self.cache: Dict[str, Any] = {}

        # 会话
        self.session = requests.Session()

    def process_batch(
        self,
        batch_items: List[Any],
        prompt_callback: Callable[[List[Any]], str],
        result_callback: Callable[[str, List[Any]], Dict[int, Any]],
        cache_key_callback: Optional[Callable[[Any], str]] = None,
    ) -> Dict[int, Any]:
        """
        处理一个批次的请求

        Args:
            batch_items: 批次项目列表
            prompt_callback: 提示词生成回调函数，接收批次项目列表，返回提示词
            result_callback: 结果解析回调函数，接收API响应和批次项目列表，返回解析后的结果字典
            cache_key_callback: 缓存键生成回调函数（可选），接收项目，返回缓存键

        Returns:
            解析后的结果字典，键为项目索引，值为结果
        """
        if not batch_items:
            return {}

        # 检查缓存
        cached_results = {}
        remaining_items = []
        remaining_indices = []

        if cache_key_callback:
            for i, item in enumerate(batch_items):
                cache_key = cache_key_callback(item)
                if cache_key in self.cache:
                    cached_results[i] = self.cache[cache_key]
                else:
                    remaining_items.append(item)
                    remaining_indices.append(i)
        else:
            remaining_items = batch_items
            remaining_indices = list(range(len(batch_items)))

        # 如果没有需要请求的项，直接返回缓存
        if not remaining_items:
            return cached_results

        # 生成提示词
        prompt = prompt_callback(remaining_items)

        # 发送请求（带重试机制）
        response_text = self._send_request_with_retry(prompt)

        if not response_text:
            # 请求失败，返回缓存的结果，对于未缓存的项返回None
            all_results = cached_results.copy()
            for idx in remaining_indices:
                all_results[idx] = None
            return all_results

        # 解析结果
        batch_results = result_callback(response_text, remaining_items)

        # 合并结果并更新缓存
        all_results = cached_results.copy()
        for idx_in_remaining, result in batch_results.items():
            if idx_in_remaining < len(remaining_indices):
                original_idx = remaining_indices[idx_in_remaining]
                item = remaining_items[idx_in_remaining]

                if result is not None:
                    all_results[original_idx] = result
                    # 更新缓存
                    if cache_key_callback:
                        cache_key = cache_key_callback(item)
                        self.cache[cache_key] = result

        return all_results

    def _send_request_with_retry(self, prompt: str) -> Optional[str]:
        """
        发送请求，带重试机制

        Args:
            prompt: 提示词

        Returns:
            API响应文本，失败时返回None
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            **self.request_options,
        }

        for attempt in range(self.max_retries):
            try:
                response = self.session.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                    timeout=self.request_options.get("timeout", 120),
                )

                if response.status_code == 200:
                    result = response.json()
                    # DeepSeek API返回格式: choices[0].message.content
                    if "choices" in result and len(result["choices"]) > 0:
                        return (
                            result["choices"][0]
                            .get("message", {})
                            .get("content", "")
                            .strip()
                        )
                    else:
                        # 备用方案
                        return result.get("response", "").strip()
                else:
                    print(
                        f"警告：API请求失败 ({response.status_code})，第{attempt + 1}次重试"
                    )

            except Exception as e:
                print(f"警告：请求异常 ({e})，第{attempt + 1}次重试")

            # 如果不是最后一次尝试，等待后重试
            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay)

        print(f"错误：请求失败，已达到最大重试次数 {self.max_retries}")
        return None

    def process_batches(
        self,
        all_items: List[Any],
        prompt_callback: Callable[[List[Any]], str],
        result_callback: Callable[[str, List[Any]], Dict[int, Any]],
        cache_key_callback: Optional[Callable[[Any], str]] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[Any]:
        """
        处理所有批次

        Args:
            all_items: 所有项目列表
            prompt_callback: 提示词生成回调函数
            result_callback: 结果解析回调函数
            cache_key_callback: 缓存键生成回调函数（可选）
            progress_callback: 进度回调函数（可选），接收当前批次和总批次

        Returns:
            所有项目的结果列表，顺序与输入相同
        """
        if not all_items:
            return []

        # 按批次分组
        batches = []
        for i in range(0, len(all_items), self.batch_size):
            batch = all_items[i : i + self.batch_size]
            batches.append(batch)

        total_batches = len(batches)
        print(
            f"总共 {len(all_items)} 个项目，分成 {total_batches} 个批次 (batch_size={self.batch_size})"
        )

        # 使用线程池并发处理批次
        all_results: List[Optional[Any]] = [None] * len(all_items)

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_workers
        ) as executor:
            # 提交所有批次任务
            future_to_batch = {}
            for batch_idx, batch in enumerate(batches):
                start_idx = batch_idx * self.batch_size
                future = executor.submit(
                    self.process_batch,
                    batch,
                    prompt_callback,
                    result_callback,
                    cache_key_callback,
                )
                future_to_batch[future] = (batch_idx, start_idx, batch)

            # 处理完成的任务
            for future in concurrent.futures.as_completed(future_to_batch):
                batch_idx, start_idx, batch = future_to_batch[future]
                try:
                    batch_results = future.result()
                    # 将结果放入正确的位置
                    for relative_idx, result in batch_results.items():
                        absolute_idx = start_idx + relative_idx
                        if absolute_idx < len(all_results):
                            all_results[absolute_idx] = result

                    # 调用进度回调
                    if progress_callback:
                        progress_callback(batch_idx + 1, total_batches)

                    print(f"批次 {batch_idx + 1}/{total_batches} 完成")
                except Exception as e:
                    print(f"批次 {batch_idx + 1} 处理失败: {e}")
                    # 对于失败的批次，使用None
                    for i in range(len(batch)):
                        absolute_idx = start_idx + i
                        if absolute_idx < len(all_results):
                            all_results[absolute_idx] = None

        # 确保所有项都有结果
        final_results: List[Any] = []
        for i in range(len(all_results)):
            result = all_results[i]
            final_results.append(result)

        return final_results


class AITranslator:
    """
    AI 翻译器（基于 AIClient 的回调实现）
    保持与旧版本兼容的接口
    """

    def __init__(
        self,
        api_key: str,
        api_url: str,
        model_name: str,
        translation_options: Dict[str, Any],
        batch_size: int = 20,
        max_workers: int = 5,
        glossary_path: Optional[str] = None,
        whitelist_path: Optional[str] = None,
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
            glossary_path: 名词表文件路径
            whitelist_path: 白名单文件路径
        """
        # 创建 AI 客户端
        self.client = AIClient(
            api_key=api_key,
            api_url=api_url,
            model_name=model_name,
            request_options=translation_options,
            batch_size=batch_size,
            max_workers=max_workers,
            max_retries=translation_options.get("max_retries", 3),
            retry_delay=translation_options.get("retry_delay", 2),
        )

        # 名词表
        self.glossary: Dict[str, str] = {}
        if glossary_path:
            self.load_glossary(glossary_path)

        # 白名单
        self.whitelist: Set[str] = set()
        if whitelist_path:
            self.load_whitelist(whitelist_path)

    def is_english_text(self, text: str) -> bool:
        """判断文本是否主要是英文"""
        return _is_english_text_logic(text)

    def needs_translation(self, en_value: str, zh_value: Optional[str]) -> bool:
        """判断是否需要翻译"""
        # 如果英文值是空字符串，不应该翻译
        if not en_value or en_value.strip() == "":
            return False

        # 检查是否在白名单中（完全匹配）
        if en_value.strip() in self.whitelist:
            return False

        # 检查是否包含白名单中的词（部分匹配）
        for word in self.whitelist:
            if word and word in en_value:
                # 如果白名单词出现在英文值中，且该词是独立的（前后是单词边界）
                pattern = r"\b" + re.escape(word) + r"\b"
                if re.search(pattern, en_value, re.IGNORECASE):
                    return False

        # 检查英文值是否只包含变量（如__ENTITY__kr-mineral-water__）
        # 这类值不应该被翻译，应该原样保留
        if _contains_only_variables(en_value):
            return False

        # 检查英文值是否以中括号格式开头（如 [img=...]、[entity=...] 等）
        # 这类值不应该被翻译，应该原样保留
        if _starts_with_bracket_format(en_value):
            return False

        # 如果中文值不存在，需要翻译
        if not zh_value:
            return True

        # 检查英文值中是否包含变量，并验证中文值是否也包含这些变量
        en_variables = _extract_variables(en_value)
        if en_variables:
            # 如果英文值包含变量，检查中文值是否也包含这些变量
            if zh_value:
                for var in en_variables:
                    if var not in zh_value:
                        # 中文值缺少英文值中的某个变量，需要重新翻译
                        return True
                # 如果中文值包含了所有变量，继续检查是否是英文
                # 如果中文值是英文，仍然需要翻译
                pass

        # 如果中文值主要是英文，需要翻译
        if self.is_english_text(zh_value):
            return True

        return False

    def load_glossary(self, glossary_path: str) -> None:
        """
        加载名词表文件

        Args:
            glossary_path: 名词表文件路径
        """
        try:
            import os
            from pathlib import Path

            glossary_file = Path(glossary_path)
            if not glossary_file.exists():
                print(f"警告: 名词表文件不存在: {glossary_path}")
                return

            with open(glossary_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue

                    # 解析 "英文: 中文" 格式
                    if ":" in line:
                        parts = line.split(":", 1)
                        if len(parts) == 2:
                            english = parts[0].strip()
                            chinese = parts[1].strip()
                            if english and chinese:
                                self.glossary[english] = chinese

            print(f"已加载名词表，包含 {len(self.glossary)} 个术语")

        except Exception as e:
            print(f"加载名词表失败: {e}")

    def load_whitelist(self, whitelist_path: str) -> None:
        """
        加载白名单文件

        Args:
            whitelist_path: 白名单文件路径
        """
        try:
            from pathlib import Path

            whitelist_file = Path(whitelist_path)
            if not whitelist_file.exists():
                print(f"警告: 白名单文件不存在: {whitelist_path}")
                return

            with open(whitelist_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue

                    # 添加白名单词（不区分大小写，但保留原始大小写用于显示）
                    self.whitelist.add(line)

            print(f"已加载白名单，包含 {len(self.whitelist)} 个专有名词")

        except Exception as e:
            print(f"加载白名单失败: {e}")

    def _create_batch_prompt(self, items: List[TranslationItem]) -> str:
        """
        为批量翻译创建提示词（回调函数）

        Args:
            items: 翻译项列表

        Returns:
            格式化后的提示词
        """
        # 构建项目列表
        items_text = ""
        for i, item in enumerate(items, 1):
            items_text += f"{i}. Section: {item.section}, Key: {item.key}\n"
            items_text += f"   英文: {item.en_value}\n\n"

        # 构建名词表参考部分
        glossary_text = ""
        if self.glossary:
            glossary_text = "\n名词表参考（请优先使用以下术语的翻译）：\n"
            for english, chinese in self.glossary.items():
                glossary_text += f"- {english}: {chinese}\n"
            glossary_text += "\n"

        game_context = "《异星工厂》是一款科幻/工业自动化游戏，主题包括科技、工厂、自动化、神秘、哲学等。"

        prompt = f"""请将以下游戏文本从英文翻译成简体中文。要求：

重要规则：
1. 保持准确的技术含义和游戏术语
2. 保持格式标记不变（如[color=red]、[item=...]、[fluid=...]、[entity=...]、[font=...]、[img=...]等）
3. 类似"__xxx__"这样的游戏变量（如__ENTITY__、__ITEM__、__FLUID__、__1__、__2__、__REMARK_COLOR_BEGIN__、__REMARK_COLOR_END__等）不应该被翻译，必须原样保留
4. 在准确的基础上，尽量让翻译有趣、生动、有游戏感
5. 可以适当加入幽默感，但不要过度，以免失去原文的专业和神秘氛围
6. 保持文本的流畅性和可读性
7. 如果文本中包含名词表中的术语，请优先使用名词表中的翻译

游戏背景：{game_context}

{glossary_text}
请按以下格式回复，严格保持编号对应：
1. 中文翻译：[翻译结果1]
2. 中文翻译：[翻译结果2]
...

需要翻译的文本：
{items_text}

请开始翻译："""

        return prompt

    def _parse_batch_response(
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

    def _get_cache_key(self, item: TranslationItem) -> str:
        """获取缓存键"""
        return f"{item.section}:{item.key}:{item.en_value}"

    def translate_items(
        self,
        items: List[TranslationItem],
        game_context: str = "《异星工厂》是一款科幻/工业自动化游戏，主题包括科技、工厂、自动化、神秘、哲学等。",
    ) -> List[str]:
        """翻译所有项目，使用批量处理和并发"""

        if not items:
            return []

        # 使用 AIClient 处理批次
        translations = self.client.process_batches(
            all_items=items,
            prompt_callback=self._create_batch_prompt,
            result_callback=lambda response_text, batch_items: self._parse_batch_response(
                response_text, batch_items
            ),
            cache_key_callback=self._get_cache_key,
            progress_callback=lambda current, total: None,
        )

        # 确保所有项都有翻译
        final_translations: List[str] = []
        for i, translation in enumerate(translations):
            if translation is None:
                final_translations.append(items[i].en_value)
            else:
                final_translations.append(translation)

        return final_translations


def create_batch_translator(
    batch_size: Optional[int] = None,
    max_workers: int = 10,
    glossary_path: Optional[str] = None,
    whitelist_path: Optional[str] = None,
) -> AITranslator:
    """
    创建批量翻译器（工厂函数）

    从 config.py 加载配置，保持向后兼容性

    Args:
        batch_size: 批量大小，如果为None则使用配置文件中的值
        max_workers: 最大工作线程数（增加默认值以加快速度）
        glossary_path: 名词表文件路径
        whitelist_path: 白名单文件路径

    Returns:
        配置好的 AITranslator 实例
    """
    import sys
    from pathlib import Path

    # 添加scripts目录到路径，以便导入config
    script_dir = Path(__file__).parent
    if str(script_dir) not in sys.path:
        sys.path.insert(0, str(script_dir))

    try:
        from config import (
            API_KEY,
            API_URL,
            MODEL_NAME,
            TRANSLATION_OPTIONS,
            BATCH_SIZE,
        )
    except ImportError:
        print("请复制 scripts/config.py.template 为 scripts/config.py")
        exit(1)

    # 如果未提供batch_size，则使用配置文件中的值
    if batch_size is None:
        batch_size = BATCH_SIZE

    # 创建 AITranslator 实例
    return AITranslator(
        api_key=API_KEY,
        api_url=API_URL,
        model_name=MODEL_NAME,
        translation_options=TRANSLATION_OPTIONS,
        batch_size=batch_size,
        max_workers=max_workers,
        glossary_path=glossary_path,
        whitelist_path=whitelist_path,
    )


# 为了向后兼容，保留 BatchTranslator 作为 create_batch_translator 的别名
BatchTranslator = create_batch_translator


# 导出常用类和函数
__all__ = [
    "TranslationItem",
    "AIClient",
    "AITranslator",
    "BatchTranslator",
    "is_english_text",  # 导出为独立函数
]


# 模块级私有函数，包含 is_english_text 的核心逻辑
def _is_english_text_logic(text: str) -> bool:
    """判断文本是否主要是英文（核心逻辑）"""
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


# 模块级私有函数，检查文本是否只包含变量
def _contains_only_variables(text: str) -> bool:
    """检查文本是否只包含变量（如 __ENTITY__xxx__ 等）"""
    text = text.strip()
    if not text:
        return False

    # 检查是否纯粹由单个变量构成
    variable_pattern = r"^__[A-Za-z0-9_-]+__$"
    if re.match(variable_pattern, text):
        return True

    # 检查是否只包含变量（可能多个变量组合）
    variable_only_pattern = r"^(?:__[A-Za-z0-9_-]+__)+$"
    if re.match(variable_only_pattern, text):
        return True

    return False


# 模块级私有函数，检查文本是否以中括号格式开头
def _starts_with_bracket_format(text: str) -> bool:
    """检查文本是否以中括号格式开头（如 [img=...]、[entity=...] 等）"""
    text = text.strip()
    if not text:
        return False

    # 匹配以 [ 开头，包含 =，以 ] 结尾的格式
    bracket_pattern = r"^\[[a-zA-Z]+=[^\]]+\]"
    return bool(re.match(bracket_pattern, text))


# 模块级私有函数，提取文本中的所有变量
def _extract_variables(text: str) -> List[str]:
    """提取文本中的所有变量（__xxx__ 格式）"""
    variable_pattern = r"__[A-Za-z0-9_]+__"
    return re.findall(variable_pattern, text)


# 导出独立函数，方便其他脚本使用
def is_english_text(text: str) -> bool:
    """判断文本是否主要是英文（独立函数版本）"""
    return _is_english_text_logic(text)
