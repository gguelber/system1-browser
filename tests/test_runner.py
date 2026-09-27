"""
Test SubgoalRunner with simulated PageState for system1-browser.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock
from system1_browser.core.types import InteractiveElement, PageState
from system1_browser.core.runner import SubgoalRunner

def test_runner_mock_flow():
    mock_cdp = MagicMock()
    mock_cdp.connect = AsyncMock()
    mock_cdp.close = AsyncMock()
    mock_cdp.attach_active_page = AsyncMock()
    mock_cdp.click_element = AsyncMock()
    mock_cdp.type_element = AsyncMock()
    
    initial_elements = [
        InteractiveElement(
            id=0, tag="input", type="text", label="Pesquisar por objeto",
            name="termo", dom_id="search-input", disabled=False, x=150, y=100, selector="#search-input"
        ),
        InteractiveElement(
            id=1, tag="button", type="submit", label="Buscar",
            name="", dom_id="btn-submit", disabled=False, x=350, y=100, selector="#btn-submit"
        )
    ]
    
    initial_state = PageState(
        url="https://cnetmobile.estaleiro.serpro.gov.br",
        title="Consulta Pública - Compras.gov.br",
        alerts=[],
        elementCount=2,
        elements=initial_elements
    )
    
    final_state = PageState(
        url="https://cnetmobile.estaleiro.serpro.gov.br/resultados",
        title="Resultados da Busca de Dispensas",
        alerts=[],
        elementCount=10,
        elements=[]
    )
    
    mock_cdp.extract_pruned_state = AsyncMock(side_effect=[initial_state, final_state, final_state, final_state])

    runner = SubgoalRunner(cdp_client=mock_cdp, backend="mock")
    
    def mock_eval(evidence, criterion, question_type="noul", criteria_or_options=None):
        if question_type == "choice":
            return {"decision": "[1]", "confidence": 0.95, "distribution": {"[1]": 0.95}}
        elif question_type == "noul":
            if "erro" in criterion:
                return {"decision": "false", "confidence": 0.99, "distribution": {"false": 0.99}}
            if "completamente alcançada" in criterion:
                return {"decision": "true", "confidence": 0.92, "distribution": {"true": 0.92}}
        return {"decision": "false", "confidence": 0.5, "distribution": {}}
        
    runner._evaluate_decision = mock_eval

    result = asyncio.run(runner.run(goal="Clique no botão Buscar para ver as dispensas"))
    
    assert result.status == "COMPLETED"
    assert result.steps_count == 1
    assert len(result.history) == 1
    assert result.history[0].action.action_type == "click"
    assert result.history[0].action.target_id == 1
    print("Mock SubgoalRunner flow passed perfectly for system1-browser!")

if __name__ == "__main__":
    test_runner_mock_flow()
