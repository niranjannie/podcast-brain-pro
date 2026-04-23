# Contributing to Podcast Brain Pro

Thank you for your interest! This is an open-source project and all contributions are welcome.

## How to Contribute

### 1. Report Bugs
Open an issue with:
- A clear description of the problem
- Steps to reproduce
- Your environment (macOS version, Python version, device)
- Any error logs

### 2. Suggest Features
Open a discussion or issue describing:
- What the feature should do
- Why it would be useful
- Any ideas for implementation

### 3. Submit Code
1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Run tests if available: `pytest`
5. Commit with clear messages
6. Open a Pull Request

## Development Guidelines

- **Python style:** Follow PEP 8
- **Frontend:** The UI is a single HTML file. Keep it self-contained (no build step).
- **No hardcoded paths:** Use environment variables or `os.path` relative to `__file__`
- **No secrets in code:** API keys must never be committed
- **Privacy first:** No analytics, tracking, or telemetry

## Areas We Need Help

- 🍎 **CUDA support** for NVIDIA GPUs (currently optimized for Apple Silicon MPS)
- 🔊 **Faster multi-speaker TTS** alternatives or stitching optimizations
- 🌍 **More language support** beyond English and Indian languages
- 🎨 **UI/UX improvements** in the single-page frontend
- 📚 **Documentation** and tutorials

## Code of Conduct

Be respectful, constructive, and inclusive. We’re all here to build something useful together.
