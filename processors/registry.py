from dataclasses import dataclass
from typing import Callable

ProcessorFunc = Callable[[bytes], bytes]


@dataclass(frozen=True)
class ProcessorSpec:
    name: str
    handler: ProcessorFunc
    label: str
    description: str = ""


class ProcessorRegistry:
    def __init__(self) -> None:
        self._items: dict[str, ProcessorSpec] = {}

    def register(
        self,
        name: str,
        func: ProcessorFunc,
        *,
        label: str | None = None,
        description: str = "",
    ) -> None:
        self._items[name] = ProcessorSpec(
            name=name,
            handler=func,
            label=label or name,
            description=description,
        )

    def get(self, name: str) -> ProcessorSpec | None:
        return self._items.get(name)

    def list(self) -> list[ProcessorSpec]:
        return [self._items[name] for name in sorted(self._items.keys())]


registry = ProcessorRegistry()
