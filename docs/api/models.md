# Canonical models

Every record is a Pydantic v2 model with a `schema_version`. Unknown fields are
rejected, numbers must be finite, and timestamps must be timezone-aware. See
[Canonical model](../architecture/canonical-model.md) for the rules and
[Concepts](../guide/concepts/index.md) for what each record means. All classes on
this page are importable from `agxai.core`; the most common ones are
also importable from `agxai`.

## Context and execution

::: agxai.core.models.ExecutionContext

::: agxai.core.models.Execution

::: agxai.core.models.NodeExecution

::: agxai.core.models.StateTransition

::: agxai.core.models.StateChange

::: agxai.core.models.ToolExecution

::: agxai.core.models.RetrievalExecution

::: agxai.core.models.RetrievedDocument

::: agxai.core.models.MemoryReference

::: agxai.core.models.CheckpointReference

::: agxai.core.models.HumanInteraction

::: agxai.core.models.ExceptionEvent

## Decision basis

::: agxai.core.models.Evidence

::: agxai.core.models.SourceReference

::: agxai.core.models.Decision

::: agxai.core.models.DecisionFactor

::: agxai.core.models.ProvenanceLink

## Explanation

::: agxai.core.models.AttributionResult

::: agxai.core.models.AttributionContribution

::: agxai.core.models.PolicyDecision

::: agxai.core.models.ExplanationContext

::: agxai.core.models.Explanation

::: agxai.core.models.EvidenceReference

## Events

`CanonicalEvent` is the union of the event types below, discriminated by
`event_type`.

::: agxai.core.models.XAIEvent

::: agxai.core.models.ExecutionStartedEvent

::: agxai.core.models.ExecutionCompletedEvent

::: agxai.core.models.ExecutionFailedEvent

::: agxai.core.models.StateTransitionEvent

::: agxai.core.models.NodeExecutionEvent

::: agxai.core.models.ToolExecutionEvent

::: agxai.core.models.RetrievalExecutionEvent

::: agxai.core.models.CheckpointEvent

::: agxai.core.models.InterruptEvent

## Enumerations

::: agxai.core.models.CaptureMode

::: agxai.core.models.FailureMode

::: agxai.core.models.ExecutionStatus

::: agxai.core.models.ToolStatus

::: agxai.core.models.DecisionType

::: agxai.core.models.EvidenceType

::: agxai.core.models.Audience

::: agxai.core.models.MemoryOperation

::: agxai.core.models.HumanInteractionType

::: agxai.core.models.PolicyAction

## Base classes

::: agxai.core.models.CanonicalModel

::: agxai.core.models.IdentifiedModel
