# -*- coding: utf-8 -*-
"""
Factorio Mod 打包提交脚本
将当前项目打包为zip文件，准备提交到Factorio官网
"""

import os
import sys
import json
import zipfile
import shutil
import platform
from pathlib import Path
from datetime import datetime
import argparse


def get_mod_info(script_dir: Path) -> tuple:
    """
    从info.json获取mod信息

    Args:
        script_dir: 脚本所在目录

    Returns:
        tuple: (mod_name, mod_version, mod_folder_name)
    """
    info_file = script_dir / "info.json"
    if not info_file.exists():
        print(f"错误: 找不到 info.json 文件")
        return None, None, None

    try:
        with open(info_file, "r", encoding="utf-8") as f:
            info_data = json.load(f)

        mod_name = info_data.get("name")
        mod_version = info_data.get("version")

        if not mod_name or not mod_version:
            print("错误: 无法从info.json中读取mod名称或版本")
            return None, None, None

        mod_folder_name = f"{mod_name}_{mod_version}"
        return mod_name, mod_version, mod_folder_name

    except Exception as e:
        print(f"错误: 无法解析info.json文件")
        print(f"错误详情: {e}")
        return None, None, None


def read_gitignore_patterns(source_dir: Path) -> list:
    """
    读取.gitignore文件中的排除模式

    Args:
        source_dir: 源目录

    Returns:
        list: 排除模式列表
    """
    gitignore_file = source_dir / ".gitignore"
    patterns = []

    if gitignore_file.exists():
        try:
            with open(gitignore_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    # 跳过空行和注释
                    if not line or line.startswith("#"):
                        continue
                    patterns.append(line)
            print(f"从.gitignore读取了 {len(patterns)} 个排除模式")
        except Exception as e:
            print(f"警告: 无法读取.gitignore文件: {e}")

    return patterns


def create_zip_file(
    source_dir: Path, zip_path: Path, exclude_patterns=None, mod_folder_name=None
) -> bool:
    """
    创建zip文件

    Args:
        source_dir: 源目录
        zip_path: 目标zip文件路径
        exclude_patterns: 要排除的文件模式列表
        mod_folder_name: MOD文件夹名称（用于在ZIP中创建子目录）

    Returns:
        bool: 是否成功
    """
    if exclude_patterns is None:
        # 从.gitignore读取排除模式
        gitignore_patterns = read_gitignore_patterns(source_dir)

        # 基础排除模式（包括.gitignore中的模式）
        exclude_patterns = [
            ".git",
            "__pycache__",
            ".DS_Store",
            "scripts",  # 额外排除scripts目录
        ]

        # 添加.gitignore中的模式
        for pattern in gitignore_patterns:
            if pattern not in exclude_patterns:
                exclude_patterns.append(pattern)

        print(f"使用排除模式: {exclude_patterns}")

    print(f"正在创建zip文件: {zip_path}")
    print(f"源目录: {source_dir}")

    if mod_folder_name:
        print(f"MOD文件夹名称: {mod_folder_name}")

    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            # 遍历所有文件和目录
            for root, dirs, files in os.walk(source_dir):
                # 排除不需要的目录
                dirs[:] = [
                    d
                    for d in dirs
                    if not any(
                        pattern_match(d, pattern) for pattern in exclude_patterns
                    )
                ]

                for file in files:
                    # 检查文件是否应该被排除
                    if any(
                        pattern_match(file, pattern) for pattern in exclude_patterns
                    ):
                        continue

                    file_path = Path(root) / file
                    # 计算在zip中的相对路径
                    rel_path = file_path.relative_to(source_dir)

                    # 根据异星工厂MOD要求，文件应该放在mod_folder_name目录下
                    if mod_folder_name:
                        arcname = f"{mod_folder_name}/{rel_path}"
                    else:
                        arcname = rel_path

                    # 添加到zip
                    zipf.write(file_path, arcname)
                    print(f"  ✓ 添加: {arcname}")

        # 获取zip文件大小
        zip_size = zip_path.stat().st_size
        print(f"✓ Zip文件创建成功: {zip_path}")
        print(f"  文件大小: {zip_size:,} 字节 ({zip_size/1024/1024:.2f} MB)")
        return True

    except Exception as e:
        print(f"✗ 创建zip文件失败: {e}")
        return False


def pattern_match(name: str, pattern: str) -> bool:
    """
    匹配文件名或目录名是否符合模式
    支持.gitignore风格的简单模式匹配

    Args:
        name: 文件名或目录名
        pattern: 匹配模式

    Returns:
        bool: 是否匹配
    """
    # 处理目录模式（以/结尾）
    if pattern.endswith("/"):
        # 目录模式：匹配整个目录名
        dir_pattern = pattern.rstrip("/")
        return name == dir_pattern

    # 处理通配符模式
    if "*" in pattern:
        # 简单的通配符匹配
        import fnmatch

        return fnmatch.fnmatch(name, pattern)

    # 处理普通模式
    return name == pattern


def validate_mod_structure(source_dir: Path) -> bool:
    """
    验证mod结构是否完整

    Args:
        source_dir: 源目录

    Returns:
        bool: 是否有效
    """
    print("验证mod结构...")

    required_files = ["info.json", "thumbnail.png"]
    required_dirs = ["locale"]

    all_valid = True

    # 检查必需文件
    for file in required_files:
        file_path = source_dir / file
        if not file_path.exists():
            print(f"✗ 缺少必需文件: {file}")
            all_valid = False
        else:
            print(f"✓ 找到文件: {file}")

    # 检查必需目录
    for dir_name in required_dirs:
        dir_path = source_dir / dir_name
        if not dir_path.exists():
            print(f"✗ 缺少必需目录: {dir_name}")
            all_valid = False
        else:
            # 检查目录是否为空
            try:
                has_files = any(dir_path.iterdir())
                if has_files:
                    print(f"✓ 找到目录: {dir_name}/ (包含文件)")
                else:
                    print(f"⚠ 目录为空: {dir_name}/")
            except:
                print(f"✓ 找到目录: {dir_name}/")

    # 检查locale目录结构
    locale_dir = source_dir / "locale"
    if locale_dir.exists():
        en_dir = locale_dir / "en"
        zh_dir = locale_dir / "zh-CN"

        if en_dir.exists():
            en_files = list(en_dir.glob("*.cfg"))
            print(f"✓ locale/en/ 包含 {len(en_files)} 个.cfg文件")
        else:
            print("⚠ 缺少 locale/en/ 目录")

        if zh_dir.exists():
            zh_files = list(zh_dir.glob("*.cfg"))
            print(f"✓ locale/zh-CN/ 包含 {len(zh_files)} 个.cfg文件")
        else:
            print("⚠ 缺少 locale/zh-CN/ 目录")

    return all_valid


def get_output_directory() -> Path:
    """
    获取输出目录

    Returns:
        Path: 输出目录路径
    """
    # 直接在项目根目录生成
    return Path.cwd()


def main():
    parser = argparse.ArgumentParser(description="Factorio Mod打包提交脚本")
    parser.add_argument("--output", "-o", help="输出目录路径")
    parser.add_argument("--no-validate", action="store_true", help="跳过mod结构验证")
    parser.add_argument("--list-files", action="store_true", help="列出将包含的文件")
    args = parser.parse_args()

    print("=" * 60)
    print("Factorio Mod 打包提交脚本")
    print("=" * 60)

    # 获取当前脚本所在目录的父目录（项目根目录）
    script_dir = Path(__file__).parent.absolute()
    project_dir = script_dir.parent

    print(f"项目目录: {project_dir}")

    # 获取mod信息
    mod_name, mod_version, mod_folder_name = get_mod_info(project_dir)
    if not mod_name or not mod_version:
        return 1

    print(f"Mod信息: {mod_name} 版本 {mod_version}")
    print(f"Mod文件夹名称: {mod_folder_name}")

    # 验证mod结构
    if not args.no_validate:
        if not validate_mod_structure(project_dir):
            print("\n⚠ 警告: Mod结构不完整，可能无法正常工作")
            response = input("是否继续打包? (y/n): ").strip().lower()
            if response != "y":
                print("操作已取消")
                return 0
    else:
        print("跳过mod结构验证")

    # 确定输出目录
    if args.output:
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)
    else:
        output_dir = get_output_directory()

    print(f"输出目录: {output_dir}")

    # 生成zip文件名（不带时间戳，以便覆盖）
    zip_filename = f"{mod_folder_name}.zip"
    zip_path = output_dir / zip_filename

    # 删除旧的zip文件（如果存在）
    if zip_path.exists():
        try:
            zip_path.unlink()
            print(f"已删除旧的zip文件: {zip_path}")
        except Exception as e:
            print(f"警告: 无法删除旧的zip文件: {e}")

    # 如果要列出文件
    if args.list_files:
        print("\n将包含的文件列表:")
        print("-" * 40)

        # 从.gitignore读取排除模式
        gitignore_patterns = read_gitignore_patterns(project_dir)

        # 基础排除模式
        exclude_patterns = [
            ".git",
            "__pycache__",
            ".DS_Store",
            "scripts",  # 额外排除scripts目录
        ]

        # 添加.gitignore中的模式
        for pattern in gitignore_patterns:
            if pattern not in exclude_patterns:
                exclude_patterns.append(pattern)

        print(f"使用排除模式: {exclude_patterns}")

        file_count = 0

        for root, dirs, files in os.walk(project_dir):
            # 排除不需要的目录
            dirs[:] = [
                d
                for d in dirs
                if not any(pattern_match(d, pattern) for pattern in exclude_patterns)
            ]

            for file in files:
                # 检查文件是否应该被排除
                if any(pattern_match(file, pattern) for pattern in exclude_patterns):
                    continue

                file_path = Path(root) / file
                rel_path = file_path.relative_to(project_dir)
                print(f"  {rel_path}")
                file_count += 1

        print(f"\n总共 {file_count} 个文件")
        return 0

    # 创建zip文件
    print("\n开始打包...")
    success = create_zip_file(project_dir, zip_path, mod_folder_name=mod_folder_name)

    if not success:
        return 1

    # 显示打包结果
    print("\n" + "=" * 60)
    print("✅ 打包完成!")
    print("=" * 60)
    print(f"Zip文件: {zip_path}")
    print(f"文件大小: {zip_path.stat().st_size:,} 字节")

    # 显示上传说明
    print("\n" + "=" * 60)
    print("上传到Factorio官网的说明:")
    print("=" * 60)
    print("1. 访问 https://mods.factorio.com/")
    print("2. 登录您的账户")
    print("3. 点击右上角的用户名，选择'My Mods'")
    print("4. 点击'Upload Mod'按钮")
    print("5. 选择刚刚创建的zip文件: " + str(zip_path))
    print("6. 填写mod信息:")
    print(f"   - Mod名称: {mod_name}")
    print(f"   - 版本: {mod_version}")
    print("   - 兼容的Factorio版本: 根据info.json中的factorio_version")
    print("   - 描述: 根据info.json中的description")
    print("   - 标签: 选择合适的标签（如Translation, Interface等）")
    print("7. 点击'Upload'提交")
    print("\n注意:")
    print("- 确保您有权限上传此mod")
    print("- 如果是翻译mod，请确保已获得原作者的许可")
    print("- 上传前建议在本地测试mod是否正常工作")

    # 可选：打开输出目录
    if platform.system() == "Windows":
        try:
            os.startfile(output_dir)
            print(f"\n已打开输出目录: {output_dir}")
        except:
            pass
    elif platform.system() == "Darwin":
        try:
            os.system(f'open "{output_dir}"')
            print(f"\n已打开输出目录: {output_dir}")
        except:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
