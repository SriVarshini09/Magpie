"""Compatibility engine: run the rule packs and collect fixes (PLAN §3.6 `check_compatibility`, §3.8). Owner: A.

`generic_electrical` runs on every build; the template names the domain packs to add. Each pack is called
through the shared interface in `rules/base.py`. A pack that is missing or not implemented yet is
reported as "not checked" (`needs_human`), never as a pass.
"""

from __future__ import annotations

from typing import Any

from app.models import Check, Offer
from app.pipeline.rank import offer_dict
from app.rules.base import LineCtx, PlanContext, load_pack, parse_attrs

__all__ = ["pack_names", "build_context", "run_checks", "fix_for", "respec_lines", "line_attrs", "worst"]

ALWAYS = "generic_electrical"
ORDER = {"fail": 0, "needs_human": 1, "warn": 2, "pass": 3}


def pack_names(run: Any) -> list[str]:
    names = [ALWAYS, *(run.template.rule_packs if run.template else [])]
    return list(dict.fromkeys(names))


def line_attrs(run: Any, line: Any) -> dict[str, Any]:
    """Attributes of the BOM line itself: the resolved part first, then template row attrs, then the text."""
    meta = run.line_meta.get(line.bom_line_id, {})
    attrs = parse_attrs(f"{line.spec or ''} {line.raw_name}")
    for k, v in (meta.get("attrs") or {}).items():
        if v is not None:
            attrs[k] = v
    res = run.resolved.get(line.bom_line_id)
    if res is not None:
        attrs.update(parse_attrs(res.spec))
        attrs.update({k: v for k, v in (meta.get("spec_attrs") or {}).items() if v is not None})
    return attrs


def build_context(run: Any, plan: Any = None, chosen_override: dict[str, list[tuple[Offer, int]]] | None = None) -> PlanContext:
    """The dict every pack reads. `plan` (a CartPlan) supplies the chosen offers per line."""
    chosen: dict[str, list[dict[str, Any]]] = {}
    if chosen_override is not None:
        for bid, pairs in chosen_override.items():
            chosen[bid] = [offer_dict(o, k) for o, k in pairs]
    elif plan is not None:
        for pl in plan.lines:
            o = run.offer_index.get(pl.offer_id)
            if o is not None:
                chosen.setdefault(pl.bom_line_id, []).append(offer_dict(o, pl.packs))
    lines = []
    for ln in run.bom:
        if ln.status == "removed":
            continue
        meta = run.line_meta.get(ln.bom_line_id, {})
        lines.append(LineCtx(bom_line_id=ln.bom_line_id, name=ln.raw_name, category=ln.category, qty=run.pins.qty.get(ln.bom_line_id, ln.qty),
                             line_kind=ln.line_kind, status=ln.status, row_id=meta.get("row_id"), rules=list(meta.get("rules") or []),
                             spec=(run.resolved[ln.bom_line_id].spec if ln.bom_line_id in run.resolved else ln.spec),
                             attrs=line_attrs(run, ln), chosen=chosen.get(ln.bom_line_id, [])))
    by_row = {m.get("row_id"): bid for bid, m in run.line_meta.items() if m.get("row_id")}
    edges = []
    instances: dict[str, int] = {}
    if run.template is not None:
        for e in run.template.edges:
            if e.from_ in by_row and e.to in by_row:
                edges.append({"from": by_row[e.from_], "to": by_row[e.to], "label": e.label, "rules": list(e.rules)})
        if run.template.view.kind == "urdf":
            for vp in run.template.view.parts:
                if vp.row_id in by_row:
                    instances[by_row[vp.row_id]] = instances.get(by_row[vp.row_id], 0) + vp.instances
        instances = {bid: n for bid, n in instances.items() if (run.line(bid) and run.line(bid).category == "motor")}
    return PlanContext(build_type=run.mandate.scope.build_type, lines=lines, answers=dict(run.answers), edges=edges, view_instances=instances,
                       ship_to_country=run.mandate.constraints.ship_to_country)


def respec_lines(run: Any) -> list[dict[str, Any]]:
    """Ask each pack for the spec a chip answer implies (pack hook `respec(line, plan)`). Returns what changed."""
    ctx = build_context(run).to_dict()
    changes: list[dict[str, Any]] = []
    for name in pack_names(run):
        pack = load_pack(name)
        fn = getattr(pack, "respec", None) if pack else None
        if fn is None:
            continue
        for line in ctx["lines"]:
            try:
                change = fn(line, ctx)
            except NotImplementedError:
                break
            if change:
                changes.append({"bom_line_id": line["bom_line_id"], "pack": name, **change})
    return changes


def run_checks(run: Any, plan: Any = None) -> tuple[list[Check], dict[str, str]]:
    """Run every pack. Returns (checks, {pack: "ok" | "not implemented" | "missing" | error text})."""
    ctx = build_context(run, plan).to_dict()
    checks: list[Check] = []
    state: dict[str, str] = {}
    for name in pack_names(run):
        pack = load_pack(name)
        if pack is None or not hasattr(pack, "check"):
            state[name] = "missing"
            checks.append(Check(rule_id=f"{name}", result="needs_human", message=f"Rule pack {name} is not available: its rules were not checked."))
            continue
        try:
            got = pack.check(ctx)
            checks += [c if isinstance(c, Check) else Check.model_validate(c) for c in got or []]
            state[name] = "ok"
        except NotImplementedError:
            state[name] = "not implemented"
            checks.append(Check(rule_id=f"{name}", result="needs_human", message=f"Rule pack {name} is not built yet: its rules were not checked."))
        except Exception as exc:
            state[name] = f"{type(exc).__name__}: {str(exc)[:100]}"
            checks.append(Check(rule_id=f"{name}", result="needs_human", message=f"Rule pack {name} failed to run: its rules were not checked."))
    checks.sort(key=lambda c: (_rule_key(c.rule_id), ORDER[c.result]))
    return checks, state


def _rule_key(rule_id: str) -> tuple[str, int]:
    head = rule_id.split()[0] if rule_id else ""
    return (head[:1], int(head[1:])) if head[1:].isdigit() else (head, 0)


def fix_for(run: Any, check: Check, plan: Any = None) -> dict[str, Any] | None:
    """The search filter that repairs a FAIL, from whichever pack owns the rule."""
    ctx = build_context(run, plan).to_dict()
    for name in pack_names(run):
        pack = load_pack(name)
        fn = getattr(pack, "fix", None) if pack else None
        if fn is None:
            continue
        try:
            got = fn(check, ctx)
        except (NotImplementedError, TypeError):
            continue
        if got:
            return {"pack": name, **got}
    return None


def worst(checks: list[Check], bom_line_id: str) -> str | None:
    mine = [c.result for c in checks if bom_line_id in c.bom_line_ids]
    return min(mine, key=lambda r: ORDER[r]) if mine else None
