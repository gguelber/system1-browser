import sys
import time
import asyncio
from system1_browser.cdp.client import CDPClient

if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

async def run_search(termo: str = "software"):
    start = time.time()
    cdp = CDPClient()
    await cdp.connect()
    
    target = await cdp.attach_active_page(url_filter="pncp")
    print(f"⚡ [System 1] Conectado via CDP na aba: {target.get('title')}")
    
    # 1. Percepção podada
    t0 = time.time()
    state = await cdp.extract_pruned_state()
    t_dom = (time.time() - t0) * 1000
    print(f"👁️ Percepção do DOM: {len(state.elements)} elementos interativos podados em {t_dom:.1f}ms")
    
    # Localizar input e botão
    input_elem = next((e for e in state.elements if e.dom_id == "keyword"), None)
    search_btn = next((e for e in state.elements if "buscar" in (e.label or "").lower() or (e.tag == "button" and e.x > 800)), None)
    
    if not input_elem:
        print("❌ Campo 'keyword' não encontrado.")
        await cdp.close()
        return

    # 2. Digitação mecânica de Sistema 1
    t1 = time.time()
    await cdp.type_element(input_elem, termo)
    t_type = (time.time() - t1) * 1000
    print(f"⌨️ Digitação instantânea de '{termo}' no campo [{input_elem.id}] em {t_type:.1f}ms")
    
    # 3. Clique mecânico no botão Buscar
    if search_btn:
        t2 = time.time()
        await cdp.click_element(search_btn)
        t_click = (time.time() - t2) * 1000
        print(f"🖱️ Clique no botão [{search_btn.id}] em {t_click:.1f}ms")
    
    # Aguardar 1.5s para os resultados do Angular
    await asyncio.sleep(1.5)
    
    # 4. Extração de resultados
    cards_js = """
    (() => {
      const cards = Array.from(document.querySelectorAll('a[href*="/editais/"]'));
      return cards.map(a => ({
        text: a.innerText.trim(),
        href: a.href
      })).slice(0, 10);
    })()
    """
    results = await cdp.evaluate_script(cards_js)
    total_time = (time.time() - start) * 1000
    print(f"\n✅ Concluído em {total_time:.1f}ms! Total de editais/dispensas na tela: {len(results or [])}")
    
    for idx, r in enumerate(results or [], 1):
        lines = [l.strip() for l in r['text'].splitlines() if l.strip()]
        header = lines[0] if lines else "Edital"
        orgao = next((l for l in lines if "Órgão:" in l), "")
        objeto = next((l for l in lines if "Objeto:" in l), "")
        print(f"\n[{idx}] {header} | {orgao}")
        print(f"    {objeto[:120]}...")
        print(f"    Link: {r['href']}")

    await cdp.close()

if __name__ == "__main__":
    asyncio.run(run_search("software"))
