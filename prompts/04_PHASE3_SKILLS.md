# Prompt 04: Phase 3 Skills — Strategic Advantage
## 6 Skills That Differentiate Krupp + Multi-Skill Workflows

> **Target**: Build 6 Phase 3 skills that leverage the full knowledge base and historical data, plus 4 multi-skill automated workflows.
> **Estimated time**: 10-14 development days across Weeks 9-12
> **Prerequisites**: Phase 1 + Phase 2 fully operational. Knowledge base files populated with real Krupp data. Historical cost data imported.
> **Key difference from Phase 1-2**: These skills use **accumulated institutional knowledge** — past projects, lessons learned, company capabilities — to produce documents that could not be written by a new employee. They represent Krupp's competitive intelligence captured in software.

---

## Testing Requirements (ALL PHASE 3 SKILLS)

All standard tests from Phase 1/2, plus:

1. **`test_knowledge_base_integration`** — Skill incorporates company profile, team bios, or writing standards from knowledge base
2. **`test_historical_data_enrichment`** — Skill queries and uses data from completed projects
3. **`test_cross_skill_data_access`** — Skills that reference data created by other skills (e.g., Proposal referencing Case Studies)
4. **`test_output_professional_quality`** — Output document structure matches what Krupp would send to a client/owner (verify sections, formatting, tone)
5. **`test_empty_knowledge_base_graceful`** — Skill still works without knowledge files (reduced quality, but no crash)

Additional fixtures for Phase 3:
- `tests/fixtures/sample_rfp.pdf` — 10-page request for proposal
- `tests/fixtures/sample_closeout_checklist.xlsx` — Closeout requirements
- `tests/fixtures/completed_project_data.json` — Historical project data for proposals/case studies

---

## Skill #13: Proposal Generator

### Purpose
Generate a complete project pursuit proposal from an RFP or opportunity description, using Krupp's full company profile, team bios, project experience, and safety record. This is the highest-value, most complex skill — a good proposal can win a $20M project.

### CLI Interface
```
kruppai proposal --project KRUPP-2026-005 --rfp rfp_city_library.pdf --notes "Strong fit for us - we did the community center last year. Emphasize healthcare and public facility experience. Sarah Chen as PM, Mike Rodriguez as super. Budget around $8M. Emphasize our schedule reliability and safety record."
```

**Options:**
- `--project` / `-p` (required): Project code (pre-created for pursuit tracking)
- `--rfp` (optional): Path to RFP document (PDF)
- `--notes` / `-n` (required): PM's strategic notes on the opportunity
- `--type` (optional): full / letter / qualification (defaults to full)
- `--team` (optional): Comma-separated team member names for this pursuit

### System Prompt Template
```
You are writing a construction project proposal for {company_name}, competing for a new project.

COMPANY PROFILE:
{full_company_profile}

COMPANY CAPABILITIES:
- Founded: {founded_year}
- Specialties: {specialties}
- Service Area: {service_area}
- Bonding Capacity: ${bonding_capacity}
- Current Projects: {active_project_count} valued at ${total_active_value}

PROPOSED TEAM:
{team_bios_for_proposed_members}

RELEVANT PROJECT EXPERIENCE:
{completed_projects_matching_type_and_size}
(Include: project name, client, value, size, completion date, key achievements)

CASE STUDIES (if available):
{relevant_case_studies}

SAFETY RECORD:
- EMR: {experience_modification_rate}
- DART Rate: {dart_rate}
- {safety_highlights}

RFP REQUIREMENTS (if provided):
{parsed_rfp_content}

PM'S STRATEGIC NOTES:
{pm_notes}

INSTRUCTIONS:
1. Generate a complete proposal with these sections:
   a. COVER LETTER (1 page): Personal, specific to this opportunity. Not generic.
   b. EXECUTIVE SUMMARY (1 page): Why Krupp is the right choice. Lead with the strongest differentiator.
   c. UNDERSTANDING OF PROJECT: Demonstrate Krupp understands the project's unique challenges and the client's goals.
   d. APPROACH & METHODOLOGY: How Krupp will deliver this project. Preconstruction services, construction approach, quality management. Be specific, not generic.
   e. PROPOSED TEAM: Bios of key personnel with relevant experience highlighted. Show why THIS team is right for THIS project.
   f. RELEVANT EXPERIENCE: 3-5 most relevant completed projects. Emphasize similarities to the proposed project.
   g. SCHEDULE APPROACH: High-level schedule strategy. Mention phasing, milestones, early procurement.
   h. SAFETY: Safety program overview with specific metrics. This isn't optional — it wins contracts.
   i. REFERENCES: Client references from relevant projects (use real data from completed projects if available).

2. TONE & STYLE:
   - Confident but not arrogant. "We will deliver" not "We are the best."
   - Specific not generic. Every paragraph should feel written for THIS project.
   - Client-focused. Every capability framed as a benefit to the client.
   - Use the PM's strategic notes to guide emphasis and positioning.
   - Match the formality level to the client type (government = formal, private = conversational).

3. CRITICAL RULES:
   - Only reference real completed projects from the database.
   - Only include team members that actually work at Krupp.
   - Safety statistics must be accurate — these are verifiable.
   - If the RFP has specific requirements (page limits, required sections), follow them exactly.
   - Use [VERIFY] for any fact you're uncertain about.

4. OUTPUT FORMAT:
   Return the full proposal as formatted text with clear section headers.
   Each section separated by "---SECTION BREAK---" for the formatter.
```

**Model**: `claude-opus-4-6` — Proposals demand the best writing quality and strategic thinking.

### Output Formatting (DOCX)
- **Professional cover page**: Project name, Krupp logo, date, "Prepared for [Client]"
- **Table of Contents** (auto-generated from headings)
- **Formatted sections** with consistent heading styles
- **Team page**: Photos placeholder, bio text, relevant experience bullets
- **Project experience cards**: Name, photo placeholder, key stats, brief narrative
- **Full Krupp branding throughout**

### Knowledge Base Usage
This skill uses every knowledge base file:
- `company_profile.md` → Executive summary, understanding, approach
- `team_bios.md` → Team section (filtered to proposed team members)
- `writing_standards.md` → Tone and voice throughout
- `safety_standards.md` → Safety section
- Database queries: completed projects, case studies, cost history for relevant project types

---

## Skill #14: Budget Forecaster

### Purpose
Generate a monthly budget-to-actual variance report with cost-to-complete projections and risk analysis. The "financial vital signs" of a project.

### CLI Interface
```
kruppai budget-forecast --project KRUPP-2026-003 --file job_cost_report_feb2026.xlsx --month 2026-02
```

**Options:**
- `--project` / `-p` (required): Project code
- `--file` / `-f` (required): Job cost report (XLSX from accounting system)
- `--month` (optional): Forecast month (defaults to current)
- `--contingency-used` (optional): Contingency already consumed (dollars)

### System Prompt Template
```
You are a construction project cost analyst for {company_name}.

PROJECT CONTEXT:
{project_context_with_full_financials}

CONTRACT INFORMATION:
Original Contract: ${original_contract}
Approved Change Orders: ${approved_co_total} ({co_count} COs)
Current Contract: ${current_contract}
Percent Complete: {percent_complete}%

JOB COST DATA:
{parsed_cost_report_by_code}

HISTORICAL COST PERFORMANCE ON SIMILAR PROJECTS:
{historical_cost_data_for_project_type}

INSTRUCTIONS:
1. EXECUTIVE SUMMARY:
   - Overall financial health: Green/Yellow/Red
   - Projected final cost vs. current contract value
   - Projected margin vs. original margin

2. COST CODE ANALYSIS:
   For each major cost code:
   - Budget vs. actual to date
   - Percent of budget consumed vs. percent complete
   - Projected cost to complete
   - Variance explanation (favorable or unfavorable)
   - Flag codes where actual/budget ratio significantly exceeds % complete

3. CASH FLOW PROJECTION:
   - Remaining costs by month (based on schedule)
   - Billing projections
   - Cash flow exposure

4. RISK ITEMS:
   - Cost codes trending over budget
   - Pending change orders not yet approved
   - Subcontractor payment issues
   - Contingency burn rate vs. project progress

5. RECOMMENDATIONS:
   - Specific cost control measures
   - Items requiring PM attention
   - Contingency adequacy assessment

6. OUTPUT FORMAT:
   Return JSON with executive_summary, cost_code_analysis[], cash_flow_projection, risk_items[], recommendations[]
```

### Output Formatting (DOCX + XLSX)
**DOCX**: Executive summary with status indicators, cost code analysis narrative, risk section
**XLSX**: Sheet 1: "Budget vs Actual" (full detail, formulas). Sheet 2: "Projections" (cost to complete by code). Sheet 3: "Cash Flow" (monthly projection). Sheet 4: "Risk Register"

---

## Skill #15: Closeout Package Assembler

### Purpose
Generate a project closeout checklist, cover letter, and track completion of all closeout requirements. Construction closeout is a 3-6 month process with hundreds of items — this skill organizes it.

### CLI Interface
```
kruppai closeout --project KRUPP-2026-003 --notes "Starting closeout process. Substantial completion was Jan 15. Still need warranties from ABC Electric and Pacific Mechanical. All as-builts submitted except plumbing. Owner training scheduled for HVAC next week. Final cleaning 80% complete."
```

**Options:**
- `--project` / `-p` (required): Project code
- `--notes` / `-n` (required): Current closeout status notes
- `--checklist-file` (optional): Existing closeout checklist (XLSX) to update
- `--mode` (optional): generate / update (defaults to generate)

### System Prompt Template
```
You are managing construction project closeout for {company_name}.

PROJECT CONTEXT:
{project_context}

SUBCONTRACTORS WITH CLOSEOUT REQUIREMENTS:
{sub_list_with_contract_status}

SUBSTANTIAL COMPLETION DATE: {substantial_completion_date}
FINAL COMPLETION DATE: {final_completion_date_or_target}

PM'S CLOSEOUT STATUS NOTES:
{pm_notes}

OPEN PUNCH ITEMS: {open_punch_count} remaining
PENDING CHANGE ORDERS: {pending_co_count}
RETENTION HELD: ${retention_amount}

INSTRUCTIONS:
1. Generate a comprehensive closeout checklist organized by category:

   A. CONTRACTUAL DOCUMENTS:
      - Final lien waivers (from each sub)
      - Consent of surety (if bonded)
      - Final change order log
      - Certificate of substantial completion
      - Certificate of occupancy

   B. TECHNICAL DOCUMENTS:
      - As-built drawings (by trade)
      - Operation & Maintenance manuals
      - Equipment warranties
      - Test & balance reports
      - Commissioning reports
      - Special inspections final reports

   C. FINANCIAL CLOSEOUT:
      - Final pay applications
      - Retention release documentation
      - Final accounting reconciliation
      - Subcontractor final payment

   D. OWNER TURNOVER:
      - Owner training sessions (by system)
      - Spare parts & attic stock inventory
      - Key & lock schedule
      - Final cleaning
      - Utility transfer

   E. REGULATORY:
      - Certificate of occupancy
      - Final fire marshal inspection
      - Health department approvals (if applicable)
      - ADA compliance verification

2. For each item:
   - Status: complete / in_progress / not_started / not_applicable
   - Responsible party (GC, specific sub, owner, architect)
   - Due date (based on contract or standard practice)
   - Notes (from PM's input)

3. Generate a closeout COVER LETTER to the owner summarizing:
   - Overall closeout status
   - Items requiring owner action
   - Outstanding items by responsible party
   - Estimated final completion timeline

4. OUTPUT FORMAT:
   Return JSON with checklist_items[], cover_letter_text, status_summary, items_by_responsibility{}
```

### Output Formatting (DOCX + XLSX)
**DOCX**: Cover letter on letterhead + summary of outstanding items
**XLSX**: Full closeout tracker with status columns, responsible party, due dates, notes. Color-coded status. Filter-ready.

---

## Skill #16: Lessons Learned Extractor

### Purpose
Capture and organize lessons learned from project experiences — either from a facilitated session or by mining existing daily reports, meeting minutes, and change orders for patterns.

### CLI Interface
```
# Manual capture from a lessons learned session
kruppai lessons-learned --project KRUPP-2026-003 --notes "Steel fabricator delivered 3 weeks late - should have had backup fab shop identified. Porcelain tile selection took owner 2 months - next time build mock-up room earlier. Safety: tower crane anti-collision system saved us from a potential incident in month 4."

# Auto-extract from project data
kruppai lessons-learned --project KRUPP-2026-003 --mode extract
```

**Options:**
- `--project` / `-p` (required): Project code
- `--notes` / `-n` (required for manual mode): Session notes
- `--mode` (optional): manual / extract (defaults to manual)
- `--category` (optional): Filter extraction to specific category

### Manual Mode Prompt
```
You are capturing construction lessons learned for {company_name}.

PROJECT CONTEXT:
{project_context}

SESSION NOTES:
{pm_notes}

EXISTING LESSONS LEARNED DATABASE:
{relevant_existing_lessons}

INSTRUCTIONS:
1. For each lesson identified in the notes:
   - TITLE: Short, searchable title
   - CATEGORY: scheduling / budget / subcontractor / design / safety / client / procurement / quality
   - SITUATION: What happened (factual, concise)
   - IMPACT: What was the consequence (time, cost, safety, quality)
   - LESSON: What we learned
   - RECOMMENDATION: Specific action for future projects
   - SEVERITY: low / medium / high / critical
   - APPLICABLE PROJECT TYPES: Which types of projects should heed this lesson
   - TAGS: Keywords for searchability

2. Check against existing lessons — avoid duplicating already-captured insights.
3. Frame lessons positively when possible: "Next time, do X" not "We screwed up X."

4. OUTPUT FORMAT:
   Return JSON array of lesson objects
```

### Extract Mode
Query the project's daily reports, meeting minutes, and change orders, then ask Claude to identify patterns:
```python
def extract_lessons(project_id: int) -> str:
    """
    Pull all project data and ask Claude to identify lessons learned.
    Sources: daily_reports (delays, issues), change_orders (reasons, amounts),
    meetings (decisions, action items), punch_items (trade quality patterns).
    """
```

---

## Skill #17: Case Study Builder

### Purpose
Generate a marketing-quality project case study from project data, suitable for proposals, the website, and client presentations.

### CLI Interface
```
kruppai case-study --project KRUPP-2026-001 --notes "Completed on time and $200K under budget. Client was thrilled with the lobby design. Biggest challenge was the tight site access downtown - we used a tower crane and just-in-time deliveries. Won ENR Best Projects award for this one."
```

**Options:**
- `--project` / `-p` (required): Project code (should be complete or near-complete)
- `--notes` / `-n` (required): PM's highlights and notes about the project
- `--audience` (optional): client / marketing / proposal (defaults to marketing)
- `--photos` (optional): Paths to project photos

### System Prompt Template
```
You are writing a marketing case study for {company_name}.

COMPANY PROFILE:
{company_profile}

PROJECT DATA:
Name: {project_name}
Client: {client_name}
Type: {project_type}
Size: {sqft} SF, {floors} floors
Contract Value: ${contract_value}
Delivery Method: {delivery_method}
Duration: {start_date} to {completion_date}
PM: {pm_name}
Superintendent: {super_name}

PROJECT METRICS:
- Schedule: {on_time_status}
- Budget: {budget_status}
- Change Orders: {co_count} totaling ${co_total}
- Safety: {safety_record}
- Punch Items at SC: {punch_count}

LESSONS LEARNED (from this project):
{project_lessons_learned}

PM'S NOTES:
{pm_notes}

TARGET AUDIENCE: {audience}

INSTRUCTIONS:
1. Write a compelling case study with:
   - TITLE: Project name with evocative subtitle
   - AT A GLANCE: Key metrics in bullet format (value, size, type, duration)
   - THE CHALLENGE: What made this project difficult or unique
   - OUR APPROACH: How Krupp solved it — specific methods, innovations, team decisions
   - THE RESULTS: Concrete outcomes — on time, under budget, client satisfaction, awards
   - KEY METRICS: Quantifiable achievements
   - CLIENT TESTIMONIAL: If PM provided a quote, include it. If not, note [INSERT CLIENT QUOTE]
   - TEAM: Key personnel who delivered the project

2. TONE:
   - Marketing quality — this goes on the website and in proposals
   - Specific and quantified — not vague claims
   - Story-driven — challenge → approach → results arc
   - {audience}-appropriate (client = relationship-focused, marketing = achievement-focused, proposal = capability-focused)

3. OUTPUT FORMAT:
   Return formatted text with section headers. The formatter will apply design layout.
```

### Output Formatting (DOCX)
- **Visual layout**: Project photo placeholder at top, key metrics sidebar
- **Professional formatting**: Two-column layout for metrics, single column for narrative
- **Full branding** with Krupp colors and fonts
- **Print-ready**: Suitable for a proposal appendix or standalone marketing piece

---

## Skill #18: Incident Report Generator

### Purpose
Generate a formal safety incident report from a superintendent's account of an event. Time-sensitive — incidents must be documented within 24 hours.

### CLI Interface
```
kruppai incident-report --project KRUPP-2026-003 --description "Worker from ABC Electric slipped on wet concrete on 3rd floor at approximately 2:15 PM. Was wearing proper PPE including hard hat and safety boots. Complained of sore wrist. First aid administered on site. Sent to urgent care as precaution. Area was wet from concrete curing - no barricade tape was in place. Witnesses: Mike Rodriguez (Krupp super), John Davis (ABC foreman)." --type first_aid
```

**Options:**
- `--project` / `-p` (required): Project code
- `--description` / `-d` (required): Account of the incident
- `--type` / `-t` (required): near_miss / first_aid / recordable / lost_time / property_damage / environmental
- `--date` (optional): Incident date (defaults to today)
- `--time` (optional): Incident time

### System Prompt Template
```
You are writing a construction safety incident report for {company_name}.
THIS IS A TIME-SENSITIVE LEGAL DOCUMENT. Accuracy is paramount.

PROJECT CONTEXT:
{project_context}

COMPANY SAFETY STANDARDS:
{safety_standards}

INCIDENT CLASSIFICATION: {incident_type}
DATE: {incident_date}
TIME: {incident_time}

SUPERINTENDENT'S ACCOUNT:
{raw_description}

INSTRUCTIONS:
1. Write a formal incident report with:
   - INCIDENT SUMMARY: Clear, factual description in third person. Chronological order.
   - LOCATION: Specific location within the project site.
   - INVOLVED PERSONS: Name, company, role, nature of injury/involvement.
   - WITNESSES: Names and companies.
   - IMMEDIATE ACTIONS TAKEN: First aid, medical transport, area secured, etc.
   - ROOT CAUSE ANALYSIS: Based on the description, identify likely root cause. Use [VERIFY] if speculative.
   - CONTRIBUTING FACTORS: Environmental, procedural, equipment, training factors.
   - CORRECTIVE ACTIONS: Specific actions to prevent recurrence, with responsible party and timeline.
   - PREVENTIVE MEASURES: Broader measures for similar situations.
   - OSHA RECORDABILITY: Based on incident type and description, assess if OSHA recordable.

2. CRITICAL RULES:
   - Facts only. Do not embellish or assume details not in the account.
   - Use [VERIFY] for any inference or assumption.
   - Time-specific: Include dates and times wherever possible.
   - Person-specific: Name individuals for actions taken and assigned.
   - Never use language that admits fault or liability — factual and neutral.
   - This document may be subpoenaed. Every word matters.

3. OSHA REPORTING:
   - If fatality or in-patient hospitalization: Note "OSHA notification required within 8 hours"
   - If amputation or loss of eye: Note "OSHA notification required within 24 hours"
   - For recordable injuries: Note OSHA 300 log requirement

4. OUTPUT FORMAT:
   Return JSON:
   {
     "incident_number": auto,
     "summary": "Factual summary paragraph",
     "location": "Specific location",
     "involved_persons": [{"name": "", "company": "", "role": "", "injury": ""}],
     "witnesses": [{"name": "", "company": ""}],
     "immediate_actions": "Actions taken",
     "root_cause": "Root cause analysis",
     "contributing_factors": ["factor1", "factor2"],
     "corrective_actions": [{"action": "", "responsible": "", "due_date": ""}],
     "preventive_actions": ["action1"],
     "is_osha_recordable": true|false,
     "osha_notification_required": false,
     "osha_notification_deadline": null,
     "severity": "minor|moderate|serious|critical"
   }
```

### Output Formatting (DOCX)
- **INCIDENT REPORT header** in red (#CC0000) — this is urgent and distinct from other documents
- **Classification badge**: Type and severity prominently displayed
- **Structured sections** with clear labeling
- **Corrective action table**: Action | Responsible | Due Date | Status
- **Signature lines**: Superintendent, PM, Safety Director
- **CONFIDENTIAL watermark** if recordable or lost_time

---

## Multi-Skill Workflows

### Workflow 1: Bid Day Workflow
**Trigger**: `kruppai workflow bid-day --project KRUPP-2026-003`

Orchestrates:
1. **Bid Comparison** (Skill #8) for each trade with uploaded bids
2. **Client Update** (Skill #4) summarizing bid results for owner
3. Generates a consolidated **Bid Day Summary** combining all trade comparisons

```python
class BidDayWorkflow:
    """
    Runs bid comparison for multiple trades, then generates
    a consolidated summary and client update letter.
    """
    def execute(self, project_id: int, trade_bids: dict[str, list[Path]]) -> list[SkillResult]:
        results = []
        for trade, bid_files in trade_bids.items():
            result = self.bid_comparison.execute(
                project_id=project_id, trade=trade, bid_files=bid_files
            )
            results.append(result)
        # Generate consolidated summary
        summary = self.generate_bid_day_summary(project_id, results)
        # Generate client update
        client_update = self.client_update.execute(
            project_id=project_id,
            notes=self.format_bid_summary_for_client(results)
        )
        results.append(client_update)
        return results
```

### Workflow 2: Weekly Project Cycle
**Trigger**: `kruppai workflow weekly --project KRUPP-2026-003`

Orchestrates a PM's weekly documentation cycle:
1. Aggregate daily reports from the week → **Weekly Summary** (via Client Update skill)
2. Review open action items → **Action Item Status Report**
3. Generate **Client Update Letter** from the week's activity

### Workflow 3: Change Order Pipeline
**Trigger**: `kruppai workflow co-pipeline --project KRUPP-2026-003`

1. List all pending COs with status
2. For each draft CO, generate formal **Change Order** document
3. Generate **CO Log Summary** report
4. Update project financials

### Workflow 4: Project Closeout Workflow
**Trigger**: `kruppai workflow closeout --project KRUPP-2026-003`

1. Run **Closeout Assembler** (Skill #15) for current status
2. Run **Lessons Learned Extractor** (Skill #16) in extract mode
3. Run **Case Study Builder** (Skill #17) for marketing
4. Generate **Final Client Letter** via Client Update

---

## Phase 3 Integration Test Suite

Create `tests/test_integration/test_phase3_workflow.py`:

```python
class TestPhase3Workflow:
    def test_proposal_uses_knowledge_base(self, seeded_db, populated_knowledge_base, mock_api_client):
        """Proposal prompt includes company profile and team bios."""

    def test_proposal_includes_relevant_projects(self, seeded_db_with_completed_projects, mock_api_client):
        """Proposal references completed projects matching the target type."""

    def test_budget_forecast_with_cost_report(self, seeded_db, mock_api_client, sample_cost_report):
        """Budget forecast correctly parses XLSX cost report."""

    def test_closeout_tracks_sub_requirements(self, seeded_db, mock_api_client):
        """Closeout checklist includes items for each subcontractor."""

    def test_lessons_learned_extract_mode(self, seeded_db_with_full_project_history, mock_api_client):
        """Extract mode pulls from daily reports, minutes, and COs."""

    def test_case_study_from_completed_project(self, seeded_db_with_completed_projects, mock_api_client):
        """Case study populates metrics from project data."""

    def test_incident_report_osha_flags(self, seeded_db, mock_api_client):
        """Recordable incident correctly flags OSHA notification requirements."""

    def test_bid_day_workflow(self, seeded_db, mock_api_client, sample_bid_pdfs):
        """Bid day workflow runs all trades and generates consolidated summary."""

    def test_weekly_cycle_workflow(self, seeded_db_with_weekly_data, mock_api_client):
        """Weekly workflow aggregates daily reports into client update."""

    def test_closeout_workflow(self, seeded_db_with_completed_projects, mock_api_client):
        """Closeout workflow runs all 4 skills in sequence."""
```

---

## Workflow CLI Registration

```python
@cli.group()
def workflow():
    """Run multi-skill automated workflows."""
    pass

@workflow.command("bid-day")
@click.option("--project", "-p", required=True)
def bid_day(project): ...

@workflow.command("weekly")
@click.option("--project", "-p", required=True)
def weekly(project): ...

@workflow.command("co-pipeline")
@click.option("--project", "-p", required=True)
def co_pipeline(project): ...

@workflow.command("closeout")
@click.option("--project", "-p", required=True)
def closeout(project): ...
```

---

## Verification Checklist

1. All 6 Phase 3 skill tests pass
2. All 4 workflow tests pass
3. Proposal generator produces multi-section DOCX with real project data
4. Budget forecaster parses XLSX cost reports correctly
5. Closeout assembler generates both cover letter and tracking XLSX
6. Lessons learned stores to database and avoids duplicates
7. Case study produces marketing-quality output
8. Incident report flags OSHA requirements correctly
9. Bid Day workflow runs 3 trades and generates consolidated output
10. Weekly workflow aggregates 5 daily reports into client update
11. Full test suite: `pytest tests/ -v --tb=short` — all pass
12. API cost tracking shows correct model usage (Opus for proposals, Sonnet for others)
