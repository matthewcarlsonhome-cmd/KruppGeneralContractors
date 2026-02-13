# KruppAI Gap Analysis Report
## Current State Assessment & Next Steps for Development

**Date**: February 13, 2026
**Author**: Matthew Carlson Consulting
**Status**: Architecture & Design Complete — Ready for Implementation

---

## 1. What Exists Now (Delivered in This Session)

| Deliverable | Status | File |
|---|---|---|
| Master project context (CLAUDE.md) | Complete | `CLAUDE.md` |
| Database schema (20+ tables, indexes, views) | Complete | `schema/init.sql` |
| Foundation build prompt | Complete | `prompts/01_FOUNDATION.md` |
| Phase 1 skills prompt (6 skills) | Complete | `prompts/02_PHASE1_SKILLS.md` |
| Phase 2 skills prompt (6 skills) | Complete | `prompts/03_PHASE2_SKILLS.md` |
| Phase 3 skills prompt (6 skills + workflows) | Complete | `prompts/04_PHASE3_SKILLS.md` |
| Integration & deployment prompt | Complete | `prompts/05_INTEGRATION_DEPLOYMENT.md` |
| Quick start & production setup guide | Complete | `docs/SETUP_GUIDE.md` |
| Gap analysis (this document) | Complete | `docs/GAP_ANALYSIS.md` |
| Development plan & timeline | Complete | `docs/DEVELOPMENT_PLAN.md` |
| Session insights & corrections | Complete | `CLAUDE_SESSION_NOTES.md` |

## 2. What Does NOT Exist Yet (Implementation Gaps)

### Critical Path — Must Build Before Anything Works

| Gap | Priority | Effort | Blocked By |
|---|---|---|---|
| **Python source code** — no `.py` files exist yet | P0 | 3-5 hrs | Nothing — start here |
| **pyproject.toml** — no installable package | P0 | 5 min | Nothing |
| **.env.example** — template for config | P0 | 5 min | Nothing |
| **Core framework modules** (config, db, API client, parser, formatter, context, knowledge, BaseSkill) | P0 | 3-5 hrs | pyproject.toml |
| **CLI entry point** (kruppai command) | P0 | 30 min | Core framework |
| **At least 1 working skill** (Daily Report recommended) | P0 | 1-2 hrs | Core + CLI |
| **Test suite** (conftest.py, fixtures, unit tests) | P0 | 1-2 hrs | Core framework |

### Phase 1 — Day 1 Prototype Completion

| Gap | Priority | Effort | Dependency |
|---|---|---|---|
| Daily Report skill (#1) | P1 | 1.5 hrs | Core framework |
| RFI Generator skill (#2) | P1 | 1.5 hrs | Core + auto-numbering |
| Meeting Minutes skill (#3) | P1 | 2 hrs | Core + action item DB logic |
| Client Update skill (#4) | P1 | 1 hr | Core + letterhead formatting |
| Safety Talk skill (#5) | P1 | 1 hr | Core (simplest skill) |
| Punch List skill (#6) | P1 | 1.5 hrs | Core + XLSX output |
| Weather API integration | P1 | 30 min | httpx, project lat/lng |
| Realistic test data fixtures | P1 | 1 hr | Database schema |
| Integration tests for Phase 1 | P1 | 1 hr | All Phase 1 skills |

### Phase 2 — Weeks 5-8

| Gap | Priority | Effort | Dependency |
|---|---|---|---|
| Estimate Reviewer (#7) | P2 | 3-4 days | XLSX parser, cost_history data |
| Bid Comparison (#8) | P2 | 3-4 days | PDF parser, multi-file input |
| Change Order Builder (#9) | P2 | 2-3 days | Core + CO auto-numbering |
| Schedule Variance (#10) | P2 | 2-3 days | PDF/XLSX parser for schedules |
| Submittal Tracker (#11) | P2 | 2-3 days | XLSX parser, dual-mode CLI |
| Contract/Insurance Checker (#12) | P2 | 3-4 days | PDF parser, Opus model routing |
| Test fixture generation script | P2 | 1 day | Python PDF/XLSX libraries |
| Historical cost data import tool | P2 | 1 day | cost_history table, CSV import |

### Phase 3 — Weeks 9-12

| Gap | Priority | Effort | Dependency |
|---|---|---|---|
| Proposal Generator (#13) | P3 | 3-4 days | Full knowledge base, completed projects |
| Budget Forecaster (#14) | P3 | 2-3 days | XLSX parser, cost code mapping |
| Closeout Assembler (#15) | P3 | 2-3 days | Sub/project relationship data |
| Lessons Learned (#16) | P3 | 2 days | Cross-skill data queries |
| Case Study Builder (#17) | P3 | 2 days | Completed project data |
| Incident Report (#18) | P3 | 2 days | OSHA classification logic |
| Multi-skill workflows (4) | P3 | 3-4 days | All Phase 1-3 skills |

### Infrastructure & Integration Gaps

| Gap | Priority | Effort | When Needed |
|---|---|---|---|
| Procore API integration | P4 | 3-4 days | When Krupp uses Procore |
| Microsoft Graph integration | P4 | 2-3 days | When SharePoint/Outlook needed |
| Sage 300 CRE ODBC integration | P4 | 2-3 days | When Krupp uses Sage |
| SQLite → Supabase migration script | P3 | 1-2 days | When multi-user needed |
| FastAPI web backend | P3 | 3-5 days | When web UI needed |
| React/Next.js web frontend | P4 | 10-15 days | When CLI outgrown |
| Docker deployment | P3 | 1 day | Production deployment |
| CI/CD pipeline (GitHub Actions) | P3 | 0.5 day | When team commits regularly |
| Sentry error monitoring | P4 | 0.5 day | Production deployment |

---

## 3. Data Gaps

### Must Have Before Phase 1 Demo

| Data | Source | Action Required |
|---|---|---|
| Krupp company profile | Krupp leadership | Fill in `knowledge/company_profile.md` |
| Team member bios | Each PM/super | Fill in `knowledge/team_bios.md` |
| Writing style preferences | Krupp PM feedback | Fill in `knowledge/writing_standards.md` |
| At least 1 real project | Krupp PM | Enter via `kruppai project add` |
| 2-3 subcontractors per project | Krupp PM | Enter via CLI or direct DB |

### Should Have Before Phase 2

| Data | Source | Action Required |
|---|---|---|
| Historical cost data (3+ projects) | Krupp accounting / past estimates | Import via CSV into cost_history table |
| Standard subcontract provisions | Krupp legal / contract templates | Document in knowledge base |
| Insurance requirements by project type | Krupp risk management | Document in knowledge base |
| CSI code mapping for Krupp's cost structure | Krupp estimating | Map to schema's csi_code fields |

### Nice to Have Before Phase 3

| Data | Source | Action Required |
|---|---|---|
| Completed project data (5+ projects) | Krupp historical records | Enter as completed projects in DB |
| Case study content from past marketing | Krupp marketing materials | Import or re-create via Skill #17 |
| Safety statistics (EMR, DART) | Krupp safety officer | Add to company profile |
| Client testimonials | Krupp marketing / PM relationships | Add to knowledge base |

---

## 4. Technical Risks & Open Questions

### Risk 1: Document Formatting Quality
**Gap**: We have spec'd the output formatting (fonts, colors, tables) but haven't tested it with real python-docx/openpyxl output. The first DOCX generated may need formatting iteration.
**Mitigation**: Budget 2-3 hours of formatting polish during Day 1 prototype. Have a Krupp PM review output side-by-side with their manually-created documents.
**Action**: During 01_FOUNDATION build, create a sample document with every formatting element (tables, headers, footers, letterhead) and visually verify in Word.

### Risk 2: PDF Parsing Variability
**Gap**: Construction documents (bids, contracts, schedules) vary wildly in format. PyMuPDF handles text extraction well, but table extraction from PDFs is notoriously unreliable.
**Mitigation**: For Phase 2, use Claude's native PDF understanding (pass PDF as base64 image) rather than relying solely on text extraction. Claude vision handles construction document layouts very well.
**Action**: Test with 3-5 real Krupp documents (bid, contract, schedule) during Phase 2 development to validate parsing.

### Risk 3: Prompt Template Iteration
**Gap**: The prompt templates in 02-04 are well-designed but untested against real construction data. First outputs may need prompt refinement.
**Mitigation**: Plan for 1-2 iterations per skill prompt during Weeks 2-4 hardening period. Each iteration takes ~15 minutes (adjust prompt, regenerate, compare).
**Action**: Keep a `prompts/changelog.md` tracking prompt modifications and their effect on output quality.

### Risk 4: API Cost Estimation Accuracy
**Gap**: Cost estimates ($150-300/month) are based on assumed usage patterns. Real usage may differ.
**Mitigation**: Cost tracking is built into the system. After Week 1, compare actual vs. estimated costs and adjust model routing if needed (e.g., use Haiku for safety talks).
**Action**: Review `kruppai status` output weekly during rollout. Set daily cost alert at $30.

### Risk 5: Team Adoption
**Gap**: Not a technical gap, but the biggest real-world risk. A tool nobody uses has zero value.
**Mitigation**: Start with 1 PM champion on 1 project. Let them use it for 1 week. Collect feedback. Let their results sell it to the rest of the team.
**Action**: Identify the PM most likely to champion the tool before Day 1 demo.

---

## 5. Recommended Next Steps (In Order)

### Immediate (This Week)

1. **Run Prompt 01 (Foundation)** — Build the entire core framework. This is the critical path. Without working config, database, API client, parser, formatter, and BaseSkill, nothing else can proceed.

2. **Run Prompt 02 (Phase 1 Skills)** — Build all 6 Phase 1 skills immediately after the foundation. Target: working prototype by end of Day 1.

3. **Customize Knowledge Base** — Get real Krupp data into the knowledge files. Even placeholder content dramatically improves output quality vs. generic defaults.

4. **Test with Real Data** — Run each Phase 1 skill with actual Krupp project data. Note formatting issues, terminology mismatches, and missing context.

### Short Term (Weeks 2-4)

5. **Iterate Prompts** — Based on real-data testing, refine prompt templates. This is the highest-leverage activity — a better prompt produces a better document every single time it's used.

6. **Roll Out to 1 PM** — Pick the champion. Install on their machine. Have them use it for one full week of real project work.

7. **Collect Feedback** — What works? What doesn't? What's missing? What formatting needs changing?

8. **Import Historical Data** — Get 3+ completed projects' cost data into the cost_history table. This is the foundation for Phase 2's estimate reviewer and budget forecaster.

### Medium Term (Weeks 5-8)

9. **Run Prompt 03 (Phase 2 Skills)** — Build the 6 document analysis skills.

10. **Test PDF/XLSX Parsing** — Validate with real Krupp documents.

11. **Consider Procore Integration** — If Krupp uses Procore, this eliminates a huge amount of manual data entry.

### Longer Term (Weeks 9-12)

12. **Run Prompt 04 (Phase 3 Skills)** — Build strategic skills and workflows.

13. **Evaluate Multi-User Needs** — If >2 users want the tool, plan Supabase migration.

14. **Consider Web UI** — If CLI adoption is limited, a simple web interface may expand adoption.

---

## 6. Success Criteria

### Day 1 Prototype: "It Works"
- [ ] `kruppai daily-report` generates a professional DOCX from rough notes
- [ ] All 6 Phase 1 CLI commands respond to `--help`
- [ ] Database initializes and persists data between sessions
- [ ] `pytest tests/ -m "not integration"` — all pass
- [ ] Generated documents open cleanly in Microsoft Word
- [ ] API cost tracking shows costs for each operation

### Week 4: "The Team Uses It"
- [ ] At least 1 PM using the tool daily for at least 1 project
- [ ] Knowledge base customized with real Krupp data
- [ ] Prompt templates refined based on real-world feedback
- [ ] Daily reports, meeting minutes, and RFIs generated for real projects
- [ ] Output quality rated "as good or better than manual" by PM champion

### Week 8: "We Can't Imagine Working Without It"
- [ ] Phase 2 skills operational for document analysis
- [ ] Historical cost data imported for benchmarking
- [ ] Estimate review and bid comparison used on real bid opportunities
- [ ] Time savings measurable: hours/week recovered per PM

### Week 12: "This Is a Competitive Advantage"
- [ ] All 18 skills operational
- [ ] Multi-skill workflows automated (bid day, weekly cycle, closeout)
- [ ] Proposal generator using real company data to win new work
- [ ] Lessons learned database growing across projects
- [ ] The firm's institutional knowledge is preserved in the system, not just in people's heads
