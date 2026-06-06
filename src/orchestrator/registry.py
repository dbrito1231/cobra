"""Component registry R1–R7."""

from __future__ import annotations

from orchestrator.models import ComponentName, ComponentRecord, HealthState

DEPENDENCY_GRAPH: dict[ComponentName, tuple[ComponentName, ...]] = {
    ComponentName.CONFIGURATION: (),
    ComponentName.SECURITY: (ComponentName.CONFIGURATION,),
    ComponentName.MCP: (ComponentName.CONFIGURATION,),
    ComponentName.BRAIN: (ComponentName.CONFIGURATION, ComponentName.MCP),
    ComponentName.TOOLS: (ComponentName.CONFIGURATION, ComponentName.MCP, ComponentName.BRAIN),
    ComponentName.VOICE: (ComponentName.CONFIGURATION, ComponentName.BRAIN),
    ComponentName.CHAT_UI: (
        ComponentName.CONFIGURATION,
        ComponentName.BRAIN,
        ComponentName.VOICE,
    ),
    ComponentName.ORCHESTRATOR: (),
}


class ComponentRegistry:
    """Maintains component dependency graph and health states."""

    def __init__(self) -> None:
        self._components: dict[ComponentName, ComponentRecord] = {}
        for name, deps in DEPENDENCY_GRAPH.items():
            self._components[name] = ComponentRecord(name=name, dependencies=deps)

    def mark_state(
        self,
        name: ComponentName,
        state: HealthState,
        *,
        message: str = "",
    ) -> None:
        record = self._components[name]
        record.state = state
        record.message = message

    def get(self, name: ComponentName) -> ComponentRecord:
        return self._components[name]

    def all(self) -> list[ComponentRecord]:
        return list(self._components.values())

    def dependencies_ready(self, name: ComponentName) -> bool:
        record = self._components[name]
        for dep in record.dependencies:
            dep_state = self._components[dep].state
            if dep_state not in {HealthState.HEALTHY, HealthState.DEGRADED}:
                return False
        return True

    def snapshot(self) -> list[dict]:
        return [record.to_dict() for record in self.all()]
