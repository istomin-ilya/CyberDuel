"""
E2E tests — real HTTP requests against localhost:3228.

Prerequisites:
    1. Server running: uvicorn app.main:app --port 3228
    2. Migrations applied: alembic upgrade head

Run:
    cd backend/
    pytest tests/test_api_e2e.py -v
"""
import subprocess
import sys
import os
import uuid
from decimal import Decimal

import httpx
import pytest

BASE_URL = "http://localhost:3228"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset_and_seed():
    """Truncate DB and re-seed via subprocess."""
    result = subprocess.run(
        [sys.executable, "scripts/seed.py", "--reset"],
        cwd=os.path.join(os.path.dirname(__file__), ".."),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"seed --reset failed (rc={result.returncode}):\n"
            f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        )


def _login(client: httpx.Client, email: str, password: str) -> str:
    """Login and return Bearer token."""
    r = client.post(f"{BASE_URL}/auth/login", json={
        "email": email,
        "password": password,
    })
    assert r.status_code == 200, f"Login failed for {email}: {r.text}"
    return r.json()["access_token"]


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _find_event(client: httpx.Client, team_a: str, team_b: str) -> dict:
    """Find an event by team names."""
    r = client.get(f"{BASE_URL}/api/events")
    assert r.status_code == 200
    for ev in r.json()["events"]:
        if ev["team_a"] == team_a and ev["team_b"] == team_b:
            return ev
    raise AssertionError(f"Event {team_a} vs {team_b} not found")


def _find_market(client: httpx.Client, event_id: int) -> dict:
    """Return the first market for a given event."""
    r = client.get(f"{BASE_URL}/api/markets", params={"event_id": event_id})
    assert r.status_code == 200
    markets = r.json()["markets"]
    assert len(markets) > 0, f"No markets for event {event_id}"
    return markets[0]


def _get_me(client: httpx.Client, token: str) -> dict:
    r = client.get(f"{BASE_URL}/auth/me", headers=_auth_header(token))
    assert r.status_code == 200
    return r.json()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_db():
    """Reset + seed DB before every test."""
    _reset_and_seed()


@pytest.fixture()
def client():
    with httpx.Client(timeout=15) as c:
        yield c


# ---------------------------------------------------------------------------
# Test 1 — Auth flow
# ---------------------------------------------------------------------------

class TestAuthFlow:
    def test_register_login_me(self, client: httpx.Client):
        """Register → login → /auth/me returns correct data."""
        unique = uuid.uuid4().hex[:8]
        email = f"testuser_{unique}@cyberduel.gg"
        password = "strongpass123"

        # 1. Register
        r = client.post(f"{BASE_URL}/auth/register", json={
            "email": email,
            "password": password,
        })
        assert r.status_code == 201, f"Register failed: {r.text}"
        data = r.json()
        assert "access_token" in data
        register_token = data["access_token"]

        # 2. Login with same credentials
        token = _login(client, email, password)

        # 3. GET /auth/me
        me = _get_me(client, token)
        assert me["email"] == email
        assert Decimal(str(me["balance_available"])) == Decimal("1000.00")
        assert Decimal(str(me["balance_locked"])) == Decimal("0.00")


# ---------------------------------------------------------------------------
# Test 2 — P2P Order flow
# ---------------------------------------------------------------------------

class TestP2POrderFlow:
    def test_create_order_match_contract(self, client: httpx.Client):
        """
        user2 creates order → balance decreases
        user5 matches order → contract created, balances updated

        (user1 has negative balance after seed, so we use user2 / user5)
        """
        # Login user2 (balance ~400 after seed)
        token1 = _login(client, "user2@cyberduel.gg", "user12345")
        me1_before = _get_me(client, token1)
        balance1_before = Decimal(str(me1_before["balance_available"]))

        # Find T1 vs Gen.G event & market
        event = _find_event(client, "T1", "Gen.G")
        market = _find_market(client, event["id"])
        market_id = market["id"]

        # Get the market detail with outcomes
        r = client.get(f"{BASE_URL}/api/markets/{market_id}")
        assert r.status_code == 200
        market_data = r.json()
        outcomes = market_data["outcomes"]
        assert len(outcomes) >= 2
        # Pick first outcome (T1)
        outcome_t1 = outcomes[0]

        # user2: create order
        order_amount = "50.00"
        order_odds = "1.80"
        r = client.post(
            f"{BASE_URL}/api/orders",
            json={
                "market_id": market_id,
                "outcome_id": outcome_t1["id"],
                "amount": order_amount,
                "odds": order_odds,
            },
            headers=_auth_header(token1),
        )
        assert r.status_code == 201, f"Create order failed: {r.text}"
        order = r.json()
        order_id = order["id"]
        assert order["status"] == "OPEN"
        assert Decimal(str(order["amount"])) == Decimal(order_amount)

        # user2: balance_available should decrease
        me1_after = _get_me(client, token1)
        balance1_after = Decimal(str(me1_after["balance_available"]))
        assert balance1_after == balance1_before - Decimal(order_amount)

        # Login user5 (balance ~180 after seed)
        token2 = _login(client, "user5@cyberduel.gg", "user12345")
        me2_before = _get_me(client, token2)
        balance2_before = Decimal(str(me2_before["balance_available"]))

        # user5: match the order
        match_amount = order_amount
        r = client.post(
            f"{BASE_URL}/api/orders/{order_id}/match",
            json={"amount": match_amount},
            headers=_auth_header(token2),
        )
        assert r.status_code == 201, f"Match order failed: {r.text}"
        contract = r.json()

        # Contract should exist and be active
        assert contract["maker_id"] == me1_after["id"]
        assert contract["taker_id"] == me2_before["id"]
        assert contract["order_id"] == order_id
        assert contract["status"] == "ACTIVE"

        # user5: balance should decrease by taker_risk = amount * (odds - 1)
        taker_risk = Decimal(match_amount) * (Decimal(order_odds) - 1)
        me2_after = _get_me(client, token2)
        balance2_after = Decimal(str(me2_after["balance_available"]))
        assert balance2_after == balance2_before - taker_risk


# ---------------------------------------------------------------------------
# Test 3 — Pool Bet flow
# ---------------------------------------------------------------------------

class TestPoolBetFlow:
    def test_place_pool_bet_and_check_state(self, client: httpx.Client):
        """
        user2 places a pool bet on NaVi vs G2 →
        balance decreases, pool state updated, bet visible in my-bets.

        (user2 has ~400 available after seed)
        """
        token = _login(client, "user2@cyberduel.gg", "user12345")
        me_before = _get_me(client, token)
        balance_before = Decimal(str(me_before["balance_available"]))

        # Find NaVi vs G2 event & market
        event = _find_event(client, "NaVi", "G2")
        market = _find_market(client, event["id"])
        market_id = market["id"]

        # Get market outcomes
        r = client.get(f"{BASE_URL}/api/markets/{market_id}")
        assert r.status_code == 200
        outcomes = r.json()["outcomes"]
        navi_outcome = next(o for o in outcomes if o["name"] == "NaVi")

        # Pool state BEFORE (may be empty if seed didn't create pool_states)
        r = client.get(f"{BASE_URL}/api/pool-markets/{market_id}/state")
        assert r.status_code == 200
        pool_before = r.json()
        navi_pool_match = [
            o for o in pool_before["outcomes"]
            if o["outcome_id"] == navi_outcome["id"]
        ]
        staked_before = (
            Decimal(str(navi_pool_match[0]["total_staked"]))
            if navi_pool_match
            else Decimal("0.00")
        )

        # Place bet
        bet_amount = "100.00"
        r = client.post(
            f"{BASE_URL}/api/pool-markets/{market_id}/bet",
            json={
                "outcome_id": navi_outcome["id"],
                "amount": bet_amount,
            },
            headers=_auth_header(token),
        )
        assert r.status_code == 201, f"Pool bet failed: {r.text}"
        bet = r.json()
        assert Decimal(str(bet["amount"])) == Decimal(bet_amount)

        # Balance should decrease by 100
        me_after = _get_me(client, token)
        balance_after = Decimal(str(me_after["balance_available"]))
        assert balance_after == balance_before - Decimal(bet_amount)

        # Pool state should increase (pool_states now guaranteed to exist)
        r = client.get(f"{BASE_URL}/api/pool-markets/{market_id}/state")
        assert r.status_code == 200
        pool_after = r.json()
        navi_pool_after = next(
            o for o in pool_after["outcomes"]
            if o["outcome_id"] == navi_outcome["id"]
        )
        staked_after = Decimal(str(navi_pool_after["total_staked"]))
        assert staked_after == staked_before + Decimal(bet_amount)

        # My bets should include the new bet
        r = client.get(
            f"{BASE_URL}/api/pool-markets/{market_id}/my-bets",
            headers=_auth_header(token),
        )
        assert r.status_code == 200
        my_bets = r.json()["bets"]
        assert any(
            Decimal(str(b["amount"])) == Decimal(bet_amount)
            and b["outcome_id"] == navi_outcome["id"]
            for b in my_bets
        ), "Newly placed bet not found in my-bets"


# ---------------------------------------------------------------------------
# Test 4 — Pool Bet 500 error regression
# ---------------------------------------------------------------------------

class TestPoolBet500Regression:
    def test_first_pool_bet_no_500(self, client: httpx.Client):
        """
        Regression: placing a pool bet when pool_states don't exist yet
        should NOT return 500 (NOT NULL created_at).
        After --reset + seed the pool_states exist, so we create a fresh
        pool market via admin and bet into it from scratch.
        """
        # Login as admin
        admin_token = _login(client, "admin@cyberduel.gg", "admin12345")

        # Create a brand-new event via admin
        r = client.post(
            f"{BASE_URL}/api/events",
            json={
                "game_type": "CS2",
                "team_a": "FaZe",
                "team_b": "MOUZ",
                "tournament": "E2E Test Cup",
            },
            headers=_auth_header(admin_token),
        )
        assert r.status_code == 201, f"Create event failed: {r.text}"
        new_event = r.json()

        # Create a pool market for this event
        r = client.post(
            f"{BASE_URL}/api/markets",
            json={
                "event_id": new_event["id"],
                "market_type": "MATCH_WINNER",
                "market_mode": "pool_market",
                "title": "Match Winner",
                "outcomes": [
                    {"name": "FaZe"},
                    {"name": "MOUZ"},
                ],
            },
            headers=_auth_header(admin_token),
        )
        assert r.status_code == 201, f"Create market failed: {r.text}"
        new_market = r.json()
        market_id = new_market["id"]

        # Open the market (PENDING → OPEN)
        r = client.patch(
            f"{BASE_URL}/api/markets/{market_id}",
            json={"status": "OPEN"},
            headers=_auth_header(admin_token),
        )
        assert r.status_code == 200, f"Market open failed: {r.text}"

        # Get outcomes
        r = client.get(f"{BASE_URL}/api/markets/{market_id}")
        assert r.status_code == 200
        outcomes = r.json()["outcomes"]
        assert len(outcomes) >= 2
        faze_outcome = next(o for o in outcomes if o["name"] == "FaZe")

        # Login as regular user (user2 has balance after seed)
        token = _login(client, "user2@cyberduel.gg", "user12345")

        # Place pool bet — this is the critical call.
        # Before the fix it returned 500 due to NOT NULL created_at on pool_states.
        r = client.post(
            f"{BASE_URL}/api/pool-markets/{market_id}/bet",
            json={
                "outcome_id": faze_outcome["id"],
                "amount": "50.00",
            },
            headers=_auth_header(token),
        )
        # MUST be 201, NOT 500
        assert r.status_code == 201, (
            f"Pool bet returned {r.status_code} instead of 201 — "
            f"likely the NOT NULL created_at regression. Body: {r.text}"
        )
        bet = r.json()
        assert Decimal(str(bet["amount"])) == Decimal("50.00")
