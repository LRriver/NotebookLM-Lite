## ADDED Requirements

### Requirement: Slide decks export to PPTX
The system SHALL export generated slide decks to downloadable PPTX files.

#### Scenario: Export generated deck
- **WHEN** a deck has generated slide images and the user requests PPTX export
- **THEN** the backend SHALL create an export job and produce a `.pptx` file containing the deck slides

#### Scenario: Download exported PPTX
- **WHEN** a PPTX export job succeeds
- **THEN** the frontend SHALL show a download action and the backend SHALL return the exported file with an appropriate PPTX content type

### Requirement: PPTX export uses generated slide visuals in Phase 1
The system SHALL use image-based PPTX export in Phase 1 unless a later change adds native editable shape reconstruction.

#### Scenario: Image-based PPTX
- **WHEN** the backend exports a Phase 1 deck
- **THEN** each slide SHALL contain the generated slide visual placed as the slide content at the correct aspect ratio

#### Scenario: Honest wording
- **WHEN** the UI or README describes the feature
- **THEN** it MAY say "PPTX export" but SHALL NOT claim fully editable native PowerPoint shapes

### Requirement: Export jobs are persistent
The system SHALL persist export status and file metadata.

#### Scenario: Persist export metadata
- **WHEN** a PPTX export completes
- **THEN** the backend SHALL save export format, filename, file path/reference, slide count, status, and timestamp

#### Scenario: Export failure
- **WHEN** PPTX export fails
- **THEN** the backend SHALL mark the export job failed and expose a clear error without corrupting existing deck state

### Requirement: Export respects slide aspect ratio
The system SHALL create PPTX files with dimensions matching the deck's configured aspect ratio.

#### Scenario: 16:9 deck
- **WHEN** a 16:9 deck is exported
- **THEN** the PPTX slide dimensions SHALL match a 16:9 layout

#### Scenario: 4:3 deck
- **WHEN** a 4:3 deck is exported
- **THEN** the PPTX slide dimensions SHALL match a 4:3 layout
