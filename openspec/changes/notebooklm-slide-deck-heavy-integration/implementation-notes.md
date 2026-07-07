## Baseline And Provenance Notes

### 2026-07-07 Module 1: Baseline And Provenance

- Current branch before application code: `notebooklm-slide-deck-heavy-integration`.
- Current HEAD before application code: `0a9f3a3 docs(openspec): propose slide deck heavy integration`.
- Working tree before application code: clean except for this OpenSpec implementation-notes/tasks update.
- OpenSpec CLI status: `openspec` is not available in the current shell PATH, so validation must be rerun when the CLI is available.

### Integration Source

The integration source for this change is `/Users/lzj/proj/notebook/new_pro/AIPPT`.

Inspected donor files:

- `src/models.py`: deck outline, slide outline, slide prompt plan, prompt data, generation result models.
- `src/prompt_generator.py`: source-to-outline and outline-to-prompt-plan generation, validation, and retry behavior.
- `src/model_router.py`: existing AIPPT prompt/image/edit routing behavior to be replaced by NotebookLM-Lite runtime boundaries.
- `api/routes/generate.py`: outline, prompt plan, and slide image generation route behavior.
- `api/routes/edit.py`: single-slide image edit behavior.
- `api/routes/export.py`: image-based PDF/PPTX export behavior.
- `web/src/components/DesignWorkflowPanel.tsx`: two-stage outline and prompt-plan confirmation UI behavior.
- `web/src/components/SlideList.tsx`, `EditPanel.tsx`, `ExportButton.tsx`: slide navigation, edit, and export interaction patterns.
- `web/src/contexts/AppStateContext.tsx`, `web/src/services/projectStore.ts`: state concepts to reference, but not persistence boundaries for the integrated feature.

Inspected donor tests to preserve expected behavior during porting:

- `tests/test_prompt_planning.py`: outline and prompt-plan planning expectations.
- `tests/test_generate_route_helpers.py`: confirmed prompt handling and route helper behavior.
- `tests/test_model_router.py`, `tests/test_model_profiles.py`, `tests/test_profile_resolver.py`: model routing/profile expectations to replace with NotebookLM-Lite runtime equivalents.
- `tests/test_edit_route.py`: single-slide image edit route behavior.
- `tests/test_export_pptx_ratio.py`: PPTX export aspect-ratio behavior.
- `tests/test_image_result_normalizer.py`: image response normalization expectations for raw multimodal endpoints.
- `web/src/components/__tests__/DesignWorkflowPanel.test.tsx`: two-stage workflow UI behavior.
- `web/src/components/__tests__/SlideGeneration.property.test.tsx`, `EditHistory.property.test.tsx`, `EditSession.property.test.tsx`, `ExportConsistency.property.test.tsx`: slide generation, edit history, edit state, and export consistency behavior.

`/Users/lzj/proj/notebook/OpenNotebookLM-AIPPT` is not an implementation source for this change. No code should be migrated from it unless separately inspected, verified, and explicitly documented.

### Model Configuration Boundary

NotebookLM-Lite already exposes the required model roles through `api.models`:

- `backend/config.py` defines a shared `ModelProfile` with `model`, `base_url`, `api_key`, `adapter`, `thinking`, `voice`, `response_format`, and `stream` fields.
- `backend/config.py` defines `ModelProfiles.text_model`, `embedding_model`, `rerank_model`, `audio_model`, `image_model`, and `edit_model`.
- `backend/dependencies.py` currently wires text and embedding roles through `LiteLLMProvider`; image/edit provider wiring is intentionally still future work covered by tasks 3.4 and 3.5.
- `backend/infrastructure/llm_providers/litellm_provider.py` supports text completion, structured output, embeddings, OpenAI-compatible base URL forwarding, and provider-prefix model mapping.
- `config_example.yaml` already documents `image_model` and `edit_model` fields with `model`, `base_url`, `api_key`, and `adapter`.

Local role presence without exposing secret values:

- `text_model`: field exists and is configured locally; intended for outline and prompt-plan structured output.
- `image_model`: field exists and is configured locally; intended for slide image generation after tasks 3.4/3.5 add the provider path.
- `edit_model`: field exists and is configured locally; intended for single-slide image editing after tasks 3.4/3.5 add the provider path.

The local AIPPT config at `/Users/lzj/proj/notebook/new_pro/AIPPT/config.yaml` also contains `text_model`, `image_model`, and `edit_model` roles. These values may be used only as local test parameters. Secrets must not be printed, committed, copied into docs, or exposed in screenshots.

Integrated implementation must not keep AIPPT's standalone config loader, standalone API key form, or independent runtime boundary.

### 2026-07-07 Module 8: Validation Notes

Validation commands:

- `openspec validate notebooklm-slide-deck-heavy-integration --strict`
  - Result: unavailable in this shell, `zsh: command not found: openspec`.
- `/Users/lzj/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m compileall -q backend && git diff --check`
  - Result: passed.
- `/Users/lzj/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest tests/test_slide_deck_domain_repository.py tests/test_slide_deck_export.py tests/test_slide_deck_model_runtime.py tests/test_slide_deck_workflow_api.py tests/test_ppt_adapter.py tests/test_litellm_runtime.py tests/test_runtime_config_api.py tests/test_config_settings.py -q`
  - Result: 46 passed, 4 Pydantic deprecation warnings.
- `cd frontend && npm test -- --run src/components/SlideDeckWorkspace.test.tsx`
  - Result: 12 passed.
- `cd frontend && npm test -- --run`
  - Result: 20 passed.
- `cd frontend && npm run build`
  - Result: passed.

Local services:

- Backend: `/Users/lzj/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m backend.main`, serving `http://127.0.0.1:8000`.
- Frontend: Vite dev server on `http://127.0.0.1:5173`.

Real browser smoke:

- Opened the NotebookLM-Lite frontend in the in-app browser.
- Selected source `Slide Deck Smoke Source 2` in the left source panel.
- Clicked the Studio `PPT` card and verified it opened a new `Slide Deck` workspace.
- Returned from a recovered old slide deck workspace to the main three-column workbench.
- Opened the generated-content card `Slide Deck Real Smoke SiliconFlow 1p`.
- Clicked `生成大纲`, confirmed the real outline output, clicked `确认大纲`.
- Clicked `生成提示计划`, confirmed the real prompt-plan output, clicked `确认提示计划`.
- Clicked `生成幻灯片`; the workspace displayed `slide_generation running`, then refreshed to a rendered `img.slide-image-preview`.
- Clicked `重新生成` for the current slide; the slide returned to `succeeded` with an image asset.
- Clicked `导出 PPTX`; the workspace displayed `export succeeded` and `下载 PPTX`.

Real model/provider smoke:

- Smoke deck id: `deck_d277e2efbf4f47229c32b170df82d000`.
- Source id: `src_fbbb851112be48fbb36d4f39a527696e`.
- Deck size: 1 slide.
- Text planning model role: local NotebookLM-Lite `config.yaml` text model via LiteLLM. The initially configured AIPPT text endpoint returned quota exhausted; the smoke used a local ignored fallback model profile configured through `config.yaml`.
- Image generation model role: local NotebookLM-Lite `config.yaml` image model using SiliconFlow `/images/generations` through the `siliconflow_image` adapter. This generated a real slide image URL that was downloaded and stored as a slide asset.
- After adding URL safety checks, the image provider was smoke-tested again with `Qwen/Qwen-Image` and `siliconflow_image`; it returned a non-empty PNG payload.
- PPTX verification path: `output/validation/slide-deck-real-smoke.pptx`.
- PPTX inspection: `python-pptx` opened the file and reported 1 slide.

Issues found and fixed during validation:

- LiteLLM `thinking: disabled` was forwarded to providers that do not support the parameter. Fixed by omitting disabled thinking while preserving enabled thinking.
- Raw image provider only supported chat-completions style image gateways. Added `/images/generations` adapters and separated OpenAI-style `size` from SiliconFlow-style `image_size`.
- Generation-only image adapters are rejected for edit operations to avoid silently posting an edit request to the wrong API shape.
- Generated image URL downloads now reject local/private hosts, redirects, non-raster content, and oversized payloads.
- Switching from an old recovered generating deck to another deck left stale busy/job state in the frontend and disabled the new deck workflow buttons. Fixed with per-load sequence guards and state reset on deck changes.
- Direct workspace mutations now use the same per-load sequence guard so stale confirm/regenerate/edit responses cannot overwrite a newly opened deck.
- `pyseekdb.Client(path=file.db)` can treat the SQLite file path as a directory, causing SQLite to fail opening the database. Fixed by using a sibling pyseekdb embedded directory and keeping the SQLite file path separate.

Known limitation from this validation:

- The local AIPPT-derived `edit_model` endpoint returned server errors during earlier real generation attempts. Single-slide regenerate was real-tested successfully. The single-slide edit API/UI path is implemented and covered by mocked tests, but this environment did not provide a working real edit provider.
