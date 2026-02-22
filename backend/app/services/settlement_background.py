# app/services/settlement_background.py
"""
Background task for automatic settlement of unchallenged claims.

Runs periodically to settle contracts where challenge period has expired.
"""
import time
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.contract import Contract, ContractStatus
from app.models.market import Market, MarketStatus
from app.services.settlement import SettlementService, SettlementException


class SettlementBackgroundTask:
    """
    Background task for auto-settling unchallenged claims.
    
    Checks for contracts in CLAIMED status where challenge_deadline
    has passed and automatically settles them.
    """
    
    def __init__(self, check_interval_seconds: int = 60):
        """
        Initialize settlement task.
        
        Args:
            check_interval_seconds: How often to check for pending claims
        """
        self.check_interval_seconds = check_interval_seconds
    
    def process_once(self) -> dict:
        """
        Single processing cycle.
        
        Finds and settles all contracts ready for auto-settlement.
        
        Returns:
            dict: Statistics about the processing cycle
        """
        db = SessionLocal()
        stats = {
            "contracts_checked": 0,
            "contracts_settled": 0,
            "errors": []
        }
        
        try:
            # Get contracts ready for auto-settlement
            pending_contracts = SettlementService.get_pending_claims(db)
            stats["contracts_checked"] = len(pending_contracts)
            
            for contract in pending_contracts:
                try:
                    self._settle_contract(db, contract, stats)
                except Exception as e:
                    error_msg = f"Error settling contract {contract.id}: {str(e)}"
                    stats["errors"].append(error_msg)
                    print(f"[SettlementTask] {error_msg}")
            
            db.commit()
            
        except Exception as e:
            db.rollback()
            stats["errors"].append(f"Fatal error: {str(e)}")
            print(f"[SettlementTask] Fatal error: {str(e)}")
        
        finally:
            db.close()
        
        return stats
    
    def _settle_contract(self, db: Session, contract: Contract, stats: dict):
        """
        Settle a single contract.
        
        Args:
            db: Database session
            contract: Contract to settle
            stats: Statistics dict to update
        """
        try:
            # Get market to verify it's settled
            market = db.query(Market).filter(Market.id == contract.market_id).first()
            
            if not market:
                raise SettlementException(f"Market {contract.market_id} not found")
            
            if market.status != MarketStatus.SETTLED:
                print(
                    f"[SettlementTask] Skipping contract {contract.id}: "
                    f"market {market.id} not settled yet"
                )
                return
            
            if not market.winning_outcome_id:
                raise SettlementException(
                    f"Market {market.id} has no winning outcome"
                )
            
            # Auto-settle the contract
            SettlementService.auto_settle_unchallenged(db, contract)
            stats["contracts_settled"] += 1
            
            print(
                f"[SettlementTask] Auto-settled contract {contract.id}: "
                f"winner={contract.winner_id}"
            )
        
        except SettlementException as e:
            raise  # Re-raise to be caught by caller
    
    def run_forever(self):
        """
        Run auto-settlement loop forever.
        
        Checks for pending claims at regular intervals.
        """
        print(
            f"[SettlementTask] Starting auto-settlement task "
            f"(interval: {self.check_interval_seconds}s)"
        )
        
        while True:
            try:
                print(f"[SettlementTask] Processing at {datetime.now(timezone.utc)}")
                stats = self.process_once()
                print(f"[SettlementTask] Stats: {stats}")
                
            except KeyboardInterrupt:
                print("[SettlementTask] Stopped by user")
                break
            
            except Exception as e:
                print(f"[SettlementTask] Unexpected error: {str(e)}")
            
            # Wait for next cycle
            time.sleep(self.check_interval_seconds)


# Convenience function for manual triggering
def trigger_settlement():
    """
    Manually trigger a single settlement cycle.
    
    Useful for testing or manual settlement runs.
    
    Returns:
        dict: Processing statistics
    """
    task = SettlementBackgroundTask()
    return task.process_once()