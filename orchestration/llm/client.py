"""
Unified Multi-Provider LLM Client — orchestration/llm/client.py
================================================================
Provides a unified interface across multiple LLM providers:
OpenAI, Anthropic Claude, Google Gemini, Groq, Local/Ollama, and Mock fallback.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from orchestration.llm.mock_engine import mock_llm_engine

load_dotenv()
logger = logging.getLogger(__name__)


class LLMClient:
    """
    Unified LLM Client with multi-provider fallback and ReAct prompt handling.
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.2,
    ):
        self.provider = provider or os.getenv("DEFAULT_LLM_PROVIDER", "auto").lower()
        self.model = model or os.getenv("DEFAULT_MODEL_NAME", "gpt-4o-mini")
        self.temperature = float(os.getenv("LLM_TEMPERATURE", str(temperature)))

    def generate(
        self,
        messages: List[Dict[str, str]],
        available_tools: Optional[List[str]] = None,
        iteration: int = 0,
    ) -> str:
        """
        Generate completion across configured provider or fallback.
        """
        available_tools = available_tools or []

        # Auto provider selection
        selected_provider = self._resolve_provider()

        providers_to_try = [selected_provider]
        for p in ["groq", "mistral", "gemini", "anthropic", "openai"]:
            if p not in providers_to_try and self._has_keys(p):
                providers_to_try.append(p)

        last_error = None
        for provider in providers_to_try:
            try:
                if provider == "groq":
                    return self._call_groq(messages, available_tools)
                elif provider == "mistral":
                    return self._call_mistral(messages, available_tools)
                elif provider == "openai":
                    return self._call_openai(messages, available_tools)
                elif provider == "gemini":
                    return self._call_gemini(messages, available_tools)
                elif provider == "anthropic":
                    return self._call_anthropic(messages, available_tools)
                elif provider == "ollama":
                    return self._call_ollama(messages)
                else:
                    return self._call_mock(messages, available_tools, iteration)
            except Exception as e:
                logger.warning("Provider '%s' failed with error: %s. Switching to next provider.", provider, e)
                last_error = e
                continue

        # If all available providers fail, return an observation so the ReAct loop can try to simplify.
        return f"Action: none\nAction Input: {{}}\n\nObservation: [API ERROR] All LLM providers failed. Last error: {str(last_error)}. Please retry with shorter output."

    def _resolve_provider(self) -> str:
        """Determine the active provider based on environment keys."""
        if self.provider != "auto":
            return self.provider

        if os.getenv("GROQ_API_KEY"):
            return "groq"
        if os.getenv("MISTRAL_API_KEY"):
            return "mistral"
        if os.getenv("OPENAI_API_KEY"):
            return "openai"
        if os.getenv("GEMINI_API_KEY"):
            return "gemini"
        if os.getenv("ANTHROPIC_API_KEY"):
            return "anthropic"
        return "mock"
        
    def _has_keys(self, provider: str) -> bool:
        if provider == "groq" and os.getenv("GROQ_API_KEY"): return True
        if provider == "mistral" and os.getenv("MISTRAL_API_KEY"): return True
        if provider == "openai" and os.getenv("OPENAI_API_KEY"): return True
        if provider == "gemini" and os.getenv("GEMINI_API_KEY"): return True
        if provider == "anthropic" and os.getenv("ANTHROPIC_API_KEY"): return True
        return False

    def _call_openai(self, messages: List[Dict[str, str]], tool_names: Optional[List[str]] = None) -> str:
        import openai
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"), max_retries=0)
        kwargs = {
            "model": self.model if "gpt" in self.model else "gpt-4o-mini",
            "messages": messages,
            "temperature": self.temperature,
        }
        if tool_names:
            from orchestration.tools.registry import tool_registry
            schemas = tool_registry.get_openai_schemas(tool_names)
            if schemas:
                kwargs["tools"] = schemas
                kwargs["tool_choice"] = "auto"

        resp = client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message
        if msg.tool_calls:
            first_tool = msg.tool_calls[0].function
            return f"Action: {first_tool.name}\nAction Input: {first_tool.arguments}"
        return msg.content or ""

    def _call_groq(self, messages: List[Dict[str, str]], tool_names: Optional[List[str]] = None) -> str:
        import openai
        client = openai.OpenAI(
            api_key=os.getenv("GROQ_API_KEY"),
            base_url="https://api.groq.com/openai/v1",
            max_retries=0
        )
        groq_model = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
        kwargs = {
            "model": groq_model,
            "messages": messages,
            "temperature": self.temperature,
        }
        if tool_names:
            from orchestration.tools.registry import tool_registry
            schemas = tool_registry.get_openai_schemas(tool_names)
            if schemas:
                kwargs["tools"] = schemas
                kwargs["tool_choice"] = "auto"

        resp = client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message
        if msg.tool_calls:
            first_tool = msg.tool_calls[0].function
            return f"Action: {first_tool.name}\nAction Input: {first_tool.arguments}"
        return msg.content or ""

    def _call_mistral(self, messages: List[Dict[str, str]], tool_names: Optional[List[str]] = None) -> str:
        import openai
        import os
        client = openai.OpenAI(
            api_key=os.getenv("MISTRAL_API_KEY"),
            base_url="https://api.mistral.ai/v1",
            max_retries=0
        )
        kwargs = {
            "model": "mistral-large-latest",
            "messages": messages,
            "temperature": self.temperature,
        }
        if tool_names:
            from orchestration.tools.registry import tool_registry
            schemas = tool_registry.get_openai_schemas(tool_names)
            if schemas:
                kwargs["tools"] = schemas
                kwargs["tool_choice"] = "auto"

        resp = client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message
        if msg.tool_calls:
            first_tool = msg.tool_calls[0].function
            return f"Action: {first_tool.name}\nAction Input: {first_tool.arguments}"
        return msg.content or ""

    def _call_gemini(self, messages: List[Dict[str, str]], tool_names: Optional[List[str]] = None) -> str:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            import google.generativeai as genai
            
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        kwargs = {}
        if tool_names:
            from orchestration.tools.registry import tool_registry
            schemas = tool_registry.get_openai_schemas(tool_names)
            if schemas:
                # Google's SDK expects 'type' values (e.g., 'object', 'string') to be UPPERCASE
                def to_gemini_schema(node):
                    if isinstance(node, dict):
                        new_node = {}
                        for k, v in node.items():
                            if k == "type" and isinstance(v, str):
                                new_node[k] = v.upper()
                            else:
                                new_node[k] = to_gemini_schema(v)
                        return new_node
                    elif isinstance(node, list):
                        return [to_gemini_schema(i) for i in node]
                    return node

                import copy
                gemini_tools = []
                for s in schemas:
                    f = copy.deepcopy(s["function"])
                    if "parameters" in f:
                        f["parameters"] = to_gemini_schema(f["parameters"])
                    gemini_tools.append(f)
                kwargs["tools"] = gemini_tools

        full_prompt = "\n\n".join(f"[{m.get('role', 'user').upper()}]:\n{m.get('content', '')}" for m in messages)
        
        try:
            resp = model.generate_content(full_prompt, **kwargs)
            
            # Safely check for function call
            if resp.candidates and resp.candidates[0].content.parts:
                part = resp.candidates[0].content.parts[0]
                if hasattr(part, "function_call") and part.function_call:
                    fc = part.function_call
                    # Protobuf map to dict safely
                    import json
                    args_dict = {}
                    for k, v in fc.args.items():
                        args_dict[k] = v
                    return f"Action: {fc.name}\nAction Input: {json.dumps(args_dict)}"
                    
            return resp.text or ""
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Gemini native API failed: %s", str(e))
            raise e

    def _call_anthropic(self, messages: List[Dict[str, str]], tool_names: Optional[List[str]] = None) -> str:
        import anthropic
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        
        system_msg = ""
        user_msgs = []
        for m in messages:
            if m.get("role") == "system":
                system_msg += m.get("content", "") + "\n"
            else:
                user_msgs.append(m)

        kwargs = {
            "model": "claude-3-5-sonnet-20241022",
            "system": system_msg.strip() or "You are Riva-AGI assistant.",
            "messages": user_msgs or [{"role": "user", "content": "Hello"}],
            "max_tokens": 2048,
            "temperature": self.temperature,
        }
        
        if tool_names:
            from orchestration.tools.registry import tool_registry
            schemas = tool_registry.get_openai_schemas(tool_names)
            if schemas:
                anthropic_tools = []
                for schema in schemas:
                    f = schema["function"]
                    anthropic_tools.append({
                        "name": f["name"],
                        "description": f["description"],
                        "input_schema": f["parameters"]
                    })
                kwargs["tools"] = anthropic_tools

        resp = client.messages.create(**kwargs)
        
        # Check for tool_use blocks
        if resp.content:
            for block in resp.content:
                if block.type == "tool_use":
                    import json
                    return f"Action: {block.name}\nAction Input: {json.dumps(block.input)}"
                    
        return resp.content[0].text if resp.content else ""

    def _call_ollama(self, messages: List[Dict[str, str]]) -> str:
        import openai
        base_url = os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:11434/v1")
        model = os.getenv("LOCAL_LLM_MODEL", "llama3.2")
        client = openai.OpenAI(base_url=base_url, api_key="ollama")
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=self.temperature,
        )
        return resp.choices[0].message.content or ""

    def _call_mock(self, messages: List[Dict[str, str]], tools: List[str], iteration: int) -> str:
        return mock_llm_engine.generate_step(messages, tools, iteration)


# Global default LLM client
llm_client = LLMClient()
