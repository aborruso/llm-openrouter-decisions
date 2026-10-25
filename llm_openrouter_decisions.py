"""Single-turn evaluations with the decision models of the OpenRouter Decisions API."""

import json
import time
from typing import Literal

import httpx2
import llm
from llm.parts import AttachmentPart, TextPart
from pydantic import Field, model_validator

API_URL = "https://openrouter.ai/api/alpha/decisions"
MODELS_URL = "https://openrouter.ai/api/v1/models?output_modalities=decisions"
MODELS_CACHE = "openrouter_decisions_models.json"
CACHE_TIMEOUT = 3600
PREFIX = "openrouter-decisions/"
QUESTION_ID = "evaluation"
HEADERS = {
    "HTTP-Referer": "https://llm.datasette.io/",
    "X-OpenRouter-Title": "LLM",
}
# The Decisions API takes images as base64 data URLs in these formats
IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp"}


def nonempty_string(value):
    return isinstance(value, str) and bool(value.strip()) and "\x00" not in value


def parse_json(value):
    def unique_object(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = item
        return result

    result = json.loads(value, object_pairs_hook=unique_object)
    json.dumps(result, allow_nan=False)
    return result


def get_decision_models(skip_cache=False):
    """Model definitions from the OpenRouter catalog, cached for an hour.

    Falls back to a stale cache, then to an empty list, if the download fails."""
    path = llm.user_dir() / MODELS_CACHE
    if (
        not skip_cache
        and path.is_file()
        and time.time() - path.stat().st_mtime < CACHE_TIMEOUT
    ):
        return json.loads(path.read_text())["data"]
    try:
        result = httpx2.get(MODELS_URL, headers=HEADERS, timeout=20)
        result.raise_for_status()
        data = result.json()
        models = data["data"]
    except (httpx2.HTTPError, ValueError, KeyError):
        if path.is_file():
            return json.loads(path.read_text())["data"]
        return []
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    return models


class DecisionOptions(llm.Options):
    answer_type: Literal["noul", "choice", "score", "box"] = Field(
        default="noul",
        description="noul: probability of yes; choice: one category; score: a degree on ordered levels; box: where the target is in an image (Jev 1.14 only).",
    )
    criteria: dict | list | str | None = Field(
        default=None,
        description="JSON category descriptions, rating levels, or optional true/false definitions.",
    )
    input_format: Literal["text", "json"] = Field(
        default="text",
        description="Treat the prompt as text, or parse it as JSON state (string, object, or array).",
    )
    questions: dict | str | None = Field(
        default=None,
        description="JSON object of named questions, each with type, instructions and optional criteria, asked in one request instead of -s.",
    )

    @model_validator(mode="after")
    def valid_questions(self):
        value = self.questions
        if value is None:
            return self
        if isinstance(value, str):
            try:
                value = parse_json(value)
            except ValueError:
                raise ValueError(
                    "questions must be valid JSON with unique keys and finite numbers."
                ) from None
        if (
            not isinstance(value, dict)
            or not value
            or not all(
                nonempty_string(name)
                and isinstance(q, dict)
                and q.get("type") in ("noul", "choice", "score", "box")
                and q.get("instructions")
                for name, q in value.items()
            )
        ):
            raise ValueError(
                "questions must map names to objects with a type (noul, choice, score, box) and instructions."
            )
        self.questions = value
        return self

    @model_validator(mode="after")
    def valid_criteria(self):
        if self.questions is not None:
            if self.criteria is not None or self.answer_type != "noul":
                raise ValueError(
                    "Use either questions or answer_type and criteria, not both."
                )
            return self
        value = self.criteria
        if isinstance(value, str):
            try:
                value = parse_json(value)
            except ValueError:
                raise ValueError(
                    "criteria must be valid JSON with unique keys and finite numbers."
                ) from None
        if self.answer_type == "noul":
            if value is not None and (
                not isinstance(value, dict)
                or set(value) != {"true", "false"}
                or not all(nonempty_string(v) for v in value.values())
            ):
                raise ValueError(
                    "noul criteria must contain true and false descriptions, or be omitted."
                )
        elif self.answer_type == "box":
            if value is not None:
                raise ValueError("box questions take no criteria.")
        elif self.answer_type == "choice":
            if (
                not isinstance(value, dict)
                or len(value) < 2
                or not all(
                    nonempty_string(k) and (v is None or nonempty_string(v))
                    for k, v in value.items()
                )
            ):
                raise ValueError(
                    "choice criteria need at least two named categories with descriptions or null."
                )
        elif (
            not isinstance(value, list)
            or not 2 <= len(value) <= 10
            or not all(nonempty_string(v) for v in value)
        ):
            raise ValueError(
                "score criteria need 2–10 nonempty level descriptions, from lowest to highest."
            )
        self.criteria = value
        return self


def image_part(attachment):
    mime = attachment.resolve_type()
    return {
        "type": "image_url",
        "image_url": {"url": f"data:{mime};base64,{attachment.base64_content()}"},
    }


class _Decision:
    needs_key = "openrouter"
    key_env_var = "OPENROUTER_KEY"
    can_stream = False
    supports_conversation = False
    supports_schema = False
    supports_tools = False
    Options = DecisionOptions

    def __init__(self, openrouter_id, input_modalities=()):
        self.openrouter_id = openrouter_id
        self.model_id = PREFIX + openrouter_id
        if "image" in input_modalities:
            # Jev accepts only PNG and JPEG
            jev = openrouter_id.lstrip("~").startswith("typesafe/")
            self.attachment_types = IMAGE_TYPES - {"image/webp"} if jev else IMAGE_TYPES

    def __str__(self):
        return "OpenRouter Decisions: {}".format(self.model_id)

    def build_payload(self, prompt):
        inputs, instructions, images = [], [], []
        for message in prompt.messages:
            if message.role not in ("system", "user"):
                raise ValueError("Decision models support single-turn evaluation only.")
            for part in message.parts:
                if isinstance(part, TextPart):
                    (instructions if message.role == "system" else inputs).append(
                        part.text
                    )
                elif isinstance(part, AttachmentPart) and message.role == "user":
                    images.append(image_part(part.attachment))
                else:
                    raise ValueError(
                        "Decision models accept text and image input only; tools are unsupported."
                    )
        question_text = "\n\n".join(instructions)
        state = "\n\n".join(inputs)
        if prompt.options.questions is not None:
            if question_text.strip():
                raise ValueError("Use either -s/--system or the questions option, not both.")
        elif not question_text.strip():
            raise ValueError("Supply a question using -s/--system or system= in Python.")
        if not state.strip() and not images:
            raise ValueError("Supply input data as the prompt, on stdin or as -a images.")
        if prompt.options.input_format == "json":
            try:
                state = parse_json(state)
            except ValueError:
                raise ValueError(
                    "Input must be valid JSON with unique keys and finite numbers."
                ) from None
            if not isinstance(state, (str, dict, list)):
                raise ValueError("JSON input must be a string, object, or array.")
        if images:
            # Images go in the top-level state array, the only place every model reads them
            if isinstance(state, list):
                state = state + images
            elif isinstance(state, str) and not state.strip():
                state = images
            else:
                state = [state] + images
        if prompt.options.questions is not None:
            questions = prompt.options.questions
        else:
            question = {"type": prompt.options.answer_type, "instructions": question_text}
            if prompt.options.criteria is not None:
                question["criteria"] = prompt.options.criteria
            questions = {QUESTION_ID: question}
        return {"model": self.openrouter_id, "state": state, "questions": questions}

    def finish_response(self, response, result, prompt):
        if result.status_code != 200:
            raise llm.ModelError(
                f"OpenRouter Decisions HTTP {result.status_code}: {result.text}"
            )
        try:
            data = parse_json(result.content)
            questions = prompt.options.questions
            if questions is None:
                answer = data["answers"][QUESTION_ID]
                answers = [answer]
            else:
                # Multiple questions: return every answer, keyed by question name
                answer = {name: data["answers"][name] for name in questions}
                answers = answer.values()
            model = data["model"]
            usage = data["usage"]
            if not all(isinstance(a, dict) for a in answers) or not nonempty_string(
                model
            ):
                raise ValueError("Expected answer objects and model name")
            if not all(
                type(usage[k]) is int and usage[k] >= 0
                for k in ("input_tokens", "output_tokens")
            ):
                raise ValueError("Expected token counts")
        except (ValueError, KeyError, TypeError, UnicodeError):
            raise llm.ModelError(
                "Invalid OpenRouter Decisions response: expected JSON with an answer, model, and token usage."
            ) from None
        response.response_json = data
        response.set_usage(input=usage["input_tokens"], output=usage["output_tokens"])
        response.set_resolved_model(model)
        return json.dumps(answer, ensure_ascii=False, allow_nan=False)

    def headers(self, key):
        return {"Authorization": f"Bearer {key}", **HEADERS}


class Decision(_Decision, llm.KeyModel):
    def execute(self, prompt, stream, response, conversation, key=None):
        payload = self.build_payload(prompt)
        try:
            with httpx2.Client(timeout=60, follow_redirects=False) as client:
                result = client.post(API_URL, json=payload, headers=self.headers(key))
        except httpx2.TransportError as ex:
            raise llm.ModelError(f"OpenRouter Decisions request failed: {ex}") from None
        yield self.finish_response(response, result, prompt)


class AsyncDecision(_Decision, llm.AsyncKeyModel):
    async def execute(self, prompt, stream, response, conversation, key=None):
        payload = self.build_payload(prompt)
        try:
            async with httpx2.AsyncClient(timeout=60, follow_redirects=False) as client:
                result = await client.post(
                    API_URL, json=payload, headers=self.headers(key)
                )
        except httpx2.TransportError as ex:
            raise llm.ModelError(f"OpenRouter Decisions request failed: {ex}") from None
        yield self.finish_response(response, result, prompt)


@llm.hookimpl
def register_models(register):
    # Same rule as llm-openrouter: no key, no catalog download
    if not llm.get_key("", "openrouter", "OPENROUTER_KEY"):
        return
    for definition in get_decision_models():
        modalities = definition.get("architecture", {}).get("input_modalities", [])
        register(
            Decision(definition["id"], modalities),
            AsyncDecision(definition["id"], modalities),
        )
