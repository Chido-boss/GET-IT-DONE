from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routers import (
    deals,
    auth,
    listings,
    planning,
    alerts,
    regen_zones,
    saved_searches,
    imports,
    dashboard,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: initialise the database (create tables if not exists)."""
    await init_db()
    yield


app = FastAPI(
    title="Northbridge Intelligence API",
    description=(
        "Property intelligence platform for North East England. "
        "Identifies below-market-value opportunities using scoring, "
        "planning data, and regeneration zone analysis."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(auth.router)
app.include_router(listings.router)
app.include_router(planning.router)
app.include_router(alerts.router)
app.include_router(regen_zones.router)
app.include_router(saved_searches.router)
app.include_router(imports.router)
app.include_router(dashboard.router)
app.include_router(deals.router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health", tags=["health"])
async def health_check():
    """Simple liveness probe."""
    return {"status": "ok", "service": "northbridge-intelligence"}
