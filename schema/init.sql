-- ============================================================================
-- KruppAI Database Schema v1.0
-- Compatible with: SQLite 3.35+ (prototype) and PostgreSQL 14+ (production)
-- ============================================================================
-- CONVENTIONS:
--   - All tables use INTEGER PRIMARY KEY (SQLite) / SERIAL (Postgres)
--   - Timestamps stored as TEXT in ISO-8601 format (SQLite-safe, Postgres-castable)
--   - Money stored as INTEGER in cents (avoids floating point issues)
--   - Boolean stored as INTEGER 0/1 (SQLite-safe)
--   - Foreign keys enforced: PRAGMA foreign_keys = ON (set in application code)
-- ============================================================================

-- ============================================================================
-- COMPANY & PERSONNEL
-- ============================================================================

CREATE TABLE IF NOT EXISTS company (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    legal_name TEXT,
    address_line1 TEXT,
    address_line2 TEXT,
    city TEXT,
    state TEXT,
    zip TEXT,
    phone TEXT,
    email TEXT,
    website TEXT,
    logo_path TEXT,                          -- Path to logo file for document branding
    license_number TEXT,
    founded_year INTEGER,
    description TEXT,                        -- Company bio for proposals/case studies
    specialties TEXT,                        -- JSON array: ["commercial", "healthcare", "education"]
    service_area TEXT,                       -- Geographic region description
    bonding_capacity_cents INTEGER,          -- Max bonding capacity in cents
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS team_members (
    id INTEGER PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT UNIQUE,
    phone TEXT,
    role TEXT NOT NULL,                      -- 'project_manager', 'superintendent', 'estimator', 'admin', 'executive'
    title TEXT,                              -- Job title: "Senior Project Manager"
    bio TEXT,                                -- Professional bio for proposals
    certifications TEXT,                     -- JSON array: ["PMP", "OSHA 30", "LEED AP"]
    years_experience INTEGER,
    hire_date TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- ============================================================================
-- PROJECTS
-- ============================================================================

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY,
    project_code TEXT NOT NULL UNIQUE,       -- e.g., "KRUPP-2026-003"
    name TEXT NOT NULL,
    description TEXT,
    client_name TEXT,
    client_contact_name TEXT,
    client_contact_email TEXT,
    client_contact_phone TEXT,
    architect_firm TEXT,
    architect_contact TEXT,
    architect_email TEXT,
    owner_name TEXT,                         -- Property owner (may differ from client)

    -- Location
    address TEXT,
    city TEXT,
    state TEXT,
    zip TEXT,
    latitude REAL,                           -- For weather API integration
    longitude REAL,

    -- Financials
    original_contract_cents INTEGER,         -- Original contract value in cents
    current_contract_cents INTEGER,          -- Current (with approved COs) in cents
    estimated_cost_cents INTEGER,            -- Estimated cost to complete

    -- Schedule
    notice_to_proceed_date TEXT,
    substantial_completion_date TEXT,
    final_completion_date TEXT,
    actual_start_date TEXT,
    actual_completion_date TEXT,
    current_percent_complete REAL DEFAULT 0, -- 0.0 to 100.0

    -- Classification
    project_type TEXT,                       -- 'commercial', 'healthcare', 'education', 'industrial', 'residential', 'municipal'
    delivery_method TEXT,                    -- 'hard_bid', 'negotiated', 'design_build', 'cm_at_risk', 'cm_agency'
    contract_type TEXT,                      -- 'lump_sum', 'gmp', 'cost_plus', 'unit_price'
    square_footage INTEGER,
    number_of_floors INTEGER,

    -- Status
    status TEXT NOT NULL DEFAULT 'active',   -- 'preconstruction', 'active', 'punch_list', 'closeout', 'complete', 'on_hold'
    is_archived INTEGER NOT NULL DEFAULT 0,

    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS project_team (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    team_member_id INTEGER NOT NULL REFERENCES team_members(id) ON DELETE CASCADE,
    project_role TEXT NOT NULL,              -- 'project_manager', 'superintendent', 'project_engineer', 'assistant_pm'
    is_primary INTEGER NOT NULL DEFAULT 0,   -- Primary contact for this role
    assigned_date TEXT,
    removed_date TEXT,
    UNIQUE(project_id, team_member_id, project_role)
);

-- ============================================================================
-- SUBCONTRACTORS
-- ============================================================================

CREATE TABLE IF NOT EXISTS subcontractors (
    id INTEGER PRIMARY KEY,
    company_name TEXT NOT NULL,
    contact_name TEXT,
    email TEXT,
    phone TEXT,
    address TEXT,
    city TEXT,
    state TEXT,
    zip TEXT,
    trade TEXT NOT NULL,                     -- CSI division or trade name: "electrical", "plumbing", "concrete"
    csi_division TEXT,                       -- "26" for electrical, "22" for plumbing, etc.
    license_number TEXT,
    insurance_expiry TEXT,
    bonding_capacity_cents INTEGER,
    rating REAL,                             -- Internal rating 1.0-5.0
    notes TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS project_subcontractors (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    subcontractor_id INTEGER NOT NULL REFERENCES subcontractors(id) ON DELETE CASCADE,
    contract_value_cents INTEGER,
    scope_description TEXT,                  -- Brief scope of work
    contract_status TEXT DEFAULT 'pending',  -- 'pending', 'executed', 'complete', 'terminated'
    start_date TEXT,
    completion_date TEXT,
    retention_percent REAL DEFAULT 10.0,
    change_order_total_cents INTEGER DEFAULT 0,
    paid_to_date_cents INTEGER DEFAULT 0,
    UNIQUE(project_id, subcontractor_id)
);

-- ============================================================================
-- SKILL #1: DAILY REPORTS
-- ============================================================================

CREATE TABLE IF NOT EXISTS daily_reports (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    report_date TEXT NOT NULL,
    report_number INTEGER,                   -- Auto-incrementing per project

    -- Weather (auto-populated via Open-Meteo API or manual)
    weather_high_f REAL,
    weather_low_f REAL,
    weather_conditions TEXT,                 -- "Sunny", "Rain", "Overcast"
    weather_precipitation_in REAL,
    weather_wind_mph REAL,
    weather_source TEXT DEFAULT 'manual',    -- 'open_meteo' or 'manual'

    -- Workforce
    krupp_workers INTEGER DEFAULT 0,
    sub_workers INTEGER DEFAULT 0,
    total_workers INTEGER DEFAULT 0,

    -- Content (raw input and AI-generated)
    raw_notes TEXT NOT NULL,                 -- User's rough field notes (input)
    work_performed TEXT,                     -- AI-generated structured work description
    materials_delivered TEXT,                -- JSON array of materials
    equipment_on_site TEXT,                  -- JSON array of equipment
    visitors TEXT,                           -- JSON array of visitor names/companies
    delays TEXT,                             -- Description of any delays
    safety_observations TEXT,
    quality_observations TEXT,
    issues TEXT,                             -- JSON array of issues noted

    -- Output
    document_path TEXT,                      -- Path to generated DOCX
    generated_by_skill TEXT DEFAULT 'daily_report',

    -- Workforce detail (JSON array of {subcontractor, trade, headcount, work_area})
    workforce_detail TEXT,

    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    created_by INTEGER REFERENCES team_members(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_daily_reports_project_date
    ON daily_reports(project_id, report_date);

-- ============================================================================
-- SKILL #2: RFIs
-- ============================================================================

CREATE TABLE IF NOT EXISTS rfis (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    rfi_number INTEGER NOT NULL,             -- Auto-incrementing per project
    subject TEXT NOT NULL,
    question TEXT NOT NULL,                  -- AI-generated formal question
    raw_input TEXT,                          -- User's rough description of the issue
    spec_reference TEXT,                     -- Spec section reference if applicable
    drawing_reference TEXT,                  -- Drawing sheet reference if applicable
    cost_impact TEXT DEFAULT 'unknown',      -- 'none', 'potential', 'confirmed', 'unknown'
    schedule_impact TEXT DEFAULT 'unknown',  -- 'none', 'potential', 'confirmed', 'unknown'
    suggested_solution TEXT,                 -- Proposed resolution
    priority TEXT DEFAULT 'normal',          -- 'urgent', 'high', 'normal', 'low'

    -- Routing
    assigned_to TEXT,                        -- Who the RFI is directed to (architect, engineer, owner)
    status TEXT NOT NULL DEFAULT 'draft',    -- 'draft', 'submitted', 'responded', 'closed'
    submitted_date TEXT,
    response_due_date TEXT,
    response_date TEXT,
    response_text TEXT,
    responded_by TEXT,

    -- Output
    document_path TEXT,
    generated_by_skill TEXT DEFAULT 'rfi_generator',

    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    created_by INTEGER REFERENCES team_members(id),
    UNIQUE(project_id, rfi_number)
);

-- ============================================================================
-- SKILL #3: MEETING MINUTES
-- ============================================================================

CREATE TABLE IF NOT EXISTS meetings (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    meeting_number INTEGER,                  -- Auto-incrementing per project
    meeting_type TEXT NOT NULL DEFAULT 'oac', -- 'oac', 'subcontractor', 'safety', 'preconstruction', 'internal'
    meeting_date TEXT NOT NULL,
    start_time TEXT,
    end_time TEXT,
    location TEXT,

    -- Attendees (JSON array of {name, company, role})
    attendees TEXT,

    -- Content
    raw_notes TEXT NOT NULL,                 -- User's rough meeting notes (input)
    formatted_minutes TEXT,                  -- AI-generated formatted minutes
    agenda_items TEXT,                       -- JSON array of agenda topics

    -- Key decisions (JSON array of {decision, made_by, context})
    decisions TEXT,

    -- Next meeting
    next_meeting_date TEXT,
    next_meeting_location TEXT,

    -- Output
    document_path TEXT,
    generated_by_skill TEXT DEFAULT 'meeting_minutes',

    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    created_by INTEGER REFERENCES team_members(id)
);

CREATE TABLE IF NOT EXISTS action_items (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    meeting_id INTEGER REFERENCES meetings(id) ON DELETE SET NULL,
    source_skill TEXT,                       -- Which skill created this: 'meeting_minutes', 'daily_report', etc.
    description TEXT NOT NULL,
    assigned_to TEXT NOT NULL,               -- Name or company responsible
    due_date TEXT,
    priority TEXT DEFAULT 'normal',          -- 'urgent', 'high', 'normal', 'low'
    status TEXT NOT NULL DEFAULT 'open',     -- 'open', 'in_progress', 'complete', 'cancelled'
    completion_date TEXT,
    notes TEXT,
    carried_from_meeting_id INTEGER REFERENCES meetings(id), -- If carried forward from prior meeting
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_action_items_project_status
    ON action_items(project_id, status);

-- ============================================================================
-- SKILL #4: CLIENT UPDATES (stored as generated documents, no dedicated table)
-- Uses generated_documents table for tracking
-- ============================================================================

-- ============================================================================
-- SKILL #5: SAFETY TALKS (stored as generated documents)
-- ============================================================================

CREATE TABLE IF NOT EXISTS safety_talks (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL, -- Can be project-specific or general
    topic TEXT NOT NULL,
    raw_input TEXT,                          -- User's topic description or notes
    talk_content TEXT,                       -- AI-generated safety talk content
    applicable_trades TEXT,                  -- JSON array of relevant trades
    season TEXT,                             -- 'spring', 'summer', 'fall', 'winter' for seasonal relevance
    osha_references TEXT,                    -- JSON array of OSHA standard references
    document_path TEXT,
    talk_date TEXT,                          -- Date the talk was/will be given
    attendee_count INTEGER,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    created_by INTEGER REFERENCES team_members(id)
);

-- ============================================================================
-- SKILL #6: PUNCH LIST
-- ============================================================================

CREATE TABLE IF NOT EXISTS punch_lists (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    list_name TEXT NOT NULL,                 -- "Final Punch List", "Pre-Substantial Completion", etc.
    inspection_date TEXT,
    inspector_name TEXT,
    area TEXT,                               -- Building area/zone inspected
    status TEXT NOT NULL DEFAULT 'open',     -- 'open', 'in_progress', 'complete'
    total_items INTEGER DEFAULT 0,
    completed_items INTEGER DEFAULT 0,
    document_path TEXT,
    excel_path TEXT,                         -- Punch lists often get both DOCX and XLSX
    raw_input TEXT,                          -- User's rough observations/notes
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    created_by INTEGER REFERENCES team_members(id)
);

CREATE TABLE IF NOT EXISTS punch_items (
    id INTEGER PRIMARY KEY,
    punch_list_id INTEGER NOT NULL REFERENCES punch_lists(id) ON DELETE CASCADE,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    item_number INTEGER NOT NULL,            -- Sequential within list
    location TEXT NOT NULL,                  -- Room, floor, area
    description TEXT NOT NULL,
    trade TEXT,                              -- Responsible trade
    subcontractor_id INTEGER REFERENCES subcontractors(id) ON DELETE SET NULL,
    assigned_to TEXT,                        -- Company name if sub not in system
    priority TEXT DEFAULT 'normal',          -- 'critical', 'high', 'normal', 'low', 'cosmetic'
    status TEXT NOT NULL DEFAULT 'open',     -- 'open', 'in_progress', 'complete', 'disputed'
    due_date TEXT,
    completion_date TEXT,
    notes TEXT,
    photo_path TEXT,                         -- Path to deficiency photo if any
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_punch_items_list ON punch_items(punch_list_id);
CREATE INDEX IF NOT EXISTS idx_punch_items_status ON punch_items(project_id, status);

-- ============================================================================
-- SKILL #7: ESTIMATE REVIEWER (analysis results)
-- ============================================================================

CREATE TABLE IF NOT EXISTS estimate_reviews (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    estimate_name TEXT NOT NULL,             -- Name/description of the estimate
    source_file_path TEXT,                   -- Path to uploaded estimate file
    total_estimate_cents INTEGER,
    total_benchmark_cents INTEGER,           -- Benchmark total for comparison
    variance_percent REAL,                   -- Overall variance from benchmark
    findings TEXT,                           -- AI-generated analysis (JSON array of findings)
    high_risk_items TEXT,                    -- JSON array of flagged line items
    recommendations TEXT,                    -- AI-generated recommendations
    document_path TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    created_by INTEGER REFERENCES team_members(id)
);

-- ============================================================================
-- SKILL #8: BID COMPARISON
-- ============================================================================

CREATE TABLE IF NOT EXISTS bid_comparisons (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    trade TEXT NOT NULL,                     -- Trade being bid (e.g., "Electrical")
    comparison_name TEXT NOT NULL,
    bid_date TEXT,
    number_of_bidders INTEGER,
    low_bid_cents INTEGER,
    high_bid_cents INTEGER,
    spread_percent REAL,                     -- Spread between low and high
    recommendation TEXT,                     -- AI recommendation
    analysis TEXT,                           -- Detailed AI analysis
    bidder_data TEXT,                        -- JSON array of {company, base_bid, alternates, qualifications, exclusions}
    document_path TEXT,
    excel_path TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    created_by INTEGER REFERENCES team_members(id)
);

-- ============================================================================
-- SKILL #9: CHANGE ORDERS
-- ============================================================================

CREATE TABLE IF NOT EXISTS change_orders (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    co_number INTEGER NOT NULL,              -- Auto-incrementing per project
    title TEXT NOT NULL,
    description TEXT NOT NULL,               -- AI-generated formal description
    raw_input TEXT,                          -- User's rough description
    reason TEXT,                             -- 'owner_change', 'design_error', 'unforeseen_condition', 'code_requirement', 'value_engineering'

    -- Financial
    cost_cents INTEGER,                      -- Proposed cost change (positive = increase)
    markup_percent REAL,
    total_with_markup_cents INTEGER,

    -- Schedule
    schedule_impact_days INTEGER DEFAULT 0,  -- Days added/subtracted from schedule

    -- Backup
    subcontractor_quotes TEXT,               -- JSON array of {sub, amount, scope}
    supporting_docs TEXT,                    -- JSON array of file paths

    -- Status
    status TEXT NOT NULL DEFAULT 'draft',    -- 'draft', 'submitted', 'approved', 'rejected', 'void'
    submitted_date TEXT,
    approved_date TEXT,
    approved_by TEXT,

    document_path TEXT,
    generated_by_skill TEXT DEFAULT 'change_order',

    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    created_by INTEGER REFERENCES team_members(id),
    UNIQUE(project_id, co_number)
);

-- ============================================================================
-- SKILL #10: SCHEDULE VARIANCE
-- ============================================================================

CREATE TABLE IF NOT EXISTS schedule_snapshots (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    snapshot_date TEXT NOT NULL,
    source_file_path TEXT,                   -- Path to uploaded schedule file
    planned_completion_date TEXT,
    projected_completion_date TEXT,
    variance_days INTEGER,                   -- Positive = behind, negative = ahead
    critical_path_items TEXT,                -- JSON array of critical path activities
    at_risk_items TEXT,                      -- JSON array of activities at risk
    analysis TEXT,                           -- AI-generated analysis
    recommendations TEXT,
    document_path TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    created_by INTEGER REFERENCES team_members(id)
);

-- ============================================================================
-- SKILL #11: SUBMITTALS
-- ============================================================================

CREATE TABLE IF NOT EXISTS submittals (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    submittal_number TEXT NOT NULL,          -- e.g., "03.30.001" (CSI-based numbering)
    title TEXT NOT NULL,
    spec_section TEXT,                       -- Spec section reference
    description TEXT,
    subcontractor_id INTEGER REFERENCES subcontractors(id) ON DELETE SET NULL,
    submitted_by TEXT,                       -- Company name if sub not in system

    -- Status tracking
    status TEXT NOT NULL DEFAULT 'pending',  -- 'pending', 'submitted', 'approved', 'approved_as_noted', 'revise_resubmit', 'rejected'
    revision_number INTEGER DEFAULT 0,
    submitted_date TEXT,
    required_date TEXT,                      -- When needed on site
    review_due_date TEXT,
    review_date TEXT,
    reviewed_by TEXT,
    review_comments TEXT,

    -- Tracking
    lead_time_days INTEGER,                  -- Manufacturing/delivery lead time
    document_path TEXT,
    is_critical_path INTEGER DEFAULT 0,

    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    created_by INTEGER REFERENCES team_members(id),
    UNIQUE(project_id, submittal_number, revision_number)
);

-- ============================================================================
-- SKILL #12: CONTRACT / INSURANCE CHECKER
-- ============================================================================

CREATE TABLE IF NOT EXISTS contract_reviews (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    document_name TEXT NOT NULL,
    document_type TEXT NOT NULL,             -- 'subcontract', 'prime_contract', 'insurance_cert', 'bond'
    source_file_path TEXT,
    review_date TEXT NOT NULL,

    -- Results
    risk_level TEXT,                         -- 'low', 'medium', 'high', 'critical'
    findings TEXT,                           -- JSON array of {item, severity, description, recommendation}
    missing_items TEXT,                      -- JSON array of required items not found
    non_standard_clauses TEXT,               -- JSON array of unusual provisions
    insurance_gaps TEXT,                     -- JSON array (for insurance reviews)
    compliance_score REAL,                   -- 0-100 compliance percentage
    summary TEXT,                            -- AI-generated executive summary
    recommendations TEXT,

    document_path TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    created_by INTEGER REFERENCES team_members(id)
);

-- ============================================================================
-- SKILL #13: PROPOSALS (uses knowledge base heavily)
-- ============================================================================

CREATE TABLE IF NOT EXISTS proposals (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    proposal_name TEXT NOT NULL,
    client_name TEXT NOT NULL,
    project_description TEXT,
    raw_input TEXT,                          -- User's rough notes about the opportunity
    rfp_file_path TEXT,                      -- Path to RFP document if provided
    proposal_type TEXT DEFAULT 'full',       -- 'full', 'letter', 'qualification'
    estimated_value_cents INTEGER,

    -- Content sections (AI-generated)
    executive_summary TEXT,
    approach TEXT,
    team_section TEXT,
    experience_section TEXT,
    schedule_section TEXT,
    safety_section TEXT,
    fee_narrative TEXT,

    status TEXT NOT NULL DEFAULT 'draft',    -- 'draft', 'review', 'submitted', 'won', 'lost'
    submitted_date TEXT,
    result TEXT,                             -- 'won', 'lost', 'no_decision'
    document_path TEXT,

    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    created_by INTEGER REFERENCES team_members(id)
);

-- ============================================================================
-- SKILL #14: BUDGET FORECASTER
-- ============================================================================

CREATE TABLE IF NOT EXISTS budget_forecasts (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    forecast_date TEXT NOT NULL,
    forecast_month TEXT,                     -- Target month: "2026-03"

    original_budget_cents INTEGER,
    approved_changes_cents INTEGER,
    current_budget_cents INTEGER,
    committed_costs_cents INTEGER,
    actual_costs_cents INTEGER,
    projected_final_cents INTEGER,
    variance_cents INTEGER,                  -- Current budget - projected final

    -- Detail
    cost_code_breakdown TEXT,                -- JSON array of {code, description, budget, actual, projected, variance}
    risk_items TEXT,                         -- JSON array of identified cost risks
    opportunity_items TEXT,                  -- JSON array of potential savings
    contingency_remaining_cents INTEGER,
    contingency_recommended_cents INTEGER,

    analysis TEXT,                           -- AI-generated narrative
    recommendations TEXT,
    document_path TEXT,
    excel_path TEXT,

    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    created_by INTEGER REFERENCES team_members(id)
);

-- ============================================================================
-- SKILL #15: CLOSEOUT ASSEMBLER
-- ============================================================================

CREATE TABLE IF NOT EXISTS closeout_packages (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    package_name TEXT NOT NULL DEFAULT 'Project Closeout Package',
    status TEXT NOT NULL DEFAULT 'in_progress', -- 'in_progress', 'complete', 'submitted'

    -- Checklist tracking (JSON arrays of {item, status, notes, date})
    required_documents TEXT,                 -- Warranty letters, as-builts, O&M manuals, etc.
    lien_waivers TEXT,                       -- Lien waiver status by sub
    final_inspections TEXT,                  -- Required inspections and status
    training_sessions TEXT,                  -- Owner training requirements
    spare_parts TEXT,                        -- Attic stock / spare parts inventory

    -- Financials
    final_contract_cents INTEGER,
    retention_held_cents INTEGER,
    pending_backcharges_cents INTEGER,

    -- Output
    cover_letter_path TEXT,
    checklist_path TEXT,
    document_path TEXT,

    substantial_completion_date TEXT,
    final_completion_date TEXT,

    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    created_by INTEGER REFERENCES team_members(id)
);

-- ============================================================================
-- SKILL #16: LESSONS LEARNED
-- ============================================================================

CREATE TABLE IF NOT EXISTS lessons_learned (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    category TEXT NOT NULL,                  -- 'scheduling', 'budget', 'subcontractor', 'design', 'safety', 'client', 'procurement', 'quality'
    subcategory TEXT,
    title TEXT NOT NULL,
    situation TEXT NOT NULL,                 -- What happened
    impact TEXT,                             -- What was the consequence
    lesson TEXT NOT NULL,                    -- What we learned
    recommendation TEXT,                     -- What to do differently
    applicable_project_types TEXT,           -- JSON array: ["commercial", "healthcare"]
    tags TEXT,                               -- JSON array for searchability
    severity TEXT DEFAULT 'medium',          -- 'low', 'medium', 'high', 'critical'
    source TEXT DEFAULT 'manual',            -- 'manual', 'meeting_minutes', 'daily_report', 'closeout'
    document_path TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    created_by INTEGER REFERENCES team_members(id)
);

CREATE INDEX IF NOT EXISTS idx_lessons_category ON lessons_learned(category);

-- ============================================================================
-- SKILL #17: CASE STUDIES
-- ============================================================================

CREATE TABLE IF NOT EXISTS case_studies (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    subtitle TEXT,
    raw_input TEXT,                          -- User's notes about project highlights
    executive_summary TEXT,
    challenge_section TEXT,
    solution_section TEXT,
    results_section TEXT,
    key_metrics TEXT,                        -- JSON: {on_time, on_budget, safety_record, sqft, etc.}
    testimonial TEXT,                        -- Client quote if available
    photo_paths TEXT,                        -- JSON array of photo paths
    target_audience TEXT,                    -- 'client', 'marketing', 'proposal'
    status TEXT NOT NULL DEFAULT 'draft',
    document_path TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    created_by INTEGER REFERENCES team_members(id)
);

-- ============================================================================
-- SKILL #18: INCIDENT REPORTS
-- ============================================================================

CREATE TABLE IF NOT EXISTS incident_reports (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    incident_number INTEGER NOT NULL,        -- Auto-incrementing per project
    incident_date TEXT NOT NULL,
    incident_time TEXT,
    report_date TEXT NOT NULL,

    -- Classification
    incident_type TEXT NOT NULL,             -- 'near_miss', 'first_aid', 'recordable', 'lost_time', 'fatality', 'property_damage', 'environmental'
    severity TEXT NOT NULL,                  -- 'minor', 'moderate', 'serious', 'critical'
    is_osha_recordable INTEGER DEFAULT 0,

    -- Details
    location TEXT NOT NULL,                  -- Where on site
    description TEXT NOT NULL,               -- AI-generated formal description
    raw_input TEXT,                          -- User's rough account
    involved_persons TEXT,                   -- JSON array of {name, company, role, injury}
    witnesses TEXT,                          -- JSON array of {name, company}
    immediate_actions TEXT,                  -- What was done immediately
    root_cause TEXT,
    contributing_factors TEXT,               -- JSON array
    corrective_actions TEXT,                 -- JSON array of {action, responsible, due_date}
    preventive_actions TEXT,                 -- JSON array

    -- Reporting
    reported_to_osha INTEGER DEFAULT 0,
    osha_report_date TEXT,
    insurance_notified INTEGER DEFAULT 0,
    client_notified INTEGER DEFAULT 0,

    document_path TEXT,
    status TEXT NOT NULL DEFAULT 'draft',    -- 'draft', 'submitted', 'under_review', 'closed'

    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    created_by INTEGER REFERENCES team_members(id),
    UNIQUE(project_id, incident_number)
);

-- ============================================================================
-- HISTORICAL DATA (feeds AI benchmarking and analytics)
-- ============================================================================

CREATE TABLE IF NOT EXISTS cost_history (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    csi_code TEXT NOT NULL,                  -- CSI division code: "03" for concrete, "26" for electrical
    csi_description TEXT,
    budget_cents INTEGER,
    actual_cents INTEGER,
    unit_cost_cents INTEGER,                 -- Cost per unit (per SF, per LF, etc.)
    unit_type TEXT,                          -- 'sf', 'lf', 'ea', 'ls', 'cy'
    quantity REAL,
    year INTEGER,
    region TEXT,                             -- Geographic region for cost normalization
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_cost_history_csi ON cost_history(csi_code);
CREATE INDEX IF NOT EXISTS idx_cost_history_project ON cost_history(project_id);

-- ============================================================================
-- SYSTEM TABLES
-- ============================================================================

CREATE TABLE IF NOT EXISTS api_usage (
    id INTEGER PRIMARY KEY,
    skill_name TEXT NOT NULL,
    model TEXT NOT NULL,                     -- 'claude-sonnet-4-5-20250929', 'claude-opus-4-6', etc.
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    total_tokens INTEGER NOT NULL,
    cost_cents INTEGER NOT NULL,             -- Cost in cents (e.g., 5 = $0.05)
    duration_ms INTEGER,                     -- Processing time in milliseconds
    success INTEGER NOT NULL DEFAULT 1,      -- 1 = success, 0 = failure
    error_message TEXT,                      -- Error details if failed
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_api_usage_skill ON api_usage(skill_name);
CREATE INDEX IF NOT EXISTS idx_api_usage_date ON api_usage(created_at);

CREATE TABLE IF NOT EXISTS generated_documents (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    skill_name TEXT NOT NULL,
    document_type TEXT NOT NULL,             -- 'docx', 'xlsx', 'pdf'
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size_bytes INTEGER,
    input_summary TEXT,                      -- Brief description of what was provided as input
    api_usage_id INTEGER REFERENCES api_usage(id) ON DELETE SET NULL,
    version INTEGER DEFAULT 1,              -- For regenerated documents
    is_current INTEGER DEFAULT 1,            -- 1 = latest version, 0 = superseded
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    created_by INTEGER REFERENCES team_members(id)
);

CREATE INDEX IF NOT EXISTS idx_generated_docs_project ON generated_documents(project_id);
CREATE INDEX IF NOT EXISTS idx_generated_docs_skill ON generated_documents(skill_name);

-- ============================================================================
-- CONFIGURATION & SETTINGS
-- ============================================================================

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- Default settings
INSERT OR IGNORE INTO settings (key, value, description) VALUES
    ('default_model', 'claude-sonnet-4-5-20250929', 'Default AI model for skill execution'),
    ('opus_model', 'claude-opus-4-6', 'Model for precision-critical skills'),
    ('daily_cost_limit_cents', '5000', 'Daily API cost cap in cents ($50)'),
    ('monthly_cost_limit_cents', '30000', 'Monthly API cost cap in cents ($300)'),
    ('output_directory', '~/KruppAI-Output', 'Default output directory for generated documents'),
    ('weather_enabled', '1', 'Enable automatic weather data in daily reports'),
    ('auto_backup', '1', 'Automatically backup database daily'),
    ('document_review_required', '1', 'Show review-required footer on all documents');

-- ============================================================================
-- VIEWS (convenience queries used by skills)
-- ============================================================================

-- Active project summary with team and financials
CREATE VIEW IF NOT EXISTS v_active_projects AS
SELECT
    p.*,
    (SELECT COUNT(*) FROM daily_reports dr WHERE dr.project_id = p.id) as total_daily_reports,
    (SELECT COUNT(*) FROM rfis r WHERE r.project_id = p.id) as total_rfis,
    (SELECT COUNT(*) FROM rfis r WHERE r.project_id = p.id AND r.status = 'submitted') as open_rfis,
    (SELECT COUNT(*) FROM change_orders co WHERE co.project_id = p.id) as total_change_orders,
    (SELECT COALESCE(SUM(co.total_with_markup_cents), 0) FROM change_orders co WHERE co.project_id = p.id AND co.status = 'approved') as approved_co_value_cents,
    (SELECT COUNT(*) FROM action_items ai WHERE ai.project_id = p.id AND ai.status = 'open') as open_action_items,
    (SELECT COUNT(*) FROM punch_items pi WHERE pi.project_id = p.id AND pi.status != 'complete') as open_punch_items
FROM projects p
WHERE p.status IN ('preconstruction', 'active', 'punch_list', 'closeout')
  AND p.is_archived = 0;

-- Open action items across all projects (for meeting minutes carry-forward)
CREATE VIEW IF NOT EXISTS v_open_action_items AS
SELECT
    ai.*,
    p.project_code,
    p.name as project_name,
    m.meeting_date as source_meeting_date,
    m.meeting_type as source_meeting_type
FROM action_items ai
JOIN projects p ON ai.project_id = p.id
LEFT JOIN meetings m ON ai.meeting_id = m.id
WHERE ai.status IN ('open', 'in_progress')
ORDER BY
    CASE ai.priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 WHEN 'normal' THEN 3 WHEN 'low' THEN 4 END,
    ai.due_date;

-- API cost summary by skill and month
CREATE VIEW IF NOT EXISTS v_api_cost_summary AS
SELECT
    skill_name,
    strftime('%Y-%m', created_at) as month,
    COUNT(*) as call_count,
    SUM(input_tokens) as total_input_tokens,
    SUM(output_tokens) as total_output_tokens,
    SUM(cost_cents) as total_cost_cents,
    AVG(duration_ms) as avg_duration_ms,
    SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as error_count
FROM api_usage
GROUP BY skill_name, strftime('%Y-%m', created_at);

-- Subcontractor performance across projects
CREATE VIEW IF NOT EXISTS v_subcontractor_performance AS
SELECT
    s.id as subcontractor_id,
    s.company_name,
    s.trade,
    COUNT(DISTINCT ps.project_id) as project_count,
    SUM(ps.contract_value_cents) as total_contract_value_cents,
    SUM(ps.change_order_total_cents) as total_co_value_cents,
    AVG(CAST(ps.change_order_total_cents AS REAL) / NULLIF(ps.contract_value_cents, 0) * 100) as avg_co_percent,
    (SELECT COUNT(*) FROM punch_items pi WHERE pi.subcontractor_id = s.id) as total_punch_items,
    (SELECT COUNT(*) FROM punch_items pi WHERE pi.subcontractor_id = s.id AND pi.status = 'complete') as completed_punch_items,
    s.rating
FROM subcontractors s
LEFT JOIN project_subcontractors ps ON s.id = ps.subcontractor_id
GROUP BY s.id;
