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
