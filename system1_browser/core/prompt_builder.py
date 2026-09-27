"""
Prompt and representation builder for Eikos-4B System 1 decisions.
Converts compact DOM elements and browser state into typed decision schemas.
"""
from typing import List, Tuple, Dict
from system1_browser.core.types import InteractiveElement, PageState

def format_elements_as_candidates(elements: List[InteractiveElement]) -> Tuple[str, Dict[str, str]]:
    """
    Formats the list of interactive elements into a compact evidence text and semantic options dict for Eikos `choice`.
    """
    lines = []
    options: Dict[str, str] = {}
    
    for el in elements:
        opt_key = f"[{el.id}]"
        
        type_str = f"[{el.type}]" if el.type else ""
        desc = f"<{el.tag}{type_str}>"
        if el.label:
            desc += f" '{el.label}'"
        if el.name:
            desc += f" (name={el.name})"
        if el.dom_id:
            desc += f" (id={el.dom_id})"
        if el.disabled:
            desc += " [DISABLED]"
            
        lines.append(f"{opt_key} {desc}")
        options[opt_key] = desc
        
    options["[none]"] = "Nenhum dos elementos na tela corresponde à ação desejada"
    evidence = "Elementos interativos disponíveis na página atual:\n" + "\n".join(lines)
    return evidence, options

def build_target_selection_criterion(goal: str, sub_intent: str = "") -> str:
    """
    Builds the question criterion for selecting which element index corresponds to the next user action.
    """
    if sub_intent:
        return f"Qual opção corresponde ao elemento interativo mais adequado para a ação: '{sub_intent}' na meta: '{goal}'?"
    return f"Qual opção corresponde ao elemento interativo na tela onde o usuário deve clicar ou preencher para avançar na meta: '{goal}'?"

def build_post_action_verification(
    goal: str,
    action_desc: str,
    page_before_title: str,
    page_after: PageState
) -> Tuple[str, str]:
    """
    Builds evidence and criterion for `noul` verification to detect errors, transitions, and goal completion.
    """
    alerts_text = "; ".join(page_after.alerts) if page_after.alerts else "Nenhum alerta visível"
    evidence = (
        f"Meta em execução: {goal}\n"
        f"Ação mecânica executada: {action_desc}\n"
        f"Título anterior da página: {page_before_title}\n"
        f"Título atual da página: {page_after.title} ({page_after.url})\n"
        f"Alertas/Mensagens na tela: {alerts_text}\n"
    )
    criterion = "Ocorreu algum erro impeditivo, bloqueio de acesso, falha de validação ou CAPTCHA na tela após a ação?"
    return evidence, criterion

def build_goal_completion_verification(
    goal: str,
    history_summary: str,
    current_page: PageState
) -> Tuple[str, str]:
    """
    Verifies if the overall sub-goal is now completed.
    """
    evidence = (
        f"Sub-meta planejada: {goal}\n"
        f"Ações executadas até agora: {history_summary}\n"
        f"Página atual: {current_page.title} ({current_page.url})\n"
        f"Total de elementos interativos: {current_page.elementCount}\n"
    )
    criterion = f"A sub-meta '{goal}' foi completamente alcançada pelo estado final da tela?"
    return evidence, criterion
