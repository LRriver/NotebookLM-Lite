## ADDED Requirements

### Requirement: Slide decks are first-class artifacts
The system SHALL persist generated slide decks as first-class NotebookLM-Lite Studio artifacts.

#### Scenario: Generated deck appears in artifacts
- **WHEN** a slide deck project is created or generated
- **THEN** the Studio artifact list SHALL include a Slide Deck artifact with title, status, source IDs, created timestamp, preview metadata, and open action

#### Scenario: Open existing deck
- **WHEN** a user clicks an existing Slide Deck artifact card
- **THEN** the frontend SHALL open the persisted slide deck workspace for that deck

### Requirement: Slide deck state is backend-persistent
The system SHALL persist deck state in NotebookLM-Lite backend storage rather than relying on browser IndexedDB for critical data.

#### Scenario: Persist deck draft
- **WHEN** a deck has only an outline or prompt plan
- **THEN** the backend SHALL persist that draft state so it can be resumed later

#### Scenario: Persist generated slides
- **WHEN** slide images are generated
- **THEN** the backend SHALL persist slide records and image asset references for later preview/export

#### Scenario: No critical IndexedDB dependency
- **WHEN** the browser local storage or IndexedDB is cleared
- **THEN** previously persisted deck projects SHALL still be recoverable from the backend

### Requirement: Slide deck records preserve source lineage
The system SHALL keep enough lineage to explain which notebook sources and generation settings produced a deck.

#### Scenario: View deck lineage
- **WHEN** a user opens deck details
- **THEN** the backend SHALL expose linked source IDs, source titles/filenames, model role metadata, generation config snapshot, and timestamps

#### Scenario: Frozen source context
- **WHEN** source documents are edited or removed after a deck is generated
- **THEN** the deck SHALL retain the frozen source-context snapshot used during generation while still showing original source lineage where available

### Requirement: Slide assets are durable files with metadata
The system SHALL store generated and edited slide images as durable local files referenced by metadata.

#### Scenario: Store generated image asset
- **WHEN** a slide image is generated
- **THEN** the backend SHALL store image bytes under an ignored output/data path and persist asset metadata including path, MIME type, size, checksum, and stage

#### Scenario: Do not stage generated files
- **WHEN** implementation is ready for commit
- **THEN** generated image/PPTX output directories SHALL remain ignored and unstaged

### Requirement: Integration source is new_pro/AIPPT only
The system SHALL treat `/Users/lzj/proj/notebook/new_pro/AIPPT` as the AIPPT integration source for this change.

#### Scenario: Port AIPPT behavior
- **WHEN** implementation ports AIPPT behavior
- **THEN** it SHALL reference `/Users/lzj/proj/notebook/new_pro/AIPPT` files and tests as the source implementation

#### Scenario: Avoid unverified branch migration
- **WHEN** implementation considers code from `/Users/lzj/proj/notebook/OpenNotebookLM-AIPPT`
- **THEN** it SHALL first document the reason, inspect and verify that implementation separately, and avoid treating it as the default migration source
