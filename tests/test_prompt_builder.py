"""
Tests for system1-browser prompt builder and data structures.
"""
from system1_browser.core.types import InteractiveElement, PageState
from system1_browser.core.prompt_builder import (
    format_elements_as_candidates,
    build_target_selection_criterion,
    build_post_action_verification,
    build_goal_completion_verification
)

def test_format_elements_as_candidates():
    elements = [
        InteractiveElement(
            id=0, tag="input", type="text", label="CNPJ",
            name="cnpj", dom_id="txt-cnpj", disabled=False, x=100, y=200, selector="#txt-cnpj"
        ),
        InteractiveElement(
            id=1, tag="button", type="submit", label="Consultar",
            name="", dom_id="btn-search", disabled=False, x=300, y=200, selector="#btn-search"
        ),
        InteractiveElement(
            id=2, tag="a", type="", label="Voltar",
            name="", dom_id="", disabled=False, x=50, y=50, selector="a.back"
        )
    ]
    
    evidence, options = format_elements_as_candidates(elements)
    assert "[0]" in options
    assert "[1]" in options
    assert "[2]" in options
    assert "[none]" in options
    assert len(options) == 4
    assert "Consultar" in evidence
    assert "CNPJ" in evidence

def test_verification_prompts():
    page_after = PageState(
        url="https://cnetmobile.estaleiro.serpro.gov.br",
        title="Resultado da Busca",
        alerts=["Nenhum registro encontrado"],
        elementCount=5,
        elements=[]
    )
    
    ev, crit = build_post_action_verification(
        goal="Buscar dispensas",
        action_desc="Clicou no botão Consultar",
        page_before_title="Busca ComprasNet",
        page_after=page_after
    )
    assert "Nenhum registro encontrado" in ev
    assert "erro impeditivo" in crit

    comp_ev, comp_crit = build_goal_completion_verification(
        goal="Buscar dispensas",
        history_summary="Clicou em Consultar",
        current_page=page_after
    )
    assert "Buscar dispensas" in comp_crit
