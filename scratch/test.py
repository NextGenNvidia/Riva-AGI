import sys
import os

# Ensure the root directory is in the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from orchestration.orchestrator.main import run_orchestrator

print("\n" + "="*60)
print("  TESTING KEYWORD ROUTER (NO LLM)")
print("="*60)

tasks = [
    "Write a python script to sort an array.",
    "Can you help me improve the SEO ranking of my website with better keywords?",
    "Deploy the docker container to the AWS infrastructure.",
    "Plan the architecture and break down the steps for the new system.",
    "Write some unit tests and verify the code quality."
]

for task in tasks:
    print(f"\n[USER]: {task}")
    result = run_orchestrator(task)
    
    agent = result.get("agent", "Unknown")
    intent = result.get("intent", "Unknown")
    
    # In hierarchical mode, final outputs are in completed_steps or feedback
    completed = result.get("completed_steps", [])
    if completed:
        content = completed[-1].get("result", "No result")
    else:
        # If it failed or was just a fallback
        resp = result.get("response_payload")
        content = resp.content if resp else "Empty Workflow Result"
    
    print(f" -> Routed to Agent : {agent.upper()}")
    print(f" -> Target Output   : {content[:200]}...")
    print("-" * 60)
