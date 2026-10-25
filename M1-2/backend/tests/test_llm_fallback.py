import httpx
import pytest

from services.llm import CodyProxyClient, FallbackLLM


class Ok:
    def __init__(self, text):
        self.text = text
        self.called = 0

    def complete(self, messages):
        self.called += 1
        return self.text


class Fail:
    def __init__(self, status=401):
        self.status = status
        self.called = 0

    def complete(self, messages):
        self.called += 1
        req = httpx.Request("POST", "https://example.test")
        raise httpx.HTTPStatusError("fail", request=req, response=httpx.Response(self.status, request=req))


MSGS = [{"role": "user", "content": "hi"}]


def test_cody_first_when_it_works():
    cody, openai = Ok("cody 답"), Ok("openai 답")
    assert FallbackLLM([("cody", cody), ("openai", openai)]).complete(MSGS) == ("cody 답", "cody")
    assert openai.called == 0


@pytest.mark.parametrize("status", [401, 403, 429, 500])
def test_falls_back_to_openai_on_cody_error(status):
    cody, openai = Fail(status), Ok("openai 답")
    assert FallbackLLM([("cody", cody), ("openai", openai)]).complete(MSGS) == ("openai 답", "openai")
    assert cody.called == 1


def test_raises_when_all_fail():
    with pytest.raises(httpx.HTTPStatusError):
        FallbackLLM([("cody", Fail()), ("openai", Fail(401))]).complete(MSGS)


def test_cody_client_request_shape_and_empty_reply(monkeypatch):
    seen = {}

    def fake_post(url, headers, timeout, json):
        seen.update(url=url, auth=headers["Authorization"], body=json)
        req = httpx.Request("POST", url)
        return httpx.Response(200, request=req, json={"choices": [{"message": {"content": seen.get("reply", "")}}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    client = CodyProxyClient("k", "https://copa.codyssey.kr/v1", "gpt-5-mini", 5)
    with pytest.raises(ValueError):  # 빈 응답은 실패로 보고 폴백하게 한다
        client.complete(MSGS)
    assert seen["url"] == "https://copa.codyssey.kr/v1/chat/completions"
    assert seen["auth"] == "Bearer k"
    assert seen["body"] == {"model": "gpt-5-mini", "messages": MSGS}

    seen["reply"] = " 답 "
    assert client.complete(MSGS) == "답"
