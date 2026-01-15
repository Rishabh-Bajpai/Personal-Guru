# Contributing to Personal Guru

Thank you for your interest in contributing to Personal Guru! We welcome contributions from the community.

## Quick Start

1. **Fork & Clone**

   ```bash
   git clone https://github.com/YOUR_USERNAME/Personal-Guru.git
   cd Personal-Guru
   ```

2. **Set Up Environment**

   ```bash
   conda create -n Personal-Guru python=3.11
   conda activate Personal-Guru
   pip install -r requirements.txt
   pre-commit install
   ```

3. **Start Services**

   ```bash
   docker compose up -d db      # PostgreSQL database
   python scripts/update_database.py
   python run.py                # Start the app
   ```

## How to Contribute

### Reporting Bugs

- Check [existing issues](https://github.com/Rishabh-Bajpai/Personal-Guru/issues) first
- Use the **Bug Report** issue template
- Include steps to reproduce, expected vs actual behavior

### Suggesting Features

- Use the **Feature Request** issue template
- Describe the use case and proposed solution

### Code Contributions

1. **Create a branch**

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Follow existing code style
   - Add docstrings to new functions
   - Write tests for new functionality

3. **Run checks**

   ```bash
   pre-commit run --all-files    # Linting & formatting
   python -m pytest -m unit      # Unit tests
   python -m pytest              #all tests
   ```

4. **Submit a Pull Request**

   - Use the PR template
   - Link related issues (if closes an issue, use `closes #123, #456`)
   - Provide a clear description

## Code Standards

- **Python**: Formatted with Black, linted with Ruff
- **JavaScript/CSS/HTML**: Formatted with Prettier
- **Docstrings**: Required for all public functions (checked by Interrogate)
- **Commits**: Use clear, descriptive commit messages

## Project Structure

```
Personal-Guru/
├── app/                    # Flask application
│   ├── core/              # Core routes, models, extensions
│   ├── modes/             # Learning modes (chat, chapter, quiz, etc.)
│   └── common/            # Shared utilities and agents
├── scripts/               # Development utilities
├── tests/                 # Test suite
├── docs/                  # Documentation
└── installation/          # Setup scripts
```

## Development Tips

- Use `python scripts/db_viewer.py` to browse the database
- Check `docs/architecture.md` for system design

## Getting Help

- Open an issue with the **Question** label
- Check documentation at [samosa-ai.com/personal-guru/docs](https://samosa-ai.com/personal-guru/docs)

## License

By contributing, you agree that your contributions will be licensed under the [AGPL-3.0 License](LICENSE).

---

Thank you for helping make Personal Guru better! 🙏
