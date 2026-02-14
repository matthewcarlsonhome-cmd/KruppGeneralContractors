/* ====================================================================== */
/* KruppAI — Frontend Application                                         */
/* Project-first flow with rich skill descriptions and workflow hints      */
/* ====================================================================== */

(function () {
    "use strict";

    var API = "/api/v1";

    // ------------------------------------------------------------------ //
    // Skill Icons                                                         //
    // ------------------------------------------------------------------ //
    var ICONS = {
        daily_report:       "\uD83D\uDCCB",
        rfi_generator:      "\u2753",
        meeting_minutes:    "\uD83D\uDDD3\uFE0F",
        client_update:      "\u2709\uFE0F",
        safety_talk:        "\u26D1\uFE0F",
        punch_list:         "\u2705",
        estimate_reviewer:  "\uD83D\uDCB0",
        bid_comparison:     "\uD83D\uDCCA",
        change_order:       "\uD83D\uDD04",
        schedule_variance:  "\uD83D\uDCC5",
        submittal_tracker:  "\uD83D\uDCE6",
        contract_checker:   "\uD83D\uDCDC",
        proposal_generator: "\uD83D\uDCC4",
        budget_forecaster:  "\uD83D\uDCC8",
        closeout_assembler: "\uD83C\uDFC1",
        lessons_learned:    "\uD83D\uDCA1",
        case_study:         "\uD83C\uDFD7\uFE0F",
        incident_report:    "\u26A0\uFE0F",
    };

    // ------------------------------------------------------------------ //
    // Detailed Skill Information                                          //
    // ------------------------------------------------------------------ //
    var SKILL_DETAILS = {
        daily_report: {
            what: "Transforms your rough daily field notes into a professional daily construction report with weather data, crew info, and work descriptions.",
            input: "Select your project, then type or paste your field notes from the day — activities, crews on site, equipment used, issues encountered, and progress made.",
            process: "AI analyzes your notes, automatically pulls weather data for the job site, organizes content into industry-standard sections (workforce, equipment, work performed, issues, safety).",
            deliverable: "Branded DOCX daily field report ready for distribution to the project team and client.",
            connects: "Feeds into Client Update letters and Meeting Minutes action items.",
            next_skill: "client_update"
        },
        rfi_generator: {
            what: "Converts issue descriptions into formal Request for Information (RFI) documents with proper numbering, routing, and tracking fields.",
            input: "Select your project and describe the issue or question that needs clarification from the architect, engineer, or owner.",
            process: "AI structures your issue into a formal RFI with background context, clear question, suggested resolution, and impact assessment. Auto-numbers sequentially per project.",
            deliverable: "Branded DOCX RFI document ready for submission to the design team or owner.",
            connects: "May trigger a Change Order if the response involves scope/cost changes. Track open RFIs in Meeting Minutes.",
            next_skill: "change_order"
        },
        meeting_minutes: {
            what: "Transforms raw meeting notes into formatted minutes with attendees, discussion summaries, decisions made, and action items with owners and due dates.",
            input: "Select your project, choose the meeting type (OAC, Subcontractor, Safety, etc.), then enter your rough notes from the meeting.",
            process: "AI organizes your notes into professional minutes with clear sections: attendees, old business, new business, decisions, and action items with assigned owners.",
            deliverable: "Branded DOCX meeting minutes document ready for distribution to all attendees.",
            connects: "Action items flow into daily tracking. Decisions may trigger RFIs or Change Orders.",
            next_skill: "daily_report"
        },
        client_update: {
            what: "Generates a professional project status letter for the client covering progress, schedule status, budget overview, and upcoming milestones.",
            input: "Select your project and enter notes about current status — what happened this week, milestones hit, upcoming work, and any concerns.",
            process: "AI pulls project context (team, subs, recent activity) and creates a polished executive status letter with professional language appropriate for client communication.",
            deliverable: "Branded DOCX client letter on Krupp letterhead, ready for PM signature and sending.",
            connects: "Uses data from Daily Reports and Budget Forecaster. Often follows up after OAC Meeting Minutes.",
            next_skill: "meeting_minutes"
        },
        safety_talk: {
            what: "Generates a complete toolbox safety talk document on any construction safety topic, ready for immediate field use by foremen and superintendents.",
            input: "Enter a safety topic — e.g., 'Fall protection', 'Electrical safety', 'Heat illness prevention', 'Trenching and excavation'.",
            process: "AI generates a comprehensive but field-friendly safety talk with OSHA regulatory references, hazard identification, protective measures, and crew discussion questions.",
            deliverable: "Branded DOCX toolbox talk document. Print and use at the next morning huddle.",
            connects: "If an incident occurs, follow up with an Incident Report. Safety topics often come from project risk assessments.",
            next_skill: "incident_report"
        },
        punch_list: {
            what: "Transforms walk-through observations into an organized punch list with locations, responsible trades, priority levels, and status tracking.",
            input: "Select your project and enter your walk-through notes — describe each deficiency you observed, where it is, and what trade is responsible.",
            process: "AI categorizes each item by trade and location, assigns priority levels (critical, high, normal, low), and generates sequential tracking numbers.",
            deliverable: "Branded DOCX punch list organized by area/room and trade, ready for distribution to subcontractors.",
            connects: "Punch list completion is required before Closeout Assembly. Track items in Meeting Minutes.",
            next_skill: "closeout_assembler"
        },
        estimate_reviewer: {
            what: "Reviews a cost estimate file against industry benchmarks and flags anomalies, missing line items, unit price outliers, and potential risks.",
            input: "Upload an estimate spreadsheet (XLSX or CSV). The file should contain line items with descriptions, quantities, units, and costs.",
            process: "AI (using the advanced Opus model for precision) analyzes each line item against industry norms, identifies outliers, checks for missing scope, and assesses overall estimate completeness.",
            deliverable: "Branded DOCX review report with detailed findings, variance analysis, risk assessment, and recommendations.",
            connects: "Reviewed estimates inform Budget Forecasting. Compare against actual bids with Bid Comparison.",
            next_skill: "budget_forecaster"
        },
        bid_comparison: {
            what: "Compares multiple subcontractor bids side-by-side with normalized analysis and recommends the best value option.",
            input: "Select your project, specify the trade/scope being bid, and enter bid details — bidder names, amounts, inclusions, exclusions, and any qualifications.",
            process: "AI creates a normalized comparison matrix, identifies scope gaps between bidders, flags unusually high or low bids, and provides a clear recommendation with rationale.",
            deliverable: "Branded DOCX comparison narrative plus XLSX with side-by-side bid matrix.",
            connects: "Follows Estimate Review. Selected sub may need Contract Checking before award.",
            next_skill: "contract_checker"
        },
        change_order: {
            what: "Generates a formal change order proposal from rough descriptions of scope changes, with cost/schedule impact analysis and professional justification.",
            input: "Select your project, describe the scope change in detail, and explain why the change is needed (owner request, field condition, design error, etc.).",
            process: "AI structures the change into a formal CO document with detailed scope description, cost breakdown, schedule impact, justification, and supporting references.",
            deliverable: "Branded DOCX change order document with auto-incrementing CO number, ready for owner submission.",
            connects: "Often triggered by RFI responses. Change orders affect the Budget Forecast and should be discussed in Meeting Minutes.",
            next_skill: "budget_forecaster"
        },
        schedule_variance: {
            what: "Analyzes a project schedule for variances from baseline, critical path risks, float consumption, and potential delay impacts.",
            input: "Select your project and upload a schedule export file (XLSX) with task names, planned dates, actual dates, and percent complete.",
            process: "AI identifies tasks behind schedule, analyzes critical path impacts, calculates float consumption, and provides mitigation recommendations.",
            deliverable: "Branded DOCX variance analysis report with executive summary, detailed findings, and recommended recovery actions.",
            connects: "Schedule status feeds into Client Updates. Delays may trigger Change Orders for time extensions.",
            next_skill: "client_update"
        },
        submittal_tracker: {
            what: "Analyzes a submittal log to flag overdue items, at-risk submittals that could impact the schedule, and missing required submittals.",
            input: "Select your project and upload your submittal log (XLSX) with submittal numbers, descriptions, due dates, and current status.",
            process: "AI reviews each submittal against its due date, identifies bottlenecks in the review chain, and prioritizes items that could cause procurement delays.",
            deliverable: "Branded DOCX tracker report with priority action items, organized by urgency and trade.",
            connects: "Overdue submittals affect the Schedule Variance. Discuss blockers in OAC Meeting Minutes.",
            next_skill: "schedule_variance"
        },
        contract_checker: {
            what: "Reviews a contract document or insurance certificate for compliance gaps, risk exposure, missing provisions, and non-standard clauses.",
            input: "Upload a contract or certificate of insurance file (PDF or DOCX). The AI will review the full document.",
            process: "AI (using the advanced Opus model for legal precision) performs clause-by-clause review against industry standards, identifies risks, missing protections, and non-standard terms.",
            deliverable: "Branded DOCX review report with findings organized by risk level — critical, high, medium, and informational.",
            connects: "Review contracts before signing. Ensure insurance matches contract requirements. Feeds into Proposal Generator for contract alignment.",
            next_skill: "proposal_generator"
        },
        proposal_generator: {
            what: "Generates a comprehensive project proposal leveraging Krupp's company profile, past project experience, and team qualifications.",
            input: "Select your project and enter scope notes — project description, your approach, key differentiators, and any specific client requirements.",
            process: "AI (using the advanced Opus model) creates a full proposal with executive summary, company overview, scope of work, approach, timeline, team qualifications, and relevant experience.",
            deliverable: "Branded DOCX proposal document with professional formatting, ready for client presentation.",
            connects: "Reference Case Studies for past project evidence. After award, use Contract Checker on the resulting agreement.",
            next_skill: "case_study"
        },
        budget_forecaster: {
            what: "Analyzes job cost data to forecast final project cost, identify budget variances, and project cash flow trends.",
            input: "Select your project and upload a job cost report (XLSX) with cost codes, budgeted amounts, committed costs, and actual costs to date.",
            process: "AI analyzes cost-to-date vs. budget for each cost code, projects final costs based on trends, and identifies areas of concern with specific recommendations.",
            deliverable: "Branded DOCX narrative report plus XLSX workbook with three forecast sheets: summary, detail by cost code, and cash flow projection.",
            connects: "Change Orders affect the budget. Budget status feeds into Client Update letters. At project end, informs Closeout Assembly.",
            next_skill: "client_update"
        },
        closeout_assembler: {
            what: "Generates a comprehensive project closeout documentation checklist and professional cover letter for project handoff.",
            input: "Select your project. The AI pulls all project context (subs, documents, open items) to generate the closeout package.",
            process: "AI creates a categorized checklist covering five areas: Contractual, Technical, Financial, Owner Turnover, and Regulatory. Identifies what's complete and what's outstanding.",
            deliverable: "Branded DOCX cover letter plus XLSX closeout tracker with status for every required item.",
            connects: "Requires Punch List completion. Should capture Lessons Learned before the team disperses. Final step in the project lifecycle.",
            next_skill: "lessons_learned"
        },
        lessons_learned: {
            what: "Compiles and structures project lessons learned for institutional knowledge capture, organized by severity and category.",
            input: "Select your project and enter observations — what went well, what went poorly, what you'd do differently next time.",
            process: "AI categorizes lessons by severity (critical, high, medium, low) and topic, identifies patterns, checks for duplicates against existing lessons, and stores each lesson individually.",
            deliverable: "Branded DOCX lessons learned report organized by category and severity.",
            connects: "Lessons feed into future Proposals as institutional knowledge. Build Case Studies from successful projects.",
            next_skill: "case_study"
        },
        case_study: {
            what: "Generates a professional marketing case study from project data, suitable for proposals, website, and business development materials.",
            input: "Select your project and enter highlights — key challenges overcome, innovative solutions, notable results, and client feedback.",
            process: "AI creates a compelling narrative case study with sections: Project Overview, Challenge, Solution/Approach, Results/Impact, and Key Takeaways.",
            deliverable: "Branded DOCX case study document formatted for marketing use.",
            connects: "Case studies are referenced in Proposals. Source material comes from Lessons Learned and project data.",
            next_skill: "proposal_generator"
        },
        incident_report: {
            what: "Documents a safety incident or near miss with OSHA recordability assessment, root cause analysis, and corrective action plan.",
            input: "Select your project and enter incident details — what happened, when, where, who was involved, injuries, and immediate actions taken.",
            process: "AI generates a formal incident report with timeline, root cause analysis, OSHA recordability assessment, witness statements framework, and required corrective actions.",
            deliverable: "Branded DOCX incident report with auto-incrementing incident number and all required regulatory fields.",
            connects: "Follow up with a Safety Talk on the relevant topic. Incidents are part of the project record for Closeout Assembly.",
            next_skill: "safety_talk"
        }
    };

    var PHASE_LABELS = {
        1: { name: "Field & Communication", desc: "Daily operations — the documents your team creates and shares every day on active projects." },
        2: { name: "Analysis & Review", desc: "Document analysis — review estimates, compare bids, track submittals, and check contracts." },
        3: { name: "Strategic & Institutional", desc: "Big-picture documents — proposals, forecasts, closeout packages, and institutional knowledge." },
    };

    var PARAM_CONFIG = {
        project: { label: "Project", type: "project-select" },
        notes:   { label: "Notes / Details", type: "textarea", placeholder: "Enter your field notes, observations, or details here. The more context you provide, the better the output." },
        issue:   { label: "Issue Description", type: "textarea", placeholder: "Describe the issue or question that needs clarification. Include relevant drawing/spec references." },
        type:    { label: "Meeting Type", type: "select", options: ["OAC Meeting", "Subcontractor Meeting", "Safety Meeting", "Internal Team Meeting", "Pre-Construction Meeting", "Closeout Meeting", "Other"] },
        topic:   { label: "Safety Topic", type: "text", placeholder: "e.g., Fall protection, Electrical safety, Heat illness, Trenching" },
        description: { label: "Change Description", type: "textarea", placeholder: "Describe the scope change in detail — what work is being added, modified, or removed." },
        reason:  { label: "Reason for Change", type: "textarea", placeholder: "Explain why this change is needed — owner request, field condition, design error, etc." },
        trade:   { label: "Trade / Scope", type: "text", placeholder: "e.g., Electrical, Plumbing, HVAC, Concrete" },
        bids:    { label: "Bid Details", type: "textarea", placeholder: "Enter bid information: bidder names, amounts, scope inclusions/exclusions, and qualifications." },
        file:    { label: "Upload File", type: "file" },
    };

    var QUICK_ACTIONS = [
        "daily_report", "rfi_generator", "meeting_minutes", "client_update",
        "safety_talk", "punch_list", "change_order", "incident_report",
    ];

    // ------------------------------------------------------------------ //
    // State                                                               //
    // ------------------------------------------------------------------ //
    var skills = [];
    var projects = [];
    var activeProject = null; // project_code of active project
    var currentView = "dashboard";

    // ------------------------------------------------------------------ //
    // API Client                                                          //
    // ------------------------------------------------------------------ //
    function apiGet(path) {
        return fetch(API + path).then(function (r) {
            if (!r.ok) return r.json().catch(function () { return {}; }).then(function (b) { throw new Error(b.detail || "Request failed (" + r.status + ")"); });
            return r.json();
        });
    }

    function apiPost(path, data) {
        return fetch(API + path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) }).then(function (r) {
            if (!r.ok) return r.json().catch(function () { return {}; }).then(function (b) { throw new Error(b.detail || "Request failed (" + r.status + ")"); });
            return r.json();
        });
    }

    function apiPostForm(path, fd) {
        return fetch(API + path, { method: "POST", body: fd }).then(function (r) {
            if (!r.ok) return r.json().catch(function () { return {}; }).then(function (b) { throw new Error(b.detail || "Request failed (" + r.status + ")"); });
            return r.json();
        });
    }

    // ------------------------------------------------------------------ //
    // Data Loading                                                        //
    // ------------------------------------------------------------------ //
    function loadSkills() { return apiGet("/skills").then(function (d) { skills = d; }).catch(function (e) { console.error(e); toast("Could not load skills.", "error"); }); }
    function loadProjects() { return apiGet("/projects").then(function (d) { projects = d; }).catch(function (e) { console.error(e); }); }
    function loadStatus() { return apiGet("/status").catch(function () { return null; }); }

    function checkConfig() {
        return apiGet("/config-check").then(function (cfg) {
            if (cfg.issues && cfg.issues.length > 0) {
                showAlert(cfg.issues[0]);
            }
        }).catch(function () { /* endpoint may not exist yet */ });
    }

    // ------------------------------------------------------------------ //
    // Navigation                                                          //
    // ------------------------------------------------------------------ //
    function navigateTo(view) {
        currentView = view;
        document.querySelectorAll(".view").forEach(function (el) { el.classList.remove("active"); });
        document.querySelectorAll(".nav-tab").forEach(function (el) { el.classList.remove("active"); });
        var v = document.getElementById("view-" + view);
        if (v) v.classList.add("active");
        var n = document.querySelector('.nav-tab[data-view="' + view + '"]');
        if (n) n.classList.add("active");
        if (view === "dashboard") renderDashboard();
        if (view === "generate") renderSkills();
        if (view === "documents") renderDocuments();
        if (view === "projects") renderProjects();
    }
    // Make globally accessible for inline handlers
    window.navigateTo = navigateTo;

    // ------------------------------------------------------------------ //
    // Project Selector                                                    //
    // ------------------------------------------------------------------ //
    function updateProjectSelector() {
        var sel = document.getElementById("activeProjectSelect");
        var html = '<option value="">-- No project selected --</option>';
        projects.forEach(function (p) {
            var selected = activeProject === p.project_code ? " selected" : "";
            html += '<option value="' + esc(p.project_code) + '"' + selected + '>'
                + esc(p.project_code + " \u2014 " + p.name) + '</option>';
        });
        sel.innerHTML = html;
    }

    function onProjectChange() {
        var val = document.getElementById("activeProjectSelect").value;
        activeProject = val || null;
        if (currentView === "dashboard") renderDashboard();
        if (currentView === "generate") renderSkills();
    }

    // ------------------------------------------------------------------ //
    // System Alert                                                        //
    // ------------------------------------------------------------------ //
    function showAlert(msg) {
        var el = document.getElementById("systemAlert");
        document.getElementById("systemAlertText").textContent = msg;
        el.style.display = "flex";
    }

    // ------------------------------------------------------------------ //
    // Dashboard                                                           //
    // ------------------------------------------------------------------ //
    function renderDashboard() {
        var welcome = document.getElementById("welcomeState");
        var content = document.getElementById("dashboardContent");

        if (!activeProject || projects.length === 0) {
            welcome.style.display = "block";
            content.style.display = "none";
            // Update welcome button text if projects exist
            var btn = document.getElementById("welcomeCreateBtn");
            if (projects.length > 0) {
                btn.textContent = "Select a Project Above";
            } else {
                btn.textContent = "Create Your First Project";
            }
            return;
        }

        welcome.style.display = "none";
        content.style.display = "block";

        // Project hero card
        var proj = projects.find(function (p) { return p.project_code === activeProject; });
        if (proj) {
            document.getElementById("projectHero").innerHTML =
                '<div class="project-hero-info">'
                + '<h2>' + esc(proj.name) + '</h2>'
                + '<div class="hero-code">' + esc(proj.project_code) + '</div>'
                + (proj.client_name ? '<div class="hero-client">' + esc(proj.client_name) + '</div>' : '')
                + '</div>'
                + '<span class="project-hero-status">' + esc(proj.status) + '</span>';
        }

        // Costs
        loadStatus().then(function (st) {
            if (!st) return;
            document.getElementById("dailyCostValue").textContent = cents(st.today_cost_cents);
            document.getElementById("monthlyCostValue").textContent = cents(st.month_cost_cents);
            document.getElementById("dailyCostLimit").textContent = "of " + cents(st.daily_limit_cents) + " daily limit";
            document.getElementById("monthlyCostLimit").textContent = "of " + cents(st.monthly_limit_cents) + " monthly limit";

            var dp = st.daily_limit_cents > 0 ? Math.min(100, st.today_cost_cents / st.daily_limit_cents * 100) : 0;
            var mp = st.monthly_limit_cents > 0 ? Math.min(100, st.month_cost_cents / st.monthly_limit_cents * 100) : 0;
            var df = document.getElementById("dailyCostFill");
            df.style.width = dp + "%";
            df.className = "metric-bar-fill" + (dp > 80 ? " danger" : dp > 60 ? " warning" : "");
            var mf = document.getElementById("monthlyCostFill");
            mf.style.width = mp + "%";
            mf.className = "metric-bar-fill" + (mp > 80 ? " danger" : mp > 60 ? " warning" : "");

            document.getElementById("headerCost").textContent = cents(st.today_cost_cents) + " today";
            renderRecentDocs(st.recent_documents);
        });

        renderQuickActions();
    }

    function renderQuickActions() {
        var c = document.getElementById("quickActions");
        var html = "";
        QUICK_ACTIONS.forEach(function (sn) {
            var sk = skills.find(function (s) { return s.skill_name === sn; });
            if (!sk) return;
            var icon = ICONS[sn] || "\u2699\uFE0F";
            var detail = SKILL_DETAILS[sn];
            var shortDesc = detail ? detail.what.split(".")[0] + "." : sk.description;
            html += '<button class="quick-action-btn" data-skill="' + sn + '">'
                + '<span class="qa-icon">' + icon + '</span>'
                + '<div class="qa-text">'
                + '<span class="qa-label">' + esc(sk.display_name) + '</span>'
                + '<span class="qa-desc">' + esc(shortDesc) + '</span>'
                + '</div></button>';
        });
        c.innerHTML = html;
        c.querySelectorAll(".quick-action-btn").forEach(function (b) {
            b.addEventListener("click", function () { openSkillModal(b.getAttribute("data-skill")); });
        });
    }

    function renderRecentDocs(docs) {
        var c = document.getElementById("recentDocs");
        if (!docs || docs.length === 0) {
            c.innerHTML = '<div class="empty-state"><p>No documents generated yet. Choose a skill above to create your first document.</p></div>';
            return;
        }
        var html = "";
        docs.forEach(function (d) {
            var sk = skills.find(function (s) { return s.skill_name === d.skill_name; });
            var name = sk ? sk.display_name : d.skill_name;
            var icon = ICONS[d.skill_name] || "\uD83D\uDCC4";
            html += '<div class="recent-item">'
                + '<div class="recent-info">'
                + '<span class="recent-name">' + icon + ' ' + esc(d.file_name) + '</span>'
                + '<span class="recent-meta">' + esc(name) + ' \u00B7 ' + fmtDate(d.created_at) + '</span>'
                + '</div>'
                + '<button class="recent-download" onclick="window.open(\'' + esc(d.download_url) + '\')">Download</button>'
                + '</div>';
        });
        c.innerHTML = html;
    }

    // ------------------------------------------------------------------ //
    // Skills View                                                         //
    // ------------------------------------------------------------------ //
    function renderSkills() {
        var container = document.getElementById("skillsContainer");
        var banner = document.getElementById("noProjectBanner");

        // Show no-project banner if needed
        if (!activeProject) {
            banner.style.display = "flex";
        } else {
            banner.style.display = "none";
        }

        var grouped = {};
        skills.forEach(function (s) {
            var p = s.phase || 0;
            if (!grouped[p]) grouped[p] = [];
            grouped[p].push(s);
        });

        var html = "";
        [1, 2, 3].forEach(function (phase) {
            var list = grouped[phase];
            if (!list || list.length === 0) return;
            var pl = PHASE_LABELS[phase] || { name: "Phase " + phase, desc: "" };
            var badgeClass = phase === 2 ? " p2" : phase === 3 ? " p3" : "";

            html += '<div class="phase-section">'
                + '<div class="phase-header">'
                + '<span class="phase-badge' + badgeClass + '">' + phase + '</span>'
                + '<div class="phase-info">'
                + '<span class="phase-name">Phase ' + phase + ': ' + esc(pl.name) + '</span>'
                + '<span class="phase-desc">' + esc(pl.desc) + '</span>'
                + '</div></div>'
                + '<div class="skills-grid">';

            list.forEach(function (sk) {
                var icon = ICONS[sk.skill_name] || "\u2699\uFE0F";
                var unavail = !sk.available ? " unavailable" : "";
                var detail = SKILL_DETAILS[sk.skill_name];
                var tags = "";
                if (sk.requires_file) tags += '<span class="skill-tag file">File Upload</span>';
                if (sk.skill_name === "estimate_reviewer" || sk.skill_name === "contract_checker" || sk.skill_name === "proposal_generator")
                    tags += '<span class="skill-tag opus">Advanced AI</span>';

                // Short detail summary for the card
                var detailHtml = "";
                if (detail) {
                    detailHtml = '<div class="skill-details">'
                        + '<strong>Input:</strong> ' + esc(detail.input.split(".")[0]) + '.<br>'
                        + '<strong>Output:</strong> ' + esc(detail.deliverable.split(".")[0]) + '.'
                        + '</div>';
                }

                html += '<div class="skill-card' + unavail + '" data-skill="' + sk.skill_name + '">'
                    + '<div class="skill-card-top">'
                    + '<span class="skill-icon">' + icon + '</span>'
                    + '<div class="skill-info">'
                    + '<div class="skill-name">' + esc(sk.display_name) + '</div>'
                    + '<div class="skill-desc">' + esc(sk.description) + '</div>'
                    + (tags ? '<div class="skill-tags">' + tags + '</div>' : '')
                    + '</div></div>'
                    + detailHtml
                    + '<button class="skill-generate-btn">Generate Document</button>'
                    + '</div>';
            });

            html += '</div></div>';
        });

        container.innerHTML = html;

        container.querySelectorAll(".skill-generate-btn").forEach(function (btn) {
            btn.addEventListener("click", function (e) {
                e.stopPropagation();
                var card = btn.closest(".skill-card");
                openSkillModal(card.getAttribute("data-skill"));
            });
        });

        // Also make entire card clickable
        container.querySelectorAll(".skill-card").forEach(function (card) {
            card.addEventListener("click", function () {
                openSkillModal(card.getAttribute("data-skill"));
            });
        });
    }

    // ------------------------------------------------------------------ //
    // Documents View                                                      //
    // ------------------------------------------------------------------ //
    function renderDocuments() {
        loadStatus().then(function (st) {
            var tbody = document.getElementById("documentsBody");
            if (!st || !st.recent_documents || st.recent_documents.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No documents generated yet.</td></tr>';
                return;
            }
            var html = "";
            st.recent_documents.forEach(function (d) {
                var sk = skills.find(function (s) { return s.skill_name === d.skill_name; });
                var name = sk ? sk.display_name : d.skill_name;
                html += '<tr>'
                    + '<td>' + fmtDate(d.created_at) + '</td>'
                    + '<td>' + esc(name) + '</td>'
                    + '<td>' + esc(d.file_name) + '</td>'
                    + '<td>' + esc((d.document_type || "").toUpperCase()) + '</td>'
                    + '<td><button class="recent-download" onclick="window.open(\'' + esc(d.download_url) + '\')">Download</button></td>'
                    + '</tr>';
            });
            tbody.innerHTML = html;
        });
    }

    // ------------------------------------------------------------------ //
    // Projects View                                                       //
    // ------------------------------------------------------------------ //
    function renderProjects() {
        loadProjects().then(function () {
            updateProjectSelector();
            var c = document.getElementById("projectsList");
            if (projects.length === 0) {
                c.innerHTML = '<div class="empty-state"><p>No projects yet. Create your first project above to get started.</p></div>';
                return;
            }
            var html = "";
            projects.forEach(function (p) {
                var stClass = p.status.toLowerCase().replace(/\s+/g, "-");
                var pct = Math.round(p.percent_complete || 0);
                var selected = activeProject === p.project_code ? " selected" : "";
                html += '<div class="project-card' + selected + '" data-code="' + esc(p.project_code) + '">'
                    + '<div class="project-card-header">'
                    + '<span class="project-card-name">' + esc(p.name) + '</span>'
                    + '<span class="status-badge ' + stClass + '">' + esc(p.status) + '</span>'
                    + '</div>'
                    + '<div class="project-card-code">' + esc(p.project_code) + '</div>'
                    + (p.client_name ? '<div class="project-client">' + esc(p.client_name) + '</div>' : '')
                    + '<div class="project-progress">'
                    + '<div class="project-progress-bar"><div class="project-progress-fill" style="width:' + pct + '%"></div></div>'
                    + '<span class="project-progress-label">' + pct + '%</span>'
                    + '</div></div>';
            });
            c.innerHTML = html;

            // Click to select project
            c.querySelectorAll(".project-card").forEach(function (card) {
                card.addEventListener("click", function () {
                    var code = card.getAttribute("data-code");
                    activeProject = code;
                    document.getElementById("activeProjectSelect").value = code;
                    renderProjects();
                    toast("Project '" + code + "' selected. Go to Dashboard or Generate Document to get started.", "info");
                });
            });
        });
    }

    // ------------------------------------------------------------------ //
    // Skill Modal                                                         //
    // ------------------------------------------------------------------ //
    function openSkillModal(skillName) {
        var sk = skills.find(function (s) { return s.skill_name === skillName; });
        if (!sk) { toast("Skill not found.", "error"); return; }

        // Check if project required but not selected
        var needsProject = (sk.required_params || []).indexOf("project") >= 0;
        if (needsProject && !activeProject) {
            toast("Please select a project first using the dropdown in the header, or create one in the Projects tab.", "error");
            return;
        }

        var modal = document.getElementById("skillModal");
        var title = document.getElementById("modalTitle");
        var body = document.getElementById("modalBody");
        var icon = ICONS[skillName] || "\u2699\uFE0F";
        var detail = SKILL_DETAILS[skillName];

        title.textContent = icon + " " + sk.display_name;

        // Build modal content
        var html = '';

        // Skill info card
        if (detail) {
            html += '<div class="modal-skill-info">'
                + '<p>' + esc(detail.what) + '</p>'
                + '<div class="modal-skill-meta">'
                + '<div class="modal-skill-meta-item"><div class="detail-label">What You Provide</div><div class="detail-value">' + esc(detail.input) + '</div></div>'
                + '<div class="modal-skill-meta-item"><div class="detail-label">What You Get</div><div class="detail-value">' + esc(detail.deliverable) + '</div></div>'
                + '</div></div>';
        }

        // Form
        html += '<form id="skillForm">';
        var params = sk.required_params || [];
        params.forEach(function (param) {
            if (param === "file") return;
            if (param === "project") return; // auto-filled from header
            var cfg = PARAM_CONFIG[param] || { label: capitalize(param), type: "text", placeholder: "" };
            html += '<div class="form-group">'
                + '<label for="param_' + param + '">' + esc(cfg.label) + ' <span class="req">*</span></label>';
            if (cfg.type === "textarea") {
                html += '<textarea id="param_' + param + '" name="' + param + '" placeholder="' + esc(cfg.placeholder || "") + '" rows="5" required></textarea>';
            } else if (cfg.type === "select") {
                html += '<select id="param_' + param + '" name="' + param + '" required>';
                (cfg.options || []).forEach(function (o) { html += '<option value="' + esc(o) + '">' + esc(o) + '</option>'; });
                html += '</select>';
            } else {
                html += '<input type="text" id="param_' + param + '" name="' + param + '" placeholder="' + esc(cfg.placeholder || "") + '" required>';
            }
            html += '<span class="field-error">This field is required.</span></div>';
        });

        if (sk.requires_file) {
            html += '<div class="form-group">'
                + '<label for="param_file">Upload File <span class="req">*</span></label>'
                + '<input type="file" id="param_file" name="file" accept=".pdf,.docx,.xlsx,.xls,.csv,.png,.jpg,.jpeg" required>'
                + '<span class="field-hint">Accepted formats: PDF, DOCX, XLSX, CSV, or images</span>'
                + '<span class="field-error">Please select a file to upload.</span></div>';
        }

        html += '<button type="submit" class="btn btn-gold btn-lg" style="width:100%;margin-top:12px;">Generate Document</button>';
        html += '</form>';

        body.innerHTML = html;
        modal.classList.add("open");

        // Form submit
        document.getElementById("skillForm").addEventListener("submit", function (e) {
            e.preventDefault();
            executeSkill(skillName, sk);
        });
    }

    function closeModal() {
        document.getElementById("skillModal").classList.remove("open");
    }

    function executeSkill(skillName, sk) {
        var body = document.getElementById("modalBody");
        var params = {};
        var fileInput = null;
        var required = sk.required_params || [];

        // Validate
        var valid = true;
        required.forEach(function (param) {
            if (param === "project" || param === "file") return;
            var el = document.getElementById("param_" + param);
            if (el && !el.value.trim()) {
                el.closest(".form-group").classList.add("has-error");
                valid = false;
            } else if (el) {
                el.closest(".form-group").classList.remove("has-error");
                params[param] = el.value.trim();
            }
        });

        if (sk.requires_file) {
            fileInput = document.getElementById("param_file");
            if (fileInput && fileInput.files.length === 0) {
                fileInput.closest(".form-group").classList.add("has-error");
                valid = false;
            }
        }

        if (!valid) { toast("Please fill in all required fields.", "error"); return; }

        // Show loading
        body.innerHTML = '<div class="loading-state">'
            + '<div class="spinner spinner-lg"></div>'
            + '<p>Generating your ' + esc(sk.display_name) + '...</p>'
            + '<p class="loading-sub">This typically takes 15\u201360 seconds. The AI is analyzing your input and creating a professional document.</p>'
            + '</div>';

        var promise;
        if (sk.requires_file && fileInput && fileInput.files.length > 0) {
            var fd = new FormData();
            fd.append("file", fileInput.files[0]);
            if (activeProject) fd.append("project_code", activeProject);
            fd.append("parameters", JSON.stringify(params));
            promise = apiPostForm("/skills/" + skillName + "/execute-with-file", fd);
        } else {
            promise = apiPost("/skills/" + skillName + "/execute", {
                skill_name: skillName,
                project_code: activeProject,
                parameters: params,
            });
        }

        promise.then(function (result) {
            if (result.success) {
                renderSuccess(result, sk, skillName);
                toast("Document generated successfully!", "success");
            } else {
                renderError(result.error || "An unknown error occurred.", sk);
            }
        }).catch(function (err) {
            renderError(err.message || "Network error. Please check your connection and try again.", sk);
        });
    }

    function renderSuccess(result, sk, skillName) {
        var body = document.getElementById("modalBody");
        var costStr = result.cost_cents != null ? cents(result.cost_cents) : "$0.00";
        var tokensStr = result.tokens_used != null ? result.tokens_used.toLocaleString() : "0";
        var detail = SKILL_DETAILS[skillName];

        var html = '<div class="result-state success">'
            + '<div class="result-icon">\u2705</div>'
            + '<h3>Document Generated Successfully</h3>'
            + '<p>Your ' + esc(sk.display_name) + ' has been created and saved. It\'s ready for download and distribution.</p>'
            + '<div class="result-stats">'
            + '<div>Cost: <span>' + costStr + '</span></div>'
            + '<div>Tokens: <span>' + tokensStr + '</span></div>'
            + '</div>'
            + '<div class="result-actions">';

        if (result.download_url) {
            html += '<a href="' + esc(result.download_url) + '" class="btn btn-gold btn-lg" download>Download Document</a>';
        }
        html += '<button class="btn btn-outline" onclick="document.getElementById(\'skillModal\').classList.remove(\'open\')">Close</button>';
        html += '</div>';

        // Workflow suggestion
        if (detail && detail.next_skill) {
            var nextSk = skills.find(function (s) { return s.skill_name === detail.next_skill; });
            if (nextSk) {
                var nextIcon = ICONS[detail.next_skill] || "\u2699\uFE0F";
                html += '<div class="workflow-suggestion">'
                    + '<div class="workflow-suggestion-title">Suggested Next Step</div>'
                    + '<p>' + esc(detail.connects) + '</p>'
                    + '<button class="btn btn-navy" onclick="document.getElementById(\'skillModal\').classList.remove(\'open\'); setTimeout(function(){openSkillModal(\'' + detail.next_skill + '\');},300);">'
                    + nextIcon + ' Generate ' + esc(nextSk.display_name)
                    + '</button></div>';
            }
        }

        html += '</div>';
        body.innerHTML = html;

        // Refresh dashboard
        loadStatus().then(function (st) {
            if (st) document.getElementById("headerCost").textContent = cents(st.today_cost_cents) + " today";
        });
    }
    // Make globally accessible for inline onclick
    window.openSkillModal = openSkillModal;

    function renderError(msg, sk) {
        var body = document.getElementById("modalBody");
        var html = '<div class="result-state error">'
            + '<div class="result-icon">\u274C</div>'
            + '<h3>Generation Failed</h3>'
            + '<p>' + esc(msg) + '</p>'
            + '<div class="result-actions">'
            + '<button class="btn btn-gold" onclick="openSkillModal(\'' + sk.skill_name + '\')">Try Again</button>'
            + '<button class="btn btn-outline" onclick="document.getElementById(\'skillModal\').classList.remove(\'open\')">Close</button>'
            + '</div></div>';
        body.innerHTML = html;
    }

    // ------------------------------------------------------------------ //
    // Project Form                                                        //
    // ------------------------------------------------------------------ //
    function setupProjectForm() {
        var form = document.getElementById("addProjectForm");
        if (!form) return;
        form.addEventListener("submit", function (e) {
            e.preventDefault();
            var btn = form.querySelector('button[type="submit"]');

            // Validate required fields
            var valid = true;
            ["projCode", "projName"].forEach(function (id) {
                var el = document.getElementById(id);
                if (!el.value.trim()) {
                    el.closest(".form-group").classList.add("has-error");
                    valid = false;
                } else {
                    el.closest(".form-group").classList.remove("has-error");
                }
            });
            if (!valid) { toast("Please fill in required fields.", "error"); return; }

            btn.disabled = true;
            btn.innerHTML = '<span class="spinner"></span> Creating...';

            var data = {
                project_code: form.project_code.value.trim(),
                name: form.name.value.trim(),
                client_name: form.client_name.value.trim() || null,
                project_type: form.project_type.value,
                status: "active",
                address: form.address.value.trim(),
            };

            apiPost("/projects", data).then(function () {
                toast("Project '" + data.project_code + "' created! It's now your active project.", "success");
                form.reset();
                activeProject = data.project_code;
                return loadProjects();
            }).then(function () {
                updateProjectSelector();
                document.getElementById("activeProjectSelect").value = activeProject;
                renderProjects();
            }).catch(function (err) {
                toast("Failed to create project: " + err.message, "error");
            }).finally(function () {
                btn.disabled = false;
                btn.innerHTML = '<svg viewBox="0 0 20 20" fill="currentColor" width="18" height="18"><path fill-rule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clip-rule="evenodd"/></svg> Create Project';
            });
        });
    }

    // ------------------------------------------------------------------ //
    // Toast                                                               //
    // ------------------------------------------------------------------ //
    function toast(msg, type) {
        type = type || "info";
        var stack = document.getElementById("toastStack");
        var el = document.createElement("div");
        el.className = "toast " + type;
        el.textContent = msg;
        stack.appendChild(el);
        setTimeout(function () {
            el.classList.add("fade-out");
            setTimeout(function () { if (el.parentNode) el.parentNode.removeChild(el); }, 300);
        }, 5000);
    }

    // ------------------------------------------------------------------ //
    // Utilities                                                           //
    // ------------------------------------------------------------------ //
    function cents(c) { return c == null ? "$0.00" : "$" + (c / 100).toFixed(2); }

    function fmtDate(s) {
        if (!s) return "";
        try { var d = new Date(s); return isNaN(d.getTime()) ? s : d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }); }
        catch (e) { return s; }
    }

    function capitalize(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1).replace(/_/g, " ") : ""; }

    function esc(s) {
        if (s == null) return "";
        var d = document.createElement("div");
        d.appendChild(document.createTextNode(String(s)));
        return d.innerHTML;
    }

    // ------------------------------------------------------------------ //
    // Init                                                                //
    // ------------------------------------------------------------------ //
    function init() {
        // Navigation
        document.querySelectorAll(".nav-tab").forEach(function (b) {
            b.addEventListener("click", function () { navigateTo(b.getAttribute("data-view")); });
        });

        // Modal
        document.getElementById("modalClose").addEventListener("click", closeModal);
        document.getElementById("skillModal").addEventListener("click", function (e) { if (e.target === this) closeModal(); });
        document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeModal(); });

        // Alert dismiss
        document.getElementById("alertDismiss").addEventListener("click", function () {
            document.getElementById("systemAlert").style.display = "none";
        });

        // Project selector
        document.getElementById("activeProjectSelect").addEventListener("change", onProjectChange);

        // Welcome button
        document.getElementById("welcomeCreateBtn").addEventListener("click", function () {
            if (projects.length > 0) {
                // Scroll to project selector in header
                document.getElementById("activeProjectSelect").focus();
            } else {
                navigateTo("projects");
            }
        });

        // No-project link
        var npl = document.getElementById("noProjectLink");
        if (npl) npl.addEventListener("click", function (e) { e.preventDefault(); navigateTo("projects"); });

        // Project form
        setupProjectForm();

        // Load data
        Promise.all([loadSkills(), loadProjects(), checkConfig()]).then(function () {
            updateProjectSelector();
            renderDashboard();
        });

        // Auto-refresh every 60s
        setInterval(function () {
            if (currentView === "dashboard" && activeProject) {
                loadStatus().then(function (st) {
                    if (st) document.getElementById("headerCost").textContent = cents(st.today_cost_cents) + " today";
                });
            }
        }, 60000);
    }

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
    else init();

})();
