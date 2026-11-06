# Testing

`agxai.testing` holds conformance tests for your own extensions. Subclass
`ProvenanceStoreContract` in a test module and return a new, empty store from
`make_store`; pytest then runs one test per promise in the
[store contract](../architecture/storage.md#testing-a-store).

```python
from agxai.testing import ProvenanceStoreContract


class TestMyDatabaseStore(ProvenanceStoreContract):
    async def make_store(self):
        return await MyDatabaseStore.open(TEST_DSN)
```

::: agxai.testing.ProvenanceStoreContract
