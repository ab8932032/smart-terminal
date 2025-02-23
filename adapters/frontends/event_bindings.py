from core.events import EventType
from tkinter import Event

class TkinterEventBinder:
    _EVENT_MAP = {
        "<Control-Return>": EventType.USER_INPUT,
        "<Escape>": EventType.CANCEL_OPERATION,
        "<Button-3>": EventType.CONTEXT_MENU
    }

    @classmethod
    def bind_all(cls, master, event_bus):
        """自动绑定所有预设事件"""
        for tk_event, std_event in cls._EVENT_MAP.items():
            master.bind_all(tk_event,
                            lambda e, ev=std_event: cls._translate_event(e, ev, event_bus)
                            )

    @staticmethod
    def _translate_event(tk_event: Event, std_event: EventType, bus):
        """将Tkinter事件转换为标准事件"""
        event_data = {
            "source": "tkinter",
            "widget": tk_event.widget,
            "timestamp": tk_event.time,
            "coordinates": (tk_event.x, tk_event.y)
        }

        if std_event == EventType.USER_INPUT:
            event_data["text"] = tk_event.widget.get("1.0", "end-1c")

        bus.publish(std_event, event_data)

    @staticmethod
    def bind_input_events(widget, event_bus):
        widget.bind("<Control-Return>",
                    lambda e: event_bus.publish(EventType.USER_INPUT, widget.get())
                    )
