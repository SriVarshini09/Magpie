"""Superlinked SIE: encode, score (rerank), extract (spans), detect (photo boxes) (PLAN §3.15, §3.20). Owner: D.

Live calls use the installed `sie-sdk` (0.11.1) async client, read from the package source:
    SIEAsyncClient(base_url, api_key=…)                      base_url from SIE_BASE_URL; with only SIE_API_KEY the
                                                             SDK uses SIE Serverless
    await c.encode(model, [{"text": …}], is_query=…)         -> [{"dense": ndarray, …}]
    await c.score(model, {"text": query}, [{"id", "text"}])  -> {"scores": [{"item_id", "score", "rank"}]}
    await c.extract(model, {"text": …}, labels=[…])          -> {"entities": [{"text", "label", "score", "start", "end"}]}
    await c.extract("IDEA-Research/grounding-dino-base", {"images": [{"data": jpeg, "format": "jpeg"}]}, labels=[…])
                                                             -> {"objects": [{"label", "score", "bbox"}]}
The SDK waits for capacity on a cold start (503 PROVISIONING) by itself; we add one retry that honours
`retry_after` on ProvisioningError / RateLimitError.

Box format: the SDK docstring says `bbox` is [x, y, width, height] in pixels; the doc samples read like
[x1, y1, x2, y2]. `SIE_BOX_FORMAT` (xywh | xyxy, default xywh, settled by check C25) picks one, and
`to_xyxy()` is the ONE place that converts to `box_xyxy_px`. Detections under 0.35 are dropped.

Every call is timed and logged in CALL_LOG (step, model, latency, item count) for the footer
("SIE: N calls, median ms") and the Data drawer's SIE table (`call_table()`).
"""

from __future__ import annotations

import asyncio
import io
import os
import statistics
import time
from typing import Any, Protocol

from app import fixtures
from app.integrations.base import MOCK_LABEL
from app.models import PhotoPart

MIN_SCORE = 0.35
BOX_FORMATS = ("xywh", "xyxy")
DEFAULT_DETECT_MODEL = "IDEA-Research/grounding-dino-base"
DETECTOR = "sie:grounding-dino-base"
EXTRACT_LABELS = ["component", "model number", "voltage", "current", "connector", "pitch", "quantity"]
CALL_LOG: list[dict[str, Any]] = []
_LOG_CAP = 2000


class SIEConfigError(RuntimeError):
    """A model name or the key is missing. Raised before any network call."""


def to_xyxy(bbox: list[float] | tuple[float, ...], fmt: str | None = None, *, width: float | None = None,
            height: float | None = None) -> tuple[float, float, float, float] | None:
    """THE conversion from SIE's `bbox` to `box_xyxy_px` (PLAN §3.20). None for an empty or degenerate box.

    fmt "xywh": [x, y, w, h] -> [x, y, x + w, y + h];  fmt "xyxy": unchanged. The box is clamped to the image
    when its size is known.
    """
    fmt = (fmt or os.getenv("SIE_BOX_FORMAT") or "xywh").strip().lower()
    if fmt not in BOX_FORMATS:
        raise SIEConfigError(f"SIE_BOX_FORMAT must be one of {BOX_FORMATS}, got {fmt!r}")
    if not bbox or len(bbox) != 4:
        return None
    a, b, c, d = (float(v) for v in bbox)
    x1, y1, x2, y2 = (a, b, a + c, b + d) if fmt == "xywh" else (a, b, c, d)
    if width is not None:
        x1, x2 = max(0.0, min(x1, width)), max(0.0, min(x2, width))
    if height is not None:
        y1, y2 = max(0.0, min(y1, height)), max(0.0, min(y2, height))
    if x2 - x1 < 1 or y2 - y1 < 1:
        return None
    return (round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1))


def image_size(jpeg: bytes) -> tuple[int, int] | None:
    try:
        from PIL import Image

        with Image.open(io.BytesIO(jpeg)) as im:
            return im.size
    except Exception:
        return None


def _log(step: str, model: str, latency_ms: float, items: int, ok: bool, error: str | None = None) -> None:
    CALL_LOG.append({"step": step, "model": model, "latency_ms": round(latency_ms, 1), "items": items, "ok": ok,
                     "error": error, "at": time.time()})
    if len(CALL_LOG) > _LOG_CAP:
        del CALL_LOG[: len(CALL_LOG) - _LOG_CAP]


def call_table() -> list[dict[str, Any]]:
    """[{step, model, calls, median_ms, errors}] for the Data drawer's SIE table (four rows when all four run)."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for c in CALL_LOG:
        groups.setdefault((c["step"], c["model"]), []).append(c)
    return [{"step": s, "model": m, "calls": len(cs), "median_ms": int(statistics.median(x["latency_ms"] for x in cs)),
             "errors": sum(1 for x in cs if not x["ok"])} for (s, m), cs in groups.items()]


def stats() -> dict[str, Any]:
    ok = [c["latency_ms"] for c in CALL_LOG if c["ok"]]
    return {"calls": len(CALL_LOG), "median_ms": int(statistics.median(ok)) if ok else 0}


class SIE(Protocol):
    async def encode(self, texts: list[str], is_query: bool = False) -> list[list[float]]: ...

    async def score(self, query: str, items: list[str]) -> list[float]: ...

    async def extract(self, text: str, labels: list[str]) -> list[dict[str, Any]]: ...

    async def detect(self, image_jpeg: bytes, labels: list[str]) -> list[PhotoPart]:
        """grounding-dino-base boxes, converted to box_xyxy_px in ONE place (box format: check C25)."""
        ...


class MockSIE:
    """No network. Labelled: vectors are zeros, scores are flat, extract is a local pattern reader (provider "mock"),
    detection replays the sample photo fixture."""

    def configured(self) -> bool:
        return False

    async def encode(self, texts: list[str], is_query: bool = False) -> list[list[float]]:
        return [[0.0] * 8 for _ in texts]  # mock vectors: all zeros, 8 dims

    async def score(self, query: str, items: list[str]) -> list[float]:
        return [0.5 for _ in items]

    async def extract(self, text: str, labels: list[str] | None = None) -> list[dict[str, Any]]:
        """MOCK: a local pattern reader, not SIE. Same span shape, provider "mock", simulated, no score."""
        from app.rules import spec_reads  # lazy: the rules import nothing from here

        return [{**s, **MOCK_LABEL} for s in spec_reads.pattern_spans(text, labels)]

    async def detect(self, image_jpeg: bytes, labels: list[str]) -> list[PhotoPart]:
        return [PhotoPart.model_validate(p) for p in fixtures.load("intake_photo.json")["visible_parts"]]


class LiveSIE:
    """SIE Serverless (or any SIE base URL). Models come from SIE_EMBED_MODEL / _RERANK_ / _EXTRACT_ / _DETECT_MODEL."""

    def __init__(self, client: Any | None = None, *, base_url: str | None = None, api_key: str | None = None,
                 models: dict[str, str] | None = None, box_format: str | None = None, retries: int = 1) -> None:
        self._client = client
        self._base_url = base_url
        self._api_key = api_key
        self._models = models or {}
        self._box_format = box_format
        self._retries = retries

    # ------------------------------------------------------------------ config

    def configured(self) -> bool:
        return bool(self._client is not None or self._api_key or os.getenv("SIE_API_KEY") or os.getenv("SIE_BASE_URL"))

    def model(self, step: str) -> str:
        env = {"encode": "SIE_EMBED_MODEL", "score": "SIE_RERANK_MODEL", "extract": "SIE_EXTRACT_MODEL",
               "detect": "SIE_DETECT_MODEL"}[step]
        name = self._models.get(step) or (os.getenv(env) or "").strip() or (DEFAULT_DETECT_MODEL if step == "detect" else "")
        if not name:
            raise SIEConfigError(f"{env} is not set: copy the model name from the SIE console (PLAN §3.3)")
        return name

    def client(self) -> Any:
        if self._client is None:
            if not self.configured():
                raise SIEConfigError("SIE_API_KEY (or SIE_BASE_URL) is not set")
            from sie_sdk import SIEAsyncClient  # lazy: a missing SDK breaks only this service

            self._client = SIEAsyncClient(self._base_url or os.getenv("SIE_BASE_URL") or None,
                                          api_key=self._api_key or os.getenv("SIE_API_KEY") or None)
        return self._client

    async def _call(self, step: str, model: str, n_items: int, fn: Any) -> Any:
        t0 = time.perf_counter()
        attempt = 0
        while True:
            try:
                out = await fn()
                _log(step, model, (time.perf_counter() - t0) * 1000, n_items, True)
                return out
            except Exception as exc:
                retry_after = getattr(exc, "retry_after", None)
                retryable = type(exc).__name__ in ("ProvisioningError", "RateLimitError", "ModelLoadingError")
                if retryable and attempt < self._retries:
                    attempt += 1
                    await asyncio.sleep(min(float(retry_after or 2.0), 20.0))
                    continue
                _log(step, model, (time.perf_counter() - t0) * 1000, n_items, False, type(exc).__name__)
                raise

    # ------------------------------------------------------------------ the four uses

    async def encode(self, texts: list[str], is_query: bool = False) -> list[list[float]]:
        """Dense vectors for KB chunks (seed time) and for each lookup query. Order matches `texts`."""
        if not texts:
            return []
        model = self.model("encode")
        res = await self._call("encode", model, len(texts),
                               lambda: self.client().encode(model, [{"text": t} for t in texts], is_query=is_query))
        res = res if isinstance(res, list) else [res]
        out = []
        for r in res:
            dense = r.get("dense") if isinstance(r, dict) else None
            out.append([float(x) for x in (dense.tolist() if hasattr(dense, "tolist") else (dense or []))])
        return out

    async def score(self, query: str, items: list[str]) -> list[float]:
        """Rerank scores for `items` against `query`, in the order of `items` (the SDK returns them sorted)."""
        if not items:
            return []
        model = self.model("score")
        payload = [{"id": f"i{n}", "text": t} for n, t in enumerate(items)]
        res = await self._call("score", model, len(items), lambda: self.client().score(model, {"text": query}, payload))
        by_id = {e.get("item_id"): float(e.get("score", 0.0)) for e in (res.get("scores") or [])}
        return [by_id.get(f"i{n}", 0.0) for n in range(len(items))]

    async def extract(self, text: str, labels: list[str] | None = None) -> list[dict[str, Any]]:
        """Attribute spans (component, model number, voltage, current, connector, pitch, quantity) with offsets."""
        model = self.model("extract")
        labels = labels or EXTRACT_LABELS
        # GLiNER's own default threshold (0.5) drops real specs; 0.3 here, and spec_reads keeps only spans >= 0.35
        thr = float(os.getenv("SIE_EXTRACT_THRESHOLD") or 0.3)
        res = await self._call("extract", model, 1,
                               lambda: self.client().extract(model, {"text": text}, labels=labels, options={"threshold": thr}))
        res = res[0] if isinstance(res, list) else res
        out = []
        for e in res.get("entities") or []:
            start, end = e.get("start"), e.get("end")
            span = text[start:end] if isinstance(start, int) and isinstance(end, int) else e.get("text", "")
            out.append({"label": e.get("label"), "text": span, "score": float(e.get("score", 0.0)), "start": start, "end": end,
                        "provider": "sie", "model": model})
        return out

    async def detect(self, image_jpeg: bytes, labels: list[str], size: tuple[int, int] | None = None) -> list[PhotoPart]:
        """Boxes on the user's photo for the given labels. Scores under 0.35 and empty boxes are dropped."""
        if not labels:
            return []
        model = self.model("detect")
        w, h = size or image_size(image_jpeg) or (None, None)
        item = {"images": [{"data": image_jpeg, "format": "jpeg"}]}
        res = await self._call("detect", model, 1, lambda: self.client().extract(model, item, labels=list(labels)))
        res = res[0] if isinstance(res, list) else res
        parts = []
        for obj in res.get("objects") or []:
            score = float(obj.get("score", 0.0))
            if score < MIN_SCORE:
                continue
            box = to_xyxy(obj.get("bbox") or [], self._box_format, width=w, height=h)
            if box is None:
                continue
            parts.append(PhotoPart(label=str(obj.get("label", "")).lower(), category="", box_xyxy_px=box,
                                   score=round(score, 3), detector=DETECTOR))
        return parts

    async def warm(self) -> dict[str, Any]:
        """One small call per configured model (cold start absorbs here, not on stage). Used by warm_sie.py."""
        out: dict[str, Any] = {}
        for step, call in (("encode", lambda: self.encode(["warm up"], is_query=True)),
                           ("score", lambda: self.score("12V power supply", ["12V 5A power supply 5.5x2.1mm"])),
                           ("extract", lambda: self.extract("STS3215 12V servo, JST-PH 2.0 connector")),
                           ("detect", lambda: self.detect(_tiny_jpeg(), ["servo motor"], size=(64, 64)))):
            t0 = time.perf_counter()
            try:
                self.model(step)
                await call()
                out[step] = {"ok": True, "ms": int((time.perf_counter() - t0) * 1000)}
            except Exception as exc:
                out[step] = {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:160]}"}
        return out

    async def aclose(self) -> None:
        if self._client is not None and hasattr(self._client, "close"):
            await self._client.close()


def _tiny_jpeg() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (128, 128, 128)).save(buf, format="JPEG")
    return buf.getvalue()
