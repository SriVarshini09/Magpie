"""One check per provenance type. No provenance, no line (PLAN §3.9, §3.18). Owner: A.

A line that fails its check is dropped and logged as `extraction_rejected`. Nothing else reaches the cart:
a part is quoted, cited, seen, or openly assumed and confirmed.

`ctx` for the checks:
    docs              {doc_sha256: exact fetched text}       readme_quote, reference_project
    template_rows     {kb_ref: row dict}, template_sha256    template_row
    kb_resolver       optional callable(kb_ref) -> bool      template_row (SingleStore lookup)
    image_sha256      iterable of hashes in the mandate scope, images {image_id: (w, h)}, labels  photo_region
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.audit.chain import sha256_hex
from app.models import AssumptionProvenance, BOMLine
from app.stores.http import is_never_request

__all__ = ["check_line", "check_lines", "why_failed", "merge_lines", "open_assumptions", "STRENGTH", "find_span", "make_assumption", "norm_name"]

STRENGTH = {"readme_quote": 1, "reference_project": 2, "template_row": 3, "photo_region": 4, "assumption": 5}


def find_span(text: str, quote: str, line_from: int | None = None) -> tuple[int, int] | None:
    """Character span of `quote` in `text`: the occurrence on `line_from` when given, else the first."""
    if not quote:
        return None
    if line_from and line_from >= 1:
        start = 0
        for _ in range(line_from - 1):
            nl = text.find("\n", start)
            if nl < 0:
                start = -1
                break
            start = nl + 1
        if start >= 0:
            end = text.find("\n", start)
            pos = text.find(quote, start, len(text) if end < 0 else end)
            if pos >= 0:
                return pos, pos + len(quote)
    pos = text.find(quote)
    return (pos, pos + len(quote)) if pos >= 0 else None


def _line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def _quote_ok(text: str | None, quote: str, span: tuple[int, int] | None) -> str | None:
    if text is None:
        return "the source document was not fetched in this run"
    if not quote or not quote.strip():
        return "empty quote"
    if quote not in text:
        return "quote is not an exact substring of the fetched document"
    if span is not None and text[span[0]:span[1]] != quote:
        return "span does not point at the quote"
    return None


def why_failed(line: BOMLine, ctx: dict[str, Any]) -> str | None:
    """None when the line passes its provenance check; otherwise the reason it is dropped."""
    p = line.provenance
    docs: dict[str, str] = ctx.get("docs") or {}
    if p.type == "readme_quote":
        text = docs.get(p.doc_sha256)
        if text is not None and sha256_hex(text) != p.doc_sha256 and ctx.get("verify_hash", False):
            return "document hash does not match"
        err = _quote_ok(text, p.quote, tuple(p.span))
        if err:
            return err
        for mq in p.more_quotes:
            err = _quote_ok(text, mq.quote, tuple(mq.span))
            if err:
                return f"second quote: {err}"
        return None
    if p.type == "reference_project":
        if is_never_request(p.url):
            return "reference host is on the never-request list"
        return _quote_ok(docs.get(p.doc_sha256), p.quote, tuple(p.span))
    if p.type == "template_row":
        rows: dict[str, Any] = ctx.get("template_rows") or {}
        resolver = ctx.get("kb_resolver")
        if p.kb_ref not in rows and not (resolver and resolver(p.kb_ref)):
            return f"kb_ref does not resolve: {p.kb_ref}"
        if p.kb_ref != f"kb://{p.template_id}#{p.row_id}":
            return "kb_ref does not match template_id and row_id"
        want = ctx.get("template_sha256")
        if want and p.template_sha256 != want:
            return "template hash does not match the loaded template"
        return None
    if p.type == "photo_region":
        if p.image_sha256 not in set(ctx.get("image_sha256") or ()):
            return "image hash is not in the mandate scope"
        size = (ctx.get("images") or {}).get(p.image_id)
        x1, y1, x2, y2 = p.box_xyxy_px
        if x1 < 0 or y1 < 0 or x2 <= x1 or y2 <= y1:
            return "box is empty or negative"
        if size and (x2 > size[0] + 0.5 or y2 > size[1] + 0.5):
            return "box lies outside the image"
        labels = ctx.get("labels")
        if labels is not None and p.label.lower() not in {str(x).lower() for x in labels}:
            return "label was not named by the classifier or the template"
        return None
    if p.type == "assumption":
        return None if p.statement and p.statement.strip() else "assumption without a statement"
    return "unknown provenance type"


def check_line(line: BOMLine, ctx: dict[str, Any]) -> bool:
    """readme_quote / reference_project: quote in source_text; template_row: kb_ref resolves and the hash
    matches; photo_region: hash in the mandate, box inside the image; assumption: has a statement.
    Supports are checked too: a support that fails is removed, the line stays."""
    if why_failed(line, ctx) is not None:
        return False
    kept = []
    for sup in line.provenance.supports:
        probe = line.model_copy(update={"provenance": sup})
        if why_failed(probe, ctx) is None:
            kept.append(sup)
    line.provenance.supports = kept
    line.provenance.check = "pass"
    return True


def check_lines(lines: Iterable[BOMLine], ctx: dict[str, Any]) -> tuple[list[BOMLine], list[dict[str, Any]]]:
    """(kept, rejected). Each rejected entry is the body of an `extraction_rejected` chain record."""
    kept: list[BOMLine] = []
    rejected: list[dict[str, Any]] = []
    for ln in lines:
        reason = why_failed(ln, ctx)
        if reason is None and check_line(ln, ctx):
            kept.append(ln)
        else:
            rejected.append({"raw_name": ln.raw_name, "qty": ln.qty, "provenance_type": ln.provenance.type,
                             "reason": reason or "provenance check failed",
                             "quote": getattr(ln.provenance, "quote", None)})
    return kept, rejected


def make_assumption(statement: str, basis: str, supports: list[Any] | None = None) -> AssumptionProvenance:
    return AssumptionProvenance(type="assumption", statement=statement, basis=basis, supports=supports or [])


def norm_name(name: str) -> str:
    import re

    s = re.sub(r"\([^)]*\)", " ", name.lower())
    s = re.sub(r"\b\d+\s*(pcs?|pieces?|x)\b", " ", s)
    return " ".join(re.findall(r"[a-z0-9.]+", s))


def _same_part(a: BOMLine, b: BOMLine, meta: dict[int, dict[str, Any]]) -> bool:
    ra, rb = meta.get(id(a), {}).get("row_id"), meta.get(id(b), {}).get("row_id")
    if ra and rb:
        return ra == rb
    na, nb = norm_name(a.raw_name), norm_name(b.raw_name)
    if na and na == nb:
        return True
    try:
        from rapidfuzz import fuzz

        return bool(na and nb and fuzz.token_set_ratio(na, nb) >= 88 and (a.category is None or b.category is None or a.category == b.category))
    except ImportError:  # pragma: no cover
        return False


def merge_lines(groups: list[list[BOMLine]], meta: dict[int, dict[str, Any]] | None = None) -> list[BOMLine]:
    """Merge lines from several inputs. The strongest provenance becomes primary, the others move to `supports`.

    `groups` are in input order (document, reference, template, photo, model additions). `meta` maps
    `id(line)` to hints such as the template `row_id`, so a README row and its template row merge.
    The result keeps source order of the strongest input and is renumbered b1…bn.
    """
    meta = meta or {}
    merged: list[BOMLine] = []
    for group in groups:
        for ln in group:
            twin = next((m for m in merged if _same_part(m, ln, meta)), None)
            if twin is None:
                merged.append(ln)
                continue
            strong, weak = (twin, ln) if STRENGTH[twin.provenance.type] <= STRENGTH[ln.provenance.type] else (ln, twin)
            weak_p = weak.provenance.model_copy(update={"supports": []})
            strong.provenance.supports = [*strong.provenance.supports, weak_p, *weak.provenance.supports]
            for attr in ("category", "spec", "qty_note"):
                if getattr(strong, attr) is None and getattr(weak, attr) is not None:
                    setattr(strong, attr, getattr(weak, attr))
            if not strong.mesh_keys and weak.mesh_keys:
                strong.mesh_keys = list(weak.mesh_keys)
            if id(weak) in meta and id(strong) not in meta:
                meta[id(strong)] = meta[id(weak)]
            elif id(weak) in meta:
                meta[id(strong)] = {**meta[id(weak)], **{k: v for k, v in meta[id(strong)].items() if v is not None}}
            if strong is not twin:
                merged[merged.index(twin)] = strong
    for i, ln in enumerate(merged, 1):
        ln.bom_line_id = f"b{i}"
    return merged


def open_assumptions(bom: Iterable[BOMLine]) -> list[str]:
    """bom_line_ids whose primary provenance is an unconfirmed assumption. Approve is refused while non-empty."""
    return [ln.bom_line_id for ln in bom
            if ln.provenance.type == "assumption" and not ln.provenance.confirmed_by_user and ln.status != "removed"]
