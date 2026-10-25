"""Claude Code(헤드리스 `claude -p`)로 MCP 서버를 실제 대화에서 쓰는지 확인한다.

M1-2 폴더에서 실행: python mcp_server/check_claude.py "질문"
- --mcp-config .mcp.json --strict-mcp-config : 이 프로젝트의 MCP 서버만 붙인다 (전역 설정 변경 없음)
- --allowedTools mcp__my-stock-ai__*       : 이 서버의 도구만 허용한다
stream-json 이벤트에서 Claude가 고른 도구와 인자, 최종 답을 뽑아 출력한다.
"""

import json
import subprocess
import sys

question = sys.argv[1] if len(sys.argv) > 1 else "삼성전자 6월과 9월 월평균을 비교해 줘"
cmd = ["claude", "-p", question, "--mcp-config", ".mcp.json", "--strict-mcp-config",
       "--allowedTools", "mcp__my-stock-ai__*", "--output-format", "stream-json", "--verbose"]
proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=600)

print("Q:", question)
for line in proc.stdout.splitlines():
    try:
        ev = json.loads(line)
    except json.JSONDecodeError:
        continue
    if ev.get("type") == "system" and ev.get("subtype") == "init":
        servers = [(s.get("name"), s.get("status")) for s in ev.get("mcp_servers", [])]
        tools = [t for t in ev.get("tools", []) if t.startswith("mcp__my-stock-ai__")]
        print("MCP 서버:", servers, "| 도구:", [t.split("__")[-1] for t in tools])
    elif ev.get("type") == "assistant":
        for block in ev["message"].get("content", []):
            if block.get("type") == "tool_use":
                print(f"  🔧 {block['name'].split('__')[-1]}({json.dumps(block.get('input', {}), ensure_ascii=False)})")
    elif ev.get("type") == "user":
        for block in ev["message"].get("content", []) if isinstance(ev["message"].get("content"), list) else []:
            if block.get("type") == "tool_result":
                print("     ↳", "오류" if block.get("is_error") else "결과 수신")
    elif ev.get("type") == "result":
        print("A:", (ev.get("result") or "")[:500])
        print(f"(turns={ev.get('num_turns')}, {ev.get('duration_ms', 0) / 1000:.1f}s, is_error={ev.get('is_error')})")
if proc.returncode:
    print("exit", proc.returncode, proc.stderr[-500:])
