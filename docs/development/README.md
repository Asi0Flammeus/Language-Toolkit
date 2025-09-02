# Development Guide

Welcome to the Language Toolkit development guide. This document provides guidelines for contributing to the project.

## 🚀 Getting Started

### Development Setup

1. **Fork and Clone**:
```bash
git clone https://github.com/YOUR_USERNAME/Language-Toolkit.git
cd Language-Toolkit
```

2. **Create Virtual Environment**:
```bash
python3 -m venv env
source env/bin/activate  # Linux/Mac
# or
.\env\Scripts\activate  # Windows
```

3. **Install Development Dependencies**:
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt  # Development tools
```

4. **Set Up Pre-commit Hooks**:
```bash
pre-commit install
```

## 📁 Project Architecture

### Directory Structure
```
Language-Toolkit/
├── main.py              # GUI application entry
├── api_server.py        # FastAPI server
├── ui/                  # GUI components
│   ├── base_tool.py     # Base class for all tools
│   └── mixins.py        # Shared UI functionality
├── tools/               # Tool implementations
│   ├── __init__.py      # Tool exports
│   └── *.py             # Individual tools
├── services/            # Business logic
│   ├── translation.py   # Translation service
│   ├── transcription.py # Transcription service
│   └── ...
├── utils/               # Utility functions
│   ├── file_handler.py  # File operations
│   ├── progress.py      # Progress tracking
│   └── ...
├── config/              # Configuration
│   └── manager.py       # Config management
└── tests/               # Test suite
```

### Design Principles

1. **Separation of Concerns**: Tools, services, and UI are clearly separated
2. **DRY (Don't Repeat Yourself)**: Common functionality in base classes and mixins
3. **Dependency Injection**: Tools receive dependencies through constructor
4. **Observer Pattern**: Progress updates via queue system
5. **Factory Pattern**: Tool creation and initialization

## 🔧 Adding New Features

### Creating a New Tool

1. **Create Tool Module** in `tools/`:
```python
# tools/my_new_tool.py
from ui.base_tool import ToolBase

class MyNewTool(ToolBase):
    def __init__(self, master, config_manager, progress_queue):
        super().__init__(master, "My New Tool", config_manager, progress_queue)
        self.setup_ui()
    
    def setup_ui(self):
        # Tool-specific UI setup
        pass
    
    def process_single_file(self, input_path, output_dir):
        # Implement file processing logic
        pass
```

2. **Export from** `tools/__init__.py`:
```python
from .my_new_tool import MyNewTool
```

3. **Add to Main Application** in `main.py`:
```python
self.my_tool = MyNewTool(my_tab, self.config_manager, self.progress_queue)
```

### Creating a New API Endpoint

1. **Add Route** in `api_server.py`:
```python
@app.post("/api/my-endpoint")
async def my_endpoint(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    token: str = Depends(verify_token)
):
    # Implement endpoint logic
    pass
```

2. **Add Service Logic** if needed in `services/`:
```python
# services/my_service.py
class MyService:
    def process(self, input_data):
        # Implement business logic
        pass
```

## 🧪 Testing

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/test_translation.py

# Run with verbose output
pytest -v
```

### Writing Tests
```python
# tests/test_my_feature.py
import pytest
from tools.my_new_tool import MyNewTool

class TestMyNewTool:
    def test_initialization(self):
        # Test tool initialization
        pass
    
    def test_file_processing(self, tmp_path):
        # Test file processing logic
        pass
```

### Test Coverage Goals
- Minimum 80% code coverage
- 100% coverage for critical paths
- All API endpoints tested
- Error handling verified

## 🎨 Code Style

### Python Style Guide
- Follow PEP 8
- Maximum line length: 120 characters
- Use type hints where appropriate
- Docstrings for all public methods

### Naming Conventions
- Classes: `PascalCase`
- Functions/Methods: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Private methods: `_leading_underscore`

### Example Docstring
```python
def process_file(input_path: str, output_dir: str) -> bool:
    """
    Process a single file.
    
    Args:
        input_path: Path to input file
        output_dir: Output directory path
    
    Returns:
        bool: True if successful, False otherwise
    
    Raises:
        FileNotFoundError: If input file doesn't exist
        PermissionError: If output directory isn't writable
    """
```

## 🔄 Git Workflow

### Branch Naming
- Features: `feature/description`
- Bugfixes: `fix/description`
- Documentation: `docs/description`
- Refactoring: `refactor/description`

### Commit Messages
```
type(scope): brief description

Longer explanation if needed.

Fixes #123
```

Types: feat, fix, docs, style, refactor, test, chore

### Pull Request Process
1. Create feature branch from `main`
2. Make changes and commit
3. Run tests and ensure passing
4. Update documentation if needed
5. Submit PR with clear description
6. Address review feedback
7. Squash and merge when approved

## 🐛 Debugging

### Logging
```python
import logging

logger = logging.getLogger(__name__)

def my_function():
    logger.debug("Debug information")
    logger.info("General information")
    logger.warning("Warning message")
    logger.error("Error occurred")
```

### Debug Mode
```python
# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# API server debug mode
uvicorn api_server:app --reload --log-level debug
```

## 📋 Checklist for Contributors

Before submitting a PR:
- [ ] Code follows style guidelines
- [ ] Tests added/updated and passing
- [ ] Documentation updated
- [ ] Commit messages follow convention
- [ ] No sensitive data in commits
- [ ] Branch is up-to-date with main
- [ ] PR description is clear

## 🤝 Getting Help

- Review existing [issues](https://github.com/Asi0Flammeus/Language-Toolkit/issues)
- Check [documentation](../README.md)
- Ask in PR comments
- Contact maintainers

## 📄 License

By contributing, you agree that your contributions will be licensed under the MIT License.