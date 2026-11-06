# Human-in-the-loop

Read this file when a graph uses `interrupt`, `Command(resume=...)`, breakpoints, or approvals made outside the graph.

## Interrupt and resume

Compile with a checkpointer and pass a `thread_id`. Nothing else is needed to
record interrupts, answers, checkpoints, and the link between the runs:

```python
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command, interrupt


def human_review(state: WireTransfer) -> WireTransfer:
    approved = interrupt({"question": "Approve this wire transfer?", "amount": state["amount"]})
    return {"approved": bool(approved)}


graph = runtime.instrument(builder.compile(checkpointer=InMemorySaver()))
thread = {"configurable": {"thread_id": "wire-42"}}

with runtime.collect_runs() as runs:
    await graph.ainvoke({"amount": 9000.0}, thread)  # run 1: interrupted
    await graph.ainvoke(Command(resume=True), thread)  # run 2: completed
paused, resumed = runs
assert resumed.execution.continuation_of == paused.run_id

await runtime.record_human_interaction(
    HumanInteractionType.APPROVAL, actor_reference="reviewer:ana", run=resumed
)
```

- The paused run has an `interrupt` interaction with the payload in
  `metadata["value"]`; the resumed run has a `resume` interaction with the
  answer and the same interrupt ID in `request_reference`.
- Each run records the checkpoint it continued from (`restored=True`) and the
  last checkpoint it wrote. Load one with
  `graph.aget_state({"configurable": {"thread_id": ..., "checkpoint_id": ...}})`.
- Retries after a failure and replays from a past checkpoint are linked the
  same way. Static breakpoints are recorded as interrupts with
  `pending_nodes`.
- Use a durable checkpointer (PostgreSQL or SQLite saver) in production, so
  links survive restarts.
- Do not also call `record_checkpoint` for these graphs; each checkpoint would
  be recorded twice. It is for runs you manage yourself, or for
  `XAIConfig(capture_checkpoints=False)`.
- Record approvals made outside the graph with `record_human_interaction`,
  passing `run=`; it works even after the run finished.
