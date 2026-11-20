"""The simulated store: offers from data/mock_store.json (PLAN §3.11). Owner: B.

Includes one listing whose description carries an injected instruction, for the refusal demo.
A listing's text is data. It is never an instruction.
"""

from __future__ import annotations

import json

from app.config import DATA_DIR
from app.models import Offer, PartQuery
from app.stores.base import RunCtx, mock_refresh


class MockStore:
    source_api = "mock"
    hosts: frozenset[str] = frozenset()

    async def search(self, q: PartQuery, ctx: RunCtx) -> list[Offer]:
        rows = json.loads((DATA_DIR / "mock_store.json").read_text(encoding="utf-8"))
        return [Offer.model_validate({k: v for k, v in r.items() if k != "bom_line_id"}) for r in rows if r.get("bom_line_id") == q.bom_line_id]

    async def refresh(self, offer: Offer, ctx: RunCtx) -> Offer | None:
        return mock_refresh(offer, ctx)
