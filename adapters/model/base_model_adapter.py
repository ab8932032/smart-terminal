from abc import ABC, abstractmethod
from typing import List, Dict, AsyncGenerator

class BaseModelAdapter(ABC):
    def __init__(self, config: dict,event_bus):
        self.config = config
        self._event_bus = event_bus
        
    @abstractmethod
    async def chat(
            self,
            messages: List[Dict],
            stream: bool = False,
            **kwargs
    ) -> AsyncGenerator[str, None]:
        pass
    
    @property
    def event_bus(self):
        return self._event_bus
