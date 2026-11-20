"""Airbyte GitHub connector: project README, commit SHA, directory listing (PLAN §3.15). Owner: A.

Live path: `airbyte_agent_sdk.connectors.github.GithubConnector` (entities read from the installed
SDK: `commits.list`, `file_content.get`, `directory_content.list`), `via: "airbyte.github"`.
Fallback: raw `httpx` to api.github.com and raw.githubusercontent.com, `via: "http"`. The fallback is
reported as what it is; it is not counted as an Airbyte read.

Every read returns the exact bytes we hash, and a `reads` list (entity, action, params, bytes, sha256)
for the `source_fetch` records.
"""

from __future__ import annotations

import base64
import os
import re
from typing import Any, Protocol

from app import fixtures
from app.audit.chain import sha256_hex
from app.config import FIXTURES_DIR
from app.models import SourceDoc
from app.stores.http import HostNotAllowed, is_never_request

GITHUB_HOSTS = frozenset({"api.github.com", "raw.githubusercontent.com"})
_REPO = re.compile(r"^https://(?:www\.)?github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?(?:/(?:tree|blob)/([^/]+)(?:/(.*))?)?/?(?:[?#].*)?$")
README_NAMES = ("README.md", "readme.md", "Readme.md", "README.MD", "README.rst", "README")


def parse_repo_url(url: str) -> tuple[str, str, str | None] | None:
    """(owner, repo, ref) for a GitHub repository URL, else None."""
    m = _REPO.match(url.strip())
    return (m.group(1), m.group(2), m.group(3)) if m else None


def is_github_repo(url: str) -> bool:
    return parse_repo_url(url) is not None


class GitHubSource(Protocol):
    async def fetch_readme(self, repo_url: str) -> SourceDoc:
        """README of the default branch, pinned to the latest commit SHA, hashed on arrival."""
        ...

    async def list_dir(self, repo_url: str, path: str) -> list[str]: ...


class MockGitHubSource:
    """Returns the bundled copy of the SO-ARM100 README (fixtures/sources/, Apache-2.0)."""

    reads: list[dict[str, Any]] = []

    async def fetch_readme(self, repo_url: str) -> SourceDoc:
        src = fixtures.load("run_so101.json")["source"]
        asked, bundled = parse_repo_url(repo_url), parse_repo_url(src["url"])
        if asked is not None and bundled is not None and [x.lower() for x in asked[:2]] != [x.lower() for x in bundled[:2]]:
            # never hand back another project's README under this repository's name
            raise LookupError(f"mock GitHub source: only {bundled[0]}/{bundled[1]} is bundled. "
                              f"Reading {asked[0]}/{asked[1]} needs IMPL_AIRBYTE_GITHUB=live")
        raw = (FIXTURES_DIR / "sources" / "SO-ARM100_README.md").read_bytes()
        return SourceDoc(
            id="src_mock_so101", url=src["url"], path=src["path"], commit_sha=src["commit_sha"], text=raw.decode("utf-8"),
            sha256=sha256_hex(raw), fetched_at=src["fetched_at"], via="airbyte.github", source_api="mock", simulated=True,
        )

    async def list_dir(self, repo_url: str, path: str) -> list[str]:
        return ["so101_new_calib.urdf", "assets"]


def _dig(obj: Any, *keys: str) -> Any:
    """First value found under any of `keys`, searching nested dicts and lists (connector shapes vary)."""
    if hasattr(obj, "model_dump"):
        obj = obj.model_dump()
    if isinstance(obj, dict):
        for k in keys:
            if obj.get(k) not in (None, "", [], {}):
                return obj[k]
        for v in obj.values():
            got = _dig(v, *keys)
            if got is not None:
                return got
    elif isinstance(obj, list):
        for v in obj:
            got = _dig(v, *keys)
            if got is not None:
                return got
    return None


class LiveGitHubSource:
    """`connector` (anything with `async execute(entity, action, params)`) and `transport` (an httpx
    transport) may be injected; tests use fakes and never reach the network."""

    def __init__(self, connector: Any = None, transport: Any = None) -> None:
        self._connector = connector
        self._transport = transport
        self.reads: list[dict[str, Any]] = []
        self.last_error: str | None = None

    # ------------------------------------------------------------------ Airbyte

    def connector(self) -> Any:
        if self._connector is None:
            token = os.getenv("AIRBYTE_GITHUB_TOKEN") or ""
            if not token:
                raise RuntimeError("AIRBYTE_GITHUB_TOKEN is not set")
            if os.getenv("PYTEST_CURRENT_TEST"):
                raise RuntimeError("no live connector under pytest")
            from airbyte_agent_sdk.connectors.github import GithubConnector
            from airbyte_agent_sdk.connectors.github.models import GithubPersonalAccessTokenAuthConfig

            self._connector = GithubConnector(auth_config=GithubPersonalAccessTokenAuthConfig(token=token))
        return self._connector

    async def _execute(self, entity: str, action: str, params: dict[str, Any]) -> Any:
        res = await self.connector().execute(entity, action, params)
        return res.model_dump() if hasattr(res, "model_dump") else res

    def _log(self, entity: str, action: str, params: dict[str, Any], data: bytes, via: str) -> None:
        self.reads.append({"entity": entity, "action": action, "params": params, "bytes": len(data), "sha256": sha256_hex(data), "via": via})

    async def _airbyte_readme(self, owner: str, repo: str, ref: str | None) -> tuple[str, str, bytes]:
        commits = await self._execute("commits", "list", {"owner": owner, "repo": repo, "per_page": 1})
        sha = _dig(commits, "oid", "sha", "commit_sha")
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise RuntimeError("the connector returned no commit SHA")
        self._log("commits", "list", {"owner": owner, "repo": repo, "per_page": 1}, sha.encode(), "airbyte.github")
        last: Exception | None = None
        for path in README_NAMES:
            params = {"owner": owner, "repo": repo, "path": path, "ref": sha}
            try:
                res = await self._execute("file_content", "get", params)
            except Exception as exc:
                last = exc
                continue
            text = _dig(res, "text", "content", "body")
            if isinstance(text, str) and text:
                if _dig(res, "encoding") == "base64":
                    text = base64.b64decode(text).decode("utf-8", "replace")
                data = text.encode("utf-8")
                self._log("file_content", "get", params, data, "airbyte.github")
                return sha, path, data
        raise RuntimeError(f"the connector returned no README ({last})")

    # ------------------------------------------------------------------ httpx fallback

    async def _get(self, url: str) -> Any:
        import httpx

        from app.stores.http import host_of

        if is_never_request(url) or host_of(url) not in GITHUB_HOSTS:
            raise HostNotAllowed(url, reason="GitHub fallback may only reach api.github.com and raw.githubusercontent.com")
        if self._transport is None and os.getenv("PYTEST_CURRENT_TEST"):
            raise RuntimeError("no network under pytest")
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "build-to-cart"}
        async with httpx.AsyncClient(timeout=10, transport=self._transport, follow_redirects=False) as client:
            resp = await client.get(url, headers=headers)
            for _ in range(3):  # a renamed or moved repository redirects; follow only while it stays on the GitHub hosts
                if resp.status_code not in (301, 302, 307, 308) or "location" not in resp.headers:
                    break
                nxt = str(resp.request.url.join(resp.headers["location"]))
                if is_never_request(nxt) or host_of(nxt) not in GITHUB_HOSTS:
                    raise HostNotAllowed(nxt, reason="GitHub redirected off api.github.com / raw.githubusercontent.com")
                resp = await client.get(nxt, headers=headers)
        resp.raise_for_status()
        return resp

    async def _http_readme(self, owner: str, repo: str, ref: str | None) -> tuple[str, str, bytes]:
        import httpx

        q = f"?per_page=1&sha={ref}" if ref else "?per_page=1"
        try:
            commits = (await self._get(f"https://api.github.com/repos/{owner}/{repo}/commits{q}")).json()
        except httpx.HTTPStatusError as exc:  # say what happened in words the person can act on
            code = exc.response.status_code
            if code in (404, 451):
                raise LookupError(f"GitHub has no public repository {owner}/{repo} (HTTP {code}). Check the link, or use a public repository") from exc
            if code in (403, 429):
                raise LookupError(f"GitHub refused the keyless read of {owner}/{repo} (HTTP {code}); the limit is 60 reads an hour without a token. "
                                  "Try again later, or set AIRBYTE_GITHUB_TOKEN") from exc
            raise
        sha = commits[0]["sha"]
        self._log("commits", "list", {"owner": owner, "repo": repo, "per_page": 1}, sha.encode(), "http")
        last: Exception | None = None
        for path in README_NAMES:
            try:
                resp = await self._get(f"https://raw.githubusercontent.com/{owner}/{repo}/{sha}/{path}")
            except Exception as exc:
                last = exc
                continue
            self._log("file_content", "get", {"owner": owner, "repo": repo, "path": path, "ref": sha}, resp.content, "http")
            return sha, path, resp.content
        raise RuntimeError(f"no README found at {owner}/{repo}@{sha[:7]} ({last})")

    # ------------------------------------------------------------------ interface

    async def fetch_readme(self, repo_url: str) -> SourceDoc:
        """Record and replay go through B's cache (PLAN §3.11): replay reads the recording and never the network."""
        from app import cache

        if is_never_request(repo_url):
            raise HostNotAllowed(repo_url, reason="never-request list")
        if cache.mode() not in ("record", "replay"):
            return await self._fetch_readme(repo_url)
        before = len(self.reads)

        async def go() -> dict[str, Any]:
            doc = await self._fetch_readme(repo_url)
            return {"doc": doc.model_dump(mode="json"), "reads": self.reads[before:]}

        value = await cache.cached("airbyte_github.fetch_readme", {"repo_url": repo_url.strip().rstrip("/")}, go)
        if len(self.reads) == before:  # served from the recording: the reads are the recorded ones
            self.reads.extend(value.get("reads") or [])
        return SourceDoc.model_validate(value["doc"])

    async def _fetch_readme(self, repo_url: str) -> SourceDoc:
        from app.runstate import now_iso

        if is_never_request(repo_url):
            raise HostNotAllowed(repo_url, reason="never-request list")
        parsed = parse_repo_url(repo_url)
        if parsed is None:
            raise ValueError("not a GitHub repository URL")
        owner, repo, ref = parsed
        via = "airbyte.github"
        try:
            sha, path, data = await self._airbyte_readme(owner, repo, ref)
        except Exception as exc:  # P3 fallback: raw fetch, and say so
            self.last_error = f"{type(exc).__name__}: {str(exc)[:160]}"
            via = "http"
            try:
                sha, path, data = await self._http_readme(owner, repo, ref)
            except Exception as http_exc:
                # Pipeline mode only (B2C_GITHUB_BUNDLED_FALLBACK=1): when the keyless read fails (60 reads an hour, or
                # offline), the one repository we ship a copy of is served from that copy, labelled as the mock
                # connector's bundled README (simulated). Any other repository still fails with the real reason.
                if os.getenv("B2C_GITHUB_BUNDLED_FALLBACK") == "1":
                    try:
                        doc = await MockGitHubSource().fetch_readme(repo_url)
                    except LookupError:
                        raise http_exc from None
                    self.last_error = f"keyless read failed ({str(http_exc)[:120]}); served the bundled copy"
                    return doc
                raise
        text = data.decode("utf-8", "replace")
        return SourceDoc(id=f"src_{sha[:10]}", url=f"https://github.com/{owner}/{repo}", path=path, commit_sha=sha, text=text,
                         sha256=sha256_hex(text), fetched_at=now_iso(), via=via, source_api="airbyte_github" if via == "airbyte.github" else "github_raw")

    async def list_dir(self, repo_url: str, path: str) -> list[str]:
        parsed = parse_repo_url(repo_url)
        if parsed is None:
            return []
        owner, repo, ref = parsed
        params = {"owner": owner, "repo": repo, "path": path, **({"ref": ref} if ref else {})}
        try:
            res = await self._execute("directory_content", "list", params)
            entries = _dig(res, "entries", "data", "items") or []
            names = [e.get("name") for e in entries if isinstance(e, dict) and e.get("name")]
            self._log("directory_content", "list", params, "\n".join(names).encode(), "airbyte.github")
            return names
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {str(exc)[:160]}"
        try:
            q = f"?ref={ref}" if ref else ""
            items = (await self._get(f"https://api.github.com/repos/{owner}/{repo}/contents/{path}{q}")).json()
            names = [i["name"] for i in items if isinstance(i, dict) and "name" in i]
            self._log("directory_content", "list", params, "\n".join(names).encode(), "http")
            return names
        except Exception:
            return []
