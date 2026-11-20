"""Service registry: picks the mock or the live implementation of every external service.

SHARED FILE, owned by the coordinator (OWNERSHIP.md). To add a service, ask in your final report.

    DEMO_MODE=mock                      every service is its Mock class (fixtures, no network, no keys)
    DEMO_MODE=live | record | replay    every service is its Live class
                                        (record and replay are handled by app/cache.py around the live call)
    IMPL_<SERVICE>=mock | live          per-service override, e.g. IMPL_STRIPE=mock, IMPL_SERPAPI=live

Service modules are imported lazily, so a missing or broken SDK only breaks the service that needs it.
Every Mock class labels what it returns: source_api == "mock", simulated is True.
"""

from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from typing import Any

from app.config import ConfigError, get_settings


@dataclass(frozen=True)
class ServiceSpec:
    name: str
    module: str
    mock_cls: str
    live_cls: str
    owner: str  # A | B | C | D
    plan: str  # PLAN section
    kind: str  # integration | store | checkout


_SPECS = [
    ServiceSpec("anthropic", "app.integrations.anthropic_client", "MockLLM", "LiveLLM", "A", "§3.5, §3.17", "integration"),
    ServiceSpec("airbyte_github", "app.integrations.airbyte_github", "MockGitHubSource", "LiveGitHubSource", "A", "§3.15", "integration"),
    ServiceSpec("singlestore", "app.integrations.s2", "MockKnowledgeStore", "LiveKnowledgeStore", "D", "§3.14", "integration"),
    ServiceSpec("sie", "app.integrations.sie", "MockSIE", "LiveSIE", "D", "§3.15, §3.20", "integration"),
    ServiceSpec("cognee", "app.integrations.cognee_mem", "MockMemory", "LiveMemory", "D", "§3.15", "integration"),
    ServiceSpec("amplitude", "app.integrations.amplitude", "MockAnalytics", "LiveAnalytics", "D", "§3.15", "integration"),
    ServiceSpec("statsig", "app.integrations.statsig_gate", "MockGates", "LiveGates", "D", "§3.15", "integration"),
    ServiceSpec("keenable", "app.integrations.keenable", "MockKeenable", "LiveKeenable", "B", "§3.18", "integration"),
    ServiceSpec("exa_airbyte", "app.integrations.airbyte_exa", "MockExa", "LiveExa", "B", "§3.15, §3.18", "integration"),
    ServiceSpec("github_search", "app.integrations.github_search", "MockGitHubSearch", "LiveGitHubSearch", "B", "§3.18", "integration"),
    ServiceSpec("stripe", "app.checkout.stripe_test", "MockStripeTest", "LiveStripeTest", "B", "§12.3, §12.4", "checkout"),
    ServiceSpec("shopify_ucp", "app.stores.shopify_ucp", "MockShopifyUCP", "LiveShopifyUCP", "B", "§3.16, App. A.1", "store"),
    ServiceSpec("serpapi", "app.stores.serpapi", "MockSerpApi", "LiveSerpApi", "B", "§3.16, §3.11", "store"),
    ServiceSpec("adafruit", "app.stores.adafruit", "MockAdafruit", "LiveAdafruit", "B", "§3.16, App. A.4", "store"),
    ServiceSpec("magento", "app.stores.magento", "MockMagento", "LiveMagento", "B", "§3.16, App. A.4", "store"),
    ServiceSpec("digikey", "app.stores.digikey", "MockDigiKey", "LiveDigiKey", "B", "§3.16, App. A.4", "store"),
    ServiceSpec("cartlinks", "app.stores.cartlinks", "MockCartLinks", "LiveCartLinks", "B", "§3.16, App. A.3", "store"),
]
SERVICES: dict[str, ServiceSpec] = {s.name: s for s in _SPECS}

_instances: dict[tuple[str, str], Any] = {}


def impl_mode(name: str) -> str:
    """Return "mock" or "live" for one service, after DEMO_MODE and the IMPL_<SERVICE> override."""
    if name not in SERVICES:
        raise KeyError(f"unknown service {name!r}; known: {sorted(SERVICES)}")
    override = (os.getenv(f"IMPL_{name.upper()}") or "").strip().lower()
    if override:
        if override not in ("mock", "live"):
            raise ConfigError(f"IMPL_{name.upper()} must be mock or live, got {override!r}")
        return override
    return "mock" if get_settings().is_mock else "live"


def get(name: str) -> Any:
    """Return the implementation of a service (one instance per service and mode)."""
    mode = impl_mode(name)
    key = (name, mode)
    if key not in _instances:
        spec = SERVICES[name]
        module = importlib.import_module(spec.module)
        _instances[key] = getattr(module, spec.mock_cls if mode == "mock" else spec.live_cls)()
    return _instances[key]


def modes() -> dict[str, str]:
    return {name: impl_mode(name) for name in SERVICES}


def any_mock() -> bool:
    return get_settings().is_mock or "mock" in modes().values()


def reset() -> None:
    _instances.clear()
