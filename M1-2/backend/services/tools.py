"""GPT가 호출할 수 있는 내부 기능(도구) 정의와 실행.

- TOOL_SPECS: OpenAI function calling 스키마. 모든 도구는 읽기 전용이다.
- 모든 도구는 `reason`(왜 이 도구를 부르는지)을 필수 인자로 받는다. 실행에는 쓰지 않지만
  호출 기록에 남겨 "어떤 근거로 어떤 도구를 호출했는지"를 모델 스스로 설명하게 한다.
- execute_tool(): 인자를 검증하고 저장소에서 값을 읽어 JSON 직렬화 가능한 dict 를 돌려준다.
"""

import datetime as dt

from services.repository import Repository
from services.summary import build_summary

RANGE_LIMIT = 120          # get_data_range 한 번에 돌려주는 최대 포인트 수
CONV_LIST_LIMIT = 20
MESSAGE_PREVIEW = 600      # get_conversation 메시지 한 개당 최대 글자 수

_REASON = {"type": "string", "description": "이 도구를 호출하는 이유를 한국어 한 문장으로"}


def _spec(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {**properties, "reason": _REASON},
                "required": [*required, "reason"],
                "additionalProperties": False,
            },
        },
    }


TOOL_SPECS = [
    _spec("get_data_summary",
          "저장된 시계열 데이터 전체의 요약(기간, 개수, 평균·최고·최저·최신, 변화율, 변동성, 이동평균, 최근 트렌드)을 조회한다.",
          {}, []),
    _spec("get_data_range",
          f"start_date~end_date(포함) 기간의 원본 데이터 포인트(date, value, memo)를 날짜순으로 조회한다. "
          f"한 번에 최대 {RANGE_LIMIT}개까지 돌려주며, 넘으면 truncated=true 와 함께 앞부분만 준다.",
          {"start_date": {"type": "string", "description": "YYYY-MM-DD"},
           "end_date": {"type": "string", "description": "YYYY-MM-DD"}},
          ["start_date", "end_date"]),
    _spec("get_monthly_stats",
          "월별 통계(평균·최고·최저·월말값·개수)를 조회한다. month 를 주면 그 달만, 생략하면 전체 월을 돌려준다.",
          {"month": {"type": "string", "description": "YYYY-MM (생략 가능)"}}, []),
    _spec("list_conversations",
          f"저장된 대화 목록(id, 제목, 메시지 수, 수정 시각)을 최근 수정순으로 최대 {CONV_LIST_LIMIT}개 조회한다.",
          {}, []),
    _spec("get_conversation",
          "conversation_id 로 저장된 대화 하나의 메시지들을 조회한다. id 는 list_conversations 로 먼저 확인한다.",
          {"conversation_id": {"type": "string"}}, ["conversation_id"]),
]
TOOL_NAMES = {s["function"]["name"] for s in TOOL_SPECS}


class ToolError(ValueError):
    """잘못된 도구 이름·인자. 모델에게 오류 내용을 돌려줘 스스로 고치게 한다."""


def _parse_date(value, field: str) -> str:
    try:
        return dt.date.fromisoformat(str(value)).isoformat()
    except ValueError:
        raise ToolError(f"{field} 는 YYYY-MM-DD 형식이어야 합니다: {value!r}")


def _iso(v) -> str:
    return v.isoformat() if hasattr(v, "isoformat") else str(v)


def execute_tool(repo: Repository, name: str, args: dict) -> dict:
    if name not in TOOL_NAMES:
        raise ToolError(f"알 수 없는 도구: {name}")

    if name == "get_data_summary":
        s = build_summary(repo.list_data())
        return {k: s[k] for k in ("dataset", "unit", "period", "count", "metrics", "trend")}

    if name == "get_data_range":
        start = _parse_date(args.get("start_date"), "start_date")
        end = _parse_date(args.get("end_date"), "end_date")
        if start > end:
            raise ToolError("start_date 가 end_date 보다 늦습니다.")
        points = [{k: d[k] for k in ("date", "value", "memo")}
                  for d in repo.list_data() if start <= d["date"] <= end]
        return {"start_date": start, "end_date": end, "count": len(points),
                "truncated": len(points) > RANGE_LIMIT, "points": points[:RANGE_LIMIT]}

    if name == "get_monthly_stats":
        monthly = build_summary(repo.list_data())["monthly"]
        month = args.get("month")
        if month:
            if len(str(month)) != 7:
                raise ToolError(f"month 는 YYYY-MM 형식이어야 합니다: {month!r}")
            monthly = [m for m in monthly if m["month"] == month]
        return {"months": monthly}

    if name == "list_conversations":
        convs = repo.list_conversations()[:CONV_LIST_LIMIT]
        return {"conversations": [
            {"id": c["id"], "title": c["title"], "message_count": c["message_count"],
             "updated_at": _iso(c["updated_at"])} for c in convs]}

    # get_conversation
    conv_id = str(args.get("conversation_id") or "").strip()
    if not conv_id:
        raise ToolError("conversation_id 가 필요합니다.")
    conv = repo.get_conversation(conv_id)
    if not conv:
        raise ToolError(f"대화를 찾을 수 없습니다: {conv_id}")
    return {"id": conv["id"], "title": conv["title"], "messages": [
        {"role": m["role"], "content": m["content"][:MESSAGE_PREVIEW]} for m in conv["messages"]]}


def summarize_result(name: str, result: dict) -> str:
    """호출 기록(화면·README)에 보여줄 짧은 결과 설명."""
    if name == "get_data_summary":
        return f"{result['period']} · {result['count']}개 · {result['trend']}"
    if name == "get_data_range":
        more = " (일부만)" if result["truncated"] else ""
        return f"{result['start_date']}~{result['end_date']} {result['count']}개{more}"
    if name == "get_monthly_stats":
        return f"{len(result['months'])}개월"
    if name == "list_conversations":
        return f"대화 {len(result['conversations'])}건"
    return f"'{result['title']}' 메시지 {len(result['messages'])}개"
