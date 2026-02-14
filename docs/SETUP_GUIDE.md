# KruppAI Setup Guide

## Part A: Quick Start — Prototype in 30 Minutes

This gets a developer from zero to running the first skill on a local machine. No servers, no cloud accounts, no complicated setup.

### Prerequisites

| Requirement | Version | Check Command |
|---|---|---|
| Python | 3.11+ | `python3 --version` |
| pip | Latest | `pip --version` |
| Git | Any | `git --version` |
| Anthropic API Key | — | Get from https://console.anthropic.com/ |

### Step 1: Clone and Install (2 minutes)

```bash
git clone <repo-url> kruppai
cd kruppai
python3 -m venv venv
source venv/bin/activate    # Linux/Mac
# venv\Scripts\activate     # Windows

pip install -e ".[dev]"
```

### Step 2: Configure (1 minute)

```bash
cp .env.example .env
```

Edit `.env` and add your Anthropic API key:
```
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here
```

That's the only required configuration. Everything else has sensible defaults.

### Step 3: Initialize (30 seconds)

```bash
kruppai init
```

This creates:
- `~/.kruppai/kruppai.db` — SQLite database with full schema
- `~/KruppAI-Output/` — Where generated documents are saved

### Step 4: Add Your First Project (1 minute)

```bash
kruppai project add
```

Follow the interactive prompts:
- Project code: `KRUPP-2026-001`
- Name: `City Center Medical Office`
- Client: `Regional Health Partners`
- Address, lat/lng (for weather), dates, etc.

Or quick-add with flags:
```bash
kruppai project add --code KRUPP-2026-001 --name "City Center Medical Office" --client "Regional Health Partners" --type healthcare --status active
```

### Step 5: Generate Your First Document (30 seconds)

```bash
kruppai daily-report \
  --project KRUPP-2026-001 \
  --notes "Poured 3rd floor slab today, 85 yards. ABC Electric running conduit 2nd floor. 42 workers. Rain delay 2hrs morning."
```

Output: `~/KruppAI-Output/daily_report_KRUPP-2026-001_2026-02-13_001.docx`

Open it. You should see a professional daily report with Krupp branding, structured sections, and weather data auto-populated.

### Step 6: Launch the Web Interface

```bash
uvicorn kruppai.api.main:app --reload
```

Open http://localhost:8000 in your browser. You'll see the KruppAI dashboard with all 18 skills available in a clean, card-based interface. No CLI knowledge needed.

### Step 7: Run Tests to Verify (1 minute)

```bash
pytest tests/ -v -m "not integration"
```

All tests should pass. Integration tests (marked `@pytest.mark.integration`) require a real API key and hit the Anthropic API — run them selectively.

### You're Done

You now have a working prototype with all 18 skills across 3 phases:

**Phase 1 — Field & Communication**
| Command | What It Does |
|---|---|
| `kruppai daily-report` | Rough field notes → Professional daily report (DOCX) |
| `kruppai rfi` | Design question → Formal RFI document (DOCX) |
| `kruppai minutes` | Meeting notes → Formatted minutes with action tracking (DOCX) |
| `kruppai client-update` | PM notes → Client letter on letterhead (DOCX) |
| `kruppai safety-talk` | Topic → 5-10 minute safety talk with sign-in sheet (DOCX) |
| `kruppai punch-list` | Walk-through notes → Organized punch list (DOCX + XLSX) |

**Phase 2 — Analysis & Review**
| Command | What It Does |
|---|---|
| `kruppai estimate-review` | XLSX estimate → Benchmarked analysis report (DOCX + XLSX) |
| `kruppai bid-compare` | Multiple bid files → Side-by-side comparison (DOCX + XLSX) |
| `kruppai change-order` | Scope change → Formal CO proposal with cost breakdown (DOCX) |
| `kruppai schedule-analysis` | Schedule file → Variance and critical path analysis (DOCX + XLSX) |
| `kruppai submittal-status` | Submittal log → Status report with overdue flags (DOCX + XLSX) |
| `kruppai contract-review` | Contract/insurance → Compliance review with risk flags (DOCX) |

**Phase 3 — Strategic & Institutional**
| Command | What It Does |
|---|---|
| `kruppai proposal` | Opportunity notes → Professional project proposal (DOCX) |
| `kruppai budget-forecast` | Job cost report → Budget-to-actual variance analysis (DOCX + XLSX) |
| `kruppai closeout` | Closeout notes → Package checklist with cover letter (DOCX + XLSX) |
| `kruppai lessons-learned` | Session notes → Structured lessons learned report (DOCX) |
| `kruppai case-study` | Project highlights → Marketing case study (DOCX) |
| `kruppai incident-report` | Incident details → Formal report with OSHA assessment (DOCX) |

---

## Part B: Web Interface Guide

The web interface is the recommended way for non-technical team members to use KruppAI.

### Accessing the Web UI

**Local development:**
```bash
uvicorn kruppai.api.main:app --reload
# Open http://localhost:8000
```

**Production (Render):**
Access at your Render deployment URL (e.g., `https://kruppai.onrender.com`)

### Web UI Features

1. **Dashboard** — API cost tracking, recent documents, quick action buttons
2. **Skills** — 18 AI skills organized by phase, each with a simple input form
3. **Documents** — All generated documents with download links
4. **Projects** — Project list with status and "Add Project" form

### For Non-Technical Users

The web interface is designed for construction PMs who don't use command lines:
- Big, clearly labeled buttons
- Dropdown menus instead of typed inputs where possible
- File upload areas for drag-and-drop
- Progress spinners during AI generation
- One-click document download

---

## Part C: Production Deployment on Render

### One-Click Deploy (Recommended)

KruppAI includes a `render.yaml` Blueprint for one-click deployment.

1. **Push code to GitHub** (if not already done)
2. **Go to** https://dashboard.render.com
3. **Click** "New" → "Blueprint"
4. **Connect** your GitHub repo
5. **Set environment variables** in the Render dashboard:
   - `ANTHROPIC_API_KEY` = your Anthropic API key
6. **Click** "Apply" — Render builds and deploys automatically

The blueprint configures:
- Docker-based web service with health checks
- Persistent disk for SQLite database and generated documents
- All default environment variables

### Manual Render Setup

If you prefer manual configuration:

```bash
# Install Render CLI
pip install render-cli

# Deploy
render deploy
```

Or use Docker locally first:
```bash
docker build -t kruppai .
docker run -p 8000:8000 --env-file .env kruppai
```

### Supabase Setup (For Multi-User)

When you need multiple people using KruppAI simultaneously:

1. Create account at https://supabase.com
2. Create new project: "KruppAI"
3. Go to SQL Editor, paste and run `schema/postgres_init.sql`
4. Note your project URL and API keys
5. Set in Render environment:
   ```
   SUPABASE_URL=https://xxxxx.supabase.co
   SUPABASE_KEY=eyJ...
   SUPABASE_DB_URL=postgresql://postgres:password@db.xxxxx.supabase.co:5432/postgres
   ```
6. Run the migration script:
   ```bash
   python -m kruppai.core.migrate_to_supabase
   ```

---

## Part D: Team Rollout Guide

### Customizing the Knowledge Base

Before rolling out to the team, customize these files with real Krupp data:

**`knowledge/company_profile.md`** — Company bio, capabilities, differentiators
**`knowledge/team_bios.md`** — Professional bios for proposals
**`knowledge/writing_standards.md`** — Tone, terminology preferences
**`knowledge/safety_standards.md`** — Safety policies and standards

### Training the Team

**For Superintendents (Daily Reports, Safety Talks):**
1. Open the web interface
2. Click "Daily Report" or "Safety Talk"
3. Fill in the form, click "Generate"
4. Download the document

**For Project Managers (All Skills):**
1. Walk through the web interface with their actual project data
2. Demonstrate the Dashboard for cost tracking
3. Show how documents auto-populate with project context

---

## Appendix: Environment Variables Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | **Yes** | — | Anthropic API key |
| `KRUPPAI_DB_PATH` | No | `~/.kruppai/kruppai.db` | SQLite database path |
| `KRUPPAI_OUTPUT_DIR` | No | `~/KruppAI-Output` | Document output directory |
| `KRUPPAI_DEFAULT_MODEL` | No | `claude-sonnet-4-5-20250929` | Default AI model |
| `KRUPPAI_LOG_LEVEL` | No | `INFO` | Logging level |
| `KRUPPAI_DAILY_COST_LIMIT_CENTS` | No | `5000` | Daily API cost cap ($50) |
| `KRUPPAI_MONTHLY_COST_LIMIT_CENTS` | No | `30000` | Monthly API cost cap ($300) |
| `OPEN_METEO_ENABLED` | No | `true` | Auto-fetch weather for daily reports |
| `SUPABASE_URL` | Production | — | Supabase project URL |
| `SUPABASE_KEY` | Production | — | Supabase API key |
| `SUPABASE_DB_URL` | Production | — | PostgreSQL connection string |
| `SENTRY_DSN` | No | — | Sentry error tracking DSN |
