# NotebookLM-Lite

[中文](./README_zh.md) | [English](./README.md)

NotebookLM-Lite is an open-source NotebookLM-style AI knowledge workspace for local files, grounded RAG chat, notes, interactive Studio artifacts, and long-form podcast generation. It is built for people who like the Google NotebookLM workflow but want a hackable, self-hosted project with their own model endpoints, their own document pipeline, and a clear backend architecture.

NotebookLM-Lite is not affiliated with Google NotebookLM. The goal is to bring most of the NotebookLM learning and research experience into an open project: source-grounded answers, citations, mind maps, flashcards, quizzes, reports, data tables, infographics, podcast/audio overviews, notes, native slide deck workflows, and future video workflows.

![NotebookLM-Lite workbench demo](docs/assets/notebooklm-lite-demo.gif)

[Watch the HD demo video](docs/assets/notebooklm-lite-demo.webm)

The demo uses [doc/L9.md](doc/L9.md) as the sample source and shows model configuration, source upload, cited RAG chat, interactive Mind Map, Flashcards/Quiz, Data Table, Podcast, and the Video Overview placeholder. Model waiting time is shortened for README pacing.

## Why NotebookLM-Lite

NotebookLM-style tools are becoming the default interface for working with long documents, research notes, study material, product manuals, papers, and course content. NotebookLM-Lite focuses on the same core loop:

1. Add sources to a notebook-like knowledge base.
2. Ask questions grounded in selected sources.
3. Save useful answers and notes back into the knowledge base.
4. Generate structured outputs such as maps, quizzes, reports, tables, infographics, and podcasts.
5. Keep every generated artifact downloadable and inspectable.

That makes the project useful as a NotebookLM alternative, a RAG notebook starter, an AI study assistant, a document Q&A system, and a backend reference for multi-step AI workflows.

## Highlights

- **NotebookLM-like three-panel workspace**: sources on the left, grounded chat in the center, Studio artifacts and generated files on the right.
- **Multi-format source ingestion**: upload or paste sources such as PDF, DOCX, TXT, Markdown, HTML, CSV, JSON, and YAML.
- **Document intelligence pipeline**: Docling extracts document text, Chonkie chunks it, and SeekDB persists sources, chunks, notes, jobs, and artifacts.
- **Hybrid RAG retrieval**: SeekDB combines lexical BM25-style recall, optional embeddings, optional rerank, selected-source filtering, and citations.
- **Streaming grounded chat**: ask questions over selected sources, render Markdown answers, and keep citations attached to retrieved chunks.
- **Notes as first-class knowledge**: create notes, save chat answers as notes, and convert notes back into sources for later RAG.
- **Interactive Studio artifacts**: generate Mind Maps, FAQ, Flashcards/Quiz, Reports/Study Guides, Data Tables, SVG Infographics, Podcast scripts, and Slide Decks from selected sources.
- **NotebookLM-like study UX**: flashcards flip, quizzes show feedback and scores, mind maps expand, tables render as tables, and artifacts can be downloaded as Markdown/JSON/SVG where applicable.
- **Native Slide Deck workspace**: generate a deck outline, confirm/edit it, generate a per-slide image prompt plan, confirm/edit it, render slide images, regenerate or edit one slide, and export an image-based PPTX.
- **Podcast and Audio Overview workflow**: structured podcast scripts are generated with Pydantic validation and can be expanded toward controllable durations up to 30 minutes; speech generation is optional when a compatible audio model is configured.
- **Unified model runtime**: LiteLLM manages text generation, embeddings, rerank, and OpenAI-compatible speech profiles. OpenAI-compatible, Anthropic, Gemini/GenAI-style, and custom gateway deployments can be configured from `config.yaml`.
- **Extensible backend boundaries**: FastAPI owns resource APIs, while longer workflows are isolated for future LangGraph orchestration, Deep Research, richer Slide Deck automation, and Video Overview support.

## Capability Map

| Capability | Status | Notes |
| --- | --- | --- |
| Source upload and pasted text | Available | File sources and text sources are stored in SeekDB. |
| RAG chat with citations | Available | Supports selected sources, Markdown answers, and streaming response UI. |
| Notes | Available | Create notes, save answers as notes, and convert notes into sources. |
| Mind Maps | Available | Structured tree output with expandable frontend viewer. |
| FAQ | Available | Structured FAQ generated from selected sources. |
| Flashcards and Quizzes | Available | Flip-card viewer plus quiz feedback, score, and retake. |
| Reports and Study Guides | Available | Structured summaries, sections, and takeaways. |
| Data Tables | Available | Rendered as real tables and downloadable as artifact data. |
| Infographics | Available | Structured SVG infographic generation and safe image rendering. |
| Podcast / Audio Overview | Available | Script generation is core; audio download is available when speech config is valid. |
| Runtime model configuration | Available | Separate text, embedding, rerank, speech, image, and edit profiles. |
| Deep Research | Placeholder | API/job boundary exists so future research output can be saved as a source. |
| Slide Deck / PPT | Available | Native Slide Deck workspace with two confirmation steps, generated slide previews, single-slide regenerate/edit, and image-based PPTX export. |
| Video Overview | Placeholder | Studio card is present and shows an in-development notice. |

## Architecture

```text
frontend/
  React + Vite workbench
  SourcePanel, ChatPanel, NotesPanel, StudioPanel, ArtifactViewer, SlideDeckWorkspace

backend/
  FastAPI routes for sources, chat, notes, artifacts, podcast, slide decks, config
  Docling parser + Chonkie chunking
  SeekDB repository and vector-store adapter
  LiteLLM provider for text, structured output, embeddings, and rerank
  Podcast workflow with Pydantic structured output
  Native slide deck workflow with generated image assets and PPTX export
```

Key backend choices:

- **FastAPI** for CRUD, list, download, runtime config, and status APIs.
- **Docling** for document parsing.
- **Chonkie** for chunking, with a simple fallback.
- **SeekDB** as the project knowledge repository.
- **LiteLLM** as the unified model access layer.
- **Pydantic structured output** for Studio artifacts and podcast scripts.
- **Native Slide Deck workflow** integrated into NotebookLM-Lite state, jobs, artifacts, model config, and downloads.

## Getting Started

### Requirements

- Python 3.10+
- Node.js 18+
- A text model endpoint configured in `config.yaml`
- Optional: embedding, rerank, and speech model endpoints

### Backend

```bash
pip install -r requirements.txt
cp config_example.yaml config.yaml
```

Edit `config.yaml` and fill in the profiles you want to use:

- `api.models.text_model`: chat, RAG answers, Studio artifacts, podcast scripts
- `api.models.embedding_model`: optional vector retrieval
- `api.models.rerank_model`: optional rerank
- `api.models.audio_model`: optional speech/audio generation
- `api.models.image_model`: slide image generation
- `api.models.edit_model`: single-slide image editing
- `storage.seekdb_path`: local knowledge database
- `documents.chunking`: Chonkie/simple chunking settings

Keep `config.yaml` local. It is ignored by git and should not contain committed keys.

Start the backend:

```bash
python -m backend.main
```

The API runs at `http://localhost:8000`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Usage

1. Open the workbench and check the settings panel.
2. Upload a source file or paste text in the Sources panel.
3. Select one or more sources.
4. Ask source-grounded questions in Chat.
5. Save useful answers as notes or sources.
6. Generate Studio artifacts:
   - Podcast
   - Mind Map
   - FAQ
   - Flashcards / Quiz
   - Report / Study Guide
   - Data Table
   - Infographic
   - Slide Deck / PPT
7. For Slide Decks, open the dedicated workspace, generate and confirm the outline, generate and confirm the prompt plan, render slide images, optionally regenerate or edit one slide, then export/download the PPTX.
8. Download generated artifacts as Markdown, JSON, SVG, transcript, PPTX, or audio where supported.

## Testing

Backend:

```bash
PYTHONPATH=. pytest -q
PYTHONPATH=. python -m compileall -q backend
```

Frontend:

```bash
cd frontend
npm run build
npm run test
npm run test:e2e -- --project=chromium
```

OpenSpec:

```bash
openspec validate notebooklm-slide-deck-heavy-integration --strict
```

## Current Scope and Roadmap

NotebookLM-Lite already covers the core NotebookLM-style loop: sources, cited chat, notes, Studio study artifacts, data tables, infographics, podcast scripts/audio, and native Slide Deck generation with image-based PPTX export. The next major areas are:

- Real Video Overview generation instead of the current placeholder card.
- Stronger Deep Research workflows that can search, synthesize, and save research reports as sources.
- More export targets, including CSV/Sheets-style table export and richer artifact sharing.
- More source types, such as URLs, audio, images, YouTube, and Google Drive-style integrations.

## Slide Deck Notes

The Slide Deck integration is intentionally native to NotebookLM-Lite:

- It uses the same source selection, LiteLLM/runtime model configuration, SeekDB persistence, job APIs, artifact list, and download flow as the rest of the app.
- The workflow has two human confirmation points: outline confirmation and prompt-plan confirmation.
- Phase 1 exports a PPTX where each slide is a generated full-slide image. This is a PPTX export, not a promise that every PowerPoint element is a native editable shape.
- Image generation and editing use the same NotebookLM-Lite runtime model profiles as the rest of the app; credentials stay in local ignored config files.
- The integrated workflow is native to this repository and does not require running a separate AIPPT server.

## License

Apache 2.0
