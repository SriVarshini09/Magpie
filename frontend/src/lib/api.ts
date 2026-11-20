// Typed client for every endpoint in PLAN §4.2. Owner: C.
// Types come from ./types (generated from backend/app/models.py: do not edit them by hand).
import { useAppStore } from "@/lib/store";
import type {
  Accepted,
  ApiError,
  ApproveRequest,
  ApproveResponse,
  AssumptionRequest,
  CartEditRequest,
  CartRefreshResponse,
  ChatSendResponse,
  ChatSession,
  ChatSessionSummary,
  CreateRunRequest,
  CreateRunResponse,
  DataStats,
  ForgetRequest,
  ForgetResponse,
  HandoffUpdateRequest,
  Health,
  Intake,
  IntakeAnswersRequest,
  KbSearchResponse,
  MandatePreset,
  MemoryResponse,
  OwnedRequest,
  PartPanel,
  PayIntentResponse,
  PricesResponse,
  ProjectSample,
  Receipt,
  ReplanRequest,
  ReplanResponse,
  RunState,
  RunSummary,
  StoreInfo,
  UniversalCart,
  VerifyResult,
  ViewData,
} from "@/lib/types";

export const API_BASE = (import.meta.env.VITE_API_BASE ?? "http://localhost:8000").replace(/\/$/, "");

/** A non-2xx answer. `detail` is the backend's ApiError (409 refusals carry `refusal`). */
export class ApiFailure extends Error {
  readonly status: number;
  readonly detail: ApiError;

  constructor(status: number, detail: ApiError) {
    super(detail.message || `Request failed (${status})`);
    this.name = "ApiFailure";
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new ApiFailure(0, { error: "network", message: `Couldn't reach the backend at ${API_BASE}. Check that it is running, then retry.`, bom_line_ids: [] });
  }
  // The backend labels every response; this is what switches the "Mock data" badge on.
  if (res.headers.get("X-B2C-Mock") === "true") useAppStore.getState().setMockSeen(true);
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as { detail?: unknown } | null;
    const d = body?.detail;
    const detail: ApiError =
      d && typeof d === "object" && !Array.isArray(d)
        ? (d as ApiError)
        : { error: "http_error", message: typeof d === "string" ? d : `Request failed (${res.status})`, bom_line_ids: [] };
    throw new ApiFailure(res.status, detail);
  }
  return (await res.json()) as T;
}

const get = <T>(path: string) => request<T>(path);
const post = <T>(path: string, body?: unknown) =>
  request<T>(path, {
    method: "POST",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

const run = (id: string) => `/api/runs/${encodeURIComponent(id)}`;
const chat = (id: string) => `/api/chat/sessions/${encodeURIComponent(id)}`;

export const api = {
  health: () => get<Health>("/api/health"),
  projects: () => get<ProjectSample[]>("/api/projects"),
  stores: () => get<StoreInfo[]>("/api/stores"),

  /** Multipart: text, link and up to two photos (already resized in the browser, PLAN §3.17). */
  intake: (input: { text?: string; images?: File[]; runId?: string }) => {
    const form = new FormData();
    if (input.text) form.append("text", input.text);
    if (input.runId) form.append("run_id", input.runId);
    for (const file of input.images ?? []) form.append("images", file);
    return request<Intake>("/api/intake", { method: "POST", body: form });
  },
  answers: (intakeId: string, body: IntakeAnswersRequest) => post<Intake>(`/api/intake/${encodeURIComponent(intakeId)}/answers`, body),
  uploadUrl: (imageId: string) => `${API_BASE}/api/uploads/${encodeURIComponent(imageId)}`,

  createRun: (body: Omit<CreateRunRequest, "reference_search"> & { reference_search?: boolean }) => post<CreateRunResponse>("/api/runs", body),
  run: (id: string) => get<RunState>(run(id)),
  eventsUrl: (id: string, after = 0) => `${API_BASE}${run(id)}/events${after ? `?after=${after}` : ""}`,
  assumption: (id: string, body: AssumptionRequest) => post<RunState>(`${run(id)}/assumptions`, body),
  partPanel: (id: string, bomLineId: string) => get<PartPanel>(`${run(id)}/parts/${encodeURIComponent(bomLineId)}`),
  prices: (id: string, bomLineId: string) => get<PricesResponse>(`${run(id)}/prices/${encodeURIComponent(bomLineId)}`),
  dataStats: () => get<DataStats>("/api/data/stats"),
  kbSearch: (q: string) => get<KbSearchResponse>(`/api/kb/search?q=${encodeURIComponent(q)}`),
  message: (id: string, text: string) => post<Accepted>(`${run(id)}/message`, { text }),
  owned: (id: string, body: OwnedRequest) => post<Accepted>(`${run(id)}/owned`, body),
  variant: (id: string, option: string) => post<Accepted>(`${run(id)}/variant`, { option }),
  replan: (id: string, body: ReplanRequest) => post<ReplanResponse>(`${run(id)}/replan`, body),

  cart: (id: string) => get<UniversalCart>(`${run(id)}/cart`),
  cartEdit: (id: string, body: CartEditRequest) => post<UniversalCart>(`${run(id)}/cart/edit`, body),
  cartRefresh: (id: string) => post<CartRefreshResponse>(`${run(id)}/cart/refresh`),
  approve: (id: string, body: ApproveRequest) => post<ApproveResponse>(`${run(id)}/approve`, body),
  handoff: (id: string, body: HandoffUpdateRequest) => post<UniversalCart>(`${run(id)}/cart/handoff`, body),
  /** "Edit cart" on an approved cart: open carts are cancelled, the cart is a draft again. */
  cartReopen: (id: string) => post<UniversalCart>(`${run(id)}/cart/reopen`),
  /** The per-item "added" tick on a product-link store; kept on the backend with the cart. */
  cartItemAdded: (id: string, offerId: string, added: boolean) => post<UniversalCart>(`${run(id)}/cart/item-added`, { offer_id: offerId, added }),
  cartCsvUrl: (id: string) => `${API_BASE}${run(id)}/cart/export.csv`,

  // Tier 2, Stripe TEST MODE only. Started by a person clicking, never by the agent.
  payIntent: (id: string, consentText: string) => post<PayIntentResponse>(`${run(id)}/pay/intent`, { consent_text: consentText }),
  payFanout: (id: string, paymentIntentId: string) => post<Accepted>(`${run(id)}/pay/fanout`, { payment_intent_id: paymentIntentId }),

  receipt: (id: string) => get<Receipt>(`${run(id)}/receipt`),
  verify: (id: string) => get<VerifyResult>(`${run(id)}/verify`),

  // The chat start page. Sessions live in the backend's memory.
  runs: () => get<RunSummary[]>("/api/runs"),
  chatCreate: (referenceSearch = true) => post<ChatSession>("/api/chat/sessions", { reference_search: referenceSearch }),
  chatSessions: () => get<ChatSessionSummary[]>("/api/chat/sessions"),
  chatSession: (id: string) => get<ChatSession>(`${chat(id)}`),
  /** Multipart: text, a link and up to two photos (resized in the browser first). */
  chatSend: (id: string, input: { text?: string; link?: string | null; images?: File[]; referenceSearch?: boolean }) => {
    const form = new FormData();
    if (input.text) form.append("text", input.text);
    if (input.link) form.append("link", input.link);
    if (input.referenceSearch !== undefined) form.append("reference_search", String(input.referenceSearch));
    for (const file of input.images ?? []) form.append("images", file);
    return request<ChatSendResponse>(`${chat(id)}/messages`, { method: "POST", body: form });
  },
  /** The Sign button: the person's action. Chat text can never reach it. */
  chatSign: (id: string, mandate: MandatePreset) => post<ChatSendResponse>(`${chat(id)}/mandate`, mandate),
  chatSync: (id: string) => post<ChatSendResponse>(`${chat(id)}/sync`),
  chatAssumption: (id: string, body: AssumptionRequest) => post<ChatSendResponse>(`${chat(id)}/assumptions`, body),
  /** The run's SSE stream, ending once the run stops (the chat's progress card). */
  eventsOnceUrl: (id: string) => `${API_BASE}${run(id)}/events?close=true`,

  /** What the agent remembers about this user, and the last improve pass (the Memory panel). */
  memory: () => get<MemoryResponse>("/api/memory"),
  /** The Forget button: the person's action, never an agent tool. */
  memoryForget: (scope: ForgetRequest["scope"] = "everything") => post<ForgetResponse>("/api/memory/forget", { scope }),

  /** Mock mode only: extra view samples (view_diagram_esp32.json, view_photo_sample.json). */
  mockView: (name: string) => get<ViewData>(`/api/mock/fixtures/${encodeURIComponent(name)}`),
};
