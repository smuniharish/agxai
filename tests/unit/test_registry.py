from typing import Any

import pytest

from agxai import (
    AttributionEngine,
    CapturePolicy,
    ExplanationEngine,
    ObservabilityProvider,
    PolicyProvider,
    ProvenanceStore,
    Registry,
    XAIPlugin,
    XAIRuntime,
)
from tests.helpers import RecordingObservability


def test_registry_is_instance_scoped() -> None:
    first, second = Registry(), Registry()
    provider = RecordingObservability()

    assert first.register(ObservabilityProvider, provider) is provider
    assert first.get(ObservabilityProvider) is provider
    assert first.require(ObservabilityProvider) is provider
    assert second.get(ObservabilityProvider) is None
    assert first.capabilities() == (ObservabilityProvider,)


def test_require_and_register_validate_providers() -> None:
    registry = Registry()

    with pytest.raises(LookupError, match="ObservabilityProvider"):
        registry.require(ObservabilityProvider)
    with pytest.raises(TypeError, match="does not subclass ProvenanceStore"):
        registry.register(ProvenanceStore, object())


def test_remove_returns_the_provider() -> None:
    registry = Registry()
    provider = registry.register(ObservabilityProvider, RecordingObservability())

    assert registry.remove(ObservabilityProvider) is provider
    assert registry.remove(ObservabilityProvider) is None
    assert registry.get(ObservabilityProvider) is None


def test_structurally_matching_classes_are_rejected() -> None:
    class LooksLikeObservability:
        async def emit(self, event: object) -> None: ...

        async def flush(self) -> None: ...

        async def close(self) -> None: ...

    class LooksLikePlugin:
        async def record(self, artifact: object) -> None: ...

        async def flush(self) -> None: ...

        async def close(self) -> None: ...

    runtime = XAIRuntime()
    with pytest.raises(TypeError, match="does not subclass ObservabilityProvider"):
        runtime.register(ObservabilityProvider, LooksLikeObservability())  # pyrefly: ignore[bad-argument-type]
    with pytest.raises(TypeError, match="does not subclass XAIPlugin"):
        runtime.plugins.add(LooksLikePlugin())  # pyrefly: ignore[bad-argument-type]


@pytest.mark.parametrize(
    ("capability", "method"),
    [
        (ProvenanceStore, "write"),
        (ObservabilityProvider, "emit"),
        (CapturePolicy, "evaluate"),
        (PolicyProvider, "evaluate"),
        (AttributionEngine, "attribute"),
        (ExplanationEngine, "explain"),
        (XAIPlugin, "record"),
    ],
)
def test_capabilities_enforce_their_abstract_methods(capability: type[Any], method: str) -> None:
    incomplete = type(f"Incomplete{capability.__name__}", (capability,), {})

    assert method in capability.__abstractmethods__
    with pytest.raises(TypeError, match="abstract"):
        incomplete()


async def test_lifecycle_hooks_default_to_no_ops() -> None:
    class Observability(ObservabilityProvider):
        async def emit(self, event: object) -> None: ...

    class Plugin(XAIPlugin):
        async def record(self, artifact: object) -> None: ...

    assert not ExplanationEngine.requires_llm
    for provider in (Observability(), Plugin()):
        assert await provider.flush() is None
        assert await provider.close() is None
