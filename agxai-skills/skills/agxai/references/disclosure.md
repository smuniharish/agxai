# Disclosure and explanations

Read this file when audiences must see different explanations, or when a model should phrase them. Copy `assets/test_disclosure_policy.py` into the project's tests and adapt it.

## Different explanations per audience

A `PolicyProvider` decides which explanation sections each audience may see.
Withheld sections are announced in `explanation.disclosure`.

```python
from agxai import (
    Audience,
    ExplanationContext,
    PolicyAction,
    PolicyDecision,
    PolicyProvider,
)


class CustomerSafePolicy(PolicyProvider):
    """End users see the outcome and reasons; other audiences see everything."""

    async def evaluate(self, context: ExplanationContext, action: PolicyAction) -> PolicyDecision:
        end_user = context.audience == Audience.END_USER
        return PolicyDecision(
            context=context.execution.context,
            policy_id="customer-safe",
            action=action,
            allowed=True,
            audience=context.audience,
            denied_fields={"contributing_factors", "supporting_evidence"} if end_user else set(),
            reason="Customers receive the outcome and reasons only." if end_user else None,
        )


runtime.register(PolicyProvider, CustomerSafePolicy())
```

- Withholding `contributing_factors` also removes factor values from
  `reasons`.
- `allowed_fields`, when non-empty, is an allowlist of sections.
- Test every audience, and check the serialized explanation for values that
  must never appear. Start from `assets/test_disclosure_policy.py`.

## LLM-phrased explanations

The structured engine is deterministic and needs no model. To have a model
phrase the explanation, both opt-ins are required:

```python
from agxai import ExplanationEngine, LLMExplanationEngine, XAIConfig, XAIRuntime

runtime = XAIRuntime(XAIConfig(llm_explanation_enabled=True, operation_timeout_seconds=60))
runtime.register(ExplanationEngine, LLMExplanationEngine(model, enabled=True, timeout=45))
```

The model receives only the policy-filtered record and is told which sections
were withheld. Its reply is validated; an invalid or late reply raises
`XAIInstrumentationError`, so keep a structured fallback for that case.
