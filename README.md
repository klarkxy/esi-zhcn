# ESI: Remembrance 中文汉化

[![Factorio Version](https://img.shields.io/badge/Factorio-2.0-blue)](https://factorio.com)
[![License](https://img.shields.io/badge/License-SATA-green)](LICENSE)

本模组为《异星工厂》MOD **"Exotic Space Industries: Remembrance"** 的中文汉化，兼容 Krastorio2。

* 源MOD地址: [https://mods.factorio.com/mod/exotic-space-industries-remembrance](https://mods.factorio.com/mod/exotic-space-industries-remembrance)
* K2地址: [https://mods.factorio.com/mod/krastorio2](https://mods.factorio.com/mod/krastorio2)
* K2-SO地址: [https://mods.factorio.com/mod/krastorio2-spaced-out](https://mods.factorio.com/mod/krastorio2-spaced-out)
注意：本模组仅包含汉化文件，依赖于原模组才能使用。

## 📖 项目简介

这是一个使用AI辅助翻译的自动化汉化项目，旨在为《异星工厂》的ESI: Remembrance模组提供高质量的中文本地化支持。

### 主要特性
- ✅ 完整的游戏文本汉化
- ✅ 兼容 Krastorio2 和 Krastorio2-spaced-out
- ✅ 使用AI翻译确保术语一致性
- ✅ 自动化翻译流程，支持批量处理
- ✅ 包含专业名词表，确保翻译准确性

## 🚀 安装方法

### 方法一：通过 Factorio 官方模组管理工具（推荐）
1. 打开《异星工厂》游戏
2. 进入主菜单，点击"模组"按钮
3. 在模组管理界面中，点击"安装模组"
4. 在搜索框中输入 "ESI: R 个人汉化" 或 "esi-zhcn"
5. 找到本汉化模组并点击"安装"
6. 确保已安装原模组 "Exotic Space Industries: Remembrance"

### 方法二：从源码构建
1. 克隆或下载本仓库
2. 运行打包脚本：
   ```powershell
   python scripts\打包提交.py
   ```
3. 生成的 `.zip` 文件位于项目根目录

## 🔧 使用方法

### 翻译新内容
1. 确保已配置好API密钥（见下文）
2. 运行翻译脚本：
   ```powershell
   python scripts\翻译脚本.py
   ```
3. 脚本会自动：
   - 读取英文原文（`locale/en/`）
   - 使用AI翻译生成中文
   - 保存到中文目录（`locale/zh-CN/`）

### 更新现有翻译
```powershell
python scripts\更新MOD.py
```

## 🤖 AI翻译系统

本项目采用先进的AI翻译系统，显著提高了翻译效率和质量。

### 技术架构
- **AI翻译引擎**: 基于 DeepSeek API 的批量翻译系统
- **名词表系统**: 专业术语一致性管理
- **批量处理**: 支持并发翻译，提高效率
- **缓存机制**: 避免重复翻译，节省API调用

### 配置说明
1. 复制配置文件模板：
   ```powershell
   Copy-Item scripts\config.py.template scripts\config.py
   ```
2. 编辑 `scripts/config.py`，填入你的API密钥：
   ```python
   API_KEY = "your-deepseek-api-key-here"
   API_URL = "https://api.deepseek.com/v1/chat/completions"
   MODEL_NAME = "deepseek-chat"
   ```

## 🛠️ 开发与贡献

### 项目结构
```
esi-zhcn/
├── locale/              # 本地化文件
│   ├── en/             # 英文原文
│   └── zh-CN/          # 中文翻译
├── scripts/            # 工具脚本
│   ├── 翻译脚本.py     # 主翻译脚本
│   ├── ai_translator.py # AI翻译模块
│   ├── cfg_io.py       # 配置文件读写
│   └── 打包提交.py     # 打包脚本
├── 名词表.txt          # 专业术语对照表
├── info.json           # MOD信息
└── README.md           # 本文档
```

### 二次开发指南

#### 1. 准备英文原文
如果您想为其他MOD创建汉化，需要先准备英文原文文件：

```powershell
# 清空现有的英文目录（如果需要重新开始）
Remove-Item -Path "locale\en\*" -Force -Recurse -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path "locale\en" -Force

# 将MOD的英文.cfg文件复制到locale/en/目录中
# 例如：Copy-Item "C:\path\to\mod\*.cfg" -Destination "locale\en\"
```

#### 2. 构造名词表
名词表（`名词表.txt`）是确保术语一致性的关键：
```txt
# 格式：英文术语: 中文翻译
Advanced Assembling Machine: 高级组装机
Advanced Chemical Plant: 高级化工厂
Advanced Furnace: 高级熔炉
AI Core: AI核心
Antimatter Reactor: 反物质反应堆

```

#### 3. 配置API密钥
1. 复制配置文件模板：
   ```powershell
   Copy-Item scripts\config.py.template scripts\config.py
   ```

2. 编辑 `scripts/config.py`，填入您的DeepSeek API密钥：
   ```python
   API_KEY = "your-deepseek-api-key-here"
   API_URL = "https://api.deepseek.com/v1/chat/completions"
   MODEL_NAME = "deepseek-chat"
   ```

#### 4. 运行翻译
```powershell
# 首次翻译（生成初步翻译）
python scripts\翻译脚本.py

# 测试翻译结果（检查MOD是否可用）
python scripts\更新MOD.py

# 打包发布（生成可发布的.zip文件）
python scripts\打包提交.py
```

**注意：** 确保已安装Python并添加到系统PATH环境变量中。

#### 5. 翻译工作流程
1. **准备阶段**：
   - 收集英文原文（将MOD的.cfg文件复制到`locale/en/`目录）
   - **手动创建名词表初稿**（基于游戏术语和已有翻译经验）

2. **翻译阶段**：
   - 运行翻译脚本生成初步中文翻译
   - AI翻译会参考名词表中的术语，确保一致性

3. **校对阶段**：
   - 人工校对翻译结果，修正不准确或生硬的翻译
   - 根据校对结果**手动更新名词表**，添加新的术语或修正现有术语

4. **测试阶段**：
   - 运行更新MOD脚本测试翻译结果
   - 检查MOD在游戏中是否可用，翻译是否显示正常

5. **发布阶段**：
   - 运行打包脚本生成可发布的.zip文件
   - 发布到GitHub Releases或Factorio MOD门户

**重要提示**：名词表需要手动创建和维护，这是确保翻译质量的关键步骤。AI翻译会优先使用名词表中的术语，因此一个完善的名词表能显著提高翻译一致性。

### 贡献指南
1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

### 翻译规范
- 保持技术术语准确性
- 保留游戏格式标记（如 `[color=red]`、`[item=...]` 等）
- 保持游戏变量不变（如 `__ENTITY__`、`__ITEM__` 等）
- 在准确的基础上，让翻译生动有趣
- 优先使用名词表中的术语翻译

## 🙏 致谢

### Cline Chinese 的帮助
本项目在开发过程中得到了 **Cline Chinese** 的宝贵帮助：
- 提供了AI翻译系统的架构设计建议
- 协助优化了批量处理逻辑
- 改进了错误处理和重试机制
- 增强了代码的可维护性和扩展性

### DeepSeek 的贡献
**DeepSeek** 作为AI翻译引擎，为本项目提供了：
- 高质量的翻译结果
- 稳定的API服务
- 高效的批量处理能力
- 合理的成本控制

## 📄 许可证

本项目采用 **The Star And Thank Author License (SATA)** 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

### SATA 许可证要点
- ✅ 可以自由使用、复制、修改、合并、发布、分发、再许可和/或销售本软件
- ✅ 必须在所有副本或实质性部分中包含上述版权声明和本许可声明
- ⭐ **最重要的一点**：您应该先给项目点星（star/+1/点赞），然后感谢作者
- 📧 建议的感谢方式：
  - 给作者发送感谢邮件，与作者成为朋友
  - 报告错误或问题
  - 告诉朋友这个项目有多棒
  - 当然，您也可以在心中默默表达感谢

### 贡献者注意事项
通过 fork 本项目的贡献者可以选择在版权和项目 URL 部分添加他/她的姓名和 fork 的项目 URL，但不得删除或修改这两个部分中的任何其他内容。

## 📞 联系方式

- 项目主页: [https://github.com/klarkxy/esi-zhcn](https://github.com/klarkxy/esi-zhcn)
- 问题反馈: [GitHub Issues](https://github.com/klarkxy/esi-zhcn/issues)

## 📊 统计数据
- 已翻译文件: 8个
- 专业术语: 100+ 条
- 支持 Factorio 版本: 2.0+

---

**Happy automating! 祝您游戏愉快！** 🚀

*最后更新: 2026年2月*
