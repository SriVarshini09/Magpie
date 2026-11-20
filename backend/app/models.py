"""Shared contracts: the single source of truth (PLAN §3.7, §3.16, §3.18, §3.19, §3.20, §4.2, §12.4).

SHARED FILE, owned by the coordinator (OWNERSHIP.md). Builders do not edit it: list the
change you need in your final report.

`frontend/src/lib/types.ts` is GENERATED from this file:

    cd backend && uv run python scripts/gen_types.py

and `tests/test_contract_parity.py` fails when the two drift apart.

Conventions
- Timestamps and dates are ISO-8601 strings (the wire format), never datetime objects.
- Money is a float in USD unless the field name ends in `_cents`.
- `None` means "not known / not quoted". It is never a guess (PLAN §3.16 rule 4).
- Mock data is always labelled: `source_api == "mock"` and `simulated is True`.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

CONTRACT_VERSION = "0.4"  # mandate and record version (PLAN "What changed from v3", item 12)


class Model(BaseModel):
    """Base for every contract model: unknown fields are an error, aliases round-trip."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


# --------------------------------------------------------------------------- aliases

ActionLevel = Literal["agent_cart", "prefilled_cart", "product_link"]
BuildType = Literal["robot_arm", "quadcopter", "rc_car", "claw_gripper", "electronics_mcu", "generic"]
DemoMode = Literal["mock", "live", "record", "replay"]
ProvenanceType = Literal["readme_quote", "reference_project", "template_row", "photo_region", "assumption"]
LineKind = Literal["part", "tool", "optional"]
BomStatus = Literal[
    "extracted", "resolved", "owned", "offers", "chosen", "warning",
    "needs_human", "not_found", "skipped", "removed",
]
Stock = Literal["in_stock", "out_of_stock", "unknown"]
Condition = Literal["new", "used", "unknown"]
OfferStatus = Literal["chosen", "alternative", "rejected", "refused"]
ResolveMethod = Literal["exact_from_source", "kb", "llm_inferred"]
# PLAN §4.2 lists pass|warn|fail; §3.6 and §3.8 require `needs_human` for a missing attribute.
CheckResult = Literal["pass", "warn", "fail", "needs_human"]
Severity = Literal["info", "ok", "warn", "refusal", "error"]
# `fallback`: the live class runs on its keyless fallback (SingleStore -> SQLite with no S2_URL; GitHub -> raw fetch
# with no token). Real data, not the sponsor service.
HealthState = Literal["ok", "down", "off", "mock", "fallback"]
ViewKind = Literal["urdf", "procedural", "diagram", "kit", "generated"]
ViewModel = Literal["so101", "quadcopter", "rc_car", "claw"]
PartCategory = Literal[
    "board", "motor", "esc_driver", "battery", "power", "sensor",
    "camera", "radio", "cable", "mechanical", "printed", "tool",
]
CartState = Literal["draft", "approved", "checking_out", "complete"]
HandoffState = Literal["ready", "opened", "done", "skipped"]
DoneVia = Literal["user", "checkout_kit"]
StoreTestState = Literal["queued", "card_issued", "authorized", "declined", "settled"]
LeftOutReason = Literal["owned", "removed_by_you", "print_at_home", "not_found"]
RunStatus = Literal["running", "waiting_approval", "approved", "done", "error"]
SetBy = Literal["classifier", "user"]
FetchedVia = Literal["airbyte.github", "http", "keenable", "exa_airbyte"]
FoundVia = Literal["keenable", "exa_airbyte", "claude_web_search", "github_search", "template"]
Detector = Literal["sie:grounding-dino-base", "claude_vision"]
RefusalRule = Literal[
    "merchant_allowed", "data_sharing", "action_allowed", "budget", "approval_required",
    "unknown_offer", "host_not_allowed", "stale_price", "assumption_unconfirmed",
    "reference_host_not_allowed", "photo_not_shared", "scope_mismatch",
]
TriggeredBy = Literal["source_document", "user_chat", "store_listing", "agent", "user_edit"]
AssumptionAction = Literal["confirm", "edit", "remove"]
CartEditOp = Literal["swap_offer", "move_store", "remove", "restore", "set_qty"]
EventProvider = Literal[
    "airbyte", "singlestore", "sie", "cognee", "shopify", "serpapi", "digikey",
    "stripe_test", "claude", "keenable", "exa_airbyte", "github", "huggingface",
]
EventType = Literal[
    "run.started", "mandate.opened", "source.fetched", "bom.line", "kb.search", "spec.resolved",
    "owned.matched", "offers.found", "offer.rejected", "compat.check", "compat.fix", "plan.ready",
    "plan.changed", "cart.edited", "price.refreshed", "refusal", "approval.granted", "mandate.closed",
    "handoff.created", "handoff.opened", "handoff.done",
    "pay.hold_placed", "pay.card_issued", "pay.authorized", "pay.declined", "pay.captured",
    "memory.written", "agent.message", "run.waiting_approval", "run.done", "error",
    "intake.classified", "intake.answered", "template.loaded", "reference.searched", "reference.found",
    "photo.parts", "assumption.opened", "assumption.resolved", "view.ready",
]
RecordKind = Literal[
    "intake", "template_load", "reference_search", "photo_parts", "assumption", "mandate_open",
    "source_fetch", "kb_search", "part_decision", "refusal", "extraction_rejected", "compat_fix", "plan",
    "cart_edit", "price_refresh", "approval", "mandate_closed", "cart_action", "handoff",
    "payment_mandate", "payment_hold", "issuing_card", "issuing_authorization", "payment_capture",
    "memory_write",
]

BoxXyxy = tuple[float, float, float, float]
Vec3 = tuple[float, float, float]


# --------------------------------------------------------------------------- provenance (§3.18)


class QuoteSpan(Model):
    """A second quote on the same line (e.g. a table row that points to another section, §3.9)."""

    quote: str
    span: tuple[int, int]
    line_from: int
    line_to: int


class ProvenanceBase(Model):
    check: Literal["pass", "fail"] = "pass"
    supports: list[Provenance] = []


class ReadmeQuoteProvenance(ProvenanceBase):
    type: Literal["readme_quote"]
    url: str
    path: str
    commit_sha: str
    via: FetchedVia
    quote: str  # exact substring of the fetched document
    span: tuple[int, int]  # character offsets in the fetched text
    line_from: int
    line_to: int
    doc_sha256: str
    more_quotes: list[QuoteSpan] = []


class ReferenceProjectProvenance(ProvenanceBase):
    type: Literal["reference_project"]
    url: str
    title: str
    licence: str | None = None
    quote: str
    span: tuple[int, int]
    doc_sha256: str
    fetched_at: str
    found_via: FoundVia
    fetched_via: FetchedVia


class TemplateRowProvenance(ProvenanceBase):
    type: Literal["template_row"]
    kb_ref: str  # kb://tpl_quadcopter#motor
    template_id: str
    row_id: str
    variant: str | None = None
    template_sha256: str
    basis: Literal["reference", "rule_of_thumb"]
    derived_from: str | None = None


class PhotoRegionProvenance(ProvenanceBase):
    type: Literal["photo_region"]
    image_id: str
    image_sha256: str
    box_xyxy_px: BoxXyxy
    label: str
    score: float
    detector: Detector


class AssumptionProvenance(ProvenanceBase):
    type: Literal["assumption"]
    statement: str
    basis: str
    confirmed_by_user: bool = False
    confirmed_at: str | None = None


Provenance = Annotated[
    Union[
        ReadmeQuoteProvenance,
        ReferenceProjectProvenance,
        TemplateRowProvenance,
        PhotoRegionProvenance,
        AssumptionProvenance,
    ],
    Field(discriminator="type"),
]


# --------------------------------------------------------------------------- offers, checks, plan


class Rerank(Model):
    provider: str
    model: str
    score: float
    latency_ms: int


class SpecRead(Model):
    """One spec read from a listing's title or description by SIE `extract` (PLAN §3.15). The rules judge `value`.

    `text` is the span as the listing wrote it ("30.5x30.5 mm"); `value` is our normalized form ("30x30").
    provider "mock" is the local pattern reader that stands in for SIE when no SIE key is set (labelled in the UI).
    """

    attr: str  # the attribute the rules read: mount_mm | prop_in | stator | cells | capacity_mah | connector | current_a | voltage_v | kv
    value: str
    text: str
    label: str  # the SIE label that found it, e.g. "mounting pattern"
    score: float | None = None
    start: int | None = None
    end: int | None = None
    field: Literal["title", "description"] = "title"
    provider: Literal["sie", "mock"]
    model: str
    simulated: bool = False


class Offer(Model):
    """One listing from one store adapter (PLAN §3.16 `stores/base.py`)."""

    offer_id: str
    store_id: str
    store_name: str
    seller_name: str | None = None
    title: str
    description: str | None = None
    url: str
    price_usd: float
    currency: str = "USD"
    units_per_pack: int = 1
    tier_prices: list[dict[str, Any]] | None = None
    shipping_usd: float | None = None
    eta_text: str | None = None
    eta_date: str | None = None
    stock: Stock = "unknown"
    condition: Condition = "unknown"
    rating: float | None = None
    reviews: int | None = None
    ids: dict[str, str] = {}  # variant_gid | asin | walmart_id | bestbuy_sku | digikey_pn | ebay_item | sku
    action_level: ActionLevel
    downgrade_reason: str | None = None
    source_api: str  # shopify_ucp | serpapi:<engine> | adafruit | magento | digikey | jsonld | mock
    mock_of: str | None = None  # the source_api a mock offer stands in for
    seen_at: str
    evidence_path: str | None = None
    evidence_sha256: str
    rerank: Rerank | None = None
    spec_reads: list[SpecRead] = []  # specs SIE extract read from the listing; the rules prefer these to title patterns
    refused: str | None = None  # e.g. "merchant_not_in_mandate"
    simulated: bool = False


class OfferRow(Model):
    """One row of the part panel's "every store" table (PLAN §4.2)."""

    offer_id: str
    store_id: str
    store_name: str
    seller_name: str | None = None
    title: str
    url: str
    price_usd: float
    units_per_pack: int
    packs_needed: int
    line_usd: float
    shipping_usd: float | None = None  # null or absent renders "not quoted"
    eta_text: str | None = None
    stock: Stock
    rating: float | None = None
    reviews: int | None = None
    action_level: ActionLevel
    downgrade_reason: str | None = None
    source_api: str
    mock_of: str | None = None
    seen_at: str
    evidence_sha256: str
    status: OfferStatus
    reason: str | None = None  # rejected: "R2: 2 A < 5 A"; refused: "constraints.allowed_merchants"
    rerank_score: float | None = None
    vs_chosen_usd: float | None = None
    spec_reads: list[SpecRead] = []
    simulated: bool = False


class Check(Model):
    rule_id: str
    result: CheckResult
    message: str
    fix: str | None = None
    kb_refs: list[str] = []
    bom_line_ids: list[str] = []
    needs_ack: bool = False  # must be acknowledged before Approve (R10, Statsig gate, §3.15)


class PlanLine(Model):
    bom_line_id: str
    offer_id: str
    store_id: str
    packs: int
    qty: int
    line_usd: float


class CartPlan(Model):
    """Optimizer output for one tier (PLAN §3.10; `Plan` in §4.2)."""

    plan_id: str
    tier: str
    total_usd: float
    stores: list[str]
    checkouts: int
    by_level: dict[ActionLevel, int]
    items_by_hand: int
    feasible: bool
    over_budget_by: float | None = None
    plan_sha256: str | None = None
    lines: list[PlanLine] = []
    simulated: bool = False


# --------------------------------------------------------------------------- BOM


class ChosenOffer(Model):
    offer_id: str
    store_id: str
    store_name: str
    action_level: ActionLevel
    title: str
    packs: int
    price: float
    url: str
    seen_at: str
    source_api: str = "mock"
    simulated: bool = False


class BOMLine(Model):
    """One bill-of-materials line. No provenance, no line (PLAN §3.18)."""

    bom_line_id: str  # b1…bn in source order
    raw_name: str
    qty: int
    qty_note: str | None = None  # "1 set", "2 CW + 2 CCW"
    provenance: Provenance
    line_kind: LineKind
    status: BomStatus
    category: PartCategory | None = None
    mesh_keys: list[str] = []
    spec: str | None = None
    confidence: float | None = None
    owned_note: str | None = None
    stores_count: int | None = None
    chosen: list[ChosenOffer] | None = None


class TrustedContext(Model):
    provider: str
    kb_ref: str
    query: str
    snippet: str
    score: float


class ResolvedPart(Model):
    spec: str
    attrs: dict[str, str] = {}
    confidence: float
    method: ResolveMethod
    trusted_context: list[TrustedContext] = []


class PartQuery(Model):
    """What a store adapter is asked to find (PLAN §3.16)."""

    bom_line_id: str
    query: str
    name: str | None = None  # the BOM line's own name (the mock catalog matches on it)
    spec: str | None = None
    qty: int = 1
    attrs: dict[str, str] = {}
    ship_to_country: str = "US"


class SourceDoc(Model):
    """Result of `ingest_source` (PLAN §3.6)."""

    id: str
    url: str
    path: str
    commit_sha: str
    text: str
    sha256: str
    fetched_at: str
    via: FetchedVia
    source_api: str | None = None
    simulated: bool = False


class PhotoPart(Model):
    """A part seen in the user's photo (PLAN §3.6 `identify_parts`)."""

    label: str
    category: str
    box_xyxy_px: BoxXyxy
    score: float
    detector: str


# --------------------------------------------------------------------------- mandates (§3.7, §12.4)


class Signature(Model):
    alg: str = "ES256"
    kid: str = "demo-key-1"
    jws: str


class MandateInputs(Model):
    source_url: str | None = None
    text_sha256: str | None = None
    image_sha256: list[str] = []


class MandateScope(Model):
    build_type: BuildType
    build_type_set_by: SetBy
    goal: str
    intake_sha256: str
    inputs: MandateInputs
    template_id: str
    reference_search: bool = True


class DataSharing(Model):
    country: bool = True
    postal_code: bool = False
    street_address: bool = False
    email: bool = False
    phone: bool = False
    name: bool = False
    photo_to_models: bool = False


class MandateActions(Model):
    search: bool = True
    create_cart: bool = True
    build_cart_link: bool = True
    checkout: bool = False
    pay: bool = False  # false for the agent in every mode
    message_seller: bool = False


class MandateConstraints(Model):
    budget_usd: float
    deadline: str
    ship_to_country: str = "US"
    allowed_merchants: list[str]
    data_sharing: DataSharing
    actions: MandateActions


class OpenMandate(Model):
    type: Literal["b2c.mandate.open"] = "b2c.mandate.open"
    version: str = CONTRACT_VERSION
    note: str = "AP2-inspired (v0.2 open Checkout Mandate shape); not AP2-compliant"
    mandate_id: str
    run_id: str
    user_id: str = "demo_user"
    created_at: str
    expires_at: str
    scope: MandateScope
    constraints: MandateConstraints
    signature: Signature
    simulated: bool = False


class HandoffItem(Model):
    offer_id: str
    ids: dict[str, str] = {}
    title: str
    qty: int
    unit_price_usd: float
    seen_at: str
    source_api: str
    evidence_sha256: str
    edited_by_user: bool = False


class Handoff(Model):
    """One hand-off per store (PLAN §3.6 `create_carts`, §3.7 closed mandate)."""

    store_id: str
    action_level: ActionLevel
    cart_id: str | None = None
    url: str
    url_sha256: str
    subtotal_usd: float
    caveat: str | None = None
    items: list[HandoffItem]
    simulated: bool = False


class StepUp(Model):
    provider: str
    inquiry_id: str
    status: str


class ClosedMandate(Model):
    type: Literal["b2c.mandate.closed"] = "b2c.mandate.closed"
    version: str = CONTRACT_VERSION
    open_mandate_sha256: str
    plan_id: str
    plan_sha256: str
    tier: str
    handoffs: list[Handoff]
    total_usd: float
    prices_checked_at: str
    approved_by: Literal["ui_button"] = "ui_button"
    approved_at: str
    approval_token_sha256: str
    chain_head: str
    step_up: StepUp | None = None
    signature: Signature
    simulated: bool = False


class Amount(Model):
    amount: int  # cents
    currency: str = "usd"


class UserConsent(Model):
    at: str
    text_shown: str


class PaymentInstrument(Model):
    kind: str = "issuing_card_test"
    id: str
    last4: str


class PaymentAllocation(Model):
    store_id: str
    action_level: ActionLevel
    url_sha256: str
    limit: int  # cents
    instrument: PaymentInstrument | None = None
    authorization_id: str | None = None
    simulated: Literal[True] = True  # authorizations are simulated in every mode
    status: str


class PaymentSummary(Model):
    provider: Literal["stripe_test"] = "stripe_test"
    payment_intent: str
    authorized: int  # cents
    captured: int
    released: int


class PaymentMandate(Model):
    """Tier 2 only. TEST MODE: no real money moves (PLAN §12.4)."""

    type: Literal["b2c.mandate.payment"] = "b2c.mandate.payment"
    version: str = CONTRACT_VERSION
    mode: Literal["test"] = "test"
    mandate_id: str
    closed_mandate_sha256: str
    status: Literal["open", "funded", "executing", "closed"]
    user_consent: UserConsent
    total: Amount
    allocations: list[PaymentAllocation]
    payment: PaymentSummary | None = None
    mandate_hash: str
    signature: Signature | None = None
    simulated: Literal[True] = True


# --------------------------------------------------------------------------- audit chain (§3.7)


class ChainRecord(Model):
    """Any record in the hash chain. Extra keys carry the record body.

    hash = sha256(prev_hash + canonical_json(record without `hash`)); see app/audit/chain.py.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    run_id: str
    seq: int
    ts: str
    kind: RecordKind
    prev_hash: str
    hash: str


class RefusalAttempt(Model):
    tool: str | None = None
    field: str | None = None
    value: str | None = None


class RefusalRecord(Model):
    kind: Literal["refusal"] = "refusal"
    rule: RefusalRule
    attempted: RefusalAttempt
    clause: str
    triggered_by: TriggeredBy
    ts: str


class DecisionPart(Model):
    bom_line_id: str
    raw_name: str
    qty: int
    line_kind: LineKind
    provenance: Provenance


class OwnedCheck(Model):
    provider: Literal["cognee", "owned_parts"]
    matched: str | None = None
    action: Literal["keep", "remove"]


class Candidate(Model):
    offer_id: str
    store_id: str
    action_level: ActionLevel
    url: str
    title: str
    price: float
    currency: str = "USD"
    units_per_pack: int = 1
    shipping: float | None = None
    eta: str | None = None
    stock: Stock = "unknown"
    rating: float | None = None
    reviews: int | None = None
    seen_at: str
    source_api: str
    evidence_path: str | None = None
    evidence_sha256: str
    rerank: Rerank | None = None
    simulated: bool = False


class RejectedOffer(Model):
    offer_id: str
    reason: str


class MandateCheck(Model):
    rule: RefusalRule
    result: Literal["allowed", "refused"]
    attempted: str
    clause: str


class CompatibilityResult(Model):
    rule_id: str
    result: CheckResult
    message: str
    kb_ref: str | None = None
    fix: str | None = None


class ChosenPack(Model):
    offer_id: str
    packs: int


class Decision(Model):
    chosen: list[ChosenPack]
    tier: str
    reason_codes: list[str]
    explanation: str
    edited_by_user: bool = False


class ModelUsage(Model):
    name: str
    input_tokens: int = 0
    output_tokens: int = 0


class DecisionRecord(Model):
    """One per part; the part panel is built from it (PLAN §3.7)."""

    run_id: str
    seq: int
    ts: str
    kind: Literal["part_decision"] = "part_decision"
    part: DecisionPart
    resolution: ResolvedPart
    owned_check: OwnedCheck
    candidates: list[Candidate]
    rejected: list[RejectedOffer]
    mandate_checks: list[MandateCheck]
    compatibility: list[CompatibilityResult]
    decision: Decision
    model: ModelUsage
    prev_hash: str
    hash: str
    simulated: bool = False


# --------------------------------------------------------------------------- intake (§3.17)


class Chip(Model):
    value: str
    label: str


class IntakeQuestion(Model):
    id: str
    text: str
    chips: list[Chip]
    default: str
    answer: str | None = None


class IntakeImage(Model):
    image_id: str
    url: str
    w: int
    h: int
    sha256: str


class IntakeInputs(Model):
    text: str | None = None
    source_url: str | None = None
    images: list[IntakeImage] = []


class IntakeConstraints(Model):
    budget_usd: float | None = None
    size_class: str | None = None


class BuildTypeAlternative(Model):
    build_type: BuildType
    confidence: float


class MandatePreset(Model):
    """Prefills the mandate form (also the `mandate` body of POST /api/runs)."""

    budget_usd: float
    deadline: str
    ship_to_country: str = "US"
    allowed_merchants: list[str]
    data_sharing: DataSharing


class Intake(Model):
    """Result of POST /api/intake and POST /api/intake/{id}/answers."""

    intake_id: str
    ready: bool
    summary: str
    build_type: BuildType
    confidence: float
    alternatives: list[BuildTypeAlternative] = []
    inputs: IntakeInputs
    constraints: IntakeConstraints
    questions: list[IntakeQuestion] = []  # 0–3
    visible_parts: list[PhotoPart] | None = None
    template_id: str
    mandate_preset: MandatePreset
    source_api: str | None = None
    simulated: bool = False


class IntakeRequest(Model):
    """Documentation of the multipart form of POST /api/intake (fields, not JSON)."""

    text: str | None = None
    run_id: str | None = None
    image_count: int = 0  # `images[]`: ≤ UPLOAD_MAX_IMAGES files, JPEG/PNG/WebP, ≤ UPLOAD_MAX_MB each


class IntakeAnswersRequest(Model):
    answers: dict[str, str] = {}
    build_type: BuildType | None = None
    skip_defaults: bool | None = None


# --------------------------------------------------------------------------- view data (§3.20, §13.7)


class ViewPart(Model):
    mesh: str
    bom_line_id: str
    instances: int = 1
    explode: Vec3 = (0, 0, 0)
    order: int = 0


class ViewEdge(Model):
    from_: str = Field(alias="from")
    to: str
    label: str
    rule_ids: list[str] = []


class PhotoRegion(Model):
    bom_line_id: str | None = None
    box_xyxy_px: BoxXyxy
    label: str
    score: float
    approximate: bool  # true for Claude's own coordinates (drawn dashed)


class PhotoView(Model):
    """Photo hotspots: the user's photo with one clickable box per part."""

    image_id: str
    url: str
    w: int
    h: int
    sha256: str
    regions: list[PhotoRegion]


class DiagramNode(Model):
    id: str
    bom_line_id: str | None = None  # null for the centre project node
    label: str
    icon: str  # lucide icon name
    x: float
    y: float
    w: float
    h: float


class DiagramData(Model):
    """2D board diagram layout (PLAN §13.7). Edges are `ViewData.edges`."""

    nodes: list[DiagramNode]
    tray: list[str] = []  # bom_line_ids with no node


class KitToken(Model):
    bom_line_id: str
    category: PartCategory
    qty: int = 1
    label: str


class ViewData(Model):
    kind: ViewKind
    model: ViewModel | None = None  # urdf and procedural
    variant: str | None = None
    scale: float | None = None
    urdf_url: str | None = None  # urdf: served from frontend/public
    parts: list[ViewPart] = []
    edges: list[ViewEdge] | None = None  # diagram
    diagram: DiagramData | None = None  # diagram: designed layout; absent means auto layout
    tokens: list[KitToken] | None = None  # kit
    photo: PhotoView | None = None  # photo hotspots overlay, any kind
    glb_url: str | None = None  # generated (stretch 11)
    tray: list[str] = []  # bom_line_ids with no mesh (off-model tray)
    note: str  # "Illustrative model…" | "Model from the project's own repository"
    simulated: bool = False


# --------------------------------------------------------------------------- templates (§3.19)


class TemplateReference(Model):
    url: str
    title: str
    licence: str | None = None
    used_for: str


class TemplateQuestion(Model):
    id: str
    text: str
    chips: list[Chip]
    default: str
    skip_if: list[str] = []


class TemplateVariant(Model):
    id: str
    label: str
    when: dict[str, str] = {}
    overrides: dict[str, Any] = {}


class TemplateSource(Model):
    url: str
    quote: str | None = None
    licence: str | None = None


class TemplatePart(Model):
    row_id: str
    name: str
    category: PartCategory
    qty: int | None  # null = unknown, never a guess
    qty_note: str | None = None
    line_kind: LineKind = "part"
    typical_spec: str | None = None
    attrs: dict[str, Any] = {}  # a range ("3500-4500") is allowed; null = unknown
    search_query: str | None = None
    rules: list[str] = []
    own_question: str | None = None
    basis: Literal["reference", "rule_of_thumb", "assumption"]
    source: TemplateSource | None = None
    mesh: str | None = None
    kb_refs: list[str] = []


class TemplateViewPart(Model):
    mesh: str
    row_id: str
    instances: int = 1
    explode: Vec3 = (0, 0, 0)
    order: int = 0


class TemplateView(Model):
    kind: ViewKind
    model: ViewModel | None = None
    parts: list[TemplateViewPart] = []


class TemplateEdge(Model):
    from_: str = Field(alias="from")
    to: str
    label: str
    rules: list[str] = []


class Template(Model):
    template_id: str
    build_type: BuildType
    version: str
    title: str
    summary: str
    references: list[TemplateReference] = []
    questions: list[TemplateQuestion] = []
    variants: list[TemplateVariant] = []
    parts: list[TemplatePart]
    rule_packs: list[str] = ["generic_electrical"]
    view: TemplateView
    edges: list[TemplateEdge] = []


# --------------------------------------------------------------------------- part panel (§4.2, §11.6)


class OwnedInfo(Model):
    memory_text: str
    provider: Literal["cognee", "owned_parts"]


class MemoryFact(Model):
    """One fact in the user's memory (PLAN §3.15). Only what the user stated or confirmed, never buyer data."""

    text: str
    kind: Literal["owned", "preference", "purchase", "seed"]
    source: str | None = None  # "seed" | "you said" | "approved cart r_…" | "you rejected …"
    run_id: str | None = None
    at: str | None = None
    provider: Literal["cognee", "owned_parts"]
    simulated: bool = False


class MemoryStage(Model):
    """One stage of Cognee `improve()` and what it did (status as Cognee reports it, e.g. ran / skipped)."""

    stage: str
    status: str
    reason: str | None = None


class MemoryImprove(Model):
    """What one `improve()` pass fed back and what Cognee's stages did with it."""

    at: str
    run_id: str | None = None
    feedback: list[str] = []
    stages: list[MemoryStage] = []
    provider: Literal["cognee", "owned_parts"]
    simulated: bool = False


class MemoryResponse(Model):
    """GET /api/memory: what the agent remembers about this user, and the last improve pass."""

    facts: list[MemoryFact]
    mode: str  # mock | cloud | local | off
    provider: Literal["cognee", "owned_parts"]
    last_improve: MemoryImprove | None = None
    simulated: bool = False


class ForgetRequest(Model):
    scope: Literal["everything", "preferences"] = "everything"


class ForgetResponse(Model):
    """POST /api/memory/forget. `forgotten` is null when the provider does not say how many items it removed."""

    scope: Literal["everything", "preferences"]
    forgotten: int | None = None
    detail: str
    provider: Literal["cognee", "owned_parts"]
    simulated: bool = False


class Why(Model):
    tier: str
    reason_codes: list[str]
    explanation: str
    edited_by_user: bool = False


class PanelRefusal(Model):
    rule: RefusalRule
    clause: str
    attempted: str
    triggered_by: TriggeredBy
    count: int = 1


class KbChunk(Model):
    kb_ref: str
    doc_title: str
    line_from: int
    line_to: int
    text: str
    score: float
    sql: str | None = None
    matched_terms: list[str] = []  # the query's index tokens found in this chunk ("why this matched")
    vector_rank: int | None = None  # 1-based rank in the vector half of the hybrid search; null when it did not appear
    fulltext_rank: int | None = None  # 1-based rank in the full-text half; null when it did not appear


class PartPanel(Model):
    bom_line_id: str
    name: str
    qty: int
    line_kind: LineKind
    status: BomStatus
    mesh_keys: list[str] = []
    provenance: Provenance
    spec: str
    attrs: dict[str, str] = {}
    confidence: float
    method: ResolveMethod
    owned: OwnedInfo | None = None
    offers: list[OfferRow] = []  # sorted: chosen, alternatives by line_usd, rejected, refused
    why: Why
    checks: list[Check] = []
    refusals: list[PanelRefusal] = []
    kb: list[KbChunk] = []
    needs_confirmation: bool = False  # an open assumption on this line
    record_hash: str
    source_api: str | None = None
    simulated: bool = False


# --------------------------------------------------------------------------- Universal Cart (§12)


class PriceChange(Model):
    offer_id: str
    old_usd: float
    new_usd: float
    stock: Stock | None = None


class CartCounts(Model):
    stores: int
    done: int
    agent_cart: int
    prefilled_cart: int
    product_link: int
    items_by_hand: int


class PriceChanged(Model):
    old_usd: float


class CartItem(Model):
    bom_line_id: str
    offer_id: str
    title: str
    qty: int
    packs: int
    unit_price_usd: float
    line_usd: float
    seen_at: str
    source_api: str
    url: str
    added: bool | None = None  # product-link tick
    changed: PriceChanged | None = None
    edited_by_user: bool | None = None
    alternatives: int = 0
    simulated: bool = False


class CartHandoff(Model):
    """Hand-off state for one store group (exists after approval)."""

    kind: ActionLevel
    url: str
    cart_id: str | None = None
    caveat: str | None = None
    url_sha256: str
    state: HandoffState = "ready"
    done_via: DoneVia | None = None
    order_id: str | None = None
    simulated: bool = False


class StoreTest(Model):
    """Tier 2 Stripe TEST state per store. Always simulated."""

    state: StoreTestState
    card_last4: str | None = None
    limit_usd: float | None = None
    simulated: Literal[True] = True


class StoreGroup(Model):
    store_id: str
    display_name: str
    domain: str
    action_level: ActionLevel
    downgrade_reason: str | None = None
    order: int
    subtotal_usd: float
    items: list[CartItem]
    handoff: CartHandoff | None = None
    test: StoreTest | None = None


class LeftOut(Model):
    bom_line_id: str
    name: str
    reason: LeftOutReason
    note: str | None = None


class TestPayment(Model):
    payment_intent: str
    authorized_usd: float
    captured_usd: float
    released_usd: float
    mandate_hash: str
    simulated: Literal[True] = True


class UniversalCart(Model):
    """The cart of record: every item from every store (PLAN §12)."""

    run_id: str
    state: CartState
    plan_id: str
    tier: str
    editable: bool
    total_usd: float
    budget_usd: float
    bought_usd: float  # stores marked done
    remaining_usd: float
    prices_checked_at: str
    price_changes: list[PriceChange] = []
    counts: CartCounts
    stores: list[StoreGroup]
    left_out: list[LeftOut] = []
    open_assumptions: list[str] = []  # bom_line_ids; Approve is refused while non-empty
    current_store_id: str | None = None  # checkout run: the store that is up next
    test_payment: TestPayment | None = None
    source_api: str | None = None
    simulated: bool = False


# --------------------------------------------------------------------------- SSE timeline (§4.2)


class Event(Model):
    seq: int
    ts: str
    severity: Severity
    type: EventType
    title: str
    detail: str | None = None
    bom_line_id: str | None = None
    store_id: str | None = None
    record_hash: str | None = None
    provider: EventProvider | None = None
    simulated: bool | None = None  # true for mock data and every Stripe test event
    data: dict[str, Any] | None = None


# --------------------------------------------------------------------------- run state (§4.2)


class RunSource(Model):
    url: str
    path: str
    commit_sha: str
    sha256: str
    fetched_at: str
    via: FetchedVia
    simulated: bool = False  # the bundled copy a mock connector returned, not a fresh read


class RunTemplate(Model):
    template_id: str
    variant: str | None = None
    kb_ref: str
    sql: str


class RunStats(Model):
    claude_calls: int = 0
    sie_calls: int = 0
    sie_median_ms: int = 0
    kb_queries: int = 0
    serpapi_calls: int = 0
    stores_searched: int = 0


class RunState(Model):
    run_id: str
    build_type: BuildType
    build_type_set_by: SetBy
    intake: Intake
    view: ViewData
    status: RunStatus
    mandate: OpenMandate
    source: RunSource | None = None  # link runs only
    template: RunTemplate | None = None
    provenance_counts: dict[ProvenanceType, int]
    open_assumptions: list[str] = []  # bom_line_ids
    bom: list[BOMLine]
    checks: list[Check] = []
    plans: dict[str, CartPlan] = {}
    active_tier: str = "cheapest"
    refusals: int = 0
    head_hash: str
    stats: RunStats
    source_api: str | None = None
    simulated: bool = False


# --------------------------------------------------------------------------- API bodies (§4.2)


class ProjectSample(Model):
    build_type: BuildType
    title: str
    example_text: str | None = None
    source_url: str | None = None
    blurb: str
    mandate_preset: MandatePreset
    view_kind: ViewKind
    simulated: bool = False


class StoreInfo(Model):
    store_id: str
    display_name: str
    domain: str
    action_level: ActionLevel
    caveat: str | None = None
    enabled: bool = True
    simulated: bool = False


class CreateRunRequest(Model):
    intake_id: str | None = None
    source_url: str | None = None  # v3 form: makes a link-only intake
    mandate: MandatePreset
    reference_search: bool = True  # the chat's "Find reference designs" chip; false is signed into the mandate scope


class CreateRunResponse(Model):
    run_id: str
    mandate: OpenMandate
    simulated: bool = False


class AssumptionRequest(Model):
    bom_line_id: str
    action: AssumptionAction
    spec: str | None = None
    qty: int | None = None


class MessageRequest(Model):
    text: str


class OwnedRequest(Model):
    bom_line_id: str
    owned: bool
    note: str | None = None


class VariantRequest(Model):
    option: str  # e.g. servo_7v4, servo_12v


class ReplanRequest(Model):
    tier: str
    budget_cap_usd: float | None = None


class ReplanResponse(Model):
    plan: CartPlan
    simulated: bool = False


class CartEditRequest(Model):
    op: CartEditOp
    bom_line_id: str
    offer_id: str | None = None
    store_id: str | None = None
    qty: int | None = None


class CartRefreshResponse(Model):
    checked_at: str
    changes: list[PriceChange] = []
    note: str | None = None  # "Replay: prices as recorded at 2:45 PM"
    simulated: bool = False


class ApproveRequest(Model):
    plan_id: str
    acknowledged_warnings: list[str] = []


class ApproveResponse(Model):
    closed_mandate: ClosedMandate
    cart: UniversalCart
    simulated: bool = False


class HandoffUpdateRequest(Model):
    store_id: str
    state: Literal["opened", "done", "skipped", "ready"]
    done_via: DoneVia | None = None
    order_id: str | None = None


class CartItemAddedRequest(Model):
    """The per-item "added" tick on a product-link store (PLAN §12.3). A UI action."""

    offer_id: str
    added: bool = True


class PayIntentRequest(Model):
    consent_text: str


class PayIntentResponse(Model):
    client_secret: str
    payment_intent_id: str
    payment_mandate: PaymentMandate
    livemode: Literal[False] = False
    simulated: Literal[True] = True


class PayFanoutRequest(Model):
    payment_intent_id: str
    over_limit_store: str | None = None  # TEST MODE demo: the store whose authorization is sent over the card's limit


class Accepted(Model):
    """Body of a 202: the effect arrives as SSE events."""

    accepted: Literal[True] = True
    simulated: bool = False


class PriceRow(Model):
    store_id: str
    title: str
    price_usd: float
    seen_at: str
    age_min: float
    vs_median_pct: float
    source_api: str
    refused: bool = False
    simulated: bool = False


class PricesResponse(Model):
    sql: str
    rows: list[PriceRow]
    simulated: bool = False


class KbSearchResponse(Model):
    sql: str
    took_ms: int
    chunks: list[KbChunk]
    query_terms: list[str] = []  # how the full-text analyzer split the query into index tokens
    analyzer: str | None = None  # "singlestore" (ANALYZE FULLTEXT) | "sqlite_fts5" (local fallback) | "mock"
    analyze_sql: str | None = None  # the statement that produced query_terms, shown in the Data drawer
    simulated: bool = False


class Receipt(Model):
    open_mandate: OpenMandate
    closed_mandate: ClosedMandate | None = None
    payment_mandate: PaymentMandate | None = None
    records: list[ChainRecord]
    head_hash: str
    public_key_jwk: dict[str, Any]
    source_api: str | None = None
    simulated: bool = False


class VerifyCheck(Model):
    name: str
    ok: bool
    detail: str | None = None


class VerifyResult(Model):
    ok: bool
    records: int
    head_hash: str
    broken_at: int | None = None
    signatures_ok: bool
    checks: list[VerifyCheck] = []
    simulated: bool = False


class DataLastQuery(Model):
    sql: str
    took_ms: float
    at: str


class SieCallRow(Model):
    step: str
    model: str
    calls: int
    median_ms: float
    errors: int = 0


class DataStats(Model):
    """`GET /api/data/stats`: the Data drawer's row counts, last query and SIE call table (owner D)."""

    backend: Literal["singlestore", "sqlite", "mock"]
    tables: dict[str, int] = {}
    kb_by_kind: dict[str, int] = {}
    last_query: DataLastQuery | None = None
    sie: list[SieCallRow] = []
    queries: int = 0
    fallback_reason: str | None = None
    sink_errors: dict[str, int] = {}
    simulated: bool = False


class Health(Model):
    mode: DemoMode
    mock: bool  # true when any data on screen may be mock: the UI shows the "Mock data" badge
    pay_tier: int
    serpapi_used: int
    integrations: dict[str, HealthState]
    stores: dict[str, HealthState]
    impl: dict[str, str] = {}  # service -> "mock" | "live" (registry choice)


# --------------------------------------------------------------------------- chat start page
# The shopping chat on `/`. Both agents (the keyword router and Claude with tools) answer with the same
# blocks. Chat can never approve, pay or widen a mandate: those stay UI actions (PLAN §3.6).

ChatRole = Literal["user", "agent"]
ChatAgentKind = Literal["keyword", "claude"]
ChatBlockKind = Literal[
    "text", "build_type", "questions", "mandate", "progress", "parts", "comparison", "why",
    "cart", "assumptions", "refusal", "actions",
]
ChatActionKind = Literal["reply", "link", "assumption"]
ChatTone = Literal["info", "ok", "warn"]


class ChatAction(Model):
    """A button under an agent message. `reply` sends `text` as the next message; `link` opens an app route;
    `assumption` is the person's own Confirm / Edit / Remove (POST /api/runs/{id}/assumptions), never the agent's."""

    kind: ChatActionKind
    label: str
    text: str | None = None
    href: str | None = None
    bom_line_id: str | None = None
    action: AssumptionAction | None = None


class ChatPartRow(Model):
    bom_line_id: str
    name: str
    qty: int
    status: BomStatus
    provenance: Provenance
    store_id: str | None = None
    store_name: str | None = None
    action_level: ActionLevel | None = None
    line_usd: float | None = None  # null: nothing chosen, so no price to show
    more_stores: int = 0  # other stores with an acceptable offer ("+N stores")
    note: str | None = None
    simulated: bool = False


class ChatCartStore(Model):
    store_id: str
    display_name: str
    action_level: ActionLevel
    subtotal_usd: float
    items: int


class ChatCartSummary(Model):
    run_id: str
    state: CartState
    tier: str
    total_usd: float
    budget_usd: float
    previous_total_usd: float | None = None  # set after a change made from chat
    stores: list[ChatCartStore] = []
    left_out: list[LeftOut] = []
    open_assumptions: list[str] = []
    items_by_hand: int = 0
    simulated: bool = False


class ChatAssumption(Model):
    bom_line_id: str
    name: str
    qty: int
    spec: str | None = None
    statement: str
    basis: str


class ChatBlock(Model):
    kind: ChatBlockKind
    text: str | None = None
    tone: ChatTone | None = None
    intake: Intake | None = None  # build_type, questions, mandate
    run_id: str | None = None  # progress (the run's SSE stream), parts, comparison, why, assumptions
    parts: list[ChatPartRow] | None = None
    panel: PartPanel | None = None  # comparison and why: the part panel's own data
    cart: ChatCartSummary | None = None
    assumptions: list[ChatAssumption] | None = None
    refusal: RefusalRecord | None = None
    actions: list[ChatAction] = []
    simulated: bool = False


class ChatMessage(Model):
    message_id: str
    role: ChatRole
    ts: str
    text: str | None = None
    link: str | None = None
    images: list[IntakeImage] = []
    blocks: list[ChatBlock] = []
    agent: ChatAgentKind | None = None  # which implementation wrote an agent message


class ChatSessionSummary(Model):
    session_id: str
    title: str
    created_at: str
    updated_at: str
    intake_id: str | None = None
    run_id: str | None = None
    build_type: BuildType | None = None
    status: RunStatus | None = None
    message_count: int = 0


class ChatSession(ChatSessionSummary):
    messages: list[ChatMessage] = []
    agent: ChatAgentKind = "keyword"
    agent_label: str = "Keyword assistant (no AI key)"
    reference_search: bool = True
    awaiting_summary: bool = False  # a run is going; POST …/sync posts its summary once it stops
    simulated: bool = False


class ChatCreateRequest(Model):
    reference_search: bool = True


class ChatSendResponse(Model):
    session: ChatSessionSummary
    messages: list[ChatMessage]  # the new messages only (the user's, then the agent's)
    awaiting_summary: bool = False
    agent: ChatAgentKind = "keyword"
    agent_label: str = "Keyword assistant (no AI key)"


class RunSummary(Model):
    """One row of the Library / Carts / Receipts lists on the start page."""

    run_id: str
    title: str
    build_type: BuildType
    status: RunStatus
    cart_state: CartState
    total_usd: float | None = None
    stores: int = 0
    lines: int = 0
    created_at: str
    simulated: bool = False


class ApiError(Model):
    """Body of a 4xx/5xx: `detail` of FastAPI's HTTPException."""

    error: str
    message: str
    refusal: RefusalRecord | None = None
    bom_line_ids: list[str] = []
    todo: str | None = None  # "TODO(A) — PLAN §4.2" for an endpoint with no live implementation yet


ProvenanceBase.model_rebuild()
for _m in (
    ReadmeQuoteProvenance, ReferenceProjectProvenance, TemplateRowProvenance,
    PhotoRegionProvenance, AssumptionProvenance,
):
    _m.model_rebuild()
del _m

# Names exported to TypeScript, in this order (scripts/gen_types.py).
TS_ALIASES: dict[str, Any] = {
    "ActionLevel": ActionLevel, "BuildType": BuildType, "DemoMode": DemoMode,
    "ProvenanceType": ProvenanceType, "LineKind": LineKind, "BomStatus": BomStatus,
    "Stock": Stock, "Condition": Condition, "OfferStatus": OfferStatus,
    "ResolveMethod": ResolveMethod, "CheckResult": CheckResult, "Severity": Severity,
    "HealthState": HealthState, "ViewKind": ViewKind, "ViewModel": ViewModel,
    "PartCategory": PartCategory, "CartState": CartState, "HandoffState": HandoffState,
    "DoneVia": DoneVia, "StoreTestState": StoreTestState, "LeftOutReason": LeftOutReason,
    "RunStatus": RunStatus, "SetBy": SetBy, "FetchedVia": FetchedVia, "FoundVia": FoundVia,
    "Detector": Detector, "RefusalRule": RefusalRule, "TriggeredBy": TriggeredBy,
    "AssumptionAction": AssumptionAction, "CartEditOp": CartEditOp,
    "EventProvider": EventProvider, "EventType": EventType, "RecordKind": RecordKind,
    "ChatRole": ChatRole, "ChatAgentKind": ChatAgentKind, "ChatBlockKind": ChatBlockKind,
    "ChatActionKind": ChatActionKind, "ChatTone": ChatTone,
}
