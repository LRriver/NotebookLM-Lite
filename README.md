# 📚 Easy-NotebookLM

[English] | [中文](README_zh.md)

**Easy-NotebookLM** is a tool designed to generate Chinese podcasts based on the concept of Google's NotebookLM. It transforms content from PDF documents into natural, conversational-style podcast audio and supports multiple dialogue styles. Currently, it uses the [DeepSeek-v3](https://platform.deepseek.com/) API for model inference, though you can replace it with any other compatible model interface. For speech synthesis, it leverages the **CosyVoice** model.

> 🎙️ NotebookLM is an AI audio content generation tool developed by Google, previously limited to English content only. Easy-NotebookLM aims to provide a simple and user-friendly way to quickly generate high-quality Chinese podcasts from PDF files.

---

## 🧰 Requirements

- Python version: `3.12.8`
- Other dependencies: see `requirements.txt`
- Additional dependency: `ffmpeg` (must be installed manually)

### Setup Instructions
```bash
# Install dependencies
pip install -r requirements.txt

# Install ffmpeg (Mac/Linux examples)
brew install ffmpeg      # macOS
sudo apt-get install ffmpeg  # Ubuntu/Debian
```

### API Key Configuration

Before running, ensure the following environment variables are configured or set in the code:
- `DEEPSEEK_API_KEY` (for large language model inference)
- `DASHSCOPE_API_KEY` (optional, for Alibaba Cloud's Bailing platform)

Create a `.env` file in the project root directory and add your keys as follows:
```
DEEPSEEK_API_KEY=""
DASHSCOPE_API_KEY=""
```

---

## 📁 File Overview

| File Name         | Description |
|------------------|-------------|
| `notelm.py`        | Stable base version script for podcast generation, suitable for most users |
| `notelm_react.py`  | Enhanced version with ReAct pattern support; automatically evaluates generated results and regenerates if not up to standard. Still under development |
| `prompt.txt`       | Prompt template file used to control dialogue style |
| `speech/`          | Directory containing text materials used for podcast generation |
| `speech_pre/`      | Pre-generated podcast dialogues (both audio and text) |

---

## ⚙️ Command Line Arguments

You can customize the podcast generation process using command line arguments:

| Argument         | Description |
|------------------|-------------|
| `--input`         | Path to the input PDF file |
| `--output_dir`    | Output directory for generated files |
| `--len`           | Maximum length (in characters) per dialogue segment |
| `--minutes`       | Target duration of the generated audio (in minutes) |
| `--count`         | Number of dialogue segments to generate |
| `--prompt_type`   | Dialogue style type, default is `'default'`. See below for options: |

### ✨ Supported Prompt Types (Dialogue Styles)

| Type         | Description |
|--------------|-------------|
| `default`     | Default mode: host primarily guides the guest through Q&A |
| `discussion`  | Discussion mode: host has some knowledge and actively interacts with the guest |
| `teaching`    | Teaching mode: dialogue between a teacher and student |
| `argument`    | Debate mode: host and guest have opposing views and engage in discussion |
| `interview`   | Interview mode: interviewer asks questions, interviewee answers; ideal for technical articles |

> ⚠️ Note: These parameters offer approximate control — actual output may vary slightly.

---

## 🧪 Usage Examples

Basic usage:
```bash
python notelm.py --input sample.pdf --output_dir ./output --prompt_type discussion
```

Enable ReAct mode (experimental):
```bash
python notelm_react.py --input sample.pdf --output_dir ./output --count 5
```

---

## 📌 Development Roadmap & Improvements

- 🔜 Add support for MCP (upcoming feature)
- 🔜 Support additional  models
- 🔜 Add GUI support
- 🔜 Support video generation with embedded subtitles
- 🔜 Support Markdown or Word document inputs

---

## 🤝 Contributing

All contributions are welcome! Whether it's feature suggestions, bug reports, or pull requests — we'd love to hear from you!

For more details, please read our [CONTRIBUTING.md](CONTRIBUTING.md).

---

## 📄 License

This project is licensed under the [Apache 2.0 License](LICENSE).

---

## ❤️ Acknowledgments

- Inspired by [Google NotebookLM](https://notebooklm.withgoogle.com/)
- Thanks to [open-notebooklm](https://github.com/lfnovo/open-notebook) for reference implementation ideas
- Powered by [DeepSeek](https://platform.deepseek.com/) and [CosyVoice](https://github.com/FunAudioLLM/CosyVoice)

---

If you like this project, feel free to give it a Star, Fork, or share it with others! 🚀  
Got any questions or suggestions? Feel free to open an issue or leave a comment.