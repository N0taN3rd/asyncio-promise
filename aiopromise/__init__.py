from asyncio import (
    AbstractEventLoop,
    Future,
    run,
    get_event_loop,
    sleep,
    CancelledError
)
from asyncio.base_futures import _CANCELLED, _FINISHED, InvalidStateError
from contextvars import ContextVar
from inspect import isawaitable
from random import randint
from typing import Generic, Optional, TypeVar, Callable, Awaitable

import uvloop

uvloop.install()

__all__ = ["Promise"]

T = TypeVar("T")
TT = TypeVar("TT")


thenable_call_count: ContextVar[int] = ContextVar("thenable_call_count")
thenable_call_count.set(0)


class Promise(Generic[T], Future):
    def __init__(self, *, loop: Optional[AbstractEventLoop] = None) -> None:
        super().__init__(loop=loop)
        self._actual_result: T = None
        self._result_once: bool = False
        self._await_count = 0
        self._eloop = loop
        self._children = []
        self._thenable: Callable[..., Awaitable[T]] = None

    def then(self, fn: Callable[..., Awaitable[TT]]) -> 'Promise[TT]':
        self._children.append(fn)
        return self

    def set_result(self, result: T) -> None:
        if self._actual_result is None:
            super().set_result(result)
        self._actual_result = result

    def result(self) -> T:
        if self._state == _CANCELLED:
            raise CancelledError
        if self._state != _FINISHED:
            raise InvalidStateError("Result is not ready.")
        return self._actual_result

    def __await__(self) -> T:
        if not self.done():
            self._asyncio_future_blocking = True
            yield self  # This tells Task to wait for completion.
        if len(self._children):
            for child in self._children:
                result = child(self._actual_result)
                if isawaitable(result):
                    self._actual_result = yield from result.__await__()
                else:
                    self._actual_result = result
        if not self.done():
            raise RuntimeError("await wasn't used with future")
        return self._actual_result


async def thenable(*args) -> bool:
    thenable_call_count.set(thenable_call_count.get() + 1)
    # thenable_call_count += 1
    print(f"thenable awaited {thenable_call_count.get()}")
    return randint(0, 100)


async def test_promise():
    loop = get_event_loop()
    p: Promise[int] = Promise(loop=loop).then(thenable)

    async def resolve_promise():
        await sleep(0)
        p.set_result(0)

    loop.create_task(resolve_promise())
    print(await p)
    print(await p)
    print(await p)


if __name__ == "__main__":
    run(test_promise())
