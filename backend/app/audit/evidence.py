"""Evidence store: every raw response we act on is written to `evidence/<run_id>/<sha256>.<ext>` (PLAN §3.11).

Owner: D.

- The file name IS the content hash, so a citation (`evidence_sha256`) can be re-checked at any time
  with `verify_evidence`. Files are written once and never rewritten (same bytes, same name).
- Secrets are stripped BEFORE hashing: API keys, tokens, passwords, `api_key=` query parameters,
  bearer tokens, `sk-…`, `sk_test_…`, `ghp_…`, `github_pat_…`, and the current value of every
  secret environment variable. Buyer fields (email, phone, address, name of a buyer) are redacted too:
  they must never reach an evidence file (CLAUDE.md rule 2).
- JSON payloads are stored as canonical JSON (sorted keys, no whitespace), so the same response
  always gets the same hash. Bytes are stored as-is (`.bin`), text as UTF-8 (`.txt`).
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from app.audit.chain import canonical_json, check_run_id, sha256_hex

REDACTED = "[redacted]"
SECRET_KEYS = re.compile(
    r"^(api[_-]?key|apikey|x[_-]api[_-]key|key|secret|client[_-]secret|token|access[_-]token|refresh[_-]token|"
    r"id[_-]token|password|passwd|authorization|auth|cookie|set[_-]cookie|session[_-]token|private[_-]key|jws_key)$",
    re.I,
)
BUYER_KEYS = re.compile(
    r"^(email|e[_-]?mail|phone|phone[_-]number|telephone|street|street[_-]address|address|address[_-]line[12]?|"
    r"postal[_-]code|zip|zip[_-]code|first[_-]name|last[_-]name|full[_-]name|buyer[_-]name|card[_-]number|cvc|cvv)$",
    re.I,
)
SECRET_PATTERNS = [
    (re.compile(r"(?i)([?&](?:api_key|apikey|key|token|access_token|client_secret)=)[^&#\s\"']+"), r"\1" + REDACTED),
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}"), "Bearer " + REDACTED),
    (re.compile(r"\bsk_(?:test|live)_[A-Za-z0-9]{6,}"), REDACTED),
    (re.compile(r"\b(?:pk|rk)_(?:test|live)_[A-Za-z0-9]{6,}"), REDACTED),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{8,}"), REDACTED),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"), REDACTED),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"), REDACTED),
    (re.compile(r"\bpersona_(?:sandbox|production)_[A-Za-z0-9_-]{8,}"), REDACTED),
    (re.compile(r"\b(?:secret|ck)-[A-Za-z0-9]{16,}"), REDACTED),
]
SECRET_ENV = (
    "ANTHROPIC_API_KEY", "SERPAPI_KEY", "SERPER_API_KEY", "KEENABLE_API_KEY", "EXA_API_KEY", "HF_TOKEN",
    "DIGIKEY_CLIENT_ID", "DIGIKEY_CLIENT_SECRET", "S2_URL", "SIE_API_KEY", "AIRBYTE_GITHUB_TOKEN",
    "AMPLITUDE_AI_API_KEY", "STATSIG_SERVER_SECRET", "COGNEE_API_KEY", "LLM_API_KEY", "STRIPE_SECRET_KEY",
    "STRIPE_CARDHOLDER_ID", "PERSONA_SANDBOX_KEY",
)
_DIR: dict[str, Path | None] = {"dir": None}


def configure(evidence_dir: str | Path | None) -> None:
    """Point the store at another folder (tests). None restores `backend/evidence`."""
    _DIR["dir"] = Path(evidence_dir) if evidence_dir is not None else None


def evidence_dir() -> Path:
    if _DIR["dir"] is not None:
        return _DIR["dir"]
    from app.audit.chain import runtime_dir

    return runtime_dir("evidence")


def _env_secrets() -> list[str]:
    vals = []
    for name in SECRET_ENV:
        v = (os.getenv(name) or "").strip()
        if len(v) >= 6:
            vals.append(v)
            if name == "S2_URL" and "@" in v:  # user:password@host -> also hide the password alone
                cred = v.split("@", 1)[0].split("//")[-1]
                if ":" in cred and len(cred.split(":", 1)[1]) >= 4:
                    vals.append(cred.split(":", 1)[1])
    return sorted(set(vals), key=len, reverse=True)


def scrub_text(text: str, env_values: list[str] | None = None) -> str:
    for value in env_values if env_values is not None else _env_secrets():
        text = text.replace(value, REDACTED)
    for pattern, repl in SECRET_PATTERNS:
        text = pattern.sub(repl, text)
    return text


def scrub(obj: Any, env_values: list[str] | None = None) -> Any:
    """A copy of `obj` with secrets and buyer fields redacted (keys by name, values by pattern)."""
    env_values = _env_secrets() if env_values is None else env_values
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            ks = str(k)
            if SECRET_KEYS.match(ks) or BUYER_KEYS.match(ks):
                out[k] = REDACTED if v not in (None, "", [], {}) else v
            elif ks.lower() in ("headers", "request_headers") and isinstance(v, dict):
                out[k] = {hk: (REDACTED if SECRET_KEYS.match(str(hk)) or str(hk).lower() in ("authorization", "cookie")
                               else scrub(hv, env_values)) for hk, hv in v.items()}
            else:
                out[k] = scrub(v, env_values)
        return out
    if isinstance(obj, (list, tuple)):
        return [scrub(x, env_values) for x in obj]
    if isinstance(obj, str):
        return scrub_text(obj, env_values)
    return obj


def encode(payload: Any) -> tuple[bytes, str]:
    """(bytes to store, extension) after scrubbing."""
    if isinstance(payload, bytes):
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError:
            return payload, "bin"
        clean = scrub_text(text)
        return (payload, "bin") if clean == text else (clean.encode("utf-8"), "txt")
    if isinstance(payload, str):
        return scrub_text(payload).encode("utf-8"), "txt"
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump(mode="json", by_alias=True)
    data = json.loads(json.dumps(payload, default=str, ensure_ascii=False))
    return canonical_json(scrub(data)).encode("utf-8"), "json"


def write_evidence(run_id: str, payload: Any) -> tuple[str, str]:
    """Write one raw response. Returns (path relative to backend/, sha256 hex of the stored bytes).

    The path uses forward slashes, e.g. `evidence/r_ab12/3f…e1.json` (PLAN §3.7 `evidence_path`).
    """
    check_run_id(run_id)
    data, ext = encode(payload)
    sha = sha256_hex(data)
    folder = evidence_dir() / run_id
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{sha}.{ext}"
    if not path.exists():
        tmp = folder / f".{sha}.{ext}.tmp"
        tmp.write_bytes(data)
        os.replace(tmp, path)
    return f"evidence/{run_id}/{sha}.{ext}", sha


def _resolve(rel_path: str) -> Path:
    rel = rel_path.replace("\\", "/")
    m = re.fullmatch(r"evidence/([A-Za-z0-9_\-]{1,80})/([0-9a-f]{64})\.(json|txt|bin)", rel)
    if not m:
        raise ValueError(f"not an evidence path: {rel_path!r}")
    return evidence_dir() / m.group(1) / f"{m.group(2)}.{m.group(3)}"


def read_evidence(rel_path: str) -> bytes:
    return _resolve(rel_path).read_bytes()


def verify_evidence(rel_path: str, sha256: str | None = None) -> bool:
    """True when the file exists and its bytes hash to its name (and to `sha256`, if given)."""
    try:
        path = _resolve(rel_path)
        digest = sha256_hex(path.read_bytes())
    except (OSError, ValueError):
        return False
    return digest == path.stem and (sha256 is None or digest == sha256)


def list_evidence(run_id: str) -> list[str]:
    check_run_id(run_id)
    folder = evidence_dir() / run_id
    if not folder.is_dir():
        return []
    return sorted(f"evidence/{run_id}/{p.name}" for p in folder.iterdir() if p.is_file() and not p.name.startswith("."))
