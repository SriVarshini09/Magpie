"""The agent tool loop: Claude Sonnet 5.5 through the SDK Tool Runner (PLAN §3.1, §3.5, §3.6). Owner: A.

Written against the `claude-api` skill:
- `client.beta.messages.tool_runner` with `beta_async_tool` tools, every tool `strict` (schemas carry
  `additionalProperties: false` and `required`);
- `tool_choice` is left at `auto` (forcing a tool is a 400 on this model); the prompt names the order;
- no prefill, no sampling parameters; thinking stays adaptive, depth via `output_config.effort`;
- `stop_reason` is checked on every message; a refusal ends the model loop;
- server-side refusal fallbacks: beta `server-side-fallback-2026-07-01`, `fallbacks="default"`.

Stage order is enforced by the harness (`tools.call_tool`), not by the model. Whatever the model leaves
undone, `scripted.run_scripted` finishes in the fixed order, so a run always ends staged or in error.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any

from app import registry, runstate
from app.agent import ports, prompts, scripted, tools
from app.config import get_settings

__all__ = ["run_agent", "build_tools", "MAX_ITERATIONS"]

MAX_ITERATIONS = 60
FALLBACK_BETA = "server-side-fallback-2026-07-01"
EXPOSED = [n for n in tools.TOOL_SPECS]  # no checkout or payment tool exists to expose


def build_tools(run_id: str) -> list[Any]:
    """One strict Tool Runner tool per agent tool, each calling the single wrapper."""
    from anthropic import beta_async_tool

    out = []
    for name in EXPOSED:
        spec = tools.TOOL_SPECS[name]

        def make(tool_name: str) -> Callable[..., Any]:
            async def fn(**kwargs: Any) -> str:
                return json.dumps(await tools.call_tool(run_id, tool_name, kwargs), ensure_ascii=False, default=str)

            fn.__name__ = tool_name
            return fn

        out.append(beta_async_tool(make(name), name=name, description=spec["description"], input_schema=spec["input_schema"], strict=True))
    return out


def _default_runner(run: Any) -> Any:
    llm = registry.get("anthropic")
    if not hasattr(llm, "client"):
        raise NotImplementedError("the mock LLM has no tool loop")
    client = llm.client()  # raises NotImplementedError when there are no credentials
    s = get_settings()
    intake = run.intake.model_dump(mode="json") | {"answers": run.answers}
    return client.beta.messages.tool_runner(
        model=s.model_fast, max_tokens=16000, max_iterations=MAX_ITERATIONS,
        system=[{"type": "text", "text": prompts.SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": prompts.context_block(run.mandate.model_dump(mode="json"), intake)}],
        tools=build_tools(run.run_id), messages=[{"role": "user", "content": prompts.KICKOFF}],
        output_config={"effort": "medium"}, betas=[FALLBACK_BETA], fallbacks="default")


async def _model_loop(run: Any, runner: Any) -> str | None:
    """Drive the Tool Runner until the cart is staged. Returns a reason when the model stopped early."""
    t0 = time.perf_counter()
    async for message in runner:
        run.stats.claude_calls += 1
        usage = getattr(message, "usage", None)
        ports.track("track_ai_message", run.run_id, getattr(message, "model", ""), getattr(usage, "input_tokens", 0) or 0,
                    getattr(usage, "output_tokens", 0) or 0, int((time.perf_counter() - t0) * 1000))
        t0 = time.perf_counter()
        stop = getattr(message, "stop_reason", None)
        if stop == "refusal":
            details = getattr(message, "stop_details", None)
            return f"Claude declined to continue (category: {getattr(details, 'category', None) or 'unspecified'})"
        for block in getattr(message, "content", []) or []:
            text = getattr(block, "text", None) if getattr(block, "type", None) == "text" else None
            if text and text.strip():
                run.emit("agent.message", text.strip()[:280], "info", provider="claude", data={"role": "agent"})
        if stop == "max_tokens":
            return "Claude's answer was cut off"
        if "staged" in run.stages:
            return None  # stop and wait for the Approve button
    return None


async def run_agent(run_id: str, *, runner_factory: Callable[[Any], Any] | None = None) -> None:
    """Tool loop; stage order enforced by the harness; stops at stage_cart."""
    run = runstate.get(run_id)
    try:
        from app.agent import memory as agent_memory

        await agent_memory.recall_preferences(run)  # what the user chose before, on the timeline; never raises
        why: str | None = None
        try:
            runner = (runner_factory or _default_runner)(run)
        except NotImplementedError:
            runner = None  # no Claude key: the scripted run is the whole run
        except Exception as exc:
            runner, why = None, f"Claude loop not started: {type(exc).__name__}"
        if runner is not None:
            try:
                why = await _model_loop(run, runner)
            except Exception as exc:
                why = f"Claude loop stopped: {type(exc).__name__}"
        if why:
            run.emit("agent.message", f"{why}. Continuing with the fixed tool order.", "warn")
        if "staged" not in run.stages and run.status != "error":
            await scripted.run_scripted(run_id)
    except Exception as exc:  # never leave a run "running" forever
        run.status = "error"
        run.emit("error", f"The run stopped: {type(exc).__name__}", "error", detail=str(exc)[:200])
    finally:
        runstate.save_run(run)
        ports.track("end_session", run.run_id)  # the agent's work is done: the analytics session closes ("Complete")
