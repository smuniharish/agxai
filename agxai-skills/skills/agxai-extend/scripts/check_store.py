"""Check a ProvenanceStore against agxai's conformance contract, without pytest.

Imports a store factory, runs every test of `agxai.testing.ProvenanceStoreContract`
against a new store from it, and reports one line per promise:

    python scripts/check_store.py myapp.storage:make_store
    python scripts/check_store.py myapp.storage:DatabaseStore --json

The factory is a class or a callable, sync or async, that takes no arguments
and returns a new, empty store. Run it from the project root, or pass --path.

Exit codes: 0 every promise holds, 1 a promise is broken, 2 the factory
cannot be imported or is not a store factory.
"""

from __future__ import annotations

import argparse
import inspect
import json
import sys
import traceback
from importlib import import_module
from pathlib import Path
from typing import Any


def load_factory(spec: str) -> Any:
    module_name, separator, attribute = spec.partition(":")
    if not separator or not module_name or not attribute:
        raise ValueError(f"expected MODULE:FACTORY, got {spec!r}")
    target: Any = import_module(module_name)
    for part in attribute.split("."):
        target = getattr(target, part)
    if not callable(target):
        raise TypeError(f"{spec} is not callable")
    return target


def contract_for(factory: Any) -> type:
    from agxai import ProvenanceStore
    from agxai.testing import ProvenanceStoreContract

    class Contract(ProvenanceStoreContract):
        async def make_store(self) -> ProvenanceStore:
            store = factory()
            if inspect.isawaitable(store):
                store = await store
            if not isinstance(store, ProvenanceStore):
                raise TypeError(
                    f"the factory returned {type(store).__name__}, not a ProvenanceStore"
                )
            return store

    return Contract


def run_contract(factory: Any) -> list[dict[str, Any]]:
    contract = contract_for(factory)
    results = []
    for name in sorted(name for name in dir(contract) if name.startswith("test_")):
        try:
            getattr(contract(), name)()
        except AssertionError as error:
            results.append({"test": name, "passed": False, "error": str(error)})
        except Exception as error:  # report every broken promise, then the summary
            detail = "".join(traceback.format_exception_only(error)).strip()
            results.append({"test": name, "passed": False, "error": detail})
        else:
            results.append({"test": name, "passed": True, "error": None})
    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("factory", help="MODULE:FACTORY returning a new, empty store")
    parser.add_argument("--json", action="store_true", help="print one JSON object to stdout")
    parser.add_argument(
        "--path", type=Path, default=Path.cwd(), help="directory to import from (default: cwd)"
    )
    arguments = parser.parse_args()
    sys.path.insert(0, str(arguments.path.resolve()))
    try:
        factory = load_factory(arguments.factory)
    except Exception as error:
        message = f"cannot load {arguments.factory}: {type(error).__name__}: {error}"
        if arguments.json:
            print(json.dumps({"ok": False, "error": message, "results": []}))
        else:
            print(message, file=sys.stderr)
        return 2
    results = run_contract(factory)
    failed = [result for result in results if not result["passed"]]
    if arguments.json:
        print(json.dumps({"ok": not failed, "error": None, "results": results}, indent=2))
    else:
        for result in results:
            line = f"{'PASS' if result['passed'] else 'FAIL'}  {result['test']}"
            print(line + (f"\n      {result['error']}" if result["error"] else ""))
        print(
            f"All {len(results)} promises hold."
            if not failed
            else f"{len(failed)} of {len(results)} promises broken."
        )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
