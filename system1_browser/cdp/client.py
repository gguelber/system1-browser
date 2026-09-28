"""
Chrome DevTools Protocol (CDP) WebSocket client for system1-browser.
Provides direct, low-latency (<5ms) connection to active Chrome sessions.
"""
import os
import json
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import websockets
from system1_browser.core.types import PageState, InteractiveElement

logger = logging.getLogger("system1_browser.cdp")

class CDPClient:
    """
    Direct asynchronous CDP client connecting over WebSockets.
    Automatically detects active Chrome session port and DevTools security token.
    """
    def __init__(self, host: str = "127.0.0.1", port: Optional[int] = None):
        self.host = host
        self.port = port
        self.ws_url: Optional[str] = None
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self._msg_id = 0
        self._pending_futures: Dict[int, asyncio.Future] = {}
        self._receive_task: Optional[asyncio.Task] = None
        self._current_session_id: Optional[str] = None

        # Load JS pruner
        js_path = Path(__file__).parent / "pruner_script.js"
        self._pruner_js = js_path.read_text(encoding="utf-8")

    def _discover_chrome_endpoint(self) -> str:
        """
        Discovers the active Chrome DevTools endpoint from DevToolsActivePort.
        """
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        candidates = [
            Path(local_app_data) / "Google" / "Chrome" / "User Data" / "DevToolsActivePort",
            Path(os.environ.get("USERPROFILE", "")) / ".config" / "google-chrome" / "DevToolsActivePort",
        ]
        
        for cand in candidates:
            if cand.exists():
                try:
                    lines = [l.strip() for l in cand.read_text(encoding="utf-8").splitlines() if l.strip()]
                    if len(lines) >= 2:
                        port = lines[0]
                        token = lines[1]
                        return f"ws://{self.host}:{port}{token}"
                except Exception as e:
                    logger.warning(f"Error reading DevToolsActivePort from {cand}: {e}")

        # Fallback to direct port 9222
        port = self.port or 9222
        return f"ws://{self.host}:{port}/devtools/browser"

    async def connect(self):
        """Establishes a persistent WebSocket connection to Chrome."""
        if self.ws is not None and not self.ws.closed:
            return
        self.ws_url = self._discover_chrome_endpoint()
        logger.info(f"Connecting to Chrome CDP at: {self.ws_url}")
        logger.info("⏳ Aguardando aprovação no Chrome (clique em 'Permitir' no navegador)...")
        self.ws = await websockets.connect(
            self.ws_url,
            max_size=20 * 1024 * 1024,
            open_timeout=None,  # Aguarda indefinidamente a aprovação no Chrome
            ping_interval=20.0,
            ping_timeout=20.0
        )
        self._receive_task = asyncio.create_task(self._listen_loop())
        logger.info("✅ Conexão CDP persistente autorizada e estabelecida com sucesso.")

    async def ensure_connected(self):
        """Ensures the CDP connection is open and active without recreating it unnecessarily."""
        if self.ws is None or self.ws.closed:
            await self.connect()

    async def close(self):
        """Closes the CDP connection cleanly."""
        if self._receive_task:
            self._receive_task.cancel()
        if self.ws:
            await self.ws.close()
            self.ws = None

    async def _listen_loop(self):
        """Background loop handling incoming CDP messages."""
        try:
            async for raw_msg in self.ws:
                msg = json.loads(raw_msg)
                msg_id = msg.get("id")
                if msg_id and msg_id in self._pending_futures:
                    fut = self._pending_futures.pop(msg_id)
                    if not fut.done():
                        fut.set_result(msg)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"CDP listener error: {e}")

    async def send_command(self, method: str, params: Optional[Dict[str, Any]] = None, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Sends a CDP command and awaits its typed response."""
        self._msg_id += 1
        call_id = self._msg_id
        
        payload: Dict[str, Any] = {
            "id": call_id,
            "method": method,
            "params": params or {}
        }
        
        active_session = session_id or self._current_session_id
        if active_session and not method.startswith("Target."):
            payload["sessionId"] = active_session

        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        self._pending_futures[call_id] = fut
        
        await self.ws.send(json.dumps(payload))
        resp = await fut
        
        if "error" in resp:
            raise RuntimeError(f"CDP Error in {method}: {resp['error']}")
        return resp.get("result", {})

    async def get_pages(self) -> List[Dict[str, Any]]:
        """Returns all open page targets."""
        res = await self.send_command("Target.getTargets")
        targets = res.get("targetInfos", [])
        return [t for t in targets if t.get("type") == "page"]

    async def attach_page(self, target_id: str) -> str:
        """Attaches to a specific page target and stores the session ID."""
        if self._current_session_id:
            try:
                await self.send_command("Target.detachFromTarget", {"sessionId": self._current_session_id})
            except Exception:
                pass
        res = await self.send_command("Target.attachToTarget", {"targetId": target_id, "flatten": True})
        self._current_session_id = res.get("sessionId")
        return self._current_session_id

    async def attach_active_page(self, url_filter: Optional[str] = None) -> Dict[str, Any]:
        """Finds and attaches to the target page, optionally filtered by url/title keyword."""
        pages = await self.get_pages()
        if not pages:
            raise RuntimeError("No open browser pages found in Chrome.")
        
        target = None
        if url_filter:
            kw = url_filter.lower()
            target = next((p for p in reversed(pages) if kw in p.get("url", "").lower() or kw in p.get("title", "").lower()), None)
        
        if not target:
            # Prioritize relevant procurement portals if currently open
            target = next((p for p in reversed(pages) if "pncp.gov.br" in p.get("url", "") or "comprasnet" in p.get("url", "") or "estaleiro.serpro.gov.br" in p.get("url", "")), None)

        if not target:
            # Default to the most recently opened/active page
            target = pages[-1]
            
        await self.attach_page(target["targetId"])
        return target

    async def evaluate_script(self, expression: str) -> Any:
        """Evaluates JavaScript expression in the attached page and returns the parsed value."""
        res = await self.send_command("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True
        })
        result = res.get("result", {})
        return result.get("value")

    async def extract_pruned_state(self) -> PageState:
        """Executes the JS Pruner and returns a compact PageState (~300 tokens)."""
        raw_state = await self.evaluate_script(self._pruner_js)
        if not raw_state:
            raise RuntimeError("Failed to extract DOM state from page.")
        return PageState(**raw_state)

    async def click_element(self, element: InteractiveElement):
        """
        Dispatches a high-precision click using mouse simulation or fallback native click.
        """
        js_click = f"""
        (() => {{
          const el = document.querySelector({json.dumps(element.selector)}) || document.elementFromPoint({element.x}, {element.y});
          if (el) {{
            el.scrollIntoView({{ behavior: 'instant', block: 'center' }});
            el.focus();
            el.click();
            return true;
          }}
          return false;
        }})()
        """
        await self.evaluate_script(js_click)

    async def type_element(self, element: InteractiveElement, text: str):
        """
        Types text into an element with native value dispatching (supporting React/Vue SPAs).
        """
        js_type = f"""
        (() => {{
          const el = document.querySelector({json.dumps(element.selector)}) || document.elementFromPoint({element.x}, {element.y});
          if (el) {{
            el.scrollIntoView({{ behavior: 'instant', block: 'center' }});
            el.focus();
            // React / Angular / Ember native setter
            const prototype = el.tagName === 'TEXTAREA' 
              ? window.HTMLTextAreaElement.prototype 
              : window.HTMLInputElement.prototype;
            const descriptor = Object.getOwnPropertyDescriptor(prototype, 'value');
            if (descriptor && descriptor.set) {{
              descriptor.set.call(el, {json.dumps(text)});
            }} else {{
              el.value = {json.dumps(text)};
            }}
            el.dispatchEvent(new Event('input', {{ bubbles: true }}));
            el.dispatchEvent(new Event('change', {{ bubbles: true }}));
            return true;
          }}
          return false;
        }})()
        """
        await self.evaluate_script(js_type)
