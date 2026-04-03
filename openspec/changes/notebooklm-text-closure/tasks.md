## 1. Baseline And Configuration

- [x] 1.1 Add backend test scaffolding with pytest and fixture utilities for temporary data directories, fake LiteLLM responses, and fake SeekDB repositories.
- [x] 1.2 Add missing frontend TypeScript configuration so `npm run build` can run from `frontend/`.
- [x] 1.3 Update `requirements.txt` with `docling`, `litellm`, `pyseekdb`, `langgraph`, `pytest`, and required FastAPI/runtime packages.
- [x] 1.4 Replace the empty `config_example.yaml` with a safe example covering text model, text thinking toggle, embedding model, `audio_model`, image/edit models, storage, chunking, and output directories.
- [x] 1.5 Update README setup instructions to copy `config_example.yaml` to ignored local `config.yaml` and configure text-model credentials without committing keys.
- [x] 1.6 Add a smoke test that imports backend settings without reading real local secrets.

## 2. Source Knowledge Base

- [x] 2.1 Define source, chunk, artifact, and job domain models with durable IDs, statuses, timestamps, selected metadata fields, and downloadable file references.
- [x] 2.2 Implement a Docling parser service that converts supported uploaded files to canonical Markdown/text and falls back to plain text for simple text-like inputs.
- [x] 2.3 Implement chunking with configurable chunk size/overlap and citation metadata including source ID, chunk index, filename/title, parser metadata, and offsets when available.
- [x] 2.4 Implement a SeekDB embedded repository wrapper around `pyseekdb` for source, chunk, artifact, job, and vector-search operations.
- [x] 2.5 Add a fake in-memory repository for tests with the same repository interface.
- [x] 2.6 Replace the in-memory `_documents_cache` path with repository-backed source persistence.
- [x] 2.7 Add `/api/sources/upload`, `/api/sources/text`, `/api/sources`, `/api/sources/{id}`, and `/api/sources/{id}` delete endpoints.
- [x] 2.8 Add tests for successful upload, parse failure, backend restart persistence, chunk metadata, and source deletion excluding chunks from retrieval.

## 3. LiteLLM Model Runtime

- [x] 3.1 Create a `LiteLLMProvider` that supports text completion, structured completion with Pydantic validation, embeddings, and optional thinking passthrough.
- [x] 3.2 Map frontend model configuration to LiteLLM model strings for OpenAI-compatible, Anthropic, and Gemini/GenAI-style usage.
- [x] 3.3 Implement thinking enabled/disabled request handling using `{"thinking": {"type": "enabled"}}` or `{"thinking": {"type": "disabled"}}` for compatible backends, with safe omission or clear errors for incompatible backends.
- [x] 3.4 Implement structured-output retry once when model output fails Pydantic validation.
- [x] 3.5 Replace OpenAI/Google-specific LLM provider wiring in dependency construction with the LiteLLM provider.
- [x] 3.6 Update embedding generation so SeekDB ingestion and query search use the configured embedding model instead of hard-coded OpenAI embeddings.
- [x] 3.7 Implement an `AudioSpeechProvider` that reads `api.models.audio_model`, prefers LiteLLM/OpenAI-compatible speech routing when available, and otherwise streams `/audio/speech` responses to MP3 files through the same provider interface.
- [x] 3.8 Add model-runtime tests for provider mapping, base URL forwarding, thinking passthrough, structured validation success, structured validation retry/failure, embedding calls, and audio streaming payloads.

## 4. RAG Chat

- [x] 4.1 Redesign chat request/response schemas around `query`, required `source_ids`, optional history, model config, answer text, and citation entries.
- [x] 4.2 Implement source-scoped retrieval so only selected source IDs contribute chunks to a chat answer.
- [x] 4.3 Add history-aware query contextualization without allowing retrieval outside selected sources.
- [x] 4.4 Return citations with source ID, source title/filename, chunk ID, score, and excerpt text.
- [x] 4.5 Add an endpoint or action to save selected chat answers as new reusable sources.
- [x] 4.6 Add tests for selected-source restriction, empty-source rejection, no-results response, citation content, follow-up handling, and save-answer-as-source.

## 5. Studio Artifacts

- [x] 5.1 Define artifact schemas for mind map / 思维图谱, FAQ, flashcards/quiz, report/study guide, data table, podcast script, and PPT outline/placeholder.
- [x] 5.2 Implement a generic artifact generation service that creates jobs, gathers selected source context, calls LiteLLM structured output, validates payloads, and persists artifacts.
- [x] 5.3 Implement first-phase text artifact generators for mind map / 思维图谱, FAQ, flashcards/quiz, report/study guide, and data table.
- [x] 5.4 Add artifact listing, detail, preview payload, and Markdown/JSON download endpoints.
- [x] 5.5 Add `/api/research/jobs` placeholder behavior that records the requested research job shape and can later save research output as a source.
- [x] 5.6 Add an AIPPT adapter boundary for future PPT outline/prompts/export integration without making image generation mandatory.
- [x] 5.7 Add tests for each text artifact type, invalid structured output, job status transitions, download output, and disabled visual artifact behavior.

## 6. Podcast Script Workflow

- [x] 6.1 Expand podcast duration options and schemas to support user-selected durations up to 30 minutes.
- [x] 6.2 Implement a LangGraph podcast script workflow with planning, initial dialogue batch, critique/coverage check, expansion loop, and final transcript assembly.
- [x] 6.3 Enforce Pydantic validation for script title, speakers, dialogue turns, coverage notes, estimated duration, and transcript.
- [x] 6.4 Synthesize MP3 audio from the generated transcript when `api.models.audio_model` is configured, using configured model, base URL, API key, voice, response format, and streaming behavior.
- [x] 6.5 Make script-only podcast artifact generation succeed when no TTS configuration is present or audio synthesis fails, while recording a clear audio status/error.
- [x] 6.6 Attach audio URL, local download metadata, transcript download metadata, and duration estimates to successful podcast artifacts.
- [x] 6.7 Add tests for short script generation, 20-30 minute expansion, bounded failure when duration cannot be reached, no-TTS success, audio streaming when TTS is mocked, and audio failure preserving the script.

## 7. Frontend Workbench

- [x] 7.1 Refactor app state around persisted sources, selected source IDs, chat messages with citations, Studio jobs, and artifact lists.
- [x] 7.2 Update the source panel to upload supported formats, add pasted text, show processing/error states, search, select/unselect, and delete persisted sources.
- [x] 7.3 Update the chat panel to require selected sources, render citations, handle follow-up history, and offer saving answers as sources.
- [x] 7.4 Update the Studio panel so mind map / 思维图谱, FAQ, flashcards/quiz, report/study guide, data table, and podcast script tools are enabled when sources and text config are available.
- [x] 7.5 Implement artifact cards with expand/collapse previews, transcript display, JSON/Markdown downloads, real audio controls when audio exists, and PPT placeholder preview behavior.
- [x] 7.6 Update the settings modal to configure text and speech models separately, including text thinking enabled/disabled, text LiteLLM-compatible fields, and speech model/base URL/API key/voice/response format fields.
- [x] 7.7 Redesign the title/header and responsive layout so desktop three-column and narrow/mobile views do not clip or compress panels.
- [x] 7.8 Add frontend build verification and browser smoke checks for source upload flow, selected-source chat, text artifact generation, podcast script preview, settings, and responsive breakpoints.

## 8. Validation And Cleanup

- [x] 8.1 Run `openspec validate notebooklm-text-closure --strict` and fix any spec/task formatting errors.
- [x] 8.2 Run backend unit and integration tests for source ingestion, model runtime, RAG, artifacts, and podcast workflow.
- [x] 8.3 Run `npm run build` in `frontend/` and fix TypeScript or bundling errors.
- [x] 8.4 Start the backend and frontend locally, then verify the primary text closure path in the browser.
- [x] 8.5 With local `config.yaml` text and `audio_model` credentials, run a full podcast smoke test from selected sources through script generation, audio synthesis, browser playback, and MP3 download; if latency is excessive, repeat with thinking disabled and record the result.
- [x] 8.6 Remove or deprecate old Chroma/OpenAI-specific and in-memory document code only after the new routes pass smoke tests.
- [x] 8.7 Confirm `config.yaml`, local data directories, generated output, `.codex/`, and cloned `seekdb/` remain ignored and are not staged.
