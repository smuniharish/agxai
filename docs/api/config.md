# Configuration

`XAIConfig` holds the settings of one runtime. It is immutable and never reads
environment variables. See [Configuration](../getting-started/configuration.md)
for guidance and real examples of each capture mode.

```python
from agxai import CaptureMode, FailureMode, XAIConfig, XAIRuntime

runtime = XAIRuntime(
    XAIConfig(capture_state=CaptureMode.DELTA, failure_mode=FailureMode.FAIL_CLOSED)
)
```

::: agxai.config.XAIConfig
