# Provenance

Provenance links form a directed graph from source entities to the entities
derived from them. This page describes how that graph is stored and walked.
[Concepts: Provenance](../guide/concepts/provenance.md) covers how to record it.

## Identity

`source_id` and `target_id` are entity IDs: the UUID of a recorded artifact,
such as evidence or a decision, or any string that identifies an external
entity, such as a URI or a database key. UUIDs and their string forms refer to
the same entity, so `store.lineage(str(decision.id), ...)` finds links recorded
with `decision.id`.

Each link is itself a record with its own `id`, timestamp, and
`ExecutionContext`. It is stored like any other record and is scoped to the run
that recorded it.

## Walking lineage

`lineage(entity_id, context=..., max_depth=100)` returns upstream links
breadth-first, nearest first, up to the requested depth. Each link appears
once and cycles terminate. The inherited implementation uses the store's
`parents` method; stores can override it with a native query while preserving
these semantics.

## Scoping

Provenance queries are scoped to the application, tenant, and run of the
`context` you pass. Two consequences follow:

- **Isolation.** A tenant can never walk into another tenant's lineage, even
  when entity IDs collide.
- **Per-run lineage.** A link recorded in one run is not visible from another.
  To trace an entity across runs, record the cross-run link in the run that
  uses the entity, or query each run's context in turn.
