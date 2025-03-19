# core/event_bus.py
from collections import defaultdict
from typing import Callable, Any
from concurrent.futures import ThreadPoolExecutor
from utils.logger import get_logger
import threading  # _lock的使用依赖
import asyncio    # 异步执行依赖
import inspect    # 函数类型检查依赖
import os         # 线程数计算依赖
import traceback  # 错误堆栈跟踪依赖
from core.events import EventType

logger = get_logger(__name__)
"""
1. **模块间通信中枢**
- 实现发布-订阅模式，解耦系统组件
- 支持`UserInputEvent`/`QueryResultEvent`/`ErrorEvent`等事件类型（需配合core/events.py使用）

2. **关键功能特性**
✅ 异步事件处理（ThreadPoolExecutor线程池）
✅ 同步/异步双模式发布（async_exec开关）
✅ 错误事件自动捕获与重发布
✅ 线程安全的订阅管理（with _lock）
"""
class EventBus:
    def __init__(self):
        self._subscriptions = defaultdict(list)
        self._executor = ThreadPoolExecutor(
            max_workers=min(32, (os.cpu_count() or 1) + 4)  # 动态线程数
        )
        self._lock = threading.RLock()
        self._async_loop = asyncio.new_event_loop()  # 独立事件循环

    def subscribe(self, event_type: EventType, handler: Callable[[Any], None]):
        """订阅事件类型"""
        with self._lock:
            self._subscriptions[event_type].append(handler)
            logger.debug(f"Subscribed to {event_type} with {handler.__name__}")

    def unsubscribe(self, event_type: EventType, handler: Callable[[Any], None]):
        """取消订阅"""
        with self._lock:
            if handler in self._subscriptions[event_type]:
                self._subscriptions[event_type].remove(handler)
                logger.debug(f"Unsubscribed {handler.__name__} from {event_type}")
                
    async def publish_async(self, event_type: EventType, data: Any):
        """原生异步发布方法"""
        handlers = self._subscriptions.get(event_type, [])
        try:
            await asyncio.gather(*[
                handler(data)
                for handler in handlers
                if inspect.iscoroutinefunction(handler)
            ])
        except Exception as e:
            self.publish(EventType.ERROR, {"error": str(e)})
    def publish(self, event_type: EventType, data: Any = None, async_exec: bool = True):
        """发布事件"""
        handlers = self._subscriptions.get(event_type, [])
        logger.debug(f"Dispatching {event_type} to {len(handlers)} handlers")

        def _execute_handler(handler):
            try:
                if inspect.iscoroutinefunction(handler):
                    asyncio.run_coroutine_threadsafe(handler(data), self._async_loop)
                else:
                    handler(data)
            except Exception as e:
                logger.error(f"Error handling {event_type}: {str(e)}")
                self.publish(EventType.ERROR, {
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
