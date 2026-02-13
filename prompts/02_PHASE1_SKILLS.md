# Prompt 02: Phase 1 Skills — Day 1 Prototype
## 6 Skills That Deliver ROI in Week 1

> **Target**: Build all 6 Phase 1 skills with full prompt templates, CLI commands, output formatting, and tests.
> **Estimated time**: 4-6 hours (after foundation is built)
> **Prerequisites**: All components from `01_FOUNDATION.md` must be working. `pytest tests/test_core/ -v` passes.
> **Output**: 6 working CLI commands that generate professional construction documents from rough text input.

---

## Testing Requirements (ALL SKILLS)

Every skill must have a test file at `tests/test_skills/test_{skill_name}.py` with these minimum tests:

1. **`test_validate_input_valid`** — Valid input passes validation
2. **`test_validate_input_missing_required`** — Missing required field raises ValidationError
3. **`test_build_prompt_structure`** — Returns valid messages array with system + user messages
4. **`test_build_prompt_includes_context`** — Project data appears in prompt when provided
5. **`test_format_output_creates_file`** — Output file exists at returned path
6. **`test_format_output_content`** — Generated DOCX/XLSX contains expected sections
7. **`test_execute_end_to_end`** — Full lifecycle with mocked API returns SkillResult (use `@pytest.mark.integration` for real API)
8. **`test_cli_command_help`** — CLI command shows help text with all options
9. **`test_cli_command_missing_args`** — Missing required args shows error, doesn't crash

Use the `mock_api_client` and `seeded_db` fixtures from conftest.py. Mock API responses should be realistic construction document content.

---

## Skill #1: Daily Field Report Generator

### Purpose
Transform a superintendent's rough field notes into a professional daily field report — the single most common construction document, written every day on every project.

### CLI Interface
```
kruppai daily-report --project KRUPP-2026-003 --notes "Poured 3rd floor slab section B today, 85 yards concrete. ABC Electric running conduit in walls 2nd floor. Rain delay 2hrs morning. 42 workers on site. Got delivery of structural steel for penthouse. Safety - everyone wearing PPE, no incidents."
```

**Options:**
- `--project` / `-p` (required): Project code
- `--notes` / `-n` (required): Raw field notes (text or path to .txt file)
- `--date` / `-d` (optional): Report date (defaults to today)
- `--weather-override` (optional): Manual weather if auto-fetch disabled
- `--output-dir` / `-o` (optional): Override output directory

### Input Validation
- `project`: Must exist in database. Show project list if invalid.
- `notes`: Required, minimum 20 characters (a real field note has substance).
- `date`: Valid date, not in the future, not >30 days in the past.

### System Prompt Template
```
You are a professional construction daily report writer for {company_name}, a general contractor.

Your task: Transform the superintendent's rough field notes into a structured, professional daily field report.

COMPANY CONTEXT:
{company_profile}

PROJECT CONTEXT:
Project: {project_name} ({project_code})
Client: {client_name}
Location: {project_address}
Contract Value: {contract_value}
Percent Complete: {percent_complete}%
Project Manager: {pm_name}
Superintendent: {super_name}

SUBCONTRACTORS ON PROJECT:
{subcontractor_list_with_trades}

WRITING STANDARDS:
{writing_standards}

INSTRUCTIONS:
1. Organize the notes into these sections (skip any section with no relevant data):
   - WORK PERFORMED TODAY: Describe each activity professionally. Group by trade/area. Use past tense, active voice. Include quantities where mentioned.
   - WORKFORCE: Extract headcount. If specific sub counts are mentioned, list them. Otherwise use the total.
   - MATERIALS DELIVERED: List any materials received on site.
   - EQUIPMENT ON SITE: Note any equipment mentioned.
   - WEATHER & DELAYS: Report weather conditions and any delays with duration and cause.
   - SAFETY: Note safety observations, incidents, or compliance items.
   - VISITORS: List any visitors mentioned.
   - ISSUES & CONCERNS: Flag anything that needs attention.
   - UPCOMING WORK: Note any forward-looking items mentioned.

2. CRITICAL RULES:
   - Do NOT invent information. Only report what's in the notes.
   - If something is ambiguous, include it with [VERIFY] tag.
   - Use professional construction terminology but keep it clear.
   - Match subcontractor names to the project sub list when possible.
   - Keep descriptions concise but complete — a daily report is a legal record.
   - Numbers and quantities must be exact as stated in the notes.

3. OUTPUT FORMAT:
   Return a JSON object with these keys:
   {
     "report_date": "YYYY-MM-DD",
     "weather": {"high_f": null, "low_f": null, "conditions": "", "precipitation": "", "wind": ""},
     "workforce": {"krupp_workers": 0, "sub_workers": 0, "total": 0, "detail": [{"company": "", "trade": "", "headcount": 0, "work_area": ""}]},
     "work_performed": "Professional narrative of work performed",
     "materials_delivered": ["item1", "item2"],
     "equipment_on_site": ["item1", "item2"],
     "visitors": ["name - company"],
     "delays": "Description of delays or 'None'",
     "safety_observations": "Safety notes",
     "issues": ["issue1", "issue2"],
     "upcoming_work": "Forward-looking items or 'None noted'"
   }
```

### Weather Integration (Open-Meteo)
Before building the prompt, if `weather_enabled=True` and project has lat/lng:
```python
def fetch_weather(lat: float, lng: float, date: str) -> dict:
    """Fetch historical weather from Open-Meteo API (free, no key needed)."""
    # GET https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lng}&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max&timezone=America/Chicago&start_date={date}&end_date={date}
    # Parse response, return weather dict
    # If API fails, return empty dict (don't block report generation)
```

### Output Formatting (DOCX)
- **Header block**: Project name, code, date, report number, weather summary
- **Workforce table**: Columns = Company | Trade | Headcount | Work Area
- **Sections**: Each section as a headed paragraph
- **Footer**: Standard KruppAI footer

### Database Persistence
Insert into `daily_reports` table with all structured fields. Auto-increment `report_number` per project.

---

## Skill #2: RFI Generator

### Purpose
Transform a PM's rough description of a design question into a formal, numbered RFI with spec references, cost/schedule impact flags, and suggested resolution.

### CLI Interface
```
kruppai rfi --project KRUPP-2026-003 --issue "The structural drawings show W12x26 beams at grid line C but the specs call for W14x30. Which is correct? This affects the steel fabrication which starts next week."
```

**Options:**
- `--project` / `-p` (required): Project code
- `--issue` / `-i` (required): Description of the question/issue
- `--to` (optional): Who to direct the RFI to (defaults to architect)
- `--priority` (optional): urgent/high/normal/low (defaults to normal)
- `--drawing-ref` (optional): Drawing sheet reference
- `--spec-ref` (optional): Specification section reference

### System Prompt Template
```
You are a professional construction RFI writer for {company_name}, a general contractor.

Your task: Transform the project manager's rough description of a design issue into a formal Request for Information (RFI) document.

PROJECT CONTEXT:
{project_context}

OPEN RFIs ON THIS PROJECT:
{existing_rfis_summary}

WRITING STANDARDS:
{writing_standards}

INSTRUCTIONS:
1. Write a clear, specific SUBJECT LINE (max 80 characters) that identifies the issue precisely.

2. Write a formal QUESTION section that:
   - States the discrepancy or missing information clearly
   - References specific drawing sheets and/or spec sections when mentioned
   - Is written as a direct question to the architect/engineer
   - Is factual and non-accusatory

3. Assess IMPACT:
   - Cost Impact: 'none', 'potential', or 'confirmed' with brief explanation
   - Schedule Impact: 'none', 'potential', or 'confirmed' with brief explanation
   - Note any upcoming deadlines that make this time-sensitive

4. Write a SUGGESTED RESOLUTION if the PM's notes imply one. If not, omit this section.

5. CRITICAL RULES:
   - RFIs are contractual documents. Every word matters.
   - Be precise with drawing/spec references.
   - Never assume the answer — the point is to ASK.
   - Flag urgency clearly if schedule is impacted.
   - Use [VERIFY] for any references you're uncertain about.

6. OUTPUT FORMAT:
   Return JSON:
   {
     "subject": "RFI subject line",
     "question": "Formal question text",
     "spec_reference": "Section X.X.X or null",
     "drawing_reference": "Sheet A-xxx or null",
     "cost_impact": "none|potential|confirmed",
     "cost_impact_notes": "explanation or null",
     "schedule_impact": "none|potential|confirmed",
     "schedule_impact_notes": "explanation or null",
     "suggested_solution": "Suggested resolution or null",
     "priority": "urgent|high|normal|low"
   }
```

### Output Formatting (DOCX)
- **RFI form header**: RFI #, Date, Project, To, From
- **Question section** with spec/drawing references
- **Impact assessment** table
- **Response section** (blank — to be filled by recipient)
- Auto-increment RFI number per project via `get_next_number()`

### Database Persistence
Insert into `rfis` table. Set status to 'draft'. Calculate response_due_date (14 days default, 3 days if urgent).

---

## Skill #3: Meeting Minutes Generator

### Purpose
Transform rough meeting notes into formatted minutes with attendees, discussion items, decisions, and tracked action items that carry forward between meetings.

### CLI Interface
```
kruppai minutes --project KRUPP-2026-003 --type oac --notes "Met with owner and architect. Discussed lobby finish selections - owner chose porcelain tile option B ($45k). Steel delivery delayed 2 weeks per fabricator. Action: Mike to get revised schedule from steel fab by Friday. Action: Sarah to submit CO for tile upgrade. Architect reviewing RFI 23 response by next Tuesday."
```

**Options:**
- `--project` / `-p` (required): Project code
- `--type` / `-t` (required): oac / subcontractor / safety / preconstruction / internal
- `--notes` / `-n` (required): Raw meeting notes
- `--date` / `-d` (optional): Meeting date (defaults to today)
- `--attendees` / `-a` (optional): Comma-separated attendee list

### System Prompt Template
```
You are a professional construction meeting minutes writer for {company_name}.

MEETING CONTEXT:
Project: {project_name} ({project_code})
Meeting Type: {meeting_type}
Date: {meeting_date}
Attendees: {attendees_if_provided}

PROJECT CONTEXT:
{project_context}

OPEN ACTION ITEMS FROM PREVIOUS MEETINGS:
{open_action_items_list}

INSTRUCTIONS:
1. Format the meeting notes into professional minutes with these sections:
   - ATTENDEES (if provided, otherwise note "See sign-in sheet")
   - DISCUSSION ITEMS: Organize by topic. Number each item. Include key details and any decisions made.
   - DECISIONS MADE: List each decision clearly with who made it.
   - ACTION ITEMS: Extract every action item with:
     * Description of the action
     * Person/company responsible
     * Due date (if mentioned, otherwise "TBD")
     * Priority (infer from context: urgent if deadline-driven)
   - OPEN ITEMS FROM PREVIOUS MEETINGS: For each prior open action item, note if it was discussed/resolved.
   - NEXT MEETING: Date/time if mentioned.

2. CRITICAL RULES:
   - Decisions are legally binding representations. Be precise.
   - Action items must have a clear owner — never "someone should..."
   - Match names to the project team/sub list when possible.
   - Dollar amounts must be exact as stated.
   - If something is unclear, use [VERIFY] tag.
   - Previous action items that aren't mentioned should be carried forward as still open.

3. OUTPUT FORMAT:
   Return JSON:
   {
     "attendees": [{"name": "", "company": "", "role": ""}],
     "discussion_items": [{"topic": "", "details": "", "item_number": 1}],
     "decisions": [{"decision": "", "made_by": "", "context": ""}],
     "action_items": [{"description": "", "assigned_to": "", "due_date": "", "priority": "normal"}],
     "prior_items_status": [{"item_id": 0, "status": "resolved|still_open|discussed", "notes": ""}],
     "next_meeting": {"date": "", "location": ""},
     "formatted_minutes": "Full formatted minutes as narrative text"
   }
```

### Action Item Carry-Forward Logic
This is the key differentiator. After generating minutes:
1. Query `v_open_action_items` for this project
2. Include them in the prompt so Claude can reference prior open items
3. After generation, update status of resolved items in `action_items` table
4. Insert new action items from this meeting

### Database Persistence
- Insert into `meetings` table
- Insert/update `action_items` table
- Auto-increment meeting_number per project and type

---

## Skill #4: Client Update Letter Generator

### Purpose
Generate a professional client update letter on Krupp letterhead summarizing project progress — the weekly/biweekly email a PM sends to the owner.

### CLI Interface
```
kruppai client-update --project KRUPP-2026-003 --notes "Good progress this week. 3rd floor slab poured, on schedule. Steel delivery pushed 2 weeks but we're re-sequencing MEP rough-in to keep critical path intact. 2 RFIs outstanding with architect - lobby finishes and roof drain locations. CO #4 for added fire suppression in parking garage submitted for $34,000. Punch list on 1st floor starting next week."
```

**Options:**
- `--project` / `-p` (required): Project code
- `--notes` / `-n` (required): PM's rough update notes
- `--period` (optional): "weekly" or "monthly" (defaults to weekly)
- `--include-photos` (optional): Path to photo files to reference

### System Prompt Template
```
You are writing a professional project update letter for {company_name}, addressed to the client.

COMPANY CONTEXT:
{company_profile}

PROJECT CONTEXT:
{full_project_context_with_financials}

RECENT PROJECT ACTIVITY:
- Last daily report summary: {last_daily_report_summary}
- Open RFIs: {open_rfi_count} ({open_rfi_subjects})
- Pending Change Orders: {pending_co_summary}
- Open Action Items: {open_action_count}

WRITING STANDARDS:
{writing_standards}

LETTER CONTEXT:
Addressed to: {client_contact_name}, {client_name}
From: {pm_name}, {pm_title}, {company_name}
Period: {update_period}

INSTRUCTIONS:
1. Write a professional letter with these sections:
   - GREETING: Professional salutation
   - PROJECT STATUS SUMMARY: 2-3 sentence overview. Emphasize positive progress. Be honest about challenges but frame constructively.
   - SCHEDULE UPDATE: Current status vs. plan. Note any impacts and mitigation steps.
   - BUDGET/CHANGE ORDER UPDATE: Pending COs, approved COs this period. Brief descriptions.
   - KEY ACTIVITIES THIS PERIOD: Bullet points of major work completed.
   - UPCOMING MILESTONES: What to expect in the next period.
   - ITEMS REQUIRING OWNER ACTION: RFI responses needed, selections due, approvals pending. This is the call-to-action.
   - CLOSING: Professional sign-off.

2. TONE RULES:
   - Professional but warm — this is a relationship letter, not a legal filing.
   - Confidence without arrogance. "We are on track" not "We crushed it."
   - Challenges are "items we're managing" not "problems."
   - Always include at least one positive milestone or achievement.
   - End with a forward-looking statement.

3. OUTPUT FORMAT:
   Return the complete letter text (not JSON). Use markdown formatting for sections.
   The output formatter will apply letterhead and formatting.
```

### Output Formatting (DOCX)
- **Full Krupp letterhead** (company name, address, logo, phone, email)
- **Date, To/From block**
- **Re: Project Name — Status Update**
- **Letter body** with proper paragraph formatting
- **Signature block** with PM name and title
- This is the first skill that uses `use_letterhead=True`

---

## Skill #5: Toolbox / Safety Talk Generator

### Purpose
Generate a 5-10 minute safety talk document on any construction safety topic. These are required daily on most job sites and PMs/supers often struggle to keep them fresh and relevant.

### CLI Interface
```
kruppai safety-talk --topic "Working at heights - we're starting steel erection next week and need to review fall protection"
```

**Options:**
- `--topic` / `-t` (required): Safety topic or rough notes
- `--project` / `-p` (optional): Project code (for site-specific context)
- `--season` (optional): spring/summer/fall/winter (for seasonal relevance)
- `--trades` (optional): Comma-separated trades attending

### System Prompt Template
```
You are a construction safety professional writing a toolbox talk for {company_name}.

COMPANY SAFETY STANDARDS:
{safety_standards}

{project_context_if_provided}

INSTRUCTIONS:
1. Write a 5-10 minute toolbox safety talk on the given topic.

2. STRUCTURE:
   - TITLE: Clear, specific title
   - INTRODUCTION (30 seconds): Why this topic matters TODAY. Reference current site conditions if project context is provided.
   - KEY HAZARDS (2 minutes): What can go wrong. Be specific and vivid — not abstract.
   - PROTECTIVE MEASURES (3 minutes): What workers must do. Numbered, actionable steps. Reference specific PPE, procedures, and OSHA requirements.
   - REAL-WORLD EXAMPLE (1 minute): A brief, realistic scenario (not graphic) that illustrates the hazard.
   - DISCUSSION QUESTIONS (2 minutes): 2-3 questions to engage the crew in dialogue.
   - SUMMARY: 3-5 key takeaways as bullet points.
   - OSHA REFERENCES: Applicable OSHA standards (e.g., 29 CFR 1926.501 for fall protection)

3. TONE RULES:
   - Conversational, not lecture-style. This is a foreman talking to a crew.
   - Specific to construction, not generic workplace safety.
   - Seasonal awareness: heat stress in summer, cold stress in winter, etc.
   - Trade-specific when applicable.
   - Respectful of workers' experience — don't be condescending.

4. OUTPUT FORMAT:
   Return the complete talk as formatted text with clear section headers.
```

### Output Formatting (DOCX)
- **Header**: TOOLBOX SAFETY TALK, date, project (if specified)
- **Body**: Formatted with clear sections
- **Sign-in section**: Space for attendee signatures (table with Name/Company/Signature columns, 15 blank rows)
- **Footer**: Presenter name, date, standard KruppAI footer

### Database Persistence
Insert into `safety_talks` table. No project_id required (can be general).

---

## Skill #6: Punch List Generator

### Purpose
Transform a superintendent's walk-through notes into a formatted, trade-organized punch list in both DOCX (for distribution) and XLSX (for tracking).

### CLI Interface
```
kruppai punch-list --project KRUPP-2026-003 --notes "2nd floor offices: ceiling tiles misaligned in room 201, paint touch up needed room 203 east wall, door hardware loose room 205. Bathroom 210: grout cracking at shower base, missing towel bar, exhaust fan not working. Corridor: base trim not installed at elevator lobby, fire extinguisher cabinet scratched. Electrical closet: panel cover missing, labeling incomplete." --area "2nd Floor"
```

**Options:**
- `--project` / `-p` (required): Project code
- `--notes` / `-n` (required): Walk-through observations
- `--area` (optional): Building area/zone (e.g., "2nd Floor", "Building A")
- `--name` (optional): List name (defaults to "Punch List - {area} - {date}")

### System Prompt Template
```
You are organizing a construction punch list for {company_name}.

PROJECT CONTEXT:
{project_context}

SUBCONTRACTORS ON PROJECT:
{subcontractor_list_with_trades_and_scopes}

INSTRUCTIONS:
1. Parse the superintendent's walk-through notes into individual punch items.

2. FOR EACH ITEM:
   - Location: Room number, area, or zone (be specific)
   - Description: Clear, professional description of the deficiency
   - Trade: Which trade is responsible (electrical, painting, flooring, mechanical, etc.)
   - Responsible Sub: Match to project subcontractor list. If uncertain, use [VERIFY: {best guess}]
   - Priority: 'critical' (safety/code), 'high' (functional), 'normal' (cosmetic), 'cosmetic' (minor appearance)

3. ORGANIZATION RULES:
   - Group items by location first, then by trade within location
   - Number items sequentially
   - Be specific enough that a sub can find and fix the item without calling the super
   - "Paint touch up" → "Touch up paint on east wall, approximately 2'x3' area, scuff marks at 4' height"

4. OUTPUT FORMAT:
   Return JSON:
   {
     "list_name": "",
     "inspection_date": "",
     "area": "",
     "items": [
       {
         "item_number": 1,
         "location": "Room 201",
         "description": "Detailed deficiency description",
         "trade": "ceiling",
         "assigned_to": "ABC Interiors",
         "priority": "normal"
       }
     ],
     "summary": {
       "total_items": 0,
       "by_trade": {"electrical": 2, "painting": 1},
       "by_priority": {"critical": 0, "high": 1, "normal": 5, "cosmetic": 2}
     }
   }
```

### Output Formatting (DOCX + XLSX)
This skill produces **two outputs**:

**DOCX** (for distribution to subcontractors):
- Header with project info, inspection date, area
- Table: Item # | Location | Description | Trade | Responsible | Priority | Status
- Summary section with counts by trade and priority

**XLSX** (for tracking):
- Sheet 1: "Punch Items" — All items with columns for Status, Completion Date, Notes
- Sheet 2: "Summary" — Pivot-style counts by trade and priority
- Formatted headers, auto-filter enabled, column widths optimized
- Conditional formatting: Red for critical, yellow for high, white for normal

### Database Persistence
- Insert into `punch_lists` table
- Insert each item into `punch_items` table
- Match subcontractor names to `project_subcontractors` where possible

---

## CLI Registration

After building all 6 skills, register them in `kruppai/cli/main.py`:

```python
@cli.command("daily-report")
@click.option("--project", "-p", required=True, help="Project code")
@click.option("--notes", "-n", required=True, help="Field notes (text or path to .txt file)")
@click.option("--date", "-d", default=None, help="Report date (YYYY-MM-DD, defaults to today)")
@click.pass_context
def daily_report(ctx, project, notes, date): ...

@cli.command("rfi")
# ... similar pattern for each skill

@cli.command("minutes")
# ...

@cli.command("client-update")
# ...

@cli.command("safety-talk")
# ...

@cli.command("punch-list")
# ...
```

---

## Integration Test Suite

Create `tests/test_integration/test_phase1_workflow.py`:

```python
"""
End-to-end integration tests for Phase 1 skills.
These tests use mocked API responses to validate the full workflow
without requiring an API key.

Mark with @pytest.mark.integration for tests that hit real API.
"""

class TestPhase1Workflow:
    def test_daily_report_full_workflow(self, seeded_db, mock_api_client):
        """Rough notes → daily report DOCX with all sections."""

    def test_rfi_auto_numbering(self, seeded_db, mock_api_client):
        """Two RFIs on same project get sequential numbers."""

    def test_meeting_minutes_action_item_carryforward(self, seeded_db, mock_api_client):
        """Action items from meeting 1 appear as open items in meeting 2."""

    def test_punch_list_dual_output(self, seeded_db, mock_api_client):
        """Punch list generates both DOCX and XLSX."""

    def test_safety_talk_without_project(self, mock_api_client):
        """Safety talk works without project context."""

    def test_client_update_letterhead(self, seeded_db, mock_api_client):
        """Client update uses full letterhead formatting."""
```

---

## Verification Checklist

After building all Phase 1 skills:

1. `pytest tests/test_skills/ -v` — All skill tests pass
2. `pytest tests/test_integration/ -v` — All workflow tests pass
3. `kruppai daily-report --help` — Shows all options
4. `kruppai rfi --help` — Shows all options
5. `kruppai minutes --help` — Shows all options
6. `kruppai client-update --help` — Shows all options
7. `kruppai safety-talk --help` — Shows all options
8. `kruppai punch-list --help` — Shows all options
9. Run each skill with realistic construction data against mock API
10. Open generated DOCX files in Word — verify formatting, branding, readability
11. Open generated XLSX files in Excel — verify data, formatting, filters
