"""Proves the Stage A probes cannot place, modify, or unlock trading.

This is the machine-checkable backing for the 'read-only' claim in docs/feasibility.md.
Run:  python -m pytest tests/ -v      (or: python tests/test_probe_is_readonly.py)
"""

from __future__ import annotations

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
PROBES = sorted((ROOT / "tools").glob("probe_*.py"))

# Any moomoo SDK call that can change broker state or unlock trading.
FORBIDDEN_CALLS = {
    "place_order",
    "modify_order",
    "cancel_order",
    "unlock_trade",
    "deal_list_query_fake",
}


def called_names(path: pathlib.Path) -> set[str]:
    """Every attribute/function name that appears in a call position."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute):
                names.add(func.attr)
            elif isinstance(func, ast.Name):
                names.add(func.id)
    return names


def test_probes_exist() -> None:
    assert PROBES, "no probe scripts found in tools/"


def test_no_write_calls() -> None:
    for probe in PROBES:
        used = called_names(probe)
        bad = used & FORBIDDEN_CALLS
        assert not bad, f"{probe.name} calls forbidden write API: {sorted(bad)}"


def test_no_write_identifiers_in_source() -> None:
    """Belt and braces: the strings must not appear at all, even dynamically."""
    for probe in PROBES:
        src = probe.read_text(encoding="utf-8")
        # tools/probe_readonly.py names them in its FORBIDDEN tuple / docstring,
        # so only flag occurrences that look like an actual call.
        for name in FORBIDDEN_CALLS:
            assert f".{name}(" not in src, f"{probe.name} appears to call .{name}()"


if __name__ == "__main__":
    test_probes_exist()
    test_no_write_calls()
    test_no_write_identifiers_in_source()
    print(f"OK: {len(PROBES)} probe script(s) verified read-only: "
          f"{', '.join(p.name for p in PROBES)}")
