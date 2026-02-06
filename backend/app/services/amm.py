"""
AMM (Automated Market Maker) utilities for pool markets.

Liquidity Pool Model:
- Each outcome has its own liquidity pool (total_staked)
- Users add liquidity and receive a share of the pool
- Display odds are calculated for informational purposes only
- Winners split the entire market pool proportionally to their shares

Example:
    Market: "Match Winner"
    Pool NaVi: $700 (User1: 500$, User3: 200$)
    Pool G2: $300 (User2: 300$)
    Total market pool: $1000
    
    Display odds (informational):
    - NaVi: 1000 / 700 = 1.43x
    - G2: 1000 / 300 = 3.33x
    
    If NaVi wins:
    - User1 share of NaVi pool: 500/700 = 71.43%
    - User1 gets: 71.43% × 1000$ = 714.30$ (before fee)
    - User3 share of NaVi pool: 200/700 = 28.57%
    - User3 gets: 28.57% × 1000$ = 285.70$ (before fee)
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
        Calculate current display odds for an outcome (informational only).
        
        These odds are NOT used in payouts. They only show approximate returns
        to help users understand the pool distribution.
        
        Formula: display_odds = total_pool / outcome_pool
        
        If outcome pool is 0 (no bets yet), returns a default high odds.
        
        Args:
            db: Database session
            market_id: Market ID
            outcome_id: Outcome ID
            
        Returns:
            Display odds (e.g., 1.80 means if you bet $100 and win, you'd get ~$180)
            
        Example:
            Total pool: $1000
            Outcome pool: $700
            Display odds: 1000 / 700 = 1.43x
            
        Note: These odds change with every new bet and are only approximate.
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
    def calculate_pool_share(
        current_pool_size: Decimal,
        user_deposit: Decimal
    ) -> Decimal:
        """
        Calculate user's share percentage when adding liquidity to a pool.
        
        Formula: share = user_deposit / (current_pool_size + user_deposit)
        
        Special case: If pool is empty (first contributor), share = 100%
        
        Args:
            current_pool_size: Current size of the outcome pool
            user_deposit: Amount user is contributing
            
        Returns:
            Share percentage (e.g., 37.5 for 37.5%)
            
        Examples:
            Empty pool (first bet):
            - current_pool_size = 0
            - user_deposit = 100
            - share = 100 / (0 + 100) = 100%
            
            Existing pool:
            - current_pool_size = 500
            - user_deposit = 300
            - share = 300 / (500 + 300) = 37.5%
        """
        new_pool_size = current_pool_size + user_deposit
        
        if new_pool_size == Decimal("0.00"):
            return Decimal("0.00")
        
        share = (user_deposit / new_pool_size) * Decimal("100")
        return share.quantize(Decimal("0.000001"))  # 6 decimal places
    
    @staticmethod
    def get_all_current_odds(
        db: Session,
        market_id: int
    ) -> Dict[int, Decimal]:
        """
        Get current display odds for all outcomes in a market.
        
        Args:
            db: Database session
            market_id: Market ID
            
        Returns:
            Dictionary mapping outcome_id -> display_odds
            
        Example:
            {
                1: Decimal("1.43"),  # NaVi
                2: Decimal("3.33")   # G2
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
    
    @staticmethod
    def calculate_estimated_roi(
        db: Session,
        market_id: int,
        outcome_id: int
    ) -> Decimal:
        """
        Calculate estimated ROI (Return on Investment) if this outcome wins.
        
        This shows users approximately how much profit they'd make relative
        to their investment if they bet on this outcome and it wins.
        
        Formula: ROI = (display_odds - 1) × 100
        
        Args:
            db: Database session
            market_id: Market ID
            outcome_id: Outcome ID
            
        Returns:
            Estimated ROI percentage (e.g., 43.0 for 43% profit)
            
        Example:
            Display odds = 1.43x
            ROI = (1.43 - 1) × 100 = 43%
            (Bet $100, get back $143, profit = $43)
        """
        odds = AMMCalculator.get_current_odds(db, market_id, outcome_id)
        roi = (odds - Decimal("1.00")) * Decimal("100")
        return roi.quantize(Decimal("0.01"))