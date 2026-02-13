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

### Step 6: Run Tests to Verify (1 minute)

```bash
pytest tests/ -v -m "not integration"
```

All tests should pass. Integration tests (marked `@pytest.mark.integration`) require a real API key and hit the Anthropic API — run them selectively:

```bash
pytest tests/ -v -m "integration" -k "test_daily_report"
```

### You're Done

You now have a working prototype with 6 Phase 1 skills:

| Command | What It Does |
|---|---|
| `kruppai daily-report` | Rough field notes → Professional daily report (DOCX) |
| `kruppai rfi` | Design question → Formal RFI document (DOCX) |
| `kruppai minutes` | Meeting notes → Formatted minutes with action tracking (DOCX) |
| `kruppai client-update` | PM notes → Client letter on letterhead (DOCX) |
| `kruppai safety-talk` | Topic → 5-10 minute safety talk with sign-in sheet (DOCX) |
| `kruppai punch-list` | Walk-through notes → Organized punch list (DOCX + XLSX) |

---

## Part B: Team Rollout Guide

### Preparing for Multiple Users (Single Office)

Since the prototype uses SQLite (a local file), each user gets their own database. For a small team (2-5 users), this is actually fine — each PM manages their own projects.

**Per-user setup:**
1. Install Python 3.11+ on each machine
2. Clone the repo
3. `pip install -e .`
4. Copy the shared `.env` file (same API key for the firm)
5. `kruppai init`
6. Each user adds their own projects

**Shared configuration files:**
- `knowledge/company_profile.md` — Same for everyone (keep in git)
- `knowledge/team_bios.md` — Same for everyone (keep in git)
- `knowledge/writing_standards.md` — Same for everyone (keep in git)
- `.env` — Shared Anthropic API key, individual paths

### Customizing the Knowledge Base

Before rolling out to the team, customize these files with real Krupp data:

**`knowledge/company_profile.md`:**
```markdown
# Krupp General Contractors

## Company Overview
Krupp General Contractors is a [full-service / specialty] general contractor
based in [City, State], founded in [year]. We specialize in [project types].

## Capabilities
- [List core capabilities]
- [Annual revenue range]
- [Bonding capacity]

## Differentiators
- [What makes Krupp different from competitors]
- [Awards, certifications, unique capabilities]
```

**`knowledge/team_bios.md`:**
```markdown
# Krupp Team

## [Name], [Title]
[Professional bio — 2-3 paragraphs covering experience, certifications,
notable projects. This text is used verbatim in proposals.]

## [Name], [Title]
[Bio]
```

**`knowledge/writing_standards.md`:**
```markdown
# Krupp Writing Standards

## Tone
- Professional and confident
- Client communications: warm but formal
- Internal documents: direct and clear
- Never use: [words/phrases Krupp avoids]

## Terminology
- Use "owner" not "client" in contractual documents
- Use "GC" or "Krupp" not "us" or "we" in formal documents
- [Industry-specific terminology preferences]
```

### Training the Team

**For Superintendents (Daily Reports, Safety Talks):**
1. Show them these two commands:
   - `kruppai daily-report -p PROJECT-CODE -n "your notes here"`
   - `kruppai safety-talk -t "topic"`
2. Show them one generated document side-by-side with what they write manually
3. That's it. No further training needed.

**For Project Managers (All Phase 1 Skills):**
1. Walk through each of the 6 commands with their actual project data
2. Show the `kruppai status` command for cost tracking
3. Demonstrate the action item carry-forward in meeting minutes
4. Show how the client update letter uses their project's real data

**Quick Reference Card** (print and laminate for job trailers):
```
KRUPPAI QUICK REFERENCE
========================
Daily Report:  kruppai daily-report -p [CODE] -n "[notes]"
RFI:           kruppai rfi -p [CODE] -i "[issue description]"
Minutes:       kruppai minutes -p [CODE] -t oac -n "[notes]"
Client Update: kruppai client-update -p [CODE] -n "[notes]"
Safety Talk:   kruppai safety-talk -t "[topic]"
Punch List:    kruppai punch-list -p [CODE] -n "[observations]"
Project List:  kruppai project list
System Status: kruppai status
Help:          kruppai --help
```

---

## Part C: Production Deployment Guide

### When to Go Production

Migrate from prototype to production when:
- [x] More than 2 users need simultaneous access
- [x] Web UI is needed (not everyone wants a CLI)
- [x] Centralized data needed across office
- [x] Backup/recovery beyond manual file copies needed

### Step 1: Supabase Setup (30 minutes)

1. Create account at https://supabase.com
2. Create new project: "KruppAI"
3. Note your project URL and API keys
4. Go to SQL Editor, paste and run `schema/init.sql` (PostgreSQL compatible)
5. Enable Row Level Security on all tables
6. Create auth users for each team member

### Step 2: Migrate Existing Data (15 minutes)

```bash
kruppai migrate --from sqlite --to supabase \
  --supabase-url "https://xxxxx.supabase.co" \
  --supabase-key "your-service-role-key"
```

This exports all data from local SQLite and imports into Supabase. Verify:
```bash
kruppai migrate --verify
```

### Step 3: Update Configuration

```env
# .env (production)
ANTHROPIC_API_KEY=sk-ant-api03-...
KRUPPAI_DB_BACKEND=supabase
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=eyJ...
KRUPPAI_ENVIRONMENT=production
SENTRY_DSN=https://xxxx@sentry.io/xxxx  # Optional but recommended
```

### Step 4: Web UI Deployment (Optional)

**Backend (Railway):**
```bash
# Install Railway CLI
npm i -g @railway/cli
railway init
railway up
```

**Frontend (Vercel):**
```bash
cd web-ui
vercel deploy --prod
```

### Step 5: Docker Deployment (Alternative)

```bash
docker build -t kruppai .
docker run -p 8000:8000 --env-file .env kruppai
```

### Step 6: Monitoring Setup

1. **Sentry**: Create project, add DSN to .env
2. **Cost alerts**: Set `KRUPPAI_DAILY_COST_LIMIT_CENTS=5000` ($50/day)
3. **Database backups**: Supabase handles automatically (daily for Pro plan)
4. **Log retention**: Application logs via standard Python logging → file or cloud logging service

### Step 7: Security Hardening

- [ ] Anthropic API key: Use organization-level key with usage limits
- [ ] Supabase: Row Level Security enabled on all tables
- [ ] Auth: Email + password minimum; Microsoft SSO recommended if using M365
- [ ] Network: Backend API behind HTTPS only
- [ ] File access: Output directory permissions restricted
- [ ] Zero data retention: Add `anthropic-beta: zero-data-retention` header in API client
- [ ] Secrets: Never in git. Use environment variables or secrets manager.

### Step 8: Verify Production

```bash
# Run full test suite against production database (read-only tests)
pytest tests/ -v -m "not integration" --tb=short

# Smoke test: generate a document
kruppai daily-report -p KRUPP-2026-001 -n "Production smoke test - 10 workers on site, concrete pour complete."

# Check API usage
kruppai status

# Check health endpoint (if web UI deployed)
curl https://your-api.railway.app/api/v1/health
```

---

## Appendix: Environment Variables Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | **Yes** | — | Anthropic API key |
| `KRUPPAI_DB_PATH` | No | `~/.kruppai/kruppai.db` | SQLite database path |
| `KRUPPAI_DB_BACKEND` | No | `sqlite` | `sqlite` or `supabase` |
| `KRUPPAI_OUTPUT_DIR` | No | `~/KruppAI-Output` | Document output directory |
| `KRUPPAI_DEFAULT_MODEL` | No | `claude-sonnet-4-5-20250929` | Default AI model |
| `KRUPPAI_LOG_LEVEL` | No | `INFO` | Logging level |
| `KRUPPAI_DAILY_COST_LIMIT_CENTS` | No | `5000` | Daily API cost cap ($50) |
| `KRUPPAI_MONTHLY_COST_LIMIT_CENTS` | No | `30000` | Monthly API cost cap ($300) |
| `KRUPPAI_WEATHER_ENABLED` | No | `true` | Auto-fetch weather for daily reports |
| `SUPABASE_URL` | Production | — | Supabase project URL |
| `SUPABASE_KEY` | Production | — | Supabase API key |
| `SENTRY_DSN` | No | — | Sentry error tracking DSN |
| `PROCORE_CLIENT_ID` | No | — | Procore OAuth client ID |
| `PROCORE_CLIENT_SECRET` | No | — | Procore OAuth client secret |
| `PROCORE_COMPANY_ID` | No | — | Procore company ID |
