## ADDED Requirements

### Requirement: Slide decks are generated from selected NotebookLM-Lite sources
The system SHALL create slide decks from NotebookLM-Lite selected source IDs and a frozen source-context snapshot.

#### Scenario: Create deck from selected sources
- **WHEN** a user selects one or more sources and starts Slide Deck generation from Studio
- **THEN** the backend SHALL create a slide deck project linked to those source IDs and store the source context used for generation

#### Scenario: Reject empty source selection
- **WHEN** a user starts Slide Deck generation without selected sources
- **THEN** the frontend SHALL prevent the action or the backend SHALL reject it with a clear selected-source-required error

### Requirement: Slide deck workflow has two confirmation gates
The system SHALL require user confirmation after deck outline generation and after slide prompt plan generation.

#### Scenario: Confirm generated outline
- **WHEN** the model generates a deck outline
- **THEN** the frontend SHALL show the outline in editable form and SHALL NOT generate slide prompt plans until the user confirms or saves the outline

#### Scenario: Confirm generated prompt plan
- **WHEN** the model generates per-slide prompt plans
- **THEN** the frontend SHALL show the prompt plan in editable form and SHALL NOT generate slide images until the user confirms or saves the prompt plan

### Requirement: Outline and prompt plans use structured output
The system SHALL validate model-generated deck outlines and slide prompt plans with Pydantic models before saving successful workflow stages.

#### Scenario: Valid outline
- **WHEN** the text model returns JSON matching the deck outline schema
- **THEN** the backend SHALL save the typed outline and mark the outline job as succeeded

#### Scenario: Invalid prompt plan
- **WHEN** the text model returns missing, malformed, or schema-invalid prompt-plan output
- **THEN** the backend SHALL retry with repair instructions and SHALL fail the job if validation still fails

### Requirement: Slide image generation is a real Phase 1 workflow
The system SHALL generate real slide images from confirmed slide prompt plans using configured image model credentials.

#### Scenario: Generate slide images
- **WHEN** a user confirms the prompt plan and starts generation
- **THEN** the backend SHALL call the configured image model for each slide prompt, store generated image assets, and update per-slide progress

#### Scenario: Partial slide failure
- **WHEN** one slide image generation fails but other slides succeed
- **THEN** the backend SHALL persist successful slides, record the failed slide error, and allow retry or regeneration for the failed slide

### Requirement: Slide deck jobs are resumable and inspectable
The system SHALL represent slide deck stages as persistent jobs with progress, status, and error metadata.

#### Scenario: Poll job progress
- **WHEN** a slide deck job is queued, running, succeeded, or failed
- **THEN** the frontend SHALL be able to read job status and render progress without relying only on transient browser state

#### Scenario: Recover after browser refresh
- **WHEN** the browser refreshes after a deck reaches outline, prompt-plan, image-generation, or export stage
- **THEN** the frontend SHALL reload the deck state from the backend and continue from the persisted stage

### Requirement: Slide deck runtime uses NotebookLM-Lite model profiles
The system SHALL use NotebookLM-Lite model profile configuration for slide deck text planning, image generation, and image editing.

#### Scenario: Text planning uses LiteLLM
- **WHEN** the backend generates outlines or prompt plans
- **THEN** it SHALL use the NotebookLM-Lite text model provider and configured `api.models.text_model`

#### Scenario: Image generation uses shared model profiles
- **WHEN** the backend generates slide images
- **THEN** it SHALL use `api.models.image_model` from NotebookLM-Lite config rather than AIPPT's standalone config loader

#### Scenario: Image editing uses shared model profiles
- **WHEN** the backend edits a generated slide
- **THEN** it SHALL use `api.models.edit_model` from NotebookLM-Lite config rather than AIPPT's standalone config loader
