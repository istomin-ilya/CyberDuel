# CyberDuel Protocol

A Peer-to-Peer Prediction Market Protocol for Esports Event Outcomes

## Abstract

This repository implements a distributed prediction market system demonstrating alternative architectures to traditional bookmaker models. The protocol facilitates direct peer-to-peer order matching between market participants, with deterministic escrow mechanisms and hybrid oracle-based outcome verification.

Unlike centralized betting platforms where the house acts as counterparty to all positions, this system operates as a neutral matching and settlement layer, charging only a 2% commission on realized profits rather than extracting value through house edge or spread manipulation.

## Research Objectives

This implementation explores three primary research questions:

1. **Order Matching Efficiency**: Can peer-to-peer order books effectively replace centralized bookmaker architectures while maintaining liquidity and fair pricing?

2. **Oracle Reliability**: How can hybrid verification systems (automated API + social consensus) provide trustworthy outcome determination without centralized authority?

3. **Concurrency Safety**: What architectural patterns ensure atomic escrow operations and prevent race conditions in high-throughput financial systems?

## System Architecture

### Three-Tier Service-Oriented Design
```
┌─────────────────────────────────────┐
│     Presentation Layer              │
│  React + TypeScript + WebSocket     │
└──────────────┬──────────────────────┘
               │ REST + WS
┌──────────────▼──────────────────────┐
│      Execution Layer                │
│         FastAPI (ASGI)              │
│  ┌────────┬─────────┬──────────┐   │
│  │  Auth  │ Matching│  Oracle  │   │
│  │ Service│  Engine │  Worker  │   │
│  └────────┴─────────┴──────────┘   │
└──────────────┬──────────────────────┘
               │ SQLAlchemy ORM
┌──────────────▼──────────────────────┐
│     Persistence Layer               │
│   SQLite (dev) / PostgreSQL (prod)  │
│        Redis (cache + pubsub)       │
└─────────────────────────────────────┘
```

### Core Components

**Matching Engine**
- Continuous order book implementation (FIFO with partial fills)
- Atomic order matching using database row-level locks
- Support for maker/taker liquidity provision model

**Escrow Service**
- Dual-balance accounting (available/locked funds)
- ACID-compliant balance updates via SQL transactions
- Comprehensive transaction audit trail

**Hybrid Oracle System**
- Tier 1: Automated verification via external APIs (PandaScore)
- Tier 2: Optimistic oracle with challenge periods (social consensus)
- Tier 3: Dispute resolution through arbitration

## Technology Stack

| Layer | Component | Version | Justification |
|-------|-----------|---------|---------------|
| **Backend** | Python | 3.12+ | Modern async features, type hints |
| | FastAPI | 0.128.0+ | Native async, auto OpenAPI docs |
| | SQLAlchemy | 2.0.46+ | ORM with multi-DB support |
| | Pydantic | 2.12.0+ | Runtime validation, settings |
| | Uvicorn | 0.40.0+ | Production-grade ASGI server |
| **Frontend** | React | 18+ | Component architecture |
| | TypeScript | 5+ | Type safety for financial data |
| | Vite | 5+ | Fast HMR, modern bundling |
| **Database** | SQLite | 3+ | Development (zero-config) |
| | PostgreSQL | 16+ | Production (row locks, ACID) |
| **Cache** | Redis | 7+ | Session storage, pub/sub |

## Project Structure
```
cyberduel-protocol/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI application entry
│   │   ├── config.py         # Settings management
│   │   ├── database.py       # SQLAlchemy engine
│   │   ├── models/           # ORM models
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── services/         # Business logic
│   │   └── api/              # Route handlers
│   └── pyproject.toml        # Dependencies (uv)
├── frontend/
│   ├── src/
│   │   ├── components/       # Reusable UI
│   │   ├── pages/            # Route views
│   │   ├── services/         # API client
│   │   └── stores/           # State management
│   └── package.json
└── README.md                 # This file
```

## Installation and Setup

### Prerequisites

- Python 3.12 or higher
- Node.js 18 or higher
- uv package manager: `pip install uv`

### Backend
```bash
cd backend
uv sync                              # Install dependencies from pyproject.toml
uvicorn app.main:app --reload        # Start development server
```

Server runs at `http://localhost:8000`

API documentation available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Frontend
```bash
cd frontend
npm install                          # Install dependencies
npm run dev                          # Start development server
```

Application runs at `http://localhost:5173`

## Configuration

Backend configuration is managed via `backend/app/config.py` using Pydantic settings. Values can be set through environment variables or a `.env` file:
```bash
# backend/.env
DEBUG=True
DATABASE_URL=sqlite:///./cyberduel.db
JWT_SECRET=your-secret-key-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=15
CORS_ORIGINS=["http://localhost:5173"]
```

Database backend is abstracted via SQLAlchemy. To switch from SQLite to PostgreSQL, simply change the `DATABASE_URL` - no code modifications required.

## Development Roadmap

### Week 1: Foundation
- User authentication (Argon2 + JWT)
- SQLAlchemy models: User, Event, Order, Contract, Transaction
- Balance management with atomic operations
- Order CRUD endpoints

### Week 2: Core Logic
- P2P matching engine implementation
- Escrow service (lock/unlock/transfer)
- Event lifecycle management
- External API integration (PandaScore)

### Week 3: Oracle & Settlement
- Optimistic oracle with challenge periods
- Settlement algorithm (2% fee calculation)
- Dispute resolution workflow
- Background workers (Celery)

### Week 4: Integration & Polish
- WebSocket real-time updates
- Redis pub/sub integration
- End-to-end testing
- Deployment configuration (Docker Compose)

## Security Model

This implementation demonstrates financial system patterns in an educational context. Security considerations include:

- **Password Security**: Argon2 hashing (memory-hard, GPU-resistant)
- **Authentication**: JWT with short-lived access tokens (15 min) and refresh tokens (7 days)
- **Input Validation**: Pydantic schemas on all API endpoints
- **SQL Injection**: Prevented via SQLAlchemy ORM parameterized queries
- **Race Conditions**: Handled via PostgreSQL row-level locking (`SELECT FOR UPDATE`)
- **CORS**: Restricted to configured frontend origins

Note: This system operates in simulation mode with non-redeemable internal credits for educational purposes.

## Testing Strategy

Planned test coverage using pytest:
```bash
cd backend
pytest tests/                        # Run all tests
pytest tests/unit/                   # Unit tests only
pytest tests/integration/            # Integration tests
pytest --cov=app tests/              # Coverage report
```

Test categories:
- Unit: Service layer business logic
- Integration: API endpoints with test database
- Concurrency: Race condition scenarios
- E2E: Critical user flows (order creation, matching, settlement)

## Database Schema (Planned)

### Core Entities

**User**
- Authentication: email, password_hash
- Balance: available, locked
- Metadata: created_at, updated_at

**Event**
- Identity: game_type, team_a, team_b
- Status: SCHEDULED, OPEN, LIVE, PENDING, SETTLED
- Result: winner_team_id, settled_at

**Order** (Maker liquidity)
- Position: side (YES/NO), amount, odds
- Fill state: unfilled_amount
- Status: OPEN, PARTIALLY_FILLED, FILLED, CANCELLED

**Contract** (Matched position)
- Parties: maker_id, taker_id
- Terms: amount, odds, side
- Lifecycle: ACTIVE, CLAIMED, DISPUTED, SETTLED

**Transaction** (Audit log)
- Type: ORDER_LOCK, CONTRACT_LOCK, SETTLEMENT, FEE
- Balances: before, after
- References: order_id, contract_id

## API Design (Planned)

### Authentication
```
POST   /auth/register         # Create account
POST   /auth/login            # Get JWT tokens
POST   /auth/refresh          # Refresh access token
```

### Orders
```
GET    /orders                # List orders (filterable)
POST   /orders                # Create order (Maker)
POST   /orders/{id}/match     # Match order (Taker)
DELETE /orders/{id}           # Cancel order
```

### Events
```
GET    /events                # List events
GET    /events/{id}           # Event details + order book
```

### Contracts
```
GET    /contracts             # User's positions
POST   /contracts/{id}/claim  # Claim outcome
POST   /contracts/{id}/dispute # Challenge claim
```

## Academic Context

This project demonstrates distributed systems concepts applicable to financial technology:

- **Consensus Mechanisms**: Optimistic oracle with economic finality
- **Atomic Transactions**: ACID guarantees in escrow operations
- **Order Matching**: Exchange-style order book algorithms
- **API Design**: RESTful principles with OpenAPI specification
- **Type Safety**: Static typing throughout stack (Python + TypeScript)

## Future Work

- Decentralized jury system for disputes (reputation-weighted voting)
- Multi-asset support (portfolio positions)
- Advanced order types (limit, stop-loss)
- Machine learning fraud detection
- Blockchain integration for transparency
- Mobile applications

## References

- FastAPI Documentation: https://fastapi.tiangolo.com/
- SQLAlchemy 2.0: https://docs.sqlalchemy.org/
- UMA Protocol Optimistic Oracle: https://docs.umaproject.org/
- OWASP Top 10: https://owasp.org/www-project-top-ten/

## License

Educational and research purposes only.

---

**Version**: 0.1.0-alpha  
**Last Updated**: January 28, 2025