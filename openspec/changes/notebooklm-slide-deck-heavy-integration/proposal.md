## Why

NotebookLM-Lite already has a NotebookLM-style source/chat/Studio workbench and a placeholder boundary for slide decks, but PPT generation is not yet a native product capability. The user-selected direction is heavy integration: the slide deck workflow from `/Users/lzj/proj/notebook/new_pro/AIPPT` should become a first-class NotebookLM-Lite Studio artifact, powered by selected notebook sources, persisted in the shared backend store, configured by the shared model runtime, and edited in a dedicated slide deck workspace.

This change replaces the current PPT placeholder with a real Phase 1 slide deck feature: source-grounded outline generation, user confirmation, prompt plan generation, second confirmation, real slide image generation, single-slide regeneration/editing, browser preview, and PPTX export.

## What Changes

- Add a native Slide Deck Studio artifact type backed by NotebookLM-Lite source IDs, jobs, artifacts, files, and source lineage.
- Integrate the validated workflow from `/Users/lzj/proj/notebook/new_pro/AIPPT` as the implementation source for outline planning, prompt planning, image generation, single-slide editing, and PPTX export.
- Do not migrate from `/Users/lzj/proj/notebook/OpenNotebookLM-AIPPT` unless a specific implementation is separately inspected and verified; it is not the source of truth for this integration.
- Remove AIPPT's independent API/config boundary from the integrated path. NotebookLM-Lite owns routes, jobs, persistence, runtime configuration, and UI state.
- Route all text, image, and edit model execution through NotebookLM-Lite model profiles in `config.yaml` / runtime config, using LiteLLM for text and a shared image/edit adapter under the same model-profile boundary.
- Allow implementers to read `/Users/lzj/proj/notebook/new_pro/AIPPT/config.yaml` for local testing credentials, but never commit that file or leak keys. If config schema changes are needed, update NotebookLM-Lite `config_example.yaml`.
- Add a dedicated full-screen slide deck editor entered from the right Studio panel or generated deck card, with a clear return path to the main NotebookLM-Lite workbench.
- Preserve the warm NotebookLM-Lite visual system while reusing AIPPT's proven interaction structure: left slide list, center large preview, right outline/design/edit/export panel.
- Preserve two human confirmation gates: sources to deck outline, then deck outline to slide prompt plan.
- Persist deck draft state, outline, prompt plan, slide images, edit history, export files, job progress, errors, and retry metadata in the NotebookLM-Lite backend store.
- Support Phase 1 real image generation and PPTX export. Product wording may say "PPTX export", but implementation/docs must not claim fully editable native PowerPoint shapes.
- Support Phase 1 single-slide regenerate and single-slide edit, including edit history and restore behavior.
- Add real end-to-end validation tasks using current local NotebookLM-Lite model config plus PPT model parameters from `/Users/lzj/proj/notebook/new_pro/AIPPT/config.yaml`, including browser mouse-click testing of the new frontend buttons.

## Capabilities

### New Capabilities

- `slide-deck-workflow`: Covers source-grounded deck creation, outline generation, prompt plan generation, human confirmation gates, jobs, retries, and model-runtime use.
- `slide-deck-artifacts`: Covers persistent deck/project records, slide records, assets, source lineage, job state, artifact list/detail, and recoverability.
- `slide-deck-editor`: Covers the dedicated slide deck workspace UI, slide preview/list, outline/prompt editing, single-slide regeneration/editing, return navigation, and visual integration.
- `slide-deck-export`: Covers PPTX export, download metadata, export jobs, file lifecycle, and honest product wording.
- `slide-deck-validation`: Covers unit/integration/browser/manual-real-model validation, including real generation with local configured models and mouse-click frontend smoke tests.

### Modified Capabilities

- `studio-artifacts`: The existing PPT placeholder becomes a real slide deck artifact entry point and generated artifact card.
- `model-runtime`: The existing model profile system expands to cover slide deck text planning, image generation, and image editing under NotebookLM-Lite configuration.
- `frontend-workbench`: The right Studio panel opens a dedicated slide deck workspace instead of treating PPT as a disabled placeholder.

## Impact

- Backend: new slide deck domain models, repository methods, services/workflows, routes, job handling, asset/file storage, model adapter integration, and export service integration.
- Frontend: new slide deck workspace route/state, Studio card behavior, outline and prompt plan confirmation UI, slide list/preview/editor panels, regenerate/edit/export actions, and browser E2E tests.
- Dependencies: likely retain `python-pptx`; reuse compatible logic from `new_pro/AIPPT`; add no second application server or standalone AIPPT API.
- Configuration: NotebookLM-Lite `api.models.text_model`, `image_model`, and `edit_model` remain the source of truth. AIPPT config values may be copied into local NotebookLM-Lite `config.yaml` for testing only.
- Data/storage: generated images, edited images, PPTX files, and deck manifests are stored under ignored output/data paths and referenced by persisted artifact records.
- Documentation: README and config example must describe the integrated slide deck workflow and clarify that PPTX export is image-based in Phase 1 unless native editable reconstruction is later implemented.

## Out of Scope

- Native editable PowerPoint shape reconstruction.
- Video Overview generation.
- Infographic image generation changes unrelated to slide decks.
- Maintaining AIPPT as an independent embedded app with its own API, config page, IndexedDB project store, or upload silo.
- Using `/Users/lzj/proj/notebook/OpenNotebookLM-AIPPT` as an implementation source without separate verification.
