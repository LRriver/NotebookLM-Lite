## ADDED Requirements

### Requirement: Text models are routed through LiteLLM
The system SHALL use LiteLLM as the unified runtime for text generation instead of provider-specific backend branches.

#### Scenario: OpenAI-compatible model call
- **WHEN** a user configures an OpenAI-compatible model, API key, and optional base URL
- **THEN** the backend SHALL call the model through LiteLLM using the provided configuration

#### Scenario: Anthropic or Gemini model call
- **WHEN** a user configures an Anthropic or Gemini/GenAI model supported by LiteLLM
- **THEN** the backend SHALL call the model through the same LiteLLM provider interface used for OpenAI-compatible models

### Requirement: Text generation supports a thinking toggle
The system SHALL expose a user-configurable thinking toggle for text generation and pass the selected state to compatible model backends.

#### Scenario: Thinking enabled
- **WHEN** the user enables thinking in model configuration
- **THEN** text model requests SHALL include a parameter equivalent to `{"thinking": {"type": "enabled"}}` when the selected backend supports passthrough thinking options

#### Scenario: Thinking disabled
- **WHEN** the user disables thinking in model configuration
- **THEN** text model requests SHALL include a parameter equivalent to `{"thinking": {"type": "disabled"}}` when the selected backend supports passthrough thinking options

#### Scenario: Backend does not support thinking
- **WHEN** the selected backend rejects or does not support the thinking parameter
- **THEN** the model runtime SHALL either omit the parameter for that backend or return a clear configuration error without breaking unrelated model calls

### Requirement: Structured outputs are Pydantic-validated
The system SHALL validate model-generated structured outputs with Pydantic models before saving artifacts or returning successful workflow results.

#### Scenario: Valid structured artifact
- **WHEN** a model returns JSON that conforms to the requested Pydantic schema
- **THEN** the backend SHALL parse and save the typed payload

#### Scenario: Invalid structured artifact
- **WHEN** a model returns missing, malformed, or schema-invalid structured output
- **THEN** the backend SHALL retry once with schema repair instructions and fail the job if the retry is still invalid

### Requirement: Embeddings use the configured model runtime
The system SHALL generate retrieval embeddings through a configurable model runtime instead of hard-coding OpenAI embeddings in the vector store.

#### Scenario: Embedding configuration
- **WHEN** an embedding model is configured in settings or request context
- **THEN** source ingestion and RAG query embedding SHALL use that configured model

### Requirement: Local secrets stay out of version control
The system SHALL use a committed example config and an ignored local config for sensitive keys.

#### Scenario: Example configuration
- **WHEN** the repository is prepared for commit
- **THEN** `config_example.yaml` SHALL describe required text, embedding, audio, image, and edit model fields without real keys, and `config.yaml` SHALL remain ignored

### Requirement: Audio models use the shared model profile configuration
The system SHALL configure speech synthesis through `api.models.audio_model` and expose it through the same backend model configuration boundary as other model roles.

#### Scenario: Configured OpenAI-compatible speech endpoint
- **WHEN** `api.models.audio_model` provides model, base URL, API key, optional voice, and optional response format
- **THEN** podcast audio synthesis SHALL use those values to call an OpenAI-compatible `/audio/speech` endpoint and stream MP3 bytes to a local output file

#### Scenario: LiteLLM speech route is available
- **WHEN** the LiteLLM runtime supports the configured speech endpoint and streaming behavior
- **THEN** the backend SHALL use LiteLLM or its OpenAI-compatible route for speech synthesis

#### Scenario: LiteLLM speech route is unavailable
- **WHEN** LiteLLM does not expose the required streaming speech behavior for the configured endpoint
- **THEN** the backend SHALL use a thin direct HTTP/OpenAI-compatible fallback behind the same `AudioSpeechProvider` interface without adding a separate provider-specific UI path
