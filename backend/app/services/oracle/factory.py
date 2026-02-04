# app/services/oracle/factory.py
"""
Factory for creating oracle providers.
"""
from typing import Optional
from .base import OracleProvider
from .providers.mock import MockOracleProvider


class OracleFactory:
    """
    Factory for creating oracle provider instances.
    
    Usage:
        oracle = OracleFactory.create("mock")
        result = oracle.fetch_match_result("match_1")
    """
    
    # Registry of available providers
    PROVIDERS = {
        "mock": MockOracleProvider,
        # "pandascore": PandaScoreProvider,  # Add later
        # "hltv": HLTVProvider,  # Add later
    }
    
    @classmethod
    def create(
        cls,
        provider_name: str,
        api_key: Optional[str] = None,
        **kwargs
    ) -> OracleProvider:
        """
        Create oracle provider instance.
        
        Args:
            provider_name: Name of provider ("mock", "pandascore", etc)
            api_key: Optional API key for authenticated providers
            **kwargs: Additional provider-specific configuration
            
        Returns:
            OracleProvider: Instance of the requested provider
            
        Raises:
            ValueError: If provider_name is not registered
            
        Example:
            # Create mock provider
            oracle = OracleFactory.create("mock")
            
            # Create PandaScore provider (later)
            oracle = OracleFactory.create("pandascore", api_key="your_key")
        """
        provider_class = cls.PROVIDERS.get(provider_name.lower())
        
        if not provider_class:
            available = ", ".join(cls.PROVIDERS.keys())
            raise ValueError(
                f"Unknown oracle provider: {provider_name}. "
                f"Available providers: {available}"
            )
        
        return provider_class(api_key=api_key, **kwargs)
    
    @classmethod
    def register_provider(cls, name: str, provider_class: type):
        """
        Register a new provider.
        
        Allows adding custom providers at runtime.
        
        Args:
            name: Provider name
            provider_class: Provider class (must inherit from OracleProvider)
            
        Example:
            OracleFactory.register_provider("custom", CustomProvider)
        """
        if not issubclass(provider_class, OracleProvider):
            raise TypeError(
                f"{provider_class} must inherit from OracleProvider"
            )
        
        cls.PROVIDERS[name.lower()] = provider_class
    
    @classmethod
    def list_providers(cls) -> list[str]:
        """
        List all registered providers.
        
        Returns:
            list: Names of available providers
        """
        return list(cls.PROVIDERS.keys())