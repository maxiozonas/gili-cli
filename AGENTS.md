# AGENTS.md - Guidelines for AI Coding Agents

This file provides guidelines for AI agents operating in this Magento Automation repository.

## Project Overview

Python-based CLI tool for Magento e-commerce automation. Uses:
- **CLI Framework**: Typer with Rich console output
- **Settings**: Pydantic + pydantic-settings with `.env`
- **Logging**: Structlog (structured JSON logs in `logs/app.log`)
- **Data Processing**: Pandas for ETL operations
- **API Integration**: requests with retry logic, Google Sheets (gspread)

## Build, Lint, and Test Commands

### Installation
```bash
pip install -r requirements.txt
```

### Development Dependencies
```bash
pip install -r requirements-dev.txt
```

### Linting (Ruff)
```bash
# Lint entire project
ruff check src/

# Fix auto-fixable issues
ruff check src/ --fix

# Lint specific file
ruff check src/core/client.py
```

### Formatting (Black)
```bash
# Format entire project
black src/

# Check formatting without changes
black src/ --check
```

### Type Checking (MyPy)
```bash
# Type check entire project
mypy src/

# Type check specific file
mypy src/core/client.py

# Verbose output with error codes
mypy src/ --show-error-codes
```

### All Checks (Pre-commit)
```bash
# Run ruff, black, and mypy
ruff check src/ && black src/ --check && mypy src/
```

### Testing (PyTest)
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_rfm.py

# Run specific test class
pytest tests/test_rfm.py::TestRFMProcessor

# Run single test
pytest tests/test_rfm.py::TestRFMProcessor::test_process_rfm_analysis

# Run with coverage
pytest --cov=src --cov-report=term-missing

# Run in verbose mode
pytest -v
```

### Running the Application
```bash
# Help
python main.py --help

# Run specific command
python main.py rfm --year 2025
python main.py sync
python main.py merchant
python main.py manual-update --apply
python main.py monthly-report -y 2025 -m 1

# Verbose logging
python main.py -v rfm --year 2025
```

---

## Code Style Guidelines

### Imports

**Standard Library First, Then Third-Party, Then Local:**
```python
# stdlib
from typing import Any, Dict, Iterator, List, Optional, Union
from datetime import datetime
from pathlib import Path
import json

# third-party
import pandas as pd
import requests
import structlog
from tqdm import tqdm
from rich.console import Console

# local (relative imports)
from ..config.settings import Settings
from ..core.exceptions import APIError
from ..utils import get_logger
```

**Avoid `from X import *`. Use explicit imports.**

### Type Hints

**Required for All Functions:**
```python
# Good
def fetch_orders(self, min_year: int, status: str = "processing") -> pd.DataFrame:
    ...

# Bad - missing return type
def fetch_orders(self, min_year: int):
    ...
```

**Use Optional for nullable values:**
```python
def get_product(self, sku: str) -> Optional[Dict[str, Any]]:
    ...

# Avoid
def get_product(self, sku: str) -> Dict[str, Any] | None:
    ...
```

**Use Iterator/Generator for paginated streams:**
```python
def get_products(self, page_size: int = 100) -> Iterator[Dict[str, Any]]:
    ...
```

### Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Classes | PascalCase | `MagentoAPIClient`, `RFMProcessor` |
| Functions/Methods | snake_case | `fetch_orders()`, `get_brand_map()` |
| Variables | snake_case | `order_data`, `brand_map` |
| Constants | UPPER_SASE | `MAX_RETRIES`, `DEFAULT_PAGE_SIZE` |
| Private Methods | snake_case with prefix | `_process_order()`, `_make_request()` |
| Module-level Config | UPPER_SNAKE_CASE | `MAGENTO_URL`, `API_TIMEOUT` |

### File Structure

```
src/
├── __init__.py           # Package exports
├── core/                 # Core business logic
│   ├── client.py         # Magento API client
│   └── exceptions.py     # Custom exceptions
├── connectors/           # External integrations
│   ├── google_sheets.py
│   ├── flexxus.py
│   └── merchant.py
├── processors/           # Data processing
│   ├── rfm.py
│   └── scoring.py
├── operations/           # CLI operation implementations
│   ├── manual_update.py
│   ├── monthly_report.py
│   └── export_category.py
├── config/               # Configuration
│   ├── settings.py       # Pydantic settings
│   └── constants.py
└── utils/                # Utilities
    ├── helpers.py
    └── logging.py
```

### Error Handling

**Use Custom Exceptions from `src/core/exceptions.py`:**
```python
from src.core.exceptions import APIError, AuthenticationError, ValidationError

# Good - raise with context
raise APIError(
    f"Failed to fetch orders: {e}",
    status_code=response.status_code,
    endpoint="/orders"
)

# Bad - generic exception
raise Exception("Error fetching orders")
```

**Log Errors with Context:**
```python
try:
    response = self.session.get(url)
    response.raise_for_status()
    return response.json()
except requests.RequestException as e:
    logger.error("api_request_failed", endpoint=endpoint, error=str(e))
    raise APIError(f"Request failed: {e}", endpoint=endpoint) from e
```

### Docstrings

**Use Google-style docstrings:**
```python
def fetch_orders(self, min_year: int, status: OrderStatus) -> pd.DataFrame:
    """Fetch orders from Magento API with field mapping.

    Args:
        min_year: Minimum order year to fetch
        status: Order status filter

    Returns:
        DataFrame with mapped order data

    Raises:
        AuthenticationError: If API authentication fails
        APIError: If the request fails
    """
    ...
```

### Logging

**Use Structlog for structured logging:**
```python
import structlog

logger = structlog.get_logger(__name__)

# Log with structured data
logger.info("orders_fetched", count=len(df), year=min_year)

# Avoid - print statements
print(f"Fetched {len(df)} orders")
```

**User-facing output goes to Rich Console, not logs:**
```python
from rich.console import Console

console = Console()

# For users
console.print("[bold green]Operación completada[/bold green]")

# For debugging/logs
logger.info("operation_completed", items_processed=count)
```

### Configuration (Pydantic Settings)

**Define settings in `src/config/settings.py`:**
```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    magento_url: str
    magento_user: str
    magento_password: str
    api_timeout: int = 30
    api_retries: int = 3
```

### CLI Commands (Typer)

**Use Typer with type hints:**
```python
import typer
from typing import Optional

app = typer.Typer()

@app.command()
def process(
    year: int = typer.Option(..., "--year", "-y", help="Year to process"),
    output: str = typer.Option("output.csv", "--output", "-o"),
    dry_run: bool = typer.Option(True, "--dry-run/--apply"),
) -> None:
    """Process data for a given year."""
    ...
```

### Code Patterns

**Context Manager for Resources:**
```python
# Good
with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
    df.to_excel(writer, sheet_name="Data", index=False)

# Avoid - manual close
writer = pd.ExcelWriter(output_file)
df.to_excel(writer, index=False)
writer.close()
```

**Iterator/Pagination Pattern:**
```python
def fetch_all(self, endpoint: str) -> Iterator[Dict]:
    """Paginate through API results."""
    page = 1
    while True:
        response = self._make_request("GET", endpoint, params={"page": page})
        items = response.get("items", [])
        if not items:
            break
        for item in items:
            yield item
        page += 1
```

### Performance

- Use `Iterator` for large API responses (don't load all into memory)
- Use `tqdm` for progress bars on long operations
- Reuse `requests.Session()` for connection pooling
- Batch operations where possible

### Security

- Never log sensitive data (passwords, tokens, customer PII)
- Use `.env` for credentials, never commit to version control
- Validate all inputs with Pydantic models
