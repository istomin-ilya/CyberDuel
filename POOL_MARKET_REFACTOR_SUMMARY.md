# Pool Market Refactor Summary

## Overview
Successfully refactored the Pool Market system from AMM with locked odds to a DeFi-style Liquidity Pool model.

## Key Changes

### 1. Database Model ([app/models/pool_bet.py](backend/app/models/pool_bet.py))
**Removed fields:**
- `locked_odds` - No longer calculating locked odds for individual bets
- `potential_payout` - Payout now calculated during settlement based on pool share

**Added fields:**
- `pool_share_percentage` (Decimal) - User's percentage share of the outcome pool
- `pool_size_at_bet` (Decimal) - Pool size when the bet was placed (for historical tracking)

### 2. AMM Calculator ([app/services/amm.py](backend/app/services/amm.py))
**Removed functions:**
- `calculate_locked_odds()` - No longer needed
- `calculate_potential_payout()` - No longer needed

**Added functions:**
- `calculate_pool_share()` - Calculates user's share when adding liquidity
  - Formula: `share = user_deposit / (pool_size + user_deposit)`
- `calculate_estimated_roi()` - Shows estimated ROI for informational purposes
  - Formula: `ROI = (display_odds - 1) × 100`

**Modified functions:**
- `get_current_odds()` - Now explicitly for display/informational purposes only

### 3. Pool Market Service ([app/services/pool_market.py](backend/app/services/pool_market.py))

**place_pool_bet():**
- Now calculates pool share percentage instead of locked odds
- Stores pool size at time of bet for historical tracking
- Uses `calculate_pool_share()` to determine user's ownership

**settle_pool_market():**
Completely redesigned settlement logic:
- Winners share the ENTIRE market pool proportionally
- Formula: `payout = (user_share × total_market_pool) - fee`
- Fee (2%) charged only on profit
- No concept of "insufficient liquidity" - pool is always sufficient

**Example:**
```
Pool NaVi: 700$ (User1: 500$, User3: 200$)
Pool G2: 300$ (User2: 300$)
Total: 1000$

NaVi wins:
- User1 share: 500/700 = 71.43%
- User1 payout: 71.43% × 1000 = 714.30
- User1 profit: 214.30, fee: 4.29
- User1 final: 710.01

- User3 share: 200/700 = 28.57%
- User3 payout: 28.57% × 1000 = 285.70
- User3 profit: 85.70, fee: 1.71
- User3 final: 283.99

- User2: loses 300$
```

**get_pool_state():**
- Returns `estimated_odds` instead of `current_odds`
- Includes `estimated_roi` for each outcome

### 4. API Schemas ([app/schemas/pool_market.py](backend/app/schemas/pool_market.py))

**PoolBetResponse:**
- Removed: `locked_odds`, `potential_payout`
- Added: `pool_share_percentage`, `pool_size_at_bet`

**OutcomePoolState:**
- Changed: `current_odds` → `estimated_odds` (informational only)
- Added: `estimated_roi`

**PoolSettlementResponse:**
- Removed: `total_promised`, `total_from_losers`, `distribution_ratio`, `liquidity_sufficient`
- Added: `total_market_pool`, `winning_pool_total`

### 5. Database Migration
**File:** [alembic/versions/1afa276bfbc8_refactor_pool_bet_to_liquidity_model.py](backend/alembic/versions/1afa276bfbc8_refactor_pool_bet_to_liquidity_model.py)

Migration handles:
- Dropping `locked_odds` and `potential_payout` columns
- Adding `pool_share_percentage` and `pool_size_at_bet` columns
- Setting default values for existing rows (0.0 for both - historical data lost)
- SQLite-compatible batch operations

### 6. Tests Updated

**Unit Tests ([tests/test_pool_market.py](backend/tests/test_pool_market.py)):**
- Added tests for `calculate_pool_share()` with various scenarios
- Added tests for `calculate_estimated_roi()`
- Updated `place_pool_bet()` tests to verify pool shares
- Removed tests for locked odds calculations

**Integration Tests ([tests/test_pool_market_service.py](backend/tests/test_pool_market_service.py)):**
- `test_single_user_bet_and_win()` - Equal pools scenario
- `test_multiple_winners_share_pool()` - Multiple winners with proportional sharing
- `test_dominant_pool_wins()` - Dominant pool with small profit
- Removed all "insufficient liquidity" tests (concept no longer exists)

### 7. API Endpoints Updated
**File:** [app/api/pool_markets.py](backend/app/api/pool_markets.py), [app/api/admin.py](backend/app/api/admin.py)
- Updated pool state endpoint to return `estimated_odds` and `estimated_roi`
- Updated settlement response to use new fields

## Mathematical Model

### Adding Liquidity
```
pool_share = user_deposit / (current_pool + user_deposit)
```

### Settlement (Winners)
```
user_share = user_amount / winning_pool_total
payout_before_fee = user_share × total_market_pool
profit = payout_before_fee - user_amount
fee = profit × 0.02 (if profit > 0)
final_payout = payout_before_fee - fee
```

### Display Odds (Informational Only)
```
display_odds = total_market_pool / outcome_pool
estimated_roi = (display_odds - 1) × 100
```

## Key Advantages

1. **Simplicity**: No complex locked odds calculations
2. **Fairness**: All participants share proportionally based on contribution
3. **Always Sufficient**: Pool is always sufficient to pay winners
4. **DeFi Standard**: Follows established liquidity pool patterns
5. **Transparency**: Users know exactly what share they own

## Breaking Changes

⚠️ **This is a breaking change** - existing bets in the database will have pool_share_percentage and pool_size_at_bet set to 0.0 after migration. Consider:
- Settling all open markets before migration
- Or calculating historical pool shares from old locked_odds data

## Test Results
All 23 tests pass ✅
- 9 AMM Calculator tests
- 14 Pool Market Service tests including settlement scenarios
