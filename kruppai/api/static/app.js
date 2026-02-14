/* ====================================================================== */
/* KruppAI — Frontend Application                                         */
/* Vanilla JS single-page application                                     */
/* ====================================================================== */

(function () {
    "use strict";

    // ------------------------------------------------------------------ //
    // Constants                                                           //
    // ------------------------------------------------------------------ //

    const API_BASE = "/api/v1";

    /** Emoji icons for each skill (keyed by skill_name). */
    const SKILL_ICONS = {
        daily_report:       "\uD83D\uDCCB",  // clipboard
        rfi_generator:      "\u2753",          // question mark
        meeting_minutes:    "\uD83D\uDDD3\uFE0F",  // calendar
        client_update:      "\u2709\uFE0F",    // envelope
        safety_talk:        "\u26D1\uFE0F",    // helmet
        punch_list:         "\u2705",          // check mark
        estimate_reviewer:  "\uD83D\uDCB0",   // money bag
        bid_comparison:     "\uD83D\uDCCA",   // chart
        change_order:       "\uD83D\uDD04",   // arrows
        schedule_variance:  "\uD83D\uDCC5",   // calendar
        submittal_tracker:  "\uD83D\uDCE6",   // package
        contract_checker:   "\uD83D\uDCDC",   // scroll
        proposal_generator: "\uD83D\uDCC4",   // page
        budget_forecaster:  "\uD83D\uDCC8",   // chart up
        closeout_assembler: "\uD83C\uDFC1",   // flag
        lessons_learned:    "\uD83D\uDCA1",   // light bulb
        case_study:         "\uD83C\uDFD7\uFE0F",  // building construction
        incident_report:    "\u26A0\uFE0F",    // warning
    };

    /** Phase labels for skill grouping. */
    const PHASE_LABELS = {
        1: "Field & Communication",
        2: "Analysis & Review",
        3: "Strategic & Institutional",
    };

    /** Human-readable labels and form configs for skill parameters. */
    const PARAM_CONFIG = {
        project:     { label: "Project",                type: "project-select",  placeholder: "" },
        notes:       { label: "Notes",                  type: "textarea",        placeholder: "Enter your field notes, observations, or details..." },
        issue:       { label: "Issue Description",      type: "textarea",        placeholder: "Describe the issue or question that needs clarification..." },
        type:        { label: "Meeting Type",           type: "select",          options: ["OAC Meeting", "Subcontractor Meeting", "Safety Meeting", "Internal Team Meeting", "Pre-Construction Meeting", "Closeout Meeting", "Other"] },
        topic:       { label: "Safety Topic",           type: "text",            placeholder: "e.g. Fall protection, Electrical safety, Heat illness" },
        description: { label: "Description",            type: "textarea",        placeholder: "Describe the change, scope, or details..." },
        reason:      { label: "Reason for Change",      type: "textarea",        placeholder: "Explain why this change is needed..." },
        trade:       { label: "Trade / Scope",          type: "text",            placeholder: "e.g. Electrical, Plumbing, HVAC" },
        bids:        { label: "Bid Details",            type: "textarea",        placeholder: "Enter bid information (amounts, bidders, scope)..." },
        file:        { label: "Upload File",            type: "file",            placeholder: "" },
    };

    /** Quick-action skills shown on the dashboard. */
    const QUICK_ACTIONS = [
        "daily_report",
        "rfi_generator",
        "meeting_minutes",
        "client_update",
        "safety_talk",
        "punch_list",
        "change_order",
        "incident_report",
    ];

    // ------------------------------------------------------------------ //
    // State                                                               //
    // ------------------------------------------------------------------ //

    let cachedSkills = [];
    let cachedProjects = [];
    let currentView = "dashboard";

    // ------------------------------------------------------------------ //
    // API Client                                                          //
    // ------------------------------------------------------------------ //

    async function apiGet(path) {
        const resp = await fetch(API_BASE + path);
        if (!resp.ok) {
            const body = await resp.json().catch(() => ({}));
            throw new Error(body.detail || `Request failed (${resp.status})`);
        }
        return resp.json();
    }

    async function apiPost(path, data) {
        const resp = await fetch(API_BASE + path, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data),
        });
        if (!resp.ok) {
            const body = await resp.json().catch(() => ({}));
            throw new Error(body.detail || `Request failed (${resp.status})`);
        }
        return resp.json();
    }

    async function apiPostForm(path, formData) {
        const resp = await fetch(API_BASE + path, {
            method: "POST",
            body: formData,
        });
        if (!resp.ok) {
            const body = await resp.json().catch(() => ({}));
            throw new Error(body.detail || `Request failed (${resp.status})`);
        }
        return resp.json();
    }

    // ------------------------------------------------------------------ //
    // Data Fetching                                                       //
    // ------------------------------------------------------------------ //

    async function fetchSkills() {
        try {
            cachedSkills = await apiGet("/skills");
        } catch (err) {
            console.error("Failed to load skills:", err);
            showToast("Could not load skills. Is the server running?", "error");
        }
    }

    async function fetchProjects() {
        try {
            cachedProjects = await apiGet("/projects");
        } catch (err) {
            console.error("Failed to load projects:", err);
        }
    }

    async function fetchStatus() {
        try {
            return await apiGet("/status");
        } catch (err) {
            console.error("Failed to load status:", err);
            return null;
        }
    }

    // ------------------------------------------------------------------ //
    // View Router                                                         //
    // ------------------------------------------------------------------ //

    function navigateTo(view) {
        currentView = view;

        document.querySelectorAll(".view").forEach(function (el) {
            el.classList.remove("active");
        });
        document.querySelectorAll(".nav-btn").forEach(function (el) {
            el.classList.remove("active");
        });

        var viewEl = document.getElementById("view-" + view);
        if (viewEl) viewEl.classList.add("active");

        var navBtn = document.querySelector('.nav-btn[data-view="' + view + '"]');
        if (navBtn) navBtn.classList.add("active");

        // Refresh data when switching views
        if (view === "dashboard") renderDashboard();
        if (view === "skills") renderSkills();
        if (view === "documents") renderDocuments();
        if (view === "projects") renderProjects();
    }

    // ------------------------------------------------------------------ //
    // Dashboard Rendering                                                 //
    // ------------------------------------------------------------------ //

    async function renderDashboard() {
        var status = await fetchStatus();
        if (status) {
            renderCostBars(status);
            renderRecentDocs(status.recent_documents);
            updateHeaderCost(status.today_cost_cents);
        }
        renderQuickActions();
    }

    function renderCostBars(status) {
        var dailyPct = status.daily_limit_cents > 0
            ? Math.min(100, (status.today_cost_cents / status.daily_limit_cents) * 100)
            : 0;
        var monthlyPct = status.monthly_limit_cents > 0
            ? Math.min(100, (status.month_cost_cents / status.monthly_limit_cents) * 100)
            : 0;

        var dailyFill = document.getElementById("dailyCostFill");
        dailyFill.style.width = dailyPct + "%";
        dailyFill.className = "cost-bar-fill";
        if (dailyPct > 80) dailyFill.classList.add("danger");
        else if (dailyPct > 60) dailyFill.classList.add("warning");

        document.getElementById("dailyCostLabel").textContent =
            formatCents(status.today_cost_cents) + " / " + formatCents(status.daily_limit_cents);

        var monthlyFill = document.getElementById("monthlyCostFill");
        monthlyFill.style.width = monthlyPct + "%";
        monthlyFill.className = "cost-bar-fill monthly";
        if (monthlyPct > 80) monthlyFill.classList.add("danger");
        else if (monthlyPct > 60) monthlyFill.classList.add("warning");

        document.getElementById("monthlyCostLabel").textContent =
            formatCents(status.month_cost_cents) + " / " + formatCents(status.monthly_limit_cents);
    }

    function updateHeaderCost(cents) {
        document.getElementById("headerCostBadge").textContent = formatCents(cents) + " today";
    }

    function renderRecentDocs(docs) {
        var container = document.getElementById("recentDocs");
        if (!docs || docs.length === 0) {
            container.innerHTML = '<p class="empty-state">No documents generated yet. Use a skill above to get started.</p>';
            return;
        }

        var html = "";
        docs.forEach(function (doc) {
            var skillMeta = cachedSkills.find(function (s) { return s.skill_name === doc.skill_name; });
            var displayName = skillMeta ? skillMeta.display_name : doc.skill_name;
            var icon = SKILL_ICONS[doc.skill_name] || "\uD83D\uDCC4";
            var dateStr = formatDate(doc.created_at);

            html += '<div class="recent-doc-item">'
                + '<div class="doc-info">'
                + '<span class="doc-name">' + icon + " " + escapeHtml(doc.file_name) + '</span>'
                + '<span class="doc-meta">' + escapeHtml(displayName) + ' &middot; ' + dateStr + '</span>'
                + '</div>'
                + '<button class="doc-download-btn" onclick="window.open(\'' + escapeHtml(doc.download_url) + '\')">Download</button>'
                + '</div>';
        });
        container.innerHTML = html;
    }

    function renderQuickActions() {
        var container = document.getElementById("quickActions");
        var html = "";

        QUICK_ACTIONS.forEach(function (skillName) {
            var skill = cachedSkills.find(function (s) { return s.skill_name === skillName; });
            if (!skill) return;
            var icon = SKILL_ICONS[skillName] || "\u2699\uFE0F";

            html += '<button class="quick-action-btn" data-skill="' + skillName + '">'
                + '<span class="qa-icon">' + icon + '</span>'
                + '<span class="qa-label">' + escapeHtml(skill.display_name) + '</span>'
                + '</button>';
        });
        container.innerHTML = html;

        container.querySelectorAll(".quick-action-btn").forEach(function (btn) {
            btn.addEventListener("click", function () {
                var skillName = btn.getAttribute("data-skill");
                openSkillModal(skillName);
            });
        });
    }

    // ------------------------------------------------------------------ //
    // Skills Rendering                                                    //
    // ------------------------------------------------------------------ //

    function renderSkills() {
        var container = document.getElementById("skillsContainer");
        var grouped = {};

        cachedSkills.forEach(function (skill) {
            var phase = skill.phase || 0;
            if (!grouped[phase]) grouped[phase] = [];
            grouped[phase].push(skill);
        });

        var html = "";
        [1, 2, 3].forEach(function (phase) {
            var skills = grouped[phase];
            if (!skills || skills.length === 0) return;

            html += '<div class="phase-group">'
                + '<div class="phase-header">'
                + '<span class="phase-badge">' + phase + '</span>'
                + '<span class="phase-title">Phase ' + phase + ': ' + (PHASE_LABELS[phase] || "") + '</span>'
                + '</div>'
                + '<div class="skills-grid">';

            skills.forEach(function (skill) {
                var icon = SKILL_ICONS[skill.skill_name] || "\u2699\uFE0F";
                var unavailable = !skill.available ? " unavailable" : "";
                var fileTag = skill.requires_file
                    ? '<span class="skill-tag file-required">File upload required</span>'
                    : '';

                html += '<div class="skill-card' + unavailable + '" data-skill="' + skill.skill_name + '">'
                    + '<div class="skill-card-top">'
                    + '<span class="skill-emoji">' + icon + '</span>'
                    + '<div class="skill-info">'
                    + '<div class="skill-name">' + escapeHtml(skill.display_name) + '</div>'
                    + '<div class="skill-desc">' + escapeHtml(skill.description) + '</div>'
                    + fileTag
                    + '</div>'
                    + '</div>'
                    + '<button class="skill-generate-btn">Generate</button>'
                    + '</div>';
            });

            html += '</div></div>';
        });

        container.innerHTML = html;

        container.querySelectorAll(".skill-generate-btn").forEach(function (btn) {
            btn.addEventListener("click", function () {
                var card = btn.closest(".skill-card");
                var skillName = card.getAttribute("data-skill");
                openSkillModal(skillName);
            });
        });
    }

    // ------------------------------------------------------------------ //
    // Documents Rendering                                                 //
    // ------------------------------------------------------------------ //

    async function renderDocuments() {
        var status = await fetchStatus();
        var tbody = document.getElementById("documentsBody");

        if (!status || !status.recent_documents || status.recent_documents.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No documents found.</td></tr>';
            return;
        }

        var html = "";
        status.recent_documents.forEach(function (doc) {
            var skillMeta = cachedSkills.find(function (s) { return s.skill_name === doc.skill_name; });
            var displayName = skillMeta ? skillMeta.display_name : doc.skill_name;
            var dateStr = formatDate(doc.created_at);

            html += '<tr>'
                + '<td>' + dateStr + '</td>'
                + '<td>' + escapeHtml(displayName) + '</td>'
                + '<td>' + escapeHtml(doc.file_name) + '</td>'
                + '<td>' + escapeHtml((doc.document_type || "").toUpperCase()) + '</td>'
                + '<td><button class="doc-download-btn" onclick="window.open(\'' + escapeHtml(doc.download_url) + '\')">Download</button></td>'
                + '</tr>';
        });
        tbody.innerHTML = html;
    }

    // ------------------------------------------------------------------ //
    // Projects Rendering                                                  //
    // ------------------------------------------------------------------ //

    async function renderProjects() {
        await fetchProjects();
        var container = document.getElementById("projectsList");

        if (cachedProjects.length === 0) {
            container.innerHTML = '<p class="empty-state">No projects found. Add one above.</p>';
            return;
        }

        var html = "";
        cachedProjects.forEach(function (proj) {
            var statusClass = proj.status.toLowerCase().replace(/\s+/g, "-");
            var pct = Math.round(proj.percent_complete || 0);

            html += '<div class="project-card">'
                + '<div class="project-card-header">'
                + '<span class="project-card-name">' + escapeHtml(proj.name) + '</span>'
                + '<span class="status-badge ' + statusClass + '">' + escapeHtml(proj.status) + '</span>'
                + '</div>'
                + '<div class="project-card-code">' + escapeHtml(proj.project_code) + '</div>'
                + (proj.client_name ? '<div class="project-client">' + escapeHtml(proj.client_name) + '</div>' : '')
                + '<div class="project-progress">'
                + '<div class="project-progress-bar"><div class="project-progress-fill" style="width:' + pct + '%"></div></div>'
                + '<span class="project-progress-label">' + pct + '%</span>'
                + '</div>'
                + '</div>';
        });
        container.innerHTML = html;
    }

    // ------------------------------------------------------------------ //
    // Skill Modal                                                         //
    // ------------------------------------------------------------------ //

    function openSkillModal(skillName) {
        var skill = cachedSkills.find(function (s) { return s.skill_name === skillName; });
        if (!skill) {
            showToast("Skill not found.", "error");
            return;
        }

        var modal = document.getElementById("skillModal");
        var title = document.getElementById("modalTitle");
        var body = document.getElementById("modalBody");

        var icon = SKILL_ICONS[skillName] || "\u2699\uFE0F";
        title.textContent = icon + " " + skill.display_name;

        // Build the form
        var formHtml = '<form id="skillForm" class="skill-modal-form">';
        formHtml += '<p style="color: var(--gray-600); font-size: 14px; margin-bottom: 20px;">'
            + escapeHtml(skill.description) + '</p>';

        var params = skill.required_params || [];
        params.forEach(function (param) {
            if (param === "file") return; // handled separately
            var config = PARAM_CONFIG[param] || { label: capitalize(param), type: "text", placeholder: "" };

            formHtml += '<div class="form-group">';
            formHtml += '<label for="param_' + param + '">' + escapeHtml(config.label) + '</label>';

            if (config.type === "project-select") {
                formHtml += '<select id="param_' + param + '" name="' + param + '" required>';
                formHtml += '<option value="">-- Select a Project --</option>';
                cachedProjects.forEach(function (proj) {
                    formHtml += '<option value="' + escapeHtml(proj.project_code) + '">'
                        + escapeHtml(proj.project_code + " - " + proj.name) + '</option>';
                });
                formHtml += '</select>';
                if (cachedProjects.length === 0) {
                    formHtml += '<span style="font-size: 12px; color: var(--warning); margin-top: 4px;">No projects found. Add a project in the Projects tab first.</span>';
                }
            } else if (config.type === "textarea") {
                formHtml += '<textarea id="param_' + param + '" name="' + param + '" placeholder="'
                    + escapeHtml(config.placeholder) + '" rows="4" required></textarea>';
            } else if (config.type === "select") {
                formHtml += '<select id="param_' + param + '" name="' + param + '" required>';
                (config.options || []).forEach(function (opt) {
                    formHtml += '<option value="' + escapeHtml(opt) + '">' + escapeHtml(opt) + '</option>';
                });
                formHtml += '</select>';
            } else {
                formHtml += '<input type="text" id="param_' + param + '" name="' + param + '" placeholder="'
                    + escapeHtml(config.placeholder) + '" required>';
            }

            formHtml += '</div>';
        });

        // File upload if required
        if (skill.requires_file) {
            formHtml += '<div class="form-group">';
            formHtml += '<label for="param_file">Upload File</label>';
            formHtml += '<input type="file" id="param_file" name="file" accept=".pdf,.docx,.xlsx,.xls,.csv,.png,.jpg,.jpeg" required>';
            formHtml += '<span style="font-size: 12px; color: var(--gray-500); margin-top: 2px;">Accepted: PDF, DOCX, XLSX, CSV, or images</span>';
            formHtml += '</div>';
        }

        formHtml += '<button type="submit" class="btn btn-primary btn-lg" style="width: 100%; margin-top: 8px;">'
            + 'Generate Document</button>';
        formHtml += '</form>';

        body.innerHTML = formHtml;
        modal.classList.add("open");

        // Bind form submit
        document.getElementById("skillForm").addEventListener("submit", function (e) {
            e.preventDefault();
            executeSkill(skillName, skill);
        });
    }

    function closeModal() {
        document.getElementById("skillModal").classList.remove("open");
    }

    async function executeSkill(skillName, skill) {
        var body = document.getElementById("modalBody");
        var form = document.getElementById("skillForm");

        // Collect parameters
        var params = {};
        var projectCode = null;
        var fileInput = null;
        var requiredParams = skill.required_params || [];

        requiredParams.forEach(function (param) {
            if (param === "file") {
                fileInput = document.getElementById("param_file");
                return;
            }
            var el = document.getElementById("param_" + param);
            if (el) {
                if (param === "project") {
                    projectCode = el.value;
                } else {
                    params[param] = el.value;
                }
            }
        });

        // Also check for file upload if required
        if (skill.requires_file && !fileInput) {
            fileInput = document.getElementById("param_file");
        }

        // Show loading state
        body.innerHTML = '<div class="loading-state">'
            + '<div class="spinner spinner-lg"></div>'
            + '<p>Generating your document...</p>'
            + '<p style="font-size: 13px; color: var(--gray-400);">This may take 15-60 seconds depending on the skill.</p>'
            + '</div>';

        try {
            var result;

            if (skill.requires_file && fileInput && fileInput.files.length > 0) {
                // Multipart form upload
                var formData = new FormData();
                formData.append("file", fileInput.files[0]);
                if (projectCode) formData.append("project_code", projectCode);
                formData.append("parameters", JSON.stringify(params));

                result = await apiPostForm("/skills/" + skillName + "/execute-with-file", formData);
            } else {
                // JSON request
                result = await apiPost("/skills/" + skillName + "/execute", {
                    skill_name: skillName,
                    project_code: projectCode,
                    parameters: params,
                });
            }

            if (result.success) {
                renderSuccessResult(result, skill);
                showToast("Document generated successfully!", "success");
            } else {
                renderErrorResult(result.error || "An unknown error occurred.");
                showToast("Generation failed. See details in the dialog.", "error");
            }
        } catch (err) {
            renderErrorResult(err.message || "Network error. Please try again.");
            showToast("Request failed: " + err.message, "error");
        }
    }

    function renderSuccessResult(result, skill) {
        var body = document.getElementById("modalBody");
        var costStr = result.cost_cents != null ? formatCents(result.cost_cents) : "$0.00";
        var tokensStr = result.tokens_used != null ? result.tokens_used.toLocaleString() : "0";

        var html = '<div class="result-state success">'
            + '<div class="result-icon">\u2705</div>'
            + '<h3>Document Generated</h3>'
            + '<p>Your ' + escapeHtml(skill.display_name) + ' has been created and is ready for download.</p>'
            + '<div class="result-stats">'
            + '<div>Cost: <span>' + costStr + '</span></div>'
            + '<div>Tokens: <span>' + tokensStr + '</span></div>'
            + '</div>';

        if (result.download_url) {
            html += '<a href="' + escapeHtml(result.download_url) + '" class="btn btn-primary btn-lg" '
                + 'style="display: inline-flex; text-decoration: none;" download>Download Document</a>';
        }

        html += '<button class="btn btn-secondary" style="margin-left: 8px; margin-top: 8px;" onclick="document.getElementById(\'skillModal\').classList.remove(\'open\')">Close</button>';
        html += '</div>';

        body.innerHTML = html;

        // Refresh dashboard cost
        fetchStatus().then(function (status) {
            if (status) {
                renderCostBars(status);
                updateHeaderCost(status.today_cost_cents);
            }
        });
    }

    function renderErrorResult(errorMsg) {
        var body = document.getElementById("modalBody");

        var html = '<div class="result-state error">'
            + '<div class="result-icon">\u274C</div>'
            + '<h3>Generation Failed</h3>'
            + '<p>' + escapeHtml(errorMsg) + '</p>'
            + '<button class="btn btn-secondary" onclick="document.getElementById(\'skillModal\').classList.remove(\'open\')">Close</button>'
            + '</div>';

        body.innerHTML = html;
    }

    // ------------------------------------------------------------------ //
    // Project Form                                                        //
    // ------------------------------------------------------------------ //

    function setupProjectForm() {
        var form = document.getElementById("addProjectForm");
        if (!form) return;

        form.addEventListener("submit", async function (e) {
            e.preventDefault();
            var submitBtn = form.querySelector('button[type="submit"]');
            submitBtn.disabled = true;
            submitBtn.textContent = "Adding...";

            var data = {
                project_code: form.project_code.value.trim(),
                name: form.name.value.trim(),
                client_name: form.client_name.value.trim() || null,
                project_type: form.project_type.value,
                status: "active",
                address: form.address.value.trim(),
            };

            try {
                await apiPost("/projects", data);
                showToast("Project added successfully!", "success");
                form.reset();
                await fetchProjects();
                renderProjects();
            } catch (err) {
                showToast("Failed to add project: " + err.message, "error");
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = "Add Project";
            }
        });
    }

    // ------------------------------------------------------------------ //
    // Toast Notifications                                                 //
    // ------------------------------------------------------------------ //

    function showToast(message, type) {
        type = type || "info";
        var container = document.getElementById("toastContainer");
        var toast = document.createElement("div");
        toast.className = "toast " + type;
        toast.textContent = message;
        container.appendChild(toast);

        setTimeout(function () {
            toast.classList.add("fade-out");
            setTimeout(function () {
                if (toast.parentNode) toast.parentNode.removeChild(toast);
            }, 300);
        }, 4000);
    }

    // ------------------------------------------------------------------ //
    // Utilities                                                           //
    // ------------------------------------------------------------------ //

    function formatCents(cents) {
        if (cents == null) return "$0.00";
        return "$" + (cents / 100).toFixed(2);
    }

    function formatDate(dateStr) {
        if (!dateStr) return "";
        try {
            var d = new Date(dateStr);
            if (isNaN(d.getTime())) return dateStr;
            return d.toLocaleDateString("en-US", {
                month: "short",
                day: "numeric",
                year: "numeric",
            });
        } catch (e) {
            return dateStr;
        }
    }

    function capitalize(str) {
        if (!str) return "";
        return str.charAt(0).toUpperCase() + str.slice(1).replace(/_/g, " ");
    }

    function escapeHtml(str) {
        if (str == null) return "";
        var div = document.createElement("div");
        div.appendChild(document.createTextNode(str));
        return div.innerHTML;
    }

    // ------------------------------------------------------------------ //
    // Navigation Event Binding                                            //
    // ------------------------------------------------------------------ //

    function setupNavigation() {
        document.querySelectorAll(".nav-btn").forEach(function (btn) {
            btn.addEventListener("click", function () {
                var view = btn.getAttribute("data-view");
                if (view) navigateTo(view);
            });
        });
    }

    function setupModal() {
        var modal = document.getElementById("skillModal");
        var closeBtn = document.getElementById("modalClose");

        closeBtn.addEventListener("click", closeModal);

        modal.addEventListener("click", function (e) {
            if (e.target === modal) closeModal();
        });

        document.addEventListener("keydown", function (e) {
            if (e.key === "Escape") closeModal();
        });
    }

    // ------------------------------------------------------------------ //
    // Auto Refresh                                                        //
    // ------------------------------------------------------------------ //

    function startAutoRefresh() {
        // Refresh status every 60 seconds if on the dashboard
        setInterval(function () {
            if (currentView === "dashboard") {
                fetchStatus().then(function (status) {
                    if (status) {
                        renderCostBars(status);
                        updateHeaderCost(status.today_cost_cents);
                    }
                });
            }
        }, 60000);
    }

    // ------------------------------------------------------------------ //
    // Initialization                                                      //
    // ------------------------------------------------------------------ //

    async function init() {
        setupNavigation();
        setupModal();
        setupProjectForm();

        // Load initial data in parallel
        await Promise.all([fetchSkills(), fetchProjects()]);

        // Render default view
        renderDashboard();

        // Start background refresh
        startAutoRefresh();
    }

    // Boot when DOM is ready
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }

})();
