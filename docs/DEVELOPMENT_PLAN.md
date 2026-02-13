# KruppAI Master Development Plan
## Construction AI Toolkit — Full Build Roadmap

**Version**: 1.0
**Date**: February 13, 2026
**Prepared by**: Matthew Carlson Consulting
**Prepared for**: Krupp General Contractors

---

## Executive Summary

This document is the master execution plan for building KruppAI — an 18-skill AI toolkit that transforms how Krupp's project managers and superintendents produce construction documents. The plan is organized around one principle: **deliver value fast, then expand**.

- **Day 1**: Working prototype with 6 skills that save PMs 16-25 hours/week
- **Week 4**: Hardened, refined system running on real projects
- **Week 8**: Document analysis skills for estimates, bids, contracts, schedules
- **Week 12**: Strategic skills for proposals, forecasting, closeout — plus automated workflows

Total investment: 35-45 development days. Monthly operating cost: $120-280 (prototype) to $170-430 (production). ROI: 11x-50x on operating costs from Phase 1 alone.

---

## Architecture Summary

```
┌─────────────────────────────────────────────────┐
│                CLI / Web UI                      │
│          (Click CLI → FastAPI future)            │
├─────────────────────────────────────────────────┤
│              18 SKILL MODULES                    │
│  Phase 1: Daily Report, RFI, Minutes,           │
│           Client Update, Safety Talk, Punch List │
│  Phase 2: Estimate Review, Bid Compare, CO,     │
│           Schedule, Submittals, Contracts        │
│  Phase 3: Proposals, Budget, Closeout,           │
│           Lessons, Case Studies, Incidents        │
├─────────────────────────────────────────────────┤
│            CORE FRAMEWORK                        │
│  Config │ Database │ API Client │ Doc Parser     │
│  Output Formatter │ Context Manager │ Knowledge  │
│  BaseSkill (abstract lifecycle)                  │
├─────────────────────────────────────────────────┤
│              DATA LAYER                          │
│  SQLite (prototype) → Supabase PostgreSQL (prod) │
│  20+ tables │ Views │ Full audit trail           │
├─────────────────────────────────────────────────┤
│           EXTERNAL SERVICES                      │
│  Anthropic Claude API │ Open-Meteo Weather       │
│  Procore (opt) │ MS Graph (opt) │ Sage (opt)     │
└─────────────────────────────────────────────────┘
```

---

## Technology Stack

| Layer | Technology | Cost |
|---|---|---|
| Language | Python 3.11+ | Free |
| AI Engine | Anthropic Claude API (Sonnet + Opus) | ~$150-300/mo |
| CLI | Click + Rich | Free |
| Word Docs | python-docx | Free |
| Excel | openpyxl | Free |
| PDF Parsing | PyMuPDF (fitz) | Free |
| Data Models | Pydantic v2 | Free |
| Database (proto) | SQLite | Free |
| Database (prod) | Supabase PostgreSQL | $25/mo |
| Weather | Open-Meteo API | Free |
| Testing | pytest + pytest-cov | Free |
| Formatting | Black + isort + ruff | Free |

---

## Database Design

20+ tables organized around the project lifecycle. Full schema in `schema/init.sql`.

**Core entities**: Company → Team Members → Projects → Subcontractors
**Skill tables**: Daily Reports, RFIs, Meetings, Action Items, Change Orders, Submittals, Punch Lists, Safety Talks, Proposals, Budget Forecasts, Closeout Packages, Lessons Learned, Case Studies, Incident Reports, Estimate Reviews, Bid Comparisons, Schedule Snapshots, Contract Reviews
**System tables**: API Usage, Generated Documents, Settings
**Views**: Active Projects (with stats), Open Action Items, API Cost Summary, Subcontractor Performance

---

## 18-Skill Inventory

### Phase 1: Day 1 Essentials (6 skills)

| # | Skill | Input | Output | Model | Time Saved |
|---|---|---|---|---|---|
| 1 | Daily Field Report | Rough notes | DOCX | Sonnet | 30-45 min/day |
| 2 | RFI Generator | Issue description | DOCX | Sonnet | 20-30 min/RFI |
| 3 | Meeting Minutes | Meeting notes | DOCX | Sonnet | 45-60 min/meeting |
| 4 | Client Update Letter | PM notes | DOCX (letterhead) | Sonnet | 30-45 min/letter |
| 5 | Safety Talk Generator | Topic | DOCX | Sonnet | 20-30 min/talk |
| 6 | Punch List Organizer | Walk-through notes | DOCX + XLSX | Sonnet | 1-2 hrs/list |

**Phase 1 total time savings: 16-25 hours/week** (5 active projects)

### Phase 2: Core Operations (6 skills)

| # | Skill | Input | Output | Model | Time Saved |
|---|---|---|---|---|---|
| 7 | Estimate Reviewer | XLSX estimate | DOCX + XLSX | **Opus** | 2-4 hrs/estimate |
| 8 | Bid Comparison | Multiple PDFs | DOCX + XLSX | Sonnet | 2-3 hrs/trade |
| 9 | Change Order Builder | Description + quotes | DOCX | Sonnet | 1-2 hrs/CO |
| 10 | Schedule Variance | PDF/XLSX schedule | DOCX | Sonnet | 1-2 hrs/analysis |
| 11 | Submittal Tracker | XLSX log or spec ref | DOCX + XLSX | Sonnet | 1-2 hrs/analysis |
| 12 | Contract/Insurance Checker | PDF contract/cert | DOCX | **Opus** | 2-4 hrs/review |

**Phase 2 total time savings: 15-25 hours/week** (5 active projects)

### Phase 3: Strategic Advantage (6 skills)

| # | Skill | Input | Output | Model | Time Saved |
|---|---|---|---|---|---|
| 13 | Proposal Generator | RFP + notes | DOCX (multi-section) | **Opus** | 8-16 hrs/proposal |
| 14 | Budget Forecaster | XLSX cost report | DOCX + XLSX | Sonnet | 2-4 hrs/month |
| 15 | Closeout Assembler | Status notes | DOCX + XLSX | Sonnet | 4-8 hrs/project |
| 16 | Lessons Learned | Session notes or auto | DOCX | Sonnet | 1-2 hrs/session |
| 17 | Case Study Builder | Project + PM notes | DOCX (marketing) | Sonnet | 4-8 hrs/study |
| 18 | Incident Report | Incident description | DOCX | Sonnet | 1-2 hrs/report |

**Phase 3 total time savings: 15-21 hours/week** (active use across portfolio)

### Multi-Skill Workflows (4 workflows)

| Workflow | Skills Orchestrated | Trigger |
|---|---|---|
| Bid Day | #8 Bid Compare → #4 Client Update | Per-trade bid analysis + owner summary |
| Weekly Cycle | Aggregate #1 → #4 Client Update | Weekly project status package |
| CO Pipeline | List + generate #9 COs → summary | Pending change order processing |
| Closeout | #15 Closeout → #16 Lessons → #17 Case Study → #4 Final Letter | End-of-project documentation |

---

## Development Timeline

### Day 1: Foundation + Phase 1 Prototype (10 hours)

| Hour | Task | Deliverable | Validates |
|---|---|---|---|
| 1-3 | Run Prompt 01 Part 1 | Config, database, API client, document parser | Infrastructure works |
| 3-5 | Run Prompt 01 Part 2 | Output formatter, BaseSkill, CLI skeleton, knowledge base | Docs look professional |
| 5-7 | Run Prompt 02 Skills 1+5 | Daily Report + Safety Talk | Core text-in/doc-out works |
| 7-9 | Run Prompt 02 Skills 2+3 | RFI + Meeting Minutes | Auto-numbering + action tracking works |
| 9-10 | Run Prompt 02 Skills 4+6 | Client Update + Punch List | Letterhead + dual-output works |
| 10+ | Testing & polish | All tests pass, formatting verified | Ready for team demo |

**Day 1 success = `pytest tests/ -v` passes + 6 skills generate real documents**

### Weeks 2-4: Phase 1 Hardening

| Activity | Effort | Output |
|---|---|---|
| Test with real Krupp project data | 2-3 days | Identified prompt refinements |
| Customize knowledge base files | 1 day | Krupp-specific company profile, bios, standards |
| Iterate prompt templates | 2-3 days | Improved output quality |
| Roll out to PM champion | 0.5 day | 1 PM using tool daily |
| Collect feedback, fix formatting | 1-2 days | Polished output matching Krupp standards |
| Import historical cost data | 1 day | cost_history table populated |

### Weeks 5-8: Phase 2 Build

| Week | Build | Dev Days |
|---|---|---|
| 5 | Skill #7 (Estimate Reviewer) + #8 (Bid Comparison) | 3-4 |
| 6 | Skill #9 (Change Order) + #10 (Schedule Variance) | 3-4 |
| 7 | Skill #11 (Submittal Tracker) + #12 (Contract Checker) | 3-4 |
| 8 | Integration testing, prompt refinement, fixture generation | 2-3 |

### Weeks 9-12: Phase 3 Build

| Week | Build | Dev Days |
|---|---|---|
| 9 | Skill #17 (Case Study) + #16 (Lessons Learned) + #18 (Incident Report) | 3-4 |
| 10 | Skill #15 (Closeout) + #14 (Budget Forecaster) | 3-4 |
| 11 | Skill #13 (Proposal Generator) — most complex skill | 3-4 |
| 12 | Multi-skill workflows (4) + production hardening | 3-4 |

---

## Cost Analysis

### Development Investment

| Phase | Dev Days | Description |
|---|---|---|
| Foundation + Phase 1 | 1 day | Core framework + 6 skills |
| Phase 1 Hardening | 5-8 days | Real data testing, prompt iteration, rollout |
| Phase 2 | 12-15 days | 6 document analysis skills |
| Phase 3 | 12-16 days | 6 strategic skills + 4 workflows |
| Integration/Production | 5-6 days | Procore, migration, deployment |
| **Total** | **35-45 days** | Over 12 weeks |

### Monthly Operating Costs

| Stage | API Cost | Infrastructure | Total |
|---|---|---|---|
| Prototype (Weeks 1-4) | $120-280 | $0 | **$120-280/mo** |
| Growing Usage (Weeks 5-8) | $150-300 | $0 | **$150-300/mo** |
| Production (Week 9+) | $150-300 | $50-150 | **$200-450/mo** |

### Return on Investment

| Metric | Conservative | Optimistic |
|---|---|---|
| Hours saved/week (Phase 1) | 16 hrs | 25 hrs |
| Blended PM/admin rate | $50/hr | $60/hr |
| Monthly value recovered | $3,200 | $6,000 |
| Monthly cost (prototype) | $200 | $280 |
| **Monthly ROI** | **16x** | **21x** |
| Break-even (development investment) | 4-6 weeks | 2-3 weeks |

At full deployment (all 18 skills), savings reach 46-71 hours/week = $9,200-17,000/month against $200-450/month in costs.

---

## Third-Party Dependencies

### Required (Day 1)

| Service | Purpose | Cost | Setup Time |
|---|---|---|---|
| **Anthropic Claude API** | AI processing for all skills | ~$150-300/mo | 5 min (get API key) |

### Recommended (Free)

| Service | Purpose | Cost | Setup Time |
|---|---|---|---|
| **Open-Meteo API** | Auto-populate weather in daily reports | Free, no key | 0 (built-in) |

### Optional (When Needed)

| Service | Purpose | Cost | When |
|---|---|---|---|
| Supabase | Production database + auth | $25/mo | Multi-user or web UI |
| Procore API | PM platform data sync | Free w/ license | If Krupp uses Procore |
| Microsoft Graph | SharePoint + Outlook integration | Free w/ M365 | If Krupp uses M365 |
| Sage 300 CRE | Accounting data access | Included w/ Sage | If Krupp uses Sage |
| Vercel + Railway | Web UI hosting | $20-50/mo | When web UI deployed |
| Sentry | Error monitoring | Free tier | Production deployment |

---

## Risk Register

| Risk | Severity | Probability | Mitigation | Owner |
|---|---|---|---|---|
| AI generates inaccurate content | High | Medium | [VERIFY] flags, PM review required, confidence scoring | Dev team |
| API cost exceeds budget | Medium | Low | Model routing (Sonnet default), cost caps, usage dashboard | Dev team |
| Team adoption resistance | Medium | Medium | Start with 1 champion, let results sell, quick reference cards | Krupp PM |
| Document formatting below standard | Medium | Medium | Iterative refinement with real data, PM feedback loop | Dev + Krupp |
| PDF parsing unreliable | Medium | Medium | Use Claude vision for complex PDFs, test with real docs | Dev team |
| Anthropic API downtime | Low | Low | Retry logic, queue system, offline data entry | Dev team |
| Data security concerns | Medium | Low | Local-only data, Anthropic doesn't train on API data, ZDR header | Dev + Krupp IT |
| Scope creep | Medium | High | Strict phase gating, change requests go to next phase backlog | Project lead |

---

## Build Process — How to Use These Prompts

### Recommended Workflow

```
1. Place CLAUDE.md at project root
2. Open Claude Code
3. Feed prompts in order:

   01_FOUNDATION.md  →  Build core framework (3-5 hours)
                        Run: pytest tests/test_core/ -v
                        Verify: kruppai --help works

   02_PHASE1_SKILLS.md  →  Build 6 Phase 1 skills (4-6 hours)
                           Run: pytest tests/ -v
                           Verify: Each skill generates a real document

   03_PHASE2_SKILLS.md  →  Build 6 Phase 2 skills (Weeks 5-8)
                           Run: pytest tests/ -v
                           Verify: File analysis skills work with test fixtures

   04_PHASE3_SKILLS.md  →  Build 6 Phase 3 skills + workflows (Weeks 9-12)
                           Run: pytest tests/ -v
                           Verify: All 18 skills + 4 workflows operational

   05_INTEGRATION_DEPLOYMENT.md  →  Reference for production deployment
                                    Build as needed
```

### Testing Discipline

Every prompt includes specific test requirements. The testing philosophy:

- **Unit tests**: Every public method, mocked dependencies
- **Integration tests**: Full skill lifecycle with mocked API
- **API tests**: Marked `@pytest.mark.integration`, hit real API selectively
- **Fixture generation**: Programmatic test documents (no manual test file management)

Run after every prompt:
```bash
pytest tests/ -v -m "not integration" --cov=kruppai --cov-report=term-missing
```

Target: >80% coverage on `core/`, >70% coverage on `skills/`.

---

## Approval & Next Steps

This plan is ready for execution. The next action is:

**Run Prompt 01 (`prompts/01_FOUNDATION.md`) to build the core framework.**

Everything else depends on the foundation. Once the foundation passes all tests, Phase 1 skills can be built immediately (same day). The sooner a Krupp PM sees a generated daily report using their real project data, the sooner this tool starts saving the firm time and money.
