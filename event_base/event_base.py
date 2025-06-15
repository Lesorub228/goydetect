import asyncio
from typing import Any, Callable, Coroutine, Optional


EventCallable = Callable[[Any], Any] | Callable[[], Any]


class EventBase:
    def __init__(self):
        self._listeners: dict[Any, set[EventCallable]] = {}
        self._task_group: Optional[asyncio.TaskGroup] = None
        self.tore_down: bool = False
        self._setup_listeners()

    def _setup_listeners(self) -> None:
        pass

    async def _close(self) -> None:
        raise NotImplementedError

    async def teardown(self) -> None:
        self.tore_down = True
        await self._close()

    def create_task(self, coroutine: Coroutine) -> asyncio.Task:
        return self._task_group.create_task(coroutine)

    def add_listener(self, event: Any, function: EventCallable) -> None:
        if event not in self._listeners:
            self._listeners[event] = {function}
        else:
            self._listeners[event].add(function)

    def remove_listener(self, event: Any, function: EventCallable) -> None:
        self._listeners[event].remove(function)
        if not self._listeners[event]:
            self._listeners.pop(event)

    def _notify_listener(self, listener: EventCallable, message: Any = None) -> None:
        if message is not None:
            result = listener(message)
        else:
            result = listener()
        if asyncio.iscoroutine(result):
            self.create_task(result)

    def _notify_listeners(self, event: Any, message: Any = None) -> None:
        if event in self._listeners:
            for listener in self._listeners[event]:
                self._notify_listener(listener, message)

    async def _wait_for(self, event: Any) -> Any:
        ev = asyncio.Event()
        ev.result = None

        def set_event(e=None):
            ev.result = e
            ev.set()

        self.add_listener(event, set_event)
        await ev.wait()
        self.remove_listener(event, set_event)
        return ev.result

    def wait_for(self, event: Any) -> asyncio.Task:
        return self.create_task(self._wait_for(event))

    async def _run(self) -> None:
        raise NotImplementedError

    async def run(self) -> None:
        try:
            async with asyncio.TaskGroup() as task_group:
                self._task_group = task_group
                await self._run()
        finally:
            await self.teardown()
