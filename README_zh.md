# NotebookLM-Lite

[中文](./README_zh.md) | [English](./README.md)

NotebookLM-Lite 是一个开源的 NotebookLM 风格 AI 知识工作台，用于把本地资料变成可问答、可整理、可生成内容的知识库。它面向长文档阅读、课程学习、论文/手册分析、产品资料整理、播客脚本生成、RAG 应用原型等场景，目标是在一个可自托管、可改造、可接入自定义模型的项目里，复刻大部分 NotebookLM 的核心体验。

NotebookLM-Lite 与 Google NotebookLM 没有关联。这个项目借鉴的是 NotebookLM 的产品形态：添加资料、基于资料问答、保存笔记、生成思维导图、学习卡片、测验、报告、数据表、信息图和播客等 Studio 内容。

![NotebookLM-Lite 工作台演示](docs/assets/notebooklm-lite-demo.gif)

[查看高清演示视频](docs/assets/notebooklm-lite-demo.webm)

演示视频使用 [doc/L9.md](doc/L9.md) 作为默认示例资料，覆盖模型配置、添加来源、带引用的 RAG 问答、交互式思维图谱、学习卡片/测验、数据表、播客，以及视频概览占位入口。为了 README 展示节奏，视频里压缩了模型等待时间。

## 为什么做 NotebookLM-Lite

NotebookLM 这类产品正在成为处理长资料、学习材料、研究笔记和复杂文档的新入口。NotebookLM-Lite 聚焦同一个核心闭环：

1. 把资料加入 notebook-like 知识库。
2. 只基于选中的资料进行问答。
3. 把有价值的回答和笔记保存回知识库。
4. 生成结构化内容：思维图谱、测验、报告、表格、信息图、播客。
5. 让生成内容可浏览、可下载、可继续作为资料使用。

因此它既可以作为 NotebookLM alternative / 开源替代探索，也可以作为 RAG notebook、AI 学习助手、文档问答系统、多阶段 AI 工作流后端的参考项目。

## 核心亮点

- **NotebookLM-like 三栏工作台**：左侧 Sources，中央 Chat，右侧 Studio 与生成内容。
- **多格式资料输入**：支持上传或粘贴 PDF、DOCX、TXT、Markdown、HTML、CSV、JSON、YAML 等资料。
- **文档智能处理管线**：Docling 负责解析，Chonkie 负责切分 chunk，SeekDB 持久化 sources、chunks、notes、jobs 和 artifacts。
- **混合 RAG 检索**：SeekDB 支持 BM25 风格词法召回、可选 embedding、可选 rerank、按选中 source 限定检索，并返回 citation。
- **流式资料问答**：Chat 面板支持基于资料的流式回答、Markdown 渲染和引用来源展示。
- **笔记进入知识闭环**：可以手写笔记、把回答保存为笔记，也可以把笔记转换成新的 source 继续问答。
- **Studio 文本闭环**：支持生成思维图谱、FAQ、Flashcards/Quiz、报告/学习指南、数据表、SVG 信息图、播客脚本等。
- **更接近 NotebookLM 的交互体验**：卡片可翻面，Quiz 可答题/看分数/重做，思维图谱可展开，数据表按表格渲染，信息图安全渲染为图片。
- **播客 / Audio Overview 工作流**：播客脚本使用 Pydantic 结构化输出约束，可向最长 30 分钟扩展；配置语音模型后可生成并下载音频。
- **统一模型接入**：LiteLLM 统一管理文本生成、embedding、rerank、OpenAI-compatible speech；可接 OpenAI-compatible、Anthropic、Gemini/GenAI 风格接口或自建网关。
- **面向扩展的架构边界**：FastAPI 负责资源接口，长流程为 LangGraph、Deep Research、Slide Deck、Video Overview 等后续能力预留边界。

## 功能矩阵

| 功能 | 状态 | 说明 |
| --- | --- | --- |
| 文件上传和粘贴文本 | 已支持 | 文件 source 和文本 source 会进入 SeekDB。 |
| 带引用 RAG 问答 | 已支持 | 支持选中来源、流式回答、Markdown 和 citation。 |
| Notes 笔记 | 已支持 | 创建笔记、保存回答为笔记、笔记转 source。 |
| 思维图谱 | 已支持 | 结构化树形输出，前端可展开浏览。 |
| FAQ | 已支持 | 基于选中资料生成结构化问答。 |
| Flashcards / Quizzes | 已支持 | 翻卡、答题、反馈、得分、重做。 |
| Reports / Study Guides | 已支持 | 生成摘要、章节和 key takeaways。 |
| Data Tables | 已支持 | 前端按真实表格渲染，可下载 artifact 数据。 |
| Infographics 信息图 | 已支持 | 生成结构化 SVG 信息图，并以安全图片方式渲染。 |
| Podcast / Audio Overview | 已支持 | 脚本生成是核心；配置语音模型后可下载音频。 |
| 运行时模型配置 | 已支持 | 文本、embedding、rerank、语音、图像、编辑模型分开配置。 |
| Deep Research | 占位边界 | 已有 API/job placeholder，后续可把研究报告保存为 source。 |
| Slide Deck / PPT | Adapter 边界 | 已有 AIPPT 集成边界，完整浏览/下载流程暂未开放。 |
| Video Overview | 占位入口 | Studio 卡片已存在，点击提示功能开发中。 |

## 架构

```text
frontend/
  React + Vite 工作台
  SourcePanel, ChatPanel, NotesPanel, StudioPanel, ArtifactViewer

backend/
  FastAPI routes: sources, chat, notes, artifacts, podcast, config
  Docling parser + Chonkie chunking
  SeekDB repository and vector-store adapter
  LiteLLM provider for text, structured output, embeddings, rerank
  Podcast workflow with Pydantic structured output
```

关键技术选择：

- **FastAPI**：负责 CRUD、列表、下载、运行时配置和状态查询。
- **Docling**：统一解析文档资料。
- **Chonkie**：负责 chunk 切分，缺失时回退到 simple splitter。
- **SeekDB**：作为项目知识库与 artifact repository。
- **LiteLLM**：统一模型调用入口。
- **Pydantic structured output**：约束 Studio artifacts 和播客脚本生成格式。

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- 一个可用的文本模型接口
- 可选：embedding、rerank、语音模型接口

### 后端

```bash
pip install -r requirements.txt
cp config_example.yaml config.yaml
```

编辑 `config.yaml`，填写模型与存储配置：

- `api.models.text_model`：聊天、RAG 回答、Studio artifact、播客脚本
- `api.models.embedding_model`：可选向量召回
- `api.models.rerank_model`：可选 rerank
- `api.models.audio_model`：可选语音/音频生成
- `storage.seekdb_path`：本地知识库路径
- `documents.chunking`：Chonkie/simple chunk 参数

`config.yaml` 只用于本地运行，已被 git 忽略，不要提交真实 key。

启动后端：

```bash
python -m backend.main
```

API 默认运行在 `http://localhost:8000`。

### 前端

```bash
cd frontend
npm install
npm run dev
```

打开 `http://localhost:5173`。

## 使用流程

1. 打开工作台，检查右上角 Settings 中的模型配置。
2. 在 Sources 面板上传文件或粘贴文本。
3. 选择一个或多个 source。
4. 在 Chat 中基于选中资料提问。
5. 把有价值的回答保存为笔记或 source。
6. 在 Studio 中生成内容：
   - 播客
   - 思维图谱
   - FAQ
   - 学习卡片 / 测验
   - 报告 / 学习指南
   - 数据表
   - 信息图
7. 根据 artifact 类型下载 Markdown、JSON、SVG、transcript 或音频。

## 测试

后端：

```bash
PYTHONPATH=. pytest -q
PYTHONPATH=. python -m compileall -q backend
```

前端：

```bash
cd frontend
npm run build
npm run test
npm run test:e2e -- --project=chromium
```

OpenSpec：

```bash
openspec validate notebooklm-text-closure --strict
```

## 当前范围与路线图

NotebookLM-Lite 已覆盖 NotebookLM 文本闭环的大部分核心能力：资料输入、带引用问答、笔记、Studio 学习类 artifacts、数据表、信息图、播客脚本和可选音频。接下来重点会补齐：

- 完整 Slide Deck / PPT 集成，基于当前 AIPPT adapter 边界继续推进。
- 真正的视频概览生成，目前前端是占位提示。
- 更完整的 Deep Research 工作流：联网检索、综合报告、保存为 source。
- 更多导出方式，例如 CSV/Sheets 风格表格导出和 artifact 分享。
- 更多 source 类型，例如 URL、音频、图片、YouTube、Google Drive 风格接入。

## 许可证

Apache 2.0
