# 📚 Easy-NotebookLM

[English](./README.md) | 中文

**Easy-NotebookLM** 是一个基于 Google NotebookLM 思路实现的中文播客生成工具。它能够将 PDF 文档内容转化为自然对话形式的中文播客音频，并支持多种对话风格。目前模型推理使用的是 [DeepSeek-v3](https://platform.deepseek.com/) API，也可以替换为任意具备相同能力的模型接口；语音合成部分则采用了 **CosyVoice** 模型。

> 🎙️ NotebookLM 是谷歌推出的一款 AI 音频内容生成工具，此前仅支持英文内容生成。Easy-NotebookLM 旨在提供一种简单易用的方式，快速从 PDF 中生成高质量中文播客。


---

## 🧰 环境依赖

- Python 版本：`3.12.8`
- 其他依赖包：详见 `requirements.txt`
- 额外依赖：需要手动安装 `ffmpeg`

### 环境搭建步骤：
```bash
# 安装依赖
pip install -r requirements.txt

# 安装 ffmpeg（Mac/Linux 示例）
brew install ffmpeg      # macOS
sudo apt-get install ffmpeg  # Ubuntu/Debian
```

### API Key 配置
在运行前，请确保配置以下环境变量或在代码中设置：
- `DEEPSEEK_API_KEY`（用于大模型对话生成）
- `BAILIAN_API_KEY`（可选，百炼平台 API）

在项目根目录下创建一个名为 `.env` 的文件，并添加以下内容，并填上自己的key：
```
DEEPSEEK_API_KEY=""
DASHSCOPE_API_KEY=""
```

---

## 📁 文件说明

| 文件名             | 功能说明 |
|------------------|--------|
| `notelm.py`        | 基础版本播客合成脚本，运行稳定，适合大多数用户 |
| `notelm_react.py`  | 支持 ReAct 模式的增强版本，会自动评估生成结果是否合格，若不合格则重新生成。目前处于开发阶段，稳定性有待提升 |
| `prompt.txt`       | 提示词模板文件，控制生成对话的风格 |
| `speech/`          | 存放用于生成播客的文本材料 |
| `speech_pre/`      | 已生成的播客对话语音及对应文本样例 |

---

## ⚙️ 参数说明

可以通过命令行参数控制播客生成过程：

| 参数         | 含义描述 |
|-------------|---------|
| `--input`     | 输入 PDF 文件路径 |
| `--output_dir` | 输出文件保存目录 |
| `--len`       | 每段对话的最大长度（字符数） |
| `--minutes`   | 生成语音时长（单位：分钟） |
| `--count`     | 输出的对话条数 |
| `--prompt_type` | 对话风格类型，默认为 `'default'`，可选值如下： |

### ✨ 支持的 Prompt 类型（对话风格）

| 类型         | 描述 |
|-------------|------|
| `default`     | 默认模式：主持人引导嘉宾回答问题为主 |
| `discussion`  | 热情讨论模式：主持人了解部分内容，双方积极互动 |
| `teaching`    | 教学模式：老师与学生之间的教学对话 |
| `argument`    | 争论模式：主持人与嘉宾持有不同观点进行辩论 |
| `interview`   | 面试模式：面试官提问，应试者回答，适用于技术类文章 |

> ⚠️ 注意：以上参数均为大致控制，实际输出可能略有浮动。

---

## 🧪 使用示例

基础使用：
```bash
python notelm.py --input sample.pdf --output_dir ./output --prompt_type discussion
```

启用 ReAct 模式（实验性）：
```bash
python notelm_react.py --input sample.pdf --output_dir ./output --count 5
```

---

## 📌 开发计划 & 待改进点

- 🔜 对项目进行改造，支持MCP（即将上线）
- 🔜 支持更多合成模型
- 🔜 增加图形界面（GUI）支持
- 🔜 支持视频生成 + 字幕嵌入
- 🔜 支持 Markdown 或 Word 格式输入

---

## 🤝 贡献指南

欢迎任何形式的贡献！无论是提出建议、提交 Issue 还是 Pull Request，都十分欢迎你的参与！

---

## 📄 许可证

本项目采用 [Apache 2.0 License](LICENSE) 开源协议。

---

## ❤️ 致谢

- 感谢 [Google NotebookLM](https://notebooklm.withgoogle.com/) 提供灵感
- 感谢 [open-notebooklm](https://github.com/lfnovo/open-notebook) 提供思路参考
- 感谢 [DeepSeek](https://platform.deepseek.com/) 和 [CosyVoice](https://github.com/FunAudioLLM/CosyVoice) 提供核心技术支撑

---

如果你喜欢这个项目，欢迎 Star、Fork 并分享给更多人！🚀  
有任何疑问或建议，也欢迎在 Issues 区留言。


