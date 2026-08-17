"""
MCP (Model Context Protocol) Client for Obsidian Smart Connections.
Communicates with smart-connections-mcp server to perform local semantic search over Obsidian embedding index.
"""

import json
import urllib.request
import urllib.parse
import urllib.error
from typing import Dict, List, Any, Optional


class ObsidianMCPClient:
    """Client for smart-connections-mcp server."""

    def __init__(self, mcp_url: str = "http://127.0.0.1:3000", timeout: float = 0.8):
        self.mcp_url = mcp_url.rstrip('/')
        self.timeout = timeout

    def is_server_online(self) -> bool:
        """Check if the MCP server is reachable."""
        try:
            req = urllib.request.Request(self.mcp_url, method="GET")
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.status in (200, 204, 404)
        except Exception:
            return False

    def search_notes(self, query: str, limit: int = 3) -> Optional[List[Dict[str, Any]]]:
        """
        Query Smart Connections embedding index via MCP server.
        Returns list of matching notes dicts: [{'title': ..., 'path': ..., 'score': ..., 'content': ...}]
        Returns None if server is unreachable or fails.
        """
        if not query or not query.strip():
            return []

        # Strategy 1: MCP JSON-RPC tools/call (smart_search or semantic_search)
        rpc_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "smart_search",
                "arguments": {
                    "query": query.strip(),
                    "limit": limit
                }
            }
        }

        headers = {"Content-Type": "application/json"}
        endpoints = [
            f"{self.mcp_url}/tools/call",
            f"{self.mcp_url}/rpc"
        ]

        for ep in endpoints:
            try:
                data_bytes = json.dumps(rpc_payload).encode("utf-8")
                req = urllib.request.Request(ep, data=data_bytes, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    if resp.status == 200:
                        res_data = json.loads(resp.read().decode("utf-8"))
                        results = self._extract_results_from_rpc(res_data)
                        if results:
                            return results[:limit]
            except Exception:
                continue

        # Strategy 2: Direct REST search endpoint fallback
        try:
            encoded_query = urllib.parse.quote(query.strip())
            rest_url = f"{self.mcp_url}/search?query={encoded_query}&limit={limit}"
            req = urllib.request.Request(rest_url, method="GET")
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                if resp.status == 200:
                    res_data = json.loads(resp.read().decode("utf-8"))
                    results = self._extract_results_from_json(res_data)
                    if results:
                        return results[:limit]
        except Exception:
            pass

        return None

    def _extract_results_from_rpc(self, rpc_response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse MCP JSON-RPC tool output."""
        try:
            result = rpc_response.get("result", {})
            content = result.get("content", [])
            items = []
            for c in content:
                if c.get("type") == "text":
                    text_val = c.get("text", "")
                    try:
                        parsed = json.loads(text_val)
                        if isinstance(parsed, list):
                            for item in parsed:
                                items.append(self._format_note_item(item))
                        elif isinstance(parsed, dict):
                            items.append(self._format_note_item(parsed))
                    except Exception:
                        items.append({"title": "Smart Note", "path": "", "score": 1.0, "content": text_val})
            if items:
                return items
        except Exception:
            pass
        return []

    def _extract_results_from_json(self, data: Any) -> List[Dict[str, Any]]:
        """Parse raw JSON array or dict search output."""
        items = []
        if isinstance(data, list):
            for d in data:
                if isinstance(d, dict):
                    items.append(self._format_note_item(d))
        elif isinstance(data, dict):
            raw_items = data.get("results") or data.get("notes") or data.get("data") or []
            for d in raw_items:
                if isinstance(d, dict):
                    items.append(self._format_note_item(d))
        return items

    def _format_note_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize note fields."""
        title = item.get("title") or item.get("name") or item.get("path") or "Untitled Note"
        path = item.get("path") or item.get("filepath") or ""
        score = item.get("score") or item.get("similarity") or 0.0
        content = item.get("content") or item.get("text") or item.get("excerpt") or ""
        return {
            "title": str(title),
            "path": str(path),
            "score": float(score) if isinstance(score, (int, float)) else 0.0,
            "content": str(content)
        }
