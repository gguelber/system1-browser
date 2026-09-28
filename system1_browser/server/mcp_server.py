"""
FastMCP Server for system1-browser.
Exposes low-latency System-1 browser automation tools as a permanent daemon.
Pre-warms Julia-1 in memory and maintains persistent CDP connection.
"""
import sys
import os
import asyncio
import logging
from typing import Dict, Any, Optional, Literal

from fastmcp import FastMCP
from system1_browser.cdp.client import CDPClient
from system1_browser.core.runner import SubgoalRunner

logger = logging.getLogger("system1_browser.mcp")

AGENT_INSTRUCTIONS = """
system1-browser is a low-latency System-1 browser automation co-processor for frontier agentic LLMs (GPT Astra, Claude 5.5 Opus, Gemini 3.8 Pro).
Operational Guidelines:
1. Do not dump massive raw HTML or request continuous full-page screenshots for repetitive web tasks.
2. For multi-step forms, searches, or repetitive clicking workflows, call `system1_browser_subgoal(goal, max_steps)` to resolve steps locally at sub-10ms latency.
3. Call `system1_browser_inspect()` to receive a compact, pruned Set-of-Marks list of actionable candidates [0..N] (~250 tokens).
4. For atomic actions, use `system1_browser_click(element_id)` or `system1_browser_type(element_id, text)`.
5. If `system1_browser_subgoal` returns ESCALATED, resolve the single ambiguous decision from the diagnostic rationale, then re-dispatch.
"""

mcp = FastMCP("system1-browser-coprocessor", instructions=AGENT_INSTRUCTIONS)

# Persistent daemon singletons
_cdp_client: Optional[CDPClient] = None
_runner: Optional[SubgoalRunner] = None

def get_shared_cdp() -> CDPClient:
    global _cdp_client
    if _cdp_client is None:
        _cdp_client = CDPClient()
    return _cdp_client

def get_shared_runner(backend: str = "julia") -> SubgoalRunner:
    global _runner
    if _runner is None:
        cdp = get_shared_cdp()
        _runner = SubgoalRunner(cdp_client=cdp, backend=backend)
        # Pre-warm Julia model in memory
        _runner._ensure_engine()
    return _runner

@mcp.tool()
async def system1_browser_subgoal(
    goal: str,
    max_steps: int = 8,
    backend: Literal["julia", "eikos", "auto"] = "julia"
) -> Dict[str, Any]:
    """
    Executa uma sub-meta autônoma no navegador ativo usando o modelo de Sistema 1 pre-aquecido na GPU.
    Resolve seletores, cliques e preenchimentos localmente sem gastar tokens de nuvem.
    """
    runner = get_shared_runner(backend=backend)
    result = await runner.run(goal=goal, max_steps=max_steps)
    return result.model_dump()

@mcp.tool()
async def system1_browser_inspect() -> Dict[str, Any]:
    """
    Inspeciona a aba ativa do Chrome e retorna uma representação ultracompacta
    do DOM (~250 tokens) com apenas os elementos interativos numerados [0..N].
    Mantém a conexão persistente ativa.
    """
    cdp = get_shared_cdp()
    await cdp.ensure_connected()
    await cdp.attach_active_page()
    state = await cdp.extract_pruned_state()
    return state.model_dump()

@mcp.tool()
async def system1_browser_click(element_id: int) -> Dict[str, Any]:
    """
    Clica instantaneamente em um elemento da página identificado pelo ID [0..N] via CDP persistente.
    """
    cdp = get_shared_cdp()
    await cdp.ensure_connected()
    await cdp.attach_active_page()
    state = await cdp.extract_pruned_state()
    elem = next((e for e in state.elements if e.id == element_id), None)
    if not elem:
        return {"success": False, "error": f"Elemento ID {element_id} não encontrado."}
    await cdp.click_element(elem)
    return {"success": True, "clicked": elem.model_dump()}

@mcp.tool()
async def system1_browser_type(element_id: int, text: str) -> Dict[str, Any]:
    """
    Digita um texto instantaneamente em um input da página identificado pelo ID [0..N] via CDP persistente.
    """
    cdp = get_shared_cdp()
    await cdp.ensure_connected()
    await cdp.attach_active_page()
    state = await cdp.extract_pruned_state()
    elem = next((e for e in state.elements if e.id == element_id), None)
    if not elem:
        return {"success": False, "error": f"Elemento ID {element_id} não encontrado."}
    await cdp.type_element(elem, text)
    return {"success": True, "typed": text, "element": elem.model_dump()}

def main():
    # Pre-warm engine on daemon startup
    logger.info("⚡ Pre-warming Julia-1 model into memory...")
    try:
        get_shared_runner()
    except Exception as e:
        logger.warning(f"Could not pre-warm on startup: {e}")
    mcp.run()

if __name__ == "__main__":
    main()
