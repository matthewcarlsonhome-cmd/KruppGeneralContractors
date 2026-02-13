# KruppAI — Construction AI Toolkit

## Project Identity
KruppAI is a modular, CLI-first AI document generation and analysis toolkit for Krupp General Contractors. It transforms rough field notes, PDFs, and spreadsheets into professional construction documents using the Anthropic Claude API.

## Architecture Rules (Non-Negotiable)

### Language & Runtime
- **Python 3.11+** — all code, no exceptions
- **Type hints on every function** — `def generate_report(notes: str, project_id: int) -> Path:`
- **Pydantic v2 for all data models** — input validation, serialization, config
- **Click for CLI** — composable commands, automatic help text
- **Rich for terminal output** — tables, progress bars, status indicators

### Project Layout
```
kruppai/
├── __init__.py
├── cli/                    # Click CLI commands (one file per skill)
│   ├── __init__.py
│   └── main.py             # CLI entry point, group registration
├── core/                   # Shared framework components
│   ├── __init__.py
│   ├── config.py            # Settings via Pydantic BaseSettings + .env
│   ├── database.py          # SQLite/PostgreSQL connection manager
│   ├── api_client.py        # Anthropic API wrapper with retry, cost tracking
│   ├── document_parser.py   # PDF, DOCX, XLSX, image → text extraction
│   ├── output_formatter.py  # DOCX, XLSX, PDF generation with branding
│   ├── context_manager.py   # Load project/team/sub data for prompt assembly
│   └── knowledge_base.py    # Company profile, standards, templates loader
├── skills/                  # One module per skill, all inherit BaseSkill
│   ├── __init__.py
│   ├── base.py              # Abstract BaseSkill class
│   ├── daily_report.py
│   ├── rfi_generator.py
│   ├── meeting_minutes.py
│   ├── client_update.py
│   ├── safety_talk.py
│   ├── punch_list.py
│   ├── estimate_reviewer.py
│   ├── bid_comparison.py
│   ├── change_order.py
│   ├── schedule_variance.py
│   ├── submittal_tracker.py
│   ├── contract_checker.py
│   ├── proposal_generator.py
│   ├── budget_forecaster.py
│   ├── closeout_assembler.py
│   ├── lessons_learned.py
│   ├── case_study.py
│   └── incident_report.py
├── knowledge/               # Company-specific knowledge base files
│   ├── company_profile.md
│   ├── team_bios.md
│   ├── writing_standards.md
│   └── safety_standards.md
├── templates/               # DOCX/XLSX template files for output formatting
│   ├── krupp_letterhead.docx
│   ├── daily_report_template.docx
│   ├── rfi_template.docx
│   └── ...
├── schema/
│   └── init.sql             # Database schema (SQLite-compatible, Postgres-ready)
└── tests/
    ├── conftest.py
    ├── test_core/
    └── test_skills/
```

### BaseSkill Contract
Every skill MUST inherit from `BaseSkill` and implement this lifecycle:
```python
class BaseSkill(ABC):
    skill_name: str           # Unique identifier (e.g., "daily_report")
    display_name: str         # Human name (e.g., "Daily Field Report")
    description: str          # One-line description for CLI help
    phase: int                # 1, 2, or 3
    default_model: str        # "sonnet" or "opus"
    output_formats: list[str] # ["docx"], ["docx", "xlsx"], etc.

    @abstractmethod
    def validate_input(self, **kwargs) -> ValidatedInput: ...

    @abstractmethod
    def build_prompt(self, validated: ValidatedInput, context: ProjectContext) -> list[dict]: ...

    @abstractmethod
    def format_output(self, response: str, context: ProjectContext) -> Path: ...

    # Provided by base class (do not override):
    def execute(self, **kwargs) -> SkillResult:
        validated = self.validate_input(**kwargs)
        context = self.context_manager.load(validated.project_id)
        messages = self.build_prompt(validated, context)
        response = self.api_client.call(messages, model=self.default_model)
        output_path = self.format_output(response.content, context)
        self.persist(validated, response, output_path)
        return SkillResult(path=output_path, cost=response.cost, tokens=response.tokens)
```

### API Client Rules
- **Default model: `claude-sonnet-4-5-20250929`** for all Phase 1 skills and speed-critical tasks
- **Opus model: `claude-opus-4-6`** only for: contract review, proposal generation, estimate analysis
- **Retry logic**: 3 retries with exponential backoff (2s, 4s, 8s) on 429/500/503
- **Every call logged** to `api_usage` table: skill, model, input_tokens, output_tokens, cost, duration_ms, success
- **Token estimation before call** — warn user if estimated cost > $0.50 for a single operation
- **Streaming for long outputs** — show Rich progress indicator during generation

### Database Rules
- **SQLite for prototype** — single file at `~/.kruppai/kruppai.db`
- **All schema in `schema/init.sql`** — must be valid for both SQLite and PostgreSQL
- **Use parameterized queries only** — never string interpolation for SQL
- **Connection via context manager**: `with get_db() as conn:`
- **Migrations via numbered SQL files** when schema changes: `schema/002_add_column.sql`

### Output Formatting Rules
- **Every DOCX output** uses Krupp branding: logo, colors (#1B3A5C navy, #D4A84B gold), Calibri font
- **File naming convention**: `{skill}_{project_code}_{date}_{sequence}.{ext}`
  - Example: `daily_report_KRUPP-2024-003_2026-02-13_001.docx`
- **All documents include footer**: "Generated by KruppAI | {date} | Review required before distribution"
- **Tables must be properly formatted** — alternating row colors, headers bold, borders consistent

### Code Style
- **Black formatter**, 88 char line length
- **isort** for import ordering
- **No global state** — dependency injection via constructor
- **Docstrings on public methods** — Google style
- **Tests for every skill** — at minimum: valid input produces output, invalid input raises ValidationError

### Error Handling
- **Never crash silently** — all errors logged, user gets actionable message via Rich
- **API errors**: retry, then show cost-free "try again" message
- **File errors**: check permissions before write, suggest fix
- **Validation errors**: show exactly what's wrong, show expected format

### Environment Variables (.env)
```
ANTHROPIC_API_KEY=sk-ant-...
KRUPPAI_DB_PATH=~/.kruppai/kruppai.db
KRUPPAI_OUTPUT_DIR=~/KruppAI-Output
KRUPPAI_LOG_LEVEL=INFO
KRUPPAI_DEFAULT_MODEL=sonnet
OPEN_METEO_ENABLED=true
```
