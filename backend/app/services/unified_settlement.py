"""
Unified Settlement Service - роутер для settlement обоих типов маркетов
"""
from sqlalchemy.orm import Session
from app.models.market import Market, MarketMode, MarketStatus
from app.services.pool_market import PoolMarketService
from app.services.settlement import SettlementService


class UnifiedSettlementService:
    """
    Сервис для унифицированного settlement маркетов.
    Автоматически определяет тип маркета и вызывает нужный settlement service.
    """
    
    @staticmethod
    def settle_market(market_id: int, db: Session) -> dict:
        """
        Универсальный метод для settlement маркета любого типа.
        
        Args:
            market_id: ID маркета для settlement
            db: Database session
            
        Returns:
            Dict с результатами settlement (структура зависит от типа маркета)
            
        Raises:
            ValueError: если маркет не найден, не в статусе SETTLED, или неизвестный mode
        """
        # Получаем маркет
        market = db.query(Market).filter(Market.id == market_id).first()
        if not market:
            raise ValueError("Market not found")
        
        # Проверяем что маркет в статусе SETTLED
        if market.status != MarketStatus.SETTLED:
            raise ValueError("Market must be in SETTLED status before settlement")
        
        # Проверяем что есть winning outcome
        if not market.winning_outcome_id:
            raise ValueError("Market must have winning_outcome_id set")
        
        # Роутинг по типу маркета
        if market.market_mode == MarketMode.P2P_DIRECT:
            # P2P Direct - settlement через SettlementService
            result = SettlementService.settle_market(market_id, db)
            result["mode"] = "P2P_DIRECT"
            return result
            
        elif market.market_mode == MarketMode.POOL_MARKET:
            # Pool Market - settlement через PoolMarketService
            result = PoolMarketService.settle_pool_market(
                db=db,
                market_id=market_id,
                winning_outcome_id=market.winning_outcome_id
            )
            
            # Добавляем mode к результату
            result["mode"] = "POOL_MARKET"
            return result
        
        else:
            # Неизвестный режим
            raise ValueError(f"Unknown market mode: {market.market_mode}")