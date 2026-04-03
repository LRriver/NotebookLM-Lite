## ADDED Requirements

### Requirement: Chat queries are scoped to selected sources
The system SHALL answer RAG questions using only the source IDs selected by the user.

#### Scenario: Selected-source query
- **WHEN** a user asks a question with one or more selected source IDs
- **THEN** the backend SHALL retrieve chunks only from those sources and generate an answer from that scoped context

#### Scenario: No selected sources
- **WHEN** a user submits a RAG question without any selected source IDs
- **THEN** the backend SHALL reject the request with a clear message that at least one source is required

### Requirement: Answers include citations
The system SHALL return citations that connect answer content to retrieved source chunks.

#### Scenario: Answer with supporting chunks
- **WHEN** relevant chunks are retrieved for a chat query
- **THEN** the response SHALL include citation entries with source ID, source title or filename, chunk ID, score, and excerpt text

#### Scenario: No relevant chunks
- **WHEN** no chunks meet retrieval criteria for the selected sources
- **THEN** the response SHALL state that no relevant information was found and SHALL return an empty citations list

### Requirement: Conversation history is supported
The system SHALL accept recent chat history and use it to improve follow-up question interpretation without expanding retrieval outside selected sources.

#### Scenario: Follow-up question
- **WHEN** a user asks a follow-up question with prior turns
- **THEN** the backend SHALL use recent history to reformulate or contextualize the query while still retrieving only from selected sources

### Requirement: Chat outputs can become reusable sources
The system SHALL support saving selected chat outputs as source material.

#### Scenario: Save answer
- **WHEN** a user chooses to save a chat answer as a reference
- **THEN** the backend SHALL create a source from the answer text and make it available for source selection after ingestion completes
