import sys
import asyncio
from system1_browser.cdp.client import CDPClient

async def inspect():
    cdp = CDPClient()
    await cdp.connect()
    target = await cdp.attach_active_page(url_filter="pncp")
    print(f"Target anexado: {target.get('title')} ({target.get('url')})")
    
    state = await cdp.extract_pruned_state()
    print(f"Título da Página: {state.title}")
    print(f"Total de elementos interativos: {len(state.elements)}")
    
    for e in state.elements:
        if any(w in (e.label or "").lower() or w in (e.name or "").lower() or w in (e.dom_id or "").lower() for w in ["pesquisar", "buscar", "keyword", "termo", "filtro", "proposta"]):
            print(f"  -> [{e.id}] <{e.tag}> id='{e.dom_id}' label='{e.label}' name='{e.name}'")
            
    await cdp.close()

if __name__ == "__main__":
    asyncio.run(inspect())
