# Framework integrations

The abstract base class is available without any framework installed:

```python
from agxai import FrameworkInstrumentor
```

## FrameworkInstrumentor

::: agxai.integrations.base.FrameworkInstrumentor

## LangGraphInstrumentor

Requires `pip install "agxai[langgraph]"`. Import this integration explicitly;
it is not loaded by `import agxai`.

::: agxai.integrations.langgraph.LangGraphInstrumentor

## InstrumentedGraph

::: agxai.integrations.langgraph.graph.InstrumentedGraph

## InterruptLike

::: agxai.core.protocols.InterruptLike
