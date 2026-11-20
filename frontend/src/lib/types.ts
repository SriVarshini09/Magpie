// GENERATED FILE. DO NOT EDIT BY HAND.
// Source of truth: backend/app/models.py (PLAN §3.7, §3.16, §3.18, §3.19, §3.20, §4.2, §12.4).
// Regenerate: cd backend && uv run python scripts/gen_types.py
// Shared file, owned by the coordinator (OWNERSHIP.md). `tests/test_contract_parity.py` fails on drift.
//
// Optional (`?`) means the server may send null or leave the field out. null is "not known / not quoted".
// Mock data is always labelled: `source_api === "mock"` and `simulated === true`.

export const CONTRACT_VERSION = "0.4";

export type ActionLevel =
  | "agent_cart"
  | "prefilled_cart"
  | "product_link";

export type BuildType =
  | "robot_arm"
  | "quadcopter"
  | "rc_car"
  | "claw_gripper"
  | "electronics_mcu"
  | "generic";

export type DemoMode =
  | "mock"
  | "live"
  | "record"
  | "replay";

export type ProvenanceType =
  | "readme_quote"
  | "reference_project"
  | "template_row"
  | "photo_region"
  | "assumption";

export type LineKind =
  | "part"
  | "tool"
  | "optional";

export type BomStatus =
  | "extracted"
  | "resolved"
  | "owned"
  | "offers"
  | "chosen"
  | "warning"
  | "needs_human"
  | "not_found"
  | "skipped"
  | "removed";

export type Stock =
  | "in_stock"
  | "out_of_stock"
  | "unknown";

export type Condition =
  | "new"
  | "used"
  | "unknown";

export type OfferStatus =
  | "chosen"
  | "alternative"
  | "rejected"
  | "refused";

export type ResolveMethod =
  | "exact_from_source"
  | "kb"
  | "llm_inferred";

export type CheckResult =
  | "pass"
  | "warn"
  | "fail"
  | "needs_human";

export type Severity =
  | "info"
  | "ok"
  | "warn"
  | "refusal"
  | "error";

export type HealthState =
  | "ok"
  | "down"
  | "off"
  | "mock"
  | "fallback";

export type ViewKind =
  | "urdf"
  | "procedural"
  | "diagram"
  | "kit"
  | "generated";

export type ViewModel =
  | "so101"
  | "quadcopter"
  | "rc_car"
  | "claw";

export type PartCategory =
  | "board"
  | "motor"
  | "esc_driver"
  | "battery"
  | "power"
  | "sensor"
  | "camera"
  | "radio"
  | "cable"
  | "mechanical"
  | "printed"
  | "tool";

export type CartState =
  | "draft"
  | "approved"
  | "checking_out"
  | "complete";

export type HandoffState =
  | "ready"
  | "opened"
  | "done"
  | "skipped";

export type DoneVia =
  | "user"
  | "checkout_kit";

export type StoreTestState =
  | "queued"
  | "card_issued"
  | "authorized"
  | "declined"
  | "settled";

export type LeftOutReason =
  | "owned"
  | "removed_by_you"
  | "print_at_home"
  | "not_found";

export type RunStatus =
  | "running"
  | "waiting_approval"
  | "approved"
  | "done"
  | "error";

export type SetBy =
  | "classifier"
  | "user";

export type FetchedVia =
  | "airbyte.github"
  | "http"
  | "keenable"
  | "exa_airbyte";

export type FoundVia =
  | "keenable"
  | "exa_airbyte"
  | "claude_web_search"
  | "github_search"
  | "template";

export type Detector =
  | "sie:grounding-dino-base"
  | "claude_vision";

export type RefusalRule =
  | "merchant_allowed"
  | "data_sharing"
  | "action_allowed"
  | "budget"
  | "approval_required"
  | "unknown_offer"
  | "host_not_allowed"
  | "stale_price"
  | "assumption_unconfirmed"
  | "reference_host_not_allowed"
  | "photo_not_shared"
  | "scope_mismatch";

export type TriggeredBy =
  | "source_document"
  | "user_chat"
  | "store_listing"
  | "agent"
  | "user_edit";

export type AssumptionAction =
  | "confirm"
  | "edit"
  | "remove";

export type CartEditOp =
  | "swap_offer"
  | "move_store"
  | "remove"
  | "restore"
  | "set_qty";

export type EventProvider =
  | "airbyte"
  | "singlestore"
  | "sie"
  | "cognee"
  | "shopify"
  | "serpapi"
  | "digikey"
  | "stripe_test"
  | "claude"
  | "keenable"
  | "exa_airbyte"
  | "github"
  | "huggingface";

export type EventType =
  | "run.started"
  | "mandate.opened"
  | "source.fetched"
  | "bom.line"
  | "kb.search"
  | "spec.resolved"
  | "owned.matched"
  | "offers.found"
  | "offer.rejected"
  | "compat.check"
  | "compat.fix"
  | "plan.ready"
  | "plan.changed"
  | "cart.edited"
  | "price.refreshed"
  | "refusal"
  | "approval.granted"
  | "mandate.closed"
  | "handoff.created"
  | "handoff.opened"
  | "handoff.done"
  | "pay.hold_placed"
  | "pay.card_issued"
  | "pay.authorized"
  | "pay.declined"
  | "pay.captured"
  | "memory.written"
  | "agent.message"
  | "run.waiting_approval"
  | "run.done"
  | "error"
  | "intake.classified"
  | "intake.answered"
  | "template.loaded"
  | "reference.searched"
  | "reference.found"
  | "photo.parts"
  | "assumption.opened"
  | "assumption.resolved"
  | "view.ready";

export type RecordKind =
  | "intake"
  | "template_load"
  | "reference_search"
  | "photo_parts"
  | "assumption"
  | "mandate_open"
  | "source_fetch"
  | "kb_search"
  | "part_decision"
  | "refusal"
  | "extraction_rejected"
  | "compat_fix"
  | "plan"
  | "cart_edit"
  | "price_refresh"
  | "approval"
  | "mandate_closed"
  | "cart_action"
  | "handoff"
  | "payment_mandate"
  | "payment_hold"
  | "issuing_card"
  | "issuing_authorization"
  | "payment_capture"
  | "memory_write";

export type ChatRole =
  | "user"
  | "agent";

export type ChatAgentKind =
  | "keyword"
  | "claude";

export type ChatBlockKind =
  | "text"
  | "build_type"
  | "questions"
  | "mandate"
  | "progress"
  | "parts"
  | "comparison"
  | "why"
  | "cart"
  | "assumptions"
  | "refusal"
  | "actions";

export type ChatActionKind =
  | "reply"
  | "link"
  | "assumption";

export type ChatTone =
  | "info"
  | "ok"
  | "warn";

export type Provenance =
  | ReadmeQuoteProvenance
  | ReferenceProjectProvenance
  | TemplateRowProvenance
  | PhotoRegionProvenance
  | AssumptionProvenance;

export type QuoteSpan = {
  quote: string;
  span: [number, number];
  line_from: number;
  line_to: number;
};

export type ReadmeQuoteProvenance = {
  check: "pass" | "fail";
  supports: Array<Provenance>;
  type: "readme_quote";
  url: string;
  path: string;
  commit_sha: string;
  via: FetchedVia;
  quote: string;
  span: [number, number];
  line_from: number;
  line_to: number;
  doc_sha256: string;
  more_quotes: Array<QuoteSpan>;
};

export type ReferenceProjectProvenance = {
  check: "pass" | "fail";
  supports: Array<Provenance>;
  type: "reference_project";
  url: string;
  title: string;
  licence?: string | null;
  quote: string;
  span: [number, number];
  doc_sha256: string;
  fetched_at: string;
  found_via: FoundVia;
  fetched_via: FetchedVia;
};

export type TemplateRowProvenance = {
  check: "pass" | "fail";
  supports: Array<Provenance>;
  type: "template_row";
  kb_ref: string;
  template_id: string;
  row_id: string;
  variant?: string | null;
  template_sha256: string;
  basis: "reference" | "rule_of_thumb";
  derived_from?: string | null;
};

export type PhotoRegionProvenance = {
  check: "pass" | "fail";
  supports: Array<Provenance>;
  type: "photo_region";
  image_id: string;
  image_sha256: string;
  box_xyxy_px: [number, number, number, number];
  label: string;
  score: number;
  detector: Detector;
};

export type AssumptionProvenance = {
  check: "pass" | "fail";
  supports: Array<Provenance>;
  type: "assumption";
  statement: string;
  basis: string;
  confirmed_by_user: boolean;
  confirmed_at?: string | null;
};

export type Rerank = {
  provider: string;
  model: string;
  score: number;
  latency_ms: number;
};

export type SpecRead = {
  attr: string;
  value: string;
  text: string;
  label: string;
  score?: number | null;
  start?: number | null;
  end?: number | null;
  field: "title" | "description";
  provider: "sie" | "mock";
  model: string;
  simulated: boolean;
};

export type Offer = {
  offer_id: string;
  store_id: string;
  store_name: string;
  seller_name?: string | null;
  title: string;
  description?: string | null;
  url: string;
  price_usd: number;
  currency: string;
  units_per_pack: number;
  tier_prices?: Array<Record<string, unknown>> | null;
  shipping_usd?: number | null;
  eta_text?: string | null;
  eta_date?: string | null;
  stock: Stock;
  condition: Condition;
  rating?: number | null;
  reviews?: number | null;
  ids: Record<string, string>;
  action_level: ActionLevel;
  downgrade_reason?: string | null;
  source_api: string;
  mock_of?: string | null;
  seen_at: string;
  evidence_path?: string | null;
  evidence_sha256: string;
  rerank?: Rerank | null;
  spec_reads: Array<SpecRead>;
  refused?: string | null;
  simulated: boolean;
};

export type OfferRow = {
  offer_id: string;
  store_id: string;
  store_name: string;
  seller_name?: string | null;
  title: string;
  url: string;
  price_usd: number;
  units_per_pack: number;
  packs_needed: number;
  line_usd: number;
  shipping_usd?: number | null;
  eta_text?: string | null;
  stock: Stock;
  rating?: number | null;
  reviews?: number | null;
  action_level: ActionLevel;
  downgrade_reason?: string | null;
  source_api: string;
  mock_of?: string | null;
  seen_at: string;
  evidence_sha256: string;
  status: OfferStatus;
  reason?: string | null;
  rerank_score?: number | null;
  vs_chosen_usd?: number | null;
  spec_reads: Array<SpecRead>;
  simulated: boolean;
};

export type Check = {
  rule_id: string;
  result: CheckResult;
  message: string;
  fix?: string | null;
  kb_refs: Array<string>;
  bom_line_ids: Array<string>;
  needs_ack: boolean;
};

export type PlanLine = {
  bom_line_id: string;
  offer_id: string;
  store_id: string;
  packs: number;
  qty: number;
  line_usd: number;
};

export type CartPlan = {
  plan_id: string;
  tier: string;
  total_usd: number;
  stores: Array<string>;
  checkouts: number;
  by_level: Record<ActionLevel, number>;
  items_by_hand: number;
  feasible: boolean;
  over_budget_by?: number | null;
  plan_sha256?: string | null;
  lines: Array<PlanLine>;
  simulated: boolean;
};

export type ChosenOffer = {
  offer_id: string;
  store_id: string;
  store_name: string;
  action_level: ActionLevel;
  title: string;
  packs: number;
  price: number;
  url: string;
  seen_at: string;
  source_api: string;
  simulated: boolean;
};

export type BOMLine = {
  bom_line_id: string;
  raw_name: string;
  qty: number;
  qty_note?: string | null;
  provenance: Provenance;
  line_kind: LineKind;
  status: BomStatus;
  category?: PartCategory | null;
  mesh_keys: Array<string>;
  spec?: string | null;
  confidence?: number | null;
  owned_note?: string | null;
  stores_count?: number | null;
  chosen?: Array<ChosenOffer> | null;
};

export type TrustedContext = {
  provider: string;
  kb_ref: string;
  query: string;
  snippet: string;
  score: number;
};

export type ResolvedPart = {
  spec: string;
  attrs: Record<string, string>;
  confidence: number;
  method: ResolveMethod;
  trusted_context: Array<TrustedContext>;
};

export type PartQuery = {
  bom_line_id: string;
  query: string;
  name?: string | null;
  spec?: string | null;
  qty: number;
  attrs: Record<string, string>;
  ship_to_country: string;
};

export type SourceDoc = {
  id: string;
  url: string;
  path: string;
  commit_sha: string;
  text: string;
  sha256: string;
  fetched_at: string;
  via: FetchedVia;
  source_api?: string | null;
  simulated: boolean;
};

export type PhotoPart = {
  label: string;
  category: string;
  box_xyxy_px: [number, number, number, number];
  score: number;
  detector: string;
};

export type Signature = {
  alg: string;
  kid: string;
  jws: string;
};

export type MandateInputs = {
  source_url?: string | null;
  text_sha256?: string | null;
  image_sha256: Array<string>;
};

export type MandateScope = {
  build_type: BuildType;
  build_type_set_by: SetBy;
  goal: string;
  intake_sha256: string;
  inputs: MandateInputs;
  template_id: string;
  reference_search: boolean;
};

export type DataSharing = {
  country: boolean;
  postal_code: boolean;
  street_address: boolean;
  email: boolean;
  phone: boolean;
  name: boolean;
  photo_to_models: boolean;
};

export type MandateActions = {
  search: boolean;
  create_cart: boolean;
  build_cart_link: boolean;
  checkout: boolean;
  pay: boolean;
  message_seller: boolean;
};

export type MandateConstraints = {
  budget_usd: number;
  deadline: string;
  ship_to_country: string;
  allowed_merchants: Array<string>;
  data_sharing: DataSharing;
  actions: MandateActions;
};

export type OpenMandate = {
  type: "b2c.mandate.open";
  version: string;
  note: string;
  mandate_id: string;
  run_id: string;
  user_id: string;
  created_at: string;
  expires_at: string;
  scope: MandateScope;
  constraints: MandateConstraints;
  signature: Signature;
  simulated: boolean;
};

export type HandoffItem = {
  offer_id: string;
  ids: Record<string, string>;
  title: string;
  qty: number;
  unit_price_usd: number;
  seen_at: string;
  source_api: string;
  evidence_sha256: string;
  edited_by_user: boolean;
};

export type Handoff = {
  store_id: string;
  action_level: ActionLevel;
  cart_id?: string | null;
  url: string;
  url_sha256: string;
  subtotal_usd: number;
  caveat?: string | null;
  items: Array<HandoffItem>;
  simulated: boolean;
};

export type StepUp = {
  provider: string;
  inquiry_id: string;
  status: string;
};

export type ClosedMandate = {
  type: "b2c.mandate.closed";
  version: string;
  open_mandate_sha256: string;
  plan_id: string;
  plan_sha256: string;
  tier: string;
  handoffs: Array<Handoff>;
  total_usd: number;
  prices_checked_at: string;
  approved_by: "ui_button";
  approved_at: string;
  approval_token_sha256: string;
  chain_head: string;
  step_up?: StepUp | null;
  signature: Signature;
  simulated: boolean;
};

export type Amount = {
  amount: number;
  currency: string;
};

export type UserConsent = {
  at: string;
  text_shown: string;
};

export type PaymentInstrument = {
  kind: string;
  id: string;
  last4: string;
};

export type PaymentAllocation = {
  store_id: string;
  action_level: ActionLevel;
  url_sha256: string;
  limit: number;
  instrument?: PaymentInstrument | null;
  authorization_id?: string | null;
  simulated: true;
  status: string;
};

export type PaymentSummary = {
  provider: "stripe_test";
  payment_intent: string;
  authorized: number;
  captured: number;
  released: number;
};

export type PaymentMandate = {
  type: "b2c.mandate.payment";
  version: string;
  mode: "test";
  mandate_id: string;
  closed_mandate_sha256: string;
  status: "open" | "funded" | "executing" | "closed";
  user_consent: UserConsent;
  total: Amount;
  allocations: Array<PaymentAllocation>;
  payment?: PaymentSummary | null;
  mandate_hash: string;
  signature?: Signature | null;
  simulated: true;
};

export type ChainRecord = {
  run_id: string;
  seq: number;
  ts: string;
  kind: RecordKind;
  prev_hash: string;
  hash: string;
  [key: string]: unknown;
};

export type RefusalAttempt = {
  tool?: string | null;
  field?: string | null;
  value?: string | null;
};

export type RefusalRecord = {
  kind: "refusal";
  rule: RefusalRule;
  attempted: RefusalAttempt;
  clause: string;
  triggered_by: TriggeredBy;
  ts: string;
};

export type DecisionPart = {
  bom_line_id: string;
  raw_name: string;
  qty: number;
  line_kind: LineKind;
  provenance: Provenance;
};

export type OwnedCheck = {
  provider: "cognee" | "owned_parts";
  matched?: string | null;
  action: "keep" | "remove";
};

export type Candidate = {
  offer_id: string;
  store_id: string;
  action_level: ActionLevel;
  url: string;
  title: string;
  price: number;
  currency: string;
  units_per_pack: number;
  shipping?: number | null;
  eta?: string | null;
  stock: Stock;
  rating?: number | null;
  reviews?: number | null;
  seen_at: string;
  source_api: string;
  evidence_path?: string | null;
  evidence_sha256: string;
  rerank?: Rerank | null;
  simulated: boolean;
};

export type RejectedOffer = {
  offer_id: string;
  reason: string;
};

export type MandateCheck = {
  rule: RefusalRule;
  result: "allowed" | "refused";
  attempted: string;
  clause: string;
};

export type CompatibilityResult = {
  rule_id: string;
  result: CheckResult;
  message: string;
  kb_ref?: string | null;
  fix?: string | null;
};

export type ChosenPack = {
  offer_id: string;
  packs: number;
};

export type Decision = {
  chosen: Array<ChosenPack>;
  tier: string;
  reason_codes: Array<string>;
  explanation: string;
  edited_by_user: boolean;
};

export type ModelUsage = {
  name: string;
  input_tokens: number;
  output_tokens: number;
};

export type DecisionRecord = {
  run_id: string;
  seq: number;
  ts: string;
  kind: "part_decision";
  part: DecisionPart;
  resolution: ResolvedPart;
  owned_check: OwnedCheck;
  candidates: Array<Candidate>;
  rejected: Array<RejectedOffer>;
  mandate_checks: Array<MandateCheck>;
  compatibility: Array<CompatibilityResult>;
  decision: Decision;
  model: ModelUsage;
  prev_hash: string;
  hash: string;
  simulated: boolean;
};

export type Chip = {
  value: string;
  label: string;
};

export type IntakeQuestion = {
  id: string;
  text: string;
  chips: Array<Chip>;
  default: string;
  answer?: string | null;
};

export type IntakeImage = {
  image_id: string;
  url: string;
  w: number;
  h: number;
  sha256: string;
};

export type IntakeInputs = {
  text?: string | null;
  source_url?: string | null;
  images: Array<IntakeImage>;
};

export type IntakeConstraints = {
  budget_usd?: number | null;
  size_class?: string | null;
};

export type BuildTypeAlternative = {
  build_type: BuildType;
  confidence: number;
};

export type MandatePreset = {
  budget_usd: number;
  deadline: string;
  ship_to_country: string;
  allowed_merchants: Array<string>;
  data_sharing: DataSharing;
};

export type Intake = {
  intake_id: string;
  ready: boolean;
  summary: string;
  build_type: BuildType;
  confidence: number;
  alternatives: Array<BuildTypeAlternative>;
  inputs: IntakeInputs;
  constraints: IntakeConstraints;
  questions: Array<IntakeQuestion>;
  visible_parts?: Array<PhotoPart> | null;
  template_id: string;
  mandate_preset: MandatePreset;
  source_api?: string | null;
  simulated: boolean;
};

export type IntakeRequest = {
  text?: string | null;
  run_id?: string | null;
  image_count: number;
};

export type IntakeAnswersRequest = {
  answers: Record<string, string>;
  build_type?: BuildType | null;
  skip_defaults?: boolean | null;
};

export type ViewPart = {
  mesh: string;
  bom_line_id: string;
  instances: number;
  explode: [number, number, number];
  order: number;
};

export type ViewEdge = {
  from: string;
  to: string;
  label: string;
  rule_ids: Array<string>;
};

export type PhotoRegion = {
  bom_line_id?: string | null;
  box_xyxy_px: [number, number, number, number];
  label: string;
  score: number;
  approximate: boolean;
};

export type PhotoView = {
  image_id: string;
  url: string;
  w: number;
  h: number;
  sha256: string;
  regions: Array<PhotoRegion>;
};

export type DiagramNode = {
  id: string;
  bom_line_id?: string | null;
  label: string;
  icon: string;
  x: number;
  y: number;
  w: number;
  h: number;
};

export type DiagramData = {
  nodes: Array<DiagramNode>;
  tray: Array<string>;
};

export type KitToken = {
  bom_line_id: string;
  category: PartCategory;
  qty: number;
  label: string;
};

export type ViewData = {
  kind: ViewKind;
  model?: ViewModel | null;
  variant?: string | null;
  scale?: number | null;
  urdf_url?: string | null;
  parts: Array<ViewPart>;
  edges?: Array<ViewEdge> | null;
  diagram?: DiagramData | null;
  tokens?: Array<KitToken> | null;
  photo?: PhotoView | null;
  glb_url?: string | null;
  tray: Array<string>;
  note: string;
  simulated: boolean;
};

export type TemplateReference = {
  url: string;
  title: string;
  licence?: string | null;
  used_for: string;
};

export type TemplateQuestion = {
  id: string;
  text: string;
  chips: Array<Chip>;
  default: string;
  skip_if: Array<string>;
};

export type TemplateVariant = {
  id: string;
  label: string;
  when: Record<string, string>;
  overrides: Record<string, unknown>;
};

export type TemplateSource = {
  url: string;
  quote?: string | null;
  licence?: string | null;
};

export type TemplatePart = {
  row_id: string;
  name: string;
  category: PartCategory;
  qty: number | null;
  qty_note?: string | null;
  line_kind: LineKind;
  typical_spec?: string | null;
  attrs: Record<string, unknown>;
  search_query?: string | null;
  rules: Array<string>;
  own_question?: string | null;
  basis: "reference" | "rule_of_thumb" | "assumption";
  source?: TemplateSource | null;
  mesh?: string | null;
  kb_refs: Array<string>;
};

export type TemplateViewPart = {
  mesh: string;
  row_id: string;
  instances: number;
  explode: [number, number, number];
  order: number;
};

export type TemplateView = {
  kind: ViewKind;
  model?: ViewModel | null;
  parts: Array<TemplateViewPart>;
};

export type TemplateEdge = {
  from: string;
  to: string;
  label: string;
  rules: Array<string>;
};

export type Template = {
  template_id: string;
  build_type: BuildType;
  version: string;
  title: string;
  summary: string;
  references: Array<TemplateReference>;
  questions: Array<TemplateQuestion>;
  variants: Array<TemplateVariant>;
  parts: Array<TemplatePart>;
  rule_packs: Array<string>;
  view: TemplateView;
  edges: Array<TemplateEdge>;
};

export type OwnedInfo = {
  memory_text: string;
  provider: "cognee" | "owned_parts";
};

export type MemoryFact = {
  text: string;
  kind: "owned" | "preference" | "purchase" | "seed";
  source?: string | null;
  run_id?: string | null;
  at?: string | null;
  provider: "cognee" | "owned_parts";
  simulated: boolean;
};

export type MemoryStage = {
  stage: string;
  status: string;
  reason?: string | null;
};

export type MemoryImprove = {
  at: string;
  run_id?: string | null;
  feedback: Array<string>;
  stages: Array<MemoryStage>;
  provider: "cognee" | "owned_parts";
  simulated: boolean;
};

export type MemoryResponse = {
  facts: Array<MemoryFact>;
  mode: string;
  provider: "cognee" | "owned_parts";
  last_improve?: MemoryImprove | null;
  simulated: boolean;
};

export type ForgetRequest = {
  scope: "everything" | "preferences";
};

export type ForgetResponse = {
  scope: "everything" | "preferences";
  forgotten?: number | null;
  detail: string;
  provider: "cognee" | "owned_parts";
  simulated: boolean;
};

export type Why = {
  tier: string;
  reason_codes: Array<string>;
  explanation: string;
  edited_by_user: boolean;
};

export type PanelRefusal = {
  rule: RefusalRule;
  clause: string;
  attempted: string;
  triggered_by: TriggeredBy;
  count: number;
};

export type KbChunk = {
  kb_ref: string;
  doc_title: string;
  line_from: number;
  line_to: number;
  text: string;
  score: number;
  sql?: string | null;
  matched_terms: Array<string>;
  vector_rank?: number | null;
  fulltext_rank?: number | null;
};

export type PartPanel = {
  bom_line_id: string;
  name: string;
  qty: number;
  line_kind: LineKind;
  status: BomStatus;
  mesh_keys: Array<string>;
  provenance: Provenance;
  spec: string;
  attrs: Record<string, string>;
  confidence: number;
  method: ResolveMethod;
  owned?: OwnedInfo | null;
  offers: Array<OfferRow>;
  why: Why;
  checks: Array<Check>;
  refusals: Array<PanelRefusal>;
  kb: Array<KbChunk>;
  needs_confirmation: boolean;
  record_hash: string;
  source_api?: string | null;
  simulated: boolean;
};

export type PriceChange = {
  offer_id: string;
  old_usd: number;
  new_usd: number;
  stock?: Stock | null;
};

export type CartCounts = {
  stores: number;
  done: number;
  agent_cart: number;
  prefilled_cart: number;
  product_link: number;
  items_by_hand: number;
};

export type PriceChanged = {
  old_usd: number;
};

export type CartItem = {
  bom_line_id: string;
  offer_id: string;
  title: string;
  qty: number;
  packs: number;
  unit_price_usd: number;
  line_usd: number;
  seen_at: string;
  source_api: string;
  url: string;
  added?: boolean | null;
  changed?: PriceChanged | null;
  edited_by_user?: boolean | null;
  alternatives: number;
  simulated: boolean;
};

export type CartHandoff = {
  kind: ActionLevel;
  url: string;
  cart_id?: string | null;
  caveat?: string | null;
  url_sha256: string;
  state: HandoffState;
  done_via?: DoneVia | null;
  order_id?: string | null;
  simulated: boolean;
};

export type StoreTest = {
  state: StoreTestState;
  card_last4?: string | null;
  limit_usd?: number | null;
  simulated: true;
};

export type StoreGroup = {
  store_id: string;
  display_name: string;
  domain: string;
  action_level: ActionLevel;
  downgrade_reason?: string | null;
  order: number;
  subtotal_usd: number;
  items: Array<CartItem>;
  handoff?: CartHandoff | null;
  test?: StoreTest | null;
};

export type LeftOut = {
  bom_line_id: string;
  name: string;
  reason: LeftOutReason;
  note?: string | null;
};

export type TestPayment = {
  payment_intent: string;
  authorized_usd: number;
  captured_usd: number;
  released_usd: number;
  mandate_hash: string;
  simulated: true;
};

export type UniversalCart = {
  run_id: string;
  state: CartState;
  plan_id: string;
  tier: string;
  editable: boolean;
  total_usd: number;
  budget_usd: number;
  bought_usd: number;
  remaining_usd: number;
  prices_checked_at: string;
  price_changes: Array<PriceChange>;
  counts: CartCounts;
  stores: Array<StoreGroup>;
  left_out: Array<LeftOut>;
  open_assumptions: Array<string>;
  current_store_id?: string | null;
  test_payment?: TestPayment | null;
  source_api?: string | null;
  simulated: boolean;
};

export type Event = {
  seq: number;
  ts: string;
  severity: Severity;
  type: EventType;
  title: string;
  detail?: string | null;
  bom_line_id?: string | null;
  store_id?: string | null;
  record_hash?: string | null;
  provider?: EventProvider | null;
  simulated?: boolean | null;
  data?: Record<string, unknown> | null;
};

export type RunSource = {
  url: string;
  path: string;
  commit_sha: string;
  sha256: string;
  fetched_at: string;
  via: FetchedVia;
  simulated: boolean;
};

export type RunTemplate = {
  template_id: string;
  variant?: string | null;
  kb_ref: string;
  sql: string;
};

export type RunStats = {
  claude_calls: number;
  sie_calls: number;
  sie_median_ms: number;
  kb_queries: number;
  serpapi_calls: number;
  stores_searched: number;
};

export type RunState = {
  run_id: string;
  build_type: BuildType;
  build_type_set_by: SetBy;
  intake: Intake;
  view: ViewData;
  status: RunStatus;
  mandate: OpenMandate;
  source?: RunSource | null;
  template?: RunTemplate | null;
  provenance_counts: Record<ProvenanceType, number>;
  open_assumptions: Array<string>;
  bom: Array<BOMLine>;
  checks: Array<Check>;
  plans: Record<string, CartPlan>;
  active_tier: string;
  refusals: number;
  head_hash: string;
  stats: RunStats;
  source_api?: string | null;
  simulated: boolean;
};

export type ProjectSample = {
  build_type: BuildType;
  title: string;
  example_text?: string | null;
  source_url?: string | null;
  blurb: string;
  mandate_preset: MandatePreset;
  view_kind: ViewKind;
  simulated: boolean;
};

export type StoreInfo = {
  store_id: string;
  display_name: string;
  domain: string;
  action_level: ActionLevel;
  caveat?: string | null;
  enabled: boolean;
  simulated: boolean;
};

export type CreateRunRequest = {
  intake_id?: string | null;
  source_url?: string | null;
  mandate: MandatePreset;
  reference_search: boolean;
};

export type CreateRunResponse = {
  run_id: string;
  mandate: OpenMandate;
  simulated: boolean;
};

export type AssumptionRequest = {
  bom_line_id: string;
  action: AssumptionAction;
  spec?: string | null;
  qty?: number | null;
};

export type MessageRequest = {
  text: string;
};

export type OwnedRequest = {
  bom_line_id: string;
  owned: boolean;
  note?: string | null;
};

export type VariantRequest = {
  option: string;
};

export type ReplanRequest = {
  tier: string;
  budget_cap_usd?: number | null;
};

export type ReplanResponse = {
  plan: CartPlan;
  simulated: boolean;
};

export type CartEditRequest = {
  op: CartEditOp;
  bom_line_id: string;
  offer_id?: string | null;
  store_id?: string | null;
  qty?: number | null;
};

export type CartRefreshResponse = {
  checked_at: string;
  changes: Array<PriceChange>;
  note?: string | null;
  simulated: boolean;
};

export type ApproveRequest = {
  plan_id: string;
  acknowledged_warnings: Array<string>;
};

export type ApproveResponse = {
  closed_mandate: ClosedMandate;
  cart: UniversalCart;
  simulated: boolean;
};

export type HandoffUpdateRequest = {
  store_id: string;
  state: HandoffState;
  done_via?: DoneVia | null;
  order_id?: string | null;
};

export type CartItemAddedRequest = {
  offer_id: string;
  added: boolean;
};

export type PayIntentRequest = {
  consent_text: string;
};

export type PayIntentResponse = {
  client_secret: string;
  payment_intent_id: string;
  payment_mandate: PaymentMandate;
  livemode: false;
  simulated: true;
};

export type PayFanoutRequest = {
  payment_intent_id: string;
  over_limit_store?: string | null;
};

export type Accepted = {
  accepted: true;
  simulated: boolean;
};

export type PriceRow = {
  store_id: string;
  title: string;
  price_usd: number;
  seen_at: string;
  age_min: number;
  vs_median_pct: number;
  source_api: string;
  refused: boolean;
  simulated: boolean;
};

export type PricesResponse = {
  sql: string;
  rows: Array<PriceRow>;
  simulated: boolean;
};

export type KbSearchResponse = {
  sql: string;
  took_ms: number;
  chunks: Array<KbChunk>;
  query_terms: Array<string>;
  analyzer?: string | null;
  analyze_sql?: string | null;
  simulated: boolean;
};

export type Receipt = {
  open_mandate: OpenMandate;
  closed_mandate?: ClosedMandate | null;
  payment_mandate?: PaymentMandate | null;
  records: Array<ChainRecord>;
  head_hash: string;
  public_key_jwk: Record<string, unknown>;
  source_api?: string | null;
  simulated: boolean;
};

export type VerifyCheck = {
  name: string;
  ok: boolean;
  detail?: string | null;
};

export type VerifyResult = {
  ok: boolean;
  records: number;
  head_hash: string;
  broken_at?: number | null;
  signatures_ok: boolean;
  checks: Array<VerifyCheck>;
  simulated: boolean;
};

export type DataLastQuery = {
  sql: string;
  took_ms: number;
  at: string;
};

export type SieCallRow = {
  step: string;
  model: string;
  calls: number;
  median_ms: number;
  errors: number;
};

export type DataStats = {
  backend: "singlestore" | "sqlite" | "mock";
  tables: Record<string, number>;
  kb_by_kind: Record<string, number>;
  last_query?: DataLastQuery | null;
  sie: Array<SieCallRow>;
  queries: number;
  fallback_reason?: string | null;
  sink_errors: Record<string, number>;
  simulated: boolean;
};

export type Health = {
  mode: DemoMode;
  mock: boolean;
  pay_tier: number;
  serpapi_used: number;
  integrations: Record<string, HealthState>;
  stores: Record<string, HealthState>;
  impl: Record<string, string>;
};

export type ChatAction = {
  kind: ChatActionKind;
  label: string;
  text?: string | null;
  href?: string | null;
  bom_line_id?: string | null;
  action?: AssumptionAction | null;
};

export type ChatPartRow = {
  bom_line_id: string;
  name: string;
  qty: number;
  status: BomStatus;
  provenance: Provenance;
  store_id?: string | null;
  store_name?: string | null;
  action_level?: ActionLevel | null;
  line_usd?: number | null;
  more_stores: number;
  note?: string | null;
  simulated: boolean;
};

export type ChatCartStore = {
  store_id: string;
  display_name: string;
  action_level: ActionLevel;
  subtotal_usd: number;
  items: number;
};

export type ChatCartSummary = {
  run_id: string;
  state: CartState;
  tier: string;
  total_usd: number;
  budget_usd: number;
  previous_total_usd?: number | null;
  stores: Array<ChatCartStore>;
  left_out: Array<LeftOut>;
  open_assumptions: Array<string>;
  items_by_hand: number;
  simulated: boolean;
};

export type ChatAssumption = {
  bom_line_id: string;
  name: string;
  qty: number;
  spec?: string | null;
  statement: string;
  basis: string;
};

export type ChatBlock = {
  kind: ChatBlockKind;
  text?: string | null;
  tone?: ChatTone | null;
  intake?: Intake | null;
  run_id?: string | null;
  parts?: Array<ChatPartRow> | null;
  panel?: PartPanel | null;
  cart?: ChatCartSummary | null;
  assumptions?: Array<ChatAssumption> | null;
  refusal?: RefusalRecord | null;
  actions: Array<ChatAction>;
  simulated: boolean;
};

export type ChatMessage = {
  message_id: string;
  role: ChatRole;
  ts: string;
  text?: string | null;
  link?: string | null;
  images: Array<IntakeImage>;
  blocks: Array<ChatBlock>;
  agent?: ChatAgentKind | null;
};

export type ChatSessionSummary = {
  session_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  intake_id?: string | null;
  run_id?: string | null;
  build_type?: BuildType | null;
  status?: RunStatus | null;
  message_count: number;
};

export type ChatSession = {
  session_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  intake_id?: string | null;
  run_id?: string | null;
  build_type?: BuildType | null;
  status?: RunStatus | null;
  message_count: number;
  messages: Array<ChatMessage>;
  agent: ChatAgentKind;
  agent_label: string;
  reference_search: boolean;
  awaiting_summary: boolean;
  simulated: boolean;
};

export type ChatCreateRequest = {
  reference_search: boolean;
};

export type ChatSendResponse = {
  session: ChatSessionSummary;
  messages: Array<ChatMessage>;
  awaiting_summary: boolean;
  agent: ChatAgentKind;
  agent_label: string;
};

export type RunSummary = {
  run_id: string;
  title: string;
  build_type: BuildType;
  status: RunStatus;
  cart_state: CartState;
  total_usd?: number | null;
  stores: number;
  lines: number;
  created_at: string;
  simulated: boolean;
};

export type ApiError = {
  error: string;
  message: string;
  refusal?: RefusalRecord | null;
  bom_line_ids: Array<string>;
  todo?: string | null;
};
