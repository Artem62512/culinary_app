import httpx
import json

MCP_URL = "https://mcp.vkusvill.ru/mcp"

headers = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}

def initialize_session():
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "culinary-app", "version": "0.1"}
        }
    }

    with httpx.Client(timeout=30) as client:
        resp = client.post(MCP_URL, json=payload, headers=headers)
        print(f"Status: {resp.status_code}")

        session_id = resp.headers.get("mcp-session-id")
        print(f"Session ID: {session_id}")

        print(f"Response: {resp.text[:1000]}")
        return session_id

if __name__ == "__main__":
    initialize_session()
