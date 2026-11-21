import httpx
import json

MCP_URL = "https://mcp.vkusvill.ru/mcp"
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}

def call_tool(name: str, arguments: dict, session_id: str | None = None):
    headers = HEADERS.copy()
    if session_id:
        headers["Mcp-Session-Id"] = session_id

    payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments}
    }

    with httpx.Client(timeout=30) as client:
        resp = client.post(MCP_URL, json=payload, headers=headers)
        print(f"Tool '{name}' -> status {resp.status_code}")
        if resp.status_code != 200:
            print(f"Error body: {resp.text[:500]}")
            return None
        return resp.json()

def main():
    # Ищем по правильному параметру q
    result = call_tool("vkusvill_products_search", {"q": "молоко", "page": 1})
    if not result:
        return

    try:
        content = result["result"]["content"][0]["text"]
        data = json.loads(content)
        products = data.get("products", [])
        if not products:
            print("No products found. Raw response:")
            print(json.dumps(data, ensure_ascii=False, indent=2)[:1500])
            return

        first = products[0]
        product_id = first.get("id") or first.get("xml_id")
        print(f"\nFound: {first.get('name')}, id={product_id}")

        details = call_tool("vkusvill_product_details", {"product_id": product_id})
        if details:
            print(f"\nDetails response (first 2000 chars):")
            print(json.dumps(details, ensure_ascii=False, indent=2)[:2000])

    except (KeyError, IndexError, json.JSONDecodeError) as e:
        print(f"Parse error: {e}")
        print(f"Raw response: {json.dumps(result, ensure_ascii=False)[:1000]}")

if __name__ == "__main__":
    main()
