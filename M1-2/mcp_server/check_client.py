"""MCP 서버를 stdio 로 띄워 도구 목록 조회와 호출을 확인하는 클라이언트.

사용: python mcp_server/check_client.py [API_BASE_URL]
      (생략하면 서버 기본값 https://mystock-ai-api.onrender.com)
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import Client, StdioServerParameters

SERVER = Path(__file__).resolve().parent / "server.py"


def data_of(result) -> dict:
    if result.structured_content is not None:
        return result.structured_content
    return json.loads(result.content[0].text)


def show(result) -> str:
    if result.is_error:
        return "ERROR " + " ".join(getattr(c, "text", "") for c in result.content)[:200]
    return json.dumps(data_of(result), ensure_ascii=False)[:260]


async def main():
    env = dict(os.environ)
    if len(sys.argv) > 1:
        env["MYSTOCK_API_BASE_URL"] = sys.argv[1]
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER)], env=env)

    async with Client(params, read_timeout_seconds=120) as client:
        print("server:", client.server_info.name if client.server_info else "?",
              "| API:", env.get("MYSTOCK_API_BASE_URL", "(기본값)"))
        tools = (await client.list_tools()).tools
        for t in tools:
            ro = t.annotations.read_only_hint if t.annotations else None
            print(f"  tool {t.name}({', '.join(t.input_schema.get('properties', {}))}) read_only={ro}")

        calls = [
            ("get_data_summary", {}),
            ("get_data_range", {"start_date": "2026-03-02", "end_date": "2026-03-06"}),
            ("get_monthly_stats", {"month": "2026-06"}),
            ("list_conversations", {}),
            ("get_data_range", {"start_date": "2026-03-06", "end_date": "2026-03-02"}),  # 오류 기대
            ("get_conversation", {"conversation_id": "no-such-id"}),                     # 404 기대
        ]
        for name, args in calls:
            print(f"\n> {name}({args})\n  {show(await client.call_tool(name, args))}")

        convs = data_of(await client.call_tool("list_conversations", {}))["conversations"]
        if convs:
            r = await client.call_tool("get_conversation", {"conversation_id": convs[0]["id"]})
            print(f"\n> get_conversation({convs[0]['id'][:8]}…)\n  {show(r)}")


if __name__ == "__main__":
    asyncio.run(main())
