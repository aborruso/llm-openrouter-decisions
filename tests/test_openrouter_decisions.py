import base64
import json

import llm
import pytest
from click.testing import CliRunner
from llm.cli import cli

URL = "https://openrouter.ai/api/alpha/decisions"
MODEL = "openrouter-decisions/typesafe/jev-1.14"
TEXT_MODEL = "openrouter-decisions/microsoft/microsoft-decision-1"
CRITERIA = {
    "noul": None,
    "choice": {"billing": "Payments", "other": None},
    "score": ["None", "Some", "Complete"],
    "box": None,
}
ANSWERS = {
    "noul": {"type": "noul", "noul": 0.8},
    "choice": {
        "type": "choice",
        "choice": "billing",
        "probabilities": {"billing": 0.8, "other": 0.2},
        "confidence": 0.6,
    },
    "score": {
        "type": "score",
        "score": 1.2,
        "legend": {"0": "None", "1": "Some", "2": "Complete"},
        "probabilities": {"0": 0.1, "1": 0.6, "2": 0.3},
        "confidence": 0.4,
    },
    "box": {
        "type": "box",
        "box": {"top": 0.49, "bottom": 0.89, "left": 0.58, "right": 0.96},
        "confidence": 0.93,
    },
}
# Smallest valid PNG: 1x1 transparent pixel
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


def payload(kind="noul"):
    return {
        "model": "typesafe/jev-1.14-20261014",
        "answers": {"evaluation": ANSWERS[kind]},
        "usage": {"input_tokens": 12, "output_tokens": 3, "cost": 0.0000012},
        "id": "gen-dec-1",
        "provider": "TypeSafe",
    }


def test_registration():
    for model in [llm.get_model(MODEL), llm.get_async_model(MODEL)]:
        assert model.supports_conversation is False
        assert model.can_stream is False
        assert model.supports_schema is False
        assert model.supports_tools is False
        assert model.needs_key == "openrouter"
        assert model.attachment_types == {"image/png", "image/jpeg"}
    assert llm.get_model(TEXT_MODEL).attachment_types == set()


def test_no_models_without_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_KEY")
    with pytest.raises(llm.UnknownModelError):
        llm.get_model(MODEL)


@pytest.mark.parametrize("kind", ANSWERS)
@pytest.mark.parametrize("async_", [False, True])
@pytest.mark.asyncio
async def test_evaluate(kind, async_, httpx2_mock):
    httpx2_mock.add_response(url=URL, json=payload(kind))
    model = llm.get_async_model(MODEL) if async_ else llm.get_model(MODEL)
    response = model.prompt(
        "Please refund my payment",
        system="Evaluate this message",
        answer_type=kind,
        criteria=CRITERIA[kind],
    )
    text = await response.text() if async_ else response.text()
    assert json.loads(text) == ANSWERS[kind]
    data = await response.json() if async_ else response.json()
    assert data == payload(kind)
    usage = await response.usage() if async_ else response.usage()
    assert (usage.input, usage.output) == (12, 3)
    request = httpx2_mock.get_request()
    assert request.headers["Authorization"] == "Bearer test-openrouter-secret"
    assert request.headers["X-OpenRouter-Title"] == "LLM"
    body = json.loads(request.content)
    assert body["model"] == "typesafe/jev-1.14"
    assert body["state"] == "Please refund my payment"
    question = body["questions"]["evaluation"]
    assert question["instructions"] == "Evaluate this message"
    assert question["type"] == kind
    assert question.get("criteria") == CRITERIA[kind]


def test_image_attachment(httpx2_mock):
    httpx2_mock.add_response(json=payload())
    llm.get_model(MODEL).prompt(
        "Listing title: Red square sticker",
        system="The photo shows the item in the title.",
        attachments=[llm.Attachment(content=PNG)],
    ).text()
    state = json.loads(httpx2_mock.get_request().content)["state"]
    assert state[0] == "Listing title: Red square sticker"
    assert state[1] == {
        "type": "image_url",
        "image_url": {
            "url": "data:image/png;base64," + base64.b64encode(PNG).decode()
        },
    }


def test_image_only(httpx2_mock):
    httpx2_mock.add_response(json=payload("box"))
    llm.get_model(MODEL).prompt(
        "", system="the red square", answer_type="box",
        attachments=[llm.Attachment(content=PNG)],
    ).text()
    state = json.loads(httpx2_mock.get_request().content)["state"]
    assert len(state) == 1 and state[0]["type"] == "image_url"


@pytest.mark.parametrize(
    "state,expected_len", [(["a", "b"], 3), ({"title": "x"}, 2), ("text", 2)]
)
def test_json_state_with_image(state, expected_len, httpx2_mock):
    httpx2_mock.add_response(json=payload())
    llm.get_model(MODEL).prompt(
        json.dumps(state), system="Q", input_format="json",
        attachments=[llm.Attachment(content=PNG)],
    ).text()
    body_state = json.loads(httpx2_mock.get_request().content)["state"]
    assert len(body_state) == expected_len
    assert body_state[-1]["type"] == "image_url"


def test_image_rejected_by_text_model(httpx2_mock):
    with pytest.raises(ValueError):
        llm.get_model(TEXT_MODEL).prompt(
            "Input", system="Q", attachments=[llm.Attachment(content=PNG)]
        ).text()
    assert not httpx2_mock.get_requests()


@pytest.mark.parametrize(
    "state", [{"text": "Refund please", "count": 0}, ["a", "b"], "a string"]
)
def test_json_state(state, httpx2_mock):
    httpx2_mock.add_response(json=payload())
    llm.get_model(MODEL).prompt(
        json.dumps(state), system="Refund?", input_format="json"
    ).text()
    assert json.loads(httpx2_mock.get_request().content)["state"] == state


def test_fragments_and_explicit_messages(httpx2_mock):
    httpx2_mock.add_response(json=payload())
    llm.get_model(MODEL).prompt(
        messages=[llm.system("Refund?"), llm.user("Please refund")],
        fragments=["this payment"],
    ).text()
    body = json.loads(httpx2_mock.get_request().content)
    assert "Please refund" in body["state"] and "this payment" in body["state"]
    assert body["questions"]["evaluation"]["instructions"] == "Refund?"


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"system": " "},
        {"system": "Q", "input_format": "invalid"},
        {"system": "Q", "answer_type": "invalid"},
        {"system": "Q", "answer_type": "choice"},
        {"system": "Q", "answer_type": "choice", "criteria": {"one": "Only one"}},
        {"system": "Q", "answer_type": "score", "criteria": ["Only one"]},
        {"system": "Q", "answer_type": "score", "criteria": ["a"] * 11},
        {"system": "Q", "answer_type": "box", "criteria": ["a", "b"]},
        {"system": "Q", "criteria": '{"true":"yes","true":"again","false":"no"}'},
        {"system": "Q", "criteria": {"yes": "yes", "no": "no"}},
    ],
)
def test_invalid_config(kwargs, httpx2_mock):
    with pytest.raises(ValueError):
        llm.get_model(MODEL).prompt("Input", **kwargs).text()
    assert not httpx2_mock.get_requests()


@pytest.mark.parametrize(
    "state", ["null", "12", "true", "{broken", '{"x":1,"x":2}', '{"x":NaN}']
)
def test_invalid_json_state(state, httpx2_mock):
    with pytest.raises(ValueError):
        llm.get_model(MODEL).prompt(state, system="Q", input_format="json").text()
    assert not httpx2_mock.get_requests()


@pytest.mark.parametrize("async_", [False, True])
@pytest.mark.asyncio
async def test_replies_rejected(async_, httpx2_mock):
    httpx2_mock.add_response(json=payload())
    model = llm.get_async_model(MODEL) if async_ else llm.get_model(MODEL)
    response = model.prompt("Input", system="Q")
    if async_:
        await response.text()
    else:
        response.text()
    with pytest.raises(llm.ConversationNotSupported):
        if async_:
            await response.reply("Again")
        else:
            response.reply("Again")
    assert len(httpx2_mock.get_requests()) == 1


def test_cli_logging_template_and_continuation(httpx2_mock):
    runner = CliRunner()
    args = ["-m", MODEL, "-s", "Refund?", "-o", "answer_type", "noul"]
    saved = runner.invoke(cli, [*args, "--save", "refund"])
    assert saved.exit_code == 0, saved.output
    httpx2_mock.add_response(json=payload())
    result = runner.invoke(cli, ["-t", "refund"], input="Refund my payment")
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == ANSWERS["noul"]
    logs = runner.invoke(cli, ["logs", "--json"])
    assert logs.exit_code == 0, logs.output
    assert "jev-1.14-20261014" in logs.output
    assert "test-openrouter-secret" not in logs.output
    for args in [["-c", "Again"], ["chat", "-m", MODEL]]:
        result = runner.invoke(cli, args)
        assert result.exit_code != 0
        assert "does not support conversations" in result.output
    assert len(httpx2_mock.get_requests()) == 1


def test_no_key_at_prompt_time(monkeypatch, httpx2_mock):
    model = llm.get_model(MODEL)
    monkeypatch.delenv("OPENROUTER_KEY")
    with pytest.raises(llm.NeedsKeyException):
        model.prompt("Input", system="Q").text()
    assert not httpx2_mock.get_requests()


QUESTIONS = {
    "refund": {"type": "noul", "instructions": "Does it ask for a refund?"},
    "department": {
        "type": "choice",
        "instructions": "Which department?",
        "criteria": {"billing": None, "other": None},
    },
}


@pytest.mark.parametrize("as_string", [False, True])
def test_multiple_questions(as_string, httpx2_mock):
    data = payload()
    data["answers"] = {"refund": ANSWERS["noul"], "department": ANSWERS["choice"]}
    httpx2_mock.add_response(json=data)
    response = llm.get_model(MODEL).prompt(
        "Please refund my payment",
        questions=json.dumps(QUESTIONS) if as_string else QUESTIONS,
    )
    assert json.loads(response.text()) == data["answers"]
    body = json.loads(httpx2_mock.get_request().content)
    assert body["questions"] == QUESTIONS


def test_multiple_questions_missing_answer(httpx2_mock):
    data = payload()
    data["answers"] = {"refund": ANSWERS["noul"]}
    httpx2_mock.add_response(json=data)
    with pytest.raises(llm.ModelError, match="Invalid OpenRouter Decisions response"):
        llm.get_model(MODEL).prompt("Input", questions=QUESTIONS).text()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"system": "Q", "questions": QUESTIONS},
        {"questions": QUESTIONS, "answer_type": "choice"},
        {"questions": QUESTIONS, "criteria": {"true": "a", "false": "b"}},
        {"questions": {}},
        {"questions": "[1]"},
        {"questions": {"q": {"type": "essay", "instructions": "Q"}}},
        {"questions": {"q": {"type": "noul"}}},
    ],
)
def test_invalid_questions(kwargs, httpx2_mock):
    with pytest.raises(ValueError):
        llm.get_model(MODEL).prompt("Input", **kwargs).text()
    assert not httpx2_mock.get_requests()
