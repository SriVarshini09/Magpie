"""Generate frontend/src/lib/types.ts from app/models.py (the single source of truth).

SHARED FILE, owned by the coordinator (OWNERSHIP.md).

    cd backend && uv run python scripts/gen_types.py          # write the file
    cd backend && uv run python scripts/gen_types.py --check  # exit 1 if the file is out of date

tests/test_contract_parity.py runs the same comparison.
"""

from __future__ import annotations

import inspect
import json
import sys
import types
import typing
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from pydantic import BaseModel  # noqa: E402

from app import models as M  # noqa: E402

OUT = BACKEND.parent / "frontend" / "src" / "lib" / "types.ts"
PROVENANCE_CLASSES = (
    M.ReadmeQuoteProvenance, M.ReferenceProjectProvenance, M.TemplateRowProvenance,
    M.PhotoRegionProvenance, M.AssumptionProvenance,
)
SKIP = {"Model", "ProvenanceBase"}

HEADER = """\
// GENERATED FILE. DO NOT EDIT BY HAND.
// Source of truth: backend/app/models.py (PLAN §3.7, §3.16, §3.18, §3.19, §3.20, §4.2, §12.4).
// Regenerate: cd backend && uv run python scripts/gen_types.py
// Shared file, owned by the coordinator (OWNERSHIP.md). `tests/test_contract_parity.py` fails on drift.
//
// Optional (`?`) means the server may send null or leave the field out. null is "not known / not quoted".
// Mock data is always labelled: `source_api === "mock"` and `simulated === true`.
"""


def model_classes() -> list[type[BaseModel]]:
    found = {
        c for _, c in inspect.getmembers(M, inspect.isclass)
        if issubclass(c, BaseModel) and c.__module__ == M.__name__ and c.__name__ not in SKIP
    }
    return sorted(found, key=lambda c: inspect.getsourcelines(c)[1])


def ts(ann: Any) -> str:
    for name, alias in M.TS_ALIASES.items():
        if ann == alias:
            return name
    if ann is Any:
        return "unknown"
    if ann is None or ann is type(None):
        return "null"
    if ann is str:
        return "string"
    if ann in (int, float):
        return "number"
    if ann is bool:
        return "boolean"
    origin, args = typing.get_origin(ann), typing.get_args(ann)
    if origin is typing.Annotated:
        return ts(args[0])
    if origin is typing.Literal:
        return " | ".join(json.dumps(a) for a in args)
    if origin in (typing.Union, types.UnionType):
        if set(args) == set(PROVENANCE_CLASSES):
            return "Provenance"
        parts = list(dict.fromkeys(ts(a) for a in args))
        return " | ".join(parts)
    if origin is list:
        inner = ts(args[0])
        return f"Array<{inner}>"
    if origin is tuple:
        return "[" + ", ".join(ts(a) for a in args) + "]"
    if origin is dict:
        return f"Record<{ts(args[0])}, {ts(args[1])}>"
    if inspect.isclass(ann) and issubclass(ann, BaseModel):
        return ann.__name__
    raise TypeError(f"gen_types: no TypeScript mapping for {ann!r}")


def render_model(cls: type[BaseModel]) -> str:
    lines = [f"export type {cls.__name__} = {{"]
    for name, field in cls.model_fields.items():
        key = field.alias or name
        optional = (not field.is_required()) and field.default is None
        lines.append(f"  {key}{'?' if optional else ''}: {ts(field.annotation)};")
    if cls.model_config.get("extra") == "allow":
        lines.append("  [key: string]: unknown;")
    lines.append("};")
    return "\n".join(lines)


def render() -> str:
    out = [HEADER, f'export const CONTRACT_VERSION = "{M.CONTRACT_VERSION}";', ""]
    for name, alias in M.TS_ALIASES.items():
        members = typing.get_args(alias)
        body = "\n".join(f"  | {json.dumps(m)}" for m in members)
        out.append(f"export type {name} =\n{body};\n")
    out.append("export type Provenance =\n" + "\n".join(f"  | {c.__name__}" for c in PROVENANCE_CLASSES) + ";\n")
    for cls in model_classes():
        out.append(render_model(cls) + "\n")
    return "\n".join(out).rstrip("\n") + "\n"


def main() -> int:
    text = render()
    if "--check" in sys.argv:
        current = OUT.read_text(encoding="utf-8").replace("\r\n", "\n") if OUT.exists() else ""
        if current != text:
            print(f"{OUT} is out of date. Run: uv run python scripts/gen_types.py")
            return 1
        print("types.ts matches models.py")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT} ({len(model_classes())} types, {len(M.TS_ALIASES)} aliases)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
