# Prompt 05: Integration, Deployment & Production Architecture
## Third-Party Integrations, Database Migration, Web UI, Security, and Monitoring

> **Target**: Reference architecture and build instructions for production deployment.
> **Scope**: This document is a roadmap — components are built incrementally as Krupp's needs grow.
> **Prerequisites**: All 18 skills operational on local CLI prototype.

---

## Part 1: Third-Party Integrations

### 1.1 Open-Meteo Weather API (Free — Implement Day 1)

Already referenced in Skill #1 (Daily Report). Build as a standalone utility in `kruppai/core/weather.py`:

```python
"""
Weather data provider using Open-Meteo API.
Free, no API key required, no rate limiting concerns at our scale.

API docs: https://open-meteo.com/en/docs
Endpoint: https://api.open-meteo.com/v1/forecast

Provides:
- Historical weather by date + GPS coordinates
- Forecast weather for upcoming days
- Temperature, precipitation, wind speed, conditions

Integration:
- Daily Report skill auto-populates weather when project has lat/lng
- Falls back gracefully to manual entry if API unavailable
"""

import httpx
from dataclasses import dataclass

@dataclass
class WeatherData:
    high_f: float | None
    low_f: float | None
    conditions: str
    precipitation_in: float | None
    wind_mph: float | None
    source: str  # 'open_meteo' or 'manual'

async def fetch_weather(lat: float, lng: float, date: str) -> WeatherData:
    """Fetch weather for a specific date and location."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lng,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max,weather_code",
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "timezone": "auto",
        "start_date": date,
        "end_date": date,
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            daily = data["daily"]
            return WeatherData(
                high_f=daily["temperature_2m_max"][0],
                low_f=daily["temperature_2m_min"][0],
                conditions=_weather_code_to_text(daily["weather_code"][0]),
                precipitation_in=daily["precipitation_sum"][0],
                wind_mph=daily["wind_speed_10m_max"][0],
                source="open_meteo",
            )
    except Exception:
        return WeatherData(None, None, "", None, None, "manual")

def _weather_code_to_text(code: int) -> str:
    """Convert WMO weather code to human-readable text."""
    codes = {
        0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Fog", 48: "Depositing rime fog",
        51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
        61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
        71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
        80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
        95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail",
    }
    return codes.get(code, f"Weather code {code}")
```

**Tests:**
- `test_fetch_weather_success` — Mock successful API response, verify WeatherData populated
- `test_fetch_weather_api_failure` — Mock timeout, verify returns manual fallback
- `test_weather_code_mapping` — Known codes map to expected text

### 1.2 Procore API Integration (Optional — Week 8+)

Build as `kruppai/integrations/procore.py`:

```python
"""
Procore API integration for pulling project data directly.
Requires: Procore account with API access, OAuth2 credentials.

Procore REST API v1.1: https://developers.procore.com/reference

What we pull:
- Projects: Sync project list with local database
- Daily Logs: Import daily log data as starting point for daily reports
- RFIs: Sync RFI log for numbering continuity
- Submittals: Import submittal log for Skill #11
- Change Events/Orders: Sync CO data for Skill #9
- Directory: Import team members and subcontractors

Authentication: OAuth2 with refresh tokens
Rate Limiting: 3600 requests/hour (more than sufficient)
"""

class ProcoreClient:
    def __init__(self, client_id: str, client_secret: str, company_id: int): ...
    def sync_projects(self) -> list[dict]: ...
    def sync_rfis(self, project_id: int) -> list[dict]: ...
    def sync_submittals(self, project_id: int) -> list[dict]: ...
    def pull_daily_log(self, project_id: int, date: str) -> dict: ...
    def sync_directory(self, project_id: int) -> dict: ...
```

**CLI commands:**
```
kruppai procore sync --all                  # Sync everything
kruppai procore sync --projects             # Just projects
kruppai procore sync --project KRUPP-2026-003 --rfis --submittals
```

**Environment variables:**
```
PROCORE_CLIENT_ID=...
PROCORE_CLIENT_SECRET=...
PROCORE_COMPANY_ID=...
```

### 1.3 Microsoft Graph Integration (Optional — Week 10+)

Build as `kruppai/integrations/microsoft.py`:

```python
"""
Microsoft Graph API for SharePoint document storage and Outlook email.

What it enables:
- Auto-save generated documents to project SharePoint folder
- Email client updates directly from the CLI
- Pull project documents from SharePoint for analysis

Authentication: Azure AD app registration, MSAL library
"""

class MicrosoftGraphClient:
    def upload_to_sharepoint(self, file_path: Path, site_name: str, folder_path: str) -> str: ...
    def send_email(self, to: list[str], subject: str, body: str, attachments: list[Path]) -> bool: ...
    def list_sharepoint_files(self, site_name: str, folder_path: str) -> list[dict]: ...
```

**CLI commands:**
```
kruppai share --file daily_report_KRUPP-2026-003_2026-02-13_001.docx --to sharepoint
kruppai share --file client_update_KRUPP-2026-003_2026-02-13_001.docx --email owner@client.com
```

### 1.4 Sage 300 CRE Integration (Optional — Week 10+)

Build as `kruppai/integrations/sage.py`:

```python
"""
Sage 300 CRE ODBC integration for direct accounting data access.

What it enables:
- Pull job cost reports directly (feeds Budget Forecaster, Skill #14)
- Pull subcontractor payment history
- Pull committed cost data for project financials

Connection: ODBC via pyodbc
Requires: Sage 300 CRE with ODBC driver installed, read-only DB user
"""

class SageClient:
    def get_job_cost_report(self, job_number: str) -> pd.DataFrame: ...
    def get_subcontractor_payments(self, job_number: str) -> pd.DataFrame: ...
    def get_committed_costs(self, job_number: str) -> pd.DataFrame: ...
```

---

## Part 2: SQLite → Supabase PostgreSQL Migration

### When to Migrate
Migrate when ANY of these conditions are met:
- Multiple users need simultaneous access (>1 PM using the system)
- Web UI is being deployed
- Data needs to be accessible from multiple machines
- Backup/recovery beyond file copies is needed

### Migration Script

Build as `kruppai/core/migrate_to_supabase.py`:

```python
"""
One-time migration from SQLite to Supabase PostgreSQL.

Steps:
1. Create Supabase project (manual — done via dashboard)
2. Run PostgreSQL version of schema/init.sql
3. Export all SQLite data as INSERT statements
4. Execute INSERTs against Supabase
5. Verify row counts match
6. Update .env to point to Supabase
7. Run integration tests against new database

Schema changes for PostgreSQL:
- INTEGER PRIMARY KEY → SERIAL PRIMARY KEY
- TEXT dates → TIMESTAMPTZ (optional, TEXT still works)
- strftime() → to_char() or NOW()
- PRAGMA foreign_keys → always enforced in PostgreSQL
"""

def migrate(sqlite_path: Path, supabase_url: str, supabase_key: str) -> MigrationResult:
    """Execute full migration with verification."""
    ...
```

### Supabase Configuration

```
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=eyJ...  # anon key for client, service_role key for admin
SUPABASE_DB_URL=postgresql://postgres:password@db.xxxxx.supabase.co:5432/postgres
```

### Row Level Security (Multi-User)
```sql
-- Enable RLS on all tables
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see projects they're assigned to
CREATE POLICY "Users see their projects" ON projects
    FOR SELECT USING (
        id IN (
            SELECT project_id FROM project_team
            WHERE team_member_id = auth.uid()
        )
    );

-- Admin policy: Admins and executives see everything
CREATE POLICY "Admins see all" ON projects
    FOR ALL USING (
        (SELECT role FROM team_members WHERE id = auth.uid()) IN ('admin', 'executive')
    );
```

---

## Part 3: Web UI Architecture (Future Phase)

### Technology Stack
- **Backend**: FastAPI (Python) — reuses all existing skill modules
- **Frontend**: React + Tailwind CSS (or Next.js for SSR)
- **Hosting**: Vercel (frontend) + Railway (backend) or single Railway deployment
- **Auth**: Supabase Auth (email/password, or Microsoft SSO)

### API Design
```python
# kruppai/api/main.py
from fastapi import FastAPI, Depends
from fastapi.security import HTTPBearer

app = FastAPI(title="KruppAI API", version="1.0")

@app.post("/api/v1/skills/{skill_name}/execute")
async def execute_skill(skill_name: str, request: SkillRequest, user = Depends(get_current_user)):
    """Execute any skill via API — same interface as CLI."""
    ...

@app.get("/api/v1/projects")
async def list_projects(user = Depends(get_current_user)):
    ...

@app.get("/api/v1/projects/{project_id}/documents")
async def list_documents(project_id: int, user = Depends(get_current_user)):
    ...

@app.get("/api/v1/status/usage")
async def api_usage(user = Depends(get_current_user)):
    """Dashboard data: costs, usage by skill, recent documents."""
    ...
```

### Key Web UI Pages
1. **Dashboard**: Active projects, recent documents, API usage, cost tracker
2. **Project View**: All data for one project — team, subs, documents, financials
3. **Skill Launcher**: Select skill, fill inputs, generate → download document
4. **Document Library**: Search/filter all generated documents
5. **Admin**: Team management, settings, API keys, cost limits

---

## Part 4: Security Architecture

### Data Security
- **API keys**: Stored in `.env`, never committed to git. `.gitignore` enforced.
- **Anthropic data policy**: API data not used for training. Enable zero-data-retention header for maximum security.
- **Local data**: SQLite file permissions restricted to user. Output directory permissions checked.
- **Supabase**: Row Level Security enforced. Service role key used only server-side.

### Application Security
```python
# kruppai/core/security.py

def sanitize_input(text: str) -> str:
    """Remove potential prompt injection patterns from user input."""
    # Strip system prompt override attempts
    # Limit input length
    # Log suspicious patterns
    ...

def validate_file_path(path: Path, allowed_extensions: list[str]) -> Path:
    """Prevent path traversal and restrict to allowed file types."""
    resolved = path.resolve()
    if not resolved.suffix.lower() in allowed_extensions:
        raise ValueError(f"File type {resolved.suffix} not allowed")
    return resolved
```

### Audit Trail
Every action is logged:
- `api_usage` table: Every AI call with cost and tokens
- `generated_documents` table: Every document produced with inputs
- Application logs: Errors, warnings, user actions

---

## Part 5: Monitoring & Observability

### Cost Monitoring Dashboard
```python
# Built into CLI: kruppai status
# Shows:
# - Today's API spend vs. daily limit
# - This month's spend vs. monthly limit
# - Cost by skill (which skills cost the most?)
# - Average cost per document type
# - Trend: increasing or decreasing usage
```

### Sentry Integration (Production)
```python
# kruppai/core/monitoring.py
import sentry_sdk

def init_monitoring(settings: Settings):
    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            traces_sample_rate=0.1,
            environment=settings.environment,
        )
```

### Health Check
```python
@app.get("/api/v1/health")
async def health():
    """Production health check endpoint."""
    return {
        "status": "healthy",
        "database": check_db_connection(),
        "anthropic_api": check_api_key_valid(),
        "disk_space": check_output_directory_space(),
        "version": "1.0.0",
    }
```

---

## Part 6: Deployment Procedures

### Local Development (Day 1)
```bash
git clone <repo>
cd kruppai
python -m venv venv && source venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # Add ANTHROPIC_API_KEY
kruppai init
pytest tests/ -v -m "not integration"
```

### Docker Deployment (Production)
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install .
COPY kruppai/ kruppai/
COPY schema/ schema/
COPY knowledge/ knowledge/
EXPOSE 8000
CMD ["uvicorn", "kruppai.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### CI/CD Pipeline (GitHub Actions)
```yaml
name: KruppAI CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -e ".[dev]"
      - run: black --check kruppai/ tests/
      - run: isort --check kruppai/ tests/
      - run: pytest tests/ -v -m "not integration" --cov=kruppai
```

---

## Testing Requirements for Integrations

```python
# tests/test_integrations/test_weather.py
class TestWeatherIntegration:
    def test_fetch_success(self, mock_httpx): ...
    def test_fetch_timeout_fallback(self, mock_httpx): ...
    def test_weather_code_mapping(self): ...

# tests/test_integrations/test_procore.py (all mocked)
class TestProcoreIntegration:
    def test_sync_projects(self, mock_procore_api): ...
    def test_sync_rfis(self, mock_procore_api): ...
    def test_oauth_refresh(self, mock_procore_api): ...

# tests/test_integrations/test_migration.py
class TestMigration:
    def test_sqlite_to_postgres_schema_compat(self): ...
    def test_data_export_import_roundtrip(self, seeded_db): ...
    def test_row_counts_match(self, seeded_db): ...

# tests/test_api/test_endpoints.py (for web UI API)
class TestAPIEndpoints:
    def test_health_check(self, test_client): ...
    def test_execute_skill_authenticated(self, test_client, auth_headers): ...
    def test_execute_skill_unauthenticated(self, test_client): ...
    def test_list_projects(self, test_client, auth_headers, seeded_db): ...
```
