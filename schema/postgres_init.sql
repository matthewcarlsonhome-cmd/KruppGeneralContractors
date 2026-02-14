-- ============================================================================
-- KruppAI Database Schema v1.0 — PostgreSQL Edition
-- Compatible with: PostgreSQL 14+
-- Converted from: schema/init.sql (SQLite)
-- ============================================================================
-- CONVENTIONS:
--   - All tables use SERIAL PRIMARY KEY (auto-incrementing)
--   - Timestamps stored as TEXT in ISO-8601 format (preserves compatibility)
--   - Money stored as INTEGER in cents (avoids floating point issues)
--   - Boolean stored as INTEGER 0/1 (preserves compatibility with SQLite data)
--   - Foreign keys enforced natively by PostgreSQL
-- ============================================================================

-- ============================================================================
-- COMPANY & PERSONNEL
-- ============================================================================

CREATE TABLE IF NOT EXISTS company (
    id SERIAL PRIMARY KEY,
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
    logo_path TEXT,
    license_number TEXT,
    founded_year INTEGER,
    description TEXT,
    specialties TEXT,
    service_area TEXT,
    bonding_capacity_cents INTEGER,
    created_at TEXT NOT NULL DEFAULT (NOW()::text),
    updated_at TEXT NOT NULL DEFAULT (NOW()::text)
);

CREATE TABLE IF NOT EXISTS team_members (
    id SERIAL PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT UNIQUE,
    phone TEXT,
    role TEXT NOT NULL,
    title TEXT,
    bio TEXT,
    certifications TEXT,
    years_experience INTEGER,
    hire_date TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (NOW()::text),
    updated_at TEXT NOT NULL DEFAULT (NOW()::text)
);

-- ============================================================================
-- PROJECTS
-- ============================================================================

CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    project_code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    client_name TEXT,
    client_contact_name TEXT,
    client_contact_email TEXT,
    client_contact_phone TEXT,
    architect_firm TEXT,
    architect_contact TEXT,
    architect_email TEXT,
    owner_name TEXT,

    -- Location
    address TEXT,
    city TEXT,
    state TEXT,
    zip TEXT,
    latitude REAL,
    longitude REAL,

    -- Financials
    original_contract_cents INTEGER,
    current_contract_cents INTEGER,
    estimated_cost_cents INTEGER,

    -- Schedule
    notice_to_proceed_date TEXT,
    substantial_completion_date TEXT,
    final_completion_date TEXT,
    actual_start_date TEXT,
    actual_completion_date TEXT,
    current_percent_complete REAL DEFAULT 0,

    -- Classification
    project_type TEXT,
    delivery_method TEXT,
    contract_type TEXT,
    square_footage INTEGER,
    number_of_floors INTEGER,

    -- Status
    status TEXT NOT NULL DEFAULT 'active',
    is_archived INTEGER NOT NULL DEFAULT 0,

    created_at TEXT NOT NULL DEFAULT (NOW()::text),
    updated_at TEXT NOT NULL DEFAULT (NOW()::text)
);

CREATE TABLE IF NOT EXISTS project_team (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    team_member_id INTEGER NOT NULL REFERENCES team_members(id) ON DELETE CASCADE,
    project_role TEXT NOT NULL,
    is_primary INTEGER NOT NULL DEFAULT 0,
    assigned_date TEXT,
    removed_date TEXT,
    UNIQUE(project_id, team_member_id, project_role)
);

-- ============================================================================
-- SUBCONTRACTORS
-- ============================================================================

CREATE TABLE IF NOT EXISTS subcontractors (
    id SERIAL PRIMARY KEY,
    company_name TEXT NOT NULL,
    contact_name TEXT,
    email TEXT,
    phone TEXT,
    address TEXT,
    city TEXT,
    state TEXT,
    zip TEXT,
    trade TEXT NOT NULL,
    csi_division TEXT,
    license_number TEXT,
    insurance_expiry TEXT,
    bonding_capacity_cents INTEGER,
    rating REAL,
    notes TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (NOW()::text),
    updated_at TEXT NOT NULL DEFAULT (NOW()::text)
);

CREATE TABLE IF NOT EXISTS project_subcontractors (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    subcontractor_id INTEGER NOT NULL REFERENCES subcontractors(id) ON DELETE CASCADE,
    contract_value_cents INTEGER,
    scope_description TEXT,
    contract_status TEXT DEFAULT 'pending',
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
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    report_date TEXT NOT NULL,
    report_number INTEGER,

    -- Weather (auto-populated via Open-Meteo API or manual)
    weather_high_f REAL,
    weather_low_f REAL,
    weather_conditions TEXT,
    weather_precipitation_in REAL,
    weather_wind_mph REAL,
    weather_source TEXT DEFAULT 'manual',

    -- Workforce
    krupp_workers INTEGER DEFAULT 0,
    sub_workers INTEGER DEFAULT 0,
    total_workers INTEGER DEFAULT 0,

    -- Content (raw input and AI-generated)
    raw_notes TEXT NOT NULL,
    work_performed TEXT,
    materials_delivered TEXT,
    equipment_on_site TEXT,
    visitors TEXT,
    delays TEXT,
    safety_observations TEXT,
    quality_observations TEXT,
    issues TEXT,

    -- Output
    document_path TEXT,
    generated_by_skill TEXT DEFAULT 'daily_report',

    -- Workforce detail (JSON array)
    workforce_detail TEXT,

    created_at TEXT NOT NULL DEFAULT (NOW()::text),
    created_by INTEGER REFERENCES team_members(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_daily_reports_project_date
    ON daily_reports(project_id, report_date);

-- ============================================================================
-- SKILL #2: RFIs
-- ============================================================================

CREATE TABLE IF NOT EXISTS rfis (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    rfi_number INTEGER NOT NULL,
    subject TEXT NOT NULL,
    question TEXT NOT NULL,
    raw_input TEXT,
    spec_reference TEXT,
    drawing_reference TEXT,
    cost_impact TEXT DEFAULT 'unknown',
    schedule_impact TEXT DEFAULT 'unknown',
    suggested_solution TEXT,
    priority TEXT DEFAULT 'normal',

    -- Routing
    assigned_to TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    submitted_date TEXT,
    response_due_date TEXT,
    response_date TEXT,
    response_text TEXT,
    responded_by TEXT,

    -- Output
    document_path TEXT,
    generated_by_skill TEXT DEFAULT 'rfi_generator',

    created_at TEXT NOT NULL DEFAULT (NOW()::text),
    created_by INTEGER REFERENCES team_members(id),
    UNIQUE(project_id, rfi_number)
);

-- ============================================================================
-- SKILL #3: MEETING MINUTES
-- ============================================================================

CREATE TABLE IF NOT EXISTS meetings (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    meeting_number INTEGER,
    meeting_type TEXT NOT NULL DEFAULT 'oac',
    meeting_date TEXT NOT NULL,
    start_time TEXT,
    end_time TEXT,
    location TEXT,

    -- Attendees (JSON array)
    attendees TEXT,

    -- Content
    raw_notes TEXT NOT NULL,
    formatted_minutes TEXT,
    agenda_items TEXT,

    -- Key decisions (JSON array)
    decisions TEXT,

    -- Next meeting
    next_meeting_date TEXT,
    next_meeting_location TEXT,

    -- Output
    document_path TEXT,
    generated_by_skill TEXT DEFAULT 'meeting_minutes',

    created_at TEXT NOT NULL DEFAULT (NOW()::text),
    created_by INTEGER REFERENCES team_members(id)
);

CREATE TABLE IF NOT EXISTS action_items (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    meeting_id INTEGER REFERENCES meetings(id) ON DELETE SET NULL,
    source_skill TEXT,
    description TEXT NOT NULL,
    assigned_to TEXT NOT NULL,
    due_date TEXT,
    priority TEXT DEFAULT 'normal',
    status TEXT NOT NULL DEFAULT 'open',
    completion_date TEXT,
    notes TEXT,
    carried_from_meeting_id INTEGER REFERENCES meetings(id),
    created_at TEXT NOT NULL DEFAULT (NOW()::text)
);

CREATE INDEX IF NOT EXISTS idx_action_items_project_status
    ON action_items(project_id, status);

-- ============================================================================
-- SKILL #4: CLIENT UPDATES (stored as generated documents, no dedicated table)
-- ============================================================================

-- ============================================================================
-- SKILL #5: SAFETY TALKS
-- ============================================================================

CREATE TABLE IF NOT EXISTS safety_talks (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    topic TEXT NOT NULL,
    raw_input TEXT,
    talk_content TEXT,
    applicable_trades TEXT,
    season TEXT,
    osha_references TEXT,
    document_path TEXT,
    talk_date TEXT,
    attendee_count INTEGER,
    created_at TEXT NOT NULL DEFAULT (NOW()::text),
    created_by INTEGER REFERENCES team_members(id)
);

-- ============================================================================
-- SKILL #6: PUNCH LIST
-- ============================================================================

CREATE TABLE IF NOT EXISTS punch_lists (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    list_name TEXT NOT NULL,
    inspection_date TEXT,
    inspector_name TEXT,
    area TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    total_items INTEGER DEFAULT 0,
    completed_items INTEGER DEFAULT 0,
    document_path TEXT,
    excel_path TEXT,
    raw_input TEXT,
    created_at TEXT NOT NULL DEFAULT (NOW()::text),
    created_by INTEGER REFERENCES team_members(id)
);

CREATE TABLE IF NOT EXISTS punch_items (
    id SERIAL PRIMARY KEY,
    punch_list_id INTEGER NOT NULL REFERENCES punch_lists(id) ON DELETE CASCADE,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    item_number INTEGER NOT NULL,
    location TEXT NOT NULL,
    description TEXT NOT NULL,
    trade TEXT,
    subcontractor_id INTEGER REFERENCES subcontractors(id) ON DELETE SET NULL,
    assigned_to TEXT,
    priority TEXT DEFAULT 'normal',
    status TEXT NOT NULL DEFAULT 'open',
    due_date TEXT,
    completion_date TEXT,
    notes TEXT,
    photo_path TEXT,
    created_at TEXT NOT NULL DEFAULT (NOW()::text)
);

CREATE INDEX IF NOT EXISTS idx_punch_items_list ON punch_items(punch_list_id);
CREATE INDEX IF NOT EXISTS idx_punch_items_status ON punch_items(project_id, status);

-- ============================================================================
-- SKILL #7: ESTIMATE REVIEWER
-- ============================================================================

CREATE TABLE IF NOT EXISTS estimate_reviews (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    estimate_name TEXT NOT NULL,
    source_file_path TEXT,
    total_estimate_cents INTEGER,
    total_benchmark_cents INTEGER,
    variance_percent REAL,
    findings TEXT,
    high_risk_items TEXT,
    recommendations TEXT,
    document_path TEXT,
    created_at TEXT NOT NULL DEFAULT (NOW()::text),
    created_by INTEGER REFERENCES team_members(id)
);

-- ============================================================================
-- SKILL #8: BID COMPARISON
-- ============================================================================

CREATE TABLE IF NOT EXISTS bid_comparisons (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    trade TEXT NOT NULL,
    comparison_name TEXT NOT NULL,
    bid_date TEXT,
    number_of_bidders INTEGER,
    low_bid_cents INTEGER,
    high_bid_cents INTEGER,
    spread_percent REAL,
    recommendation TEXT,
    analysis TEXT,
    bidder_data TEXT,
    document_path TEXT,
    excel_path TEXT,
    created_at TEXT NOT NULL DEFAULT (NOW()::text),
    created_by INTEGER REFERENCES team_members(id)
);

-- ============================================================================
-- SKILL #9: CHANGE ORDERS
-- ============================================================================

CREATE TABLE IF NOT EXISTS change_orders (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    co_number INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    raw_input TEXT,
    reason TEXT,

    -- Financial
    cost_cents INTEGER,
    markup_percent REAL,
    total_with_markup_cents INTEGER,

    -- Schedule
    schedule_impact_days INTEGER DEFAULT 0,

    -- Backup
    subcontractor_quotes TEXT,
    supporting_docs TEXT,

    -- Status
    status TEXT NOT NULL DEFAULT 'draft',
    submitted_date TEXT,
    approved_date TEXT,
    approved_by TEXT,

    document_path TEXT,
    generated_by_skill TEXT DEFAULT 'change_order',

    created_at TEXT NOT NULL DEFAULT (NOW()::text),
    created_by INTEGER REFERENCES team_members(id),
    UNIQUE(project_id, co_number)
);

-- ============================================================================
-- SKILL #10: SCHEDULE VARIANCE
-- ============================================================================

CREATE TABLE IF NOT EXISTS schedule_snapshots (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    snapshot_date TEXT NOT NULL,
    source_file_path TEXT,
    planned_completion_date TEXT,
    projected_completion_date TEXT,
    variance_days INTEGER,
    critical_path_items TEXT,
    at_risk_items TEXT,
    analysis TEXT,
    recommendations TEXT,
    document_path TEXT,
    created_at TEXT NOT NULL DEFAULT (NOW()::text),
    created_by INTEGER REFERENCES team_members(id)
);

-- ============================================================================
-- SKILL #11: SUBMITTALS
-- ============================================================================

CREATE TABLE IF NOT EXISTS submittals (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    submittal_number TEXT NOT NULL,
    title TEXT NOT NULL,
    spec_section TEXT,
    description TEXT,
    subcontractor_id INTEGER REFERENCES subcontractors(id) ON DELETE SET NULL,
    submitted_by TEXT,

    -- Status tracking
    status TEXT NOT NULL DEFAULT 'pending',
    revision_number INTEGER DEFAULT 0,
    submitted_date TEXT,
    required_date TEXT,
    review_due_date TEXT,
    review_date TEXT,
    reviewed_by TEXT,
    review_comments TEXT,

    -- Tracking
    lead_time_days INTEGER,
    document_path TEXT,
    is_critical_path INTEGER DEFAULT 0,

    created_at TEXT NOT NULL DEFAULT (NOW()::text),
    created_by INTEGER REFERENCES team_members(id),
    UNIQUE(project_id, submittal_number, revision_number)
);

-- ============================================================================
-- SKILL #12: CONTRACT / INSURANCE CHECKER
-- ============================================================================

CREATE TABLE IF NOT EXISTS contract_reviews (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    document_name TEXT NOT NULL,
    document_type TEXT NOT NULL,
    source_file_path TEXT,
    review_date TEXT NOT NULL,

    -- Results
    risk_level TEXT,
    findings TEXT,
    missing_items TEXT,
    non_standard_clauses TEXT,
    insurance_gaps TEXT,
    compliance_score REAL,
    summary TEXT,
    recommendations TEXT,

    document_path TEXT,
    created_at TEXT NOT NULL DEFAULT (NOW()::text),
    created_by INTEGER REFERENCES team_members(id)
);

-- ============================================================================
-- SKILL #13: PROPOSALS
-- ============================================================================

CREATE TABLE IF NOT EXISTS proposals (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    proposal_name TEXT NOT NULL,
    client_name TEXT NOT NULL,
    project_description TEXT,
    raw_input TEXT,
    rfp_file_path TEXT,
    proposal_type TEXT DEFAULT 'full',
    estimated_value_cents INTEGER,

    -- Content sections (AI-generated)
    executive_summary TEXT,
    approach TEXT,
    team_section TEXT,
    experience_section TEXT,
    schedule_section TEXT,
    safety_section TEXT,
    fee_narrative TEXT,

    status TEXT NOT NULL DEFAULT 'draft',
    submitted_date TEXT,
    result TEXT,
    document_path TEXT,

    created_at TEXT NOT NULL DEFAULT (NOW()::text),
    created_by INTEGER REFERENCES team_members(id)
);

-- ============================================================================
-- SKILL #14: BUDGET FORECASTER
-- ============================================================================

CREATE TABLE IF NOT EXISTS budget_forecasts (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    forecast_date TEXT NOT NULL,
    forecast_month TEXT,

    original_budget_cents INTEGER,
    approved_changes_cents INTEGER,
    current_budget_cents INTEGER,
    committed_costs_cents INTEGER,
    actual_costs_cents INTEGER,
    projected_final_cents INTEGER,
    variance_cents INTEGER,

    -- Detail
    cost_code_breakdown TEXT,
    risk_items TEXT,
    opportunity_items TEXT,
    contingency_remaining_cents INTEGER,
    contingency_recommended_cents INTEGER,

    analysis TEXT,
    recommendations TEXT,
    document_path TEXT,
    excel_path TEXT,

    created_at TEXT NOT NULL DEFAULT (NOW()::text),
    created_by INTEGER REFERENCES team_members(id)
);

-- ============================================================================
-- SKILL #15: CLOSEOUT ASSEMBLER
-- ============================================================================

CREATE TABLE IF NOT EXISTS closeout_packages (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    package_name TEXT NOT NULL DEFAULT 'Project Closeout Package',
    status TEXT NOT NULL DEFAULT 'in_progress',

    -- Checklist tracking (JSON arrays)
    required_documents TEXT,
    lien_waivers TEXT,
    final_inspections TEXT,
    training_sessions TEXT,
    spare_parts TEXT,

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

    created_at TEXT NOT NULL DEFAULT (NOW()::text),
    created_by INTEGER REFERENCES team_members(id)
);

-- ============================================================================
-- SKILL #16: LESSONS LEARNED
-- ============================================================================

CREATE TABLE IF NOT EXISTS lessons_learned (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    category TEXT NOT NULL,
    subcategory TEXT,
    title TEXT NOT NULL,
    situation TEXT NOT NULL,
    impact TEXT,
    lesson TEXT NOT NULL,
    recommendation TEXT,
    applicable_project_types TEXT,
    tags TEXT,
    severity TEXT DEFAULT 'medium',
    source TEXT DEFAULT 'manual',
    document_path TEXT,
    created_at TEXT NOT NULL DEFAULT (NOW()::text),
    created_by INTEGER REFERENCES team_members(id)
);

CREATE INDEX IF NOT EXISTS idx_lessons_category ON lessons_learned(category);

-- ============================================================================
-- SKILL #17: CASE STUDIES
-- ============================================================================

CREATE TABLE IF NOT EXISTS case_studies (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    subtitle TEXT,
    raw_input TEXT,
    executive_summary TEXT,
    challenge_section TEXT,
    solution_section TEXT,
    results_section TEXT,
    key_metrics TEXT,
    testimonial TEXT,
    photo_paths TEXT,
    target_audience TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    document_path TEXT,
    created_at TEXT NOT NULL DEFAULT (NOW()::text),
    created_by INTEGER REFERENCES team_members(id)
);

-- ============================================================================
-- SKILL #18: INCIDENT REPORTS
-- ============================================================================

CREATE TABLE IF NOT EXISTS incident_reports (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    incident_number INTEGER NOT NULL,
    incident_date TEXT NOT NULL,
    incident_time TEXT,
    report_date TEXT NOT NULL,

    -- Classification
    incident_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    is_osha_recordable INTEGER DEFAULT 0,

    -- Details
    location TEXT NOT NULL,
    description TEXT NOT NULL,
    raw_input TEXT,
    involved_persons TEXT,
    witnesses TEXT,
    immediate_actions TEXT,
    root_cause TEXT,
    contributing_factors TEXT,
    corrective_actions TEXT,
    preventive_actions TEXT,

    -- Reporting
    reported_to_osha INTEGER DEFAULT 0,
    osha_report_date TEXT,
    insurance_notified INTEGER DEFAULT 0,
    client_notified INTEGER DEFAULT 0,

    document_path TEXT,
    status TEXT NOT NULL DEFAULT 'draft',

    created_at TEXT NOT NULL DEFAULT (NOW()::text),
    created_by INTEGER REFERENCES team_members(id),
    UNIQUE(project_id, incident_number)
);

-- ============================================================================
-- HISTORICAL DATA
-- ============================================================================

CREATE TABLE IF NOT EXISTS cost_history (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    csi_code TEXT NOT NULL,
    csi_description TEXT,
    budget_cents INTEGER,
    actual_cents INTEGER,
    unit_cost_cents INTEGER,
    unit_type TEXT,
    quantity REAL,
    year INTEGER,
    region TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (NOW()::text)
);

CREATE INDEX IF NOT EXISTS idx_cost_history_csi ON cost_history(csi_code);
CREATE INDEX IF NOT EXISTS idx_cost_history_project ON cost_history(project_id);

-- ============================================================================
-- SYSTEM TABLES
-- ============================================================================

CREATE TABLE IF NOT EXISTS api_usage (
    id SERIAL PRIMARY KEY,
    skill_name TEXT NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    total_tokens INTEGER NOT NULL,
    cost_cents INTEGER NOT NULL,
    duration_ms INTEGER,
    success INTEGER NOT NULL DEFAULT 1,
    error_message TEXT,
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT (NOW()::text)
);

CREATE INDEX IF NOT EXISTS idx_api_usage_skill ON api_usage(skill_name);
CREATE INDEX IF NOT EXISTS idx_api_usage_date ON api_usage(created_at);

CREATE TABLE IF NOT EXISTS generated_documents (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    skill_name TEXT NOT NULL,
    document_type TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size_bytes INTEGER,
    input_summary TEXT,
    api_usage_id INTEGER REFERENCES api_usage(id) ON DELETE SET NULL,
    version INTEGER DEFAULT 1,
    is_current INTEGER DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (NOW()::text),
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
    updated_at TEXT NOT NULL DEFAULT (NOW()::text)
);

-- Default settings
INSERT INTO settings (key, value, description) VALUES
    ('default_model', 'claude-sonnet-4-5-20250929', 'Default AI model for skill execution'),
    ('opus_model', 'claude-opus-4-6', 'Model for precision-critical skills'),
    ('daily_cost_limit_cents', '5000', 'Daily API cost cap in cents ($50)'),
    ('monthly_cost_limit_cents', '30000', 'Monthly API cost cap in cents ($300)'),
    ('output_directory', '~/KruppAI-Output', 'Default output directory for generated documents'),
    ('weather_enabled', '1', 'Enable automatic weather data in daily reports'),
    ('auto_backup', '1', 'Automatically backup database daily'),
    ('document_review_required', '1', 'Show review-required footer on all documents')
ON CONFLICT DO NOTHING;

-- ============================================================================
-- VIEWS
-- ============================================================================

-- Active project summary with team and financials
CREATE OR REPLACE VIEW v_active_projects AS
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

-- Open action items across all projects
CREATE OR REPLACE VIEW v_open_action_items AS
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
CREATE OR REPLACE VIEW v_api_cost_summary AS
SELECT
    skill_name,
    to_char(created_at::timestamp, 'YYYY-MM') as month,
    COUNT(*) as call_count,
    SUM(input_tokens) as total_input_tokens,
    SUM(output_tokens) as total_output_tokens,
    SUM(cost_cents) as total_cost_cents,
    AVG(duration_ms) as avg_duration_ms,
    SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as error_count
FROM api_usage
GROUP BY skill_name, to_char(created_at::timestamp, 'YYYY-MM');

-- Subcontractor performance across projects
CREATE OR REPLACE VIEW v_subcontractor_performance AS
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
GROUP BY s.id, s.company_name, s.trade, s.rating;
