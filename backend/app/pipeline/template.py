"""Build-type templates, the loader side (PLAN §3.19, §3.17). Owner: A. D owns the data.

Load order (each step keeps the same `kb://<template_id>#<row_id>` ids):
  1. SingleStore through D's client: `registry.get("singlestore").load_template(build_type)`
     -> {"template": {...}, "sql": "..."} (requested from D; skipped while it does not exist)
  2. `data/kb/templates/*.json` on disk (D writes these)
  3. a template rebuilt from the mock fixtures (labelled simulated), until D's files exist
  4. `tpl_generic`: categories only, every line an assumption

A template that fails validation is not loaded and its build type routes to `generic`.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app import fixtures
from app.audit.chain import canonical_json, sha256_hex
from app.config import DATA_DIR, REPO_ROOT
from app.models import (
    BOMLine, Intake, IntakeQuestion, KitToken, PhotoRegion, PhotoView, Template, TemplatePart, TemplateRowProvenance,
    ViewData, ViewEdge, ViewPart,
)
from app.pipeline.provenance import make_assumption

__all__ = ["LoadedTemplate", "load_template", "load_template_sync", "pick_variant", "rows_to_lines", "questions_for",
           "build_view", "match_row", "validate_template", "template_rows", "guess_category"]

TEMPLATES_DIR = DATA_DIR / "kb" / "templates"
PUBLIC_DIR = REPO_ROOT / "frontend" / "public"
KNOWN_RULE = re.compile(r"^(G([1-9]|1[01])|R([1-9]|1[0-7]))$")

CATEGORY_WORDS: list[tuple[str, str]] = [
    (r"\b(3d[- ]?print|printed)", "printed"),
    (r"\b(screwdriver|soldering|solder\b|charger|multimeter|tool|pliers|wrench|hex key|goggles|transmitter, goggles)", "tool"),
    (r"\b(servo|motor)s?\b(?!.*\b(board|driver|controller|adapter)\b)", "motor"),
    (r"\b(esc|motor driver|driver board|h-bridge)\b", "esc_driver"),
    (r"\b(lipo|li-?ion|battery|cell)\b", "battery"),
    (r"\b(power supply|psu|adapter 1?\d?v|wall adapter|power distribution|pdb|bec|regulator)\b", "power"),
    (r"\b(camera|webcam)\b", "camera"),
    (r"\b(receiver|vtx|video transmitter|antenna|radio|elrs)\b", "radio"),
    (r"\b(sensor|imu|gps|bme\d+|dht\d+|ultrasonic)\b", "sensor"),
    (r"\b(cable|wire|jumper|lead)s?\b", "cable"),
    (r"\b(board|controller|arduino|esp32|raspberry|pico|mcu|microcontroller|adapter|hat)\b", "board"),
    (r"\b(clamp|frame|chassis|screw|bolt|standoff|prop|propeller|wheel|bracket|mount|breadboard)", "mechanical"),
]


def guess_category(name: str) -> str | None:
    low = name.lower()
    for pattern, cat in CATEGORY_WORDS:
        if re.search(pattern, low):
            return cat
    return None


@dataclass
class LoadedTemplate:
    template: Template
    sha256: str
    source: str  # singlestore | disk | fixture | builtin
    sql: str = ""
    simulated: bool = False
    variant: str | None = None
    notice: str | None = None
    rows: dict[str, dict[str, Any]] = field(default_factory=dict)  # kb_ref -> row dict (variant applied)

    @property
    def template_id(self) -> str:
        return self.template.template_id


def validate_template(data: dict[str, Any]) -> tuple[Template | None, list[str]]:
    """The loader's own checks (D's test_template.py checks the files). Returns (template, errors)."""
    try:
        tpl = Template.model_validate(data)
    except Exception as exc:
        return None, [f"schema: {str(exc)[:300]}"]
    errors: list[str] = []
    ids = [p.row_id for p in tpl.parts]
    if len(ids) != len(set(ids)):
        errors.append("duplicate row_id")
    known = set(ids)
    for p in tpl.parts:
        for r in p.rules:
            if not KNOWN_RULE.match(r.split()[0]):
                errors.append(f"{p.row_id}: unknown rule {r}")
        if p.basis == "reference" and not (p.source and p.source.url and p.source.quote):
            errors.append(f"{p.row_id}: basis reference needs a source url and quote")
    for vp in tpl.view.parts:
        if vp.row_id not in known:
            errors.append(f"view row {vp.row_id} does not exist")
    for e in tpl.edges:
        if e.from_ not in known or e.to not in known:
            errors.append(f"edge {e.from_}->{e.to} names a missing row")
    return (None, errors) if errors else (tpl, [])


def _hash(data: dict[str, Any]) -> str:
    return sha256_hex(canonical_json(data))


def _from_disk(build_type: str) -> tuple[LoadedTemplate | None, str | None]:
    if not TEMPLATES_DIR.is_dir():
        return None, None
    for path in sorted(TEMPLATES_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if data.get("build_type") != build_type:
            continue
        tpl, errors = validate_template(data)
        if tpl is None:
            return None, f"{path.name} failed validation: {'; '.join(errors[:3])}"
        return LoadedTemplate(tpl, _hash(data), "disk"), None
    return None, None




def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:24] or "row"


def _has_pack(name: str) -> bool:
    import importlib.util

    try:
        return importlib.util.find_spec(f"app.rules.{name}") is not None
    except (ImportError, ValueError):
        return False


def _from_fixtures(build_type: str) -> LoadedTemplate | None:
    """Rebuild a template from the mock run fixtures. Labelled simulated: it stands in for D's file."""
    for name in [n for n in fixtures.names() if n.startswith("run_") and n.endswith(".json")]:
        try:
            run = fixtures.load(name)
        except FileNotFoundError:
            continue
        if run.get("build_type") != build_type:
            continue
        tpl_id = (run.get("template") or {}).get("template_id") or f"tpl_{build_type}"
        mesh_by_line: dict[str, list[dict[str, Any]]] = {}
        for vp in run["view"].get("parts", []):
            mesh_by_line.setdefault(vp["bom_line_id"], []).append(vp)
        q_ids = [q["id"] for q in run["intake"].get("questions", [])]
        parts: list[dict[str, Any]] = []
        view_parts: list[dict[str, Any]] = []
        for ln in run["bom"]:
            prov = ln["provenance"]
            row = prov if prov["type"] == "template_row" else next((s for s in prov.get("supports", []) if s["type"] == "template_row"), None)
            row_id = row["row_id"] if row else _slug(ln.get("category") or ln["raw_name"])
            if any(p["row_id"] == row_id for p in parts):
                row_id = _slug(ln["raw_name"])
            own_q = next((q for q in q_ids if q.startswith("own_") and q[4:] in row_id), None) if prov["type"] == "assumption" else None
            source = None
            basis = (row or {}).get("basis") or "rule_of_thumb"
            if prov["type"] == "readme_quote":
                basis, source = "reference", {"url": prov["url"], "quote": prov["quote"]}
            elif (row or {}).get("derived_from"):
                source = {"url": row["derived_from"], "quote": None}
            spec = ln.get("spec") if prov["type"] != "readme_quote" else ln["raw_name"]
            parts.append({"row_id": row_id, "name": ln["raw_name"], "category": ln.get("category") or guess_category(ln["raw_name"]) or "mechanical",
                          "qty": ln["qty"], "qty_note": ln.get("qty_note"), "line_kind": ln["line_kind"], "typical_spec": spec,
                          "attrs": {}, "search_query": None, "rules": [], "own_question": own_q, "basis": basis, "source": source,
                          "mesh": (mesh_by_line.get(ln["bom_line_id"]) or [{}])[0].get("mesh")})
            for vp in mesh_by_line.get(ln["bom_line_id"], []):
                view_parts.append({"mesh": vp["mesh"], "row_id": row_id, "instances": vp.get("instances", 1),
                                   "explode": vp.get("explode", [0, 0, 0]), "order": vp.get("order", 0)})
        variant = (run.get("template") or {}).get("variant")
        data = {
            "template_id": tpl_id, "build_type": build_type, "version": "0.0-fixture", "title": run["intake"].get("summary") or build_type,
            "summary": f"Rebuilt from the mock fixture {name}; replaced by data/kb/templates when it exists",
            "references": [], "questions": [{"id": q["id"], "text": q["text"], "chips": q["chips"], "default": q["default"], "skip_if": []}
                                           for q in run["intake"].get("questions", [])],
            "variants": [{"id": variant, "label": variant, "when": {}, "overrides": {}}] if variant else [],
            "parts": parts, "rule_packs": ["generic_electrical"] + ([build_type] if _has_pack(build_type) else []),
            "view": {"kind": run["view"]["kind"], "model": run["view"].get("model"), "parts": view_parts},
            "edges": [],  # fixture edges name BOM lines, not rows
        }
        tpl, _ = validate_template(data)
        if tpl is None:
            try:
                tpl = Template.model_validate(data)
            except Exception:
                return None
        return LoadedTemplate(tpl, _hash(data), "fixture", simulated=True,
                              notice="Template rebuilt from mock fixtures (D's template file is not present)")
    return None


GENERIC_ROWS = [("board", "Controller board", "board"), ("power", "Power source", "power"), ("actuators", "Motors or actuators", "motor"),
                ("sensors", "Sensors", "sensor"), ("wiring", "Cables and connectors", "cable"), ("structure", "Frame or enclosure", "mechanical")]


def _generic(build_type: str = "generic") -> LoadedTemplate:
    data = {
        "template_id": "tpl_generic", "build_type": "generic", "version": "0.1", "title": "Generic build",
        "summary": "Categories only. Every line is an assumption until you confirm it.",
        "references": [], "variants": [],
        "questions": [{"id": "budget", "text": "What is your budget?", "chips": [{"value": "50", "label": "About $50"}, {"value": "150", "label": "About $150"},
                                                                                {"value": "300", "label": "About $300"}], "default": "150", "skip_if": ["text_mentions_budget"]}],
        "parts": [{"row_id": rid, "name": name, "category": cat, "qty": None, "line_kind": "part", "typical_spec": None, "attrs": {},
                   "search_query": None, "rules": [], "own_question": None, "basis": "assumption", "source": None, "mesh": None}
                  for rid, name, cat in GENERIC_ROWS],
        "rule_packs": ["generic_electrical"], "view": {"kind": "kit", "model": None, "parts": []}, "edges": [],
    }
    lt = LoadedTemplate(Template.model_validate(data), _hash(data), "builtin")
    if build_type != "generic":
        lt.notice = f"No template for {build_type}: using the generic build (all lines are assumptions)"
    return lt


def load_template_sync(build_type: str) -> LoadedTemplate:
    """Disk, then fixtures, then generic. Never raises."""
    lt, notice = _from_disk(build_type)
    if lt is None and notice is None:
        lt = _from_fixtures(build_type)
    if lt is None:
        lt = _generic(build_type)
        if notice:
            lt.notice = notice + ". Routed to the generic build."
    return lt


async def load_template(build_type: str, answers: dict[str, str] | None = None, *, store: Any = None) -> LoadedTemplate:
    """Load a template through D's SingleStore client, falling back to disk (same kb:// ids)."""
    lt: LoadedTemplate | None = None
    sql = ""
    if store is None:
        try:
            from app import registry

            store = registry.get("singlestore")
        except Exception:
            store = None
    loader = getattr(store, "load_template", None)
    if loader is not None:
        try:
            got = await loader(build_type)
            if got and got.get("template"):
                tpl, errors = validate_template(got["template"])
                if tpl is not None:
                    lt = LoadedTemplate(tpl, _hash(got["template"]), str(got.get("source") or "singlestore"), sql=str(got.get("sql") or ""),
                                        simulated=bool(got.get("simulated")))
        except NotImplementedError:
            pass
        except Exception:
            lt = None
    if lt is None:
        lt = load_template_sync(build_type)
        if store is not None and not lt.sql:
            try:  # the hybrid query still shows which template text search picks
                res = await store.hybrid_search(build_type.replace("_", " "), kind="template")
                sql = res.sql if hasattr(res, "sql") else str(res.get("sql", ""))
                if getattr(res, "simulated", False):
                    lt.simulated = True
            except Exception:
                sql = ""
            lt.sql = sql or f"-- template read from {lt.source}: data/kb/templates (SingleStore not connected)"
    lt.variant = pick_variant(lt.template, answers or {})
    lt.rows = template_rows(lt.template, lt.variant)
    return lt


def pick_variant(template: Template, answers: dict[str, str]) -> str | None:
    """The first variant whose `when` is satisfied by the answers (defaults fill unanswered questions)."""
    full = {q.id: q.default for q in template.questions} | {k: v for k, v in answers.items() if v is not None}

    def same(k: str, want: Any) -> bool:
        if k == "source_url":  # the project's own link: compare without case, trailing slash or ".git"
            norm = lambda u: str(u or "").strip().lower().rstrip("/").removesuffix(".git")  # noqa: E731
            return bool(full.get(k)) and norm(full.get(k)) == norm(want)
        return full.get(k) == want

    best: tuple[tuple[int, int], str] | None = None
    for v in template.variants:
        if all(same(k, val) for k, val in v.when.items()):
            rank = (1 if "source_url" in v.when else 0, len(v.when))  # a variant written for this very project wins
            if best is None or rank > best[0]:
                best = (rank, v.id)
    return best[1] if best else None


def _deep_merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in over.items():
        out[k] = _deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def template_rows(template: Template, variant: str | None) -> dict[str, dict[str, Any]]:
    """{kb_ref: row dict} with the variant's overrides applied."""
    overrides: dict[str, Any] = {}
    for v in template.variants:
        if v.id == variant:
            overrides = v.overrides
    out: dict[str, dict[str, Any]] = {}
    for p in template.parts:
        row = p.model_dump(mode="json")
        if p.row_id in overrides and isinstance(overrides[p.row_id], dict):
            row = _deep_merge(row, overrides[p.row_id])
            row["_overridden"] = True
        out[f"kb://{template.template_id}#{p.row_id}"] = row
    return out


def rows_to_lines(lt: LoadedTemplate, answers: dict[str, str], defaulted: set[str] | None = None) -> tuple[list[BOMLine], dict[int, dict[str, Any]]]:
    """Template rows as BOM lines with `template_row` provenance (or `assumption`, see below).

    A row becomes an assumption when: its basis is `assumption`; its quantity is unknown; a chip that
    was defaulted (not tapped) selected the variant that changed it; or its `own_question` was defaulted.
    The template row stays underneath as a support.
    """
    tpl, defaulted = lt.template, defaulted or set()
    variant = next((v for v in tpl.variants if v.id == lt.variant), None)
    variant_defaulted = bool(variant and variant.when and any(k in defaulted for k in variant.when))
    lines: list[BOMLine] = []
    meta: dict[int, dict[str, Any]] = {}
    for i, (kb_ref, row) in enumerate(lt.rows.items(), 1):
        part = TemplatePart.model_validate({k: v for k, v in row.items() if not k.startswith("_")})
        basis = part.basis if part.basis in ("reference", "rule_of_thumb") else "rule_of_thumb"
        row_prov = TemplateRowProvenance(type="template_row", kb_ref=kb_ref, template_id=tpl.template_id, row_id=part.row_id,
                                         variant=lt.variant, template_sha256=lt.sha256, basis=basis,  # type: ignore[arg-type]
                                         derived_from=part.source.url if part.source else None)
        prov: Any = row_prov
        status, owned_note = "extracted", None
        label = part.typical_spec or part.name
        if part.basis == "assumption":
            prov = make_assumption(f"Assumed you need: {part.name}", "generic template: categories only", [row_prov])
        elif part.qty is None:
            prov = make_assumption(f"Quantity of {part.name} is not stated; assumed 1", "quantity not stated in the template", [row_prov])
        elif row.get("_overridden") and variant_defaulted:
            prov = make_assumption(f"Assumed {variant.label if variant else lt.variant}: {label}", "chip defaulted", [row_prov])
        if part.own_question:
            ans = answers.get(part.own_question)
            q = next((q for q in tpl.questions if q.id == part.own_question), None)
            val = ans if ans is not None else (q.default if q else None)
            if val == "yes":
                status, owned_note = "owned", "You said you have this"
                if part.own_question in defaulted or ans is None:
                    prov = make_assumption(f"Assumed you already own: {part.name}", "chip defaulted", [row_prov])
                    owned_note = "Assumed owned"
        ln = BOMLine(bom_line_id=f"b{i}", raw_name=part.name, qty=part.qty if part.qty is not None else 1, qty_note=part.qty_note,
                     provenance=prov, line_kind=part.line_kind, status=status, category=part.category,  # type: ignore[arg-type]
                     mesh_keys=[vp.mesh for vp in tpl.view.parts if vp.row_id == part.row_id] or ([part.mesh] if part.mesh else []),
                     spec=part.typical_spec, owned_note=owned_note)
        lines.append(ln)
        meta[id(ln)] = {"row_id": part.row_id, "rules": list(part.rules), "search_query": part.search_query,
                        "attrs": {k: v for k, v in part.attrs.items() if v is not None}, "own_question": part.own_question}
    return lines, meta


def match_row(template: Template, name: str, category: str | None = None) -> TemplatePart | None:
    """The template row a document line corresponds to (for its category, meshes and rules)."""
    try:
        from rapidfuzz import fuzz
    except ImportError:  # pragma: no cover
        return None
    best: tuple[float, TemplatePart] | None = None
    low = name.lower()
    for p in template.parts:
        score = max(fuzz.token_set_ratio(low, p.name.lower()), fuzz.partial_ratio(low, (p.typical_spec or "").lower()) if p.typical_spec else 0)
        if p.source and p.source.quote:
            score = max(score, fuzz.token_set_ratio(low, p.source.quote.lower()))
        if category and p.category == category:
            score += 5
        if best is None or score > best[0]:
            best = (score, p)
    return best[1] if best and best[0] >= 72 else None


_SIZE = re.compile(r"(?i)\b(\d+(\.\d+)?\s*(-|\s)?(inch|in\b|\")|palm[- ]size|small|tiny|mini|micro|large|big|full[- ]size)")
_BUDGET = re.compile(r"(?i)(?:under|below|less than|max(?:imum)?|budget(?: of)?|about|around|for|<=?|up to)?\s*\$\s?(\d{1,5}(?:\.\d{1,2})?)|\b(\d{2,5})\s*(?:dollars|usd|bucks)\b")
_VOLT = re.compile(r"(?i)\b(7\.4|12)\s?v\b")


def text_signals(text: str | None) -> dict[str, Any]:
    """What a typed request already answers (PLAN §3.17 clarifying chips)."""
    t = text or ""
    out: dict[str, Any] = {}
    m = _BUDGET.search(t)
    if m:
        out["budget_usd"] = float(m.group(1) or m.group(2))
    if _SIZE.search(t):
        out["size"] = _SIZE.search(t).group(0).strip()  # type: ignore[union-attr]
    if _VOLT.search(t):
        out["voltage"] = _VOLT.search(t).group(1)  # type: ignore[union-attr]
    return out


_INCHES = re.compile(r"(?i)(?<![\d.])(\d+(?:\.\d+)?)\s*(?:-|\s)?(?:inch(?:es)?|in\b|\")")


def answers_from_text(template: Template, text: str | None) -> dict[str, str]:
    """{question id: chip value} for a size question the text answers: "5 inch" picks the chip labelled "5-inch".

    A size that no chip names ("7 inch" when the chips are 3, 5 and 10) answers nothing, so the question is still asked.
    """
    m = _INCHES.search(text or "")
    if not m:
        return {}
    num = m.group(1)
    out: dict[str, str] = {}
    for q in template.questions:
        if "text_mentions_size" not in q.skip_if:
            continue
        hit = next((c for c in q.chips if any(x.group(1) == num for x in _INCHES.finditer(c.label))), None)
        if hit is not None:
            out[q.id] = hit.value
    return out


def questions_for(template: Template, text: str | None, *, answered: set[str] | None = None, known: set[str] | None = None,
                  limit: int = 3) -> list[IntakeQuestion]:
    """At most three questions, taken from the template in its order. Never invented by the model.

    A question is skipped when the text already answers it (`skip_if`, or its id is in `answered`,
    which the classifier fills) or memory already knows it (`known`). A size is skipped only when a
    chip names it (`answers_from_text`), so the run gets that chip's variant instead of the default.
    """
    sig = text_signals(text)
    from_text = answers_from_text(template, text)
    answered, known = answered or set(), known or set()
    out: list[IntakeQuestion] = []
    for q in template.questions:
        if q.id in answered or q.id in known:
            continue
        if q.id == "budget" and "budget_usd" in sig:
            continue
        if any((s == "text_mentions_budget" and "budget_usd" in sig) or (s == "text_mentions_voltage" and "voltage" in sig) or
               (s == "text_mentions_size" and q.id in from_text) for s in q.skip_if):
            continue
        out.append(IntakeQuestion(id=q.id, text=q.text, chips=q.chips, default=q.default))
        if len(out) >= limit:
            break
    return out


def _model_url(model: str | None) -> str | None:
    """The first .urdf under frontend/public/<model>/ (served by the frontend)."""
    if not model:
        return None
    folder = PUBLIC_DIR / model
    try:
        urdf = sorted(folder.glob("*.urdf"))
    except OSError:
        return None
    return f"/{model}/{urdf[0].name}" if urdf else None


def build_view(template: Template | None, bom: list[BOMLine], line_meta: dict[str, dict[str, Any]], *, variant: str | None = None,
               intake: Intake | None = None, has_source_model: bool | None = None, photo_parts: list[Any] | None = None) -> ViewData:
    """`ViewData` for the view router (PLAN §3.20): template meshes mapped to BOM lines by row id."""
    by_row = {m.get("row_id"): bid for bid, m in line_meta.items() if m.get("row_id")}
    live = [ln for ln in bom if ln.status != "removed"]
    kind, model = ("kit", None)
    parts: list[ViewPart] = []
    edges: list[ViewEdge] | None = None
    if template is not None:
        kind, model = template.view.kind, template.view.model
        if kind == "urdf" and (has_source_model is False or _model_url(model) is None):
            kind, model = "kit", None  # no model from the project's own repository
        if kind in ("urdf", "procedural"):
            for vp in template.view.parts:
                bid = by_row.get(vp.row_id)
                if bid:
                    parts.append(ViewPart(mesh=vp.mesh, bom_line_id=bid, instances=vp.instances, explode=vp.explode, order=vp.order))
        if template.edges:
            edges = [ViewEdge(**{"from": by_row[e.from_], "to": by_row[e.to], "label": e.label, "rule_ids": e.rules})
                     for e in template.edges if e.from_ in by_row and e.to in by_row] or None
    on_model = {p.bom_line_id for p in parts}
    photo = None
    if intake and intake.inputs.images:
        img = intake.inputs.images[0]
        regions = []
        for pp in (photo_parts if photo_parts is not None else (intake.visible_parts or [])):
            bid = next((ln.bom_line_id for ln in live for pr in [ln.provenance, *ln.provenance.supports]
                        if pr.type == "photo_region" and pr.label == pp.label and tuple(pr.box_xyxy_px) == tuple(pp.box_xyxy_px)), None)
            regions.append(PhotoRegion(bom_line_id=bid, box_xyxy_px=pp.box_xyxy_px, label=pp.label, score=pp.score,
                                       approximate=not str(pp.detector).startswith("sie:")))
        photo = PhotoView(image_id=img.image_id, url=img.url, w=img.w, h=img.h, sha256=img.sha256, regions=regions)
    note = {"urdf": "Model from the project's own repository", "procedural": "Illustrative model, not to scale",
            "diagram": "Illustrative layout", "kit": "Illustrative kit view"}.get(kind, "Illustrative")
    return ViewData(
        kind=kind, model=model, variant=variant, urdf_url=_model_url(model) if kind == "urdf" else None, parts=parts,  # type: ignore[arg-type]
        edges=edges if kind == "diagram" or edges else None,
        tokens=[KitToken(bom_line_id=ln.bom_line_id, category=ln.category or "mechanical", qty=ln.qty, label=ln.raw_name) for ln in live] if kind == "kit" else None,
        photo=photo, tray=[ln.bom_line_id for ln in live if ln.bom_line_id not in on_model] if kind in ("urdf", "procedural") else [], note=note)
