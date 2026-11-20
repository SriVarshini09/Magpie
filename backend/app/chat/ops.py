"""What the chat may do, as calls into the existing backend functions. Nothing here invents a result.

`LiveOps` calls A's service (the same functions the HTTP routes call); `MockOps` answers from the fixtures
through `MockBackend`, where edits are accepted and the sample data does not change (`mock = True`, so the
chat says so). Neither has an approve, pay or checkout method: the chat cannot reach them.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.models import (
    AssumptionRequest, CartEditRequest, CreateRunRequest, Intake, MandateActions, MandateConstraints, MandateInputs, MandatePreset,
    MandateScope, OpenMandate, PartPanel, RefusalRecord, RunState, RunSummary, Signature, UniversalCart,
)

__all__ = ["LiveOps", "MockOps", "failure", "draft_mandate"]


def failure(exc: HTTPException) -> dict[str, Any]:
    """The `ApiError` body of a failed call, whatever shape `detail` has."""
    d = exc.detail
    if isinstance(d, dict):
        return {"status": exc.status_code, "error": d.get("error", "http_error"), "message": d.get("message") or "The request failed",
                "refusal": d.get("refusal")}
    return {"status": exc.status_code, "error": "http_error", "message": str(d or "The request failed"), "refusal": None}


def draft_mandate(preset: MandatePreset, build_type: str = "generic") -> OpenMandate:
    """An unsigned stand-in, used only to run the guard over chat text before any mandate is signed."""
    return OpenMandate(
        mandate_id="m_draft", run_id="r_draft", created_at="1970-01-01T00:00:00+00:00", expires_at="1970-01-01T00:00:00+00:00",
        scope=MandateScope(build_type=build_type, build_type_set_by="classifier", goal="", intake_sha256="0" * 64,  # type: ignore[arg-type]
                           inputs=MandateInputs(), template_id="", reference_search=True),
        constraints=MandateConstraints(budget_usd=preset.budget_usd, deadline=preset.deadline, ship_to_country=preset.ship_to_country,
                                       allowed_merchants=list(preset.allowed_merchants), data_sharing=preset.data_sharing,
                                       actions=MandateActions()),
        signature=Signature(jws="unsigned"))


class LiveOps:
    mock = False

    def _svc(self) -> Any:
        from app.agent import service

        service.install_hooks()
        return service

    async def intake(self, text: str | None, files: list[tuple[str, str | None, bytes]]) -> Intake:
        return await self._svc().intake(text, files, None)

    def get_intake(self, intake_id: str) -> Intake | None:
        from app import runstate

        return runstate.intakes.get(intake_id)

    def answers(self, intake_id: str, values: dict[str, str], build_type: str | None = None, skip_defaults: bool | None = None) -> Intake:
        return self._svc().answers(intake_id, values, build_type, skip_defaults)

    async def create_run(self, intake_id: str, preset: MandatePreset, reference_search: bool) -> str:
        res = await self._svc().create_run(CreateRunRequest(intake_id=intake_id, mandate=preset, reference_search=reference_search))
        return res.run_id

    def state(self, run_id: str) -> RunState:
        return self._svc().get_run(run_id)

    def panel(self, run_id: str, bom_line_id: str) -> PartPanel:
        return self._svc().get_panel(run_id, bom_line_id)

    def cart(self, run_id: str) -> UniversalCart:
        from app.checkout import cart as b_cart

        self._svc().run_or_404(run_id)
        return getattr(b_cart, "get_cart", b_cart.build_cart)(run_id)

    def replan(self, run_id: str, tier: str, cap: float | None) -> None:
        self._svc().replan(run_id, tier, cap)

    async def owned(self, run_id: str, bom_line_id: str, note: str) -> None:
        await self._svc().owned(run_id, bom_line_id, True, note)

    async def cart_edit(self, run_id: str, req: CartEditRequest) -> None:
        await self._svc().cart_edit(run_id, req)

    async def variant(self, run_id: str, option: str) -> None:
        await self._svc().variant(run_id, option)

    async def assumption(self, run_id: str, body: AssumptionRequest) -> None:
        await self._svc().assumption(run_id, body)

    def refuse(self, run_id: str, record: RefusalRecord, title: str) -> None:
        """Log a chat refusal in the run's hash chain and on its timeline."""
        self._svc().run_or_404(run_id).refuse(record.model_dump(), title)

    def note_user_message(self, run_id: str, text: str) -> None:
        self._svc().run_or_404(run_id).emit("agent.message", f"You: \"{text[:160]}\"", "info", data={"role": "user", "via": "chat"})

    def store_words(self, run_id: str | None) -> dict[str, str]:
        from app import runstate

        return self._svc()._stores_word_map(runstate.runs.get(run_id) if run_id else None)

    def stores(self) -> list[tuple[str, str]]:
        from app.stores import registry as store_registry

        return [(s.store_id, s.display_name) for s in store_registry.stores()]

    def runs(self) -> list[RunSummary]:
        from app import runstate

        out = []
        for run in runstate.runs.values():
            plan = run.plan()
            out.append(RunSummary(
                run_id=run.run_id, title=run.intake.summary or run.run_id, build_type=run.mandate.scope.build_type, status=run.status,  # type: ignore[arg-type]
                cart_state=run.cart_state, total_usd=plan.total_usd if plan else None, stores=len(plan.stores) if plan else 0,  # type: ignore[arg-type]
                lines=sum(ln.status != "removed" for ln in run.bom), created_at=run.mandate.created_at, simulated=run.simulated))
        return sorted(out, key=lambda r: r.created_at, reverse=True)


class MockOps:
    """DEMO_MODE=mock: the sample runs. Edits are accepted; the sample data does not change."""

    mock = True

    def __init__(self, backend: Any) -> None:
        self.b = backend

    async def intake(self, text: str | None, files: list[tuple[str, str | None, bytes]]) -> Intake:
        return Intake.model_validate(self.b.intake(text, [(n, c, len(b)) for n, c, b in files]))

    def get_intake(self, intake_id: str) -> Intake | None:
        try:
            return Intake.model_validate(self.b.get_intake(intake_id))
        except HTTPException:
            return None

    def answers(self, intake_id: str, values: dict[str, str], build_type: str | None = None, skip_defaults: bool | None = None) -> Intake:
        return Intake.model_validate(self.b.answers(intake_id, values, build_type, skip_defaults))

    async def create_run(self, intake_id: str, preset: MandatePreset, reference_search: bool) -> str:
        return self.b.create_run(intake_id, None)["run_id"]

    def state(self, run_id: str) -> RunState:
        return RunState.model_validate(self.b.run(run_id))

    def panel(self, run_id: str, bom_line_id: str) -> PartPanel:
        return PartPanel.model_validate(self.b.panel(run_id, bom_line_id))

    def cart(self, run_id: str) -> UniversalCart:
        return UniversalCart.model_validate(self.b.cart(run_id))

    def replan(self, run_id: str, tier: str, cap: float | None) -> None:
        self.b.replan(run_id, tier, cap)

    async def owned(self, run_id: str, bom_line_id: str, note: str) -> None:
        self.b.line(run_id, bom_line_id)

    async def cart_edit(self, run_id: str, req: CartEditRequest) -> None:
        self.b.line(run_id, req.bom_line_id)
        self.b.cart_edit(run_id)

    async def variant(self, run_id: str, option: str) -> None:
        self.b.run(run_id)

    async def assumption(self, run_id: str, body: AssumptionRequest) -> None:
        self.b.assumption(run_id, body.bom_line_id, body.action, body.spec, body.qty)

    def refuse(self, run_id: str, record: RefusalRecord, title: str) -> None:
        return None  # the sample chain is a fixture; the refusal stays on the chat session

    def note_user_message(self, run_id: str, text: str) -> None:
        return None

    def store_words(self, run_id: str | None) -> dict[str, str]:
        out: dict[str, str] = {}
        for sid, name in self.stores():
            out[sid.lower()] = sid
            out[name.lower()] = sid
        for extra in ("alibaba", "aliexpress", "ebay", "temu"):
            out.setdefault(extra, f"{extra}.com")
        return out

    def stores(self) -> list[tuple[str, str]]:
        from app import fixtures

        return [(s["store_id"], s["display_name"]) for s in fixtures.load("stores.json")]

    def runs(self) -> list[RunSummary]:
        out = []
        for run_id, run in self.b.runs.items():
            st = RunState.model_validate(run)
            plan = st.plans.get(st.active_tier)
            cart = self.b.carts.get(run_id) or {}
            out.append(RunSummary(run_id=run_id, title=st.intake.summary or run_id, build_type=st.build_type, status=st.status,
                                  cart_state=cart.get("state", "draft"), total_usd=plan.total_usd if plan else None,
                                  stores=len(plan.stores) if plan else 0, lines=sum(ln.status != "removed" for ln in st.bom),
                                  created_at=st.mandate.created_at, simulated=True))
        return out
