## ADDED Requirements

### Requirement: Workbench keeps a left-middle-right layout
The frontend SHALL present NotebookLM-Lite as a three-region workbench: sources, chat, and Studio.

#### Scenario: Desktop layout
- **WHEN** the viewport is desktop-sized
- **THEN** the left panel SHALL show sources, the middle panel SHALL show chat, and the right panel SHALL show Studio tools and artifacts without horizontal clipping

#### Scenario: Narrow layout
- **WHEN** the viewport is narrow or mobile-sized
- **THEN** the layout SHALL remain usable through responsive stacking, tabs, or drawers without compressing any panel to unusable width

### Requirement: Sources can be selected for chat and artifact generation
The frontend SHALL let users select which successful sources participate in RAG and Studio generation.

#### Scenario: Select sources
- **WHEN** multiple sources are available
- **THEN** the user SHALL be able to include or exclude each source before asking a question or generating an artifact

### Requirement: Model configuration separates text and speech
The frontend SHALL provide separate model configuration sections for text models and speech models.

#### Scenario: Configure text model
- **WHEN** the user opens settings
- **THEN** the text model section SHALL support OpenAI-compatible, Anthropic, and Gemini/GenAI-style model configuration with model name, API key, and optional base URL

#### Scenario: Configure thinking behavior
- **WHEN** the user opens text model settings
- **THEN** the frontend SHALL expose a thinking enabled/disabled control and send the selected value with text generation requests

#### Scenario: Configure speech model
- **WHEN** the user opens settings
- **THEN** the speech model section SHALL remain separate and SHALL support model name, API key, base URL, voice, response format, and streaming-compatible audio generation options

### Requirement: Studio tools expose first-phase text capabilities
The frontend SHALL make text-model-supported Studio tools available in the first phase.

#### Scenario: Text tool availability
- **WHEN** sources and text model configuration are available
- **THEN** mind map / 思维图谱, FAQ, flashcards/quiz, report/study guide, data table, and podcast script generation SHALL be invokable from the Studio panel

### Requirement: Generated artifacts have rich interactions
The frontend SHALL support expanding, previewing, playing when audio exists, and downloading generated artifacts.

#### Scenario: Podcast artifact
- **WHEN** a podcast artifact is expanded
- **THEN** the frontend SHALL show transcript preview, download controls, and real audio playback controls when audio is available, and SHALL show a clear script-only state when audio is unavailable

#### Scenario: PPT artifact placeholder
- **WHEN** a PPT artifact exists without rendered images
- **THEN** the frontend SHALL show outline or slide text preview and indicate that image rendering/export depends on the PPT adapter and image model configuration
