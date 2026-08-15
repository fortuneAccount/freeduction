"""
Dependency Injection Container for the plugin system

Provides centralized dependency management and service location.
"""

import logging
from typing import Dict, Any, Callable, Optional, Type, TypeVar
from pathlib import Path


T = TypeVar('T')


class DependencyContainer:
    """
    Lightweight dependency injection container.
    
    Supports:
    - Singleton services
    - Factory functions
    - Lazy initialization
    - Service resolution
    """
    
    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._factories: Dict[str, Callable] = {}
        self._singletons: Dict[str, Any] = {}
        self.logger = logging.getLogger(__name__)
    
    def register_singleton(self, name: str, instance: Any):
        """
        Register a singleton instance.
        
        Args:
            name: Service name
            instance: Service instance
        """
        self._singletons[name] = instance
        self.logger.debug(f"Registered singleton: {name}")
    
    def register_factory(self, name: str, factory: Callable):
        """
        Register a factory function.
        
        Args:
            name: Service name
            factory: Factory function that creates the service
        """
        self._factories[name] = factory
        self.logger.debug(f"Registered factory: {name}")
    
    def register_type(self, name: str, service_type: Type[T], *args, **kwargs):
        """
        Register a type to be instantiated on first resolve.
        
        Args:
            name: Service name
            service_type: Class to instantiate
            *args: Constructor arguments
            **kwargs: Constructor keyword arguments
        """
        def factory():
            return service_type(*args, **kwargs)
        
        self.register_factory(name, factory)
    
    def resolve(self, name: str) -> Optional[Any]:
        """
        Resolve a service by name.
        
        Args:
            name: Service name
            
        Returns:
            Service instance or None if not found
        """
        # Check singletons first
        if name in self._singletons:
            return self._singletons[name]
        
        # Check factories
        if name in self._factories:
            instance = self._factories[name]()
            # Cache as singleton
            self._singletons[name] = instance
            return instance
        
        self.logger.warning(f"Service not found: {name}")
        return None
    
    def resolve_required(self, name: str) -> Any:
        """
        Resolve a required service (raises exception if not found).
        
        Args:
            name: Service name
            
        Returns:
            Service instance
            
        Raises:
            ValueError: If service not found
        """
        service = self.resolve(name)
        if service is None:
            raise ValueError(f"Required service not found: {name}")
        return service
    
    def has_service(self, name: str) -> bool:
        """Check if a service is registered"""
        return name in self._singletons or name in self._factories
    
    def clear(self):
        """Clear all registered services"""
        self._services.clear()
        self._factories.clear()
        self._singletons.clear()
        self.logger.info("Cleared all services from container")
    
    def get_service_names(self) -> list:
        """Get all registered service names"""
        return list(set(list(self._singletons.keys()) + list(self._factories.keys())))


# Global container instance
_container: Optional[DependencyContainer] = None


def get_container() -> DependencyContainer:
    """Get the global dependency container"""
    global _container
    if _container is None:
        _container = DependencyContainer()
    return _container


def reset_container():
    """Reset the global container (useful for testing)"""
    global _container
    _container = None
