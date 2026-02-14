# KruppAI UI Redesign Plan — "Project Command Center"

## Problem Statement

The current UI presents KruppAI as "pick a skill, type notes, get a DOCX" — which IS just
Claude with extra steps. The real value (auto-numbered sequences, weather automation, project
context injection, cross-skill data connections, structured data extraction into queryable
database records) is completely invisible to the user.

## Core Design Principle

**Show the user what the system does FOR them, not just what it asks OF them.**

Every screen should make the automation and data intelligence visible. The user should
constantly see evidence that this is faster/better than using Claude directly.

---

## Screen-by-Screen Plan

### 1. KILL THE WELCOME SCREEN → Direct "Create Project" Flow

Current: Multi-step onboarding hero with 4 numbered steps and a big button.

New: If no projects exist, the Dashboard IS the create-project form. No fluff, no steps.
Simple card: "Create Your First Project" with code, name, client, type, address fields.
Once created, auto-select it and transition to the Project Command Center.

If projects exist but none is selected: Show the project selector prominently with
"Select a project to get started" — one click, done.

### 2. DASHBOARD → "Project Command Center"

Current: Project hero card, cost metrics front and center, quick action buttons.

New: Dashboard shows the PROJECT STATE, not cost metrics.

Layout:
```
┌─────────────────────────────────────────────────────────────────┐
│ Project Status Bar                                              │
│ KRUPP-2026-003 · Downtown Office Tower · 45% Complete           │
│ Contract: $4.2M · Open RFIs: 5 · Open COs: 2 · Open Items: 12 │
└─────────────────────────────────────────────────────────────────┘

┌─ What would you like to do today? ──────────────────────────────┐
│                                                                  │
│  Organized by WORKFLOW, not by skill number:                     │
│                                                                  │
│  📋 Today's Field Work                                           │
│     Daily Report · Safety Talk · Incident Report                 │
│     "You have 46 daily reports for this project"                 │
│                                                                  │
│  ❓ Design Coordination                                          │
│     RFI · Submittal Tracker                                      │
│     "5 open RFIs — 2 past response deadline"                     │
│                                                                  │
│  💰 Financial Management                                         │
│     Change Order · Budget Forecast · Bid Comparison · Estimate   │
│     "2 pending COs totaling $45,200"                             │
│                                                                  │
│  ✉️  Communication                                               │
│     Client Update · Meeting Minutes                              │
│     "Last client update sent Feb 7"                              │
│                                                                  │
│  🏁 Project Closeout                                             │
│     Punch List · Closeout · Lessons Learned · Case Study         │
│                                                                  │
│  📄 Business Development                                         │
│     Proposal Generator · Contract Checker                        │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

┌─ Recent Activity ───────────────────────────────────────────────┐
│ Connected event feed — shows HOW skills relate:                  │
│                                                                  │
│ Feb 14  Daily Report #47 generated (weather: 45°F, Partly Cloudy)│
│ Feb 13  RFI #8 submitted → Response due Feb 27                  │
│ Feb 12  CO #3 approved → Budget updated (+$12,400)              │
│ Feb 12  Meeting Minutes (OAC) → 3 new action items created      │
│ Feb 11  Daily Report #46 generated                              │
└──────────────────────────────────────────────────────────────────┘
```

Each workflow group shows LIVE DATA from the project database — not just labels.
This communicates value: "the system knows your project state."

### 3. KILL ALL MODALS → Inline Form Expansion

Current: Click skill card → modal pops up → fill form → loading spinner → result modal.

New: Click any skill → form slides open INLINE below the workflow group, right where you
clicked. No overlay. No popup. The form is part of the page flow.

The inline form shows THREE things the user CANNOT get from Claude:

```
┌─ Create Daily Report ───────────────────────────────────────────┐
│                                                                  │
│  ┌─ What the system will auto-fill ──────────────────────────┐  │
│  │ 📍 Weather: Fetching for Denver, CO...                    │  │
│  │ 🔢 Report #: This will be Daily Report #47               │  │
│  │ 👥 Context: 3 team members, 8 subs, 5 open action items  │  │
│  │ 🏢 Company standards applied: Krupp writing guide loaded  │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  Your Field Notes *                                              │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ Type or paste your rough notes from today. Include crews, │  │
│  │ work performed, equipment, materials, issues, visitors... │  │
│  │                                                           │  │
│  │                                                           │  │
│  └───────────────────────────────────────────────────────────┘  │
│  Attach photos or documents (optional) [Browse...]               │
│                                                                  │
│  [Generate Daily Report #47]                                     │
│                                                                  │
│  Output: Branded DOCX with structured sections — workforce,     │
│  equipment, work performed, issues, safety — ready to distribute │
└──────────────────────────────────────────────────────────────────┘
```

The "What the system will auto-fill" box is THE key differentiator. It shows the
user exactly what work the system is doing that they'd have to do manually in Claude.

After generation, the result appears inline:
```
┌─ ✅ Daily Report #47 Generated ─────────────────────────────────┐
│                                                                  │
│  📄 daily_report_KRUPP-2026-003_2026-02-14_001.docx             │
│  [Download]  [View in Documents]                                 │
│                                                                  │
│  Saved to database: weather, workforce, issues all indexed       │
│  and searchable. This report connects to your 5 open RFIs.      │
│                                                                  │
│  Cost: $0.14 · Tokens: 2,340                                    │
└──────────────────────────────────────────────────────────────────┘
```

### 4. "DOCUMENTS" → "Project Record"

Current: Flat table of generated files.

New: Two tabs:
- **My Documents**: All docs the current user generated across all projects.
  Shows skill type, project, date, file. Filterable.
- **Project Record**: All docs for the active project. Shows connections between
  documents. "This CO references RFI #3." Grouped by category.

Both tabs support: download, filter by type/date, search by content.

### 5. NEW: SETTINGS SCREEN

Move all non-essential config out of the Dashboard:

- **API Usage**: Today's cost, monthly cost, usage charts over time, cost per skill type
- **API Configuration**: Key status (configured/not), model preferences
- **Output**: Output directory path, file naming convention
- **Limits**: Daily/monthly cost limit configuration
- **Knowledge Base**: View loaded company profile and writing standards
- **About**: Version, database location, health status

### 6. HEADER CHANGES

Current: Logo | Project Selector | Cost Chip

New: Logo | Project Selector | Settings gear icon

The cost chip in the header is removed. It's in Settings now. The header project
selector stays — it's the most important control in the app.

---

## How This Communicates Value

### Before (Current UI):
"Here are 18 AI document skills. Pick one. Type notes. Get a DOCX."
→ User thinks: "I could just use Claude."

### After (Proposed UI):
"Your project has 5 overdue RFIs, 2 pending change orders totaling $45K, and
today's weather is 45°F/Partly Cloudy (already loaded). Click to generate Daily
Report #47 — the system already has your team, subs, open items, and company
standards loaded. Your field notes are the only thing it needs from you."
→ User thinks: "This knows my project. Claude doesn't."

### The Key Insight:
The value isn't in the AI generation. It's in the PROJECT MEMORY. Every time the user
generates a document, the system gets smarter about their project. RFI counts go up.
Action items accumulate. Change order totals grow. The system reflects the real state
of the project — and that state is visible on every screen.

---

## Implementation Scope (5 files)

1. **index.html** — Restructure: remove welcome hero, add settings view, convert
   skill cards to workflow groups with inline expansion slots
2. **style.css** — Add inline form expansion styles, workflow group styles, activity
   feed, settings screen, remove modal-centric styles
3. **app.js** — Replace modal open/close with inline expand/collapse, add settings
   tab, add activity feed from status API, add auto-fill preview before generation,
   add workflow-based grouping logic, add "My Documents" concept
4. **api/main.py** — Add /api/v1/activity endpoint (recent documents + RFI/CO counts),
   add /api/v1/documents/user endpoint, expose project stats in /api/v1/status
5. **core/config.py** — No changes needed (already fixed)

### API Additions Needed:
- `GET /api/v1/projects/{code}/stats` — Returns open RFI count, pending CO total,
  daily report count, last client update date, action item count
- `GET /api/v1/projects/{code}/activity` — Returns recent events with connections
  (document generated, RFI submitted, CO approved, etc.)
- `GET /api/v1/documents/mine` — User's documents across all projects (placeholder
  until auth is added — returns all for now)

---

## What This Does NOT Change

- The 18 skill implementations stay as-is (they work)
- The database schema stays as-is (it's well-designed)
- The output formatter stays as-is (branded DOCX generation works)
- The API client, knowledge base, and weather modules stay as-is
- The CLI stays as-is (independent interface)

This is purely a frontend + API layer redesign to surface the value that's already
built into the backend.
