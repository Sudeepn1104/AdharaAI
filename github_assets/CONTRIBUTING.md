# Contributing to AdharaAI

Thanks for your interest in contributing! AdharaAI is an active student research project focused on making Indian legal documents accessible to everyone.

## Ways to contribute

### 🗂️ Dataset contributions
The most impactful thing you can do is share anonymised Indian legal documents:
- Rental agreements (Karnataka, Maharashtra, Delhi preferred)
- Employment offer letters
- Consumer court notices
- Section 138 notices

Please remove all personal names, addresses, and identifying details before sharing.

### 🐛 Bug reports
Open an issue with:
- What you uploaded (document type, approximate length)
- What you expected to see
- What you actually saw
- Your OS and Python version

### 💡 Feature requests
Open an issue tagged `enhancement`. High-priority features we're actively looking for help with:
- Hindi language support for mixed-script documents
- PDF export with highlighted clause annotations
- Additional Indian legal rule patterns in `risk_flagger.py`

### 🔧 Code contributions

1. Fork the repo and create a branch: `git checkout -b feature/your-feature`
2. Make your changes with clear commit messages
3. Run the test suite: `python -m pytest tests/` (when tests are added)
4. Open a pull request with a description of what you changed and why

## Development setup

See the [README](README.md) for full setup instructions.

## Code style

- Python: follow PEP 8, use type hints where practical
- Commit messages: present tense, imperative mood ("Add Hindi detection" not "Added Hindi detection")
- Comments: write why, not what

## Questions?

Open an issue or reach out on LinkedIn.
