# Prompt 01: Foundation Build
## KruppAI Core Framework — Project Scaffold, Infrastructure, and Base Components

> **Target**: Build the entire project scaffold, all shared infrastructure, and the test harness.
> **Estimated time**: 3-5 hours
> **Prerequisites**: Python 3.11+, pip, CLAUDE.md in project root
> **Output**: A runnable project with `kruppai` CLI that responds to `--help`, database initializes on first run, and all core components are importable and tested.

---

## Instructions for Claude Code

Read `CLAUDE.md` first — it defines all architecture rules, project layout, and conventions. Then build the following components in order. Every component must have corresponding tests. Do not skip tests — they are the safety net for the entire project.

---

## Step 1: Project Scaffold & Configuration

### 1.1 Create `pyproject.toml`

```toml
[project]
name = "kruppai"
version = "0.1.0"
description = "AI-powered document generation toolkit for construction general contractors"
requires-python = ">=3.11"
dependencies = [
    "anthropic>=0.40.0",
    "click>=8.1.0",
    "rich>=13.0.0",
    "python-docx>=1.1.0",
    "openpyxl>=3.1.0",
    "PyMuPDF>=1.24.0",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    "httpx>=0.27.0",
    "python-dotenv>=1.0.0",
    "Pillow>=10.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-cov>=5.0.0",
    "pytest-asyncio>=0.23.0",
    "black>=24.0.0",
    "isort>=5.13.0",
    "mypy>=1.8.0",
    "ruff>=0.3.0",
]

[project.scripts]
kruppai = "kruppai.cli.main:cli"

[tool.black]
line-length = 88

[tool.isort]
profile = "black"

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "integration: marks tests that require API key (deselect with '-m \"not integration\"')",
    "slow: marks tests that take >5s",
]
```

### 1.2 Create `kruppai/core/config.py`

Build the settings module using Pydantic BaseSettings:

```python
"""
Application configuration loaded from environment variables and .env file.

Settings hierarchy (highest priority first):
1. Environment variables
2. .env file
3. Default values

Key design decisions:
- All paths resolve to absolute paths on load
- Output directory is auto-created on first access
- API cost limits are in cents to avoid float math
- Model names use full Anthropic model IDs for clarity
"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="KRUPPAI_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # API
    anthropic_api_key: str = ""  # Also reads ANTHROPIC_API_KEY (no prefix)
    default_model: str = "claude-sonnet-4-5-20250929"
    opus_model: str = "claude-opus-4-6"

    # Paths
    db_path: Path = Path.home() / ".kruppai" / "kruppai.db"
    output_dir: Path = Path.home() / "KruppAI-Output"
    knowledge_dir: Path = Path("knowledge")  # Relative to project root

    # Limits
    daily_cost_limit_cents: int = 5000     # $50/day
    monthly_cost_limit_cents: int = 30000  # $300/month
    max_input_tokens: int = 150000         # Safety cap per request
    cost_warning_cents: int = 50           # Warn if single call > $0.50

    # Features
    weather_enabled: bool = True
    log_level: str = "INFO"

    def ensure_directories(self) -> None:
        """Create required directories if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
```

**Test requirements for config:**
- `test_default_settings_load` — Settings instantiate with defaults, no env vars needed
- `test_env_override` — Setting `KRUPPAI_OUTPUT_DIR=/tmp/test` overrides default
- `test_ensure_directories` — Calling `ensure_directories()` creates paths in a temp dir
- `test_api_key_from_anthropic_env` — Reads `ANTHROPIC_API_KEY` environment variable

---

## Step 2: Database Manager (`kruppai/core/database.py`)

Build a database connection manager that:
1. Initializes the schema from `schema/init.sql` on first run
2. Returns connections as context managers
3. Enforces `PRAGMA foreign_keys = ON` for every connection
4. Supports both SQLite (default) and future PostgreSQL via a clean interface

```python
"""
Database connection manager.

Key behaviors:
- Auto-creates database file and runs schema on first access
- Foreign keys always enforced
- All connections use context manager pattern
- Thread-safe: one connection per thread via check_same_thread=False
- get_next_number() provides auto-incrementing per project per entity type
"""
```

**Critical methods:**
- `init_db(settings: Settings) -> None` — Create DB, run `schema/init.sql`
- `get_db(settings: Settings) -> contextmanager[sqlite3.Connection]` — Yield a connection
- `get_next_number(conn, table: str, project_id: int, number_column: str) -> int` — Auto-incrementing number per project (for RFI numbers, CO numbers, etc.)

**Test requirements for database:**
- `test_init_creates_all_tables` — After init, every table from schema exists
- `test_foreign_keys_enforced` — Inserting a record with bad FK raises IntegrityError
- `test_get_next_number` — Returns 1 for first, 2 for second, handles multiple projects independently
- `test_context_manager_commits` — Successful block commits, exception block rolls back
- `test_idempotent_init` — Calling `init_db` twice doesn't error (CREATE IF NOT EXISTS)

---

## Step 3: Anthropic API Client (`kruppai/core/api_client.py`)

Build a wrapper around the Anthropic Python SDK that handles:
1. Model selection (Sonnet default, Opus for specified skills)
2. Retry logic with exponential backoff on 429/500/503
3. Token counting and cost calculation
4. Usage logging to database
5. Streaming support for long-running generations
6. Cost limit enforcement (daily/monthly caps)

```python
"""
Anthropic API client with retry logic, cost tracking, and usage limits.

Pricing (as of Feb 2026 — update if changed):
- claude-sonnet-4-5-20250929: $3/M input, $15/M output
- claude-opus-4-6: $15/M input, $75/M output

Every call returns an ApiResponse dataclass with:
- content: str (the generated text)
- model: str
- input_tokens: int
- output_tokens: int
- cost_cents: int (calculated from token counts)
- duration_ms: int
"""
```

**Key design: model routing logic**
```python
# Models that require Opus (precision-critical)
OPUS_SKILLS = {"contract_checker", "proposal_generator", "estimate_reviewer"}

def get_model_for_skill(skill_name: str, settings: Settings) -> str:
    if skill_name in OPUS_SKILLS:
        return settings.opus_model
    return settings.default_model
```

**Test requirements for API client:**
- `test_cost_calculation_sonnet` — 1000 input + 500 output tokens → correct cents
- `test_cost_calculation_opus` — Same tokens → higher cost (5x)
- `test_model_routing` — daily_report → sonnet, contract_checker → opus
- `test_retry_on_rate_limit` — Mock 429 response, verify retry with backoff
- `test_daily_cost_limit` — After exceeding limit, calls raise CostLimitExceeded
- `test_usage_logged_to_db` — After a call, api_usage table has a record
- `test_api_response_dataclass` — All fields populated correctly

> **Note**: Use `unittest.mock.patch` to mock the Anthropic client for unit tests. Mark any test that hits the real API with `@pytest.mark.integration`.

---

## Step 4: Document Parser (`kruppai/core/document_parser.py`)

Build a universal document parser that extracts text and structured data from:
1. **PDF** (via PyMuPDF) — text extraction, table detection, image extraction
2. **DOCX** (via python-docx) — paragraph text, table data, header/footer
3. **XLSX** (via openpyxl) — cell values by sheet, with headers, formulas noted
4. **Images** (via base64 encoding for Claude vision) — site photos, plan markups
5. **Plain text / Markdown** — pass-through with minimal processing

```python
"""
Universal document parser for construction documents.

Design principles:
- Returns a ParsedDocument dataclass with uniform structure regardless of source
- Handles corrupt/password-protected files gracefully (returns error, doesn't crash)
- Extracts tables as list[list[str]] for structured data
- Limits extracted text to max_chars (default 100,000) to control API costs
- Images returned as base64 for Claude vision API
"""

@dataclass
class ParsedDocument:
    source_path: Path
    file_type: str             # 'pdf', 'docx', 'xlsx', 'image', 'text'
    text: str                  # Extracted text content
    tables: list[list[list[str]]]  # List of tables, each table is rows of cells
    images: list[dict]         # [{base64: str, media_type: str, description: str}]
    metadata: dict             # {pages: int, author: str, created: str, ...}
    page_count: int
    char_count: int
    error: str | None          # Non-None if parsing failed

def parse_file(file_path: Path, max_chars: int = 100_000) -> ParsedDocument: ...
def parse_pdf(file_path: Path, max_chars: int) -> ParsedDocument: ...
def parse_docx(file_path: Path, max_chars: int) -> ParsedDocument: ...
def parse_xlsx(file_path: Path, max_chars: int) -> ParsedDocument: ...
def parse_image(file_path: Path) -> ParsedDocument: ...
```

**Test requirements for parser:**
- `test_parse_pdf_text_extraction` — Create a simple PDF in test fixture, verify text extracted
- `test_parse_docx_with_tables` — Create DOCX with table, verify table data in ParsedDocument
- `test_parse_xlsx_multi_sheet` — Create XLSX with 2 sheets, verify both extracted
- `test_parse_image_base64` — Verify image returns valid base64 string
- `test_max_chars_truncation` — Long document truncated at limit with "[TRUNCATED]" marker
- `test_unsupported_format` — `.zip` file returns ParsedDocument with error set
- `test_missing_file` — Nonexistent path returns ParsedDocument with error set
- `test_parse_file_dispatch` — Correct parser called based on file extension

---

## Step 5: Output Formatter (`kruppai/core/output_formatter.py`)

Build a document generator that creates branded output documents. This is **the most visible component** — every document the team sees comes through here.

```python
"""
Branded document generator for Krupp General Contractors.

Branding:
- Primary color: #1B3A5C (navy) — headers, table headers, borders
- Accent color: #D4A84B (gold) — highlights, accents
- Font: Calibri, 11pt body, 14pt headers
- Logo: loaded from company.logo_path or templates/krupp_logo.png
- Footer on every page: "Generated by KruppAI | {date} | Review required before distribution"

Supported output types:
- DOCX: Professional Word documents with tables, headers, branded formatting
- XLSX: Excel workbooks with formatted headers, data validation, auto-column-width
- PDF: Generated via DOCX → PDF conversion (python-docx → LibreOffice if available, else DOCX only)

File naming: {skill}_{project_code}_{date}_{sequence}.{ext}
"""

class OutputFormatter:
    def create_docx(self, content: DocumentContent, project: ProjectInfo) -> Path: ...
    def create_xlsx(self, content: SpreadsheetContent, project: ProjectInfo) -> Path: ...
    def generate_filename(self, skill: str, project_code: str, ext: str) -> str: ...
```

**DocumentContent structure** (what skills pass to the formatter):
```python
@dataclass
class DocumentContent:
    title: str
    subtitle: str | None = None
    date: str | None = None          # Defaults to today
    sections: list[Section] = field(default_factory=list)
    tables: list[TableData] = field(default_factory=list)
    header_fields: dict[str, str] = field(default_factory=dict)  # Key-value pairs for header block
    use_letterhead: bool = False      # Full letterhead (client-facing) vs. internal header

@dataclass
class Section:
    heading: str
    content: str                     # Can include markdown-style formatting
    level: int = 1                   # Heading level (1-3)

@dataclass
class TableData:
    title: str | None = None
    headers: list[str]
    rows: list[list[str]]
    column_widths: list[float] | None = None  # In inches
```

**Test requirements for output formatter:**
- `test_docx_creates_valid_file` — Generated DOCX opens without error, has content
- `test_docx_has_branding` — Verify navy headers, footer text present
- `test_xlsx_creates_valid_file` — Generated XLSX has correct sheets and data
- `test_filename_convention` — Follows `{skill}_{project_code}_{date}_{seq}.{ext}` pattern
- `test_table_formatting` — Table has alternating rows, bold headers
- `test_letterhead_vs_internal` — `use_letterhead=True` adds company address block
- `test_long_content_pagination` — Multi-page document has footer on every page
- `test_output_directory_creation` — Auto-creates output subdirectory if missing

---

## Step 6: Context Manager (`kruppai/core/context_manager.py`)

Build the project context loader that assembles all relevant data for a skill's prompt:

```python
"""
Loads project context from database for prompt assembly.

A ProjectContext contains everything a skill needs to generate a document:
- Project details (name, code, client, team, schedule, financials)
- Team members assigned to the project
- Subcontractors on the project with scope and status
- Open action items (carried forward from meetings)
- Recent documents generated (for continuity)
- Company profile (from knowledge base)

This is the "memory" that makes KruppAI outputs contextually aware.
"""

@dataclass
class ProjectContext:
    project: dict                    # Full project record
    team: list[dict]                 # Team members with roles
    subcontractors: list[dict]       # Subs with contract details
    open_action_items: list[dict]    # Unresolved action items
    recent_documents: list[dict]     # Last 10 generated docs
    company: dict                    # Company profile
    stats: dict                      # {total_rfis, open_rfis, total_cos, approved_co_value, ...}

class ContextManager:
    def load(self, project_id: int) -> ProjectContext: ...
    def load_by_code(self, project_code: str) -> ProjectContext: ...
    def get_project_list(self) -> list[dict]: ...  # For CLI project selection
```

**Test requirements for context manager:**
- `test_load_full_context` — With seeded DB, returns ProjectContext with all fields populated
- `test_load_empty_project` — New project with no docs/subs returns valid context with empty lists
- `test_stats_calculation` — RFI count, CO totals calculated correctly from DB
- `test_project_not_found` — Invalid project_id raises ProjectNotFoundError
- `test_load_by_code` — Can look up by "KRUPP-2026-003" instead of integer ID

---

## Step 7: Knowledge Base Loader (`kruppai/core/knowledge_base.py`)

Build the company knowledge base system that loads markdown files with company-specific information:

```python
"""
Loads company knowledge files for prompt enrichment.

Knowledge files are markdown documents in the knowledge/ directory:
- company_profile.md: Company history, capabilities, differentiators
- team_bios.md: Professional bios for proposals and case studies
- writing_standards.md: Tone, voice, terminology rules
- safety_standards.md: Safety policies and OSHA compliance requirements

These files are loaded and injected into system prompts so Claude generates
documents that sound like Krupp, not like generic AI output.
"""

class KnowledgeBase:
    def load_all(self) -> dict[str, str]: ...        # {filename: content}
    def load_file(self, name: str) -> str | None: ...  # Load specific file
    def get_system_context(self) -> str: ...           # Combined context for prompts
```

Create starter knowledge files with placeholder content that Krupp can customize:
- `knowledge/company_profile.md` — Placeholder company bio
- `knowledge/writing_standards.md` — Professional construction writing rules
- `knowledge/safety_standards.md` — OSHA compliance notes
- `knowledge/team_bios.md` — Template for team member bios

**Test requirements for knowledge base:**
- `test_load_all_files` — Returns dict with all .md files from knowledge dir
- `test_missing_directory` — Returns empty dict, doesn't crash
- `test_system_context_assembly` — Combines files into single formatted string
- `test_load_specific_file` — Returns content of named file, None if missing

---

## Step 8: BaseSkill Abstract Class (`kruppai/skills/base.py`)

Build the abstract base class that every skill must inherit:

```python
"""
Abstract base class for all KruppAI skills.

Every skill implements three methods:
1. validate_input() — Parse and validate user input
2. build_prompt() — Assemble the Claude API messages array
3. format_output() — Transform Claude's response into a document

The base class provides execute() which orchestrates the full lifecycle:
validate → load context → build prompt → call API → format → persist → return

Skills MUST NOT call the API directly. The base class handles retry logic,
cost tracking, and usage logging uniformly.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

@dataclass
class SkillResult:
    output_path: Path
    cost_cents: int
    input_tokens: int
    output_tokens: int
    model: str
    duration_ms: int
    skill_name: str
    project_code: str | None = None

class BaseSkill(ABC):
    # Subclass must set these
    skill_name: str
    display_name: str
    description: str
    phase: int
    default_model: str          # "sonnet" or "opus"
    output_formats: list[str]   # ["docx"], ["docx", "xlsx"], etc.

    def __init__(self, settings, db, api_client, formatter, context_manager, knowledge_base): ...

    @abstractmethod
    def validate_input(self, **kwargs) -> dict: ...

    @abstractmethod
    def build_prompt(self, validated: dict, context) -> list[dict]: ...

    @abstractmethod
    def format_output(self, response: str, context, validated: dict) -> Path: ...

    def execute(self, **kwargs) -> SkillResult:
        """Full skill lifecycle — do not override."""
        # 1. Validate
        validated = self.validate_input(**kwargs)
        # 2. Load context
        context = self.context_manager.load(validated.get("project_id")) if validated.get("project_id") else None
        # 3. Build prompt
        messages = self.build_prompt(validated, context)
        # 4. Call API
        response = self.api_client.call(
            messages=messages,
            skill_name=self.skill_name,
            project_id=validated.get("project_id"),
        )
        # 5. Format output
        output_path = self.format_output(response.content, context, validated)
        # 6. Persist
        self._persist(validated, response, output_path)
        # 7. Return
        return SkillResult(
            output_path=output_path,
            cost_cents=response.cost_cents,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            model=response.model,
            duration_ms=response.duration_ms,
            skill_name=self.skill_name,
            project_code=context.project["project_code"] if context else None,
        )

    def _persist(self, validated, response, output_path): ...
```

**Test requirements for BaseSkill:**
- `test_execute_lifecycle_order` — Mock skill confirms validate→prompt→api→format→persist order
- `test_execute_returns_skill_result` — Result has all fields populated
- `test_execute_logs_to_generated_documents` — DB has record after execution
- `test_execute_without_project` — Skills that don't require project_id still work
- `test_validation_error_stops_execution` — Bad input raises before API is called

---

## Step 9: CLI Skeleton (`kruppai/cli/main.py`)

Build the Click CLI entry point:

```python
"""
KruppAI CLI — main entry point.

Usage:
    kruppai --help                    Show all commands
    kruppai daily-report [OPTIONS]    Generate a daily field report
    kruppai rfi [OPTIONS]             Generate an RFI
    kruppai project list              List all projects
    kruppai project add               Add a new project
    kruppai status                    Show API usage, costs, recent docs
    kruppai init                      Initialize database and directories

The CLI uses Rich for all output — tables, progress bars, status messages.
"""

import click
from rich.console import Console
from rich.table import Table

console = Console()

@click.group()
@click.version_option(version="0.1.0")
@click.pass_context
def cli(ctx):
    """KruppAI — Construction AI Toolkit"""
    ctx.ensure_object(dict)
    # Load settings, init DB, create shared instances
    ...

@cli.command()
def init():
    """Initialize KruppAI database and directories."""
    ...

@cli.group()
def project():
    """Manage projects."""
    ...

@project.command("list")
def project_list():
    """List all projects."""
    ...

@project.command("add")
def project_add():
    """Add a new project interactively."""
    ...

@cli.command()
def status():
    """Show system status — API usage, costs, recent documents."""
    ...
```

**Test requirements for CLI:**
- `test_cli_help` — `kruppai --help` exits 0, shows command list
- `test_init_command` — `kruppai init` creates database and directories
- `test_project_list_empty` — Shows "No projects found" message
- `test_project_add` — Interactive add creates project in DB
- `test_status_shows_usage` — Displays API cost summary table

---

## Step 10: Test Fixtures & Conftest (`tests/conftest.py`)

Build shared test fixtures that every test module uses:

```python
"""
Shared test fixtures for KruppAI test suite.

Key fixtures:
- tmp_settings: Settings pointing to temp directories (auto-cleanup)
- test_db: Initialized SQLite database in temp directory
- seeded_db: Database pre-loaded with realistic construction project data
- mock_api_client: API client that returns canned responses without network calls
- sample_project: A realistic Krupp project record for testing
- sample_pdf / sample_docx / sample_xlsx: Minimal test documents
"""

@pytest.fixture
def tmp_settings(tmp_path):
    """Settings with all paths in temp directory."""
    ...

@pytest.fixture
def test_db(tmp_settings):
    """Empty initialized database."""
    ...

@pytest.fixture
def seeded_db(test_db):
    """Database with sample project, team, and subcontractor data."""
    # Insert: 1 company, 3 team members, 1 project, 2 subs, 5 action items
    ...

@pytest.fixture
def mock_api_client():
    """API client that returns predictable responses."""
    ...

@pytest.fixture
def sample_project():
    """Realistic construction project dict."""
    return {
        "project_code": "KRUPP-2026-TEST",
        "name": "City Center Medical Office Building",
        "client_name": "Regional Health Partners",
        "project_type": "healthcare",
        "original_contract_cents": 1_250_000_000,  # $12.5M
        "status": "active",
        ...
    }
```

**Seed data should be realistic construction industry data**, not lorem ipsum:
- Company: Krupp General Contractors, based in [City], [State]
- Project: A healthcare facility, $12.5M, 45,000 SF, active construction
- Team: Project Manager (Sarah Chen), Superintendent (Mike Rodriguez), Project Engineer (James Park)
- Subcontractors: ABC Electrical ($1.2M), Pacific Mechanical ($1.8M)
- Action items: Realistic construction tasks (RFI follow-up, submittal review, schedule update)

---

## Verification Checklist

After building all components, verify:

1. `pip install -e ".[dev]"` — Installs without error
2. `kruppai --help` — Shows all commands with descriptions
3. `kruppai init` — Creates `~/.kruppai/kruppai.db` and `~/KruppAI-Output/`
4. `pytest tests/ -v` — All tests pass (skip integration tests without API key)
5. `pytest tests/ -v --cov=kruppai --cov-report=term-missing` — Coverage report shows >80% on core/
6. `black --check kruppai/ tests/` — Code formatted correctly
7. `isort --check kruppai/ tests/` — Imports sorted correctly

---

## File Checklist

After this prompt, the following files should exist:
```
kruppai/
├── __init__.py
├── cli/
│   ├── __init__.py
│   └── main.py
├── core/
│   ├── __init__.py
│   ├── config.py
│   ├── database.py
│   ├── api_client.py
│   ├── document_parser.py
│   ├── output_formatter.py
│   ├── context_manager.py
│   └── knowledge_base.py
├── skills/
│   ├── __init__.py
│   └── base.py
├── knowledge/
│   ├── company_profile.md
│   ├── writing_standards.md
│   ├── safety_standards.md
│   └── team_bios.md
tests/
├── conftest.py
├── test_core/
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_database.py
│   ├── test_api_client.py
│   ├── test_document_parser.py
│   ├── test_output_formatter.py
│   ├── test_context_manager.py
│   └── test_knowledge_base.py
├── test_skills/
│   ├── __init__.py
│   └── test_base_skill.py
└── test_cli/
    ├── __init__.py
    └── test_main.py
pyproject.toml
schema/init.sql
.env.example
```
