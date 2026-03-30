# Northbridge Intelligence

**North East England property intelligence platform.**
Find below-market deals, track planning uplift, monitor regeneration zones.

Built for property developers, investors, and planning consultants operating across Gateshead, Newcastle, Sunderland, Durham, Teesside, and Northumberland.

---

## Stack

| Layer | Tech |
|-------|------|
| Backend | FastAPI + SQLAlchemy (async) + PostgreSQL |
| Frontend | Next.js 14 + TypeScript + Tailwind |
| Scoring | Custom deal engine (BMV, distress, planning, geo) |
| Infrastructure | Docker + docker-compose |

---

## Quick Start (Docker)

```bash
git clone <repo>
cd northbridge
cp .env.example .env
docker-compose up --build
```

Then seed demo data:
```bash
docker-compose exec backend python scripts/seed.py
```

- **App**: http://localhost:3000
- **API docs**: http://localhost:8000/docs
- **Admin login**: admin@northbridge.io / admin123
- **Demo login**: demo@northbridge.io / demo123

---

## Local Dev (without Docker)

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env — set DATABASE_URL to local postgres

# Run migrations
alembic upgrade head

# Seed data
python scripts/seed.py

# Start API
uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

---

## Architecture

```
northbridge/
├── backend/
│   ├── app/
│   │   ├── models/           SQLAlchemy models
│   │   ├── schemas/          Pydantic request/response schemas
│   │   ├── routers/          API endpoints
│   │   ├── auth/             JWT auth utilities
│   │   └── services/
│   │       ├── signals/      Keyword + distress detection
│   │       ├── geo/          Distance, zone matching, hotspots
│   │       ├── deal_engine/  Ranker, classifier, explainer
│   │       ├── pricing/      Profit estimates per strategy
│   │       ├── scoring/      Composite score engine
│   │       ├── comparables/  Land Registry matching
│   │       └── ingestion/    CSV import + adapter stubs
│   ├── alembic/              Database migrations
│   └── scripts/seed.py       Demo data seeder
└── frontend/
    ├── app/
    │   ├── (public)/         Marketing website
    │   └── (app)/            Protected dashboard
    ├── components/           Reusable UI components
    ├── lib/                  API client, utilities
    └── types/                TypeScript types
```

---

## Deal Scoring

Each listing is scored across 6 dimensions:

| Dimension | Weight | Signals |
|-----------|--------|---------|
| **BMV** | 30% | Asking price vs Land Registry comparables |
| **Distress** | 22% | Keywords: chain free, probate, cash buyers only... |
| **Momentum** | 13% | Days on market, price reduction count |
| **Planning** | 15% | Nearby change-of-use, prior approval applications |
| **Regeneration** | 15% | Distance to active NE regen zones |
| **Confidence** | 5% | Comparable data availability modifier |

Score tiers: **S (80+)** · **A (65+)** · **B (50+)** · **C (<50)**

---

## Data Sources

| Source | Status | Notes |
|--------|--------|-------|
| Land Registry Price Paid | ✅ Live (CSV import) | Official HM Land Registry data |
| Planning Applications | ✅ CSV import | All 10 NE councils supported |
| Property Listings | ✅ CSV + manual | Rightmove/Zoopla adapters: TODO (requires API partnership) |
| Regeneration Zones | ✅ Seeded | 8 major NE schemes |

---

## API

Full OpenAPI docs at `/docs` when running.

Key endpoints:
- `POST /auth/login` — JWT auth
- `GET /listings` — filtered deal feed
- `GET /listings/{id}` — deal detail with scores
- `GET /planning` — planning applications
- `GET /dashboard/stats` — KPI summary
- `POST /imports/listings` — CSV upload (admin)
- `POST /imports/rescore` — trigger rescoring (admin)

---

## Pricing Tiers (Production)

| Tier | Price | Access |
|------|-------|--------|
| Investor | £49/month | Deal alerts, BMV scoring, planning feed |
| Agent / Consultant | £99/month | Full access, saved searches, export |
| Developer | £149–£299/month | API access, team seats, bespoke intelligence |

---

## Roadmap

- [ ] Postcodes.io integration for accurate lat/lng geocoding
- [ ] Rightmove/Zoopla data partnership
- [ ] Live planning portal polling (planning.data.gov.uk)
- [ ] Email digest for alerts
- [ ] Stripe billing integration
- [ ] Map view (Mapbox)
- [ ] UK-wide expansion

---

*Northbridge Capital Partners Ltd — Gateshead, England*
