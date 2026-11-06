import asyncio
import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from agxai import (
    AttributionEngine,
    CaptureMode,
    CapturePolicy,
    DecisionFactor,
    Evidence,
    Execution,
    ExecutionStatus,
    ExplanationEngine,
    FailureMode,
    LLMExplanationEngine,
    MemoryOperation,
    NodeExecution,
    ObservabilityProvider,
    PolicyAction,
    PolicyDecision,
    PolicyProvider,
    ProvenanceStore,
    Registry,
    RetrievedDocument,
    Run,
    RunInterrupt,
    SourceReference,
    ToolStatus,
    XAIConfig,
    XAIInstrumentationError,
    XAIRuntime,
)
from agxai.core import (
    ExecutionFailedEvent,
    InterruptEvent,
    NodeExecutionEvent,
    StateTransitionEvent,
    ToolExecutionEvent,
)
from agxai.observability import NoOpObservability
from agxai.policy import REDACTED
from agxai.runtime import runtime as runtime_module
from agxai.storage import InMemoryProvenanceStore
from tests.helpers import (
    FailingStore,
    RecordingObservability,
    RecordingPlugin,
    execution,
    executions,
    explanation_context,
    stored,
)


def make_runtime(**config) -> XAIRuntime:
    return XAIRuntime(config=XAIConfig(**config), application_id="app", tenant_id="tenant")


def test_every_capability_has_a_working_default_unless_already_registered() -> None:
    registry = Registry()
    store = registry.register(ProvenanceStore, InMemoryProvenanceStore())

    runtime = XAIRuntime(registry=registry)

    assert runtime.registry.require(ProvenanceStore) is store
    assert isinstance(runtime.registry.require(ObservabilityProvider), NoOpObservability)
    assert set(runtime.registry.capabilities()) == {
        ProvenanceStore,
        ObservabilityProvider,
        AttributionEngine,
        ExplanationEngine,
        PolicyProvider,
        CapturePolicy,
    }


def test_context_from_config_applies_overrides_and_sanitizes_metadata() -> None:
    runtime = make_runtime()
    run_id = "4f8f6f1e-7a7b-4f2c-9f8a-0d6c2f1d9b11"

    ctx = runtime.context_from_config(
        {
            "metadata": {
                "xai_application_id": "other-app",
                "xai_tenant_id": "tenant-b",
                "xai_graph_id": "g2",
                "xai_run_id": run_id,
                "trace_id": "trace-1",
                "api_key": "secret",
                "team": "risk",
            },
            "configurable": {"thread_id": 7, "checkpoint_id": "cp-1"},
        }
    )

    assert (ctx.application_id, ctx.tenant_id, ctx.graph_id) == ("other-app", "tenant-b", "g2")
    assert str(ctx.run_id) == run_id
    assert (ctx.thread_id, ctx.trace_id, ctx.checkpoint_id) == ("7", "trace-1", "cp-1")
    assert ctx.metadata == {"trace_id": "trace-1", "api_key": REDACTED, "team": "risk"}
    with pytest.raises(ValueError, match="xai_run_id"):
        runtime.context_from_config({"metadata": {"xai_run_id": "not-a-uuid"}})


async def test_run_lifecycle_records_ordered_events_and_final_status() -> None:
    runtime = make_runtime()
    run = await runtime.start_run()
    await runtime.record_state_delta("node", {"a": 1}, {"a": 2}, run=run)
    await runtime.finish_run(run)

    records = await stored(runtime, run_id=run.run_id)

    assert run.execution.status is ExecutionStatus.COMPLETED
    assert [getattr(item, "event_type", "execution") for item in records] == [
        "execution",
        "execution.started",
        "state.transition",
        "execution.completed",
    ]
    assert [item.sequence for item in records[1:]] == [0, 1, 2]


@pytest.mark.parametrize(
    ("error", "cancelled", "status", "exception_type", "message"),
    [
        (ValueError("bad input"), False, ExecutionStatus.FAILED, "ValueError", "bad input"),
        (RuntimeError(), False, ExecutionStatus.FAILED, "RuntimeError", "execution failed"),
        (None, True, ExecutionStatus.CANCELLED, "CancelledError", "execution cancelled"),
        (GeneratorExit(), True, ExecutionStatus.CANCELLED, "GeneratorExit", "execution cancelled"),
    ],
)
async def test_failed_and_cancelled_runs_record_an_exception(
    error, cancelled, status, exception_type, message
) -> None:
    runtime = make_runtime()
    run = await runtime.start_run()

    await runtime.finish_run(run, error, cancelled=cancelled)

    assert run.execution.status is status
    assert run.execution.exceptions[0].exception_type == exception_type
    assert run.execution.exceptions[0].message == message
    assert isinstance(
        (await stored(runtime, item_type=ExecutionFailedEvent))[0], ExecutionFailedEvent
    )


async def test_interrupted_runs_record_one_interaction_per_interrupt() -> None:
    runtime = make_runtime()
    run = await runtime.start_run()
    question = RunInterrupt(id="interrupt-1", value={"question": "approve?", "password": "hunter2"})

    await runtime.finish_run(
        run, interrupts=[question, RunInterrupt(id="interrupt-2", value="raw")]
    )

    first, second = run.execution.human_interactions
    assert run.execution.status is ExecutionStatus.INTERRUPTED
    assert (first.request_reference, second.request_reference) == ("interrupt-1", "interrupt-2")
    assert first.metadata == {"value": {"question": "approve?", "password": REDACTED}}
    assert second.metadata == {"value": "raw"}
    assert len(await stored(runtime, item_type=InterruptEvent)) == 2


async def test_static_breakpoints_record_the_pending_nodes() -> None:
    runtime = make_runtime()
    paused, failed = await runtime.start_run(), await runtime.start_run()

    await runtime.finish_run(paused, pending_nodes=["tools"])
    await runtime.finish_run(failed, ValueError("bad"), pending_nodes=["tools"])

    (interaction,) = paused.execution.human_interactions
    assert paused.execution.status is ExecutionStatus.INTERRUPTED
    assert interaction.request_reference is None
    assert interaction.metadata == {"pending_nodes": ["tools"]}
    assert failed.execution.status is ExecutionStatus.FAILED
    assert failed.execution.human_interactions == []


async def test_continuation_links_the_resumed_run_but_never_itself() -> None:
    runtime = make_runtime()
    first = await runtime.start_run()
    own_id = str(first.run_id)

    resumed = await runtime.start_run(continuation_of=first.run_id)
    rerun = await runtime.start_run(
        {"metadata": {"xai_run_id": own_id}}, continuation_of=first.run_id
    )

    assert resumed.execution.continuation_of == first.run_id
    assert rerun.run_id == first.run_id
    assert rerun.execution.continuation_of is None


async def test_records_made_after_a_run_finishes_keep_the_stored_execution_current() -> None:
    class CountingStore(InMemoryProvenanceStore):
        execution_writes = 0

        async def write(self, item) -> None:
            self.execution_writes += isinstance(item, Execution)
            await super().write(item)

    store = CountingStore()
    registry = Registry()
    registry.register(ProvenanceStore, store)
    runtime = XAIRuntime(registry=registry)
    run = await runtime.start_run()
    await runtime.record_tool("search", run=run)
    await runtime.finish_run(run, interrupts=[RunInterrupt(id="i-1", value="approve?")])

    assert store.execution_writes == 2
    approval = await runtime.record_human_interaction("approval", actor_reference="lead", run=run)

    assert store.execution_writes == 3
    (saved,) = await executions(runtime)
    assert saved.status is ExecutionStatus.INTERRUPTED
    assert saved.human_interactions[-1] == approval


@pytest.mark.parametrize(
    ("mode", "fields", "expected"),
    [
        (CaptureMode.DELTA, (), [("changed", 1, 2), ("removed", 3, None), ("added", None, "new")]),
        (
            CaptureMode.FULL,
            (),
            [
                ("changed", 1, 2),
                ("same", "x", "x"),
                ("removed", 3, None),
                ("password", REDACTED, REDACTED),
                ("added", None, "new"),
            ],
        ),
        (CaptureMode.SELECTIVE, ("changed", "same"), [("changed", 1, 2)]),
    ],
)
async def test_capture_modes_select_changes(mode, fields, expected) -> None:
    runtime = make_runtime(capture_state=mode, capture_fields=frozenset(fields))
    run = await runtime.start_run()

    transition = await runtime.record_state_delta(
        "node",
        {"changed": 1, "same": "x", "removed": 3, "password": "a"},
        {"changed": 2, "same": "x", "password": "b", "added": "new"},
        metadata={"step": 1},
        run=run,
    )

    assert transition is not None
    assert [(c.path, c.before, c.after) for c in transition.changes] == expected
    assert transition.capture_mode is mode
    assert transition.metadata == {"step": 1}


async def test_no_transition_is_recorded_when_nothing_is_selected() -> None:
    runtime = make_runtime()
    run = await runtime.start_run()

    assert await runtime.record_state_delta("node", {"a": 1}, {"a": 1}, run=run) is None
    assert await runtime.record_state_delta("node", None, None, run=run) is None
    assert await make_runtime(capture_state="none").record_state_delta("n", {}, {"a": 1}) is None
    assert await runtime.record_state_delta("node", {}, {"a": 1}) is None
    assert run.execution.state_transitions == []


async def test_unequal_raw_values_with_equal_captures_are_not_changes() -> None:
    class Opaque:
        def __eq__(self, other: object) -> bool:
            raise TypeError("cannot compare")

        __hash__ = object.__hash__

        def __repr__(self) -> str:
            return "Opaque()"

    runtime = make_runtime()
    run = await runtime.start_run()

    nan_change = await runtime.record_state_delta(
        "node", {"value": float("nan")}, {"value": float("nan")}, run=run
    )
    opaque_change = await runtime.record_state_delta(
        "node", {"value": Opaque()}, {"value": Opaque()}, run=run
    )

    assert nan_change is None
    assert opaque_change is None


async def test_custom_capture_uses_the_callable_and_honors_failure_modes() -> None:
    with pytest.raises(ValueError, match="custom_state_capture"):
        XAIRuntime(config=XAIConfig(capture_state=CaptureMode.CUSTOM))

    runtime = XAIRuntime(
        config=XAIConfig(capture_state=CaptureMode.CUSTOM),
        custom_state_capture=lambda before, after: {"score": after["score"]},
    )
    run = await runtime.start_run()
    transition = await runtime.record_state_delta(
        "n", {"score": 1, "ssn": "x"}, {"score": 2, "ssn": "y"}, run=run
    )
    assert transition is not None
    assert [(c.path, c.before, c.after) for c in transition.changes] == [("score", 1, 2)]

    def broken(before, after):
        raise KeyError("missing")

    open_runtime = XAIRuntime(
        config=XAIConfig(capture_state=CaptureMode.CUSTOM), custom_state_capture=broken
    )
    open_run = await open_runtime.start_run()
    assert await open_runtime.record_state_delta("n", {}, {}, run=open_run) is None
    assert isinstance(open_runtime.errors[-1], KeyError)

    closed_runtime = XAIRuntime(
        config=XAIConfig(capture_state=CaptureMode.CUSTOM, failure_mode=FailureMode.FAIL_CLOSED),
        custom_state_capture=broken,
    )
    closed_run = await closed_runtime.start_run()
    with pytest.raises(XAIInstrumentationError, match="KeyError"):
        await closed_runtime.record_state_delta("n", {}, {}, run=closed_run)

    closed_runtime.custom_state_capture = None
    with pytest.raises(ValueError, match="custom_state_capture"):
        await closed_runtime.record_state_delta("n", {}, {}, run=closed_run)


async def test_recording_apis_build_canonical_artifacts() -> None:
    plugin = RecordingPlugin()
    runtime = XAIRuntime(plugins=(plugin,))
    run = await runtime.start_run()
    started = datetime.now(UTC)

    evidence = await runtime.record_evidence(
        "tool_result",
        summary="score",
        content_reference="fraud://1",
        source=SourceReference(source_id="fraud", source_type="service"),
        confidence=0.9,
        quality=0.8,
        metadata={"token": "t"},
        run=run,
    )
    decision = await runtime.record_decision(
        "HUMAN_REVIEW",
        decision_type="routing",
        candidate_actions=["AUTO", "HUMAN_REVIEW"],
        evidence_ids=[evidence.id],
        provenance_ids=[evidence.id],
        factors=[DecisionFactor(name="risk", value=0.9)],
        policy_references=["policy-7"],
        confidence=0.8,
        uncertainty=0.1,
        run=run,
    )
    tool = await runtime.record_tool("search", status=ToolStatus.TIMED_OUT, latency_ms=3, run=run)
    retrieval = await runtime.record_retrieval(
        "docs", documents=[RetrievedDocument(document_id="d1")], reranker="bm25", run=run
    )
    memory = await runtime.record_memory("m1", MemoryOperation.READ, namespace="users", run=run)
    link = await runtime.record_provenance("raw", evidence.id, "DERIVED_FROM", run=run)
    node = await runtime.record_node(
        "node", status=ExecutionStatus.COMPLETED, started_at=started, attempt=2, run=run
    )
    interaction = await runtime.record_human_interaction(
        "approval", actor_reference="reviewer-1", run=run
    )

    assert evidence.quality == 0.8
    assert evidence.metadata == {"token": REDACTED}
    assert decision.policy_references == ["policy-7"]
    assert decision.uncertainty == 0.1
    assert run.evidence == [evidence]
    assert run.decisions == [decision]
    assert plugin.artifacts == [evidence, decision, memory]
    assert run.execution.tools == [tool]
    assert run.execution.retrievals == [retrieval]
    assert run.execution.memory == [memory]
    assert run.execution.nodes == [node]
    assert node.ended_at is not None
    assert node.attempt == 2
    assert run.execution.human_interactions == [interaction]
    store = runtime.registry.require(ProvenanceStore)
    assert await store.get(str(link.id), context=link.context) == link
    assert len(await stored(runtime, item_type=NodeExecutionEvent)) == 1


async def test_nested_values_supplied_by_the_caller_are_redacted() -> None:
    runtime = make_runtime()
    run = await runtime.start_run()

    evidence = await runtime.record_evidence(
        "tool_result",
        source=SourceReference(
            source_id="crm", source_type="api", metadata={"authorization": "Bearer x"}
        ),
        run=run,
    )
    decision = await runtime.record_decision(
        "ESCALATE",
        factors=[
            DecisionFactor(name="api_key", value="sk-live"),
            DecisionFactor(name="limits", value={"token": "t", "max": 3}, metadata={"dsn": "pg"}),
        ],
        run=run,
    )
    retrieval = await runtime.record_retrieval(
        "kb",
        documents=[RetrievedDocument(document_id="d1", metadata={"cookie": "c", "lang": "en"})],
        run=run,
    )

    assert evidence.source is not None
    assert evidence.source.metadata == {"authorization": REDACTED}
    secret, limits = decision.factors
    assert secret.value == REDACTED
    assert limits.value == {"token": REDACTED, "max": 3}
    assert limits.metadata == {"dsn": REDACTED}
    assert retrieval.documents[0].metadata == {"cookie": REDACTED, "lang": "en"}


async def test_recording_requires_a_run() -> None:
    runtime = make_runtime()

    with pytest.raises(RuntimeError, match="no active run"):
        await runtime.record_evidence("rule")
    with pytest.raises(RuntimeError, match="no active run"):
        await runtime.record_node(
            "n", status=ExecutionStatus.COMPLETED, started_at=datetime.now(UTC)
        )


async def test_record_artifact_validates_the_run() -> None:
    runtime = make_runtime()
    run = await runtime.start_run()
    own = Evidence(evidence_type="rule", context=run.execution.context)
    foreign = Evidence(evidence_type="rule", context=execution().context)

    assert await runtime.record_artifact(own, run=run) is own
    with pytest.raises(ValueError, match="does not match"):
        await runtime.record_artifact(foreign, run=run)


async def test_capture_policy_can_drop_events() -> None:
    class DenyTransitions(CapturePolicy):
        async def evaluate(self, event) -> PolicyDecision:
            return PolicyDecision(
                context=event.context,
                policy_id="deny",
                action=PolicyAction.CAPTURE,
                allowed=not isinstance(event, StateTransitionEvent),
            )

    runtime = make_runtime()
    observer = RecordingObservability()
    runtime.register(CapturePolicy, DenyTransitions())
    runtime.register(ObservabilityProvider, observer)
    run = await runtime.start_run()

    assert await runtime.record_state_delta("n", {"a": 1}, {"a": 2}, run=run) is not None
    await runtime.finish_run(run)

    assert run.execution.state_transitions == []
    assert (await executions(runtime))[0].state_transitions == []
    assert await stored(runtime, item_type=StateTransitionEvent) == []
    assert [event.event_type for event in observer.events] == [
        "execution.started",
        "execution.completed",
    ]


async def test_events_whose_capture_policy_fails_are_not_captured() -> None:
    class BrokenPolicy(CapturePolicy):
        async def evaluate(self, event) -> PolicyDecision:
            raise RuntimeError("policy backend unavailable")

    runtime = make_runtime()
    runtime.register(CapturePolicy, BrokenPolicy())
    run = await runtime.start_run()

    await runtime.record_tool("search", run=run)

    assert run.execution.tools == []
    assert await stored(runtime, item_type=ToolExecutionEvent) == []
    assert all(isinstance(error, RuntimeError) for error in runtime.errors)


async def test_fail_open_records_errors_without_interrupting(
    caplog: pytest.LogCaptureFixture,
) -> None:
    runtime = make_runtime()
    runtime.register(ProvenanceStore, FailingStore())

    with caplog.at_level(logging.WARNING, logger="agxai"):
        run = await runtime.start_run()
        await runtime.finish_run(run)

    assert run.execution.status is ExecutionStatus.COMPLETED
    assert len(runtime.errors) == 4
    assert all(isinstance(error, OSError) for error in runtime.errors)
    failures = [record for record in caplog.records if record.name == "agxai.runtime.runtime"]
    assert len(failures) == 4
    assert all(record.levelno == logging.WARNING for record in failures)
    assert all(record.exc_info and record.exc_info[0] is OSError for record in failures)
    assert "fail-open" in failures[0].getMessage()


async def test_fail_closed_raises_without_also_logging(caplog: pytest.LogCaptureFixture) -> None:
    runtime = make_runtime(failure_mode=FailureMode.FAIL_CLOSED)
    runtime.register(ProvenanceStore, FailingStore())

    with caplog.at_level(logging.DEBUG, logger="agxai"), pytest.raises(XAIInstrumentationError):
        await runtime.start_run()

    assert len(runtime.errors) == 1
    assert [record for record in caplog.records if record.name.startswith("agxai")] == []


def test_the_package_logger_has_a_null_handler() -> None:
    assert any(
        isinstance(handler, logging.NullHandler) for handler in logging.getLogger("agxai").handlers
    )


async def test_error_history_is_bounded() -> None:
    runtime = make_runtime()
    runtime.register(ProvenanceStore, FailingStore())
    run = await runtime.start_run()

    for _ in range(120):
        await runtime.record_provenance("a", "b", "r", run=run)

    assert len(runtime.errors) == 100


async def test_fail_closed_raises_with_the_cause() -> None:
    runtime = make_runtime(failure_mode="fail_closed")
    runtime.register(ProvenanceStore, FailingStore(ConnectionError("db down")))

    with pytest.raises(XAIInstrumentationError, match="ConnectionError: db down") as raised:
        await runtime.start_run()

    assert isinstance(raised.value.__cause__, ConnectionError)
    assert runtime.errors == (raised.value.__cause__,)


async def test_strict_mode_requires_sinks_and_plugins() -> None:
    runtime = make_runtime(failure_mode="strict")
    run = await runtime.start_run()

    with pytest.raises(XAIInstrumentationError, match="plugin"):
        await runtime.record_evidence("rule", run=run)
    assert run.artifacts == []

    runtime.plugins.add(RecordingPlugin())
    assert await runtime.record_evidence("rule", run=run)

    runtime.registry.remove(ProvenanceStore)
    await runtime.record_provenance("a", "b", "r", run=run)
    runtime.registry.remove(ObservabilityProvider)
    with pytest.raises(XAIInstrumentationError, match="sink"):
        await runtime.record_provenance("a", "b", "r", run=run)

    lenient = make_runtime()
    lenient.registry.remove(ProvenanceStore)
    lenient.registry.remove(ObservabilityProvider)
    lenient.registry.remove(CapturePolicy)
    assert await lenient.start_run()


async def test_explain_assembles_attribution_policy_and_engine_output() -> None:
    runtime = make_runtime()

    explanation = await runtime.explain(explanation_context(audience="auditor"))

    assert explanation.audience == "auditor"
    assert explanation.summary == "The routing decision selected 'HUMAN_REVIEW'."
    assert explanation.contributing_factors
    assert explanation.disclosure == ["Private memory and raw content are withheld by default."]


async def test_explain_reuses_supplied_attribution() -> None:
    runtime = make_runtime()
    calls: list[str] = []

    class CountingAttribution(AttributionEngine):
        async def attribute(self, context):
            calls.append("attribute")
            raise AssertionError("must not be called")

    runtime.register(AttributionEngine, CountingAttribution())
    context_ = explanation_context()
    attribution = await XAIRuntime().attribute(context_)

    await runtime.explain(context_.model_copy(update={"attribution": attribution}))

    assert calls == []


async def test_llm_gate_fails_fast_before_any_policy_or_model_work() -> None:
    runtime = make_runtime()
    evaluated: list[str] = []

    class RecordingPolicy(PolicyProvider):
        async def evaluate(self, context, action):
            evaluated.append(action)
            raise AssertionError("must not be called")

    runtime.register(PolicyProvider, RecordingPolicy())
    runtime.register(ExplanationEngine, LLMExplanationEngine(enabled=True))

    with pytest.raises(XAIInstrumentationError, match="disabled in XAIConfig"):
        await runtime.explain(explanation_context())
    assert evaluated == []


@pytest.mark.parametrize("failing", ["policy", "attribution", "engine"])
async def test_explain_never_returns_an_unfiltered_or_partial_explanation(failing: str) -> None:
    runtime = make_runtime()

    class Broken(PolicyProvider, AttributionEngine, ExplanationEngine):
        async def evaluate(self, context, action):
            raise ConnectionError("policy service down")

        async def attribute(self, context):
            raise ConnectionError("attribution down")

        async def explain(self, context):
            raise ConnectionError("engine down")

    capability = {
        "policy": PolicyProvider,
        "attribution": AttributionEngine,
        "engine": ExplanationEngine,
    }[failing]
    runtime.register(capability, Broken())

    with pytest.raises(XAIInstrumentationError, match=r"see XAIRuntime\.errors"):
        await runtime.explain(explanation_context())
    assert isinstance(runtime.errors[-1], ConnectionError)


async def test_explain_decision_uses_the_run_and_its_referenced_evidence() -> None:
    runtime = make_runtime()
    run = await runtime.start_run()
    used = await runtime.record_evidence("tool_result", summary="used", run=run)
    await runtime.record_evidence("tool_result", summary="unrelated", run=run)
    decision = await runtime.record_decision(
        "APPROVE",
        decision_type="approval",
        factors=[DecisionFactor(name="score", value=1, evidence_ids=[used.id])],
        run=run,
    )
    unreferenced = await runtime.record_decision("ESCALATE", run=run)

    explanation = await runtime.explain_decision(decision, audience="end_user", run=run)
    fallback = await runtime.explain_decision(unreferenced, run=run)

    assert explanation.audience == "end_user"
    assert explanation.summary == "The approval decision selected 'APPROVE'."
    assert [str(item.factor_id) for item in explanation.contributing_factors] == [
        str(used.id),
        "score",
    ]
    assert len([c for c in fallback.contributing_factors if c.factor_type == "tool_result"]) == 2

    other = await runtime.start_run()
    with pytest.raises(ValueError, match="does not belong"):
        await runtime.explain_decision(decision, run=other)


async def test_collect_runs_follows_the_context() -> None:
    runtime, other = make_runtime(), make_runtime()

    with runtime.collect_runs() as outer:
        first = await runtime.start_run()
        with runtime.collect_runs() as inner:
            nested = await runtime.start_run()
        spawned = await asyncio.gather(runtime.start_run(), runtime.start_run())
        await other.start_run()
    after = await runtime.start_run()

    assert inner == [nested]
    assert outer == [first, *spawned]
    assert after not in outer


async def test_close_is_idempotent_attempts_every_step_and_rejects_new_runs() -> None:
    observer = RecordingObservability(fail=True)
    plugin = RecordingPlugin(fail=True)
    runtime = XAIRuntime(config=XAIConfig(failure_mode="fail_closed"), plugins=(plugin,))
    runtime.register(ObservabilityProvider, observer)

    with pytest.raises(XAIInstrumentationError, match="ConnectionError"):
        await runtime.close()
    await runtime.close()

    assert (observer.flushed, observer.closed) == (1, 1)
    assert plugin.log == ["plugin.flush", "plugin.close"]
    assert len(runtime.errors) == 4
    with pytest.raises(RuntimeError, match="closed"):
        await runtime.start_run()


async def test_flush_reaches_observability_and_plugins() -> None:
    observer, plugin = RecordingObservability(), RecordingPlugin()
    runtime = XAIRuntime(plugins=(plugin,))
    runtime.register(ObservabilityProvider, observer)

    await runtime.flush()
    await runtime.close()

    assert observer.flushed == 2
    assert observer.closed == 1
    assert plugin.log == ["plugin.flush", "plugin.flush", "plugin.close"]
    assert runtime.errors == ()


async def test_lifecycle_calls_skip_unregistered_capabilities() -> None:
    runtime = make_runtime()
    runtime.registry.remove(ObservabilityProvider)
    runtime.registry.remove(ProvenanceStore)

    await runtime.flush()
    await runtime.close()

    assert runtime.errors == ()


async def test_slow_operations_time_out_and_concurrency_is_bounded() -> None:
    observer = RecordingObservability(delay=0.2)
    runtime = make_runtime(operation_timeout_seconds=0.05)
    runtime.register(ObservabilityProvider, observer)

    await runtime.start_run()

    assert isinstance(runtime.errors[-1], TimeoutError)

    bounded = make_runtime(max_concurrency=1, operation_timeout_seconds=0.05)
    await bounded._slots.acquire()
    try:
        await bounded.record_provenance("a", "b", "r", run=detached_run(bounded))
    finally:
        bounded._slots.release()
    assert any("instrumentation slot" in str(error) for error in bounded.errors)
    assert bounded._slots._free == 1


def detached_run(runtime: XAIRuntime) -> Run:
    return Run(execution(runtime.context_from_config()))


async def test_cancellation_is_never_swallowed() -> None:
    class Hanging(RecordingObservability):
        async def emit(self, event) -> None:
            await asyncio.sleep(10)

    runtime = make_runtime()
    runtime.register(ObservabilityProvider, Hanging())
    task = asyncio.ensure_future(runtime.start_run())
    await asyncio.sleep(0.05)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
    assert runtime.errors == ()
    assert runtime._slots._free == runtime.config.max_concurrency


async def test_slot_waiters_are_woken_in_order_as_soon_as_a_slot_frees() -> None:
    slots = runtime_module._Slots(1)
    order: list[int] = []
    await slots.acquire()

    async def wait_turn(index: int) -> None:
        await slots.acquire()
        order.append(index)
        slots.release()

    waiters = [asyncio.ensure_future(wait_turn(index)) for index in range(3)]
    await asyncio.sleep(0)
    slots.release()
    await asyncio.wait_for(asyncio.gather(*waiters), timeout=1)

    assert order == [0, 1, 2]
    assert slots._free == 1


async def test_a_slot_released_on_another_loop_wakes_the_waiter() -> None:
    slots = runtime_module._Slots(1)
    await slots.acquire()
    waiter = asyncio.ensure_future(slots.acquire())
    await asyncio.sleep(0)

    await asyncio.to_thread(asyncio.run, _release_later(slots))
    await asyncio.wait_for(waiter, timeout=1)

    assert slots._free == 0
    slots.release()
    assert slots._free == 1


async def _release_later(slots) -> None:
    slots.release()


async def test_waiters_that_give_up_never_leak_a_slot() -> None:
    slots = runtime_module._Slots(1)
    await slots.acquire()
    timed_out = asyncio.ensure_future(asyncio.wait_for(slots.acquire(), timeout=0.01))
    granted_then_cancelled = asyncio.ensure_future(slots.acquire())
    await asyncio.sleep(0)

    with pytest.raises(TimeoutError):
        await timed_out  # gave up while queued
    slots.release()
    await asyncio.sleep(0)  # the grant runs, but the waiter has not resumed yet
    granted_then_cancelled.cancel()
    with pytest.raises(asyncio.CancelledError):
        await granted_then_cancelled

    assert slots._free == 1


async def test_a_slot_granted_after_its_waiter_gave_up_is_released_again() -> None:
    slots = runtime_module._Slots(1)
    await slots.acquire()
    waiter = asyncio.ensure_future(slots.acquire())
    await asyncio.sleep(0)

    slots.release()  # schedules the grant
    waiter.cancel()  # cancelled before the grant runs
    with pytest.raises(asyncio.CancelledError):
        await waiter
    await asyncio.sleep(0)

    assert slots._free == 1


async def test_waiters_on_closed_loops_are_skipped() -> None:
    slots = runtime_module._Slots(1)
    await slots.acquire()
    closed = asyncio.new_event_loop()
    closed.close()
    slots._waiters.append((closed, closed.create_future()))

    slots.release()

    assert slots._free == 1


@given(
    before=st.dictionaries(st.sampled_from("abcdef"), st.integers(0, 3), max_size=6),
    update=st.dictionaries(st.sampled_from("abcdef"), st.integers(0, 3), max_size=6),
)
async def test_delta_capture_records_exactly_the_changed_keys(before, update) -> None:
    runtime = make_runtime()
    run = await runtime.start_run()
    after = {**before, **update}

    transition = await runtime.record_state_delta("node", before, after, run=run)

    changed = {key for key in after if before.get(key) != after[key]}
    recorded = set() if transition is None else {change.path for change in transition.changes}
    assert recorded == changed
    if transition is not None:
        for change in transition.changes:
            assert (change.before, change.after) == (before.get(change.path), after[change.path])


def test_node_execution_requires_aware_times() -> None:
    with pytest.raises(ValueError, match="timezone"):
        NodeExecution(
            context=execution().context,
            node_id="n",
            status=ExecutionStatus.COMPLETED,
            started_at=datetime(2026, 1, 1),  # noqa: DTZ001 - deliberately naive
        )


@given(async_records=st.integers(0, 8), thread_records=st.integers(0, 4))
async def test_event_sequences_stay_contiguous_under_concurrent_recording(
    async_records: int, thread_records: int
) -> None:
    runtime = make_runtime()
    run = await runtime.start_run()

    def record_in_thread(index: int) -> None:
        runtime.run_sync(runtime.record_tool(f"thread-{index}", run=run))

    await asyncio.gather(
        *(runtime.record_tool(f"task-{index}", run=run) for index in range(async_records)),
        *(asyncio.to_thread(record_in_thread, index) for index in range(thread_records)),
    )
    await runtime.finish_run(run)

    events = [
        item for item in await stored(runtime, run_id=run.run_id) if hasattr(item, "sequence")
    ]
    assert sorted(event.sequence for event in events) == list(
        range(2 + async_records + thread_records)
    )


keys = st.sampled_from(["a", "b", "c", "d", "token"])
states = st.dictionaries(keys, st.integers(0, 3), max_size=5)


@given(before=states, update=states, fields=st.frozensets(keys, max_size=5))
async def test_selective_capture_records_only_changed_named_fields(before, update, fields) -> None:
    runtime = make_runtime(capture_state=CaptureMode.SELECTIVE, capture_fields=fields)
    run = await runtime.start_run()
    after = {**before, **update}

    transition = await runtime.record_state_delta("node", before, after, run=run)

    expected = {
        key for key in after if key in fields and key != "token" and before.get(key) != after[key]
    }
    recorded = set() if transition is None else {change.path for change in transition.changes}
    assert recorded == expected


@given(before=states, after=states, chosen=st.frozensets(keys, max_size=5))
async def test_custom_capture_records_what_the_selector_returns_when_it_changed(
    before, after, chosen
) -> None:
    def select(old: Mapping[str, Any], new: Mapping[str, Any]) -> dict[str, Any]:
        return {key: new.get(key, -1) for key in chosen}

    runtime = XAIRuntime(
        config=XAIConfig(capture_state=CaptureMode.CUSTOM), custom_state_capture=select
    )
    run = await runtime.start_run()

    transition = await runtime.record_state_delta("node", before, after, run=run)

    selected = select(before, after)
    expected = {
        key: (before.get(key), value)
        for key, value in selected.items()
        if key != "token" and before.get(key) != value
    }
    recorded = (
        {}
        if transition is None
        else {change.path: (change.before, change.after) for change in transition.changes}
    )
    assert recorded == expected
