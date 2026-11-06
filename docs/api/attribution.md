# Attribution engines

Deterministic engines that score how much each decision factor and piece of
evidence contributed to a decision. `HybridAttribution` is the default. See
[Attribution](../concepts/attribution.md) for a worked example.

```python
from agxai import AttributionEngine, HybridAttribution, RuleBasedAttribution

runtime.register(
    AttributionEngine,
    HybridAttribution(
        rule_based=RuleBasedAttribution(rules={"customer_tenure_years": -0.3}),
        rule_weight=0.7,
        evidence_weight=0.3,
    ),
)
```

::: agxai.attribution.engines.HybridAttribution

::: agxai.attribution.engines.RuleBasedAttribution

::: agxai.attribution.engines.EvidenceAttribution
