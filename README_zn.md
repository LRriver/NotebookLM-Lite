# NotebookLM-Lite

中文 | [English](./README.md)

NotebookLM-Lite是一个基于 Google NotebookLM 应用思路实现的笔记应用，目标是全面复刻资料问答，播客生成，PPT制作等功能，目前仍处于开发阶段，简易的中文播客生成功能请参考v0.1 分支


## ✨ 核心特性

- **统一的大模型接口**：支持无缝切换 OpenAI 兼容接口（如 DeepSeek, Moonshot）和 Anthropic 模型。
- **语音合成**：使用 CosyVoice (通过 Dashscope) 生成高质量、多角色的播客对话。
- **智能 PDF 解析**：强大的文档解析能力，精准提取核心内容。
- **交互式播放器**：内置音频播放器，支持在线播放和下载。

## 🛠️ 技术栈

- **前端**: React, Vite, TailwindCSS, Framer Motion (动画)
- **后端**: Python, FastAPI, Uvicorn
- **AI/ML**: OpenAI API, Anthropic API, Dashscope (TTS)

## 🚀 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- FFmpeg (必须安装并添加到系统 PATH 环境变量中)

### 安装步骤

#### 1. 后端设置

在项目根目录下运行：

```bash
# 安装 Python 依赖
pip install -r requirements.txt

# 启动 API 服务器
python backend/main.py
```
后端服务将在 `http://localhost:8000` 启动。

#### 2. 前端设置

打开一个新的终端窗口，进入 `frontend` 目录：

```bash
cd frontend

# 安装 Node 依赖
npm install

# 启动开发服务器
npm run dev
```
前端界面将在 `http://localhost:5173` 启动。

## 📖 使用指南

1.  **启动**：在浏览器中打开 `http://localhost:5173`。
2.  **配置**：
    *   选择 **LLM 提供商** (OpenAI Compatible 或 Anthropic)。
    *   输入你的 **API Key** 和 **模型名称** (例如 `gpt-4o` 或 `deepseek-chat`)。
    *   输入 **Dashscope API Key** (用于语音合成)。
3.  **上传**：将 PDF 文件拖拽到 "Data Source" 区域。
4.  **生成**：点击 **INITIALIZE SEQUENCE** (初始化序列)。系统将开始处理文本并合成音频。
5.  **收听**：使用内置播放器收听播客，或点击下载按钮保存音频。

## � 许可证

Apache 2.0



