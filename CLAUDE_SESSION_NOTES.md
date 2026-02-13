# KruppAI Development Session Notes
## Key Insights, Corrections, and Decisions — February 13, 2026

---

## Session Context

This session produced the complete architecture, prompt files, database schema, gap analysis, setup guides, and development plan for KruppAI. No Python code was written — this session is **design and planning only**. The output is a set of actionable build prompts that produce working code when fed to Claude Code.

---

## Key Architectural Decisions

### 1. BaseSkill Pattern Over Ad-Hoc Functions
**Decision**: Every skill inherits from an abstract `BaseSkill` class with a fixed lifecycle (validate → context → prompt → API → format → persist → return).
**Why**: This is the single most important architectural decision. It means:
- Every skill is testable the same way
- API cost tracking is automatic (base class handles it)
- New skills are faster to build (just implement 3 methods)
- Output formatting is consistent (no one-off formatting code)
**Risk if violated**: Skills with custom lifecycles become untestable, unauditable, and inconsistent.

### 2. SQLite First, PostgreSQL Second
**Decision**: Prototype uses SQLite. Migrate to Supabase PostgreSQL only when multi-user access is needed.
**Why**: SQLite is zero-config, ships with Python, and handles 30 users in a single office with no issues. It removes every infrastructure dependency from Day 1. The schema is designed to work on both — no migration rewrite needed.
**Insight**: Many projects die because they over-engineer infrastructure on Day 1. A $0/month database that works is better than a $25/month database that requires setup, configuration, and network access.

### 3. CLI First, Web UI Later
**Decision**: Click CLI is the primary interface. FastAPI web backend is a future phase.
**Why**: Superintendents and PMs are already in a terminal (or can be trained to use one in 5 minutes). A CLI is buildable in hours; a web UI takes weeks. Delivering value fast matters more than looking polished.
**When to add Web UI**: When more than 5 users want the tool OR when field staff need mobile access.

### 4. Model Routing (Sonnet Default, Opus for Critical Skills)
**Decision**: 80% of skills use Sonnet (fast, cheap). Only contract review, proposals, and estimate analysis use Opus (precise, expensive).
**Why**: A daily report doesn't need the most expensive model. A contract review does — missing a liability clause could cost Krupp millions. This routing saves ~60% on API costs vs. using Opus for everything.
**Skills using Opus**: #7 (Estimate Reviewer), #12 (Contract Checker), #13 (Proposal Generator).

### 5. JSON Output from Claude, Formatting in Python
**Decision**: Claude returns structured JSON. Python code transforms JSON into branded DOCX/XLSX documents.
**Why**:
- JSON is parseable and testable (you can assert on fields)
- Formatting is deterministic (same JSON → same DOCX every time)
- Branding changes don't require prompt changes
- If Claude returns malformed content, the error is caught at the JSON parse stage, not after writing a corrupt document
**Exception**: Client Update Letter (Skill #4) returns plain text because the output is a narrative letter, not structured data.

---

## Key Design Insights

### Insight 1: Action Item Carry-Forward Is the Killer Feature
Meeting minutes (Skill #3) are useful alone, but the **carry-forward of open action items between meetings** is what makes it transformative. No PM consistently tracks action items across 10+ meetings. The system does it automatically by querying `v_open_action_items` and injecting them into the next meeting's prompt.

### Insight 2: The Knowledge Base Is the Moat
Skills #1-12 are productivity tools — they save time. Skills #13-18 are **competitive advantages** because they use accumulated institutional knowledge (past project costs, lessons learned, team capabilities) that a new competitor can't replicate. The knowledge base grows more valuable with every project completed.

### Insight 3: Construction Documents Are Legal Records
Daily reports, RFIs, meeting minutes, change orders, and incident reports are potentially discoverable in litigation. This means:
- Every document needs a `[VERIFY]` flag system for uncertain content
- No document should be distributed without PM review
- The footer on every document says "Review required before distribution"
- Incident reports must use neutral, factual language — never admitting fault

### Insight 4: Test Fixtures Must Be Realistic
Generic test data ("Project A", "Company B") is worse than useless — it hides formatting issues that only appear with real construction terminology. Test fixtures use realistic data: "City Center Medical Office Building", "ABC Electrical", "W12x26 beam at grid line C". This catches formatting issues (long company names, special characters in spec references) during development, not during the demo.

### Insight 5: Weather Auto-Population Is a Trust Builder
Auto-populating weather data from Open-Meteo for daily reports is a small feature, but it builds trust immediately. When a superintendent sees accurate weather data they didn't type, they believe the tool is working for them. This "delightful small detail" accelerates adoption.

---

## Potential Errors / Things to Watch

### 1. python-docx Table Formatting
python-docx's table formatting API is verbose and non-intuitive. Alternating row colors, merged header cells, and precise column widths all require careful implementation. Budget extra time here.
**Action**: Build a `_format_table()` helper in the output formatter that handles all table styling uniformly. Don't let individual skills format their own tables.

### 2. PyMuPDF Table Extraction
PyMuPDF extracts text well but table detection is inconsistent, especially with:
- PDFs generated from scanned documents
- Complex bid tabulations with merged cells
- Schedule printouts with Gantt chart graphics
**Action**: For Phase 2, consider using Claude's native PDF understanding (send the PDF as a base64 document) rather than extracting text locally first. Claude handles construction document layouts very well.

### 3. SQLite String-Based Dates
Storing dates as TEXT in ISO-8601 format (required for SQLite compatibility) means date arithmetic requires `strftime()` functions in SQL. This works but is less ergonomic than PostgreSQL's native date types.
**Action**: All date comparisons in Python code, not SQL. Use `datetime.fromisoformat()` on query results.

### 4. JSON Parsing from Claude
Claude occasionally returns JSON with trailing commas, comments, or markdown code fences. The JSON parser must handle:
- `\`\`\`json ... \`\`\`` wrapper → strip before parsing
- Trailing commas → regex strip or use `json5` library
- Truncated JSON (if output is cut off by token limit) → graceful error
**Action**: Build a `parse_claude_json(text: str) -> dict` utility in the API client that handles these edge cases.

### 5. Token Limits on Large Documents
A 50-page subcontract or a 200-line estimate may exceed Claude's context window when combined with the system prompt, project context, and knowledge base.
**Action**: The document parser's `max_chars` parameter (default 100,000) prevents this. For very large documents, implement a summarize-then-analyze two-stage approach.

---

## Roadblocks Encountered

### None (Design Phase Only)
This session was architecture and design. No code was executed, no dependencies were installed, no API calls were made. Potential roadblocks are documented in the Risk Register (DEVELOPMENT_PLAN.md) and Gap Analysis (GAP_ANALYSIS.md).

**The first real roadblocks will appear during Prompt 01 execution**, likely in:
1. python-docx formatting (getting tables and branding right)
2. PyMuPDF installation on certain platforms (binary dependency)
3. Anthropic API response format edge cases

---

## Corrections Made During Design

1. **Cost storage**: Changed from dollars (float) to cents (integer) throughout the schema. Float math causes rounding errors in financial calculations. $12,500.00 is stored as 1250000 cents.

2. **Model IDs**: Used full Anthropic model IDs (`claude-sonnet-4-5-20250929`, `claude-opus-4-6`) instead of short names. Short names can be ambiguous when new model versions are released.

3. **Action items table**: Added `carried_from_meeting_id` foreign key to support the carry-forward feature. Without this, you can't distinguish between "new item from this meeting" and "carried forward from meeting #5."

4. **Punch items structure**: Split into `punch_lists` (the list itself) and `punch_items` (individual items) instead of a flat table. This supports multiple punch lists per project (pre-SC, final, by-area) with independent tracking.

5. **Contract review prompt**: Added explicit instruction "Never use language that admits fault or liability" for incident reports. Construction incident reports are legal documents — this instruction is safety-critical.

6. **Submittal tracker dual mode**: Originally designed as analyze-only. Added cover sheet generation mode after recognizing that PMs need both the log analysis AND the physical cover sheet that goes on top of submittal packages.

---

## Files Produced This Session

```
KruppGeneralContractors/
├── CLAUDE.md                          # Master project context for Claude Code
├── CLAUDE_SESSION_NOTES.md            # This file — session insights
├── schema/
│   └── init.sql                       # Complete database schema (500+ lines)
├── prompts/
│   ├── 01_FOUNDATION.md               # Core framework build prompt
│   ├── 02_PHASE1_SKILLS.md            # 6 Phase 1 skill build prompts
│   ├── 03_PHASE2_SKILLS.md            # 6 Phase 2 skill build prompts
│   ├── 04_PHASE3_SKILLS.md            # 6 Phase 3 skill + workflow build prompts
│   └── 05_INTEGRATION_DEPLOYMENT.md   # Integration & production deployment
├── docs/
│   ├── DEVELOPMENT_PLAN.md            # Master development plan & timeline
│   ├── SETUP_GUIDE.md                 # Quick start + production deployment guide
│   └── GAP_ANALYSIS.md                # Current state assessment & next steps
├── templates/                          # (empty — DOCX templates created during build)
└── tests/                              # (empty — test files created during build)
```

---

## Recommended Next Action

**Open a new Claude Code session. Place `CLAUDE.md` at the project root. Feed `prompts/01_FOUNDATION.md` as the first build instruction. Verify with `pytest`. Then immediately feed `prompts/02_PHASE1_SKILLS.md`. By end of day, you have 6 working skills generating real construction documents.**
