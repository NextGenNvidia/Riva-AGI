import os
import glob
import re

agents_dir = os.path.join(os.path.dirname(__file__), '..', 'orchestration', 'agents')
orchestrator_dir = os.path.join(os.path.dirname(__file__), '..', 'orchestration', 'orchestrator')

files = glob.glob(os.path.join(agents_dir, '*.py')) + glob.glob(os.path.join(orchestrator_dir, '*.py'))

agent_files = [f for f in files if any(f.endswith(name) for name in [
    'coder.py', 'researcher.py', 'writer.py', 'reasoner.py', 'designer.py',
    'qa_tester.py', 'data_analyst.py', 'devops.py', 'security_auditor.py', 'seo_specialist.py',
    'intent_classifier.py', 'planner.py', 'executor.py', 'reviewer.py', 'dummy_system_agent.py'
])]

for filepath in agent_files:
    with open(filepath, 'r') as f:
        content = f.read()

    # Extract the actual string for agent_id
    match = re.search(r'@registry\.register\(\s*["\']([^"\']+)["\']', content)
    if not match:
        match = re.search(r'name=["\']([^"\']+)["\']', content)
    
    actual_agent_id = match.group(1) if match else "unknown"

    # Replace the broken f-string
    content = content.replace('f"You are the {agent_id} agent. Your job is to fulfill the user\'s request expertly."',
                              f'f"You are the {actual_agent_id} agent. Your job is to fulfill the user\'s request expertly."')
    
    with open(filepath, 'w') as f:
        f.write(content)
    print(f"Fixed {os.path.basename(filepath)}")
