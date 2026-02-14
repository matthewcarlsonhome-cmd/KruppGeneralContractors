# KruppAI — Construction AI Toolkit

## Project Identity
KruppAI is a modular AI document generation and analysis toolkit for Krupp General Contractors. It transforms rough field notes, PDFs, and spreadsheets into professional construction documents using the Anthropic Claude API. Available as both a CLI tool and a web application.

## Architecture Rules (Non-Negotiable)

### Language & Runtime
- **Python 3.11+** — all code, no exceptions
- **Type hints on every function** — `def generate_report(notes: str, project_id: int) -> Path:`
- **Pydantic v2 for all data models** — input validation, serialization, config
- **Click for CLI** — composable commands, automatic help text
- **Rich for terminal output** — tables, progress bars, status indicators
- **FastAPI for web backend** — serves both REST API and static frontend

### Project Layout
```
kruppai/
├── __init__.py
├── api/                     # FastAPI web backend + static frontend
│   ├── __init__.py
│   ├── main.py              # FastAPI app, all REST endpoints
│   └── static/              # HTML/CSS/JS single-page application
│       ├── index.html
│       ├── style.css
│       └── app.js
├── cli/                     # Click CLI commands
│   ├── __init__.py
│   ├── main.py              # CLI entry point, all 18 skill commands
│   └── helpers.py           # Quick mode helpers (ensure_initialized, etc.)
├── core/                    # Shared framework components
│   ├── __init__.py
│   ├── config.py            # Settings via Pydantic BaseSettings + .env
│   ├── database.py          # SQLite/PostgreSQL connection manager
│   ├── api_client.py        # Anthropic API wrapper with retry, cost tracking
│   ├── document_parser.py   # PDF, DOCX, XLSX, image → text extraction
│   ├── output_formatter.py  # DOCX, XLSX generation with Krupp branding
│   ├── context_manager.py   # Load project/team/sub data for prompt assembly
│   ├── knowledge_base.py    # Company profile, standards, templates loader
│   ├── weather.py           # Open-Meteo weather API (free, no key needed)
│   ├── security.py          # Input sanitization, file path validation
│   ├── monitoring.py        # Health checks, cost tracking summaries
│   └── migrate_to_supabase.py  # SQLite → Supabase PostgreSQL migration
├── integrations/            # Third-party API stubs (implement when needed)
│   ├── __init__.py
│   ├── procore.py           # Procore REST API stub
│   ├── microsoft.py         # Microsoft Graph API stub
│   └── sage.py              # Sage 300 CRE ODBC stub
├── skills/                  # One module per skill, all inherit BaseSkill
│   ├── __init__.py
│   ├── base.py              # Abstract BaseSkill class
│   ├── daily_report.py      # #1 - Phase 1
│   ├── rfi_generator.py     # #2 - Phase 1
│   ├── meeting_minutes.py   # #3 - Phase 1
│   ├── client_update.py     # #4 - Phase 1
│   ├── safety_talk.py       # #5 - Phase 1
│   ├── punch_list.py        # #6 - Phase 1
│   ├── estimate_reviewer.py # #7 - Phase 2 (Opus)
│   ├── bid_comparison.py    # #8 - Phase 2
│   ├── change_order.py      # #9 - Phase 2
│   ├── schedule_variance.py # #10 - Phase 2
│   ├── submittal_tracker.py # #11 - Phase 2
│   ├── contract_checker.py  # #12 - Phase 2 (Opus)
│   ├── proposal_generator.py # #13 - Phase 3 (Opus)
│   ├── budget_forecaster.py # #14 - Phase 3
│   ├── closeout_assembler.py # #15 - Phase 3
│   ├── lessons_learned.py   # #16 - Phase 3
│   ├── case_study.py        # #17 - Phase 3
│   └── incident_report.py   # #18 - Phase 3
├── knowledge/               # Company-specific knowledge base files
├── templates/               # DOCX/XLSX template files
├── schema/
│   ├── init.sql             # SQLite schema
│   └── postgres_init.sql    # PostgreSQL schema (for Supabase)
└── tests/
```

### BaseSkill Contract
Every skill MUST inherit from `BaseSkill` and implement this lifecycle:
```python
class BaseSkill(ABC):
    skill_name: str           # Unique identifier (e.g., "daily_report")
    display_name: str         # Human name (e.g., "Daily Field Report")
    description: str          # One-line description
    phase: int                # 1, 2, or 3
    default_model: str        # "sonnet" or "opus"
    output_formats: list[str] # ["docx"], ["docx", "xlsx"], etc.

    @abstractmethod
    def validate_input(self, **kwargs) -> dict: ...

    @abstractmethod
    def build_prompt(self, validated: dict, context: ProjectContext) -> list[dict]: ...

    @abstractmethod
    def format_output(self, response: str, context: ProjectContext, validated: dict) -> Path: ...
```

### API Client Rules
- **Default model: `claude-sonnet-4-5-20250929`** for all Phase 1 skills and speed-critical tasks
- **Opus model: `claude-opus-4-6`** only for: contract review, proposal generation, estimate analysis
- **Retry logic**: 3 retries with exponential backoff (2s, 4s, 8s) on 429/500/503
- **Every call logged** to `api_usage` table
- **Token estimation before call** — warn user if estimated cost > $0.50

### Database Rules
- **SQLite for prototype** — single file at `~/.kruppai/kruppai.db`
- **PostgreSQL for production** — Supabase with `schema/postgres_init.sql`
- **Use parameterized queries only** — never string interpolation for SQL
- **Connection via context manager**: `with get_db(settings) as conn:`

### Output Formatting Rules
- **Every DOCX output** uses Krupp branding: logo, colors (#1B3A5C navy, #D4A84B gold), Calibri font
- **File naming convention**: `{skill}_{project_code}_{date}_{sequence}.{ext}`
- **All documents include footer**: "Generated by KruppAI | {date} | Review required before distribution"

### Deployment
- **Render** — Primary deployment target (render.yaml blueprint for one-click deploy)
- **Supabase** — Production PostgreSQL database (when multi-user needed)
- **Docker** — Dockerfile included for containerized deployment

## Development Session Notes (Feb 14, 2026)

### Roadblocks Encountered & Solutions
1. **estimate_reviewer.py was never committed** — The test file existed but the skill file was lost between sessions. Solution: Read the test file to reverse-engineer the expected interface, rebuild the skill to match.
2. **Phase 3 skills lost between sessions** — Context compaction caused uncommitted work to be lost. Lesson: Commit and push after completing each phase, don't batch multiple phases.
3. **Background agent test files failed to write** — "File has not been read yet" errors when Write tool was used for files that partially existed from a running agent. Solution: Let background agents complete before attempting to write the same files.
4. **Value_proc for expanded CLI menu** — When SKILL_MENU grew beyond 9 items, `value_proc=int` was needed for the choice prompt to handle two-digit numbers.

### Optimization Thoughts
1. **Skill file sizes** — Phase 3 skills are 17-26KB each. The prompt building section is the largest part. Consider extracting common prompt patterns into a shared prompt builder utility.
2. **Test fixtures** — The conftest.py seeded_db fixture creates a fresh database per test. For integration tests, consider a session-scoped fixture to reduce overhead.
3. **Model routing** — Currently hard-coded in OPUS_SKILLS set. Consider making this configurable per-deployment so Krupp can adjust cost/quality tradeoffs.
4. **Document branding** — The OutputFormatter creates a fresh DOCX from scratch each time. A template-based approach (loading a .docx template) would be more maintainable for complex branding.
5. **Weather API** — fetch_weather_sync uses httpx synchronously. For web API deployment, use the async version to avoid blocking the event loop.
6. **Frontend SPA** — Using vanilla HTML/CSS/JS avoids build tool complexity. If the UI grows significantly, consider migrating to React/Svelte with a proper build step.

### Key Patterns for Future Development
- **Adding a new skill**: Create skill file in `skills/`, add CLI command in `cli/main.py`, add quick mode handler, add test file, add to SKILL_MAP in `api/main.py`
- **Adding an integration**: Create module in `integrations/`, add env vars to config.py and .env.example
- **Database changes**: Add migration SQL file in `schema/`, update both init.sql and postgres_init.sql
