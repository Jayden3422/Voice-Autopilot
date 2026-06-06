from .base import ResourceProvider, ResourceStatus


class ResourceRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, ResourceProvider] = {}

    def register(self, provider: ResourceProvider) -> None:
        self._providers[provider.name] = provider

    def all(self) -> list[ResourceProvider]:
        return list(self._providers.values())

    def required(self) -> list[ResourceProvider]:
        return [p for p in self._providers.values() if p.required]

    def all_required_ready(self) -> bool:
        return all(p.is_ready for p in self.required())

    def status_snapshot(self) -> dict[str, str]:
        return {name: p._status.value for name, p in self._providers.items()}


registry = ResourceRegistry()
