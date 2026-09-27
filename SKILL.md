---
name: system1-browser
description: "Ultra-fast (<10ms) System-1 browser automation co-processor via Chrome DevTools Protocol (CDP). Use for filling forms, clicking, inspecting interactive elements, and multi-step web workflows with 0 cloud tokens."
---

# system1-browser Agent Skill

This skill equips frontier agentic models (**GPT Astra**, **Claude 5.5 Opus**, **Gemini 3.8 Pro**) with low-latency local browser execution reflexes.

## Operational Rules for Agents

1. **Do Not Dump Full HTML / Screenshots:**
   - Raw HTML trees consume 40k+ tokens and induce context truncation.
   - Use `system1_browser_inspect` to retrieve a clean, pruned Set-of-Marks list of actionable candidates `[0..N]` in ~250 tokens.

2. **Delegate Repetitive Sequences to Subgoals:**
   - For wizards, forms, search fields, and multi-step navigation, invoke `system1_browser_subgoal(goal, max_steps)`.
   - The on-device System-1 model resolves element selection and CDP dispatch in milliseconds.

3. **Atomic Actions:**
   - `system1_browser_click(element_id)`: Instant CDP click dispatch on target `[0..N]`.
   - `system1_browser_type(element_id, text)`: Native DOM event text typing without breaking client-side React/Vue state.

4. **Escalation Protocol:**
   - If `status == "ESCALATED"`, the local engine encountered ambiguous options, a CAPTCHA, or validation failure.
   - Read the diagnostic rationale, reason through the single ambiguous decision, and resume delegation.
