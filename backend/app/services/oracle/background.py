# app/services/oracle/background.py
"""
Background task for polling match results and triggering settlement.
"""
import time
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.event import Event, EventStatus
from app.models.market import Market, MarketStatus
from app.config import settings
from app.services.unified_settlement import UnifiedSettlementService
from .service import OracleService
from .base import MatchNotFoundException, OracleAPIException

logger = logging.getLogger(__name__)


class OracleBackgroundTask:
    """
    Background task that periodically checks for match results
    and updates event/market status.
    
    In production, this would run in Celery/RQ.
    For MVP, can be run in a separate thread or manually triggered.
    """
    
    def __init__(self, provider_name: Optional[str] = None):
        """
        Initialize background task.
        
        Args:
            provider_name: Override default provider from settings
        """
        self.provider_name = provider_name or settings.ORACLE_PROVIDER
        self.oracle = OracleService(
            provider_name=self.provider_name,
            api_key=settings.ORACLE_API_KEY
        )
    
    def poll_once(self) -> dict:
        """
        Single polling cycle.
        
        Checks all events in LIVE or FINISHED status and updates them.
        
        For each finished event:
        - Fetches result from oracle provider
        - Updates market status to SETTLED
        - Sets winning_outcome_id
        - Triggers unified settlement (supports both P2P_DIRECT and POOL_MARKET modes)
        
        Returns:
            dict: Statistics about the polling cycle
        """
        db = SessionLocal()
        stats = {
            "events_checked": 0,
            "events_updated": 0,
            "markets_settled": 0,
            "errors": []
        }
        
        try:
            # Get events that need checking
            events = db.query(Event).filter(
                Event.status.in_([EventStatus.LIVE, EventStatus.FINISHED]),
                Event.external_match_id.isnot(None)
            ).all()
            
            stats["events_checked"] = len(events)
            
            for event in events:
                try:
                    self._process_event(db, event, stats)
                except Exception as e:
                    error_msg = f"Error processing event {event.id}: {str(e)}"
                    stats["errors"].append(error_msg)
                    print(f"[OracleTask] {error_msg}")
            
            db.commit()
            
        except Exception as e:
            db.rollback()
            stats["errors"].append(f"Fatal error: {str(e)}")
            print(f"[OracleTask] Fatal error: {str(e)}")
        
        finally:
            db.close()
        
        return stats
    
    def _process_event(self, db: Session, event: Event, stats: dict):
        """
        Process a single event: fetch result and update status.
        
        Args:
            db: Database session
            event: Event to process
            stats: Statistics dict to update
        """
        try:
            # Fetch match result
            result = self.oracle.fetch_event_result(event)
            
            # Update event status based on result
            if result.status == "finished" and event.status != EventStatus.FINISHED:
                event.status = EventStatus.FINISHED
                event.actual_end = result.finished_at or datetime.now(timezone.utc)
                stats["events_updated"] += 1
                
                print(f"[OracleTask] Event {event.id} marked as FINISHED")
            
            # If event is finished, settle related markets
            if event.status == EventStatus.FINISHED:
                markets_settled = self._settle_event_markets(db, event, result)
                stats["markets_settled"] += markets_settled
        
        except MatchNotFoundException as e:
            print(f"[OracleTask] Match not found for event {event.id}: {str(e)}")
        
        except OracleAPIException as e:
            print(f"[OracleTask] API error for event {event.id}: {str(e)}")
    
    def _settle_event_markets(
        self,
        db: Session,
        event: Event,
        result
    ) -> int:
        """
        Settle all markets for a finished event.
        
        Args:
            db: Database session
            event: Finished event
            result: MatchResult from oracle
            
        Returns:
            int: Number of markets settled
        """
        settled_count = 0
        
        # Get all open markets for this event
        markets = db.query(Market).filter(
            Market.event_id == event.id,
            Market.status.in_([MarketStatus.OPEN, MarketStatus.LOCKED])
        ).all()
        
        for market in markets:
            # Only settle match_winner markets for now
            # TODO: Add logic for other market types
            if market.market_type == "match_winner":
                winning_outcome = self.oracle.determine_winning_outcome(
                    db, market, result
                )
                
                if winning_outcome:
                    market.winning_outcome_id = winning_outcome.id
                    market.status = MarketStatus.SETTLED
                    
                    print(
                        f"[OracleTask] Market {market.id} settled: "
                        f"winner={winning_outcome.name}"
                    )
                    
                    # Commit market status change before triggering settlement
                    db.commit()
                    
                    # Trigger unified settlement for both P2P and Pool markets
                    try:
                        settlement_result = UnifiedSettlementService.settle_market(
                            market.id, db
                        )
                        logger.info(
                            f"Market {market.id} settled via unified service",
                            extra={
                                "market_id": market.id,
                                "market_mode": market.market_mode.value,
                                "settlement_result": settlement_result
                            }
                        )
                        settled_count += 1
                    except Exception as e:
                        logger.error(
                            f"Failed to settle market {market.id}",
                            extra={
                                "market_id": market.id,
                                "error": str(e)
                            }
                        )
                        # Не прерываем весь процесс - продолжаем обработку других маркетов
        
        return settled_count
    
    def run_forever(self, interval_minutes: Optional[int] = None):
        """
        Run polling loop forever.
        
        Args:
            interval_minutes: Override default polling interval
        """
        interval = interval_minutes or settings.ORACLE_POLL_INTERVAL_MINUTES
        interval_seconds = interval * 60
        
        print(f"[OracleTask] Starting background task (interval: {interval}min)")
        
        while True:
            try:
                print(f"[OracleTask] Polling at {datetime.now(timezone.utc)}")
                stats = self.poll_once()
                print(f"[OracleTask] Stats: {stats}")
                
            except KeyboardInterrupt:
                print("[OracleTask] Stopped by user")
                break
            
            except Exception as e:
                print(f"[OracleTask] Unexpected error: {str(e)}")
            
            # Wait for next cycle
            time.sleep(interval_seconds)


# Convenience function for manual triggering
def trigger_oracle_poll():
    """
    Manually trigger a single oracle polling cycle.
    
    Useful for testing or manual settlement.
    
    Returns:
        dict: Polling statistics
    """
    task = OracleBackgroundTask()
    return task.poll_once()