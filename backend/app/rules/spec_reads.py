"""Specs read from a listing by SIE `extract`, normalized in our code for the compatibility rules (PLAN §3.15).

    read_offers(sie, offers)      one `sie.extract` call per offer text (title, plus description), run concurrently,
                                  cached by text hash for the process; fills `Offer.spec_reads`. Never raises.
    to_reads(spans, title, desc)  SIE spans -> SpecRead[]: each span is normalized by the SAME parsers the rules
                                  use on titles; a span we cannot parse, or cannot find in the text, is dropped.
    base_attrs(reads)             the values in `rules/base.py` attr keys (merged by `pipeline/rank.offer_dict`)
    rule_attrs(reads)             the values in `rules/generic_electrical.py` attr keys (G rules)
    best(reads)                   {attr: the read a rule judges}; `note(read)` says who read it, for a message
    pattern_spans(text, labels)   the MOCK reader: a deterministic local pattern reader with SIE's span shape
                                  (provider "mock", simulated). It is `MockSIE.extract`; it is not SIE.

A spec read wins over the title pattern for the same attribute. With no read (no SIE_EXTRACT_MODEL, a network
error, a span that does not parse) the title patterns apply exactly as before. As with the patterns, a value
stated in the description wins over one in the title, except the stack mounting pattern and the motor stator,
which are read from the title first.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import statistics
import time
from typing import Any

from app.models import Offer, SpecRead
from app.rules import base
from app.rules import generic_electrical as ge

__all__ = ["SPEC_LABELS", "LABELS", "read_offers", "to_reads", "normalize", "pattern_spans", "best", "note", "base_attrs",
           "rule_attrs", "listing_text", "reset"]

# SIE label -> the attribute the rules read. The labels are what we ask SIE for; the values are ours.
SPEC_LABELS: dict[str, str] = {
    "motor stator size": "stator",
    "propeller size": "prop_in",
    "mounting pattern": "mount_mm",
    "battery cell count": "cells",
    "battery capacity": "capacity_mah",
    "connector": "connector",
    "current rating": "current_a",
    "voltage": "voltage_v",
    "motor KV": "kv",
}
LABELS = list(SPEC_LABELS)
# What we send to the real SIE extractor (GLiNER). Measured on live listings: it does not recognise "motor stator
# size" or "mounting pattern", and a long label list dilutes every score; generic labels work ("1404" scores 0.61 as
# a model number, "25.5x25.5" 0.59 as dimensions). Our parsers decide what a span means: a "model number" counts
# only when it parses as a stator size, "dimensions" only as a stack pattern; anything else is dropped.
LIVE_LABELS = ["model number", "dimensions", "propeller size", "motor KV", "current rating", "voltage",
               "battery cell count", "battery capacity", "connector"]
_LABEL_ATTR = {k.lower(): v for k, v in SPEC_LABELS.items()}
_LABEL_ATTR.update({"current": "current_a", "kv": "kv",  # the generic labels in integrations/sie.py EXTRACT_LABELS
                    "model number": "stator", "dimensions": "mount_mm"})
ATTR_ORDER = ("mount_mm", "stator", "prop_in", "kv", "cells", "capacity_mah", "current_a", "voltage_v", "connector")
_TITLE_FIRST = frozenset({"mount_mm", "stator"})

MOCK_MODEL = "mock-patterns"
MIN_SCORE = 0.35  # the floor integrations/sie.py uses for detections
MAX_OFFERS_PER_LINE = 30
MAX_TEXT = 1200
CONCURRENCY = 4
LINE_TIMEOUT_S = 20.0
COOL_OFF_S = 60.0  # after a failed or timed-out extract, later lines skip SIE for this long (patterns apply)
_CACHE_CAP = 4000

_CACHE: dict[str, list[dict[str, Any]]] = {}
_DOWN_UNTIL: dict[str, float] = {}


def reset() -> None:
    """Forget cached spans and cool-offs (tests)."""
    _CACHE.clear()
    _DOWN_UNTIL.clear()


# --------------------------------------------------------------------------- normalizers


def _g(v: float) -> str:
    return f"{float(v):g}"


_PEAK = re.compile(r"stall|peak|burst|max", re.I)
_UNIT_AFTER = re.compile(r"\s*(?:m\s*a\s*h|kv|mw|mm|hz|khz|mhz|ghz|rpm|pcs|v|a|w|g)\b", re.I)


def normalize(attr: str, span: str, before: str = "", after: str = "") -> str | None:
    """The value the rules judge for one span, or None when the span does not state that attribute.

    Uses the rules' own parsers on the span, so "30.5x30.5 mm" -> "30x30", "XT-60" -> "XT60", "4 cell" -> "4".
    `before` / `after` are the text around the span (a peak, burst or stall current is not the current rating).
    """
    span = (span or "").strip()
    if not span:
        return None
    if attr == "mount_mm":
        return ge._mount_class(span)
    if attr == "stator":
        m = ge._STATOR.search(span)
        return m.group(0) if m and 10 <= int(m.group(1)) <= 40 and int(m.group(2)) >= 2 else None
    if attr == "connector":
        tokens = [t for t in ge.parse_connectors(span)[0] if t != "JST"]  # a bare "JST" names no family
        if tokens:
            return tokens[0]
        return "USB-C" if base.parse_attrs(span).get("connector") == "USB-C" else None
    p = ge.parse_attrs(span)
    if attr == "cells":
        return str(p["cells"]) if isinstance(p.get("cells"), int) and p.get("cells_from") == "count" and 1 <= p["cells"] <= 14 else None
    if attr == "capacity_mah":
        return str(int(p["capacity_mah"])) if p.get("capacity_mah") else None
    if attr == "kv":
        return str(int(p["kv"])) if p.get("kv") else None
    if attr == "voltage_v":
        return _g(p["voltage_v"]) if p.get("voltage_v") is not None and "voltage_range" not in p else None
    if attr == "current_a":
        if p.get("current_a") is None or _PEAK.search(before[-14:]) or _PEAK.search(after[:14]):
            return None
        return _g(p["current_a"])
    if attr == "prop_in":
        v = p.get("prop_in", p.get("size_in"))
        return _g(v) if v is not None and 1 <= float(v) <= 30 else None
    return None


# --------------------------------------------------------------------------- spans -> SpecRead


def listing_text(title: str | None, description: str | None) -> str:
    """The one text sent to extract: the title, then the description on its own line."""
    t = (title or "").replace("\n", " ")
    return (t + ("\n" + description if description else ""))[:MAX_TEXT]


def to_reads(spans: list[dict[str, Any]] | None, title: str | None, description: str | None = None, *, mock: bool = False) -> list[SpecRead]:
    """Normalize SIE spans from `listing_text(title, description)`. Unknown labels and unparseable spans are dropped."""
    text = listing_text(title, description)
    n_title = len((title or "").replace("\n", " "))
    out: list[SpecRead] = []
    seen: set[tuple[str, str, str]] = set()
    for s in spans or []:
        try:
            attr = _LABEL_ATTR.get(str(s.get("label") or "").strip().lower())
            raw = str(s.get("text") or "")
            if not attr or not raw.strip():
                continue
            score = s.get("score")
            score = float(score) if isinstance(score, (int, float)) and not isinstance(score, bool) else None
            if score is not None and score < MIN_SCORE:
                continue
            start, end = s.get("start"), s.get("end")
            if not (isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(text)):
                start = text.find(raw)
                if start < 0:
                    continue  # a span that is not in the listing text is never judged
                end = start + len(raw)
            raw = text[start:end]
            value = normalize(attr, raw, text[max(0, start - 14): start], text[end: end + 14])
            if value is None:
                continue
            field = "title" if start < n_title else "description"
            if (attr, value, field) in seen:
                continue
            seen.add((attr, value, field))
            is_mock = bool(mock or s.get("simulated") or s.get("provider") == "mock")
            off = 0 if field == "title" else n_title + 1
            out.append(SpecRead(attr=attr, value=value, text=raw.strip(), label=str(s.get("label")), score=None if score is None else round(score, 3),
                                start=start - off, end=end - off, field=field, provider="mock" if is_mock else "sie",
                                model=MOCK_MODEL if is_mock else str(s.get("model") or "sie-extract"), simulated=is_mock))
        except Exception:
            continue
    out.sort(key=lambda r: (ATTR_ORDER.index(r.attr), _field_rank(r.attr, r.field), -(r.score or 0.0), r.start or 0))
    return out


def _field_rank(attr: str, field: str) -> int:
    return int(field != ("title" if attr in _TITLE_FIRST else "description"))


def _dicts(reads: Any) -> list[dict[str, Any]]:
    return [r.model_dump() if hasattr(r, "model_dump") else dict(r) for r in (reads or []) if r]


def _by_attr(reads: Any) -> dict[str, list[dict[str, Any]]]:
    """{attr: reads from the preferred field that has any, best first}."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for r in _dicts(reads):
        if r.get("attr") in ATTR_ORDER and r.get("value") not in (None, ""):
            groups.setdefault(r["attr"], []).append(r)
    out: dict[str, list[dict[str, Any]]] = {}
    for attr, rs in groups.items():
        rs.sort(key=lambda r: (_field_rank(attr, r.get("field") or "title"), -(r.get("score") or 0.0), r.get("start") or 0))
        out[attr] = [r for r in rs if r.get("field") == rs[0].get("field")]
    return out


def best(reads: Any) -> dict[str, dict[str, Any]]:
    """{attr: the one read the rules judge}."""
    return {attr: rs[0] for attr, rs in _by_attr(reads).items()}


def note(read: dict[str, Any] | None) -> str | None:
    """Who read a value, for a rule message: 'SIE read “20x20” in the title' or 'mock SIE read “20x20”'."""
    if not read:
        return None
    quoted = f"“{str(read.get('text') or read.get('value'))[:40]}”"
    if read.get("provider") == "sie" and not read.get("simulated"):
        return f"SIE read {quoted} in the {read.get('field') or 'title'}"
    return f"mock SIE read {quoted}"


def _numbers(by: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for attr, cast in (("cells", int), ("kv", int), ("capacity_mah", float), ("current_a", float), ("voltage_v", float), ("prop_in", float)):
        if attr in by:
            try:
                out[attr] = cast(float(by[attr][0]["value"]))
            except (TypeError, ValueError):
                pass
    for attr in ("mount_mm", "stator"):
        if attr in by:
            out[attr] = str(by[attr][0]["value"])
    return out


def _base_connector(token: str) -> str:
    return "barrel_" + token[7:] if token.startswith("BARREL-") else token


def base_attrs(reads: Any) -> dict[str, Any]:
    """Spec reads in `rules/base.py` `parse_attrs` keys (what `offer_dict` merges over the title patterns)."""
    by = _by_attr(reads)
    out = _numbers(by)
    if "connector" in by:
        tokens = list(dict.fromkeys(_base_connector(str(r["value"])) for r in by["connector"]))
        out["connector"], out["connectors"] = tokens[0], tokens
        fam = tokens[0].removeprefix("JST-")
        if fam in base.JST_PITCH:
            out["pitch_mm"] = base.JST_PITCH[fam]
    return out


def rule_attrs(reads: Any) -> dict[str, Any]:
    """Spec reads in `generic_electrical.parse_attrs` keys (what the G rules judge)."""
    by = _by_attr(reads)
    out = _numbers(by)
    if "capacity_mah" in out:
        out["capacity_mah"] = int(out["capacity_mah"])
    if "cells" in out:
        out["cells_from"] = "count"
    if "connector" in by:
        tokens = [str(r["value"]) for r in by["connector"] if ge.parse_connectors(str(r["value"]))[0]]
        if tokens:
            out.update(ge._coerce_attrs({"connector": tokens}))
    return out


# --------------------------------------------------------------------------- the mock reader

_NUM = r"(\d+(?:\.\d+)?)"
_USB_C = re.compile(r"\busb[- ]?c\b|\btype[- ]?c\b", re.I)
_SPAN_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "cells": [re.compile(r"\b\d{1,2}\s*s(?:\d+p)?\b", re.I), re.compile(r"\b\d{1,2}\s*-?\s*cells?\b", re.I)],
    "capacity_mah": [re.compile(r"\b(?:\d{1,3}(?:,\d{3})+|\d{2,6})\s*m\s*a\s*h\b", re.I)],
    "kv": [re.compile(r"\b\d{2,5}\s*-?\s*kv\b|\bkv\s*-?\s*\d{2,5}\b", re.I)],
    "voltage_v": [re.compile(r"(?<![\d.])" + _NUM + r"\s*v(?:dc|ac)?(?![a-z0-9])", re.I)],
    "current_a": [re.compile(r"(?<![\d.])" + _NUM + r"\s*(?:ma|a)(?![a-z])", re.I)],
    "prop_in": [re.compile(r"\b\d{4}\s*(?:props?|propellers?)\b|\bprop(?:s|ellers?)?\s*[:\-]?\s*\d{4}\b", re.I),
                re.compile(r"\b" + _NUM + r'\s*(?:-\s*)?(?:inch(?:es)?\b|in\b(?!\s*\d)|")', re.I)],
}
_MOTOR_TEXT = re.compile(r"\bmotors?\b|brushless|\bstator\b|\d\s*kv\b", re.I)
_SIZED_TEXT = re.compile(r"\bprop|\bframe|\bfpv\b|quad|\bdrone|\bmotor|wheelbase", re.I)


def _same(a: Any, b: Any) -> bool:
    try:
        return a is not None and b is not None and abs(float(a) - float(b)) < 1e-6
    except (TypeError, ValueError):
        return False


def _segment_spans(seg: str, wanted: dict[str, str]) -> list[tuple[str, int, int]]:
    """(attr, start, end) for one line of text. A span is kept only when the rules' own parser reads the same
    value from the whole line, so this reader can never disagree with the title patterns."""
    t = seg.translate(ge._DASHES)  # one character for one: offsets stay valid
    parsed = ge.parse_attrs(seg)
    found: list[tuple[str, int, int]] = []
    if "mount_mm" in wanted:
        m = next((m for m in ge._MOUNT.finditer(t) if ge._mount_class(m.group(0))), None)
        if m:
            found.append(("mount_mm", m.start(), m.end()))
    if "stator" in wanted and _MOTOR_TEXT.search(t):
        m = next((m for m in ge._STATOR.finditer(t) if normalize("stator", m.group(0)) and not _UNIT_AFTER.match(t, m.end())), None)
        if m:
            found.append(("stator", m.start(), m.end()))
    if "connector" in wanted:
        work = t
        known = set(parsed.get("connectors") or [])
        hits: list[tuple[int, int]] = []
        for pattern, _kind in ge._CONN_PATTERNS:
            work = ge._sub_all(pattern, work, lambda m: hits.append((m.start(), m.end())))
        for s, e in sorted(hits):
            if normalize("connector", t[s:e]) in known:
                found.append(("connector", s, e))
        found += [("connector", m.start(), m.end()) for m in _USB_C.finditer(t)]
    expect = {"cells": parsed.get("cells") if parsed.get("cells_from") == "count" else None,
              "capacity_mah": parsed.get("capacity_mah"), "kv": parsed.get("kv"), "voltage_v": parsed.get("voltage_v"),
              "current_a": parsed.get("current_a"),
              "prop_in": parsed.get("prop_in", parsed.get("size_in")) if _SIZED_TEXT.search(t) else None}
    for attr, patterns in _SPAN_PATTERNS.items():
        if attr not in wanted or expect.get(attr) is None:
            continue
        for m in (m for p in patterns for m in p.finditer(t)):
            if _same(normalize(attr, m.group(0), t[max(0, m.start() - 14): m.start()], t[m.end(): m.end() + 14]), expect[attr]):
                found.append((attr, m.start(), m.end()))
                break
    return found


def pattern_spans(text: str, labels: list[str] | None = None) -> list[dict[str, Any]]:
    """MOCK extract: the local pattern reader. Same span shape as SIE's, labelled provider "mock", simulated.

    Deterministic, no network. It finds what the title patterns find and reports where; it has no score.
    """
    wanted: dict[str, str] = {}
    for label in labels or LABELS:
        attr = _LABEL_ATTR.get(str(label).strip().lower())
        if attr:
            wanted.setdefault(attr, str(label))
    out: list[dict[str, Any]] = []
    offset = 0
    for seg in (text or "").split("\n"):
        for attr, s, e in _segment_spans(seg, wanted):
            lead = len(seg[s:e]) - len(seg[s:e].lstrip())
            out.append({"label": wanted[attr], "text": seg[s + lead:e].rstrip(), "score": None, "start": offset + s + lead,
                        "end": offset + s + lead + len(seg[s + lead:e].rstrip()), "provider": "mock", "model": MOCK_MODEL,
                        "source_api": "mock", "simulated": True})
        offset += len(seg) + 1
    out.sort(key=lambda d: d["start"])
    return out


# --------------------------------------------------------------------------- one extract call per offer


def _is_mock(sie: Any) -> bool:
    return type(sie).__name__.startswith("Mock")


def _provider_key(sie: Any) -> str | None:
    """A cache key for this client and extract model; None when extract is not configured (no call is made)."""
    name = f"{type(sie).__module__}.{type(sie).__name__}"
    if _is_mock(sie):
        return name
    model = ""
    try:
        if hasattr(sie, "configured") and not sie.configured():
            return None
        if hasattr(sie, "model"):
            model = str(sie.model("extract"))  # SIEConfigError when SIE_EXTRACT_MODEL is not set
    except Exception:
        return None
    return f"{name}:{model}"


async def read_offers(sie: Any, offers: list[Offer], *, labels: list[str] | None = None, limit: int = MAX_OFFERS_PER_LINE,
                      timeout_s: float = LINE_TIMEOUT_S) -> dict[str, Any]:
    """Fill `spec_reads` on up to `limit` offers. Returns {calls, cached, listings, reads, latency_ms, provider, ok}.

    Never raises. On any failure the offers keep whatever they had and the rules fall back to the title patterns.
    """
    stats: dict[str, Any] = {"calls": 0, "cached": 0, "listings": 0, "reads": 0, "latency_ms": 0, "provider": None, "ok": False}
    if sie is None or not hasattr(sie, "extract"):
        return stats
    key = _provider_key(sie)
    if key is None or time.monotonic() < _DOWN_UNTIL.get(key, 0.0):
        return stats
    mock = _is_mock(sie)
    stats["provider"] = "mock" if mock else "sie"
    labels = list(labels or (LABELS if mock else LIVE_LABELS))
    targets = [o for o in offers if not o.refused and (o.title or o.description)][:limit]
    sem = asyncio.Semaphore(CONCURRENCY)
    state = {"dead": False}
    latencies: list[float] = []
    spans_by_hash: dict[str, list[dict[str, Any]]] = {}
    texts: dict[str, str] = {}
    for o in targets:
        text = listing_text(o.title, o.description)
        h = hashlib.sha256(f"{key}|{'|'.join(labels)}|{text}".encode("utf-8")).hexdigest()
        texts.setdefault(h, text)

    async def one(h: str, text: str) -> None:
        async with sem:
            if state["dead"]:
                return
            stats["calls"] += 1
            t0 = time.perf_counter()
            try:
                spans = await sie.extract(text, labels)
            except Exception:
                state["dead"] = True
                return
            latencies.append((time.perf_counter() - t0) * 1000)
            spans_by_hash[h] = [dict(s) for s in (spans or []) if isinstance(s, dict)]

    todo = []
    for h, text in texts.items():
        if h in _CACHE:
            spans_by_hash[h] = _CACHE[h]
            stats["cached"] += 1
        else:
            todo.append(asyncio.ensure_future(one(h, text)))
    if todo:
        try:
            _done, pending = await asyncio.wait(todo, timeout=timeout_s)
            for t in pending:
                t.cancel()
                state["dead"] = True
        except Exception:
            state["dead"] = True
    if state["dead"]:
        _DOWN_UNTIL[key] = time.monotonic() + COOL_OFF_S
    for h in texts:
        if h in spans_by_hash and h not in _CACHE:
            if len(_CACHE) >= _CACHE_CAP:
                _CACHE.clear()
            _CACHE[h] = spans_by_hash[h]
    for o in targets:
        text = listing_text(o.title, o.description)
        h = hashlib.sha256(f"{key}|{'|'.join(labels)}|{text}".encode("utf-8")).hexdigest()
        if h not in spans_by_hash:
            continue
        try:
            o.spec_reads = to_reads(spans_by_hash[h], o.title, o.description, mock=mock)
        except Exception:
            continue
        stats["listings"] += 1
        stats["reads"] += len(o.spec_reads)
    stats["latency_ms"] = int(statistics.median(latencies)) if latencies else 0
    stats["ok"] = not state["dead"]
    return stats
