"""In-memory run store with a JSON snapshot on disk (runs/<run_id>.json). Owner: A. PLAN §3.2, §4.2.

`Run` is the working state of one run. B (checkout) and D (audit) read it through `get(run_id)`:

    run.mandate, run.bom, run.offers[bom_line_id], run.offer_index[offer_id], run.plans[tier],
    run.active_tier, run.pins, run.left_out(), run.records (the chain), run.closed_mandate,
    run.handoffs, run.cart_state, run.emit(...), run.record(...)

`to_state(run)` builds the `RunState` the frontend reads. Nothing here names a build type or a store.
"""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from app.audit.chain import GENESIS
from app.config import BACKEND_DIR, get_settings
from app.models import (
    BOMLine, CartPlan, Check, ClosedMandate, Event, Handoff, Intake, IntakeImage, KbChunk, Offer, OpenMandate,
    OwnedInfo, PhotoPart, ResolvedPart, RunSource, RunState, RunStats, RunTemplate, SourceDoc, Template, ViewData,
)

__all__ = ["Run", "Pins", "get", "get_run", "save_run", "create", "runs", "intakes", "now_iso", "new_id", "to_state", "RunNotFound"]

SNAPSHOT_DIR: Path | None = BACKEND_DIR / "runs"  # tests point this at a temp folder (or None)


class RunNotFound(KeyError):
    pass


def now_iso() -> str:
    """Current time as an ISO string with the local offset. Replay keeps the pinned clock."""
    s = get_settings()
    if s.demo_mode == "replay":
        return s.pinned_now
    return datetime.now().astimezone().isoformat(timespec="seconds")


def age_minutes(ts: str, now: str | None = None) -> float | None:
    try:
        a, b = datetime.fromisoformat(ts), datetime.fromisoformat(now or now_iso())
        if a.tzinfo is None or b.tzinfo is None:
            a, b = a.replace(tzinfo=None), b.replace(tzinfo=None)
        return (b - a) / timedelta(minutes=1)
    except (ValueError, TypeError):
        return None


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(5)}"


@dataclass
class Pins:
    """Cart edits the optimizer must respect (PLAN §3.10, §12.3)."""

    require: set[str] = field(default_factory=set)  # offer_ids the user swapped in (n >= 1)
    ban: set[str] = field(default_factory=set)  # offer_ids the user swapped out (n = 0)
    qty: dict[str, int] = field(default_factory=dict)  # bom_line_id -> edited quantity
    removed: dict[str, str] = field(default_factory=dict)  # bom_line_id -> reason (removed_by_you | owned)
    store: dict[str, str] = field(default_factory=dict)  # bom_line_id -> store_id ("move to another store")

    def copy(self) -> "Pins":
        return Pins(set(self.require), set(self.ban), dict(self.qty), dict(self.removed), dict(self.store))

    def to_dict(self) -> dict[str, Any]:
        return {"require": sorted(self.require), "ban": sorted(self.ban), "qty": dict(self.qty),
                "removed": dict(self.removed), "store": dict(self.store)}


@dataclass
class Run:
    run_id: str
    intake: Intake
    mandate: OpenMandate
    status: str = "running"
    answers: dict[str, str] = field(default_factory=dict)
    # inputs
    source: SourceDoc | None = None
    docs: dict[str, str] = field(default_factory=dict)  # doc_sha256 -> exact fetched text
    reference: dict[str, Any] | None = None
    template: Template | None = None
    template_sha256: str = ""
    template_sql: str = ""
    variant: str | None = None
    images: dict[str, IntakeImage] = field(default_factory=dict)
    photo_parts: list[PhotoPart] = field(default_factory=list)
    # pipeline state
    bom: list[BOMLine] = field(default_factory=list)
    line_meta: dict[str, dict[str, Any]] = field(default_factory=dict)  # row_id, rules, search_query, attrs, links
    resolved: dict[str, ResolvedPart] = field(default_factory=dict)
    kb: dict[str, list[KbChunk]] = field(default_factory=dict)
    owned: dict[str, OwnedInfo] = field(default_factory=dict)
    offers: dict[str, list[Offer]] = field(default_factory=dict)
    offer_index: dict[str, Offer] = field(default_factory=dict)
    offer_line: dict[str, str] = field(default_factory=dict)  # offer_id -> bom_line_id
    rejected: dict[str, dict[str, str]] = field(default_factory=dict)  # bom_line_id -> offer_id -> reason
    rejected_lines: list[dict[str, Any]] = field(default_factory=list)  # extraction_rejected bodies
    refusals: list[dict[str, Any]] = field(default_factory=list)
    checks: list[Check] = field(default_factory=list)
    fixes: list[dict[str, Any]] = field(default_factory=list)
    plans: dict[str, CartPlan] = field(default_factory=dict)
    active_tier: str = "cheapest"
    budget_cap: float | None = None
    pins: Pins = field(default_factory=Pins)
    edited_lines: set[str] = field(default_factory=set)
    decisions: dict[str, str] = field(default_factory=dict)  # bom_line_id -> record hash
    # trust
    events: list[Event] = field(default_factory=list)
    records: list[dict[str, Any]] = field(default_factory=list)
    head_hash: str = GENESIS
    approval_tokens: dict[str, str] = field(default_factory=dict)  # sha256(token) -> plan_sha256 (one-time)
    closed_mandate: ClosedMandate | None = None
    handoffs: list[Handoff] = field(default_factory=list)
    cart_state: str = "draft"
    stages: set[str] = field(default_factory=set)
    stats: RunStats = field(default_factory=RunStats)
    view: ViewData | None = None
    simulated: bool = False
    task: Any = None  # the asyncio task running the agent, if any

    # ------------------------------------------------------------------ lookups

    def line(self, bom_line_id: str) -> BOMLine | None:
        return next((ln for ln in self.bom if ln.bom_line_id == bom_line_id), None)

    def open_assumptions(self) -> list[str]:
        from app.pipeline.provenance import open_assumptions

        return open_assumptions(self.bom)

    def plan(self, tier: str | None = None) -> CartPlan | None:
        return self.plans.get(tier or self.active_tier)

    def budget(self) -> float:
        return float(self.mandate.constraints.budget_usd)

    # ------------------------------------------------------------------ timeline + chain

    def emit(self, type: str, title: str, severity: str = "info", **kw: Any) -> Event:
        """Append one SSE event (PLAN §4.2). `seq` is 1-based and dense."""
        ev = Event(seq=len(self.events) + 1, ts=now_iso(), severity=severity, type=type, title=title,
                   simulated=kw.pop("simulated", None) or (True if self.simulated else None),
                   **{k: v for k, v in kw.items() if v is not None})
        self.events.append(ev)
        return ev

    def record(self, kind: str, body: dict[str, Any]) -> dict[str, Any]:
        """Append one record to the hash chain (D's `audit.chain.append`, local fallback)."""
        from app.agent import ports

        rec = ports.chain_append(self, kind, body)
        self.head_hash = rec["hash"]
        return rec

    def refuse(self, refusal: dict[str, Any], title: str, *, bom_line_id: str | None = None,
               store_id: str | None = None, count: int = 1) -> dict[str, Any]:
        """Log a refusal: chain record, timeline event, counter. `refusal` is a RefusalRecord dict."""
        entry = {**refusal, "bom_line_id": bom_line_id, "store_id": store_id, "count": count}
        self.refusals.append(entry)
        rec = self.record("refusal", {k: v for k, v in refusal.items() if k != "kind"} | {"bom_line_id": bom_line_id, "store_id": store_id})
        self.emit("refusal", title, "refusal", bom_line_id=bom_line_id, store_id=store_id, record_hash=rec["hash"],
                  data={"refusal": refusal, "rule": refusal.get("rule"), "triggered_by": refusal.get("triggered_by"), "count": count})
        return entry


runs: dict[str, Run] = {}
intakes: dict[str, Intake] = {}
intake_meta: dict[str, dict[str, Any]] = {}  # intake_id -> {"set_by", "answered", "hits"}


def create(run: Run) -> Run:
    runs[run.run_id] = run
    return run


def get(run_id: str) -> Run:
    try:
        return runs[run_id]
    except KeyError:
        raise RunNotFound(run_id) from None


# ---------------------------------------------------------------------------- RunState


def _counts(bom: list[BOMLine]) -> dict[str, int]:
    out = {k: 0 for k in ("readme_quote", "reference_project", "template_row", "photo_region", "assumption")}
    for ln in bom:
        if ln.status != "removed":
            out[ln.provenance.type] += 1
    return out


def default_view(run: Run) -> ViewData:
    from app.pipeline.template import build_view

    return build_view(run.template, run.bom, run.line_meta, variant=run.variant, intake=run.intake)


def to_state(run: Run) -> RunState:
    src = run.source
    tpl = run.template
    return RunState(
        run_id=run.run_id, build_type=run.mandate.scope.build_type, build_type_set_by=run.mandate.scope.build_type_set_by,
        intake=run.intake, view=run.view or default_view(run), status=run.status, mandate=run.mandate,  # type: ignore[arg-type]
        source=RunSource(url=src.url, path=src.path, commit_sha=src.commit_sha, sha256=src.sha256, fetched_at=src.fetched_at, via=src.via, simulated=bool(src.simulated)) if src else None,
        template=RunTemplate(template_id=tpl.template_id, variant=run.variant, kb_ref=f"kb://{tpl.template_id}", sql=run.template_sql) if tpl else None,
        provenance_counts=_counts(run.bom), open_assumptions=run.open_assumptions(), bom=run.bom, checks=run.checks,  # type: ignore[arg-type]
        plans=run.plans, active_tier=run.active_tier, refusals=len(run.refusals), head_hash=run.head_hash, stats=run.stats,
        source_api="mock" if run.simulated else None, simulated=run.simulated,
    )


def get_run(run_id: str) -> RunState:
    """Look up a run as the `RunState` contract."""
    return to_state(get(run_id))


def save_run(state: RunState | Run) -> None:
    """Snapshot to runs/<run_id>.json (best effort: OneDrive may hold a lock)."""
    if SNAPSHOT_DIR is None:
        return
    st = to_state(state) if isinstance(state, Run) else state
    try:
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        (SNAPSHOT_DIR / f"{st.run_id}.json").write_text(
            json.dumps(st.model_dump(mode="json", by_alias=True), ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    except OSError:
        pass
