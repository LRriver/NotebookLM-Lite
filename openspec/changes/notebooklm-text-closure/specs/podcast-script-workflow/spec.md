## ADDED Requirements

### Requirement: Podcast scripts use structured output
The system SHALL generate podcast scripts through Pydantic-validated structured output.

#### Scenario: Script generation
- **WHEN** a user requests a podcast script from selected sources
- **THEN** the backend SHALL return a validated script with title, speakers, ordered dialogue turns, estimated duration, source coverage notes, and transcript text

### Requirement: Podcast duration supports up to 30 minutes
The system SHALL allow users to choose podcast script duration up to 30 minutes.

#### Scenario: Long podcast request
- **WHEN** a user requests a 20 to 30 minute podcast script
- **THEN** the workflow SHALL iteratively expand dialogue content until it reaches the configured target band or hits a documented bounded-retry failure

#### Scenario: Duration estimate
- **WHEN** a podcast script is generated
- **THEN** the response SHALL include estimated duration based on transcript length and configured speech-rate assumptions

### Requirement: Podcast workflow expands coverage in batches
The system SHALL generate long scripts through planning, batched dialogue generation, critique, and expansion rather than a single prompt.

#### Scenario: Expansion loop
- **WHEN** the initial script is shorter than the requested minimum duration
- **THEN** the workflow SHALL identify under-covered source topics and request additional structured dialogue turns that continue from the existing script

### Requirement: Podcast audio is generated when audio_model is configured
The system SHALL synthesize podcast MP3 audio after script generation when `api.models.audio_model` is configured.

#### Scenario: Configured audio model
- **WHEN** podcast script generation succeeds and `audio_model` configuration is available
- **THEN** the backend SHALL call the configured speech endpoint, stream MP3 bytes to an output file, and attach an audio URL and local download endpoint to the podcast artifact

#### Scenario: Speech request payload
- **WHEN** the backend synthesizes podcast audio
- **THEN** the request SHALL include the configured model, dialogue text input, configured or derived voice, `response_format` set to `mp3` unless overridden, and streaming enabled when supported

### Requirement: Script artifacts survive audio unavailability
The system SHALL preserve script-only podcast artifacts when speech synthesis cannot run or fails.

#### Scenario: No speech configuration
- **WHEN** a user generates a podcast without TTS configuration
- **THEN** the backend SHALL save the transcript/script artifact successfully and mark audio generation as unavailable

#### Scenario: Audio synthesis failure
- **WHEN** speech model configuration is provided but audio synthesis fails or times out
- **THEN** the backend SHALL keep the transcript/script artifact, record the audio error on the job, and avoid losing the generated script
