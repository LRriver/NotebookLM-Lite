# NotebookLM-Lite

中文 | [English](./README.md)

NotebookLM-Lite是一个基于 Google NotebookLM 应用思路实现的笔记应用，目标是全面复刻资料问答，播客生成，PPT制作等功能，目前仍处于开发阶段，简易的中文播客生成功能请参考v0.1 分支

![NotebookLM-Lite 工作台演示](docs/assets/notebooklm-lite-demo.gif)

[查看高清演示视频](docs/assets/notebooklm-lite-demo.webm)

演示视频覆盖模型配置入口、添加来源、带引用的 RAG 问答、交互式思维图谱、学习卡片/测验、数据表、播客以及视频概览占位 artifact；为了 README 展示节奏，模型等待时间已做压缩。


## ✨ 核心特性

- **统一的大模型接口**：文本生成、embedding、rerank 和语音模型通过 LiteLLM/OpenAI-compatible 配置统一管理。
- **语音合成**：使用 CosyVoice (通过 Dashscope) 生成高质量、多角色的播客对话。
- **智能文档处理**：Docling 解析文件，Chonkie 负责切分 chunk，SeekDB 存储来源/切片并支持带引用的混合 RAG 检索。
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

# 创建本地配置文件
cp config_example.yaml config.yaml
```

编辑 `config.yaml`，填写你要使用的模型凭证。文本模型、embedding 模型、可选 rerank
模型和语音模型在 `api.models` 下分别配置。默认文本模型路径走
LiteLLM/OpenAI-compatible 配置，也可以通过 LiteLLM 兼容模型字符串接入
Anthropic、Gemini/GenAI 等接口。
`config.yaml` 只用于本地测试，已被 git 忽略，不能提交真实 key。

```bash

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
    *   在 `config.yaml` 中分别配置文本模型、embedding 模型、可选 rerank 模型和可选的语音模型。
    *   前端设置按钮会读取本地默认配置，并可刷新运行时模型 profile；已配置的 key 只显示状态，不回传明文。
    *   如果所选后端支持，可通过文本模型 thinking 开关控制长任务延迟。
    *   文本 artifact 生成不依赖语音凭证；没有 TTS 配置时仍可生成播客脚本。
3.  **上传**：在 Sources 区域上传文件或粘贴文本；新资料会使用 Chonkie 切分，并在配置可用时生成 embedding。
4.  **问答与生成**：选择来源后进行带引用的 RAG 问答，或生成工作室里的文本 artifact 和播客脚本。
5.  **收听**：使用内置播放器收听播客，或点击下载按钮保存音频。

## � 许可证

Apache 2.0
