from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol


@dataclass(frozen=True)
class ToolCall:
    tool: str
    input: Dict[str, Any]
    id: Optional[str] = None


class Tool(Protocol):
    name: str
    description: str

    def run(self, input: Dict[str, Any]) -> Any: ...


class Agent(Protocol):
    name: str
    description: str

    def decide(self, observation: Dict[str, Any]) -> List[ToolCall]: ...
