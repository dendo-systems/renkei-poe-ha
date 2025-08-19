# Contributing to RENKEI PoE Motor Control Integration

Thank you for your interest in contributing to the RENKEI PoE Motor Control Integration for Home Assistant! This guide will help you get started with contributing to the project.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Environment Setup](#development-environment-setup)
- [Code Standards](#code-standards)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Issue Guidelines](#issue-guidelines)
- [Translation Contributions](#translation-contributions)
- [Documentation](#documentation)

## Getting Started

### Prerequisites

- Python 3.11 or later
- Home Assistant 2023.8 or later
- Basic understanding of Home Assistant custom components
- Familiarity with asyncio and TCP networking concepts

### Types of Contributions

We welcome various types of contributions:

- **Bug reports** and issue identification
- **Feature requests** and enhancements
- **Code contributions** (bug fixes, new features, optimizations)
- **Documentation improvements**
- **Translation updates** (6 languages currently supported)
- **Testing** and quality assurance

## Development Environment Setup

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/renkei-poe-ha.git
cd renkei-poe-ha
```

### 2. Development Dependencies

```bash
# Install test dependencies
cd custom_components/renkei_poe/tests
pip install -r requirements.txt
```

### 3. Home Assistant Development

For testing with Home Assistant:

```bash
# Install Home Assistant in development mode
pip install homeassistant>=2023.8.0

# Create a test configuration directory
mkdir -p ~/.homeassistant/custom_components
ln -s /path/to/renkei-poe-ha/custom_components/renkei_poe ~/.homeassistant/custom_components/
```

## Code Standards

### Python Code Style

This project follows Home Assistant's coding standards:

- **PEP 8** compliance for Python code style
- **Type hints** required for all functions and methods
- **Async/await** patterns for all I/O operations
- **Docstrings** for all public functions and classes

### Code Quality Tools

Run these tools before submitting code:

```bash
# Python linting (ensure follows Home Assistant standards)
python3 -m flake8 custom_components/renkei_poe/
python3 -m pylint custom_components/renkei_poe/

# Type checking
python3 -m mypy custom_components/renkei_poe/

# Home Assistant validation
python3 -m script.hassfest --integration-path custom_components/renkei_poe/
```

### Code Organization

- **Follow existing patterns** in the codebase
- **Use existing utilities** and helper functions when possible
- **Maintain separation of concerns** between client, coordinator, and platform layers
- **Add comprehensive error handling** with appropriate logging levels

### Key Architecture Components

- `renkei_client.py` - Core TCP communication with motors
- `coordinator.py` - Data update coordination and caching
- `cover.py` - Home Assistant cover platform implementation
- `config_flow.py` - UI configuration flow with discovery
- `const.py` - Constants, schemas, and error definitions

## Testing

### Running Tests

```bash
# Run full test suite with coverage
python3 -m pytest tests/ --cov=custom_components/renkei_poe

# Run specific test files
python3 -m pytest tests/test_config_flow.py -v
python3 -m pytest tests/test_cover.py -v
python3 -m pytest tests/test_init.py -v

# Run tests with coverage report
python3 -m pytest tests/ --cov=custom_components/renkei_poe --cov-report=html
```

### Test Requirements

- **Minimum 80% code coverage** (enforced by pytest configuration)
- **All tests must pass** before submitting PRs
- **Add tests for new features** and bug fixes
- **Use proper mocking** for external dependencies (network, Home Assistant core)

### Test Structure

- `tests/conftest.py` - Shared fixtures and test configuration
- `tests/test_*.py` - Test files matching the module structure
- Use `pytest-asyncio` for async test functions
- Mock external dependencies appropriately

## Submitting Changes

### Pull Request Process

1. **Create a feature branch** from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** following the code standards above

3. **Add tests** for new functionality or bug fixes

4. **Run the test suite** and ensure all tests pass:
   ```bash
   python3 -m pytest tests/ --cov=custom_components/renkei_poe
   ```

5. **Update documentation** if needed (README.md, SERVICES.md, etc.)

6. **Commit your changes** with descriptive commit messages:
   ```bash
   git commit -m "Add support for motor speed control"
   # or
   git commit -m "Fix connection timeout in status updates"
   ```

7. **Push to your fork** and create a pull request:
   ```bash
   git push origin feature/your-feature-name
   ```

### Pull Request Guidelines

- **Clear description** of changes and motivation
- **Reference related issues** using `Closes #123` or `Fixes #456`
- **Include test results** and coverage information
- **Update CHANGELOG** if significant changes (we'll help with this)
- **Keep changes focused** - one feature/fix per PR when possible

### Commit Message Format

We use descriptive commit messages that clearly explain the change:

- **New features**: "Add support for motor speed control"
- **Bug fixes**: "Fix connection timeout in status updates"
- **Documentation**: "Update contributing guidelines"
- **Tests**: "Add tests for config flow validation"
- **Refactoring**: "Refactor client connection handling"
- **Releases**: "Release v1.0.5 - Documentation Update"

Use present tense and start with a capital letter. Be descriptive about what the change accomplishes.

## Issue Guidelines

### Bug Reports

When reporting bugs, please include:

- **Home Assistant version**
- **Integration version**
- **Motor model and firmware version**
- **Network configuration** (VLAN, firewall settings, etc.)
- **Complete error logs** from Home Assistant
- **Steps to reproduce** the issue
- **Expected vs actual behavior**

### Feature Requests

For feature requests, please include:

- **Use case description** - what problem does this solve?
- **Proposed solution** - how should it work?
- **Alternative solutions** - other approaches considered?
- **Additional context** - screenshots, examples, etc.

### Issue Labels

We use these labels to categorize issues:

- `bug` - Something isn't working
- `enhancement` - New feature or improvement
- `documentation` - Documentation improvements
- `help wanted` - Extra attention needed
- `good first issue` - Good for newcomers
- `translation` - Translation updates needed

## Translation Contributions

### Supported Languages

Currently supported languages in `translations/`:

- English (`en.json`)
- German (`de.json`)
- Spanish (`es.json`)
- French (`fr.json`)
- Japanese (`ja.json`)
- Chinese (`zh.json`)

### Adding/Updating Translations

1. **Copy the English template** (`translations/en.json`)
2. **Translate all strings** maintaining the JSON structure
3. **Test the translation** by changing Home Assistant language
4. **Submit a PR** with the translation file

### Translation Guidelines

- **Keep technical terms consistent** (e.g., "motor", "position", "encoder")
- **Maintain placeholder format** (e.g., `{device_name}`, `{error_code}`)
- **Use appropriate formality level** for the target language
- **Test in Home Assistant UI** to ensure proper display

## Documentation

### Documentation Standards

- **Clear and concise** explanations
- **Code examples** for complex features
- **Screenshots** for UI-related changes
- **Update all relevant files** (README.md, SERVICES.md, etc.)

### Documentation Files

- `README.md` - Main project documentation
- `SERVICES.md` - Service reference documentation
- `TROUBLESHOOTING.md` - Common issues and solutions
- `CLAUDE.md` - Development context and architecture
- Code comments and docstrings within source files

## Development Tips

### Working with the RENKEI Client

The `RenkeiClient` class in `renkei_client.py` handles all motor communication:

```python
# Example: Adding a new command
async def new_command(self, param: int) -> dict:
    """Send a new command to the motor."""
    return await self.send_command("NEW_CMD", {"param": param})
```

### Home Assistant Integration Patterns

Follow these Home Assistant patterns:

- **Use coordinators** for data management (`coordinator.py`)
- **Implement proper state management** in platform entities
- **Handle availability** based on connection status
- **Use device registry** for proper device representation
- **Implement diagnostics** for troubleshooting support

### Testing with Real Hardware

When testing with actual RENKEI PoE motors:

1. **Use a test network** to avoid disrupting production systems
2. **Document network setup** (IP addresses, VLANs, etc.)
3. **Test discovery and manual configuration** paths
4. **Verify all services** work correctly
5. **Test error scenarios** (network disconnection, motor errors, etc.)

## Getting Help

### Community Support

- **GitHub Issues** - Bug reports and feature requests
- **GitHub Discussions** - Community questions and ideas
- **Code Reviews** - We provide feedback on all pull requests

### Maintainer Contact

- **GitHub**: `@dendo-systems`
- **Issues**: [Project Issues](https://github.com/dendo-systems/renkei-poe-ha/issues)

## Code of Conduct

We are committed to providing a welcoming and inclusive experience for everyone. Please:

- **Be respectful** and constructive in all interactions
- **Focus on the code** and technical discussions
- **Help newcomers** learn and contribute
- **Assume good intentions** from other contributors

## Recognition

Contributors will be recognized in:

- **GitHub contributors list**
- **Release notes** for significant contributions
- **Project documentation** when appropriate

Thank you for contributing to making Home Assistant integration with RENKEI PoE motors better for everyone!

---

*Last updated: August 2025*