"""Run agxai's store conformance suite against your store.

Copy this file next to your store and change the import. `make_store` must
return a new, empty store for every test: for a database, connect and truncate
the table here. Each failing test names the promise the store breaks.
"""

from __future__ import annotations

from store_template import TableProvenanceStore

from agxai.testing import ProvenanceStoreContract


class TestTableProvenanceStore(ProvenanceStoreContract):
    async def make_store(self) -> TableProvenanceStore:
        return TableProvenanceStore()
