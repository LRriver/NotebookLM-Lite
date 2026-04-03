## ADDED Requirements

### Requirement: Multi-format sources are ingested through Docling
The system SHALL accept document-like source inputs and convert them into canonical Markdown/text using Docling before chunking or retrieval.

#### Scenario: Upload supported document
- **WHEN** a user uploads a supported file such as PDF, DOCX, PPTX, Markdown, TXT, HTML, or CSV
- **THEN** the backend SHALL create a source record containing original filename, detected type, canonical text, metadata, processing status, and created timestamp

#### Scenario: Parse failure is reported
- **WHEN** Docling or fallback parsing fails for an uploaded file
- **THEN** the backend SHALL mark the source as failed and return an actionable error without creating searchable chunks

### Requirement: Sources are chunked with traceable metadata
The system SHALL split canonical source text into chunks suitable for retrieval and preserve metadata needed for citations.

#### Scenario: Chunk creation
- **WHEN** a source is successfully parsed
- **THEN** the backend SHALL create ordered chunks with source ID, chunk index, text, character offsets when available, and parser metadata such as page or section when available

#### Scenario: Chunk configuration
- **WHEN** chunk size or overlap is configured in application settings
- **THEN** the ingestion pipeline SHALL use those values consistently for all newly processed sources

### Requirement: SeekDB persists sources, chunks, artifacts, and jobs
The system SHALL use SeekDB embedded mode through `pyseekdb` as the default local persistence and retrieval backend.

#### Scenario: Backend restart
- **WHEN** the backend restarts after sources have been processed
- **THEN** listing sources and querying previously ingested chunks SHALL still work without re-uploading files

#### Scenario: Source deletion
- **WHEN** a user deletes a source
- **THEN** the backend SHALL remove its source record and associated chunks from SeekDB and exclude it from future retrieval

### Requirement: Generated text can be saved as a source
The system SHALL allow selected generated outputs to become new sources for later RAG or Studio generation.

#### Scenario: Save generated report as source
- **WHEN** a user saves a chat answer, report, or future Deep Research result as a source
- **THEN** the backend SHALL create a normal source record, chunk it, and make it selectable for future questions and artifact generation
