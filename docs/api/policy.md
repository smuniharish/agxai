# Policies

The default capture and exposure policies, and the redaction helpers applied to
every free-form value. See [Policies](../concepts/policies.md) for how they fit
together and how to write your own.

```python
from agxai.policy import REDACTED, is_sensitive_key, sanitize_value

assert is_sensitive_key("x-api-key")
assert sanitize_value({"Authorization": "Bearer abc"}) == {"Authorization": REDACTED}
```

## Default policies

::: agxai.policy.defaults.DefaultCapturePolicy

::: agxai.policy.defaults.DefaultPolicyProvider

## Redaction

::: agxai.policy.defaults.sanitize_value

::: agxai.policy.defaults.sanitize_mapping

::: agxai.policy.defaults.is_sensitive_key

::: agxai.policy.defaults.REDACTED
