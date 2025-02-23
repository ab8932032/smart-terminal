from abc import ABC, abstractmethod
from typing import List, Dict, AsyncGenerator

class BaseModelAdapter(ABC):
    @abstractmethod
    async def chat(
            self,
            messages: List[Dict],
            stream: bool = False,
            **kwargs
    ) -> AsyncGenerator[str, None]:
        pass

    @property
    @abstractmethod
    def event_bus(self):
        pass