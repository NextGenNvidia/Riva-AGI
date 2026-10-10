"""
Riva-AGI Interactive Chat CLI & Universal Orchestration Testbed
===============================================================
A unified CLI to interact with the Riva-AGI LangGraph Multi-Agent Orchestrator,
test all autonomous agents, test all registered tools (file, system, web),
and inspect API key rotation, latency, and tool execution traces.
"""

import os
import sys
import time
import uuid
import re
import json
import threading
import argparse
import subprocess
from typing import Optional

# Ensure standard UTF-8 output encoding or fallback safely on Windows consoles
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Ensure root workspace directory is on sys.path
WORKSPACE_ROOT = os.path.abspath(os.path.dirname(__file__))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from dotenv import load_dotenv
load_dotenv()

from orchestration import InputData, InputType, AgentResponse, ResponseStatus
from orchestration.orchestrator.main import create_orchestrator
from orchestration.orchestrator.registry import registry
from orchestration.orchestrator.config import key_manager
from orchestration.tools import tool_registry


def initial_state(user_prompt: str, task_id: str = None, session_id: str = None, source: str = "cli") -> dict:
    """Helper to create initial state for the LangGraph orchestrator."""
    if not task_id:
        task_id = f"task-{uuid.uuid4().hex[:8]}"
    if not session_id:
        session_id = f"session-{uuid.uuid4().hex[:8]}"
    input_data = InputData(
        input_type=InputType.TEXT,
        text_content=user_prompt,
        metadata={"source": source}
    )
    return {
        "task_payload": input_data,
        "agent": "fallback",
        "response_payload": None,
        "task_id": task_id,
        "session_id": session_id,
        "source": source,
        "complexity": "simple",
        "routing_decision": "fallback",
        "plan": [],
        "current_step": 0,
        "completed_steps": [],
        "feedback": "",
        "intent": "unknown",
        "confidence": 0.0,
    }


# Optional Windows SAPI TTS Engine
def speak_text(text: str):
    """Speaks text asynchronously using Windows SAPI Speech Synthesis (TTS)."""
    if not text or not text.strip():
        return
    def _speak():
        try:
            import win32com.client
            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            cleaned = re.sub(r"```[\s\S]*?```", " [code block] ", text)
            cleaned = re.sub(r"`[^`]*`", "", cleaned)
            cleaned = re.sub(r"https?://\S+", "link", cleaned)
            cleaned = re.sub(r"[#*_~>\[\]\(\)\{\}|\\-]", " ", cleaned)
            cleaned = re.sub(r"\s+", " ", cleaned).strip()
            if cleaned:
                speaker.Speak(cleaned[:400])
        except Exception:
            pass
    threading.Thread(target=_speak, daemon=True).start()


def print_banner(voice_active: bool = False):
    print("=" * 68)
    print("         [RIVA-AGI] Universal Orchestration & Tool Testbed")
    print("=" * 68)
    print("  Type any natural language prompt to test agents and tool calling.")
    print("  Diagnostic Commands:")
    print("    'status'       - View configuration status and active Gemini models")
    print("    'agents'       - List all registered agents & capabilities")
    print("    'tools'        - List all registered tools & schemas")
    print("    'tools test'   - Run offline regression tests (no API key needed)")
    print('    tool <name> {"argument": "value"} - Call any registered tool directly')
    print("    'voice'        - Toggle Windows TTS voice readout (ON/OFF)")
    print("    'clear'        - Clear chat history and memory")
    print("    'exit'/'quit'  - Exit CLI")
    print(f"  [Voice TTS: {'ON' if voice_active else 'OFF'}]")
    print("=" * 68)


def show_registered_agents():
    agents = registry.get_all_capabilities()
    print("\n" + "=" * 68)
    print(f"[REGISTERED AGENTS] (Total: {len(agents)})")
    print("=" * 68)
    for name, cap in agents.items():
        tools_str = ", ".join(cap.tools) if cap.tools else "No direct tools"
        print(f"  * {name:<18} [{cap.agent_level}]")
        print(f"    Description: {cap.description}")
        print(f"    Tools      : {tools_str}")
        print("-" * 68)


def show_registered_tools():
    tools = tool_registry.get_all_tools()
    print("\n" + "=" * 68)
    print(f"[REGISTERED TOOLS] (Total: {len(tools)})")
    print("=" * 68)
    for name, tool_def in tools.items():
        desc = tool_def.description if hasattr(tool_def, 'description') else "No description"
        print(f"  * {name}")
        print(f"    Description: {desc}")
        if hasattr(tool_def, 'parameters') and tool_def.parameters:
            props = tool_def.parameters.get("properties", {})
            req = tool_def.parameters.get("required", [])
            print(f"    Parameters : {list(props.keys())} (Required: {req})")
        print("-" * 68)


def check_system_status():
    print("\n" + "=" * 68)
    print("[SYSTEM & API CONFIGURATION STATUS]")
    print("=" * 68)

    global_key = os.getenv("GEMINI_API_KEY")
    masked_global = f"********{global_key[-4:]}" if global_key and len(global_key) >= 4 else "NOT SET"
    print(f"  * Global GEMINI_API_KEY : {masked_global}")

    agents_to_check = [
        ("ORCHESTRATOR", "Orchestrator"),
        ("INTENT_CLASSIFIER", "Intent Classifier"),
        ("CODER", "Coder Agent"),
        ("RESEARCHER", "Researcher Agent"),
        ("WRITER", "Writer Agent"),
        ("REASONER", "Reasoner Agent"),
        ("DESIGNER", "Designer Agent"),
        ("QA_TESTER", "QA Tester Agent"),
        ("DATA_ANALYST", "Data Analyst Agent"),
        ("DEVOPS", "DevOps Agent"),
        ("SECURITY_AUDITOR", "Security Auditor"),
        ("SEO_SPECIALIST", "SEO Specialist"),
        ("PLANNER", "Planner Agent"),
        ("EXECUTOR", "Executor Agent"),
        ("REVIEWER", "Reviewer Agent"),
    ]

    for role_enum, label in agents_to_check:
        key = key_manager.get_api_key_for_role(role_enum)
        if key:
            masked = f"********{key[-4:]}" if len(key) >= 4 else "CONFIGURED"
            print(f"  * {label:<22} Key : {masked}")
        else:
            print(f"  * {label:<22} Key : [MISSING / USING GLOBAL FALLBACK]")

    all_tools = tool_registry.get_all_tools()
    print(f"  * Tools Registered      : {len(all_tools)} tool(s) active in registry")
    print("=" * 68)


def on_progress_tracker(node_name: str, node_update: dict, state: dict, start_time: list, step_timer: list):
    """Tracks and logs step progress in real time."""
    now = time.time()
    dt = now - step_timer[0]
    total_elapsed = now - start_time[0]
    step_timer[0] = now

    icon = {
        "intent": "🧠 [INTENT]",
        "planner": "📋 [PLANNER]",
        "executor": "⚙️  [EXECUTOR]",
        "coder": "💻 [CODER]",
        "researcher": "🔍 [RESEARCHER]",
        "writer": "✍️  [WRITER]",
        "reasoner": "🤔 [REASONER]",
        "designer": "🎨 [DESIGNER]",
        "qa_tester": "🧪 [QA_TESTER]",
        "data_analyst": "📊 [DATA_ANALYST]",
        "devops": "🚀 [DEVOPS]",
        "security_auditor": "🛡️  [SECURITY]",
        "seo_specialist": "📈 [SEO]",
        "reviewer": "👀 [REVIEWER]",
        "fallback": "⚠️  [FALLBACK]"
    }.get(node_name, f"⚡ [{node_name.upper()}]")

    print(f"  --> {icon:<22} executed (+{dt:.2f}s | total: {total_elapsed:.2f}s)")

    if node_name == "intent":
        intent = node_update.get("intent", "unknown")
        agent = node_update.get("routing_decision", "unknown")
        confidence = node_update.get("confidence", 0.0)
        print(f"      Intent: {intent} (Confidence: {confidence:.2f}) -> Route to: [{agent}]")

    elif node_update.get("response_payload"):
        resp: AgentResponse = node_update["response_payload"]
        if resp.tool_calls:
            print(f"      Tools Executed: {len(resp.tool_calls)} call(s)")
            for call in resp.tool_calls:
                call_info = f"'{call.tool_name}'"
                args_summary = json.dumps(call.parameters) if call.parameters else ""
                if len(args_summary) > 60:
                    args_summary = args_summary[:57] + "..."
                print(f"        * Tool: {call_info} | Args: {args_summary}")


def execute_prompt(user_input: str, conversation_history: list, session_id: str = 'cli', return_response=False):
    """Executes the user prompt through the LangGraph orchestrator."""
    print("\n" + "=" * 68)
    print("[LANGGRAPH EXECUTION TIMELINE]")
    print("=" * 68)

    t0 = time.time()
    start_time = [t0]
    step_timer = [t0]

    app = create_orchestrator()
    task_id = f"task-{uuid.uuid4().hex[:8]}"

    # Fast-path for standalone greetings
    if user_input.lower().strip().rstrip(".!?") in {"hello", "hi", "hey", "greetings", "good morning", "good evening", "good afternoon"}:
        effective_prompt = user_input
    elif conversation_history:
        context_lines = []
        for turn in conversation_history[-3:]:
            context_lines.append(f"User: {turn['user']}")
            context_lines.append(f"Assistant: {turn['assistant']}")
        context_block = "\n".join(context_lines)
        effective_prompt = f"Previous conversation context:\n{context_block}\n\nCurrent user request:\n{user_input}"
    else:
        effective_prompt = user_input

    final_agent = "assistant"
    final_payload = None
    all_workflow_tool_calls = []

    current_state = initial_state(effective_prompt, task_id=task_id, session_id=session_id)
    try:
        for step in app.stream(current_state, config={'recursion_limit': 40}):
            for node_name, node_update in step.items():
                if isinstance(node_update, dict):
                    current_state.update(node_update)
                    if node_update.get('response_payload'):
                        resp = node_update['response_payload']
                        final_payload = resp
                        final_agent = resp.agent_id
                        if hasattr(resp, 'tool_calls') and resp.tool_calls:
                            for tc in resp.tool_calls:
                                all_workflow_tool_calls.append((node_name, tc))
                    on_progress_tracker(node_name, node_update, current_state, start_time, step_timer)
    except KeyboardInterrupt:
        print("\n[Execution interrupted by user]")
        return None

    total_duration = time.time() - t0
    print("=" * 68)
    print(f"[FINISHED] in {total_duration:.2f}s | Final Agent: [{final_agent.upper()}]")
    print("=" * 68)

    if all_workflow_tool_calls:
        print("\n" + "=" * 68)
        print(f"[TOOLS CALLED IN THIS WORKFLOW ({len(all_workflow_tool_calls)} total)]")
        print("=" * 68)
        for idx, (agent_name, call) in enumerate(all_workflow_tool_calls, 1):
            args_str = json.dumps(call.parameters, indent=2) if call.parameters else "{}"
            print(f"  {idx}. Agent: [{agent_name.upper()}] -> Tool: [{call.tool_name}] (ID: {call.call_id})")
            print(f"     Arguments: {args_str.replace(chr(10), chr(10) + '     ')}")
            print("-" * 68)

    print("\n[FINAL AGENT OUTPUT]:")
    output_text = ""
    if final_payload and hasattr(final_payload, "content") and final_payload.content:
        output_text = final_payload.content
    elif isinstance(final_payload, dict):
        output_text = final_payload.get("content", str(final_payload))
    elif current_state.get("response_payload") and hasattr(current_state["response_payload"], "content"):
        output_text = current_state["response_payload"].content
    else:
        output_text = "Task completed successfully."

    print("\n" + output_text)
    print("-" * 68)
    return final_payload if return_response else output_text


def run_tools_self_test():
    tests = ['tests/unit/test_file_tools.py', 'tests/unit/test_system_tools.py', 'tests/unit/test_web_tools.py', 'tests/integration/test_orchestrator.py']
    return subprocess.run([sys.executable, '-m', 'pytest', '-v', *tests], cwd=WORKSPACE_ROOT).returncode


def execute_direct_tool(command: str):
    parts = command.strip().split(' ', 1)
    name = parts[0]
    raw = parts[1].strip() if len(parts) > 1 else '{}'
    if raw.startswith('{'):
        arguments = json.loads(raw)
    elif name in {'read_file', 'list_directory', 'execute_command'}:
        parameter = {'read_file': 'file_path', 'list_directory': 'dir_path', 'execute_command': 'command'}[name]
        arguments = {parameter: raw}
    else:
        raise ValueError('Supply tool arguments as a JSON object. Example: tool write_file {"file_path":"a.txt","content":"hello"}')
    if not isinstance(arguments, dict):
        raise ValueError('Arguments must be a JSON object.')
    
    print(f"\n[Direct Tool Execution] -> {name}")
    print(f"Arguments: {json.dumps(arguments, indent=2)}")
    result = tool_registry.execute(name, **arguments)
    print(f"Result:\n{result}")
    return result


def main():
    parser = argparse.ArgumentParser(description='RIVA interactive multi-agent and tool test console')
    parser.add_argument('--self-test', action='store_true', help='Run offline unit and integration tests')
    parser.add_argument('--prompt', help='Run a single prompt and exit')
    args = parser.parse_args()

    if args.self_test:
        return run_tools_self_test()

    if args.prompt:
        response = execute_prompt(args.prompt, [], session_id=uuid.uuid4().hex, return_response=True)
        return 0 if response and response.status == ResponseStatus.SUCCESS else 1

    session_id = uuid.uuid4().hex
    voice_mode = False
    conversation_history = []
    print_banner(voice_active=voice_mode)

    while True:
        try:
            user_input = input("\n> You: ").strip()
            if not user_input:
                continue

            cmd_lower = user_input.lower()
            if cmd_lower in ["exit", "quit", "q"]:
                print("Exiting Riva-AGI. Goodbye!")
                break

            if cmd_lower in ["clear", "reset"]:
                conversation_history.clear()
                print("[*] Conversation history cleared.")
                continue

            if cmd_lower in ["status", "pool"]:
                check_system_status()
                continue

            if cmd_lower in ["agents", "models"]:
                show_registered_agents()
                continue

            if cmd_lower == "tools":
                show_registered_tools()
                continue

            if cmd_lower in ["tools test", "tool test", "test tools"]:
                run_tools_self_test()
                continue

            if cmd_lower in ["voice", "tts"]:
                voice_mode = not voice_mode
                status_str = "ENABLED" if voice_mode else "DISABLED"
                print(f"[Voice TTS: {status_str}]")
                if voice_mode:
                    speak_text("Voice mode activated.")
                continue

            # Direct tool invocation: tool <tool_name> <params...>
            if user_input.startswith("tool "):
                execute_direct_tool(user_input[5:])
                continue

            # Execute via LangGraph Orchestrator
            output_text = execute_prompt(user_input, conversation_history, session_id=session_id)

            if voice_mode and output_text:
                speak_text(output_text)

            if output_text:
                conversation_history.append({
                    "user": user_input,
                    "assistant": output_text[:1200]
                })

        except (KeyboardInterrupt, EOFError):
            print("\nSession interrupted. Goodbye!")
            break
        except Exception as e:
            print(f"\n[!] Execution Error: {e}")


if __name__ == "__main__":
    raise SystemExit(main())
