# core/event_bus.py
import logging
from collections import defaultdict
from typing import Callable, Any
from concurrent.futures import ThreadPoolExecutor
from utils.logger import get_logger

logger = get_logger(__name__)

class EventBus:
    def __init__(self):
        self._subscriptions = defaultdict(list)
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._lock = threading.Lock()

    def subscribe(self, event_type: str, handler: Callable[[Any], None]):
        """订阅事件类型"""
        with self._lock:
            self._subscriptions[event_type].append(handler)
            logger.debug(f"Subscribed to {event_type} with {handler.__name__}")

    def unsubscribe(self, event_type: str, handler: Callable[[Any], None]):
        """取消订阅"""
        with self._lock:
            if handler in self._subscriptions[event_type]:
                self._subscriptions[event_type].remove(handler)
                logger.debug(f"Unsubscribed {handler.__name__} from {event_type}")

    def publish(self, event_type: str, data: Any = None, async_exec: bool = True):
        """发布事件"""
        handlers = self._subscriptions.get(event_type, [])
        logger.debug(f"Dispatching {event_type} to {len(handlers)} handlers")

        def _execute_handler(handler):
            try:
                if inspect.iscoroutinefunction(handler):
                    asyncio.run(handler(data))
                else:
                    handler(data)
            except Exception as e:
                logger.error(f"Error handling {event_type}: {str(e)}")
                self.publish("ERROR", {
                    "event_type": event_type,
                    "error": str(e),
                    "stack_trace": traceback.format_exc()
                })

        if async_exec:
            for handler in handlers:
                self._executor.submit(_execute_handler, handler)
        else:
            for handler in handlers:
                _execute_handler(handler)

    def clear_subscriptions(self):
        """清空所有订阅"""
        with self._lock:
            self._subscriptions.clear()
