from typing import Callable

ProcessorFunc = Callable[[bytes], bytes]


class ProcessorRegistry:
    def __init__(self) -> None:
        self._items: dict[str, ProcessorFunc] = {}

    def register(self, name: str, func: ProcessorFunc) -> None:
        self._items[name] = func

    def get(self, name: str) -> ProcessorFunc | None:
        return self._items.get(name)

    def list_names(self) -> list[str]:
        return sorted(self._items.keys())


registry = ProcessorRegistry()
