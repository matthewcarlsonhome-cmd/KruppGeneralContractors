/* ====================================================================== */
/* KruppAI — Project Command Center                                       */
/* No modals. Inline forms. Workflow-based. Shows the automation.          */
/* ====================================================================== */

(function () {
    "use strict";

    var API = "/api/v1";

    // ------------------------------------------------------------------ //
    // Skill Icons                                                         //
    // ------------------------------------------------------------------ //
    var ICONS = {
        daily_report: "\uD83D\uDCCB", rfi_generator: "\u2753",
        meeting_minutes: "\uD83D\uDDD3\uFE0F", client_update: "\u2709\uFE0F",
        safety_talk: "\u26D1\uFE0F", punch_list: "\u2705",
        estimate_reviewer: "\uD83D\uDCB0", bid_comparison: "\uD83D\uDCCA",
        change_order: "\uD83D\uDD04", schedule_variance: "\uD83D\uDCC5",
        submittal_tracker: "\uD83D\uDCE6", contract_checker: "\uD83D\uDCDC",
        proposal_generator: "\uD83D\uDCC4", budget_forecaster: "\uD83D\uDCC8",
        closeout_assembler: "\uD83C\uDFC1", lessons_learned: "\uD83D\uDCA1",
        case_study: "\uD83C\uDFD7\uFE0F", incident_report: "\u26A0\uFE0F",
    };

    // ------------------------------------------------------------------ //
    // Workflow Groups                                                     //
    // ------------------------------------------------------------------ //
    var WORKFLOW_GROUPS = [
        {
            id: "field", name: "Today's Field Work", icon: "\uD83D\uDCCB",
            desc: "Daily documentation from the job site",
            skills: ["daily_report", "safety_talk", "incident_report"],
            statFn: function (s) {
                var parts = [];
                if (s.daily_report_count) parts.push(s.daily_report_count + " daily reports");
                return parts.join(" \u00B7 ") || "No reports yet";
            }
        },
        {
            id: "coordination", name: "Design Coordination", icon: "\u2753",
            desc: "RFIs, submittals, and design team communication",
            skills: ["rfi_generator", "submittal_tracker"],
            statFn: function (s) {
                var parts = [];
                if (s.open_rfis) parts.push(s.open_rfis + " open RFIs");
                if (s.overdue_rfis) parts.push(s.overdue_rfis + " overdue");
                return parts.join(" \u00B7 ") || "No open RFIs";
            }
        },
        {
            id: "financial", name: "Financial Management", icon: "\uD83D\uDCB0",
            desc: "Change orders, budgets, bids, and estimates",
            skills: ["change_order", "budget_forecaster", "bid_comparison", "estimate_reviewer"],
            statFn: function (s) {
                var parts = [];
                if (s.pending_cos) parts.push(s.pending_cos + " pending COs");
                if (s.pending_co_cents) parts.push(cents(s.pending_co_cents) + " pending");
                return parts.join(" \u00B7 ") || "No pending changes";
            }
        },
        {
            id: "communication", name: "Communication", icon: "\u2709\uFE0F",
            desc: "Client updates, meeting minutes, and project correspondence",
            skills: ["client_update", "meeting_minutes"],
            statFn: function (s) {
                if (s.last_client_update) return "Last update: " + fmtDate(s.last_client_update);
                return "No client updates yet";
            }
        },
        {
            id: "closeout", name: "Project Closeout", icon: "\uD83C\uDFC1",
            desc: "Punch lists, closeout packages, and institutional knowledge",
            skills: ["punch_list", "closeout_assembler", "lessons_learned", "case_study"],
            statFn: function (s) {
                if (s.open_punch_items) return s.open_punch_items + " open punch items";
                return "No open items";
            }
        },
        {
            id: "development", name: "Business Development", icon: "\uD83D\uDCC4",
            desc: "Proposals and contract review for new work",
            skills: ["proposal_generator", "contract_checker"],
            statFn: function () { return "Win new work"; }
        },
    ];

    // ------------------------------------------------------------------ //
    // Auto-fill descriptions per skill                                    //
    // ------------------------------------------------------------------ //
    var AUTO_FILL = {
        daily_report: function (s) { return [
            "\uD83D\uDCCD Weather: Auto-fetching for " + (s.address || "project address"),
            "\uD83D\uDD22 This will be Daily Report #" + s.next_daily_report,
            "\uD83D\uDC65 " + s.team_count + " team members, " + s.sub_count + " subs loaded as context",
            "\uD83C\uDFE2 Krupp writing standards applied",
        ]; },
        rfi_generator: function (s) { return [
            "\uD83D\uDD22 This will be RFI #" + s.next_rfi,
            "\uD83D\uDCC5 Response due date auto-calculated (3 days urgent, 14 days normal)",
            "\uD83D\uDCB5 Cost & schedule impact assessment included",
            "\uD83D\uDC65 Project team and sub context loaded",
        ]; },
        meeting_minutes: function (s) { return [
            "\uD83D\uDC65 " + s.team_count + " team members loaded for attendee matching",
            "\u2705 " + s.open_action_items + " open action items from prior meetings",
            "\uD83D\uDD04 Decisions and new action items auto-extracted",
        ]; },
        client_update: function (s) { return [
            "\uD83D\uDCCA Project data loaded: " + s.daily_report_count + " daily reports, " + s.open_rfis + " open RFIs",
            "\uD83C\uDFE2 Professional letter format with Krupp branding",
            "\uD83D\uDC65 Client name and project details pre-filled",
        ]; },
        safety_talk: function () { return [
            "\uD83D\uDCDA OSHA references auto-included for your topic",
            "\u26D1\uFE0F Field-ready format with crew discussion questions",
            "\uD83C\uDF21\uFE0F Seasonal relevance flagged",
        ]; },
        punch_list: function (s) { return [
            "\uD83D\uDC65 " + s.sub_count + " subcontractors loaded for trade matching",
            "\uD83D\uDD22 Items auto-numbered with priority and trade assignment",
            "\uD83D\uDCCA Both DOCX and XLSX output generated",
        ]; },
        change_order: function (s) { return [
            "\uD83D\uDD22 This will be CO #" + s.next_co,
            "\uD83D\uDCB0 Cost breakdown with markup auto-calculated",
            "\uD83D\uDCC5 Schedule impact analysis included",
        ]; },
        incident_report: function (s) { return [
            "\uD83D\uDD22 This will be Incident #" + s.next_incident,
            "\u2696\uFE0F OSHA recordability assessment included",
            "\uD83D\uDD0D Root cause analysis and corrective actions generated",
        ]; },
        estimate_reviewer: function () { return [
            "\uD83E\uDDE0 Advanced AI (Opus) for precision analysis",
            "\uD83D\uDCCA Line items compared against industry benchmarks",
            "\u26A0\uFE0F Missing scope and pricing anomalies flagged",
        ]; },
        bid_comparison: function () { return [
            "\uD83D\uDCCA Normalized comparison matrix generated",
            "\uD83D\uDD0D Scope gap analysis between bidders",
            "\uD83D\uDCDD DOCX narrative + XLSX bid tabulation",
        ]; },
        budget_forecaster: function () { return [
            "\uD83D\uDCC8 Cost-to-date vs. budget by cost code",
            "\uD83D\uDD2E Final cost projection based on trends",
            "\uD83D\uDCDD DOCX report + XLSX with 3 forecast sheets",
        ]; },
        schedule_variance: function () { return [
            "\uD83D\uDCC5 Critical path analysis and float consumption",
            "\u26A0\uFE0F At-risk activities flagged with mitigation suggestions",
        ]; },
        submittal_tracker: function () { return [
            "\uD83D\uDCE6 Overdue and at-risk submittals identified",
            "\uD83D\uDD17 Procurement impact on schedule flagged",
        ]; },
        contract_checker: function () { return [
            "\uD83E\uDDE0 Advanced AI (Opus) for legal precision",
            "\u26A0\uFE0F Risk levels: critical, high, medium, informational",
            "\uD83D\uDCCB Missing clauses and non-standard terms flagged",
        ]; },
        proposal_generator: function () { return [
            "\uD83E\uDDE0 Advanced AI (Opus) for compelling proposals",
            "\uD83C\uDFE2 Company profile, team bios, and past projects loaded",
            "\uD83D\uDCC4 Full proposal: executive summary through qualifications",
        ]; },
        closeout_assembler: function () { return [
            "\uD83C\uDFC1 5-area checklist: Contractual, Technical, Financial, Owner, Regulatory",
            "\uD83D\uDCDD Cover letter + XLSX tracker generated",
        ]; },
        lessons_learned: function () { return [
            "\uD83D\uDCA1 Categorized by severity and topic",
            "\uD83D\uDD0D Duplicate check against existing lessons",
        ]; },
        case_study: function () { return [
            "\uD83C\uDFD7\uFE0F Narrative format: Challenge, Solution, Results",
            "\uD83C\uDFE2 Company branding for marketing use",
        ]; },
    };

    // ------------------------------------------------------------------ //
    // Param config for forms                                              //
    // ------------------------------------------------------------------ //
    var PARAM_CONFIG = {
        notes:   { label: "Notes / Details", type: "textarea", placeholder: "Enter your field notes, observations, or details. The more context you provide, the better the output." },
        issue:   { label: "Issue Description", type: "textarea", placeholder: "Describe the issue or question that needs clarification. Include drawing/spec references." },
        type:    { label: "Meeting Type", type: "select", options: ["OAC Meeting", "Subcontractor Meeting", "Safety Meeting", "Internal Team Meeting", "Pre-Construction Meeting", "Closeout Meeting", "Other"] },
        topic:   { label: "Safety Topic", type: "text", placeholder: "e.g., Fall protection, Electrical safety, Heat illness, Trenching" },
        description: { label: "Change Description", type: "textarea", placeholder: "Describe the scope change \u2014 what work is being added, modified, or removed." },
        reason:  { label: "Reason for Change", type: "textarea", placeholder: "Why is this change needed \u2014 owner request, field condition, design error, etc." },
        trade:   { label: "Trade / Scope", type: "text", placeholder: "e.g., Electrical, Plumbing, HVAC, Concrete" },
        bids:    { label: "Bid Details", type: "textarea", placeholder: "Enter bid info: bidder names, amounts, scope inclusions/exclusions, and qualifications." },
    };

    // ------------------------------------------------------------------ //
    // State                                                               //
    // ------------------------------------------------------------------ //
    var skills = [];
    var projects = [];
    var activeProject = null;
    var projectStats = null;
    var currentView = "dashboard";
    var openFormSkill = null;

    // ------------------------------------------------------------------ //
    // API helpers                                                         //
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
    // Data loading                                                        //
    // ------------------------------------------------------------------ //
    function loadSkills() { return apiGet("/skills").then(function (d) { skills = d; }).catch(function () {}); }
    function loadProjects() { return apiGet("/projects").then(function (d) { projects = d; }).catch(function () {}); }

    function loadProjectStats() {
        if (!activeProject) { projectStats = null; return Promise.resolve(); }
        return apiGet("/projects/" + encodeURIComponent(activeProject) + "/stats")
            .then(function (d) { projectStats = d; })
            .catch(function () { projectStats = null; });
    }

    function checkConfig() {
        return apiGet("/config-check").then(function (cfg) {
            if (cfg.issues && cfg.issues.length > 0) showAlert(cfg.issues[0]);
            var ks = document.getElementById("settingsApiKeyStatus");
            var ds = document.getElementById("settingsDbStatus");
            if (ks) ks.textContent = cfg.api_key_configured ? "Configured" : "Not configured";
            if (ds) ds.textContent = cfg.database_ready ? "Connected" : "Not found";
        }).catch(function () {});
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
        if (view === "documents") renderDocuments();
        if (view === "projects") renderProjectsPage();
        if (view === "settings") renderSettings();
    }

    // ------------------------------------------------------------------ //
    // Project selector                                                    //
    // ------------------------------------------------------------------ //
    function updateProjectSelector() {
        var sel = document.getElementById("activeProjectSelect");
        var html = '<option value="">-- No project selected --</option>';
        projects.forEach(function (p) {
            var s = activeProject === p.project_code ? " selected" : "";
            html += '<option value="' + esc(p.project_code) + '"' + s + '>' + esc(p.project_code + " \u2014 " + p.name) + '</option>';
        });
        sel.innerHTML = html;
    }

    function onProjectChange() {
        activeProject = document.getElementById("activeProjectSelect").value || null;
        openFormSkill = null;
        loadProjectStats().then(function () {
            if (currentView === "dashboard") renderDashboard();
        });
    }

    // ------------------------------------------------------------------ //
    // Alert                                                               //
    // ------------------------------------------------------------------ //
    function showAlert(msg) {
        document.getElementById("systemAlertText").textContent = msg;
        document.getElementById("systemAlert").style.display = "flex";
    }

    // ------------------------------------------------------------------ //
    // Dashboard                                                           //
    // ------------------------------------------------------------------ //
    function renderDashboard() {
        var s1 = document.getElementById("noProjectsState");
        var s2 = document.getElementById("selectProjectState");
        var s3 = document.getElementById("commandCenter");
        s1.style.display = "none";
        s2.style.display = "none";
        s3.style.display = "none";

        if (projects.length === 0) {
            s1.style.display = "block";
            return;
        }
        if (!activeProject) {
            s2.style.display = "block";
            renderSelectProjectGrid();
            return;
        }
        s3.style.display = "block";
        renderStatusBar();
        renderWorkflowGroups();
        renderActivityFeed();
    }

    function renderSelectProjectGrid() {
        var c = document.getElementById("selectProjectGrid");
        c.innerHTML = projects.map(function (p) {
            return '<div class="project-card" data-code="' + esc(p.project_code) + '">'
                + '<div class="project-card-header"><span class="project-card-name">' + esc(p.name) + '</span>'
                + '<span class="status-badge ' + p.status + '">' + esc(p.status) + '</span></div>'
                + '<div class="project-card-code">' + esc(p.project_code) + '</div>'
                + (p.client_name ? '<div class="project-client">' + esc(p.client_name) + '</div>' : '')
                + '</div>';
        }).join("");
        c.querySelectorAll(".project-card").forEach(function (card) {
            card.addEventListener("click", function () {
                activeProject = card.getAttribute("data-code");
                document.getElementById("activeProjectSelect").value = activeProject;
                loadProjectStats().then(function () { renderDashboard(); });
            });
        });
    }

    // ------------------------------------------------------------------ //
    // Status Bar                                                          //
    // ------------------------------------------------------------------ //
    function renderStatusBar() {
        var bar = document.getElementById("statusBar");
        var proj = projects.find(function (p) { return p.project_code === activeProject; });
        if (!proj) return;
        var st = projectStats || {};
        bar.innerHTML = '<div class="status-bar-info">'
            + '<div class="status-bar-name">' + esc(proj.name) + '</div>'
            + '<div class="status-bar-code">' + esc(proj.project_code) + '</div>'
            + (proj.client_name ? '<div class="status-bar-client">' + esc(proj.client_name) + '</div>' : '')
            + '</div>'
            + '<div class="status-bar-stats">'
            + statItem(st.open_rfis || 0, "Open RFIs")
            + statItem(st.pending_cos || 0, "Pending COs")
            + statItem(st.open_action_items || 0, "Action Items")
            + statItem(st.open_punch_items || 0, "Punch Items")
            + statItem(st.daily_report_count || 0, "Daily Reports")
            + '</div>';
    }

    function statItem(val, label) {
        return '<div class="stat-item"><span class="stat-value">' + val + '</span><span class="stat-label">' + label + '</span></div>';
    }

    // ------------------------------------------------------------------ //
    // Workflow Groups                                                     //
    // ------------------------------------------------------------------ //
    function renderWorkflowGroups() {
        var c = document.getElementById("workflowGroups");
        var st = projectStats || {};
        var html = "";
        WORKFLOW_GROUPS.forEach(function (g) {
            var statText = g.statFn(st);
            html += '<div class="workflow-group" data-group="' + g.id + '">'
                + '<div class="wf-header">'
                + '<span class="wf-icon">' + g.icon + '</span>'
                + '<div class="wf-info">'
                + '<span class="wf-name">' + esc(g.name) + '</span>'
                + '<span class="wf-stats">' + esc(statText) + '</span>'
                + '</div></div>'
                + '<div class="wf-skills">';

            g.skills.forEach(function (sn) {
                var sk = skills.find(function (s) { return s.skill_name === sn; });
                if (!sk) return;
                var hint = "";
                if (sn === "daily_report" && st.next_daily_report) hint = "Report #" + st.next_daily_report;
                if (sn === "rfi_generator" && st.next_rfi) hint = "RFI #" + st.next_rfi;
                if (sn === "change_order" && st.next_co) hint = "CO #" + st.next_co;
                if (sn === "incident_report" && st.next_incident) hint = "Incident #" + st.next_incident;
                var activeClass = openFormSkill === sn ? " active" : "";
                html += '<button class="wf-skill-btn' + activeClass + '" data-skill="' + sn + '">'
                    + '<span class="wf-skill-name">' + esc(sk.display_name) + '</span>'
                    + (hint ? '<span class="wf-skill-hint">' + esc(hint) + '</span>' : '')
                    + '</button>';
            });

            html += '</div>'
                + '<div class="wf-form-slot" id="form-slot-' + g.id + '" style="display:none;"></div>'
                + '</div>';
        });
        c.innerHTML = html;

        c.querySelectorAll(".wf-skill-btn").forEach(function (btn) {
            btn.addEventListener("click", function () {
                var sn = btn.getAttribute("data-skill");
                if (openFormSkill === sn) {
                    closeInlineForm();
                } else {
                    openInlineForm(sn);
                }
            });
        });
    }

    // ------------------------------------------------------------------ //
    // Inline Form                                                         //
    // ------------------------------------------------------------------ //
    function openInlineForm(skillName) {
        var sk = skills.find(function (s) { return s.skill_name === skillName; });
        if (!sk) return;

        closeInlineForm();
        openFormSkill = skillName;

        var group = WORKFLOW_GROUPS.find(function (g) { return g.skills.indexOf(skillName) >= 0; });
        if (!group) return;

        document.querySelectorAll(".wf-skill-btn").forEach(function (b) {
            b.classList.toggle("active", b.getAttribute("data-skill") === skillName);
        });

        var slot = document.getElementById("form-slot-" + group.id);
        var icon = ICONS[skillName] || "\u2699\uFE0F";
        var st = projectStats || {};

        // Auto-fill preview
        var afFn = AUTO_FILL[skillName];
        var afItems = afFn ? afFn(st) : [];
        var afHtml = "";
        if (afItems.length) {
            afHtml = '<div class="auto-fill-preview">';
            afItems.forEach(function (item) {
                afHtml += '<div class="auto-fill-item">' + esc(item) + '</div>';
            });
            afHtml += '</div>';
        }

        // Form fields
        var params = (sk.required_params || []).filter(function (p) { return p !== "project" && p !== "file"; });
        var fieldsHtml = "";
        params.forEach(function (param) {
            var cfg = PARAM_CONFIG[param] || { label: capitalize(param), type: "text", placeholder: "" };
            fieldsHtml += '<div class="form-group">'
                + '<label for="param_' + param + '">' + esc(cfg.label) + ' <span class="req">*</span></label>';
            if (cfg.type === "textarea") {
                fieldsHtml += '<textarea id="param_' + param + '" name="' + param + '" placeholder="' + esc(cfg.placeholder || "") + '" rows="5" required></textarea>';
            } else if (cfg.type === "select") {
                fieldsHtml += '<select id="param_' + param + '" name="' + param + '" required>';
                (cfg.options || []).forEach(function (o) { fieldsHtml += '<option value="' + esc(o) + '">' + esc(o) + '</option>'; });
                fieldsHtml += '</select>';
            } else {
                fieldsHtml += '<input type="text" id="param_' + param + '" name="' + param + '" placeholder="' + esc(cfg.placeholder || "") + '" required>';
            }
            fieldsHtml += '<span class="field-error">This field is required.</span></div>';
        });

        if (sk.requires_file) {
            fieldsHtml += '<div class="form-group">'
                + '<label for="param_file">Upload File <span class="req">*</span></label>'
                + '<input type="file" id="param_file" name="file" accept=".pdf,.docx,.xlsx,.xls,.csv,.png,.jpg,.jpeg" required>'
                + '<span class="field-hint">Accepted: PDF, DOCX, XLSX, CSV, or images</span>'
                + '<span class="field-error">Please select a file.</span></div>';
        }

        // Button text with auto-number
        var btnText = "Generate " + sk.display_name;
        if (skillName === "daily_report" && st.next_daily_report) btnText = "Generate Daily Report #" + st.next_daily_report;
        if (skillName === "rfi_generator" && st.next_rfi) btnText = "Generate RFI #" + st.next_rfi;
        if (skillName === "change_order" && st.next_co) btnText = "Generate CO #" + st.next_co;
        if (skillName === "incident_report" && st.next_incident) btnText = "Generate Incident Report #" + st.next_incident;

        slot.innerHTML = '<div class="inline-form">'
            + '<div class="inline-form-header">'
            + '<h3>' + icon + ' ' + esc(sk.display_name) + '</h3>'
            + '<button class="inline-form-close" id="inlineFormClose">&times;</button>'
            + '</div>'
            + afHtml
            + '<form id="inlineSkillForm">'
            + fieldsHtml
            + '<button type="submit" class="btn btn-gold btn-lg" style="width:100%;margin-top:8px;">' + esc(btnText) + '</button>'
            + '</form></div>';

        slot.style.display = "block";

        document.getElementById("inlineFormClose").addEventListener("click", closeInlineForm);
        document.getElementById("inlineSkillForm").addEventListener("submit", function (e) {
            e.preventDefault();
            executeInlineSkill(skillName, sk, slot);
        });

        slot.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    function closeInlineForm() {
        openFormSkill = null;
        document.querySelectorAll(".wf-form-slot").forEach(function (s) { s.style.display = "none"; s.innerHTML = ""; });
        document.querySelectorAll(".wf-skill-btn").forEach(function (b) { b.classList.remove("active"); });
    }

    function executeInlineSkill(skillName, sk, slot) {
        var params = {};
        var fileInput = null;
        var required = (sk.required_params || []).filter(function (p) { return p !== "project" && p !== "file"; });

        var valid = true;
        required.forEach(function (param) {
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

        slot.innerHTML = '<div class="inline-form"><div class="loading-state">'
            + '<div class="spinner spinner-lg"></div>'
            + '<p>Generating your ' + esc(sk.display_name) + '...</p>'
            + '<p class="loading-sub">This typically takes 15\u201360 seconds. The AI is analyzing your input and creating a professional document.</p>'
            + '</div></div>';

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
                showInlineSuccess(result, sk, slot);
                toast("Document generated successfully!", "success");
                loadProjectStats().then(function () { renderStatusBar(); });
            } else {
                showInlineError(result.error || "An unknown error occurred.", sk, slot);
            }
        }).catch(function (err) {
            showInlineError(err.message || "Network error.", sk, slot);
        });
    }

    function showInlineSuccess(result, sk, slot) {
        var costStr = result.cost_cents != null ? cents(result.cost_cents) : "$0.00";
        var tokensStr = result.tokens_used != null ? result.tokens_used.toLocaleString() : "0";
        slot.innerHTML = '<div class="inline-result">'
            + '<div class="inline-result-header success">'
            + '<span>\u2705 ' + esc(sk.display_name) + ' Generated</span>'
            + '<button class="inline-form-close" onclick="document.querySelectorAll(\'.wf-form-slot\').forEach(function(s){s.style.display=\'none\';s.innerHTML=\'\';});">&times;</button>'
            + '</div>'
            + (result.download_url ?
                '<div class="inline-result-file">'
                + '<span class="file-name">' + esc(result.output_path ? result.output_path.split("/").pop().split("\\\\").pop() : "document") + '</span>'
                + '<a href="' + esc(result.download_url) + '" class="btn btn-gold" download>Download</a>'
                + '</div>' : '')
            + '<div class="inline-result-meta">'
            + 'Saved to database \u00B7 Cost: ' + costStr + ' \u00B7 Tokens: ' + tokensStr
            + '</div></div>';
    }

    function showInlineError(msg, sk, slot) {
        slot.innerHTML = '<div class="inline-result">'
            + '<div class="inline-result-header error">'
            + '<span>\u274C Generation Failed</span>'
            + '<button class="inline-form-close" onclick="document.querySelectorAll(\'.wf-form-slot\').forEach(function(s){s.style.display=\'none\';s.innerHTML=\'\';});">&times;</button>'
            + '</div>'
            + '<div class="inline-result-meta" style="color:var(--error);">' + esc(msg) + '</div>'
            + '<div style="padding:0 24px 24px;">'
            + '<button class="btn btn-gold" onclick="openInlineForm(\'' + sk.skill_name + '\')">Try Again</button>'
            + '</div></div>';
    }
    window.openInlineForm = openInlineForm;

    // ------------------------------------------------------------------ //
    // Activity Feed                                                       //
    // ------------------------------------------------------------------ //
    function renderActivityFeed() {
        if (!activeProject) return;
        apiGet("/projects/" + encodeURIComponent(activeProject) + "/activity").then(function (events) {
            var c = document.getElementById("activityFeed");
            if (!events || events.length === 0) {
                c.innerHTML = '<div class="empty-state"><p>No activity yet for this project.</p></div>';
                return;
            }
            var html = "";
            events.forEach(function (e) {
                html += '<div class="activity-item">'
                    + '<span class="activity-date">' + fmtDateShort(e.date) + '</span>'
                    + '<span class="activity-type ' + esc(e.type) + '">' + esc(e.type) + '</span>'
                    + '<span class="activity-text">' + esc(e.text) + '</span>'
                    + '</div>';
            });
            c.innerHTML = html;
        }).catch(function () {});
    }

    // ------------------------------------------------------------------ //
    // Documents                                                           //
    // ------------------------------------------------------------------ //
    function renderDocuments() {
        document.querySelectorAll(".doc-tab").forEach(function (t) {
            t.onclick = function () {
                document.querySelectorAll(".doc-tab").forEach(function (x) { x.classList.remove("active"); });
                document.querySelectorAll(".doc-tab-content").forEach(function (x) { x.classList.remove("active"); });
                t.classList.add("active");
                var tab = t.getAttribute("data-tab");
                document.getElementById(tab === "mine" ? "myDocsTab" : "projectDocsTab").classList.add("active");
            };
        });

        apiGet("/documents/all").then(function (docs) {
            var tbody = document.getElementById("myDocsBody");
            if (!docs || docs.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No documents generated yet.</td></tr>';
                return;
            }
            var html = "";
            docs.forEach(function (d) {
                var sk = skills.find(function (s) { return s.skill_name === d.skill_name; });
                html += '<tr><td>' + fmtDate(d.created_at) + '</td>'
                    + '<td>' + esc(sk ? sk.display_name : d.skill_name) + '</td>'
                    + '<td>' + esc(d.project_code || "\u2014") + '</td>'
                    + '<td>' + esc(d.file_name) + '</td>'
                    + '<td><button class="recent-download" onclick="window.open(\'' + esc(d.download_url) + '\')">Download</button></td></tr>';
            });
            tbody.innerHTML = html;
        }).catch(function () {});

        if (activeProject) {
            apiGet("/status").then(function (st) {
                var tbody = document.getElementById("projectDocsBody");
                if (!st || !st.recent_documents || st.recent_documents.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No documents for this project.</td></tr>';
                    return;
                }
                var html = "";
                st.recent_documents.forEach(function (d) {
                    var sk = skills.find(function (s) { return s.skill_name === d.skill_name; });
                    html += '<tr><td>' + fmtDate(d.created_at) + '</td>'
                        + '<td>' + esc(sk ? sk.display_name : d.skill_name) + '</td>'
                        + '<td>' + esc(d.file_name) + '</td>'
                        + '<td>' + esc((d.document_type || "").toUpperCase()) + '</td>'
                        + '<td><button class="recent-download" onclick="window.open(\'' + esc(d.download_url) + '\')">Download</button></td></tr>';
                });
                tbody.innerHTML = html;
            }).catch(function () {});
        }
    }

    // ------------------------------------------------------------------ //
    // Projects page                                                       //
    // ------------------------------------------------------------------ //
    function renderProjectsPage() {
        loadProjects().then(function () {
            updateProjectSelector();
            var c = document.getElementById("projectsList");
            if (projects.length === 0) {
                c.innerHTML = '<div class="empty-state"><p>No projects yet.</p></div>';
                return;
            }
            var html = "";
            projects.forEach(function (p) {
                var pct = Math.round(p.percent_complete || 0);
                var sel = activeProject === p.project_code ? " selected" : "";
                html += '<div class="project-card' + sel + '" data-code="' + esc(p.project_code) + '">'
                    + '<div class="project-card-header"><span class="project-card-name">' + esc(p.name) + '</span>'
                    + '<span class="status-badge ' + p.status + '">' + esc(p.status) + '</span></div>'
                    + '<div class="project-card-code">' + esc(p.project_code) + '</div>'
                    + (p.client_name ? '<div class="project-client">' + esc(p.client_name) + '</div>' : '')
                    + '<div class="project-progress"><div class="project-progress-bar"><div class="project-progress-fill" style="width:' + pct + '%"></div></div>'
                    + '<span class="project-progress-label">' + pct + '%</span></div></div>';
            });
            c.innerHTML = html;
            c.querySelectorAll(".project-card").forEach(function (card) {
                card.addEventListener("click", function () {
                    activeProject = card.getAttribute("data-code");
                    document.getElementById("activeProjectSelect").value = activeProject;
                    loadProjectStats().then(function () { renderProjectsPage(); });
                    toast("Project selected. Go to Dashboard to start working.", "info");
                });
            });
        });
    }

    // ------------------------------------------------------------------ //
    // Settings                                                            //
    // ------------------------------------------------------------------ //
    function renderSettings() {
        apiGet("/status").then(function (st) {
            if (!st) return;
            document.getElementById("settingsDailyCost").textContent = cents(st.today_cost_cents);
            document.getElementById("settingsMonthlyCost").textContent = cents(st.month_cost_cents);
            document.getElementById("settingsDailyLimit").textContent = "of " + cents(st.daily_limit_cents) + " daily limit";
            document.getElementById("settingsMonthlyLimit").textContent = "of " + cents(st.monthly_limit_cents) + " monthly limit";
            var dp = st.daily_limit_cents > 0 ? Math.min(100, st.today_cost_cents / st.daily_limit_cents * 100) : 0;
            var mp = st.monthly_limit_cents > 0 ? Math.min(100, st.month_cost_cents / st.monthly_limit_cents * 100) : 0;
            document.getElementById("settingsDailyFill").style.width = dp + "%";
            document.getElementById("settingsMonthlyFill").style.width = mp + "%";
        }).catch(function () {});

        apiGet("/health").then(function (h) {
            if (h && h.output_dir) document.getElementById("settingsOutputDir").textContent = h.output_dir;
        }).catch(function () {});
    }

    // ------------------------------------------------------------------ //
    // Project forms                                                       //
    // ------------------------------------------------------------------ //
    function handleProjectForm(form, afterSuccess) {
        form.addEventListener("submit", function (e) {
            e.preventDefault();
            var btn = form.querySelector('button[type="submit"]');
            var codeEl = form.querySelector('[name="project_code"]');
            var nameEl = form.querySelector('[name="name"]');
            if (!codeEl.value.trim() || !nameEl.value.trim()) {
                toast("Project code and name are required.", "error");
                return;
            }
            btn.disabled = true;
            btn.textContent = "Creating...";
            var data = {
                project_code: codeEl.value.trim(),
                name: nameEl.value.trim(),
                client_name: (form.querySelector('[name="client_name"]') || {}).value || "",
                project_type: (form.querySelector('[name="project_type"]') || {}).value || "commercial",
                status: "active",
                address: (form.querySelector('[name="address"]') || {}).value || "",
            };
            apiPost("/projects", data).then(function () {
                toast("Project '" + data.project_code + "' created!", "success");
                form.reset();
                activeProject = data.project_code;
                return loadProjects();
            }).then(function () {
                updateProjectSelector();
                document.getElementById("activeProjectSelect").value = activeProject;
                return loadProjectStats();
            }).then(function () {
                if (afterSuccess) afterSuccess();
            }).catch(function (err) {
                toast("Failed: " + err.message, "error");
            }).finally(function () {
                btn.disabled = false;
                btn.textContent = "Create Project";
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
    function fmtDate(s) { if (!s) return ""; try { var d = new Date(s); return isNaN(d) ? s : d.toLocaleDateString("en-US", {month:"short",day:"numeric",year:"numeric"}); } catch(e) { return s; } }
    function fmtDateShort(s) { if (!s) return ""; try { var d = new Date(s); return isNaN(d) ? s : d.toLocaleDateString("en-US", {month:"short",day:"numeric"}); } catch(e) { return s; } }
    function capitalize(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1).replace(/_/g, " ") : ""; }
    function esc(s) { if (s == null) return ""; var d = document.createElement("div"); d.appendChild(document.createTextNode(String(s))); return d.innerHTML; }

    // ------------------------------------------------------------------ //
    // Init                                                                //
    // ------------------------------------------------------------------ //
    function init() {
        document.querySelectorAll(".nav-tab").forEach(function (b) {
            b.addEventListener("click", function () { navigateTo(b.getAttribute("data-view")); });
        });

        document.getElementById("headerSettingsBtn").addEventListener("click", function () { navigateTo("settings"); });

        document.getElementById("alertDismiss").addEventListener("click", function () {
            document.getElementById("systemAlert").style.display = "none";
        });

        document.getElementById("activeProjectSelect").addEventListener("change", onProjectChange);

        var fp = document.getElementById("firstProjectForm");
        if (fp) handleProjectForm(fp, function () { renderDashboard(); });
        var ap = document.getElementById("addProjectForm");
        if (ap) handleProjectForm(ap, function () { renderProjectsPage(); });

        Promise.all([loadSkills(), loadProjects(), checkConfig()]).then(function () {
            updateProjectSelector();
            renderDashboard();
        });
    }

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
    else init();

})();
