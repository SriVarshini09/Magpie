"""Open, closed and payment mandates: build, hash, sign with ES256 (PLAN §3.7, §12.4). Owner: D.

The demo signing key stands in for a key the user would hold. It is generated at first use and
stored at MANDATE_KEY_PATH (default `runs/demo_es256.pem`, git-ignored, `*.pem` is ignored too).

What is hashed and signed
    signed body   = the mandate without `signature`
                    payment mandate: also without `mandate_hash`, `payment`, `status` and each
                    allocation's `instrument`, `authorization_id`, `status` (these change while the
                    test payment runs; the consent, amounts and stores do not)
    mandate_sha256(m) = sha256 hex of canonical_json(signed body)       (open_mandate_sha256, chain records)
    payment `mandate_hash` = "sha256:" + mandate_sha256(payment)        (PLAN §12.4)
    signature.jws = RFC 7797 detached compact JWS: BASE64URL(header) + ".." + BASE64URL(sig),
                    header {"alg": "ES256", "b64": false, "crit": ["b64"], "kid": …, "typ": "b2c-mandate"},
                    signing input = BASE64URL(header) + "." + canonical_json(signed body).
                    PyJWT verifies it with `detached_payload=` (see `verify_mandate`).
Signatures are deterministic (RFC 6979) when the installed OpenSSL supports it, so re-signing the
same body gives the same JWS and the sample fixtures stay stable.

The fixture key (`fixture_key()`) is derived from a public seed: anyone can sign with it. It exists
only so mock fixtures carry verifiable signatures, and it is labelled as such everywhere.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from app.audit.chain import canonical_json, check_run_id, now_iso, sha256_hex

DEMO_KID = "demo-key-1"
FIXTURE_KID = "fixture-key-1"
FIXTURE_SEED = b"build-to-cart fixture signing key: PUBLIC SEED, NOT A SECRET, mock fixtures only"
MANDATE_VERSION = "0.4"
PAYMENT_EXEC_FIELDS = ("mandate_hash", "payment", "status")
ALLOCATION_EXEC_FIELDS = ("instrument", "authorization_id", "status")

_lock = threading.Lock()
_override: dict[str, Any] = {}  # {"key": private_key, "kid": str} for tests / the fixture signer
_cache: dict[str, Any] = {}  # loaded demo key, keyed by path


# --------------------------------------------------------------------------- keys


def key_path() -> Path:
    from app.config import BACKEND_DIR, get_settings

    p = Path(get_settings().mandate_key_path)
    if p.is_absolute():
        return p
    from app.audit.chain import runtime_dir, under_pytest

    return runtime_dir("runs") / p.name if under_pytest() else BACKEND_DIR / p


def _ec():
    from cryptography.hazmat.primitives.asymmetric import ec

    return ec


def load_or_create_key(path: Path | None = None) -> Any:
    """The demo ES256 private key. Generated (P-256) and written as PKCS#8 PEM on first use."""
    from cryptography.hazmat.primitives import serialization

    path = path or key_path()
    with _lock:
        if str(path) in _cache:
            return _cache[str(path)]
        if path.is_file():
            key = serialization.load_pem_private_key(path.read_bytes(), password=None)
        else:
            key = _ec().generate_private_key(_ec().SECP256R1())
            path.parent.mkdir(parents=True, exist_ok=True)
            pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption())
            path.write_bytes(pem)
        _cache[str(path)] = key
        return key


def fixture_key() -> Any:
    """Deterministic P-256 key from a PUBLIC seed. For mock fixtures only: it proves nothing."""
    ec = _ec()
    n = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551  # P-256 order
    d = int.from_bytes(hashlib.sha256(FIXTURE_SEED).digest(), "big") % (n - 1) + 1
    return ec.derive_private_key(d, ec.SECP256R1())


def use_key(key: Any | None, kid: str | None = None) -> None:
    """Sign with this key instead of the demo key (None restores the demo key). Tests and fixture signing."""
    _override.clear()
    if key is not None:
        _override.update(key=key, kid=kid or DEMO_KID)


def signing_key() -> tuple[Any, str]:
    if _override:
        return _override["key"], _override["kid"]
    return load_or_create_key(), DEMO_KID


def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64u_int(n: int) -> str:
    return _b64u(n.to_bytes(32, "big"))


def public_jwk(key: Any | None = None, kid: str | None = None) -> dict[str, Any]:
    """The public half as a JWK (RFC 7517), for the receipt."""
    if key is None:
        key, default_kid = signing_key()
        kid = kid or default_kid
    pub = key.public_key() if hasattr(key, "public_key") else key
    nums = pub.public_numbers()
    jwk = {"kty": "EC", "crv": "P-256", "x": _b64u_int(nums.x), "y": _b64u_int(nums.y), "alg": "ES256", "use": "sig",
           "kid": kid or DEMO_KID}
    if (kid or "") == FIXTURE_KID:
        jwk["note"] = "fixture key derived from a public seed: these signatures only show the format"
    else:
        jwk["note"] = "demo key generated by the backend; it stands in for a key the user would hold"
    return jwk


def key_from_jwk(jwk: dict[str, Any]) -> Any:
    ec = _ec()

    def b(s: str) -> int:
        return int.from_bytes(base64.urlsafe_b64decode(s + "=" * (-len(s) % 4)), "big")

    if jwk.get("kty") != "EC" or jwk.get("crv") != "P-256":
        raise ValueError("not a P-256 EC JWK")
    return ec.EllipticCurvePublicNumbers(b(jwk["x"]), b(jwk["y"]), ec.SECP256R1()).public_key()


def keyring() -> dict[str, Any]:
    """Public keys Verify trusts by kid: the backend's demo key and the (public) fixture key."""
    ring = {FIXTURE_KID: fixture_key().public_key()}
    try:
        key, kid = signing_key()
        ring[kid] = key.public_key()
        if kid != DEMO_KID:
            ring.setdefault(DEMO_KID, load_or_create_key().public_key())
    except Exception:
        pass
    return ring


# --------------------------------------------------------------------------- hashing


def _plain(m: Any) -> dict[str, Any]:
    if hasattr(m, "model_dump"):
        return m.model_dump(mode="json", by_alias=True, exclude_none=True)
    return json.loads(json.dumps(m))


def signed_body(mandate: Any) -> dict[str, Any]:
    """The part of a mandate that is hashed and signed (module docstring)."""
    m = _plain(mandate)
    body = {k: v for k, v in m.items() if k != "signature"}
    if m.get("type") == "b2c.mandate.payment":
        body = {k: v for k, v in body.items() if k not in PAYMENT_EXEC_FIELDS}
        body["allocations"] = [{k: v for k, v in a.items() if k not in ALLOCATION_EXEC_FIELDS}
                               for a in body.get("allocations", [])]
    return body


def mandate_sha256(mandate: Any) -> str:
    """sha256 hex of the canonical signed body. Used for `open_mandate_sha256`, `closed_mandate_sha256`
    and the `mandate_sha256` field of `mandate_open` / `mandate_closed` / `payment_mandate` records."""
    return sha256_hex(canonical_json(signed_body(mandate)))


def payment_mandate_hash(mandate: Any) -> str:
    return "sha256:" + mandate_sha256(mandate)


# --------------------------------------------------------------------------- JWS


def _header(kid: str) -> dict[str, Any]:
    return {"alg": "ES256", "b64": False, "crit": ["b64"], "kid": kid, "typ": "b2c-mandate"}


def _sign_bytes(key: Any, signing_input: bytes) -> bytes:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

    ec = _ec()
    try:
        algo = ec.ECDSA(hashes.SHA256(), deterministic_signing=True)
        der = key.sign(signing_input, algo)
    except Exception:  # OpenSSL without RFC 6979: a random k is still a valid ES256 signature
        der = key.sign(signing_input, ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    return r.to_bytes(32, "big") + s.to_bytes(32, "big")


def jws_detached(payload: bytes, key: Any, kid: str) -> str:
    h = _b64u(canonical_json(_header(kid)).encode("utf-8"))
    sig = _sign_bytes(key, h.encode("ascii") + b"." + payload)
    return f"{h}..{_b64u(sig)}"


def sign_mandate(body: dict[str, Any], *, key: Any | None = None, kid: str | None = None,
                 run_id: str | None = None, record: bool = True) -> dict[str, Any]:
    """Return the mandate with `signature` = ES256 detached JWS over its signed body.

    A payment mandate also gets `mandate_hash` first. The signed mandate is remembered for the
    run's receipt (`record=False` to skip, e.g. when signing fixtures).
    """
    m = _plain(body)
    if key is None:
        key, default_kid = signing_key()
        kid = kid or default_kid
    kid = kid or DEMO_KID
    m.pop("signature", None)
    if m.get("type") == "b2c.mandate.payment":
        m["mandate_hash"] = payment_mandate_hash(m)
    payload = canonical_json(signed_body(m)).encode("utf-8")
    m["signature"] = {"alg": "ES256", "kid": kid, "jws": jws_detached(payload, key, kid)}
    if record:
        remember_mandate(m, run_id=run_id)
    return m


def verify_detail(mandate: Any, public_key: Any | None = None, jwk: dict[str, Any] | None = None) -> tuple[bool, str]:
    """(ok, reason). Checks alg, kid, the b64/crit header and the ES256 signature with PyJWT."""
    import jwt
    from jwt.api_jws import PyJWS

    m = _plain(mandate)
    sig = m.get("signature") or {}
    jws = sig.get("jws") or ""
    if sig.get("alg") != "ES256":
        return False, f"alg is {sig.get('alg')!r}, not ES256"
    parts = jws.split(".")
    if len(parts) != 3 or parts[1] != "":
        return False, "not a detached compact JWS (placeholder signature?)"
    try:
        header = json.loads(base64.urlsafe_b64decode(parts[0] + "=" * (-len(parts[0]) % 4)))
    except Exception:
        return False, "unreadable JWS header"
    if header.get("kid") != sig.get("kid"):
        return False, "JWS kid does not match signature.kid"
    if public_key is None and jwk is not None:
        try:
            public_key = key_from_jwk(jwk)
        except Exception as exc:
            return False, f"bad JWK: {exc}"
    if public_key is None:
        public_key = keyring().get(sig.get("kid", ""))
        if public_key is None:
            return False, f"unknown key id {sig.get('kid')!r}"
    if m.get("type") == "b2c.mandate.payment" and m.get("mandate_hash") and m["mandate_hash"] != payment_mandate_hash(m):
        return False, "mandate_hash does not match the payment mandate body"
    payload = canonical_json(signed_body(m)).encode("utf-8")
    try:
        PyJWS().decode_complete(jws, key=public_key, algorithms=["ES256"], detached_payload=payload)
    except jwt.InvalidSignatureError:
        return False, "signature does not match the mandate body"
    except jwt.PyJWTError as exc:
        return False, f"{type(exc).__name__}: {exc}"
    return True, "ES256 signature valid"


def verify_mandate(mandate: Any, public_key: Any | None = None, jwk: dict[str, Any] | None = None) -> bool:
    """True when the mandate's ES256 signature matches its body under the given (or the kid's) key."""
    return verify_detail(mandate, public_key, jwk)[0]


# --------------------------------------------------------------------------- per-run memory


_BY_RUN: dict[str, dict[str, dict[str, Any]]] = {}
_OPEN_BY_SHA: dict[str, str] = {}
_CLOSED_BY_SHA: dict[str, str] = {}
_TYPE_KEY = {"b2c.mandate.open": "open", "b2c.mandate.closed": "closed", "b2c.mandate.payment": "payment"}


def _run_of(m: dict[str, Any]) -> str | None:
    if m.get("run_id"):
        return m["run_id"]
    if m.get("type") == "b2c.mandate.closed":
        return _OPEN_BY_SHA.get(m.get("open_mandate_sha256", ""))
    if m.get("type") == "b2c.mandate.payment":
        return _CLOSED_BY_SHA.get(m.get("closed_mandate_sha256", ""))
    return None


def remember_mandate(mandate: dict[str, Any], run_id: str | None = None) -> str | None:
    """Keep a signed mandate for the run's receipt (memory + the `mandates` table when live)."""
    m = _plain(mandate)
    kind = _TYPE_KEY.get(m.get("type", ""))
    rid = run_id or _run_of(m)
    if kind is None or rid is None:
        return None
    check_run_id(rid)
    sha = mandate_sha256(m)
    with _lock:
        _BY_RUN.setdefault(rid, {})[kind] = m
        if kind == "open":
            _OPEN_BY_SHA[sha] = rid
        elif kind == "closed":
            _CLOSED_BY_SHA[sha] = rid
    try:
        from app.audit import chain as chain_mod

        if chain_mod._persist_on():
            path = chain_mod.runs_dir() / rid / "mandates.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8", newline="\n") as f:
                f.write(canonical_json(m) + "\n")
    except OSError:
        pass
    try:
        from app import registry

        if registry.impl_mode("singlestore") == "live":
            registry.get("singlestore").insert_mandate_sync(
                {"mandate_id": m.get("mandate_id") or f"{kind}_{sha[:12]}", "run_id": rid, "type": m["type"], "body": m,
                 "sha256": sha, "jws": (m.get("signature") or {}).get("jws")})
    except Exception:
        pass
    return rid


def mandates_for(run_id: str) -> dict[str, dict[str, Any]]:
    """{"open": …, "closed": …, "payment": …} for a run (only those that exist)."""
    with _lock:
        return copy.deepcopy(_BY_RUN.get(run_id, {}))


def reset() -> None:
    """Tests only."""
    with _lock:
        _BY_RUN.clear()
        _OPEN_BY_SHA.clear()
        _CLOSED_BY_SHA.clear()


# --------------------------------------------------------------------------- builders (§3.7, §12.4)


def _normalized(model: Any, body: dict[str, Any]) -> dict[str, Any]:
    """The body exactly as the contract model dumps it (defaults filled, nulls dropped), minus `signature`.

    Signing this form means a mandate that round-trips through the model still verifies.
    """
    dumped = model.model_validate({**body, "signature": {"jws": "unsigned"}}).model_dump(mode="json", by_alias=True,
                                                                                          exclude_none=True)
    dumped.pop("signature", None)
    return dumped


def _iso_plus(ts: str, hours: float) -> str:
    return (datetime.fromisoformat(ts) + timedelta(hours=hours)).isoformat(timespec="seconds")


def build_open_mandate(run_id: str, scope: dict[str, Any], constraints: dict[str, Any], *, created_at: str | None = None,
                       expires_at: str | None = None, ttl_hours: float = 6, user_id: str = "demo_user",
                       mandate_id: str | None = None, simulated: bool = False) -> dict[str, Any]:
    """A signed OPEN mandate (validated against models.OpenMandate). `actions.pay` is forced false."""
    from app.models import MandateActions, OpenMandate

    created = created_at or now_iso()
    cons = _plain(constraints)
    cons.setdefault("actions", MandateActions().model_dump())
    cons["actions"]["pay"] = False  # PLAN §3.7: false for the agent in every mode
    cons["actions"]["checkout"] = False
    body = {"type": "b2c.mandate.open", "version": MANDATE_VERSION,
            "note": "AP2-inspired (v0.2 open Checkout Mandate shape); not AP2-compliant",
            "mandate_id": mandate_id or f"m_{uuid.uuid4().hex[:12]}", "run_id": check_run_id(run_id), "user_id": user_id,
            "created_at": created, "expires_at": expires_at or _iso_plus(created, ttl_hours),
            "scope": _plain(scope), "constraints": cons, "simulated": simulated}
    return sign_mandate(_normalized(OpenMandate, body), run_id=run_id)


def build_closed_mandate(open_mandate: dict[str, Any], *, plan_id: str, plan_sha256: str, tier: str,
                         handoffs: list[Any], total_usd: float, prices_checked_at: str, approval_token: str,
                         chain_head: str, approved_at: str | None = None, step_up: dict[str, Any] | None = None,
                         simulated: bool = False) -> dict[str, Any]:
    """A signed CLOSED mandate bound to the open mandate, the plan, every hand-off URL and the chain head.

    Only the approval token's sha256 is stored, never the token.
    """
    from app.models import ClosedMandate

    hs = [_plain(h) for h in handoffs]
    for h in hs:
        if h.get("url") and h.get("url_sha256") != sha256_hex(h["url"]):
            raise ValueError(f"hand-off {h.get('store_id')}: url_sha256 does not match its url")
    body = {"type": "b2c.mandate.closed", "version": MANDATE_VERSION, "open_mandate_sha256": mandate_sha256(open_mandate),
            "plan_id": plan_id, "plan_sha256": plan_sha256, "tier": tier, "handoffs": hs, "total_usd": round(float(total_usd), 2),
            "prices_checked_at": prices_checked_at, "approved_by": "ui_button", "approved_at": approved_at or now_iso(),
            "approval_token_sha256": sha256_hex(approval_token), "chain_head": chain_head, "step_up": step_up,
            "simulated": simulated}
    if step_up is None:
        body.pop("step_up")
    return sign_mandate(_normalized(ClosedMandate, body), run_id=_plain(open_mandate).get("run_id"))


def build_payment_mandate(closed_mandate: dict[str, Any], *, consent_text: str, allocations: list[dict[str, Any]],
                          consent_at: str | None = None, mandate_id: str | None = None, currency: str = "usd") -> dict[str, Any]:
    """A signed PAYMENT mandate (Tier 2, TEST MODE only), created BEFORE the PaymentIntent (PLAN §12.4).

    `allocations`: [{store_id, action_level, url_sha256, limit (cents)}]; one per store in the cart.
    The sum of limits is the total. Status starts "open"; execution fields are filled in later and are
    not covered by the signature (module docstring).
    """
    from app.models import PaymentMandate

    if "TEST MODE" not in consent_text:
        raise ValueError("the consent text shown to the user must say TEST MODE")
    allocs = []
    for a in allocations:
        a = _plain(a)
        allocs.append({"store_id": a["store_id"], "action_level": a["action_level"], "url_sha256": a["url_sha256"],
                       "limit": int(a["limit"]), "simulated": True, "status": a.get("status", "pending")})
    total = sum(a["limit"] for a in allocs)
    body = {"type": "b2c.mandate.payment", "version": MANDATE_VERSION, "mode": "test",
            "mandate_id": mandate_id or f"mnd_{uuid.uuid4().hex[:12]}", "closed_mandate_sha256": mandate_sha256(closed_mandate),
            "status": "open", "user_consent": {"at": consent_at or now_iso(), "text_shown": consent_text},
            "total": {"amount": total, "currency": currency}, "allocations": allocs, "mandate_hash": "", "simulated": True}
    norm = _normalized(PaymentMandate, body)
    return sign_mandate(norm)
