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
        Add liquidity to a pool market outcome.
        
        Flow:
        1. Validate market is pool market and open
        2. Initialize pool states if needed
        3. Calculate user's pool share percentage
        4. Lock user funds (escrow)
        5. Create PoolBet with pool share
        6. Update PoolState (increase total_staked, participant_count)
        
        Args:
            db: Database session
            user: User adding liquidity
            market_id: Market ID
            outcome_id: Outcome to back
            amount: Liquidity amount
            
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
        
        # Get current pool size (before this bet)
        current_pool_size = pool_state.total_staked
        
        # Calculate user's pool share percentage
        initial_pool_share_percentage = AMMCalculator.calculate_pool_share(
            current_pool_size=current_pool_size,
            user_deposit=amount
        )
        
        # Lock user funds
        EscrowService.lock_funds(
            db=db,
            user=user,
            amount=amount,
            description=f"Liquidity for {outcome.name}"
        )
        
        # Create pool bet
        pool_bet = PoolBet(
            user_id=user.id,
            market_id=market_id,
            outcome_id=outcome_id,
            amount=amount,
            initial_pool_share_percentage=initial_pool_share_percentage,
            pool_size_at_bet=current_pool_size,
            settled=False
        )
        db.add(pool_bet)
        db.flush()
        
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
            Dictionary with pool statistics, display odds, and estimated ROI
            
        Example:
            {
                "market_id": 5,
                "total_pool": "1000.00",
                "outcomes": [
                    {
                        "outcome_id": 1,
                        "name": "NaVi",
                        "total_staked": "700.00",
                        "participant_count": 2,
                        "estimated_odds": "1.43",
                        "estimated_roi": "43.00"
                    },
                    {
                        "outcome_id": 2,
                        "name": "G2",
                        "total_staked": "300.00",
                        "participant_count": 1,
                        "estimated_odds": "3.33",
                        "estimated_roi": "233.00"
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
        
        # Get all outcomes with their display odds and estimated ROI
        outcomes_data = []
        for pool_state in pool_states:
            outcome = db.query(Outcome).filter(
                Outcome.id == pool_state.outcome_id
            ).first()
            
            estimated_odds = AMMCalculator.get_current_odds(
                db=db,
                market_id=market_id,
                outcome_id=pool_state.outcome_id
            )
            
            estimated_roi = AMMCalculator.calculate_estimated_roi(
                db=db,
                market_id=market_id,
                outcome_id=pool_state.outcome_id
            )
            
            outcomes_data.append({
                "outcome_id": pool_state.outcome_id,
                "name": outcome.name if outcome else "Unknown",
                "total_staked": str(pool_state.total_staked),
                "participant_count": pool_state.participant_count,
                "estimated_odds": str(estimated_odds),
                "estimated_roi": str(estimated_roi)
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
        
        New Liquidity Pool Settlement Logic:
        1. Winners share the ENTIRE market pool proportionally to their shares
        2. Losers lose their liquidity (goes to winners)
        3. Fee (2%) is charged only on profit
        
        Formula for each winner:
            current_share = bet.amount / winning_pool_total_staked
            payout_before_fee = current_share × total_market_pool
            profit = payout_before_fee - bet.amount
            fee = profit × 2% (only if profit > 0)
            final_payout = payout_before_fee - fee
        
        Args:
            db: Database session
            market_id: Market to settle
            winning_outcome_id: Winning outcome ID
            
        Returns:
            Dictionary with settlement statistics
            
        Example:
            Pool NaVi: 700$ (User1: 500$, User3: 200$)
            Pool G2: 300$ (User2: 300$)
            Total: 1000$
            
            NaVi wins:
            User1: share = 500/700 = 71.43%
                   payout = 71.43% × 1000$ = 714.30$
                   profit = 214.30$, fee = 4.29$
                   final = 710.01$
            
            User3: share = 200/700 = 28.57%
                   payout = 28.57% × 1000$ = 285.70$
                   profit = 85.70$, fee = 1.71$
                   final = 283.99$
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
        
        # Get all unsettled bets for this market
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
                "total_fees": "0.00",
                "message": "No unsettled bets found"
            }
        
        # Separate winners and losers
        winning_bets = [bet for bet in all_bets if bet.outcome_id == winning_outcome_id]
        losing_bets = [bet for bet in all_bets if bet.outcome_id != winning_outcome_id]
        
        # Calculate pool sizes
        winning_pool_total = sum(bet.amount for bet in winning_bets)
        total_market_pool = sum(bet.amount for bet in all_bets)
        
        total_distributed = Decimal("0.00")
        total_fees = Decimal("0.00")
        
        # Settle losing bets (they lose their liquidity)
        for bet in losing_bets:
            user = db.query(User).filter(User.id == bet.user_id).first()
            
            # Unlock funds (user loses them, they go to winners)
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
            
            # Mark bet as settled with 0 payout
            bet.settled = True
            bet.settled_at = datetime.now()
            bet.actual_payout = Decimal("0.00")
        
        # Settle winning bets (they share the total market pool)
        for bet in winning_bets:
            user = db.query(User).filter(User.id == bet.user_id).first()
            
            # Calculate this user's share of the winning pool
            if winning_pool_total > Decimal("0.00"):
                current_share = bet.amount / winning_pool_total
            else:
                current_share = Decimal("0.00")
            
            # Calculate payout before fee
            payout_before_fee = current_share * total_market_pool
            
            # Calculate profit and fee
            profit = payout_before_fee - bet.amount
            if profit > Decimal("0.00"):
                fee = profit * PoolMarketService.FEE_RATE
            else:
                fee = Decimal("0.00")
            
            # Final payout after fee
            actual_payout = payout_before_fee - fee
            
            # Unlock stake and add payout to available balance
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
            
            # Record fee transaction if applicable
            if fee > Decimal("0.00"):
                fee_tx = Transaction(
                    user_id=user.id,
                    type=TransactionType.FEE,
                    amount=-fee,
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
            "total_market_pool": str(total_market_pool),
            "winning_pool_total": str(winning_pool_total),
            "total_distributed": str(total_distributed),
            "total_fees": str(total_fees)
        }
    
    # Platform fee (2%)
    FEE_RATE = Decimal("0.02")