"""
Seed script — populates the CyberDuel database with test data.

Run from the backend/ directory:
    python scripts/seed.py

Idempotent: existing events / users are skipped, not duplicated.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timezone
from decimal import Decimal

from app.database import SessionLocal
from app.models import (
    User, Event, Market, Outcome, Order, PoolBet,
    EventStatus, GameType, MarketType, MarketStatus, MarketMode, OrderStatus,
)
from app.services.auth import AuthService


# ---------------------------------------------------------------------------
# Data definitions
# ---------------------------------------------------------------------------

USERS = [
    {"email": "admin@cyberduel.gg",  "password": "admin12345", "is_admin": True},
    {"email": "user1@cyberduel.gg",  "password": "user12345"},
    {"email": "user2@cyberduel.gg",  "password": "user12345"},
    {"email": "user3@cyberduel.gg",  "password": "user12345"},
    {"email": "user4@cyberduel.gg",  "password": "user12345"},
    {"email": "user5@cyberduel.gg",  "password": "user12345"},
]

# Each entry: (game_type, team_a, team_b, tournament, status, market_mode)
EVENTS = [
    # ── Pool-market events (first 3) ─────────────────────────────────────
    (GameType.CS2,      "NaVi",        "G2",       "ESL Pro League S21",  EventStatus.OPEN,      MarketMode.POOL_MARKET),
    (GameType.CS2,      "Vitality",    "Astralis",  "BLAST Spring 2025",  EventStatus.OPEN,      MarketMode.POOL_MARKET),
    (GameType.DOTA2,    "Team Spirit", "OG",        "The International",  EventStatus.OPEN,      MarketMode.POOL_MARKET),
    # ── P2P-direct events (last 3) ────────────────────────────────────────
    (GameType.DOTA2,    "Liquid",      "Tundra",    "DPC WEU 2025",       EventStatus.SCHEDULED, MarketMode.P2P_DIRECT),
    (GameType.LOL,      "T1",          "Gen.G",     "LCK Spring 2025",    EventStatus.OPEN,      MarketMode.P2P_DIRECT),
    (GameType.VALORANT, "Sentinels",   "LOUD",      "VCT Masters 2025",   EventStatus.OPEN,      MarketMode.P2P_DIRECT),
]

# P2P orders per market (3 markets × 4 orders each).
# Tuples: (regular_user_index 0-4, outcome_index 0=teamA 1=teamB, odds_str, amount_str)
P2P_ORDERS: list[list[tuple]] = [
    # Market: Liquid vs Tundra
    [
        (0, 0, "1.75", "150"),
        (1, 1, "2.10", "100"),
        (2, 0, "1.60", "200"),
        (3, 1, "1.90",  "80"),
    ],
    # Market: T1 vs Gen.G
    [
        (1, 0, "1.85", "120"),
        (2, 1, "2.00",  "90"),
        (3, 0, "1.55", "250"),
        (4, 1, "1.70", "180"),
    ],
    # Market: Sentinels vs LOUD
    [
        (0, 0, "2.20",  "50"),
        (2, 1, "1.50", "300"),
        (3, 0, "1.95", "130"),
        (4, 1, "1.65", "170"),
    ],
]

# Pool bets per market (3 markets, 3-5 bets each).
# Tuples: (regular_user_index 0-4, outcome_index 0=teamA 1=teamB, amount_str)
POOL_BETS: list[list[tuple]] = [
    # Market: NaVi vs G2
    [
        (0, 0, "200"),
        (1, 0, "150"),
        (2, 1, "300"),
        (3, 0, "100"),
        (4, 1, "250"),
    ],
    # Market: Vitality vs Astralis
    [
        (1, 0, "180"),
        (2, 1, "120"),
        (3, 0, "350"),
        (4, 1,  "90"),
        (0, 0, "160"),
    ],
    # Market: Team Spirit vs OG
    [
        (0, 1, "500"),
        (2, 0,  "75"),
        (3, 1, "200"),
        (4, 0, "130"),
        (1, 1,  "50"),
    ],
]


def export_seed_credentials(output_path: str | None = None) -> str:
    """Export seed credentials into a simple text file for quick manual testing."""
    if output_path is None:
        output_path = os.path.join(PROJECT_ROOT, "data", "seed_credentials.txt")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    lines = [
        "CyberDuel seed credentials (dev only)",
        "",
        "API: http://localhost:3228",
        "Admin page: http://localhost:5173/admin.html",
        "",
        "Users:",
    ]

    for user in USERS:
        role = "admin" if user.get("is_admin", False) else "user"
        lines.append(f"- {user['email']} | {user['password']} | {role}")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return output_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_or_create_user(db, spec: dict) -> tuple["User", bool]:
    """Return (user, created). Skips if email already exists."""
    existing = db.query(User).filter(User.email == spec["email"]).first()
    if existing:
        return existing, False

    user = User(
        email=spec["email"],
        password_hash=AuthService.hash_password(spec["password"]),
        balance_available=Decimal("1000.00"),
        balance_locked=Decimal("0.00"),
        is_admin=spec.get("is_admin", False),
    )
    db.add(user)
    db.flush()
    return user, True


def _get_or_create_event(
    db,
    game_type: GameType,
    team_a: str,
    team_b: str,
    tournament: str,
    status: EventStatus,
    market_mode: MarketMode,
) -> tuple["Event", "Market", "Outcome", "Outcome", bool]:
    """
    Return (event, market, outcome_a, outcome_b, created).
    If the event already exists its market/outcomes are loaded from DB.
    """
    existing_event = (
        db.query(Event)
        .filter(
            Event.team_a == team_a,
            Event.team_b == team_b,
            Event.tournament == tournament,
        )
        .first()
    )

    if existing_event:
        market = db.query(Market).filter(Market.event_id == existing_event.id).first()
        outcomes = (
            db.query(Outcome).filter(Outcome.market_id == market.id).all()
            if market else []
        )
        out_a = next((o for o in outcomes if o.name == team_a), None)
        out_b = next((o for o in outcomes if o.name == team_b), None)
        return existing_event, market, out_a, out_b, False

    # Create event
    event = Event(
        game_type=game_type,
        team_a=team_a,
        team_b=team_b,
        tournament=tournament,
        status=status,
    )
    db.add(event)
    db.flush()

    # Create market
    market = Market(
        event_id=event.id,
        market_type=MarketType.MATCH_WINNER,
        market_mode=market_mode,
        title="Match Winner",
        status=MarketStatus.OPEN,
    )
    db.add(market)
    db.flush()

    # Create outcomes
    out_a = Outcome(market_id=market.id, name=team_a)
    out_b = Outcome(market_id=market.id, name=team_b)
    db.add(out_a)
    db.add(out_b)
    db.flush()

    return event, market, out_a, out_b, True


# ---------------------------------------------------------------------------
# Main seed function
# ---------------------------------------------------------------------------

def seed() -> None:
    db = SessionLocal()
    stats = {"users": 0, "events": 0, "markets": 0, "orders": 0, "bets": 0}

    try:
        # ── 1. Users ──────────────────────────────────────────────────────
        all_users: list[User] = []
        for spec in USERS:
            user, created = _get_or_create_user(db, spec)
            all_users.append(user)
            if created:
                stats["users"] += 1

        db.commit()
        for u in all_users:
            db.refresh(u)

        # admin is index 0; regular users are indices 1-5
        regular_users = all_users[1:]

        # ── 2. Events, Markets, Outcomes ──────────────────────────────────
        pool_markets:  list[tuple[Market, Outcome, Outcome]] = []
        p2p_markets:   list[tuple[Market, Outcome, Outcome]] = []

        for game_type, team_a, team_b, tournament, status, market_mode in EVENTS:
            event, market, out_a, out_b, created = _get_or_create_event(
                db, game_type, team_a, team_b, tournament, status, market_mode
            )
            if created:
                stats["events"]  += 1
                stats["markets"] += 1

            if market_mode == MarketMode.POOL_MARKET:
                pool_markets.append((market, out_a, out_b))
            else:
                p2p_markets.append((market, out_a, out_b))

        db.commit()

        # ── 3. P2P Orders ─────────────────────────────────────────────────
        for idx, (market, out_a, out_b) in enumerate(p2p_markets):
            # Idempotency: skip if orders already exist for this market
            if db.query(Order).filter(Order.market_id == market.id).count() > 0:
                continue

            orders_spec = P2P_ORDERS[idx % len(P2P_ORDERS)]
            for user_idx, outcome_idx, odds_str, amount_str in orders_spec:
                user    = regular_users[user_idx % len(regular_users)]
                outcome = out_a if outcome_idx == 0 else out_b
                amount  = Decimal(amount_str)
                odds    = Decimal(odds_str)

                order = Order(
                    user_id=user.id,
                    market_id=market.id,
                    outcome_id=outcome.id,
                    amount=amount,
                    unfilled_amount=amount,
                    odds=odds,
                    status=OrderStatus.OPEN,
                )
                db.add(order)
                user.balance_available -= amount
                user.balance_locked    += amount
                stats["orders"] += 1

        db.commit()

        # ── 4. Pool Bets ──────────────────────────────────────────────────
        for idx, (market, out_a, out_b) in enumerate(pool_markets):
            # Idempotency: skip if bets already exist for this market
            if db.query(PoolBet).filter(PoolBet.market_id == market.id).count() > 0:
                continue

            bets_spec = POOL_BETS[idx % len(POOL_BETS)]

            # Running pool sizes per outcome (needed to compute share %)
            pool_sizes: dict[int, Decimal] = {
                out_a.id: Decimal("0"),
                out_b.id: Decimal("0"),
            }

            now = datetime.now(timezone.utc)
            for user_idx, outcome_idx, amount_str in bets_spec:
                user    = regular_users[user_idx % len(regular_users)]
                outcome = out_a if outcome_idx == 0 else out_b
                amount  = Decimal(amount_str)

                pool_before = pool_sizes[outcome.id]
                pool_after  = pool_before + amount

                # Share of the outcome pool this bet captures
                # share% = (contribution / new_pool_total) × 100
                share_pct = (amount / pool_after) * Decimal("100")

                bet = PoolBet(
                    user_id=user.id,
                    market_id=market.id,
                    outcome_id=outcome.id,
                    amount=amount,
                    initial_pool_share_percentage=share_pct,
                    pool_size_at_bet=pool_before,
                    settled=False,
                    # pool_bets DDL lacks server_default for timestamps
                    # (migration created the table without DEFAULT clause)
                    created_at=now,
                    updated_at=now,
                )
                db.add(bet)
                user.balance_available -= amount
                user.balance_locked    += amount
                pool_sizes[outcome.id] = pool_after
                stats["bets"] += 1

        db.commit()

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    # ── Summary ───────────────────────────────────────────────────────────
    creds_path = export_seed_credentials()

    print("\n✅  Seed complete!")
    print(f"    Users created    : {stats['users']}")
    print(f"    Events created   : {stats['events']}")
    print(f"    Markets created  : {stats['markets']}")
    print(f"    Orders created   : {stats['orders']}")
    print(f"    Pool bets created: {stats['bets']}")
    print(f"    Credentials file : {creds_path}")


def reset_db() -> None:
    """Drop all rows from every table then re-seed."""
    from app.models import (
        PoolBet, PoolState, Transaction, Contract, Order,
        Outcome, Market, Event, User,
    )
    db = SessionLocal()
    try:
        # Delete in FK-safe order
        for model in [
            PoolBet, PoolState, Transaction, Contract, Order,
            Outcome, Market, Event, User,
        ]:
            db.query(model).delete()
        db.commit()
        print("🗑️  All tables truncated.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Seed the CyberDuel database")
    parser.add_argument("--reset", action="store_true", help="Truncate all tables before seeding")
    args = parser.parse_args()

    if args.reset:
        reset_db()
    seed()
