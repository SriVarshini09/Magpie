"""One adapter shape for every store source (PLAN §3.16). Owner: B.

`Offer`, `PartQuery` and `Handoff` are defined in app/models.py (the shared contract). This module adds
what every adapter shares: the run context, the "not configured" error, offer ids, evidence files,
and small text helpers (pack sizes, HTML stripping, registrable domains).

Listing text is data, never instructions. Nothing here interprets it beyond parsing numbers.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from app import fixtures
from app.config import BACKEND_DIR
from app.models import Offer, PartQuery

ACTION_RANK = {"agent_cart": 0, "prefilled_cart": 1, "product_link": 2}


@dataclass
class RunCtx:
    """What an adapter may know about the run. No buyer data, ever."""

    run_id: str
    allowed_merchants: tuple[str, ...] = ()
    ship_to_country: str = "US"
    demo_mode: str = "mock"
    bypass_cache: bool = False  # True only for the cart price refresh (PLAN §3.11)


@runtime_checkable
class StoreAdapter(Protocol):
    source_api: str  # shopify_ucp | serpapi:<engine> | adafruit | magento | digikey | jsonld | mock
    hosts: frozenset[str]  # the only hosts this adapter may request (enforced in stores/http.py)

    async def search(self, q: PartQuery, ctx: RunCtx) -> list[Offer]: ...

    async def refresh(self, offer: Offer, ctx: RunCtx) -> Offer | None:
        """Live price and stock for one offer; None if unsupported. May raise RefreshSkipped."""
        ...


class NotConfigured(NotImplementedError):
    """A live service that cannot run yet: a key, a CLI or a setting is missing.

    Same message shape as the scaffold TODOs ("TODO(B) — PLAN §…: …"), so the health dots and the 501
    bodies name who finishes it and where the spec is.
    """


def not_configured(plan: str, what: str) -> NotConfigured:
    return NotConfigured(f"TODO(B) — PLAN {plan}: {what}")


class RefreshSkipped(Exception):
    """A price refresh that was not attempted (quota, too recent, unsupported). The age stays visible."""


class AdapterError(RuntimeError):
    """A store source answered with something we cannot use. Never carries a key or a full URL query."""


def env_secret(name: str) -> str:
    """A secret from the environment, read at call time. Never log it."""
    return (os.getenv(name) or "").strip()


# --------------------------------------------------------------------------- time


def now() -> datetime:
    """Wall-clock time with the local offset. Tests monkeypatch this."""
    return datetime.now(timezone.utc).astimezone()


def now_iso() -> str:
    return now().isoformat(timespec="seconds")


def parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# --------------------------------------------------------------------------- ids and hashes


def sha256_hex(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def canonical(obj: Any) -> str:
    """Canonical JSON (sorted keys, no whitespace, UTF-8), the same format as audit/chain.py."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def make_offer_id(source_api: str, store_id: str, item_key: str) -> str:
    """Deterministic offer id: the same listing gets the same id in live, record and replay."""
    return "o_" + sha256_hex(f"{source_api}|{store_id}|{item_key}")[:12]


# --------------------------------------------------------------------------- evidence (PLAN §3.11)

_SECRET_KEYS = re.compile(
    r"^(api_?key|x-api-key|access_token|refresh_token|id_token|client_secret|client_id_secret|password|authorization|"
    r"cookie|set-cookie|secret|token|private_key)$",
    re.I,
)
_SECRET_VALUES = re.compile(r"\b(sk|rk|pk)_(test|live)_[A-Za-z0-9]+|\bsk-sie-[A-Za-z0-9_-]+|\bBearer\s+[A-Za-z0-9._~+/=-]+", re.I)
_SECRET_QUERY = re.compile(r"([?&](?:api_key|apikey|key|token|access_token|client_secret)=)[^&#\s\"]*", re.I)


def redact(obj: Any) -> Any:
    """Drop secret-looking keys and mask secret-looking values, recursively (evidence, cache, records)."""
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if isinstance(k, str) and _SECRET_KEYS.search(k):
                out[k] = "[redacted]"
            else:
                out[k] = redact(v)
        return out
    if isinstance(obj, list):
        return [redact(v) for v in obj]
    if isinstance(obj, str):
        return _SECRET_QUERY.sub(r"\1[redacted]", _SECRET_VALUES.sub("[redacted]", obj))
    return obj


EVIDENCE_DIR = BACKEND_DIR / "evidence"


def save_evidence(run_id: str, payload: Any) -> tuple[str, str]:
    """Write one raw store response to evidence/<run_id>/<sha256>.json. Returns (relative path, sha256).

    D owns app/audit/evidence.py; once its `write_evidence` is implemented it is used. Until then this
    writes the same layout itself. Secrets are stripped first, so the hash covers what is on disk.
    """
    clean = redact(payload)
    try:
        from app.audit import evidence as audit_evidence

        path, digest = audit_evidence.write_evidence(run_id, clean)
        return str(path), str(digest)
    except NotImplementedError:
        pass
    body = canonical(clean)
    digest = sha256_hex(body)
    safe_run = re.sub(r"[^A-Za-z0-9_.-]", "_", run_id or "adhoc")[:80]
    folder = EVIDENCE_DIR / safe_run
    target = folder / f"{digest}.json"
    if not target.exists():
        folder.mkdir(parents=True, exist_ok=True)
        _atomic_write(target, body)
    return f"evidence/{safe_run}/{digest}.json", digest


def _atomic_write(target: Path, text: str) -> None:
    tmp = target.with_suffix(target.suffix + f".{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    for attempt in range(5):  # OneDrive can hold a lock for a moment (CLAUDE.md §5)
        try:
            os.replace(tmp, target)
            return
        except PermissionError:
            if attempt == 4:
                raise
            import time

            time.sleep(0.2 * (attempt + 1))


# --------------------------------------------------------------------------- text helpers

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def strip_html(text: str | None, limit: int = 2000) -> str | None:
    """Plain text from a listing's HTML description. Data only: we never act on it."""
    if not text:
        return None
    plain = _WS.sub(" ", html.unescape(_TAG.sub(" ", text))).strip()
    return plain[:limit] or None


_PACK_PATTERNS = (
    re.compile(r"\bpack\s+of\s+(\d{1,3})\b", re.I),
    re.compile(r"\b(\d{1,3})\s*-?\s*(?:pcs|pc|pieces|piece|pack|pk|count|ct)\b", re.I),
    re.compile(r"\b(\d{1,3})\s*x\s+(?=[a-z])", re.I),
)
_SINGLE = re.compile(r"\b(single|1\s*pc|1\s*piece|one\s+piece)\b", re.I)


def parse_pack_units(*texts: str | None) -> int:
    """Units in one listing ("5 Pieces(14.99/pcs)" -> 5, "Single Piece" -> 1). 1 when not stated.

    The first text that states a size wins (variant option label first, then the title).
    """
    for text in texts:
        if not text:
            continue
        if _SINGLE.search(text):
            return 1
        for pat in _PACK_PATTERNS:
            m = pat.search(text)
            if m:
                n = int(m.group(1))
                if 1 <= n <= 100:
                    return n
    return 1


_TWO_LEVEL_SUFFIXES = {"co.uk", "org.uk", "ac.uk", "com.au", "net.au", "co.jp", "co.nz", "com.br", "com.mx", "co.in", "com.cn", "com.sg", "com.hk", "co.kr"}


def registrable_domain(host: str) -> str:
    """Approximate registrable domain ("shop.wowrobo.com" -> "wowrobo.com"). No public-suffix list needed here."""
    host = (host or "").strip(".").lower()
    parts = host.split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in _TWO_LEVEL_SUFFIXES:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def slug(text: str, limit: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:limit] or "unknown"


_ZERO_DECIMAL = {"JPY", "KRW", "VND", "CLP", "ISK", "HUF", "TWD", "UGX", "XAF", "XOF", "PYG", "RWF", "KMF", "GNF", "BIF", "DJF", "MGA", "VUV", "XPF"}


def minor_to_major(amount: Any, currency: str | None) -> float | None:
    """UCP amounts are integers in minor units; JPY and friends are zero-decimal (SD §3)."""
    try:
        value = float(amount)
    except (TypeError, ValueError):
        return None
    if (currency or "").upper() in _ZERO_DECIMAL:
        return round(value, 2)
    return round(value / 100.0, 2)


def to_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    m = re.search(r"-?\d[\d,]*(?:\.\d+)?", str(value))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def to_int(value: Any) -> int | None:
    f = to_float(value)
    return int(f) if f is not None else None


def apply_mandate(offers: list[Offer], allowed_merchants: tuple[str, ...] | list[str]) -> list[Offer]:
    """Mark offers from stores outside the mandate as refused (kept as evidence, PLAN §3.16 rule 1).

    The guard (A) is the authority; this helper only labels rows for the part panel.
    """
    allowed = set(allowed_merchants)
    if not allowed:
        return offers
    return [o if o.store_id in allowed else o.model_copy(update={"refused": "merchant_not_in_mandate"}) for o in offers]


# --------------------------------------------------------------------------- mock adapters

_PIPELINE_RUN_ID = re.compile(r"r_[0-9a-f]{10}$")  # runstate.new_id: a run made by the real pipeline
_WORD = re.compile(r"[a-z0-9]+")
_STOP = frozenset({"a", "an", "the", "and", "or", "of", "for", "with", "pcs", "pc", "set"})


def _words(text: str | None) -> set[str]:
    out = set()
    for w in _WORD.findall((text or "").lower()):
        if w in _STOP:
            continue
        out.add(w[:-1] if len(w) > 3 and w.endswith("s") else w)
    return out


def _fixture_catalog() -> list[tuple[str, str, str, set[str]]]:
    """[(fixture key, line id, normalised name, name words)] for every fixture BOM line."""
    out = []
    for key in ("so101", "drone"):
        for ln in fixtures.load(f"run_{key}.json")["bom"]:
            name = ln["raw_name"]
            out.append((key, ln["bom_line_id"], " ".join(sorted(_words(name))), _words(name)))
    return out


def truthful_level(offer: Offer) -> Offer:
    """The offer with the action level its hand-off will really use: the registry level after the same downgrades a
    live adapter applies (PLAN §3.16 rule 2: no item id, a cart link no human has opened). A fixture offer was written
    with the level its store promises; in a pipeline run the parts list, the part panel, the cart and the hand-off
    must all say the same thing, so the fixture's level is never shown as-is there."""
    from app.stores import registry as store_registry
    from app.stores.cartlinks import ID_KEYS

    promised = store_registry.registry_level(offer.store_id)
    if promised == "agent_cart":
        has_ids = bool(offer.ids.get("variant_gid"))
    elif promised == "prefilled_cart":
        has_ids = bool(offer.ids.get(ID_KEYS.get(offer.store_id, "")))
    else:
        has_ids = True
    level, reason = store_registry.effective_level(offer.store_id, has_item_ids=has_ids, qty=1)
    return offer.model_copy(update={"action_level": level, "downgrade_reason": reason})


def mock_refresh(offer: Offer, ctx: RunCtx) -> Offer:
    """A mock re-read: same price and stock. In a pipeline run it is seen now, so the 15-minute rule can be met."""
    return offer.model_copy(update={"seen_at": now_iso()}) if _PIPELINE_RUN_ID.match(ctx.run_id) else offer


def fixture_line(q: PartQuery, ctx: RunCtx) -> tuple[str, str] | None:
    """Which fixture BOM line a mock adapter answers for: (fixture key, line id), or None.

    Fixture runs (r_mock_*, hero_*, tests) keep the scaffold rule: the run id picks the fixture and the line id
    is the fixture's. A run made by the real pipeline (DEMO_MODE=live with mock stores) has its own line ids, so
    the part is looked up by NAME: the same name first, else a fixture line whose every name word is in the
    part's name or query. A drone motor never gets an arm servo's offers because both happen to be "b1".
    """
    if not _PIPELINE_RUN_ID.match(ctx.run_id):
        return ("drone" if "drone" in ctx.run_id else "so101"), q.bom_line_id
    catalog = _fixture_catalog()
    wanted = _words(q.name or q.query)
    same = " ".join(sorted(wanted))
    for key, line_id, norm, _ in catalog:
        if norm == same:
            return key, line_id
    wide = wanted | _words(q.query)
    extra = _extra_line(wanted, wide)  # an exact name in the extra catalog beats a partial match on a hero fixture
    if extra is not None:
        return extra
    best: tuple[int, str, str] | None = None
    for key, line_id, _, words in catalog:
        if words and words <= wide and (best is None or len(words) > best[0]):
            best = (len(words), key, line_id)
    return (best[1], best[2]) if best else None


EXTRA_KEY = "electronics"  # data/mock_catalog_electronics.json: electronics_mcu, generic and esp32-weather-epd parts


def _extra_catalog() -> dict[str, Any]:
    from app.config import DATA_DIR

    return json.loads((DATA_DIR / "mock_catalog_electronics.json").read_text(encoding="utf-8"))


def _extra_line(wanted: set[str], wide: set[str]) -> tuple[str, str] | None:
    """The extra catalog, consulted only when the arm and drone fixtures have nothing: exact name (words in any order),
    and when the entry has `query_any`, one of those words in the part's name or query. Never a partial-name guess."""
    same = " ".join(sorted(wanted))
    for entry in _extra_catalog()["lines"]:
        if entry.get("extends"):
            continue  # extra listings for a hero line (e.g. 5-inch drone parts): served with that line, never alone
        if same not in {" ".join(sorted(_words(n))) for n in entry["names"]}:
            continue
        if entry.get("query_any") and not wide & {w.lower() for w in entry["query_any"]}:
            continue
        return EXTRA_KEY, entry["line_id"]
    return None


def _alpha(words: set[str]) -> set[str]:
    return {w for w in words if len(w) >= 3 and any(c.isalpha() for c in w)}


def _query_fits(q: PartQuery, key: str, line_id: str, rows: list[dict[str, Any]]) -> bool:
    """A mock line answers a query only if the query shares a real word with that line's names or listing titles.

    The mock catalog is matched by part NAME; a live store searches the QUERY. When the two disagree (an assumption
    edited to "speaker driver" on a line named "Motor or actuator") the mock must not return the old part."""
    wanted = _alpha(_words(q.query))
    if not wanted:
        return True
    if key == EXTRA_KEY:
        names = next((e["names"] for e in _extra_catalog()["lines"] if e["line_id"] == line_id), [])
    else:
        names = [ln["raw_name"] for ln in fixtures.load(f"run_{key}.json")["bom"] if ln["bom_line_id"] == line_id]
    vocab: set[str] = set()
    for text in [*names, q.name or "", *(r.get("title") or "" for r in rows)]:
        vocab |= _alpha(_words(text))
    return bool(wanted & vocab)


class FixtureAdapter:
    """Base for every Mock adapter: offers from fixtures/offers_*.json that stand in for `stands_for`.

    Every offer it returns has source_api == "mock" and simulated is True.
    """

    source_api = "mock"
    hosts: frozenset[str] = frozenset()  # a mock adapter requests nothing
    stands_for: tuple[str, ...] = ()

    async def search(self, q: PartQuery, ctx: RunCtx) -> list[Offer]:
        target = fixture_line(q, ctx)
        if target is None:
            return []  # the mock catalog has nothing for this part: "no offers found", never a wrong part
        key, line_id = target
        # the simulated store's own listings (mock_of "mock") have no adapter of their own: in a pipeline run the
        # agent-cart mock serves them, so that store is searchable like any other
        pipeline = bool(_PIPELINE_RUN_ID.match(ctx.run_id))
        stands_for = (*self.stands_for, "mock") if "shopify_ucp" in self.stands_for and pipeline else self.stands_for
        out = []
        rows = _extra_catalog()["offers"] if key == EXTRA_KEY else fixtures.load(f"offers_{key}.json")
        if pipeline and key != EXTRA_KEY:
            # more listings for the same part from the extra catalog (other sizes): the rules pick the one that fits
            # A live store searches the query, so an extra listing answers only a query that asks for it: its
            # query_any words (e.g. "30x30", "xt60") must appear. A 3-inch build's "AIO ... 25.5mm" never gets a
            # 5-inch 30x30 stack.
            extra = _extra_catalog()
            asked = _words(q.query)
            ext = {e["line_id"] for e in extra["lines"] if e.get("extends") == f"{key}:{line_id}"
                   and (not e.get("query_any") or asked & {w.lower() for w in e["query_any"]})}
            if ext:
                rows = [*rows, *({**r, "bom_line_id": line_id} for r in extra["offers"] if r.get("bom_line_id") in ext)]
        if pipeline and not _query_fits(q, key, line_id, [r for r in rows if r.get("bom_line_id") == line_id]):
            return []  # e.g. the person edited the spec to something this mock line is not: "no offers", never a wrong part
        for raw in rows:
            line = raw.pop("bom_line_id", None)
            if line == line_id and (raw.get("mock_of") or "").startswith(stands_for):
                if pipeline:
                    raw["seen_at"] = now_iso()  # the mock store "answered" now; the fixture's clock is the sample run's
                    out.append(truthful_level(Offer.model_validate(raw)))
                else:
                    out.append(Offer.model_validate(raw))
        return out

    async def refresh(self, offer: Offer, ctx: RunCtx) -> Offer | None:
        return mock_refresh(offer, ctx)
