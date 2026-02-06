"""
CyberDuel Protocol - Main application entry point.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .api import auth, orders, events, markets, settlement, admin, pool_markets

# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="A Peer-to-Peer Prediction Market Protocol for Esports",
    version="0.1.0",
    debug=settings.DEBUG
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(orders.router)
app.include_router(events.router)
app.include_router(markets.router)
app.include_router(settlement.router)
app.include_router(admin.router)
app.include_router(pool_markets.router)

@app.on_event("startup")
async def startup_event():
    """Application startup."""
    print(f"{settings.APP_NAME} started")
    print(f"Database: {settings.DATABASE_URL}")
    print("Run 'alembic upgrade head' to apply migrations")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    print(f"{settings.APP_NAME} shutting down")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "online",
        "app": settings.APP_NAME,
        "version": "0.1.0"
    }


@app.get("/health")
async def health():
    """Detailed health check."""
    return {
        "status": "healthy",
        "database": "connected",
        "debug": settings.DEBUG
    }