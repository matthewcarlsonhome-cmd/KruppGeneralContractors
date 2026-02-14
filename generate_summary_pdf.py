"""Generate DEVELOPMENT_SUMMARY.pdf with Krupp branding using reportlab."""
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    HRFlowable,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER

NAVY = colors.Color(27/255, 58/255, 92/255)
GOLD = colors.Color(212/255, 168/255, 75/255)
LIGHT_BG = colors.Color(245/255, 247/255, 250/255)
MED_TEXT = colors.Color(80/255, 80/255, 80/255)


def build_styles():
    ss = getSampleStyleSheet()
    styles = {}

    styles["title"] = ParagraphStyle(
        "title", parent=ss["Title"], fontSize=22, textColor=NAVY,
        spaceAfter=2, fontName="Helvetica-Bold",
    )
    styles["subtitle"] = ParagraphStyle(
        "subtitle", parent=ss["Normal"], fontSize=12, textColor=GOLD,
        spaceAfter=6, fontName="Helvetica",
    )
    styles["meta"] = ParagraphStyle(
        "meta", parent=ss["Normal"], fontSize=9, textColor=MED_TEXT,
        spaceAfter=12, fontName="Helvetica",
    )
    styles["section"] = ParagraphStyle(
        "section", parent=ss["Heading1"], fontSize=14, textColor=colors.white,
        fontName="Helvetica-Bold", spaceBefore=16, spaceAfter=8,
        backColor=NAVY, borderPadding=(4, 6, 4, 6),
    )
    styles["subsection"] = ParagraphStyle(
        "subsection", parent=ss["Heading2"], fontSize=11, textColor=NAVY,
        fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=4,
    )
    styles["body"] = ParagraphStyle(
        "body", parent=ss["Normal"], fontSize=9, leading=13,
        textColor=colors.Color(30/255, 30/255, 30/255),
        fontName="Helvetica", spaceAfter=6,
    )
    styles["bullet"] = ParagraphStyle(
        "bullet", parent=styles["body"], leftIndent=14, bulletIndent=0,
        spaceAfter=4,
    )
    styles["numbered"] = ParagraphStyle(
        "numbered_title", parent=styles["body"], fontSize=9,
        fontName="Helvetica-Bold", textColor=NAVY, spaceAfter=1, spaceBefore=6,
    )
    styles["numbered_body"] = ParagraphStyle(
        "numbered_body", parent=styles["body"], leftIndent=14, spaceAfter=6,
        textColor=MED_TEXT,
    )
    styles["code"] = ParagraphStyle(
        "code", parent=ss["Code"], fontSize=8, leading=10,
        fontName="Courier", backColor=LIGHT_BG, borderPadding=6,
        spaceAfter=8,
    )
    return styles


def section_bar(text, styles):
    """Navy background section header."""
    return Paragraph(f"&nbsp; {text}", styles["section"])


def make_table(headers, rows, col_widths=None):
    """Styled table with navy header and alternating rows."""
    data = [headers] + rows
    t = Table(data, colWidths=col_widths, repeatRows=1)
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 7.5),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.Color(200/255, 200/255, 200/255)),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    for i in range(1, len(data)):
        if i % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), LIGHT_BG))
    t.setStyle(TableStyle(style_cmds))
    return t


def build_pdf():
    doc = SimpleDocTemplate(
        "DEVELOPMENT_SUMMARY.pdf",
        pagesize=letter,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
    )

    s = build_styles()
    story = []

    # ── Header bar ──
    story.append(Paragraph("KRUPP GENERAL CONTRACTORS", ParagraphStyle(
        "hdr", fontName="Helvetica-Bold", fontSize=9, textColor=NAVY, spaceAfter=2,
    )))
    story.append(HRFlowable(width="100%", thickness=2, color=GOLD, spaceAfter=10))

    # ── Title ──
    story.append(Paragraph("KruppAI Development Summary", s["title"]))
    story.append(Paragraph("Sprint 1 Complete", s["subtitle"]))
    story.append(Paragraph(
        "Date: February 14, 2026&nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;"
        "Test Suite: 311/311 passing&nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;"
        "Branch: claude/skill-development-plan-85oL0",
        s["meta"],
    ))

    # ── Commit History ──
    story.append(section_bar("Commit History", s))
    commits = [
        ["dce6ba5", "KruppAI: Complete architecture, build prompts, schema, and development plan"],
        ["4f88e86", "Foundation build: complete core framework, CLI, tests (78/78 passing)"],
        ["58e83c7", "Phase 1 skills: 6 working CLI commands with full test suite (177/177 passing)"],
        ["edd205e", "Phase 2 skills: 6 document analysis skills with full test suite (237/237 passing)"],
        ["f8311df", "Phase 3 complete: 7 skills, web UI, FastAPI backend, Render deployment (311/311 passing)"],
        ["3e5df9a", "Premium UI overhaul: project-first flow, rich skill details, better error handling"],
        ["50bca8d", "Add UI redesign plan based on first-principles review"],
        ["d66629a", "Implement Project Command Center redesign (PLAN.md)"],
    ]
    story.append(make_table(["Hash", "Message"], commits, col_widths=[65, None]))
    story.append(Spacer(1, 6))

    # ── 18 Skills ──
    story.append(section_bar("18 AI Document Generation Skills", s))
    skills = [
        ["1", "Daily Field Report", "1", "Sonnet", "DOCX", "Rough field notes to professional daily reports with auto-fetched weather"],
        ["2", "RFI Generator", "1", "Sonnet", "DOCX", "Issue descriptions to formal RFI documents with auto-numbering"],
        ["3", "Meeting Minutes", "1", "Sonnet", "DOCX", "Rough notes to formatted minutes with attendee & action item tracking"],
        ["4", "Client Update Letter", "1", "Sonnet", "DOCX", "Professional project status letters on Krupp letterhead"],
        ["5", "Toolbox Safety Talk", "1", "Sonnet", "DOCX", "5-10 minute safety talks with OSHA references"],
        ["6", "Punch List Generator", "1", "Sonnet", "DOCX+XLSX", "Walk-through notes to trade-organized punch lists"],
        ["7", "Estimate Reviewer", "2", "Opus", "DOCX+XLSX", "Cost estimates reviewed against industry benchmarks by CSI division"],
        ["8", "Bid Comparison", "2", "Sonnet", "DOCX+XLSX", "Multiple bids compared side-by-side with best-value recommendation"],
        ["9", "Change Order Builder", "2", "Sonnet", "DOCX", "Formal change order proposals with cost breakdown & markup"],
        ["10", "Schedule Variance", "2", "Sonnet", "DOCX+XLSX", "Schedule analysis for variance, critical path, at-risk activities"],
        ["11", "Submittal Tracker", "2", "Sonnet", "DOCX+XLSX", "Submittal logs analyzed, overdue items flagged"],
        ["12", "Contract Checker", "2", "Opus", "DOCX", "Contracts/insurance reviewed for compliance & non-standard clauses"],
        ["13", "Proposal Generator", "3", "Opus", "DOCX", "Full proposals, letter proposals, or SOQs from knowledge base"],
        ["14", "Budget Forecaster", "3", "Sonnet", "DOCX+XLSX", "Job cost analysis, final cost projection, risk identification"],
        ["15", "Closeout Assembler", "3", "Sonnet", "DOCX+XLSX", "Closeout package with branded cover letter & tracker"],
        ["16", "Lessons Learned", "3", "Sonnet", "DOCX", "Structured lessons in manual or extract (data mining) modes"],
        ["17", "Case Study Generator", "3", "Sonnet", "DOCX", "Polished marketing case studies, audience-tailored"],
        ["18", "Incident Report", "3", "Sonnet", "DOCX", "Formal incident reports with root cause & OSHA classification"],
    ]
    story.append(make_table(
        ["#", "Skill", "Ph", "Model", "Output", "Description"],
        skills,
        col_widths=[18, 90, 18, 36, 48, None],
    ))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "Every skill follows a <b>BaseSkill</b> contract: validate_input &rarr; build_prompt &rarr; format_output, "
        "producing branded DOCX/XLSX with Krupp branding (navy #1B3A5C, gold #D4A84B, Calibri font).",
        s["body"],
    ))

    # ── Core Framework ──
    story.append(section_bar("Core Framework (12 Modules)", s))
    modules = [
        ["config.py", "Pydantic settings loader with .env file support and KRUPPAI_ prefix"],
        ["database.py", "SQLite connection manager with auto-schema initialization"],
        ["api_client.py", "Anthropic API wrapper with retry logic (3x exponential backoff), cost tracking"],
        ["document_parser.py", "Universal parser for PDF, DOCX, XLSX, images, and plain text"],
        ["output_formatter.py", "Branded DOCX/XLSX generation with consistent naming convention"],
        ["context_manager.py", "Loads full project context (team, subs, open items) for prompt assembly"],
        ["knowledge_base.py", "Injects company profile, writing standards, safety standards into prompts"],
        ["weather.py", "Auto-fetches current conditions from Open-Meteo (free, no API key)"],
        ["security.py", "Input sanitization, path validation, prompt injection defense"],
        ["monitoring.py", "Health checks, cost tracking summaries"],
        ["migrate_to_supabase.py", "SQLite to Supabase PostgreSQL migration utility"],
    ]
    story.append(make_table(["Module", "Purpose"], modules, col_widths=[110, None]))
    story.append(Spacer(1, 4))

    story.append(Paragraph("Database Schema", s["subsection"]))
    story.append(HRFlowable(width="35%", thickness=1, color=GOLD, spaceAfter=4))
    story.append(Paragraph(
        "<b>23 tables</b> covering projects, team members, subcontractors, and all 18 skill-specific data stores "
        "(daily_reports, rfis, meetings, action_items, change_orders, punch_lists, etc.) plus system tables "
        "for API usage tracking and document management.",
        s["body"],
    ))
    story.append(Paragraph(
        "<b>4 views:</b> v_active_projects (with computed open RFI/action item counts), v_open_action_items, "
        "v_api_cost_summary, v_subcontractor_performance.",
        s["body"],
    ))

    story.append(Paragraph("Two Interfaces", s["subsection"]))
    story.append(HRFlowable(width="35%", thickness=1, color=GOLD, spaceAfter=4))
    story.append(Paragraph(
        "<bullet>&bull;</bullet> <b>CLI</b> (Click + Rich) &mdash; 20+ commands including interactive 18-skill guided menu.",
        s["bullet"],
    ))
    story.append(Paragraph(
        "<bullet>&bull;</bullet> <b>Web</b> (FastAPI) &mdash; REST API with vanilla HTML/CSS/JS SPA. "
        "Endpoints for health, config, project CRUD, skill execution, document download, project stats, activity feed.",
        s["bullet"],
    ))

    story.append(Paragraph("Deployment", s["subsection"]))
    story.append(HRFlowable(width="35%", thickness=1, color=GOLD, spaceAfter=4))
    story.append(Paragraph("<bullet>&bull;</bullet> <b>Render</b> &mdash; render.yaml blueprint for one-click deploy (Docker, starter plan, 1GB persistent disk)", s["bullet"]))
    story.append(Paragraph("<bullet>&bull;</bullet> <b>Supabase</b> &mdash; PostgreSQL schema ready with migration utility", s["bullet"]))
    story.append(Paragraph("<bullet>&bull;</bullet> <b>Docker</b> &mdash; Dockerfile included for containerized deployment", s["bullet"]))

    # ── UI Redesign ──
    story.append(section_bar("UI Redesign: Project Command Center", s))
    story.append(Paragraph(
        "The initial UI was redesigned based on first-principles user feedback. The original interface presented "
        "skills as a flat list with modal popups &mdash; functionally correct but indistinguishable from "
        "\"just using Claude directly.\"",
        s["body"],
    ))

    story.append(Paragraph("What Changed", s["subsection"]))
    story.append(HRFlowable(width="35%", thickness=1, color=GOLD, spaceAfter=4))
    changes = [
        ["Welcome hero with 4-step onboarding", "Direct \"Create Project\" form if no projects exist"],
        ["Cost metrics front-and-center", "Cost tracking moved to Settings screen"],
        ["Modal popups for every skill", "Inline form expansion within workflow groups"],
        ["Skills listed by phase number", "Skills organized by construction workflow"],
        ["Static skill descriptions", "Live project data in each workflow group"],
        ["Flat document table", "Dual tabs: My Documents + Project Record"],
    ]
    story.append(make_table(["Before", "After"], changes, col_widths=[None, None]))
    story.append(Spacer(1, 4))

    story.append(Paragraph("Dashboard States", s["subsection"]))
    story.append(HRFlowable(width="35%", thickness=1, color=GOLD, spaceAfter=4))
    story.append(Paragraph("<b>1. No projects</b> &mdash; Dashboard IS the create-project form. No fluff.", s["body"]))
    story.append(Paragraph("<b>2. Projects exist, none selected</b> &mdash; Project grid with \"Select a project to get started.\"", s["body"]))
    story.append(Paragraph("<b>3. Project selected</b> &mdash; Full command center: status bar, workflow groups, activity feed.", s["body"]))

    story.append(Paragraph("Workflow Groups", s["subsection"]))
    story.append(HRFlowable(width="35%", thickness=1, color=GOLD, spaceAfter=4))
    story.append(Paragraph("Skills organized by how construction professionals actually work:", s["body"]))
    groups = [
        ("Field Work", "Daily Report, Safety Talk, Incident Report"),
        ("Design Coordination", "RFI, Submittal Tracker"),
        ("Financial Management", "Change Order, Budget Forecast, Bid Comparison, Estimate Reviewer"),
        ("Communication", "Client Update, Meeting Minutes"),
        ("Project Closeout", "Punch List, Closeout, Lessons Learned, Case Study"),
        ("Business Development", "Proposal Generator, Contract Checker"),
    ]
    for name, skills_list in groups:
        story.append(Paragraph(f"<bullet>&bull;</bullet> <b>{name}</b> &mdash; {skills_list}", s["bullet"]))

    story.append(Spacer(1, 4))
    story.append(Paragraph("Auto-Fill Preview", s["subsection"]))
    story.append(HRFlowable(width="35%", thickness=1, color=GOLD, spaceAfter=4))
    story.append(Paragraph(
        "Every inline form shows a preview of what the system auto-fills &mdash; weather data, auto-numbered "
        "sequence, project context counts, company standards. This is the key differentiator: the user sees "
        "exactly what work the system does that they'd have to do manually in Claude.",
        s["body"],
    ))

    story.append(Paragraph("New API Endpoints", s["subsection"]))
    story.append(HRFlowable(width="35%", thickness=1, color=GOLD, spaceAfter=4))
    story.append(Paragraph("<bullet>&bull;</bullet> <b>GET /api/v1/projects/{code}/stats</b> &mdash; Open RFIs, pending COs, action items, punch items, daily report count, auto-numbers", s["bullet"]))
    story.append(Paragraph("<bullet>&bull;</bullet> <b>GET /api/v1/projects/{code}/activity</b> &mdash; Merged activity feed across documents, RFIs, COs, action items", s["bullet"]))
    story.append(Paragraph("<bullet>&bull;</bullet> <b>GET /api/v1/documents/all</b> &mdash; All documents across all projects (\"My Documents\")", s["bullet"]))

    # ── Key Insights ──
    story.append(section_bar("Key Insights from Development", s))

    insights = [
        ("1. The value isn't in the AI generation &mdash; it's in the PROJECT MEMORY",
         "The database layer is the real differentiator. Every document generated feeds structured data back "
         "into queryable tables (RFI counts, change order totals, action items, punch items). Over time, the "
         "system knows the project's state in a way that a raw Claude conversation never could."),
        ("2. Make the automation visible",
         "The original UI hid all the work the system does automatically &mdash; fetching weather, auto-numbering "
         "documents, loading project context, injecting company standards. The redesigned auto-fill preview box "
         "shows the user exactly what they'd have to do manually."),
        ("3. Organize by workflow, not by feature list",
         "Presenting 18 skills as a numbered list was overwhelming and abstract. Grouping them into 6 construction "
         "workflows with live project data makes the tool feel like a project command center, not a document factory."),
        ("4. Kill modals &mdash; inline everything",
         "Modals break flow and feel like interruptions. Inline form expansion &mdash; click a skill, form slides "
         "open right where you clicked, shows auto-fill preview, accepts input, shows results &mdash; all in the same page flow."),
        ("5. Cost tracking is plumbing, not a feature",
         "API usage and spend belong in a Settings screen, not front-and-center on the dashboard. Users care about "
         "their project state (open RFIs, pending COs, action items) &mdash; not token consumption."),
        ("6. Commit after each phase, not in batches",
         "Context compaction during long development sessions caused uncommitted work to be lost. "
         "Lesson: push after completing each logical unit of work."),
    ]
    for title, body in insights:
        story.append(Paragraph(title, s["numbered"]))
        story.append(Paragraph(body, s["numbered_body"]))

    # ── Next Sprint ──
    story.append(section_bar("Next Sprint Recommendations", s))

    recs = [
        ("1. Real Document Upload + OCR Pipeline",
         "The DocumentParser supports PDF/DOCX/XLSX/image extraction, but the web UI file upload path needs "
         "end-to-end testing with real construction documents. Priority: superintendent field photos to daily report seamlessly."),
        ("2. Cross-Skill Data Connections",
         "The database has the data, but the UI doesn't surface relationships yet. When a user opens the Change Order "
         "form, show \"Related RFIs: #3, #5\" from the database. When viewing Meeting Minutes, link to action items it created."),
        ("3. Procore / Microsoft Integrations",
         "Stub modules exist in integrations/. Even a read-only Procore sync (pull project data, RFI status, submittals) "
         "would eliminate double-entry and make KruppAI the intelligence layer on top of existing tools."),
        ("4. Multi-User + Authentication",
         "Currently single-user. The Supabase migration utility and PostgreSQL schema are ready. Adding auth enables "
         "real \"My Documents\" with user identity, team-based project access, and audit trails."),
        ("5. Template-Based Document Branding",
         "OutputFormatter builds DOCX from scratch each time. Loading from a .docx template would let Krupp customize "
         "letterhead, headers, and formatting without code changes."),
        ("6. Smart Defaults and Repeat Workflows",
         "If someone generates a Daily Report every morning, pre-populate yesterday's crew sizes. If the same 8 people "
         "attend every OAC meeting, remember the attendee list. Reduce input to the absolute minimum."),
        ("7. Dashboard Analytics",
         "The v_api_cost_summary and v_active_projects views have the data for cost-per-document-type over time, "
         "project activity trends, and skill usage frequency. Charts in Settings would help justify ROI."),
        ("8. Async Weather for Web API",
         "fetch_weather_sync blocks the event loop in the FastAPI context. Switching to the async variant "
         "would improve responsiveness under concurrent users."),
    ]
    for title, body in recs:
        story.append(Paragraph(title, s["numbered"]))
        story.append(Paragraph(body, s["numbered_body"]))

    # ── Technical Reference ──
    story.append(section_bar("Technical Reference", s))

    story.append(Paragraph("File Naming Convention", s["subsection"]))
    story.append(HRFlowable(width="35%", thickness=1, color=GOLD, spaceAfter=4))
    story.append(Paragraph("{skill}_{project_code}_{date}_{sequence}.{ext}", s["code"]))

    story.append(Paragraph("Model Routing", s["subsection"]))
    story.append(HRFlowable(width="35%", thickness=1, color=GOLD, spaceAfter=4))
    story.append(Paragraph("<bullet>&bull;</bullet> <b>Default:</b> claude-sonnet-4-5-20250929 &mdash; All Phase 1 skills, speed-critical tasks", s["bullet"]))
    story.append(Paragraph("<bullet>&bull;</bullet> <b>Opus:</b> claude-opus-4-6 &mdash; Estimate Reviewer, Contract Checker, Proposal Generator", s["bullet"]))

    story.append(Paragraph("Branding", s["subsection"]))
    story.append(HRFlowable(width="35%", thickness=1, color=GOLD, spaceAfter=4))
    story.append(Paragraph("<bullet>&bull;</bullet> Navy: #1B3A5C &nbsp;|&nbsp; Gold: #D4A84B &nbsp;|&nbsp; Font: Calibri", s["bullet"]))
    story.append(Paragraph("<bullet>&bull;</bullet> Footer: \"Generated by KruppAI | {date} | Review required before distribution\"", s["bullet"]))

    story.append(Paragraph("Test Suite", s["subsection"]))
    story.append(HRFlowable(width="35%", thickness=1, color=GOLD, spaceAfter=4))
    story.append(Paragraph(
        "311 tests across 38 files: 7 core module tests, 18 skill tests (one per skill), "
        "1 CLI test, 3 integration tests (one per phase), 1 weather API test.",
        s["body"],
    ))

    doc.build(story)
    print("Generated: DEVELOPMENT_SUMMARY.pdf")


if __name__ == "__main__":
    build_pdf()
