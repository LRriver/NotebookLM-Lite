## ADDED Requirements

### Requirement: Slide deck implementation has automated backend coverage
The implementation SHALL include backend automated tests for slide deck workflow, providers, persistence, and export.

#### Scenario: Backend tests pass
- **WHEN** backend validation is run
- **THEN** tests SHALL cover create deck, outline generation, prompt-plan generation, confirmation gates, image generation with mocked provider, single-slide regenerate/edit, export, and failure handling

### Requirement: Slide deck implementation has frontend coverage
The implementation SHALL include frontend automated tests for the dedicated workspace and Studio entry points.

#### Scenario: Frontend tests pass
- **WHEN** frontend validation is run
- **THEN** tests SHALL cover opening from Studio, returning to notebook, outline confirmation, prompt-plan confirmation, slide list/preview, edit/regenerate controls, export controls, and error rendering

### Requirement: Browser validation uses mouse-click flows
The implementation SHALL verify the integrated frontend through real browser interactions rather than only API tests.

#### Scenario: Click through complete deck flow
- **WHEN** the developer performs browser smoke validation
- **THEN** they SHALL use mouse clicks to select sources, click the Slide Deck/PPT Studio button, generate outline, confirm outline, generate prompt plan, confirm prompt plan, generate slides, select slides, regenerate or edit one slide, export PPTX, and download it

### Requirement: Real model smoke test is required
The implementation SHALL include at least one real model smoke test for slide deck generation.

#### Scenario: Generate real small deck
- **WHEN** final validation is performed
- **THEN** the developer SHALL use local NotebookLM-Lite model configuration plus PPT model parameters from `/Users/lzj/proj/notebook/new_pro/AIPPT/config.yaml` to generate a small real slide deck with actual slide images

#### Scenario: Validate exported PPTX
- **WHEN** the real small deck is exported
- **THEN** the developer SHALL verify the PPTX file exists and contains the expected number of slides

### Requirement: Validation reports model/provider roles explicitly
The final implementation report SHALL distinguish real provider calls from mocks.

#### Scenario: Report provider mix
- **WHEN** implementation is completed
- **THEN** the final report SHALL state which text, image, and edit provider roles used real configured models, which tests used mocks, and any skipped or failed validation

### Requirement: Secrets are protected during validation
Validation SHALL NOT expose local model credentials or commit local config files.

#### Scenario: No leaked keys
- **WHEN** validation logs, screenshots, commits, and final reports are prepared
- **THEN** API keys from NotebookLM-Lite `config.yaml` or `/Users/lzj/proj/notebook/new_pro/AIPPT/config.yaml` SHALL be omitted or redacted
