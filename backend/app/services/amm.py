"""
AMM (Automated Market Maker) formulas for pool markets.

Pool Market Pricing:
- Each outcome has its own liquidity pool (total_staked)
- Odds are calculated dynamically based on pool ratios
- Users get "locked odds" at the moment they place their bet
- This rewards early bettors who take more risk

Example:
    Market: "Match Winner"
    Outcome A pool: $500
    Outcome B pool: $300
    Total pool: $800
    
    Current odds:
    - Outcome A: 800 / 500 = 1.60x
    - Outcome B: 800 / 300 = 2.67x
    
    If user bets $100 on Outcome A:
    - New total: $900
    - New Outcome A pool: $600
    - Locked odds for this user: 900 / 600 = 1.50x
    - Potential payout: 100 * 1.50 = $150
"""
from decimal import Decimal
from typing import Dict, List
from sqlalchemy.orm import Session

from app.models.pool_state import PoolState
from app.models.outcome import Outcome


class AMMException(Exception):
    """Base exception for AMM calculations"""
    pass


class AMMCalculator:
    """AMM formulas for pool market pricing"""
    
    @staticmethod
    def get_total_pool(db: Session, market_id: int) -> Decimal:
        """
        Calculate total pool across all outcomes in a market.
        
        Args:
            db: Database session
            market_id: Market ID
            
        Returns:
            Sum of all outcome pools
            
        Example:
            Outcome A: $500
            Outcome B: $300
            Total: $800
        """
        pool_states = db.query(PoolState).filter(
            PoolState.market_id == market_id
        ).all()
        
        total = sum(ps.total_staked for ps in pool_states)
        return Decimal(str(total))
    
    @staticmethod
    def get_outcome_pool(db: Session, market_id: int, outcome_id: int) -> Decimal:
        """
        Get current pool size for specific outcome.
        
        Args:
            db: Database session
            market_id: Market ID
            outcome_id: Outcome ID
            
        Returns:
            Total staked on this outcome
        """
        pool_state = db.query(PoolState).filter(
            PoolState.market_id == market_id,
            PoolState.outcome_id == outcome_id
        ).first()
        
        if pool_state:
            return pool_state.total_staked
        return Decimal("0.00")
    
    @staticmethod
    def get_current_odds(
        db: Session,
        market_id: int,
        outcome_id: int
    ) -> Decimal:
        """
        Calculate current display odds for an outcome.
        
        Formula: odds = total_pool / outcome_pool
        
        If outcome pool is 0 (no bets yet), returns a default high odds.
        
        Args:
            db: Database session
            market_id: Market ID
            outcome_id: Outcome ID
            
        Returns:
            Current odds (e.g., 1.80 means 1.80x payout)
            
        Example:
            Total pool: $800
            Outcome pool: $500
            Odds: 800 / 500 = 1.60x
        """
        total_pool = AMMCalculator.get_total_pool(db, market_id)
        outcome_pool = AMMCalculator.get_outcome_pool(db, market_id, outcome_id)
        
        # If no bets on this outcome yet, return high odds
        if outcome_pool == Decimal("0.00"):
            # If total pool is also 0, return default odds
            if total_pool == Decimal("0.00"):
                return Decimal("2.00")  # Default 2.0x for empty pool
            # If only this outcome is empty, return very high odds
            return Decimal("10.00")
        
        # Standard formula: total / outcome
        odds = total_pool / outcome_pool
        
        # Ensure minimum odds of 1.01 (can't have odds below 1.0)
        if odds < Decimal("1.01"):
            return Decimal("1.01")
        
        return odds.quantize(Decimal("0.01"))
    
    @staticmethod
    def calculate_locked_odds(
        db: Session,
        market_id: int,
        outcome_id: int,
        bet_amount: Decimal
    ) -> Decimal:
        """
        Calculate locked odds for a new bet (what user will actually get).
        
        Formula: locked_odds = (total_pool + bet) / (outcome_pool + bet)
        
        Special case: If pool is empty (first bet in market), odds = number of outcomes.
        This ensures first bettors get fair odds based on market structure.
        
        This is different from current odds because it includes the new bet.
        The user gets the odds AFTER their bet is added to the pool.
        
        Args:
            db: Database session
            market_id: Market ID
            outcome_id: Outcome ID to bet on
            bet_amount: Amount user wants to bet
            
        Returns:
            Locked odds for this bet
            
        Example:
            Current total: $800
            Current outcome pool: $500
            User bets: $100
            
            New total: $900
            New outcome pool: $600
            Locked odds: 900 / 600 = 1.50x
        """
        total_pool = AMMCalculator.get_total_pool(db, market_id)
        outcome_pool = AMMCalculator.get_outcome_pool(db, market_id, outcome_id)
        
        # Special case: First bet in market (pool is empty)
        if total_pool == Decimal("0.00"):
            # Count number of outcomes in market
            outcome_count = db.query(Outcome).filter(
                Outcome.market_id == market_id
            ).count()
            
            # First bettor gets odds equal to number of outcomes
            # (Fair odds: equal chance for each outcome)
            return Decimal(str(outcome_count))
        
        # Calculate new pools after bet
        new_total_pool = total_pool + bet_amount
        new_outcome_pool = outcome_pool + bet_amount
        
        # Locked odds formula
        locked_odds = new_total_pool / new_outcome_pool
        
        # Ensure minimum odds
        if locked_odds < Decimal("1.01"):
            locked_odds = Decimal("1.01")
        
        return locked_odds.quantize(Decimal("0.01"))
    
    @staticmethod
    def calculate_potential_payout(
        locked_odds: Decimal,
        bet_amount: Decimal
    ) -> Decimal:
        """
        Calculate potential payout for a bet.
        
        Formula: payout = bet_amount * locked_odds
        
        Args:
            locked_odds: Locked odds for the bet
            bet_amount: Amount bet
            
        Returns:
            Potential payout if bet wins
            
        Example:
            Bet: $100
            Locked odds: 1.80x
            Payout: 100 * 1.80 = $180
        """
        payout = bet_amount * locked_odds
        return payout.quantize(Decimal("0.01"))
    
    @staticmethod
    def get_all_current_odds(
        db: Session,
        market_id: int
    ) -> Dict[int, Decimal]:
        """
        Get current odds for all outcomes in a market.
        
        Args:
            db: Database session
            market_id: Market ID
            
        Returns:
            Dictionary mapping outcome_id -> current_odds
            
        Example:
            {
                1: Decimal("1.60"),  # Outcome A
                2: Decimal("2.67")   # Outcome B
            }
        """
        # Get all outcomes for this market
        outcomes = db.query(Outcome).filter(
            Outcome.market_id == market_id
        ).all()
        
        odds_map = {}
        for outcome in outcomes:
            odds = AMMCalculator.get_current_odds(db, market_id, outcome.id)
            odds_map[outcome.id] = odds
        
        return odds_map