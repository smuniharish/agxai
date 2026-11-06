# Plugins

Plugins receive every semantic record (evidence, decisions, memory references,
and anything passed to `record_artifact`) as it is created. A plugin subclasses
`XAIPlugin` and implements `record`. See
[Extensibility](../architecture/plugins.md#plugins) for an example.

```python
from agxai import XAIRuntime

runtime = XAIRuntime(plugins=(MyArchive(),))
```

::: agxai.plugins.base.XAIPlugin

::: agxai.plugins.manager.PluginManager
