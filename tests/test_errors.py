import json

import httpx2
import llm
import pytest

from test_openrouter_decisions import ANSWERS, MODEL, payload


async def call(async_):
    model = llm.get_async_model(MODEL) if async_ else llm.get_model(MODEL)
    response = model.prompt("Input", system="Question")
    return await response.text() if async_ else response.text()


@pytest.mark.parametrize("async_", [False, True])
@pytest.mark.parametrize("status", [302, 400, 401, 402, 413, 429, 500])
@pytest.mark.asyncio
async def test_http_errors(async_, status, httpx2_mock):
    httpx2_mock.add_response(
        status_code=status,
        json={"error": {"message": "Request failed"}},
        headers={"Location": "https://example.com/redirect"},
    )
    with pytest.raises(llm.ModelError) as ex:
        await call(async_)
    assert str(status) in str(ex.value)
    assert "Request failed" in str(ex.value)
    assert len(httpx2_mock.get_requests()) == 1


@pytest.mark.parametrize("async_", [False, True])
@pytest.mark.asyncio
async def test_transport_error(async_, httpx2_mock):
    httpx2_mock.add_exception(httpx2.ConnectError("Connection refused"))
    with pytest.raises(llm.ModelError, match="Connection refused"):
        await call(async_)


@pytest.mark.parametrize("async_", [False, True])
@pytest.mark.parametrize(
    "bad", [b"{broken", b"\xff", b'{"model":"x","model":"y"}', b"{}", b"[]"]
)
@pytest.mark.asyncio
async def test_invalid_response(async_, bad, httpx2_mock):
    httpx2_mock.add_response(content=bad)
    with pytest.raises(llm.ModelError, match="Invalid OpenRouter Decisions response"):
        await call(async_)


def test_cost_preserved_in_response_json(httpx2_mock):
    httpx2_mock.add_response(json=payload())
    response = llm.get_model(MODEL).prompt("Input", system="Q")
    assert json.loads(response.text()) == ANSWERS["noul"]
    assert response.json()["usage"]["cost"] == 0.0000012
