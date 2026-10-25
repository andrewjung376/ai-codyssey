"""My Stock AI 비서 — MCP Server (보너스 5.1, 외부 채널 연동).

백엔드 /api/chat/tools 에서 GPT가 쓰는 것과 같은 읽기 전용 도구 5개를 MCP로 제공한다.
도구는 배포된(또는 로컬) REST API를 호출하므로 이 서버에는 Firebase·OpenAI 키가 필요 없다.

실행 (stdio):  python mcp_server/server.py
환경 변수:     MYSTOCK_API_BASE_URL (기본 https://mystock-ai-api.onrender.com)
"""

import logging
import os
from typing import Any

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

# stdio 서버라 stdout 은 프로토콜 전용이다. httpx 요청 로그(stderr)도 줄여 둔다
logging.getLogger("httpx").setLevel(logging.WARNING)

API_BASE = os.getenv("MYSTOCK_API_BASE_URL", "https://mystock-ai-api.onrender.com").rstrip("/")
# Render 무료 티어는 잠들어 있으면 첫 요청에 최대 1분 가까이 걸린다
TIMEOUT = float(os.getenv("MYSTOCK_API_TIMEOUT", "90"))
RANGE_LIMIT = 120
CONV_LIST_LIMIT = 20
MESSAGE_PREVIEW = 600

READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)

mcp = MCPServer(
    name="my-stock-ai",
    title="My Stock AI 비서",
    instructions=(
        "삼성전자(005930.KS) 일별 종가 시계열과 저장된 대화 기록을 조회하는 읽기 전용 도구입니다. "
        "기간이 정해진 질문은 get_data_range, 전체 흐름은 get_data_summary, 월 비교는 get_monthly_stats 를 쓰세요."
    ),
)


async def _get(path: str, params: dict | None = None) -> Any:
    """API 오류는 ToolError 로 바꿔, 클라이언트의 모델이 이유를 읽고 인자를 고칠 수 있게 한다."""
    try:
        async with httpx.AsyncClient(base_url=API_BASE, timeout=TIMEOUT) as client:
            res = await client.get(path, params=params)
    except httpx.HTTPError as e:
        raise ToolError(f"API({API_BASE})에 연결하지 못했습니다: {type(e).__name__}") from e
    if res.status_code >= 400:
        try:
            detail = res.json().get("detail")
        except ValueError:
            detail = res.text[:200]
        raise ToolError(f"API 오류 {res.status_code}: {detail}")
    return res.json()


@mcp.tool(annotations=READ_ONLY)
async def get_data_summary() -> dict:
    """저장된 시계열 데이터 전체의 요약(기간, 개수, 평균·최고·최저·최신, 변화율, 변동성, 이동평균, 최근 트렌드)을 조회한다."""
    s = await _get("/api/data/summary")
    return {k: s[k] for k in ("dataset", "unit", "period", "count", "metrics", "trend")}


@mcp.tool(annotations=READ_ONLY)
async def get_data_range(start_date: str, end_date: str) -> dict:
    """start_date~end_date(YYYY-MM-DD, 포함) 기간의 데이터 포인트(date, value, memo)를 날짜순으로 조회한다. 최대 120개."""
    if start_date > end_date:
        raise ToolError("start_date 가 end_date 보다 늦습니다.")
    rows = await _get("/api/data", {"start": start_date, "end": end_date})
    # 기간 필터가 없는 이전 버전 API와도 동작하도록 한 번 더 거른다
    points = [{k: r[k] for k in ("date", "value", "memo")} for r in rows if start_date <= r["date"] <= end_date]
    return {"start_date": start_date, "end_date": end_date, "count": len(points),
            "truncated": len(points) > RANGE_LIMIT, "points": points[:RANGE_LIMIT]}


@mcp.tool(annotations=READ_ONLY)
async def get_monthly_stats(month: str | None = None) -> dict:
    """월별 통계(평균·최고·최저·월말값·개수)를 조회한다. month(YYYY-MM)를 주면 그 달만, 생략하면 전체 월."""
    monthly = (await _get("/api/data/summary"))["monthly"]
    if month:
        monthly = [m for m in monthly if m["month"] == month]
    return {"months": monthly}


@mcp.tool(annotations=READ_ONLY)
async def list_conversations() -> dict:
    """저장된 대화 목록(id, 제목, 메시지 수, 수정 시각)을 최근 수정순으로 최대 20개 조회한다."""
    convs = await _get("/api/conversations")
    return {"conversations": [{k: c[k] for k in ("id", "title", "message_count", "updated_at")}
                              for c in convs[:CONV_LIST_LIMIT]]}


@mcp.tool(annotations=READ_ONLY)
async def get_conversation(conversation_id: str) -> dict:
    """conversation_id 로 저장된 대화 하나의 메시지들을 조회한다. id 는 list_conversations 로 먼저 확인한다."""
    conv = await _get(f"/api/conversations/{conversation_id}")
    return {"id": conv["id"], "title": conv["title"], "messages": [
        {"role": m["role"], "content": m["content"][:MESSAGE_PREVIEW]} for m in conv["messages"]]}


if __name__ == "__main__":
    mcp.run("stdio")
