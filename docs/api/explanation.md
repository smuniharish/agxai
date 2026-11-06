# Explanation engines

Engines that render an `Explanation` from a policy-filtered
`ExplanationContext`. The structured engine is the default. See
[Explanations](../concepts/explanations.md) and
[LLM-phrased explanations](../how-to/llm-explanations.md).

```python
from agxai import ExplanationEngine, LLMExplanationEngine, XAIConfig, XAIRuntime

runtime = XAIRuntime(XAIConfig(llm_explanation_enabled=True))
runtime.register(ExplanationEngine, LLMExplanationEngine(chat_model, enabled=True))
```

::: agxai.explanation.engines.StructuredExplanationEngine

::: agxai.explanation.engines.LLMExplanationEngine

::: agxai.explanation.engines.ExplanationDraft
