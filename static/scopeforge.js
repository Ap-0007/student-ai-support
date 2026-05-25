(function () {
    const state = {
        templates: [],
        latestResult: null,
        billingLinks: null
    };

    function byId(id) {
        return document.getElementById(id);
    }

    function slugify(value) {
        return value
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, "-")
            .replace(/^-+|-+$/g, "")
            .slice(0, 48) || "scopeforge-proposal";
    }

    function renderList(target, items) {
        if (!target) {
            return;
        }

        target.innerHTML = "";
        items.forEach((item) => {
            const li = document.createElement("li");
            li.textContent = item;
            target.appendChild(li);
        });
    }

    function setText(id, value) {
        const element = byId(id);
        if (element) {
            element.textContent = value;
        }
    }

    function fillAppForm(template) {
        const mappings = {
            "client-name": template.client_name,
            "currency": template.currency,
            "service-type": template.service_type,
            "budget-band": template.budget_band,
            "urgency": template.urgency,
            "raw-request": template.raw_request
        };

        Object.entries(mappings).forEach(([id, value]) => {
            const field = byId(id);
            if (field) {
                field.value = value;
            }
        });
    }

    function downloadFile(filename, content, mimeType) {
        const blob = new Blob([content], { type: mimeType || "text/plain;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
    }

    async function copyText(content, target) {
        try {
            if (navigator.clipboard) {
                await navigator.clipboard.writeText(content);
                if (target) {
                    target.textContent = "Copied.";
                }
                return;
            }
        } catch (error) {
            // use fallback
        }

        const textarea = document.createElement("textarea");
        textarea.value = content;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand("copy");
        textarea.remove();
        if (target) {
            target.textContent = "Copied.";
        }
    }

    function setGenerateButtonState(isLoading) {
        const button = byId("generate-btn");
        if (!button) {
            return;
        }
        button.disabled = isLoading;
        button.textContent = isLoading ? "Generating..." : "Generate Proposal";
    }

    function setLeadStatus(form, text, isError) {
        const status = form.querySelector(".status");
        if (!status) {
            return;
        }
        status.textContent = text || "";
        status.style.color = isError ? "#9b2226" : "#1d6b57";
    }

    async function loadTemplates() {
        const container = byId("template-list");
        if (!container) {
            return;
        }

        try {
            const response = await fetch("/api/templates");
            state.templates = await response.json();
            container.innerHTML = "";

            state.templates.forEach((template) => {
                const button = document.createElement("button");
                button.className = "template-button";
                button.type = "button";
                button.innerHTML = `<strong>${template.name}</strong><br><small>${template.currency} • ${template.service_type}</small>`;
                button.addEventListener("click", () => fillAppForm(template));
                container.appendChild(button);
            });

            if (state.templates[0]) {
                fillAppForm(state.templates[0]);
            }
        } catch (error) {
            container.innerHTML = "<div class='tiny'>Template loading failed. You can still type your own brief.</div>";
        }
    }

    function renderResult(data) {
        state.latestResult = data;

        setText("project-label", data.project_label);
        setText("recommended-price", data.recommended_price);
        setText("timeline", data.timeline);
        setText("summary", data.summary);
        setText("one-liner", data.one_liner);
        setText("anchor-price", data.anchor_price);
        setText("payment-schedule", data.payment_schedule);
        setText("roi-pitch", data.roi_pitch);
        setText("next-step-cta", data.next_step_cta);
        setText("target-market", data.target_market);
        setText("proposal-email", data.proposal_email);
        setText("change-order-clause", data.change_order_clause);
        setText("proposal-markdown", data.proposal_markdown);

        renderList(byId("scope-items"), data.scope_items);
        renderList(byId("deliverables"), data.deliverables);
        renderList(byId("delivery-phases"), data.delivery_phases);
        renderList(byId("out-of-scope"), data.out_of_scope);
        renderList(byId("risk-flags"), data.risk_flags);
        renderList(byId("discovery-questions"), data.discovery_questions);
        renderList(byId("upsells"), data.upsells);

        const emptyState = byId("empty-state");
        const resultShell = byId("result-shell");
        if (emptyState) {
            emptyState.classList.add("hidden");
        }
        if (resultShell) {
            resultShell.classList.remove("hidden");
        }
    }

    async function generateProposal() {
        const rawRequest = byId("raw-request");
        if (!rawRequest || rawRequest.value.trim().length < 20) {
            alert("Add a more detailed client brief first.");
            return;
        }

        setGenerateButtonState(true);

        const payload = {
            client_name: byId("client-name").value.trim() || "Client",
            currency: byId("currency").value,
            service_type: byId("service-type").value,
            budget_band: byId("budget-band").value,
            urgency: byId("urgency").value,
            raw_request: rawRequest.value.trim()
        };

        try {
            const response = await fetch("/api/generate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                throw new Error("Generate failed");
            }

            const data = await response.json();
            renderResult(data);
        } catch (error) {
            alert("The proposal could not be generated. Check that the FastAPI server is running.");
        } finally {
            setGenerateButtonState(false);
        }
    }

    function wireAppActions() {
        const generateButton = byId("generate-btn");
        if (generateButton) {
            generateButton.addEventListener("click", generateProposal);
        }

        const copyEmailButton = byId("copy-email-btn");
        if (copyEmailButton) {
            copyEmailButton.addEventListener("click", async () => {
                if (!state.latestResult) {
                    return;
                }
                await copyText(state.latestResult.proposal_email, byId("copy-status"));
            });
        }

        const copyMarkdownButton = byId("copy-markdown-btn");
        if (copyMarkdownButton) {
            copyMarkdownButton.addEventListener("click", async () => {
                if (!state.latestResult) {
                    return;
                }
                await copyText(state.latestResult.proposal_markdown, byId("copy-status"));
            });
        }

        const downloadButton = byId("download-markdown-btn");
        if (downloadButton) {
            downloadButton.addEventListener("click", () => {
                if (!state.latestResult) {
                    return;
                }
                const name = slugify(state.latestResult.project_label);
                downloadFile(`${name}.md`, state.latestResult.proposal_markdown, "text/markdown;charset=utf-8");
            });
        }
    }

    function serializeLeadForm(form) {
        return {
            name: form.querySelector('[name="name"]').value.trim(),
            email: form.querySelector('[name="email"]').value.trim(),
            role: form.querySelector('[name="role"]').value.trim(),
            market: form.querySelector('[name="market"]').value.trim(),
            plan_interest: form.querySelector('[name="plan_interest"]').value.trim(),
            notes: (form.querySelector('[name="notes"]') || { value: "" }).value.trim()
        };
    }

    function wireLeadForms() {
        const forms = document.querySelectorAll(".lead-form");
        forms.forEach((form) => {
            form.addEventListener("submit", async (event) => {
                event.preventDefault();
                const payload = serializeLeadForm(form);

                if (!payload.name || !payload.email || !payload.role || !payload.market || !payload.plan_interest) {
                    setLeadStatus(form, "Fill every required field first.", true);
                    return;
                }

                const submitButton = form.querySelector('button[type="submit"]');
                if (submitButton) {
                    submitButton.disabled = true;
                    submitButton.textContent = "Saving...";
                }

                setLeadStatus(form, "");

                try {
                    const response = await fetch("/api/waitlist", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(payload)
                    });

                    const data = await response.json();
                    if (!response.ok) {
                        throw new Error(data.detail || "Lead save failed");
                    }

                    form.reset();
                    setLeadStatus(form, data.message, false);
                } catch (error) {
                    setLeadStatus(form, error.message || "Could not save lead.", true);
                } finally {
                    if (submitButton) {
                        submitButton.disabled = false;
                        submitButton.textContent = submitButton.dataset.label || "Join Waitlist";
                    }
                }
            });
        });
    }

    function updatePlanLinks(data) {
        state.billingLinks = data;

        const providerTarget = document.querySelector("[data-checkout-provider]");
        if (providerTarget) {
            providerTarget.textContent = data.checkout_provider;
        }

        data.plans.forEach((plan) => {
            const button = document.querySelector(`[data-plan-link="${plan.key}"]`);
            const note = document.querySelector(`[data-plan-note="${plan.key}"]`);

            if (button) {
                if (plan.enabled && plan.checkout_url) {
                    button.href = plan.checkout_url;
                    button.target = "_blank";
                    button.rel = "noreferrer";
                    button.textContent = `${plan.cta_label} ${plan.price}`;
                } else {
                    button.href = "#lead-name-pricing";
                    button.removeAttribute("target");
                    button.removeAttribute("rel");
                    button.textContent = "Request access";
                }
            }

            if (note) {
                note.textContent = plan.enabled
                    ? `Checkout is live via ${data.checkout_provider}.`
                    : `Set ${plan.key === "setup" ? "STRIPE_SETUP_URL" : `STRIPE_${plan.key.toUpperCase()}_URL`} to turn this into a live checkout button.`;
            }
        });
    }

    async function loadBillingLinks() {
        const hasPlanLinks = document.querySelector("[data-plan-link]");
        if (!hasPlanLinks) {
            return;
        }

        try {
            const response = await fetch("/api/billing-links");
            if (!response.ok) {
                throw new Error("Billing links unavailable");
            }
            const data = await response.json();
            updatePlanLinks(data);
        } catch (error) {
            // Leave fallback links pointing to the lead form
        }
    }

    function adminToken() {
        return byId("admin-token") ? byId("admin-token").value.trim() : "";
    }

    function setAdminStatus(message, isError) {
        const status = byId("admin-status");
        if (!status) {
            return;
        }
        status.textContent = message || "";
        status.style.color = isError ? "#9b2226" : "#1d6b57";
    }

    function leadSummary(leads) {
        const counts = {};
        leads.forEach((lead) => {
            counts[lead.plan_interest] = (counts[lead.plan_interest] || 0) + 1;
        });

        let topPlan = "N/A";
        let topCount = 0;
        Object.entries(counts).forEach(([plan, count]) => {
            if (count > topCount) {
                topPlan = plan;
                topCount = count;
            }
        });

        setText("lead-count", String(leads.length));
        setText("latest-email", leads[0] ? leads[0].email : "No leads yet");
        setText("top-plan", topPlan);
    }

    function renderLeadTable(leads) {
        const body = byId("lead-table-body");
        if (!body) {
            return;
        }

        body.innerHTML = "";

        if (!leads.length) {
            body.innerHTML = '<tr><td colspan="7" class="tiny">No leads captured yet.</td></tr>';
            leadSummary(leads);
            return;
        }

        leads.forEach((lead) => {
            const row = document.createElement("tr");
            row.innerHTML = `
                <td>${lead.created_at}</td>
                <td>${lead.name}</td>
                <td>${lead.email}</td>
                <td>${lead.role}</td>
                <td>${lead.market}</td>
                <td>${lead.plan_interest}</td>
                <td>${lead.notes || ""}</td>
            `;
            body.appendChild(row);
        });

        leadSummary(leads);
    }

    async function fetchAdminLeads() {
        const token = adminToken();
        if (!token) {
            setAdminStatus("Enter the admin token first.", true);
            return;
        }

        const button = byId("load-leads-btn");
        if (button) {
            button.disabled = true;
            button.textContent = "Loading...";
        }

        try {
            const response = await fetch("/api/admin/leads", {
                headers: {
                    Authorization: `Bearer ${token}`
                }
            });

            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.detail || "Could not load leads");
            }

            localStorage.setItem("scopeforge_admin_token", token);
            renderLeadTable(data.leads);
            setAdminStatus(`Loaded ${data.count} lead${data.count === 1 ? "" : "s"}.`, false);
        } catch (error) {
            setAdminStatus(error.message || "Could not load leads.", true);
        } finally {
            if (button) {
                button.disabled = false;
                button.textContent = "Load Leads";
            }
        }
    }

    async function downloadAdminCsv() {
        const token = adminToken();
        if (!token) {
            setAdminStatus("Enter the admin token first.", true);
            return;
        }

        const button = byId("download-leads-btn");
        if (button) {
            button.disabled = true;
            button.textContent = "Preparing...";
        }

        try {
            const response = await fetch("/api/admin/leads.csv", {
                headers: {
                    Authorization: `Bearer ${token}`
                }
            });

            if (!response.ok) {
                const errorData = await response.text();
                throw new Error(errorData || "Could not export leads");
            }

            const content = await response.text();
            localStorage.setItem("scopeforge_admin_token", token);
            downloadFile("scopeforge-leads.csv", content, "text/csv;charset=utf-8");
            setAdminStatus("CSV downloaded.", false);
        } catch (error) {
            setAdminStatus(error.message || "Could not export leads.", true);
        } finally {
            if (button) {
                button.disabled = false;
                button.textContent = "Download CSV";
            }
        }
    }

    function wireAdminPage() {
        const tokenField = byId("admin-token");
        if (!tokenField) {
            return;
        }

        const savedToken = localStorage.getItem("scopeforge_admin_token");
        if (savedToken) {
            tokenField.value = savedToken;
        }

        const loadButton = byId("load-leads-btn");
        if (loadButton) {
            loadButton.addEventListener("click", fetchAdminLeads);
        }

        const downloadButton = byId("download-leads-btn");
        if (downloadButton) {
            downloadButton.addEventListener("click", downloadAdminCsv);
        }
    }

    document.addEventListener("DOMContentLoaded", () => {
        loadTemplates();
        loadBillingLinks();
        wireAppActions();
        wireLeadForms();
        wireAdminPage();
    });
})();
