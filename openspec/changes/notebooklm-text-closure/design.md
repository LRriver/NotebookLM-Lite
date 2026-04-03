## Context

NotebookLM-Lite is a FastAPI + React/Vite application with a three-column frontend that already expresses the intended product shape: sources on the left, source-scoped chat in the middle, and Studio tools/artifacts on the right. The backend is only a partial scaffold: document metadata is cached in memory, retrieval is tied to Chroma/OpenAI embeddings, provider logic is split across hand-written OpenAI/Google classes, Studio tools other than podcast are disabled, and podcast generation cannot reliably produce long structured scripts.

The first implementation slice is text-first for reasoning and artifact planning, but the local `config.yaml` now also contains `api.models.audio_model` for SiliconFlow-style OpenAI-compatible speech synthesis. The design therefore prioritizes source ingestion, knowledge-base retrieval, structured text artifacts, podcast script generation, and full podcast MP3 synthesis when audio is configured, while keeping image-heavy PPT, video overview, infographic, and full external Deep Research as compatible follow-ups.

## Goals / Non-Goals

**Goals:**

- Ingest document-like sources with Docling, convert them to Markdown/text, chunk them, and persist sources/chunks durably.
- Use SeekDB through `pyseekdb` embedded mode as the default local knowledge-base and retrieval store.
- Use LiteLLM as the main text model runtime so OpenAI-compatible, Anthropic, and Gemini models share one code path.
- Support a user-visible thinking toggle for text model calls, allowing high-latency reasoning to be disabled for long generation tests when the backend accepts a `thinking` parameter.
- Support source-selected RAG chat with citations and saved outputs.
- Generate text Studio artifacts in the first phase, including mind map / 思维图谱, FAQ, flashcards/quiz, report/study guide, data table, and podcast transcript/script.
- Use local LangGraph workflows only for long-running or multi-step tasks: ingestion, Studio artifact generation, podcast script expansion, Deep Research placeholder, and future PPT generation.
- Keep simple FastAPI routes and services for CRUD-style source, artifact, config, download, and job status operations.
- Use the configured `audio_model` to run podcast script-to-MP3 smoke tests; keep script-only fallback only for missing or failed speech synthesis.
- Make the existing frontend workbench responsive and usable without requiring image-model configuration.

**Non-Goals:**

- Do not fully re-platform every backend endpoint into LangGraph.
- Do not require speech synthesis to succeed before preserving a valid podcast transcript/script artifact.
- Do not make full AIPPT image generation, video overview, or infographic generation a first-phase acceptance requirement.
- Do not implement a real web-browsing Deep Research agent in this change; only define and expose the job/source contract.
- Do not commit local secrets from `config.yaml`; only commit a safe `config_example.yaml`.

## Decisions

### Use partial LangGraph, not a full rewrite

Decision: introduce LangGraph for multi-step workflows and keep FastAPI services as the main application boundary.

Rationale: source ingestion, long podcast expansion, Deep Research, and PPT generation benefit from explicit graph nodes, retries, progress, and resumable state. Simple resource operations such as listing sources, deleting artifacts, downloading files, or reading job status are clearer as normal services. A full LangGraph rewrite would make trivial CRUD harder to test and maintain without improving the user-facing capability.

Alternative considered: rewrite all backend behavior as graphs. Rejected because it increases migration risk and makes the first phase slower without materially improving future extensibility.

### Treat Docling output as canonical source text

Decision: Docling conversion output becomes the canonical Markdown/text body for document sources. Existing PDF/DOCX/TXT/HTML parser classes are replaced or wrapped by a Docling parser service, with plain text fallback for formats Docling cannot handle cleanly.

Rationale: the product needs multiple document-like formats and future PPT/ePub/image-aware extraction. A single conversion boundary keeps chunking, citations, RAG, and Studio generation consistent.

Alternative considered: keep current per-extension parser factory. Rejected because it duplicates parsing behavior and makes future format expansion fragmented.

### Use SeekDB embedded first

Decision: use `pyseekdb` embedded collections as the default local store for sources, chunks, artifacts, jobs, and vector search. Server/MySQL mode remains a future configuration option.

Rationale: NotebookLM-Lite is currently a local app, and the user selected embedded mode. The SeekDB repository is already cloned locally for reference, and the packaged SDK is available on PyPI. Embedded mode avoids requiring a separate database service for first-phase development.

Alternative considered: service-mode SeekDB via MySQL-compatible SQL. Deferred because it adds setup complexity before multi-user deployment is needed.

### Standardize model calls through LiteLLM

Decision: implement a `LiteLLMProvider` for text completion, structured completion, and embeddings. UI configuration stores provider-friendly fields, but backend execution uses LiteLLM model strings, optional base URLs, and optional provider-specific passthrough parameters such as `thinking`.

Rationale: the frontend needs OpenAI-compatible, Anthropic, and Gemini choices. LiteLLM removes custom provider branching and gives one place for retries, timeout, token limits, structured output, and future model support.

Alternative considered: extend the current OpenAI/Google provider classes and add Anthropic. Rejected because provider-specific branching would keep growing and duplicate structured-output handling.

### Route audio through the same model configuration boundary

Decision: implement an `AudioSpeechProvider` that reads `api.models.audio_model` from config and synthesizes MP3 through an OpenAI-compatible `/audio/speech` endpoint. The implementation should prefer LiteLLM/OpenAI-compatible speech routing when it supports the required endpoint and streaming behavior; otherwise, use a thin direct streaming HTTP fallback behind the same provider interface and configuration fields.

Rationale: SiliconFlow exposes a simple streaming speech endpoint using `model`, `input`, `voice`, `response_format`, and `stream`. The product should not create a separate ad-hoc user configuration path for this; it should treat audio as a model profile next to text, embedding, image, and edit models. Streaming writes must be supported because generated podcast audio can be large.

Alternative considered: keep audio out of first-phase validation. Rejected because `config.yaml` now includes `audio_model`, so full podcast generation can be tested end-to-end.

### Make Studio artifacts first-class records

Decision: every generated output is an artifact with type, title, source IDs, model metadata, structured payload, preview text, downloadable files, created time, and job ID.

Rationale: the right panel needs to list generated podcasts, PPTs, mind maps, FAQs, and other files uniformly. It also lets chat answers and future research reports be saved back as sources.

Alternative considered: keep generated outputs only in frontend React state. Rejected because results would vanish on refresh and could not be downloaded, previewed, or reused as sources.

### Generate long podcast scripts through expansion, not one giant prompt

Decision: podcast script generation uses a graph with planning, batched dialogue generation, critique/coverage checks, and iterative expansion until the requested duration band is reached or bounded retries are exhausted.

Rationale: asking a model for a 30-minute script in one call is brittle and often returns a short sample. Structured batches with duration estimation and coverage tracking make the output more controllable and testable.

Alternative considered: only increase `max_tokens` and prompt wording. Rejected because current behavior already shows prompts alone are not enough.

## Risks / Trade-offs

- Docling can be heavy to install and slow on large PDFs → keep upload size limits, run parsing in job workflows, and return progress/error states.
- `pyseekdb` embedded API may differ from local source examples → pin a compatible SDK version, wrap it behind a repository interface, and keep a small fake store for tests.
- Structured output may fail on weaker models → validate with Pydantic, retry once with schema repair instructions, and return a job error instead of saving invalid artifacts.
- Long podcast scripts can be expensive and slow, especially with thinking enabled → cap duration at 30 minutes, cap iterations, expose estimated duration, and let users disable model thinking for long generation runs.
- Audio synthesis can be slow or stream large responses → stream chunks to a file, expose job progress, keep transcript artifacts even when audio fails, and use the configured `audio_model` for full-flow smoke tests.
- Partial LangGraph introduces two execution styles → keep the boundary explicit: graphs produce jobs/artifacts; services manage resources and HTTP contracts.
- AIPPT integration can pull in a large parallel app → integrate through an adapter boundary and postpone image-model execution from first-phase acceptance.

## Migration Plan

1. Add tests and dependency/config scaffolding while preserving existing routes.
2. Add the new source, model runtime, store, artifact, job, and workflow services.
3. Add new `/api/sources`, `/api/chat`, `/api/artifacts`, `/api/jobs`, and `/api/research/jobs` routes.
4. Update the frontend to use the new contracts while leaving old routes untouched until the new paths pass smoke tests.
5. Remove or deprecate old document cache, Chroma store, provider-specific LLM classes, and old podcast route shapes once the new end-to-end flow works.
6. Rollback by retaining old code until the final cleanup step; if the new store fails, disable new routes and keep the prior app runnable.

## Open Questions

- Whether the final implementation should keep legacy route aliases for one release or remove them immediately.
- Whether source-level selection state should persist globally per notebook or remain frontend-local in the first phase.
- Whether AIPPT should be copied into this repository or imported as a local/package dependency after the text-first phase is stable.
