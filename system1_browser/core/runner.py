"""
Autonomous SubgoalRunner for system1-browser.
Implements the System 1 micro-action loop with pluggable backends:
- 'julia': SupersonicLabs Julia-1 (Default: ultralight ~540MB VRAM)
- 'eikos': Eikos-4B-INT4 (~2.9GB VRAM for high-capacity reasoning)
- 'auto': Attempts Julia-1, falls back to Eikos-4B, then heuristic
- 'mock': Unit testing mode without GPU
"""
import os
import sys
import time
import re
import logging
from typing import Optional, Dict, Any, List, Literal

from system1_browser.core.types import (
    PageState, InteractiveElement, ActionDecision, StepRecord, SubgoalResult
)
from system1_browser.core.prompt_builder import (
    format_elements_as_candidates,
    build_target_selection_criterion,
    build_post_action_verification,
    build_goal_completion_verification
)
from system1_browser.cdp.client import CDPClient

logger = logging.getLogger("system1_browser.runner")

class SubgoalRunner:
    """
    Executes an autonomous sub-goal on the active browser page using pluggable System-1 models.
    """
    def __init__(
        self,
        cdp_client: Optional[CDPClient] = None,
        backend: Literal["julia", "eikos", "auto", "mock"] = "julia",
        model_dir: Optional[str] = None
    ):
        self.cdp = cdp_client or CDPClient()
        self.backend = backend
        self.model_dir = model_dir
        
        # Engine instances
        self._engine_type: Optional[str] = None
        self._julia_engine = None
        self._eikos_adapter = None
        self._eikos_options_of = None

    def _ensure_engine(self):
        """Lazy-loads the selected System-1 decision backend."""
        if self._engine_type is not None:
            return

        # 1. Julia-1 Backend (Default ultralight 540MB VRAM)
        if self.backend in ("julia", "auto"):
            julia_path = self.model_dir or os.path.abspath("models/Julia-1")
            if os.path.exists(julia_path):
                if julia_path not in sys.path:
                    sys.path.insert(0, julia_path)
                try:
                    import torch
                    from julia.router.engine import FastEngine
                    device = "cuda" if torch.cuda.is_available() else "cpu"
                    self._julia_engine = FastEngine(checkpoint=julia_path, device=device)
                    self._engine_type = "julia"
                    logger.info(f"Julia-1 FastEngine loaded successfully on {device} (VRAM: ~540MB).")
                    return
                except Exception as e:
                    logger.warning(f"Could not load Julia-1: {e}")
                    if self.backend == "julia":
                        pass

        # 2. Eikos-4B Backend (High-capacity 2.9GB VRAM)
        if self.backend in ("eikos", "auto"):
            eikos_path = self.model_dir or os.path.abspath("models/Eikos-4B-INT4")
            if os.path.exists(eikos_path):
                if eikos_path not in sys.path:
                    sys.path.insert(0, eikos_path)
                try:
                    from letter_adapter import LetterAdapter
                    from decision_core import options_of
                    calib_path = os.path.join(eikos_path, "calib.json")
                    self._eikos_adapter = LetterAdapter(
                        model_path=eikos_path,
                        device="cuda",
                        calib=calib_path if os.path.exists(calib_path) else None
                    )
                    self._eikos_adapter.load()
                    self._eikos_options_of = options_of
                    self._engine_type = "eikos"
                    logger.info("Eikos-4B-INT4 model loaded successfully (VRAM: ~2.9GB).")
                    return
                except Exception as e:
                    logger.warning(f"Could not load Eikos-4B: {e}")

        # Fallback heuristic mode
        self._engine_type = "fallback"
        logger.info("Running in fallback/heuristic decision mode.")

    def _evaluate_decision(
        self,
        evidence: str,
        criterion: str,
        question_type: str = "noul",
        criteria_or_options: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Invokes the active System-1 model in 1 forward pass."""
        self._ensure_engine()
        
        # Dispatch to Julia-1
        if self._engine_type == "julia" and self._julia_engine is not None:
            try:
                if question_type == "choice":
                    questions = {
                        "action": {
                            "type": "choice",
                            "instructions": criterion,
                            "criteria": criteria_or_options or {}
                        }
                    }
                    res = self._julia_engine.predict(state=evidence, questions=questions)
                    ans = res.get("answers", {}).get("action", {})
                    return {
                        "decision": ans.get("choice", "[none]"),
                        "confidence": float(ans.get("max_probability", 0.5)),
                        "distribution": ans.get("probabilities", {})
                    }
                elif question_type == "noul":
                    questions = {
                        "verify": {
                            "type": "noul",
                            "instructions": criterion
                        }
                    }
                    res = self._julia_engine.predict(state=evidence, questions=questions)
                    ans = res.get("answers", {}).get("verify", {})
                    score = float(ans.get("noul", 0.5))
                    decision = "true" if score >= 0.5 else "false"
                    conf = score if decision == "true" else (1.0 - score)
                    return {
                        "decision": decision,
                        "confidence": conf,
                        "distribution": {"true": score, "false": 1.0 - score}
                    }
            except Exception as e:
                logger.warning(f"Julia-1 evaluation failed, falling back: {e}")

        # Dispatch to Eikos-4B
        if self._engine_type == "eikos" and self._eikos_adapter is not None:
            q_dict = {"type": question_type, "instructions": criterion}
            if criteria_or_options:
                q_dict["criteria"] = criteria_or_options
            opts = self._eikos_options_of(q_dict)
            probs, n_tokens = self._eikos_adapter.dist(evidence, q_dict, opts)
            top_choice = max(probs, key=probs.get)
            return {
                "decision": top_choice,
                "confidence": probs[top_choice],
                "distribution": probs
            }
        
        # Heuristic fallback
        return {"decision": "false", "confidence": 0.5, "distribution": {}}

    def _extract_intent_payload(self, goal: str) -> Optional[str]:
        """Extracts text payload from goal string, e.g. Preencha '123' -> 123."""
        matches = re.findall(r"['\"](.*?)['\"]", goal)
        if matches:
            return matches[0]
        with_match = re.search(r"\bcom\s+([A-Za-z0-9\.\-\_\@]+)", goal, re.IGNORECASE)
        if with_match:
            return with_match.group(1)
        return None

    async def run(self, goal: str, max_steps: int = 8) -> SubgoalResult:
        """
        Executes the autonomous sub-goal loop until completion or escalation.
        """
        start_time = time.time()
        history: List[StepRecord] = []
        
        await self.cdp.connect()
        try:
            await self.cdp.attach_active_page()
            
            for step_idx in range(1, max_steps + 1):
                step_start = time.time()
                
                # 1. Perception: Extract pruned DOM state (<3ms)
                state = await self.cdp.extract_pruned_state()
                
                # Wait automatically if page is actively loading or has busy spinners
                wait_attempts = 0
                import asyncio
                while getattr(state, "isLoading", False) and wait_attempts < 10:
                    logger.info(f"Página em carregamento ({state.loadingReason}). Aguardando 300ms...")
                    await asyncio.sleep(0.3)
                    state = await self.cdp.extract_pruned_state()
                    wait_attempts += 1
                
                title_before = state.title
                
                if not state.elements:
                    return SubgoalResult(
                        goal=goal,
                        status="ESCALATED",
                        steps_count=step_idx,
                        message="Nenhum elemento interativo acionável foi encontrado na página.",
                        history=history,
                        total_time_ms=(time.time() - start_time) * 1000
                    )

                # 2. Decision: Select target element via System-1 `choice`
                evidence, options = format_elements_as_candidates(state.elements)
                criterion = build_target_selection_criterion(goal)
                
                choice_res = self._evaluate_decision(
                    evidence=evidence,
                    criterion=criterion,
                    question_type="choice",
                    criteria_or_options=options
                )
                
                selected_opt = choice_res["decision"]
                confidence = choice_res["confidence"]
                
                # Escalate if ambiguous
                if selected_opt == "[none]" or confidence < 0.60:
                    return SubgoalResult(
                        goal=goal,
                        status="ESCALATED",
                        steps_count=step_idx,
                        message=f"Decisão ambígua pelo Sistema 1 (Opção: {selected_opt}, Confiança: {confidence:.2f}). Escalonando para planejamento de alto nível.",
                        history=history,
                        total_time_ms=(time.time() - start_time) * 1000
                    )

                # Parse element ID from [X]
                id_match = re.search(r"\[(\d+)\]", selected_opt)
                if not id_match:
                    return SubgoalResult(
                        goal=goal,
                        status="ESCALATED",
                        steps_count=step_idx,
                        message=f"Formato de seleção inválido retornado: {selected_opt}",
                        history=history,
                        total_time_ms=(time.time() - start_time) * 1000
                    )
                    
                target_id = int(id_match.group(1))
                target_elem = next((el for el in state.elements if el.id == target_id), None)
                if not target_elem:
                    return SubgoalResult(
                        goal=goal,
                        status="ESCALATED",
                        steps_count=step_idx,
                        message=f"Elemento ID {target_id} não encontrado na lista atual.",
                        history=history,
                        total_time_ms=(time.time() - start_time) * 1000
                    )

                # 3. Action Dispatch: Type or Click
                is_input_field = target_elem.tag in ["input", "textarea"] and target_elem.type not in ["submit", "button", "checkbox", "radio"]
                text_to_type = self._extract_intent_payload(goal) if is_input_field else None
                
                action_type = "type" if (is_input_field and text_to_type) else "click"
                
                # Check for action loops (anti-stall)
                recent_same = [h for h in history[-2:] if h.action.target_id == target_id and h.action.action_type == action_type]
                if len(recent_same) == 2:
                    return SubgoalResult(
                        goal=goal,
                        status="ESCALATED",
                        steps_count=step_idx,
                        message=f"Loop detectado: ação '{action_type}' repetida 3 vezes no elemento [{target_id}] sem progresso. Escalonando para Sistema 2.",
                        history=history,
                        total_time_ms=(time.time() - start_time) * 1000
                    )
                
                if action_type == "type" and text_to_type:
                    await self.cdp.type_element(target_elem, text_to_type)
                    action_desc = f"Digitou '{text_to_type}' no campo [{target_elem.id}] ({target_elem.label or target_elem.name})"
                else:
                    await self.cdp.click_element(target_elem)
                    action_desc = f"Clicou no elemento [{target_elem.id}] <{target_elem.tag}> ({target_elem.label or target_elem.dom_id})"

                # 4. Settle DOM: Brief settling period (100ms)
                import asyncio
                await asyncio.sleep(0.1)
                
                # 5. Post-Action Verification
                new_state = await self.cdp.extract_pruned_state()
                step_duration = (time.time() - step_start) * 1000
                
                step_record = StepRecord(
                    step_num=step_idx,
                    action=ActionDecision(
                        action_type=action_type,
                        target_id=target_id,
                        target_element=target_elem,
                        input_text=text_to_type,
                        confidence=confidence,
                        rationale=f"Selecionado via System-1 ({self._engine_type}) com confiança {confidence:.2f}"
                    ),
                    page_title_before=title_before,
                    page_title_after=new_state.title,
                    url_after=new_state.url,
                    alerts_after=new_state.alerts,
                    duration_ms=step_duration
                )
                history.append(step_record)

                # Check for errors/alerts via `noul`
                err_ev, err_crit = build_post_action_verification(goal, action_desc, title_before, new_state)
                err_res = self._evaluate_decision(
                    evidence=err_ev,
                    criterion=err_crit,
                    question_type="noul"
                )
                if err_res["decision"] == "true" and err_res["confidence"] >= 0.80:
                    return SubgoalResult(
                        goal=goal,
                        status="ESCALATED",
                        steps_count=step_idx,
                        message=f"Alerta ou erro impeditivo detectado após ação: {action_desc}. Alertas: {new_state.alerts}",
                        history=history,
                        total_time_ms=(time.time() - start_time) * 1000
                    )

                # Check if sub-goal is completed
                hist_summary = "; ".join([s.action.action_type for s in history])
                comp_ev, comp_crit = build_goal_completion_verification(goal, hist_summary, new_state)
                comp_res = self._evaluate_decision(
                    evidence=comp_ev,
                    criterion=comp_crit,
                    question_type="noul"
                )
                if comp_res["decision"] == "true" and comp_res["confidence"] >= 0.80:
                    return SubgoalResult(
                        goal=goal,
                        status="COMPLETED",
                        steps_count=step_idx,
                        message=f"Sub-meta concluída com sucesso em {step_idx} micro-ações mecânicas.",
                        history=history,
                        total_time_ms=(time.time() - start_time) * 1000
                    )

            # Reached max steps
            return SubgoalResult(
                goal=goal,
                status="MAX_STEPS_REACHED",
                steps_count=max_steps,
                message=f"Limite de {max_steps} passos atingido sem confirmação definitiva de conclusão.",
                history=history,
                total_time_ms=(time.time() - start_time) * 1000
            )

        finally:
            await self.cdp.close()
