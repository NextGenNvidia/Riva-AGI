import inspect
import logging
from typing import Callable, Any, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class ToolDefinition:
    name: str
    func: Callable
    description: str
    category: str = 'general'
    parameters_schema: Dict[str, Any] = field(default_factory=dict)

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}

    def register(self, func: Optional[Callable] = None, *, name: Optional[str] = None, description: Optional[str] = None, category: str = 'general'):
        """
        Decorator to register a function as an agent tool.
        Can be used as @tool or @tool(name='...', category='...').
        """
        def decorator(f: Callable):
            tool_name = name or f.__name__
            tool_desc = description or inspect.getdoc(f) or 'No description provided.'
            
            sig = inspect.signature(f)
            params = {}
            for param_name, param in sig.parameters.items():
                params[param_name] = {
                    'type': str(param.annotation if param.annotation != inspect.Parameter.empty else 'Any'),
                    'default': param.default if param.default != inspect.Parameter.empty else None,
                    'required': param.default == inspect.Parameter.empty
                }
            
            tool_def = ToolDefinition(
                name=tool_name,
                func=f,
                description=tool_desc,
                category=category,
                parameters_schema=params
            )
            self._tools[tool_name] = tool_def
            logger.debug(f'Registered tool: {tool_name} [{category}]')
            return f

        if func is not None:
            return decorator(func)
        return decorator

    def get_tool(self, name: str) -> Optional[Callable]:
        """Returns the callable function for the registered tool name."""
        defn = self._tools.get(name)
        return defn.func if defn else None

    def get_tool_definition(self, name: str) -> Optional[ToolDefinition]:
        """Returns the ToolDefinition metadata object for a registered tool."""
        return self._tools.get(name)

    def get_all_tools(self) -> Dict[str, ToolDefinition]:
        """Returns a copy of all registered tool definitions."""
        return dict(self._tools)

    def get_tools_by_names(self, names: List[str]) -> List[Callable]:
        """Returns a list of callable functions for the provided tool names."""
        funcs = []
        for n in names:
            if n in self._tools:
                funcs.append(self._tools[n].func)
            else:
                logger.warning(f'Tool not found in registry: {n}')
        return funcs

    def execute(self, tool_name: str, **kwargs) -> Any:
        """Executes a registered tool by name with keyword arguments."""
        tool_func = self.get_tool(tool_name)
        if not tool_func:
            raise ValueError(f'Tool {tool_name} not registered.')
        logger.info(f'Executing tool [{tool_name}] with args: {kwargs}')
        return tool_func(**kwargs)

# Global Tool Registry instance
tool_registry = ToolRegistry()
tool = tool_registry.register
