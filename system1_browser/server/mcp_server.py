"""
FastMCP Server for system1-browser.
Exposes low-latency System-1 browser automation tools as a permanent daemon.
Pre-warms Julia-1 in memory and maintains persistent CDP connection.
"""
import sys
import os
from pathlib import Path

# Ensure repo root and models are in sys.path
repo_root = str(Path(__file__).resolve().parent.parent.parent)
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

models_dir = os.path.abspath(os.path.join(repo_root, "..", "charming-newton", "models"))
for m in ["Julia-1", "Eikos-4B-INT4"]:
    p = os.path.join(models_dir, m)
    if os.path.exists(p) and p not in sys.path:
        sys.path.insert(0, p)

import asyncio
import logging
from typing import Dict, Any, Optional, Literal

from fastmcp import FastMCP
from system1_browser.cdp.client import CDPClient
from system1_browser.core.runner import SubgoalRunner

logging.basicConfig(stream=sys.stderr, level=logging.INFO)
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
    backend: Literal["julia", "eikos", "auto"] = "julia",
    url_filter: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executa uma sub-meta autônoma no navegador ativo usando o modelo de Sistema 1 pre-aquecido na GPU.
    Resolve seletores, cliques e preenchimentos localmente sem gastar tokens de nuvem.
    """
    runner = get_shared_runner(backend=backend)
    result = await runner.run(goal=goal, max_steps=max_steps, url_filter=url_filter)
    return result.model_dump()

@mcp.tool()
async def system1_browser_inspect(url_filter: Optional[str] = None) -> Dict[str, Any]:
    """
    Inspeciona a aba ativa do Chrome e retorna uma representação ultracompacta
    do DOM (~250 tokens) com apenas os elementos interativos numerados [0..N].
    Mantém a conexão persistente ativa.
    """
    cdp = get_shared_cdp()
    await cdp.ensure_connected()
    await cdp.attach_active_page(url_filter=url_filter)
    state = await cdp.extract_pruned_state()
    return state.model_dump()

@mcp.tool()
async def system1_browser_click(element_id: int, url_filter: Optional[str] = None) -> Dict[str, Any]:
    """
    Clica instantaneamente em um elemento da página identificado pelo ID [0..N] via CDP persistente.
    """
    cdp = get_shared_cdp()
    await cdp.ensure_connected()
    await cdp.attach_active_page(url_filter=url_filter)
    state = await cdp.extract_pruned_state()
    elem = next((e for e in state.elements if e.id == element_id), None)
    if not elem:
        return {"success": False, "error": f"Elemento ID {element_id} não encontrado."}
    await cdp.click_element(elem)
    return {"success": True, "clicked": elem.model_dump()}

@mcp.tool()
async def system1_browser_type(element_id: int, text: str, url_filter: Optional[str] = None) -> Dict[str, Any]:
    """
    Digita um texto instantaneamente em um input da página identificado pelo ID [0..N] via CDP persistente.
    """
    cdp = get_shared_cdp()
    await cdp.ensure_connected()
    await cdp.attach_active_page(url_filter=url_filter)
    state = await cdp.extract_pruned_state()
    elem = next((e for e in state.elements if e.id == element_id), None)
    if not elem:
        return {"success": False, "error": f"Elemento ID {element_id} não encontrado."}
    await cdp.type_element(elem, text)
    return {"success": True, "typed": text, "element": elem.model_dump()}

if __name__ == "__main__":
    mcp.run()
