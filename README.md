# NotebookLM-Lite (Sci-Fi Edition)

NotebookLM-Lite is a note-taking application inspired by Google's NotebookLM, aiming to fully replicate features such as document Q&A, podcast generation, and presentation creation. It is currently under development. For a simple Chinese podcast generation feature, please refer to the v0.1 branch.

## ✨ Features

- **Unified LLM Interface**: Seamlessly switch between OpenAI and Anthropic models.
- **Neural Audio Synthesis**: High-quality, multi-speaker podcast generation using CosyVoice (via Dashscope).
- **PDF Intelligence**: Robust parsing and semantic understanding of uploaded documents.
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
    *   Select your **LLM Provider** (OpenAI Compatible or Anthropic).
    *   Enter your **API Key** and **Model Name** (e.g., `gpt-4o`).
    *   Enter your **Dashscope API Key** for TTS service.
3.  **Upload**: Drag & drop a PDF file into the "Data Source" area.
4.  **Generate**: Click **INITIALIZE SEQUENCE**. The system will process the text and synthesize audio.
5.  **Listen**: Use the built-in player to listen to your podcast or download it.

## 📄 License

Apache 2.0