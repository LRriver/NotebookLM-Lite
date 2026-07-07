## 1. Baseline And Provenance

- [x] 1.1 Confirm the current working tree state with `git status --short --branch` and record any unrelated user changes before editing code.
- [x] 1.2 Inspect `/Users/lzj/proj/notebook/new_pro/AIPPT` and document the exact files reused or ported; do not use `/Users/lzj/proj/notebook/OpenNotebookLM-AIPPT` as an implementation source unless separately verified.
- [x] 1.3 Read NotebookLM-Lite current model config/runtime code and confirm text, image, and edit model profile fields are sufficient for slide deck generation.
- [x] 1.4 Inspect local `config.yaml` only for runtime testing; do not print, commit, or copy secrets. If PPT model values from `/Users/lzj/proj/notebook/new_pro/AIPPT/config.yaml` are needed, copy them into local NotebookLM-Lite `config.yaml` manually or through ignored local config only.

## 2. Backend Domain, Persistence, And Jobs

- [x] 2.1 Add Pydantic/domain models for slide deck projects, outlines, prompt plans, slides, slide assets, edit history, export records, and stage/job statuses.
- [x] 2.2 Extend the repository abstraction and SeekDB-backed implementation to persist and retrieve slide deck records, slide assets, edit history, exports, and associated jobs.
- [x] 2.3 Store generated image/PPTX files under ignored output/data paths and persist only metadata, checksums, paths, and download references.
- [x] 2.4 Add fake repository/test fixtures for slide deck state so backend tests do not require real model calls.
- [x] 2.5 Add tests for create/get/list deck state, backend restart persistence, source lineage, file metadata, and job status transitions.

## 3. Model Runtime Integration

- [x] 3.1 Port or adapt `new_pro/AIPPT` outline and prompt-plan schemas into NotebookLM-Lite backend models.
- [x] 3.2 Generate deck outlines through NotebookLM-Lite `LiteLLMProvider.generate_structured(...)`, using selected source context and Pydantic validation.
- [x] 3.3 Generate slide prompt plans through NotebookLM-Lite `LiteLLMProvider.generate_structured(...)` from confirmed outlines.
- [x] 3.4 Add NotebookLM-Lite image generation provider behavior for `api.models.image_model`, using LiteLLM where supported or a shared raw OpenAI-compatible multimodal adapter behind the same model-profile boundary.
- [x] 3.5 Add NotebookLM-Lite image edit provider behavior for `api.models.edit_model`, using LiteLLM where supported or the shared raw multimodal adapter behind the same model-profile boundary.
- [x] 3.6 Remove integrated-path dependency on AIPPT `APIConfig`, `config.py`, `model_profiles.py`, and standalone API config forms.
- [x] 3.7 Add tests for text profile use, structured validation failure/retry, image provider payloads, edit provider payloads, config redaction, and missing-model error messages.

## 4. Slide Deck Workflow And API

- [ ] 4.1 Implement `SlideDeckService` for deck creation from selected NotebookLM-Lite source IDs and frozen source-context snapshots.
- [ ] 4.2 Implement outline generation job and PATCH confirmation/edit endpoint.
- [ ] 4.3 Implement prompt-plan generation job and PATCH confirmation/edit endpoint.
- [ ] 4.4 Implement slide image generation job with per-slide status, retry, partial failure recording, and resumable job state.
- [ ] 4.5 Implement single-slide regenerate using the stored prompt plan and current generation config.
- [ ] 4.6 Implement single-slide edit using current slide image plus user instruction, with edit history and restore metadata.
- [ ] 4.7 Implement deck detail/list APIs and artifact integration so generated decks appear in Studio artifact lists.
- [ ] 4.8 Add integration tests for the full mocked workflow: create deck, generate outline, confirm outline, generate prompt plan, confirm prompt plan, generate images, regenerate one slide, edit one slide, recover deck state.

## 5. PPTX Export

- [ ] 5.1 Port the image-based PPTX export helper from `/Users/lzj/proj/notebook/new_pro/AIPPT/api/routes/export.py` into a NotebookLM-Lite export service.
- [ ] 5.2 Implement `POST /api/slide-decks/{deck_id}/export/jobs` and `GET /api/slide-decks/{deck_id}/download?format=pptx`.
- [ ] 5.3 Persist export records with status, filename, format, file path, generated timestamp, slide count, and error state.
- [ ] 5.4 Add tests that export a PPTX from generated slide images and validate the file exists and has the expected slide count.
- [ ] 5.5 Update user-facing wording to say "PPTX export" without claiming native editable PowerPoint shapes.

## 6. Frontend Slide Deck Workspace

- [ ] 6.1 Add a dedicated slide deck workspace route or app mode opened from the Studio PPT card and existing Slide Deck artifact cards.
- [ ] 6.2 Add a clear "Back to notebook" action that returns to the main three-column workbench without losing deck state.
- [ ] 6.3 Reuse AIPPT's interaction structure, adapted to NotebookLM-Lite style: left slide/page list, center preview, right workflow/edit/export panel.
- [ ] 6.4 Implement source-to-outline UI with loading/error states, editable outline, and explicit confirmation.
- [ ] 6.5 Implement outline-to-prompt-plan UI with loading/error states, editable per-slide design/prompt content, and explicit confirmation.
- [ ] 6.6 Implement slide generation UI with per-page progress, image preview, partial failure display, and deck recovery after refresh.
- [ ] 6.7 Implement single-slide regenerate, single-slide edit, edit history display, and current-slide selection.
- [ ] 6.8 Implement PPTX export and download controls.
- [ ] 6.9 Ensure the UI uses NotebookLM-Lite model settings and does not expose AIPPT's standalone API config form.
- [ ] 6.10 Add frontend unit tests for navigation, confirmations, slide list/preview, edit/regenerate controls, export controls, and error states.

## 7. Documentation And Config

- [ ] 7.1 Update `config_example.yaml` only if needed to document image/edit model fields for slide deck generation.
- [ ] 7.2 Update README and README_zn to describe native Slide Deck generation, two confirmation steps, single-slide edit/regenerate, and PPTX export.
- [ ] 7.3 Document that local testing can use PPT model parameters from `/Users/lzj/proj/notebook/new_pro/AIPPT/config.yaml`, but those credentials must remain local and ignored.
- [ ] 7.4 Document that `/Users/lzj/proj/notebook/OpenNotebookLM-AIPPT` is not the integration source for this change.
- [ ] 7.5 Keep product wording honest: Phase 1 exports PPTX with generated slide visuals and does not promise native editable PowerPoint elements.

## 8. Required Validation

- [ ] 8.0 Run `openspec validate notebooklm-slide-deck-heavy-integration --strict` if the OpenSpec CLI is available in the implementation environment, and fix any spec/task formatting errors before application code work proceeds.
- [ ] 8.1 Run `python -m compileall -q backend` and backend tests for slide deck services, providers, routes, repository, and export.
- [ ] 8.2 Run frontend unit tests and `npm run build` in `frontend/`.
- [ ] 8.3 Start the backend and frontend locally.
- [ ] 8.4 Use a real browser and mouse clicks to test the integrated frontend flow: select sources, click the PPT/Slide Deck Studio button, open the slide deck workspace, generate outline, confirm outline, generate prompt plan, confirm prompt plan, generate slides, select slides, run single-slide regenerate or edit, export PPTX, and download it.
- [ ] 8.5 Run at least one real model smoke test using local NotebookLM-Lite `config.yaml` plus PPT-related model parameters from `/Users/lzj/proj/notebook/new_pro/AIPPT/config.yaml`. The test SHALL generate a small deck with real slide images, not mocked images.
- [ ] 8.6 Verify the exported PPTX exists, can be opened or inspected, and contains the expected number of slides.
- [ ] 8.7 Verify no local secrets, generated outputs, data directories, screenshots with keys, or AIPPT local `config.yaml` files are staged.
- [ ] 8.8 Record validation commands, browser actions, model/provider roles used, generated deck size, PPTX path, and any failures or skipped items in the final implementation report.
