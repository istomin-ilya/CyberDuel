# CyberDuel Protocol

**A Decentralized Peer-to-Peer Prediction Market Protocol for Esports & Media Events (Simulation Mode).**

> **Status:** MVP / Active Development
> **Type:** Distributed Systems / Fintech (Simulation)
> **Architecture:** Hybrid Web 2.5 (Centralized Ledger, Decentralized Logic)

---

## Overview

CyberDuel Protocol is a distributed market infrastructure project aimed at creating a **trustless clearing and settlement layer** for event outcome contracts. Public deployments operate in **simulation mode with non-redeemable internal units (points/credits)**.

Unlike traditional bookmaker models, CyberDuel operates as a neutral technological facilitator, connecting **Makers** (liquidity providers) and **Takers** (market participants) directly.

The system utilizes an **"Optimistic Oracle"** mechanism and a **Continuous Order Book** matching engine to ensure fair market pricing and **deterministic settlement of internal units (escrow)** without a centralized house edge.

### Key Features

* **P2P Liquidity Matching**
  Automated clearing of counter-orders (Bid/Ask) using a *Continuous Order Book* model. Supports partial fills and dynamic odds based on market depth.

* **Deterministic Escrow**
  Internal units (points/credits) are programmatically locked in a secure holding state (Escrow) at the moment a contract is matched. Settlement distributions are released strictly upon verified outcomes, eliminating counterparty risk.

* **Hybrid Oracle & Social Consensus**
  The protocol solves the "Oracle Problem" using a dual-layer approach:

  1. **Automated Layer:** Major Tier-1 tournaments are verified automatically via external APIs (e.g., PandaScore).
  2. **Optimistic Fallback:** For niche markets without API data, the system relies on **Social Consensus**. The beneficiary asserts the outcome. If the counterparty does not raise a dispute within a specific **Challenge Period** (e.g., 15 minutes), the result is finalized and settled. This operationalizes the **"Silence is Consent"** principle.

* **Decentralized Dispute Resolution**
  If a claim is challenged, the contract enters arbitration. A **Jury System** selects random high-reputation users (Validators) to review evidence and vote on the true outcome, incentivized by **reputation-weighted incentives and reputation penalties**.

* **Skill-based Prediction Market Classification**
  The platform logic is designed to operate within legal frameworks for skill-based prediction markets.

---

## System Architecture

The project follows a **Three-Tier Service-Oriented Architecture**:

### 1. Presentation Layer (Frontend)

* **Stack:** React.js, TypeScript, Vite, TailwindCSS.
* **Role:** Single Page Application (SPA) serving as the trading terminal. Handles authentication, market feed visualization, and order management.

### 2. Execution Layer (Backend)

* **Stack:** Python 3.12, FastAPI (ASGI).
* **Role:** High-concurrency API Gateway and Business Logic.
* **Components:**

  * **Matching Engine:** Handles the logic of partial fills and order clearing.
  * **Oracle Worker:** Background process for fetching results and managing dispute timers.

### 3. Persistence Layer (Data)

* **Stack:** PostgreSQL 16, Redis.
* **Role:**

  * **PostgreSQL:** ACID-compliant ledger for ledger entries and user credit balances.
  * **Redis:** In-memory store for high-speed caching, session management, and Pub/Sub event streaming.

---

## 🛠 Tech Stack

| Component      | Technology         | Reasoning                                          |
| :------------- | :----------------- | :------------------------------------------------- |
| **Backend**    | Python (FastAPI)   | Async support for high-load matching & Websockets. |
| **Frontend**   | React + TypeScript | Type safety for market data handling.              |
| **Database**   | PostgreSQL         | Strict relational integrity and row-level locking. |
| **Caching**    | Redis              | "Hot" data storage and message brokerage.          |
| **Validation** | Pydantic           | Data parsing and sanitization.                     |
| **Security**   | Argon2 + JWT       | Industry standard for auth and password hashing.   |
| **DevOps**     | Docker Compose     | Containerized environment for reproducibility.     |

---

## Development Roadmap

### Phase 1: Foundation (Current)

* [ ] Project scaffolding and environment setup.
* [ ] Database schema design (SQLAlchemy models).
* [ ] Basic Authentication (JWT) and User management.
* [ ] DB Migrations setup (Alembic).

### Phase 2: Core Logic (The Engine)

* [ ] Event creation and lifecycle management.
* [ ] Order creation (Maker) and liquidity aggregation.
* [ ] **Matching Algorithm** implementation (Order Filling).
* [ ] Transaction processing and Escrow locking (internal units).

### Phase 3: Client Interface

* [ ] React project setup.
* [ ] Market Feed UI (Order Book view).
* [ ] Portfolio / Dashboard UI.
* [ ] Connection with Backend API.

### Phase 4: Verification & Oracle

* [ ] Settlement logic (Outcome reporting).
* [ ] "Optimistic Oracle" timer logic (Celery/Worker).
* [ ] Dispute resolution flow.

### Phase 5: Advanced & Polishing

* [ ] Real-time updates via WebSockets (Redis Pub/Sub).
* [ ] Docker Compose orchestration.
* [ ] Final Diploma Documentation.

---

## Getting Started (Dev)

### Prerequisites

* Python 3.12+
* Node.js 18+
* PostgreSQL
* Redis

### Installation

1. **Clone the repository:**

```bash
git clone https://github.com/your-username/cyberduel-protocol.git
cd cyberduel-protocol
```

2. **Backend Setup:**

```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\\Scripts\\activate on Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
```

3. **Frontend Setup:**

```bash
cd frontend
npm install
npm run dev
```

---

## 📄 License

This project is developed for educational and research purposes. All public deployments operate
