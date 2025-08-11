from __future__ import annotations
from typing import Protocol, Any, Dict, List, Optional
from dataclasses import dataclass

@dataclass(frozen=True)
class ToolCall:
    tool: str
    input: Dict[str, Any]
    id: Optional[str] = None

class Tool(Protocol):
    name: str
    description: str
    def run(self, input: Dict[str, Any]) -> Any:
        ...

class Agent(Protocol):
    name: str
    description: str
    def decide(self, observation: Dict[str, Any]) -> List[ToolCall]:
        ...
