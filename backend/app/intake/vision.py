"""Photo parts: Claude vision's visible parts, boxes refined by SIE grounding-dino when available (PLAN §3.17, §3.20).

Owner: A (P14). D owns the SIE client (`registry.get("sie").detect`).

Box rules (PLAN §3.5, §3.17):
- The image Claude sees is the stored image (long edge <= 1,024 px), so its `[x1, y1, x2, y2]` are in the
  frame we display. Claude's boxes are approximate and are drawn dashed (`detector: "claude_vision"`).
- Boxes are clamped to the image; empty boxes and detections under 0.35 are dropped.
- If every coordinate is <= 1.0 the model answered in fractions: they are scaled to pixels.
- SIE boxes arrive as `box_xyxy_px` (D converts xywh in one place) and replace Claude's box for the
  matching label; SIE failing leaves Claude's boxes in place.
"""

from __future__ import annotations

from typing import Any

from app.models import PhotoPart

__all__ = ["normalize_parts", "identify_parts", "MIN_SCORE", "iou"]

MIN_SCORE = 0.35


def _clamp_box(box: Any, w: int, h: int) -> tuple[float, float, float, float] | None:
    try:
        x1, y1, x2, y2 = (float(v) for v in box)
    except (TypeError, ValueError):
        return None
    if max(x1, y1, x2, y2) <= 1.0:  # fractions of the image
        x1, x2, y1, y2 = x1 * w, x2 * w, y1 * h, y2 * h
    x1, x2 = sorted((x1, x2))
    y1, y2 = sorted((y1, y2))
    x1, y1, x2, y2 = max(0.0, x1), max(0.0, y1), min(float(w), x2), min(float(h), y2)
    if x2 - x1 < 2 or y2 - y1 < 2:
        return None
    return (round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1))


def normalize_parts(raw: list[dict[str, Any]] | None, sizes: list[tuple[int, int]], detector: str = "claude_vision") -> list[PhotoPart]:
    """Validate the classifier's `visible_parts` against the image sizes. Only image 0 is kept for the hotspot view."""
    out: list[PhotoPart] = []
    for item in raw or []:
        idx = int(item.get("image_index", 0) or 0)
        if idx != 0 or not sizes:
            continue
        w, h = sizes[0]
        box = _clamp_box(item.get("box_xyxy_px") or item.get("box"), w, h)
        try:
            score = float(item.get("score", 0))
        except (TypeError, ValueError):
            continue
        label = str(item.get("label") or "").strip().lower()
        if box is None or not label or score < MIN_SCORE:
            continue
        out.append(PhotoPart(label=label, category=str(item.get("category") or "mechanical"), box_xyxy_px=box,
                             score=round(min(score, 1.0), 2), detector=str(item.get("detector") or detector)))
    return out


def iou(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


async def identify_parts(parts: list[PhotoPart], image_jpeg: bytes | None, size: tuple[int, int], *, sie: Any = None) -> tuple[list[PhotoPart], str]:
    """Refine the classifier's parts with SIE detection. Returns (parts, detector used).

    The labels sent to SIE are the classifier's labels: detection only refines boxes, it never adds a
    part the classifier did not name.
    """
    kept = [p for p in parts if p.score >= MIN_SCORE]
    if sie is None or image_jpeg is None or not kept:
        return kept, "claude_vision"
    try:
        detected = await sie.detect(image_jpeg, sorted({p.label for p in kept}))
    except Exception:  # NotImplementedError while D's client is a stub; any SIE failure keeps Claude's boxes
        return kept, "claude_vision"
    refined: list[PhotoPart] = []
    used = False
    for p in kept:
        cands = [d for d in detected if d.label.lower() == p.label and d.score >= MIN_SCORE]
        best = max(cands, key=lambda d: iou(tuple(d.box_xyxy_px), tuple(p.box_xyxy_px)) + d.score * 0.01, default=None)
        box = _clamp_box(best.box_xyxy_px, *size) if best else None
        if best and box:
            used = True
            refined.append(PhotoPart(label=p.label, category=p.category, box_xyxy_px=box, score=round(best.score, 2),
                                     detector=best.detector or "sie:grounding-dino-base"))
        else:
            refined.append(p)
    return refined, ("sie:grounding-dino-base" if used else "claude_vision")
