"""
Pool Market Service - Core logic for AMM-based pool betting.

Handles:
- Placing bets in liquidity pools
- Managing pool states
- Settlement and payout distribution
"""
from decimal import Decimal
from datetime import datetime
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.user import User
from app.models.market import Market, MarketStatus, MarketMode
from app.models.outcome import Outcome
from app.models.pool_bet import PoolBet
from app.models.pool_state import PoolState
from app.models.transaction import Transaction, TransactionType
from app.services.amm import AMMCalculator
from app.services.escrow import EscrowService


class PoolMarketException(Exception):
    """Base exception for pool market operations"""
    pass


class PoolMarketService:
    """Service for pool market operations"""
    
    @staticmethod
    def initialize_pool_states(
        db: Session,
        market: Market
    ) -> List[PoolState]:
        """
        Initialize pool states for all outcomes in a market.
        Called when market is created or first bet is placed.
        
        Args:
            db: Database session
            market: Market to initialize
            
        Returns:
            List of created PoolState objects
        """
        if market.market_mode != MarketMode.POOL_MARKET:
            raise PoolMarketException("Market is not a pool market")
        
        # Get all outcomes
        outcomes = db.query(Outcome).filter(
            Outcome.market_id == market.id
        ).all()
        
        if not outcomes:
            raise PoolMarketException("Market has no outcomes")
        
        pool_states = []
        for outcome in outcomes:
            # Check if already exists
            existing = db.query(PoolState).filter(
                and_(
                    PoolState.market_id == market.id,
                    PoolState.outcome_id == outcome.id
                )
            ).first()
            
            if not existing:
                pool_state = PoolState(
                    market_id=market.id,
                    outcome_id=outcome.id,
                    total_staked=Decimal("0.00"),
                    participant_count=0
                )
                db.add(pool_state)
                pool_states.append(pool_state)
        
        db.commit()
        return pool_states
    
    @staticmethod
    def place_pool_bet(
        db: Session,
        user: User,
        market_id: int,
        outcome_id: int,
        amount: Decimal
    ) -> PoolBet:
        """
        Place a bet in a pool market with locked odds.
        
        Flow:
        1. Validate market is pool market and open
        2. Initialize pool states if needed
        3. Calculate locked odds for this bet
        4. Lock user funds (escrow)
        5. Create PoolBet with locked odds
        6. Update PoolState (increase total_staked, participant_count)
        
        Args:
            db: Database session
            user: User placing bet
            market_id: Market ID
            outcome_id: Outcome to bet on
            amount: Bet amount
            
        Returns:
            Created PoolBet
            
        Raises:
            PoolMarketException: If validation fails
        """
        # Validate market
        market = db.query(Market).filter(Market.id == market_id).first()
        if not market:
            raise PoolMarketException("Market not found")
        
        if market.market_mode != MarketMode.POOL_MARKET:
            raise PoolMarketException("Market is not a pool market")
        
        if market.status != MarketStatus.OPEN:
            raise PoolMarketException(f"Market is not open for betting (status: {market.status.value})")
        
        # Validate outcome
        outcome = db.query(Outcome).filter(
            and_(
                Outcome.id == outcome_id,
                Outcome.market_id == market_id
            )
        ).first()
        if not outcome:
            raise PoolMarketException("Outcome not found or does not belong to this market")
        
        # Validate amount
        if amount <= Decimal("0.00"):
            raise PoolMarketException("Bet amount must be positive")
        
        # Initialize pool states if needed
        pool_state = db.query(PoolState).filter(
            and_(
                PoolState.market_id == market_id,
                PoolState.outcome_id == outcome_id
            )
        ).first()
        
        if not pool_state:
            PoolMarketService.initialize_pool_states(db, market)
            pool_state = db.query(PoolState).filter(
                and_(
                    PoolState.market_id == market_id,
                    PoolState.outcome_id == outcome_id
                )
            ).first()
        
        # Calculate locked odds
        locked_odds = AMMCalculator.calculate_locked_odds(
            db=db,
            market_id=market_id,
            outcome_id=outcome_id,
            bet_amount=amount
        )
        
        # Calculate potential payout
        potential_payout = AMMCalculator.calculate_potential_payout(
            locked_odds=locked_odds,
            bet_amount=amount
        )
        
        # Lock user funds
        EscrowService.lock_funds(
            db=db,
            user=user,
            amount=amount,
            description=f"Pool bet on {outcome.name}"
        )
        
        # Create pool bet
        pool_bet = PoolBet(
            user_id=user.id,
            market_id=market_id,
            outcome_id=outcome_id,
            amount=amount,
            locked_odds=locked_odds,
            potential_payout=potential_payout,
            settled=False
        )
        db.add(pool_bet)
        db.flush()
        
        # Update the transaction with pool_bet_id
        # (find the most recent POOL_BET_LOCK transaction for this user)
        # For now, just add description to transaction
        
        # Update pool state
        pool_state.total_staked += amount
        
        # Check if this is user's first bet on this outcome
        previous_bets = db.query(PoolBet).filter(
            and_(
                PoolBet.user_id == user.id,
                PoolBet.market_id == market_id,
                PoolBet.outcome_id == outcome_id,
                PoolBet.id != pool_bet.id
            )
        ).count()
        
        if previous_bets == 0:
            pool_state.participant_count += 1
        
        db.commit()
        db.refresh(pool_bet)
        
        return pool_bet
    
    @staticmethod
    def get_pool_state(
        db: Session,
        market_id: int
    ) -> Dict:
        """
        Get current pool state for a market.
        
        Returns:
            Dictionary with pool statistics and current odds
            
        Example:
            {
                "market_id": 5,
                "total_pool": "800.00",
                "outcomes": [
                    {
                        "outcome_id": 1,
                        "name": "NaVi",
                        "total_staked": "500.00",
                        "participant_count": 3,
                        "current_odds": "1.60"
                    },
                    {
                        "outcome_id": 2,
                        "name": "G2",
                        "total_staked": "300.00",
                        "participant_count": 2,
                        "current_odds": "2.67"
                    }
                ]
            }
        """
        market = db.query(Market).filter(Market.id == market_id).first()
        if not market:
            raise PoolMarketException("Market not found")
        
        if market.market_mode != MarketMode.POOL_MARKET:
            raise PoolMarketException("Market is not a pool market")
        
        # Get total pool
        total_pool = AMMCalculator.get_total_pool(db, market_id)
        
        # Get all pool states
        pool_states = db.query(PoolState).filter(
            PoolState.market_id == market_id
        ).all()
        
        # Get all outcomes with their current odds
        outcomes_data = []
        for pool_state in pool_states:
            outcome = db.query(Outcome).filter(
                Outcome.id == pool_state.outcome_id
            ).first()
            
            current_odds = AMMCalculator.get_current_odds(
                db=db,
                market_id=market_id,
                outcome_id=pool_state.outcome_id
            )
            
            outcomes_data.append({
                "outcome_id": pool_state.outcome_id,
                "name": outcome.name if outcome else "Unknown",
                "total_staked": str(pool_state.total_staked),
                "participant_count": pool_state.participant_count,
                "current_odds": str(current_odds)
            })
        
        return {
            "market_id": market_id,
            "total_pool": str(total_pool),
            "outcomes": outcomes_data
        }
    
    @staticmethod
    def get_user_pool_bets(
        db: Session,
        user_id: int,
        market_id: Optional[int] = None,
        settled: Optional[bool] = None
    ) -> List[PoolBet]:
        """
        Get user's pool bets.
        
        Args:
            db: Database session
            user_id: User ID
            market_id: Optional filter by market
            settled: Optional filter by settlement status
            
        Returns:
            List of PoolBet objects
        """
        query = db.query(PoolBet).filter(PoolBet.user_id == user_id)
        
        if market_id is not None:
            query = query.filter(PoolBet.market_id == market_id)
        
        if settled is not None:
            query = query.filter(PoolBet.settled == settled)
        
        return query.order_by(PoolBet.created_at.desc()).all()
    
    @staticmethod
    def settle_pool_market(
        db: Session,
        market_id: int,
        winning_outcome_id: int
    ) -> Dict:
        """
        Settle pool market and distribute payouts to winners.
        
        Settlement Logic:
        1. All bets on winning outcome get paid out
        2. All bets on losing outcomes are lost
        3. Payout = user's potential_payout - (profit * 2% fee)
        4. If insufficient liquidity (total from losers < total promised to winners):
           - Proportional distribution: each winner gets (ratio * their_payout)
           - ratio = total_from_losers / total_promised_to_winners
        
        Args:
            db: Database session
            market_id: Market to settle
            winning_outcome_id: Winning outcome ID
            
        Returns:
            Dictionary with settlement statistics
            
        Example:
            Winning bets promise total: $1000
            Losing bets total: $800
            Ratio: 800 / 1000 = 0.8
            User with $100 payout gets: 100 * 0.8 = $80
        """
        from app.models.transaction import Transaction
        
        # Validate market
        market = db.query(Market).filter(Market.id == market_id).first()
        if not market:
            raise PoolMarketException("Market not found")
        
        if market.market_mode != MarketMode.POOL_MARKET:
            raise PoolMarketException("Market is not a pool market")
        
        if market.status != MarketStatus.SETTLED:
            raise PoolMarketException(
                f"Market must be SETTLED status (current: {market.status.value})"
            )
        
        if market.winning_outcome_id != winning_outcome_id:
            raise PoolMarketException(
                f"Winning outcome mismatch: market says {market.winning_outcome_id}, "
                f"settlement says {winning_outcome_id}"
            )
        
        # Get all bets for this market
        all_bets = db.query(PoolBet).filter(
            PoolBet.market_id == market_id,
            PoolBet.settled == False
        ).all()
        
        if not all_bets:
            return {
                "market_id": market_id,
                "winning_outcome_id": winning_outcome_id,
                "winners_count": 0,
                "losers_count": 0,
                "total_distributed": "0.00",
                "message": "No unsettled bets found"
            }
        
        # Separate winners and losers
        winning_bets = [bet for bet in all_bets if bet.outcome_id == winning_outcome_id]
        losing_bets = [bet for bet in all_bets if bet.outcome_id != winning_outcome_id]
        
        # Calculate totals
        total_promised_to_winners = sum(bet.potential_payout for bet in winning_bets)
        total_from_losers = sum(bet.amount for bet in losing_bets)
        
        # Calculate distribution ratio
        if total_promised_to_winners == Decimal("0.00"):
            # No winners (shouldn't happen, but handle gracefully)
            distribution_ratio = Decimal("0.00")
        elif total_from_losers >= total_promised_to_winners:
            # Sufficient liquidity - full payout with fees
            distribution_ratio = Decimal("1.00")
        else:
            # Insufficient liquidity - proportional distribution
            distribution_ratio = total_from_losers / total_promised_to_winners
        
        total_distributed = Decimal("0.00")
        total_fees = Decimal("0.00")
        
        # Settle losing bets (they lose their stake)
        for bet in losing_bets:
            user = db.query(User).filter(User.id == bet.user_id).first()
            
            # Unlock funds (user loses them)
            user.balance_locked -= bet.amount
            
            # Record transaction
            tx = Transaction(
                user_id=user.id,
                type=TransactionType.SETTLEMENT,
                amount=-bet.amount,
                balance_available_before=user.balance_available,
                balance_available_after=user.balance_available,
                balance_locked_before=user.balance_locked + bet.amount,
                balance_locked_after=user.balance_locked,
                description=f"Pool bet #{bet.id} settled: LOSS"
            )
            db.add(tx)
            
            # Mark bet as settled
            bet.settled = True
            bet.settled_at = datetime.now()
            bet.actual_payout = Decimal("0.00")
        
        # Settle winning bets (they get paid out)
        for bet in winning_bets:
            user = db.query(User).filter(User.id == bet.user_id).first()
            
            # Calculate actual payout
            if distribution_ratio == Decimal("1.00"):
                # Full payout with 2% fee
                profit = bet.potential_payout - bet.amount
                fee = profit * PoolMarketService.FEE_RATE
                actual_payout = bet.potential_payout - fee
            else:
                # Proportional payout (no fee on partial payouts)
                actual_payout = bet.potential_payout * distribution_ratio
                fee = Decimal("0.00")
            
            # Unlock stake and add payout
            user.balance_locked -= bet.amount
            user.balance_available += actual_payout
            
            # Record transaction
            net_profit = actual_payout - bet.amount
            tx = Transaction(
                user_id=user.id,
                type=TransactionType.SETTLEMENT,
                amount=net_profit,
                balance_available_before=user.balance_available - actual_payout,
                balance_available_after=user.balance_available,
                balance_locked_before=user.balance_locked + bet.amount,
                balance_locked_after=user.balance_locked,
                description=f"Pool bet #{bet.id} settled: WIN (payout: {actual_payout}, fee: {fee})"
            )
            db.add(tx)
            
            # Record fee if applicable
            if fee > Decimal("0.00"):
                fee_tx = Transaction(
                    user_id=user.id,
                    type=TransactionType.FEE,
                    amount=fee,
                    balance_available_before=user.balance_available,
                    balance_available_after=user.balance_available,
                    balance_locked_before=user.balance_locked,
                    balance_locked_after=user.balance_locked,
                    description=f"Platform fee (2%) on pool bet #{bet.id}"
                )
                db.add(fee_tx)
                total_fees += fee
            
            # Mark bet as settled
            bet.settled = True
            bet.settled_at = datetime.now()
            bet.actual_payout = actual_payout
            
            total_distributed += actual_payout
        
        db.commit()
        
        # Return settlement summary
        return {
            "market_id": market_id,
            "winning_outcome_id": winning_outcome_id,
            "winners_count": len(winning_bets),
            "losers_count": len(losing_bets),
            "total_promised": str(total_promised_to_winners),
            "total_from_losers": str(total_from_losers),
            "distribution_ratio": str(distribution_ratio),
            "total_distributed": str(total_distributed),
            "total_fees": str(total_fees),
            "liquidity_sufficient": distribution_ratio == Decimal("1.00")
        }
    
    # Platform fee (2%)
    FEE_RATE = Decimal("0.02")