# ScopeForge

ScopeForge is a small FastAPI product you can upload immediately.

It now includes:

- a public landing page at `/`
- a working generator app at `/app`
- a pricing page at `/pricing`
- an admin page at `/admin`
- lead capture stored in local SQLite
- configurable Stripe-style checkout links
- proposal output designed for freelancers, consultants, and small agencies selling to North America, the UK, and the EU

## What it does

Paste a rough client brief and ScopeForge generates:

- a scope summary
- a one-line sales angle
- a Western-market price range in USD, GBP, or EUR
- an anchor price
- a payment schedule
- delivery phases
- deliverables
- out-of-scope boundaries
- risk flags
- discovery questions
- upsells
- proposal email copy
- a change-order clause
- downloadable markdown proposal text

## Why this is monetisable

This is not a generic AI toy. It addresses a real commercial problem:

- freelancers underprice messy client requests
- small agencies need repeatable proposal output
- consultants need faster turnaround on scoped offers

Suggested offers:

- Solo: USD 19/month
- Studio: USD 49/month
- Agency: USD 129/month
- Done-for-you setup: from USD 800 one-off

## Stack

- FastAPI
- plain HTML, CSS, and JS
- SQLite for lead capture
- no external AI or vector database dependency

## Run locally

```bash
cd /Users/amogh/Documents/side_project
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Then open:

- [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- [http://127.0.0.1:8000/app](http://127.0.0.1:8000/app)
- [http://127.0.0.1:8000/pricing](http://127.0.0.1:8000/pricing)
- [http://127.0.0.1:8000/admin](http://127.0.0.1:8000/admin)

## Environment variables

Copy `.env.example` into your own env setup and replace the placeholder values.

- `CHECKOUT_PROVIDER`
- `STRIPE_SOLO_URL`
- `STRIPE_STUDIO_URL`
- `STRIPE_AGENCY_URL`
- `STRIPE_SETUP_URL`
- `ADMIN_TOKEN`

If the Stripe URLs are set, the pricing page buttons become live checkout links.
If they are missing, the page falls back to lead capture.

The admin page uses `ADMIN_TOKEN` as a simple bearer token gate for viewing and exporting leads.

## Deploy quickly

Included for faster upload:

- `Procfile` for Procfile-style hosts
- `render.yaml` for Render
- `.env.example` for deploy-time config

## Data

Lead capture is stored in:

- `/Users/amogh/Documents/side_project/scopeforge.db`

## Sensible next upgrades

1. Replace the token gate with real admin auth.
2. Add PDF export and branded templates.
3. Add usage limits by plan.
4. Add email automation for captured leads.
5. Add saved workspaces and customer accounts.
