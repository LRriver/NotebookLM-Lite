# NotebookLM-Lite (Sci-Fi Edition)

NotebookLM-Lite is a note-taking application inspired by Google's NotebookLM, aiming to fully replicate features such as document Q&A, podcast generation, and presentation creation. It is currently under development. For a simple Chinese podcast generation feature, please refer to the v0.1 branch.

![NotebookLM-Lite workbench demo](docs/assets/notebooklm-lite-demo.gif)

[Watch the HD demo video](docs/assets/notebooklm-lite-demo.webm)

The demo covers configuring model profiles, adding a source, asking grounded RAG questions with citations, generating interactive Mind Map, Flashcards/Quiz, Data Table, Podcast, and Video Overview placeholder artifacts. Model waiting time is shortened for README pacing.

## ✨ Features

- **Unified LLM Interface**: Text generation, embeddings, rerank, and speech
  profiles are managed through LiteLLM/OpenAI-compatible settings.
- **Neural Audio Synthesis**: High-quality, multi-speaker podcast generation using CosyVoice (via Dashscope).
- **Document Intelligence**: Docling parses source files, Chonkie chunks text,
  and SeekDB stores sources/chunks for hybrid RAG retrieval with citations.
- **Interactive Player**: Integrated audio player with playback controls and download capability.

## 🛠️ Tech Stack

- **Frontend**: React, Vite, TailwindCSS, Framer Motion (animations)
- **Backend**: Python, FastAPI, Uvicorn
- **AI/ML**: OpenAI API, Anthropic API, Dashscope (TTS)

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- FFmpeg (Must be installed and added to system PATH)

### Installation

#### 1. Backend Setup

Navigate to the project root:

```bash
# Install Python dependencies
pip install -r requirements.txt

# Create your local configuration file
cp config_example.yaml config.yaml
```

Edit `config.yaml` and set the model credentials you want to use. Text,
embedding, optional rerank, and speech models are configured separately under
`api.models`. The default text path is LiteLLM/OpenAI-compatible, and
Anthropic or Gemini/GenAI-style model strings can be used through
LiteLLM-compatible configuration. Keep `config.yaml` local; it is ignored by
git and must not be committed with real keys.

```bash

# Start the API server
python backend/main.py
```
The backend will run at `http://localhost:8000`.

#### 2. Frontend Setup

Open a new terminal and navigate to the `frontend` directory:

```bash
cd frontend

# Install Node dependencies
npm install

# Start the development server
npm run dev
```
The UI will be available at `http://localhost:5173`.

## 📖 Usage Guide

1.  **Launch**: Open `http://localhost:5173` in your browser.
2.  **Configure**:
    *   Configure the text model, embedding model, optional rerank model, and optional speech model in `config.yaml`.
    *   The Settings button also loads local defaults and can refresh runtime model profiles without exposing configured keys back to the browser.
    *   Use the text model thinking toggle when the selected backend supports it.
    *   Speech/TTS is optional for text artifact generation; podcast scripts can still be generated without audio credentials.
3.  **Upload**: Drag & drop a file or paste text into Sources. New uploads use Chonkie chunking and configured embeddings when available.
4.  **Ask and Generate**: Select sources, ask RAG questions with citations, or generate Studio text artifacts and podcast scripts.
5.  **Listen**: Use the built-in player to listen to your podcast or download it.

## 📄 License

Apache 2.0
