## ADDED Requirements

### Requirement: Slide Deck opens in a dedicated workspace
The frontend SHALL open Slide Deck generation and editing in a dedicated full-screen workspace or route.

#### Scenario: Open from Studio card
- **WHEN** a user clicks the Slide Deck/PPT card in the Studio panel with sources selected
- **THEN** the frontend SHALL create or open a deck workspace instead of showing a placeholder-only message

#### Scenario: Return to main workbench
- **WHEN** a user clicks the back/return control in the deck workspace
- **THEN** the frontend SHALL return to the main NotebookLM-Lite three-column workbench without losing persisted deck state

### Requirement: Workspace follows NotebookLM-Lite visual style
The slide deck workspace SHALL use NotebookLM-Lite's warm visual system while reusing AIPPT's useful interaction structure.

#### Scenario: Workspace layout
- **WHEN** the workspace is open on desktop
- **THEN** it SHALL show a left slide/page list, center large preview, and right workflow/edit/export panel

#### Scenario: Responsive behavior
- **WHEN** the workspace is viewed on narrow screens
- **THEN** controls and previews SHALL remain usable without clipped text, overlapping panels, or inaccessible actions

### Requirement: Outline and prompt plan are editable
The frontend SHALL allow users to review and edit generated outline and prompt-plan content before confirming each stage.

#### Scenario: Edit outline before confirmation
- **WHEN** the outline is generated
- **THEN** the user SHALL be able to edit deck title, slide titles, key points, narrative goals, and visual direction before confirming

#### Scenario: Edit prompt plan before confirmation
- **WHEN** the prompt plan is generated
- **THEN** the user SHALL be able to edit per-slide title, display content, content summary, and image prompt before confirming

### Requirement: Slide preview supports generation state
The frontend SHALL render slide-level status during image generation.

#### Scenario: Render generated slide
- **WHEN** a slide image is available
- **THEN** the center preview SHALL show the selected slide image with page metadata

#### Scenario: Render loading and error states
- **WHEN** a slide is generating or failed
- **THEN** the slide list and preview SHALL show clear status and available retry actions

### Requirement: Single-slide regenerate and edit are available
The frontend SHALL expose single-slide regenerate and edit controls for generated slides.

#### Scenario: Regenerate selected slide
- **WHEN** a user selects a generated slide and clicks regenerate
- **THEN** the frontend SHALL call the backend regenerate endpoint and update only that slide when the job succeeds

#### Scenario: Edit selected slide
- **WHEN** a user enters an edit instruction for a generated slide and clicks edit
- **THEN** the frontend SHALL call the backend edit endpoint, show progress, and append an edit history entry when successful

#### Scenario: View edit history
- **WHEN** a slide has previous edits
- **THEN** the frontend SHALL show edit history with enough information to understand or restore prior versions if restore is implemented

### Requirement: The integrated UI does not expose AIPPT standalone configuration
The frontend SHALL use NotebookLM-Lite runtime settings for model configuration.

#### Scenario: No duplicate API config form
- **WHEN** a user opens the slide deck workspace
- **THEN** the UI SHALL NOT show AIPPT's standalone API configuration form or require separate PPT-only keys
