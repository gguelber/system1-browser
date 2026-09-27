"""
Example: Autonomous browser navigation with system1-browser (0 cloud tokens).
"""
import sys
import os

# Allow running directly from source checkout
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from system1_browser import BrowserCoprocessor

def main():
    print("🚀 Initializing system1-browser Coprocessor (Backend: Julia-1, 540MB VRAM)...")
    # Backend can be 'julia' (default ultralight), 'eikos' (high capacity), or 'auto'
    coprocessor = BrowserCoprocessor(backend="julia")

    goal = "Preencha o campo de busca com 'licitações de tecnologia' e clique no botão de pesquisar"
    print(f"🎯 Target Sub-Goal: {goal}")
    print("⚡ Executing local System-1 micro-actions on active Chrome tab...")

    result = coprocessor.execute_subgoal(goal=goal, max_steps=6)

    print("\n📊 Execution Summary:")
    print(f"Status:       {result.status}")
    print(f"Steps taken:  {result.steps_count}")
    print(f"Total time:   {result.total_time_ms:.1f} ms")
    print(f"Diagnosis:    {result.message}")
    
    print("\n📜 Micro-Action History:")
    for step in result.history:
        print(f"  Step {step.step_num}: {step.action.action_type.upper()} on target [{step.action.target_id}] ({step.duration_ms:.1f}ms)")
        print(f"    Confidence: {step.action.confidence:.2%}")
        print(f"    Url:        {step.url_after}")

if __name__ == "__main__":
    main()
