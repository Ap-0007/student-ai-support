from __future__ import annotations

import math
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "scopeforge.db"

app = FastAPI(title="ScopeForge")


class GenerateRequest(BaseModel):
    client_name: str = Field(default="Client", max_length=80)
    currency: Literal["USD", "GBP", "EUR"] = "USD"
    service_type: Literal["website", "automation", "branding", "content"] = "website"
    budget_band: Literal["starter", "growth", "premium"] = "growth"
    urgency: Literal["normal", "rush"] = "normal"
    raw_request: str = Field(min_length=20, max_length=4000)


class GenerateResponse(BaseModel):
    product_name: str
    target_market: str
    project_label: str
    summary: str
    one_liner: str
    recommended_price: str
    anchor_price: str
    payment_schedule: str
    timeline: str
    scope_items: list[str]
    deliverables: list[str]
    delivery_phases: list[str]
    out_of_scope: list[str]
    risk_flags: list[str]
    discovery_questions: list[str]
    upsells: list[str]
    roi_pitch: str
    next_step_cta: str
    proposal_email: str
    proposal_markdown: str
    change_order_clause: str


class WaitlistRequest(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: str = Field(min_length=5, max_length=120)
    role: str = Field(min_length=2, max_length=60)
    market: str = Field(min_length=2, max_length=40)
    plan_interest: str = Field(min_length=2, max_length=40)
    notes: str = Field(default="", max_length=500)


class WaitlistResponse(BaseModel):
    ok: bool
    message: str


class BillingPlan(BaseModel):
    key: str
    name: str
    price: str
    checkout_url: Optional[str]
    cta_label: str
    enabled: bool


class BillingLinksResponse(BaseModel):
    checkout_provider: str
    plans: list[BillingPlan]


class LeadRecord(BaseModel):
    id: int
    created_at: str
    name: str
    email: str
    role: str
    market: str
    plan_interest: str
    notes: str


class LeadsResponse(BaseModel):
    count: int
    leads: list[LeadRecord]


CURRENCY_META = {
    "USD": {"symbol": "$", "hourly_rate": 105},
    "GBP": {"symbol": "GBP ", "hourly_rate": 85},
    "EUR": {"symbol": "EUR ", "hourly_rate": 95},
}

SERVICE_PRESETS = {
    "website": {
        "label": "Website Build",
        "base_scope": [
            "Discovery call and a written brief with clear acceptance criteria",
            "Page hierarchy and conversion-first structure",
            "Responsive build for the agreed core pages",
            "QA pass for current desktop and mobile browsers",
        ],
        "deliverables": [
            "A launch-ready marketing site",
            "A page-by-page scope summary",
            "Analytics, forms, or checkout setup if included in the brief",
            "Handoff notes for the client team",
        ],
        "out_of_scope": [
            "New pages beyond the agreed page count",
            "Custom backend platforms",
            "Long-form copywriting for every page",
            "Ongoing maintenance after launch",
        ],
        "upsells": [
            "Monthly maintenance and uptime checks",
            "Conversion-rate optimization sprint",
            "Quarterly landing page refreshes",
        ],
        "roi": "Position this as revenue infrastructure, not just a prettier website. The client is buying speed to launch and a clearer conversion path.",
        "price_multiplier": 1.0,
    },
    "automation": {
        "label": "Operations Automation",
        "base_scope": [
            "Workflow audit and process mapping",
            "Automation design for the selected business process",
            "Implementation inside Zapier, Make, Airtable, or a comparable tool stack",
            "Testing plus a short handoff guide for operators",
        ],
        "deliverables": [
            "A live workflow with clear triggers and actions",
            "An exception-handling checklist",
            "A short operating guide for the client team",
            "A list of follow-up workflows worth automating next",
        ],
        "out_of_scope": [
            "Unlimited workflows across the business",
            "Custom software outside the selected tool stack",
            "Vendor outages or third-party support tickets",
            "Large-team training sessions",
        ],
        "upsells": [
            "Monthly automation monitoring",
            "A second workflow at a bundle rate",
            "Dashboard and KPI reporting add-on",
        ],
        "roi": "Sell this as margin protection. Every repetitive admin step removed saves labor hours and reduces handoff mistakes.",
        "price_multiplier": 1.15,
    },
    "branding": {
        "label": "Branding Sprint",
        "base_scope": [
            "Brand direction workshop",
            "Primary logo or wordmark routes",
            "Color and typography system",
            "Mini brand guide for handoff",
        ],
        "deliverables": [
            "A visual identity system the client can actually reuse",
            "Primary lockups and asset exports",
            "A concise brand guide",
            "Launch recommendations for web and social rollout",
        ],
        "out_of_scope": [
            "Packaging, signage, and production files",
            "Unlimited revision rounds",
            "A full website unless separately quoted",
            "Trademark or legal review",
        ],
        "upsells": [
            "Social media kit",
            "Sales deck template",
            "Landing page design add-on",
        ],
        "roi": "Branding sells faster when framed as trust-building. The client is buying clarity, consistency, and a stronger first impression in-market.",
        "price_multiplier": 0.85,
    },
    "content": {
        "label": "Content System",
        "base_scope": [
            "Messaging audit and audience positioning",
            "Editorial plan for the chosen channels",
            "Drafting and revision of the agreed assets",
            "Light optimization for readability and conversion",
        ],
        "deliverables": [
            "A repeatable content cadence",
            "Finished content assets inside the agreed scope",
            "A messaging framework the client can reuse",
            "Ideas for the next content cycle",
        ],
        "out_of_scope": [
            "Paid ads management",
            "Unlimited content requests",
            "Deep technical interviews with external experts",
            "PR outreach or distribution partnerships",
        ],
        "upsells": [
            "Monthly retainer for fresh content",
            "Email nurture sequence bundle",
            "SEO refresh every quarter",
        ],
        "roi": "The sell is consistency. Clients do not just need one article or email; they need a system that keeps publishing without last-minute panic.",
        "price_multiplier": 0.75,
    },
}

BUDGET_RANGES = {
    "starter": {"USD": (1800, 3200), "GBP": (1500, 2600), "EUR": (1700, 3000)},
    "growth": {"USD": (3500, 7500), "GBP": (2900, 6200), "EUR": (3300, 7000)},
    "premium": {"USD": (8000, 18000), "GBP": (6600, 15000), "EUR": (7600, 17000)},
}

KEYWORD_RULES = [
    (("seo", "search engine", "rank on google"), "SEO setup and metadata pass"),
    (("analytics", "tracking", "ga4", "gtm"), "Analytics and reporting setup"),
    (("stripe", "subscription", "checkout", "payment"), "Payment or subscription flow"),
    (("booking", "calendar", "calendly"), "Booking workflow integration"),
    (("crm", "hubspot", "salesforce", "pipedrive"), "CRM sync or lead pipeline setup"),
    (("email", "newsletter", "mailchimp", "klaviyo"), "Email capture and lifecycle flow"),
    (("dashboard", "portal", "admin"), "Admin or dashboard workflow"),
    (("copy", "messaging", "headline"), "Copy support for the core conversion pages"),
    (("brand", "logo", "visual identity"), "Brand direction and visual system"),
    (("ai", "assistant", "chatbot"), "AI-assisted workflow definition"),
    (("multi language", "multilingual", "translate"), "Secondary language setup"),
    (("api", "integration", "webhook"), "Third-party integration layer"),
    (("rush", "asap", "urgent", "next week"), "Compressed delivery plan"),
]

PROJECT_TEMPLATES = [
    {
        "id": "saas-landing",
        "name": "SaaS Landing Page",
        "client_name": "Westbridge Labs",
        "currency": "USD",
        "service_type": "website",
        "budget_band": "growth",
        "urgency": "rush",
        "raw_request": "We need a landing page for our B2B SaaS, plus pricing, analytics, and a Stripe checkout. The founder wants it live next week and may also want CRM and email integration if it fits. We have rough copy but no clear page structure yet.",
    },
    {
        "id": "agency-automation",
        "name": "Agency Lead Automation",
        "client_name": "Hawthorne Studio",
        "currency": "GBP",
        "service_type": "automation",
        "budget_band": "growth",
        "urgency": "normal",
        "raw_request": "We run a small agency in London and want to automate inbound leads from forms into HubSpot, trigger onboarding emails, and create project records in Airtable. If possible we also want a reporting dashboard and a Slack alert for high-value leads.",
    },
    {
        "id": "founder-rebrand",
        "name": "Startup Rebrand",
        "client_name": "Luma Freight",
        "currency": "EUR",
        "service_type": "branding",
        "budget_band": "premium",
        "urgency": "normal",
        "raw_request": "We are repositioning from a logistics marketplace to a software platform. We need a cleaner visual identity, a sharper story for European buyers, and launch assets for the new site and social channels.",
    },
]

BILLING_PLANS = [
    {"key": "solo", "name": "Solo", "price": "$19/mo", "env": "STRIPE_SOLO_URL"},
    {"key": "studio", "name": "Studio", "price": "$49/mo", "env": "STRIPE_STUDIO_URL"},
    {"key": "agency", "name": "Agency", "price": "$129/mo", "env": "STRIPE_AGENCY_URL"},
    {"key": "setup", "name": "Done-for-you setup", "price": "From $800", "env": "STRIPE_SETUP_URL"},
]


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS waitlist_leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                role TEXT NOT NULL,
                market TEXT NOT NULL,
                plan_interest TEXT NOT NULL,
                notes TEXT NOT NULL
            )
            """
        )


def money(currency: str, amount: int) -> str:
    symbol = CURRENCY_META[currency]["symbol"]
    return f"{symbol}{amount:,.0f}"


def detect_features(raw_request: str) -> list[str]:
    lower_text = raw_request.lower()
    matches: list[str] = []
    for keywords, label in KEYWORD_RULES:
        if any(keyword in lower_text for keyword in keywords):
            matches.append(label)
    return matches


def complexity_score(raw_request: str, urgency: str, features: list[str]) -> int:
    word_count = len(raw_request.split())
    score = max(1, math.ceil(word_count / 45))
    score += len(features)
    if urgency == "rush":
        score += 2
    return min(score, 9)


def target_market_label(currency: str) -> str:
    return {
        "USD": "North American clients",
        "GBP": "UK clients",
        "EUR": "EU clients",
    }[currency]


def build_project_label(service_type: str, raw_request: str) -> str:
    lower_text = raw_request.lower()
    base_label = SERVICE_PRESETS[service_type]["label"]
    if service_type == "website" and "landing page" in lower_text:
        return "Landing Page Build"
    if service_type == "automation" and "lead" in lower_text:
        return "Lead Funnel Automation"
    if service_type == "branding" and "rebrand" in lower_text:
        return "Rebrand Sprint"
    if service_type == "content" and "email" in lower_text:
        return "Email Content System"
    return base_label


def recommended_price(currency: str, service_type: str, budget_band: str, score: int) -> tuple[str, int]:
    low, high = BUDGET_RANGES[budget_band][currency]
    multiplier = SERVICE_PRESETS[service_type]["price_multiplier"]
    adjusted_low = int(low * multiplier)
    adjusted_high = int(high * multiplier)
    ratio = min(score / 9, 1)
    anchor = int(adjusted_low + ((adjusted_high - adjusted_low) * ratio))
    band_low = int(anchor * 0.9)
    band_high = int(anchor * 1.12)
    return f"{money(currency, band_low)} to {money(currency, band_high)}", anchor


def payment_schedule(currency: str, anchor_price: int) -> str:
    first = int(anchor_price * 0.5)
    second = int(anchor_price * 0.3)
    final = anchor_price - first - second
    return (
        f"50% upfront ({money(currency, first)}), "
        f"30% after midpoint approval ({money(currency, second)}), "
        f"20% before launch or final delivery ({money(currency, final)})."
    )


def timeline_label(score: int, urgency: str) -> str:
    if score <= 2:
        weeks = "1 to 2 weeks"
    elif score <= 4:
        weeks = "2 to 4 weeks"
    elif score <= 6:
        weeks = "4 to 6 weeks"
    else:
        weeks = "6 to 9 weeks"
    if urgency == "rush":
        return f"{weeks} with rush planning and faster client turnaround required"
    return weeks


def build_scope(service_type: str, features: list[str]) -> list[str]:
    scope = list(SERVICE_PRESETS[service_type]["base_scope"])
    for feature in features:
        if feature not in scope:
            scope.append(feature)
    return scope[:8]


def build_deliverables(service_type: str, features: list[str]) -> list[str]:
    deliverables = list(SERVICE_PRESETS[service_type]["deliverables"])
    if "Copy support for the core conversion pages" in features:
        deliverables.append("Edited core messaging for the launch funnel")
    if "Analytics and reporting setup" in features:
        deliverables.append("A basic reporting layer for launch KPIs")
    return deliverables[:6]


def build_delivery_phases(service_type: str, urgency: str, features: list[str]) -> list[str]:
    phases = [
        "Phase 1: Discovery, assumptions, and scope lock",
        "Phase 2: Build or execution of the agreed first deliverable set",
        "Phase 3: QA, feedback pass, and handoff",
    ]
    if service_type == "automation":
        phases[1] = "Phase 2: Workflow build, integration setup, and exception handling"
    if service_type == "branding":
        phases[1] = "Phase 2: Design routes, refinement, and selected direction"
    if service_type == "content":
        phases[1] = "Phase 2: Content drafting, revision, and asset packaging"
    if "Compressed delivery plan" in features or urgency == "rush":
        phases.append("Rush note: client feedback windows must be limited to maintain the compressed schedule")
    return phases


def build_out_of_scope(service_type: str, features: list[str]) -> list[str]:
    out_of_scope = list(SERVICE_PRESETS[service_type]["out_of_scope"])
    if "Compressed delivery plan" in features:
        out_of_scope.append("After-hours support unless explicitly priced as rush coverage")
    if "Third-party integration layer" in features:
        out_of_scope.append("Vendor-side API changes or platform outages")
    return out_of_scope[:6]


def build_risks(raw_request: str, score: int, features: list[str]) -> list[str]:
    lower_text = raw_request.lower()
    risks: list[str] = []

    if score >= 5:
        risks.append("The brief mixes multiple workstreams, so scope creep is likely unless phase boundaries are written down early.")
    if "dashboard" in lower_text or "portal" in lower_text:
        risks.append("Dashboard-style asks usually hide permissions, edge cases, and admin complexity that clients do not mention upfront.")
    if "seo" in lower_text and "content" in lower_text:
        risks.append("SEO deliverables should be positioned as best-effort work, not guaranteed rankings.")
    if "Payment or subscription flow" in features:
        risks.append("Payment flows require explicit decisions on tax, refunds, and compliance before build begins.")
    if "asap" in lower_text or "next week" in lower_text or "urgent" in lower_text:
        risks.append("A short deadline only works if the client agrees in writing to faster feedback windows and fewer review cycles.")
    if not risks:
        risks.append("The biggest risk is vague approval criteria, so define what 'done' means before any production work starts.")

    return risks[:4]


def build_questions(service_type: str, raw_request: str) -> list[str]:
    lower_text = raw_request.lower()
    prompts = [
        "Who is the primary buyer or end user for this project?",
        "What single business outcome matters most in the first 30 days after launch?",
        "What assets already exist: copy, brand files, data, logins, or visual references?",
        "Who gives final approval, and how quickly can they review work?",
    ]

    if "price" not in lower_text and "budget" not in lower_text:
        prompts.append("What budget range has already been approved internally?")
    if service_type in {"website", "automation"}:
        prompts.append("Which integrations are must-have on day one versus nice-to-have later?")
    if service_type == "content":
        prompts.append("How many deliverables per month are actually needed to hit the target outcome?")
    if service_type == "branding":
        prompts.append("Which brands feel directionally right or wrong for the repositioning?")

    return prompts[:6]


def build_upsells(service_type: str, currency: str, anchor_price: int) -> list[str]:
    presets = list(SERVICE_PRESETS[service_type]["upsells"])
    retainers = {
        "website": int(anchor_price * 0.08),
        "automation": int(anchor_price * 0.1),
        "branding": int(anchor_price * 0.07),
        "content": int(anchor_price * 0.25),
    }
    presets.append(f"Monthly support retainer starting around {money(currency, retainers[service_type])}")
    return presets[:4]


def build_summary(client_name: str, target_market: str, project_label: str, timeline: str, raw_request: str) -> str:
    short_request = " ".join(raw_request.strip().split())
    short_request = short_request[:180].rstrip()
    return (
        f"{client_name} needs a {project_label.lower()} positioned for {target_market}. "
        f"The most defensible offer is a defined first phase with a {timeline.lower()} timeline, "
        f"anchored to this brief: '{short_request}'."
    )


def build_one_liner(service_type: str, target_market: str) -> str:
    lines = {
        "website": f"Sell a fixed-scope launch build for {target_market} instead of a vague full-site promise.",
        "automation": f"Sell a single workflow win for {target_market}, then upsell monitoring and adjacent automations.",
        "branding": f"Sell a defined sprint for {target_market}, not open-ended creative exploration.",
        "content": f"Sell a repeatable publishing system for {target_market}, then convert into a retainer.",
    }
    return lines[service_type]


def build_roi_pitch(service_type: str) -> str:
    return SERVICE_PRESETS[service_type]["roi"]


def build_next_step_cta(service_type: str, currency: str, anchor_price: int) -> str:
    paid_audit = max(int(anchor_price * 0.18), 350)
    if service_type == "automation":
        return f"Offer a paid workflow audit first at about {money(currency, paid_audit)} and credit it toward implementation if they proceed."
    if service_type == "website":
        return f"Offer a paid strategy and wireframe sprint first at about {money(currency, paid_audit)} before the full build."
    if service_type == "branding":
        return f"Offer a paid brand direction workshop first at about {money(currency, paid_audit)} before the identity sprint."
    return f"Offer a paid messaging and editorial planning sprint first at about {money(currency, paid_audit)} before the full retainer."


def build_proposal_email(
    client_name: str,
    project_label: str,
    price_range: str,
    timeline: str,
    scope_items: list[str],
    out_of_scope: list[str],
) -> str:
    core_scope = "; ".join(scope_items[:4])
    boundary = out_of_scope[0]
    return (
        f"Hi {client_name},\n\n"
        f"Based on your brief, I would scope this as a focused {project_label.lower()} phase. "
        f"The recommended investment is {price_range}, with an estimated delivery window of {timeline}. "
        f"That price covers {core_scope}.\n\n"
        f"To keep the project efficient, I would treat {boundary.lower()} as a separate add-on if it comes up later. "
        "If this direction looks right, I can convert this into a final proposal with milestones and a start date."
    )


def build_change_order_clause(currency: str, service_type: str) -> str:
    hourly_rate = CURRENCY_META[currency]["hourly_rate"]
    labels = {
        "website": "new pages, extra integrations, or extra revision rounds",
        "automation": "extra workflows, extra apps, or new exception-handling rules",
        "branding": "new collateral, extra design routes, or added revision rounds",
        "content": "extra deliverables, new channels, or strategy outside the agreed cadence",
    }
    return (
        f"Any requests outside the agreed scope, including {labels[service_type]}, "
        f"will be quoted separately as a fixed add-on or at {money(currency, hourly_rate)}/hour. "
        "Work on the change starts only after written approval."
    )


def build_proposal_markdown(payload: dict[str, object]) -> str:
    scope_items = "\n".join(f"- {item}" for item in payload["scope_items"])
    deliverables = "\n".join(f"- {item}" for item in payload["deliverables"])
    phases = "\n".join(f"- {item}" for item in payload["delivery_phases"])
    out_of_scope = "\n".join(f"- {item}" for item in payload["out_of_scope"])
    risks = "\n".join(f"- {item}" for item in payload["risk_flags"])
    questions = "\n".join(f"- {item}" for item in payload["discovery_questions"])
    upsells = "\n".join(f"- {item}" for item in payload["upsells"])

    return (
        f"# {payload['project_label']}\n\n"
        f"## Summary\n{payload['summary']}\n\n"
        f"## Commercials\n"
        f"- Recommended price: {payload['recommended_price']}\n"
        f"- Anchor price: {payload['anchor_price']}\n"
        f"- Timeline: {payload['timeline']}\n"
        f"- Payment schedule: {payload['payment_schedule']}\n\n"
        f"## Included Scope\n{scope_items}\n\n"
        f"## Deliverables\n{deliverables}\n\n"
        f"## Delivery Phases\n{phases}\n\n"
        f"## Out Of Scope\n{out_of_scope}\n\n"
        f"## Risks\n{risks}\n\n"
        f"## Discovery Questions\n{questions}\n\n"
        f"## Upsells\n{upsells}\n\n"
        f"## ROI Pitch\n{payload['roi_pitch']}\n\n"
        f"## Change-Order Clause\n{payload['change_order_clause']}\n\n"
        f"## Proposal Email Draft\n{payload['proposal_email']}\n"
    )


def generate_scope_plan(request: GenerateRequest) -> GenerateResponse:
    features = detect_features(request.raw_request)
    score = complexity_score(request.raw_request, request.urgency, features)
    project_label = build_project_label(request.service_type, request.raw_request)
    target_market = target_market_label(request.currency)
    price_range, anchor_price_value = recommended_price(
        request.currency,
        request.service_type,
        request.budget_band,
        score,
    )
    timeline = timeline_label(score, request.urgency)
    scope_items = build_scope(request.service_type, features)
    deliverables = build_deliverables(request.service_type, features)
    delivery_phases = build_delivery_phases(request.service_type, request.urgency, features)
    out_of_scope = build_out_of_scope(request.service_type, features)
    payment = payment_schedule(request.currency, anchor_price_value)
    proposal_email = build_proposal_email(
        request.client_name,
        project_label,
        price_range,
        timeline,
        scope_items,
        out_of_scope,
    )
    change_order_clause = build_change_order_clause(request.currency, request.service_type)

    payload = {
        "product_name": "ScopeForge",
        "target_market": target_market,
        "project_label": project_label,
        "summary": build_summary(
            request.client_name,
            target_market,
            project_label,
            timeline,
            request.raw_request,
        ),
        "one_liner": build_one_liner(request.service_type, target_market),
        "recommended_price": price_range,
        "anchor_price": money(request.currency, anchor_price_value),
        "payment_schedule": payment,
        "timeline": timeline,
        "scope_items": scope_items,
        "deliverables": deliverables,
        "delivery_phases": delivery_phases,
        "out_of_scope": out_of_scope,
        "risk_flags": build_risks(request.raw_request, score, features),
        "discovery_questions": build_questions(request.service_type, request.raw_request),
        "upsells": build_upsells(request.service_type, request.currency, anchor_price_value),
        "roi_pitch": build_roi_pitch(request.service_type),
        "next_step_cta": build_next_step_cta(request.service_type, request.currency, anchor_price_value),
        "proposal_email": proposal_email,
        "change_order_clause": change_order_clause,
    }
    payload["proposal_markdown"] = build_proposal_markdown(payload)
    return GenerateResponse(**payload)


def save_waitlist_lead(request: WaitlistRequest) -> None:
    if "@" not in request.email or "." not in request.email.split("@")[-1]:
        raise ValueError("Invalid email address")
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            INSERT INTO waitlist_leads (
                created_at,
                name,
                email,
                role,
                market,
                plan_interest,
                notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(email) DO UPDATE SET
                created_at = excluded.created_at,
                name = excluded.name,
                role = excluded.role,
                market = excluded.market,
                plan_interest = excluded.plan_interest,
                notes = excluded.notes
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                request.name.strip(),
                request.email.lower(),
                request.role.strip(),
                request.market.strip(),
                request.plan_interest.strip(),
                request.notes.strip(),
            ),
        )


def get_checkout_provider() -> str:
    return os.getenv("CHECKOUT_PROVIDER", "Stripe Payment Links")


def get_billing_links() -> BillingLinksResponse:
    plans: list[BillingPlan] = []
    for plan in BILLING_PLANS:
        checkout_url = os.getenv(plan["env"], "").strip() or None
        plans.append(
            BillingPlan(
                key=plan["key"],
                name=plan["name"],
                price=plan["price"],
                checkout_url=checkout_url,
                cta_label="Buy now" if checkout_url else "Request access",
                enabled=bool(checkout_url),
            )
        )
    return BillingLinksResponse(
        checkout_provider=get_checkout_provider(),
        plans=plans,
    )


def get_admin_token() -> str:
    return os.getenv("ADMIN_TOKEN", "").strip()


def require_admin_token(token: Optional[str]) -> None:
    configured = get_admin_token()
    if not configured:
        raise HTTPException(
            status_code=503,
            detail="ADMIN_TOKEN is not configured on the server.",
        )

    if token != configured:
        raise HTTPException(status_code=401, detail="Invalid admin token.")


def fetch_leads() -> list[LeadRecord]:
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT id, created_at, name, email, role, market, plan_interest, notes
            FROM waitlist_leads
            ORDER BY created_at DESC, id DESC
            """
        ).fetchall()

    return [LeadRecord(**dict(row)) for row in rows]


def leads_csv(leads: list[LeadRecord]) -> str:
    header = "id,created_at,name,email,role,market,plan_interest,notes"
    rows = [header]
    for lead in leads:
        values = [
            str(lead.id),
            lead.created_at,
            lead.name,
            lead.email,
            lead.role,
            lead.market,
            lead.plan_interest,
            lead.notes,
        ]
        escaped = ['"' + value.replace('"', '""') + '"' for value in values]
        rows.append(",".join(escaped))
    return "\n".join(rows) + "\n"


init_db()
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/")
async def serve_landing() -> FileResponse:
    return FileResponse(str(BASE_DIR / "index.html"))


@app.get("/app")
async def serve_app_page() -> FileResponse:
    return FileResponse(str(BASE_DIR / "app.html"))


@app.get("/pricing")
async def serve_pricing() -> FileResponse:
    return FileResponse(str(BASE_DIR / "pricing.html"))


@app.get("/admin")
async def serve_admin() -> FileResponse:
    return FileResponse(str(BASE_DIR / "admin.html"))


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/templates")
async def templates() -> list[dict[str, str]]:
    return PROJECT_TEMPLATES


@app.get("/api/billing-links", response_model=BillingLinksResponse)
async def billing_links() -> BillingLinksResponse:
    return get_billing_links()


@app.post("/api/generate", response_model=GenerateResponse)
async def generate_endpoint(request: GenerateRequest) -> GenerateResponse:
    return generate_scope_plan(request)


@app.post("/api/waitlist", response_model=WaitlistResponse)
async def waitlist_endpoint(request: WaitlistRequest) -> WaitlistResponse:
    try:
        save_waitlist_lead(request)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return WaitlistResponse(ok=True, message="Lead saved. You can now follow up manually or plug this into email automation.")


@app.get("/api/admin/leads", response_model=LeadsResponse)
async def admin_leads(authorization: Optional[str] = Header(default=None)) -> LeadsResponse:
    token = authorization.removeprefix("Bearer ").strip() if authorization else None
    require_admin_token(token)
    leads = fetch_leads()
    return LeadsResponse(count=len(leads), leads=leads)


@app.get("/api/admin/leads.csv")
async def admin_leads_csv(authorization: Optional[str] = Header(default=None)) -> PlainTextResponse:
    token = authorization.removeprefix("Bearer ").strip() if authorization else None
    require_admin_token(token)
    csv_content = leads_csv(fetch_leads())
    response = PlainTextResponse(csv_content, media_type="text/csv")
    response.headers["Content-Disposition"] = 'attachment; filename="scopeforge-leads.csv"'
    return response
