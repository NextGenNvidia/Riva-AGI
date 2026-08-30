import json
import logging
import subprocess
from typing import Dict, Any, List, Optional
from orchestration.tools.registry import tool_registry

logger = logging.getLogger(__name__)

class MCPAdapter:
    """Adapter to bridge external Model Context Protocol (MCP) servers with RIVA."""
    
    def __init__(self, command: str, args: List[str] = None, env: Dict[str, str] = None):
        self.command = command
        self.args = args or []
        self.env = env
        self._process: Optional[subprocess.Popen] = None
        self._connected = False

    def start(self):
        """Starts the MCP server subprocess."""
        try:
            full_cmd = [self.command] + self.args
            self._process = subprocess.Popen(
                full_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=self.env
            )
            self._connected = True
            logger.info(f'MCP Server started: {self.command}')
        except Exception as e:
            logger.error(f'Failed to start MCP server {self.command}: {e}')
            self._connected = False

    def send_rpc(self, method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Sends a JSON-RPC 2.0 message to the MCP server."""
        if not self._connected or not self._process:
            raise RuntimeError('MCP server not connected.')
            
        req = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': method,
            'params': params or {}
        }
        
        msg = json.dumps(req) + '\n'
        self._process.stdin.write(msg)
        self._process.stdin.flush()
        
        resp_line = self._process.stdout.readline()
        if not resp_line:
            raise RuntimeError('Empty response from MCP server.')
            
        return json.loads(resp_line)

    def close(self):
        if self._process:
            self._process.terminate()
            self._connected = False
