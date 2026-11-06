"""agxai: a provider-neutral, framework-agnostic explainability layer for AI agents."""

import logging
from importlib.metadata import PackageNotFoundError, version

from .attribution import EvidenceAttribution, HybridAttribution, RuleBasedAttribution
from .config import XAIConfig
from .core import (
    AttributionEngine,
    AttributionResult,
    Audience,
    CanonicalEvent,
    CaptureMode,
    CapturePolicy,
    Decision,
    DecisionFactor,
    DecisionType,
    Evidence,
    EvidenceType,
    Execution,
    ExecutionContext,
    ExecutionStatus,
    Explanation,
    ExplanationContext,
    ExplanationEngine,
    FailureMode,
    HumanInteraction,
    HumanInteractionType,
    InterruptEvent,
    MemoryOperation,
    NodeExecution,
    ObservabilityProvider,
    PolicyAction,
    PolicyDecision,
    PolicyProvider,
    ProvenanceLink,
    ProvenanceStore,
    RetrievedDocument,
    SourceReference,
    StateTransition,
    ToolExecution,
    ToolStatus,
)
from .explanation import LLMExplanationEngine, StructuredExplanationEngine
from .integrations import FrameworkInstrumentor
from .observability import (
    LangfuseObservability,
    LangSmithObservability,
    NoOpObservability,
    OpenTelemetryObservability,
)
from .plugins import PluginManager, SemanticArtifact, XAIPlugin
from .policy import DefaultCapturePolicy, DefaultPolicyProvider
from .runtime import RUN_ID_METADATA_KEY, Registry, Run, XAIInstrumentationError, XAIRuntime
from .storage import InMemoryProvenanceStore, StoreFilter

try:
    __version__ = version("agxai")
except PackageNotFoundError:  # pragma: no cover - only when imported from a source tree
    __version__ = "0.0.0"

# A library must not configure logging; the application decides where records go.
logging.getLogger(__name__).addHandler(logging.NullHandler())

__all__ = [
    "RUN_ID_METADATA_KEY",
    "AttributionEngine",
    "AttributionResult",
    "Audience",
    "CanonicalEvent",
    "CaptureMode",
    "CapturePolicy",
    "Decision",
    "DecisionFactor",
    "DecisionType",
    "DefaultCapturePolicy",
    "DefaultPolicyProvider",
    "Evidence",
    "EvidenceAttribution",
    "EvidenceType",
    "Execution",
    "ExecutionContext",
    "ExecutionStatus",
    "Explanation",
    "ExplanationContext",
    "ExplanationEngine",
    "FailureMode",
    "FrameworkInstrumentor",
    "HumanInteraction",
    "HumanInteractionType",
    "HybridAttribution",
    "InMemoryProvenanceStore",
    "InterruptEvent",
    "LLMExplanationEngine",
    "LangSmithObservability",
    "LangfuseObservability",
    "MemoryOperation",
    "NoOpObservability",
    "NodeExecution",
    "ObservabilityProvider",
    "OpenTelemetryObservability",
    "PluginManager",
    "PolicyAction",
    "PolicyDecision",
    "PolicyProvider",
    "ProvenanceLink",
    "ProvenanceStore",
    "Registry",
    "RetrievedDocument",
    "RuleBasedAttribution",
    "Run",
    "SemanticArtifact",
    "SourceReference",
    "StateTransition",
    "StoreFilter",
    "StructuredExplanationEngine",
    "ToolExecution",
    "ToolStatus",
    "XAIConfig",
    "XAIInstrumentationError",
    "XAIPlugin",
    "XAIRuntime",
    "__version__",
]
