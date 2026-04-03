## Why

NotebookLM-Lite currently has a polished three-column frontend and partial backend scaffolding, but the backend does not yet provide a complete text-first NotebookLM-style loop: robust source ingestion, persistent knowledge-base retrieval, unified model routing, structured Studio artifacts, or controllable long podcast scripts.

This change turns the existing UI direction into an implementation-ready product slice by prioritizing text capabilities that can be tested with the local `config.yaml` model setup and by using the configured `api.models.audio_model` to exercise the full podcast script-to-audio flow. Image-heavy PPT generation, video overview, and full Deep Research remain extensible follow-up workflows.

## What Changes

- Add a text-first source ingestion pipeline using Docling for document conversion, chunking, metadata extraction, and source persistence.
- Replace the current Chroma/OpenAI-specific vector path with SeekDB embedded storage through `pyseekdb`, while keeping source, chunk, artifact, and job records durable across backend restarts.
- Replace provider-specific LLM implementations with a LiteLLM-based text model runtime that supports OpenAI-compatible, Anthropic, and Gemini/GenAI-style model strings, API keys, and base URLs.
- Add a model-level thinking toggle for text generation, passing `{"thinking": {"type": "enabled"}}` or `{"thinking": {"type": "disabled"}}` when the selected backend supports it, so users can trade reasoning depth for latency.
- Add an audio model runtime for configured OpenAI-compatible `/audio/speech` endpoints, using the same model configuration discipline as LiteLLM and preferring LiteLLM/OpenAI-compatible speech routing where available.
- Add source-scoped RAG chat that lets users ask questions against selected sources and returns citations linked to stored chunks.
- Add a Studio artifact system for text-generated outputs: mind map / 思维图谱, FAQ, flashcards/quiz, report/study guide, data table, podcast script, and PPT placeholders.
- Add a podcast workflow that uses Pydantic structured output and an iterative expansion graph to support user-selected duration up to 30 minutes, then synthesizes MP3 audio when `audio_model` is configured.
- Keep script generation resilient: if no speech model is configured or audio synthesis fails, podcast script generation still succeeds and produces a downloadable transcript artifact with a clear audio-unavailable state.
- Expose a Deep Research placeholder API that can create a job and save future research output as a normal source, without implementing the full external research agent in this change.
- Redesign the frontend around the existing left/middle/right layout: left sources, middle source-scoped chat, right Studio tools and generated artifacts, with responsive behavior and real artifact preview/download affordances.
- Integrate with the existing AIPPT project through a backend adapter boundary for future PPT generation/export, but do not make image model execution a first-phase acceptance requirement.
- **BREAKING**: Current `/api/documents/*`, `/api/chat/`, and `/api/podcast/*` request/response shapes may change to the new source, chat, artifact, and job contracts.

## Capabilities

### New Capabilities

- `source-knowledge-base`: Covers multi-format source ingestion, Docling conversion, chunking, metadata, source selection, deletion, and SeekDB-backed persistence/search.
- `model-runtime`: Covers LiteLLM text model configuration, OpenAI-compatible/Anthropic/Gemini support, structured output, thinking toggle, audio model configuration, local config loading, and safe example configuration.
- `rag-chat`: Covers source-scoped RAG queries, citations, conversation history, and saving chat/research outputs back as sources.
- `studio-artifacts`: Covers text-generated Studio outputs, artifact persistence, job status, preview/download behavior, and placeholders for future PPT/video/infographic features.
- `podcast-script-workflow`: Covers structured podcast script generation, user-selected duration up to 30 minutes, expansion workflow behavior, transcript artifacts, configured audio synthesis, MP3 download, and script-only fallback.
- `frontend-workbench`: Covers the user-facing left/middle/right workbench layout, model configuration UI, responsive behavior, and artifact interaction patterns.

### Modified Capabilities

- None. The project has no existing OpenSpec specs.

## Impact

- Backend: FastAPI routes, schemas, dependency container, document parsing, vector storage, RAG service, podcast workflow, audio synthesis, configuration loading, and artifact/job services.
- Frontend: React state model, source panel, chat panel, Studio panel, configuration modal, artifact preview/download controls, responsive CSS, and TypeScript build setup.
- Dependencies: add `docling`, `litellm`, `pyseekdb`, and `langgraph`; add or retain an OpenAI-compatible streaming audio client path for `/audio/speech`; retain AIPPT integration behind an adapter boundary.
- Data/storage: replace in-memory document cache and Chroma-specific persistence with a SeekDB-backed local store under an ignored data directory.
- Documentation: update `config_example.yaml` and README setup instructions so users copy it to local `config.yaml`; local keys in `config.yaml` remain ignored and must not be committed.
