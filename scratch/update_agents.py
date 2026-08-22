import os
import glob
import re

# We want to replace the `content = f"... (Key: {masked_key})..."` line with a call to LLM
# Also add the import: from orchestration.orchestrator.llm import call_gemini
# Also define the system_instruction specific to the agent.

agents_dir = os.path.join(os.path.dirname(__file__), '..', 'orchestration', 'agents')
orchestrator_dir = os.path.join(os.path.dirname(__file__), '..', 'orchestration', 'orchestrator')

files = glob.glob(os.path.join(agents_dir, '*.py')) + glob.glob(os.path.join(orchestrator_dir, '*.py'))

# We only want the 14 agent files
agent_files = [f for f in files if any(f.endswith(name) for name in [
    'coder.py', 'researcher.py', 'writer.py', 'reasoner.py', 'designer.py',
    'qa_tester.py', 'data_analyst.py', 'devops.py', 'security_auditor.py', 'seo_specialist.py',
    'intent_classifier.py', 'planner.py', 'executor.py', 'reviewer.py', 'dummy_system_agent.py'
])]

import_str = "from orchestration.orchestrator.llm import call_gemini\n"

for filepath in agent_files:
    with open(filepath, 'r') as f:
        content = f.read()

    # Skip if already imported
    if "import call_gemini" in content:
        continue

    # 1. Add the import below the key_manager import
    content = content.replace("from orchestration.orchestrator.config import key_manager", 
                              "from orchestration.orchestrator.config import key_manager\nfrom orchestration.orchestrator.llm import call_gemini")
    
    # 2. Extract agent_id from the @registry.register line
    match = re.search(r'@registry\.register\(\s*["\']([^"\']+)["\']', content)
    if not match:
        match = re.search(r'name=["\']([^"\']+)["\']', content)
    
    agent_id = match.group(1) if match else "unknown"

    # 3. Replace the masked key and content generation logic
    # Find the block starting with masked_key and ending before execution_time or return
    
    # Original block looks like:
    # masked_key = f"{my_key[:8]}...{my_key[-4:]}" if my_key else "No Key Found"
    # content = f"XYZ Agent (Key: {masked_key}) did: {task_data.text_content}"
    # OR 
    # content = f"XYZ Agent (Key: {masked_key}) did: {task_data.text_content}"
    
    replacement = f"""
    # System instruction tailored for this agent
    sys_prompt = f"You are the {{agent_id}} agent. Your job is to fulfill the user's request expertly."
    
    # Call the GenAI LLM
    content = call_gemini(
        prompt=task_data.text_content, 
        api_key=my_key, 
        system_instruction=sys_prompt, 
        agent_id="{agent_id}"
    )
    """

    # We will regex replace the masked_key line and the content = f"..." line
    pattern = re.compile(r'masked_key\s*=\s*f"[^"]*".*?\n\s*content\s*=\s*f"[^"]*task_data\.text_content[^"]*"', re.DOTALL)
    
    if pattern.search(content):
        new_content = pattern.sub(replacement.strip(), content)
        with open(filepath, 'w') as f:
            f.write(new_content)
        print(f"Updated {os.path.basename(filepath)}")
    else:
        # For dummy_system_agent, the content string might be different
        pattern2 = re.compile(r'masked_key\s*=\s*f"[^"]*".*?\n\s*# Process\s*\n\s*content\s*=\s*f"[^"]*task_data\.text_content[^"]*"', re.DOTALL)
        if pattern2.search(content):
            new_content = pattern2.sub(replacement.strip(), content)
            with open(filepath, 'w') as f:
                f.write(new_content)
            print(f"Updated {os.path.basename(filepath)}")
        else:
            print(f"Could not match pattern in {os.path.basename(filepath)}")
