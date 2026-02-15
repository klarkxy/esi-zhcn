# -*- coding: utf-8 -*-
"""
Factorio Mod 更新脚本
将当前目录的locale文件夹、info.json和thumbnail.png复制到Factorio的mod文件夹中
排除.backup文件
"""

import os
import sys
import json
import shutil
import platform
from pathlib import Path


def main():
    print("=" * 60)
    print("Factorio Mod 更新脚本")
    print("=" * 60)

    # 获取当前脚本所在目录
    script_dir = Path(__file__).parent.absolute()
    print(f"当前目录: {script_dir}")

    # 检查必要的文件是否存在
    required_files = ["info.json", "thumbnail.png"]
    for file in required_files:
        if not (script_dir / file).exists():
            print(f"错误: 找不到 {file}")
            return 1

    locale_dir = script_dir / "locale"
    if not locale_dir.exists():
        print("错误: 找不到 locale 文件夹")
        return 1

    # 从info.json读取mod名称和版本
    try:
        with open(script_dir / "info.json", "r", encoding="utf-8") as f:
            info_data = json.load(f)

        mod_name = info_data.get("name")
        mod_version = info_data.get("version")

        if not mod_name or not mod_version:
            print("错误: 无法从info.json中读取mod名称或版本")
            return 1

        mod_folder_name = f"{mod_name}_{mod_version}"
        print(f"Mod信息: {mod_name} 版本 {mod_version}")
        print(f"Mod文件夹名称: {mod_folder_name}")
    except Exception as e:
        print(f"错误: 无法解析info.json文件")
        print(f"错误详情: {e}")
        return 1

    # 构建目标路径
    if platform.system() != "Windows":
        print("警告: 此脚本主要针对Windows系统设计")
        print("尝试使用通用方法查找Factorio mods文件夹...")

    # 获取APPDATA路径
    appdata_path = os.environ.get("APPDATA")
    if not appdata_path:
        # 如果不是Windows，尝试其他路径
        if platform.system() == "Darwin":  # macOS
            appdata_path = os.path.expanduser("~/Library/Application Support")
        else:  # Linux或其他
            appdata_path = os.path.expanduser("~/.local/share")

    if not appdata_path:
        print("错误: 无法找到应用程序数据目录")
        return 1

    factorio_mods_path = Path(appdata_path) / "Factorio" / "mods"
    target_path = factorio_mods_path / mod_folder_name

    print(f"目标路径: {target_path}")

    # 检查Factorio mods文件夹是否存在
    if not factorio_mods_path.exists():
        print(f"警告: Factorio mods文件夹不存在: {factorio_mods_path}")
        response = input("是否要创建此文件夹? (y/n): ").strip().lower()
        if response != "y":
            print("操作已取消")
            return 0

        try:
            factorio_mods_path.mkdir(parents=True, exist_ok=True)
            print(f"已创建文件夹: {factorio_mods_path}")
        except Exception as e:
            print(f"错误: 无法创建文件夹")
            print(f"错误详情: {e}")
            return 1

    # 创建目标文件夹
    try:
        target_path.mkdir(parents=True, exist_ok=True)
        print(f"已创建/确认目标文件夹: {target_path}")
    except Exception as e:
        print(f"错误: 无法创建目标文件夹")
        print(f"错误详情: {e}")
        return 1

    # 复制文件
    print("\n开始复制文件...")

    # 1. 复制info.json
    try:
        shutil.copy2(script_dir / "info.json", target_path / "info.json")
        print(f"✓ 已复制: info.json")
    except Exception as e:
        print(f"✗ 复制info.json失败: {e}")
        return 1

    # 2. 复制thumbnail.png
    try:
        shutil.copy2(script_dir / "thumbnail.png", target_path / "thumbnail.png")
        print(f"✓ 已复制: thumbnail.png")
    except Exception as e:
        print(f"✗ 复制thumbnail.png失败: {e}")
        return 1

    # 3. 复制locale文件夹（排除.backup文件）
    source_locale = script_dir / "locale"
    target_locale = target_path / "locale"

    try:
        # 如果目标locale文件夹已存在，先删除
        if target_locale.exists():
            shutil.rmtree(target_locale)

        # 复制整个locale文件夹结构
        shutil.copytree(
            source_locale,
            target_locale,
            ignore=shutil.ignore_patterns("*.backup", "*.bak", "*.tmp"),
        )
        print(f"✓ 已复制: locale文件夹（已排除.backup文件）")

        # 统计复制的文件数量
        copied_files = []
        for root, dirs, files in os.walk(target_locale):
            for file in files:
                copied_files.append(os.path.join(root, file))

        print(f"  共复制了 {len(copied_files)} 个文件到locale文件夹")

    except Exception as e:
        print(f"✗ 复制locale文件夹失败: {e}")
        return 1

    print("\n" + "=" * 60)
    print("✅ 更新完成!")
    print(f"文件已成功复制到: {target_path}")
    print("=" * 60)

    # 显示目标文件夹内容
    print("\n目标文件夹内容:")
    for item in target_path.iterdir():
        if item.is_file():
            size = item.stat().st_size
            print(f"  📄 {item.name} ({size} bytes)")
        elif item.is_dir():
            file_count = sum(1 for _ in item.rglob("*") if _.is_file())
            print(f"  📁 {item.name}/ ({file_count} 个文件)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
