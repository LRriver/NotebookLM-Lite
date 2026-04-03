## ADDED Requirements

### Requirement: Studio supports text-model-generated artifacts
The system SHALL generate first-phase Studio artifacts that can be produced by text models.

#### Scenario: Generate text artifact
- **WHEN** a user selects sources and requests a mind map / 思维图谱, FAQ, flashcards/quiz, report/study guide, or data table
- **THEN** the backend SHALL create a generation job, call the text model with a Pydantic schema for that artifact type, honor the configured thinking toggle, and save a validated artifact

#### Scenario: Unsupported visual artifact
- **WHEN** a user requests video overview, infographic, or full image-rendered PPT before the required model integration is available
- **THEN** the frontend SHALL show the capability as planned or disabled rather than invoking a broken backend path

### Requirement: Artifacts are durable and listable
The system SHALL persist generated artifacts so they survive page refreshes and backend restarts.

#### Scenario: List generated artifacts
- **WHEN** the user opens the Studio panel after generating artifacts
- **THEN** the backend SHALL return persisted artifacts with type, title, source IDs, created timestamp, status, preview text, and download availability

### Requirement: Artifact generation uses job status
The system SHALL represent long-running artifact generation as jobs with inspectable progress.

#### Scenario: Job progress
- **WHEN** a Studio generation request is accepted
- **THEN** the backend SHALL return a job ID and expose status values such as queued, running, succeeded, and failed

### Requirement: Artifacts are previewable and downloadable
The system SHALL provide artifact-specific preview and download behavior.

#### Scenario: Preview mind map
- **WHEN** a user expands a mind map / 思维图谱 artifact
- **THEN** the frontend SHALL show its structured nodes and edges or a readable textual fallback

#### Scenario: Download artifact
- **WHEN** a user downloads a generated text artifact
- **THEN** the backend SHALL provide a Markdown or JSON file appropriate to the artifact type

### Requirement: Deep Research has a placeholder contract
The system SHALL expose a Deep Research job contract that can later be implemented as a full research workflow.

#### Scenario: Create research placeholder
- **WHEN** a user submits a Deep Research request in the first phase
- **THEN** the backend SHALL create a job record with a clear not-implemented or placeholder status and the API shape SHALL allow a future research report to be saved as a source
