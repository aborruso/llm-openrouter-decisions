"""Single-turn evaluations with the decision models of the OpenRouter Decisions API."""

import asyncio
import csv
import io
import json
import sys
import time
from pathlib import Path
from typing import Literal

import click
import httpx2
import llm
import pydantic
from llm.parts import AttachmentPart, TextPart
from pydantic import Field, model_validator
from sqlite_utils.utils import Format, rows_from_file

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
# batch: seconds to wait before each retry of a 429, 5xx or network error
RETRY_DELAYS = (1, 2, 4)
OUTPUT_FIELDS = ["row", "answer", "p", "error"]
SUFFIX_FORMATS = {
    ".csv": "csv",
    ".tsv": "tsv",
    ".json": "json",
    ".jsonl": "nl",
    ".ndjson": "nl",
}


class DecisionError(llm.ModelError):
    """A failed request; status_code is None for network errors."""

    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


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
        return f"OpenRouter Decisions: {self.model_id}"

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
            raise DecisionError(
                f"OpenRouter Decisions HTTP {result.status_code}: {result.text}",
                result.status_code,
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
            raise DecisionError(f"OpenRouter Decisions request failed: {ex}") from None
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
            raise DecisionError(f"OpenRouter Decisions request failed: {ex}") from None
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


def money(value):
    return "$" + f"{value:.7f}".rstrip("0").rstrip(".")


def read_done_rows(path, tabular, delimiter):
    """Rows already answered in a previous run's output, without errors.

    A last line cut off by an interruption is dropped."""
    text = path.read_text(encoding="utf-8")
    if not text.endswith("\n"):
        text = text[: text.rfind("\n") + 1]
    if tabular:
        records = list(csv.DictReader(io.StringIO(text), delimiter=delimiter))
    else:
        records = []
        for line in text.splitlines():
            try:
                records.append(json.loads(line))
            except ValueError:
                pass
    return [
        r
        for r in records
        if isinstance(r, dict) and str(r.get("row")).isdigit() and not r.get("error")
    ]


async def run_batch(
    model, jobs, question, options, column, concurrency, max_cost, write, db
):
    sem = asyncio.Semaphore(concurrency)
    state = {"cost": 0.0, "rows": 0, "errors": 0, "stopped": None, "fatal": None}

    async def one(number, row):
        async with sem:
            if state["stopped"] or state["fatal"]:
                return
            value = row if column is None else row.get(column)
            if isinstance(value, str):
                text, opts = value, options
            else:
                text = json.dumps(value, ensure_ascii=False)
                opts = {**options, "input_format": "json"}
            answer = error = None
            for delay in (*RETRY_DELAYS, None):
                try:
                    response = model.prompt(text, system=question, **opts)
                    answer = json.loads(await response.text())
                    break
                except DecisionError as ex:
                    if ex.status_code in (401, 402):
                        state["fatal"] = str(ex)
                        return
                    retry = (
                        ex.status_code is None
                        or ex.status_code == 429
                        or ex.status_code >= 500
                    )
                    if delay is None or not retry:
                        error = str(ex)
                        break
                    await asyncio.sleep(delay)
                except (llm.ModelError, ValueError) as ex:
                    error = str(ex)
                    break
            if answer is not None:
                state["cost"] += (await response.json())["usage"].get("cost") or 0
                if db is not None:
                    response.log_to_db(db)
            state["rows"] += 1
            state["errors"] += error is not None
            write(number, row, answer, error)
            if max_cost is not None and state["cost"] > max_cost:
                state["stopped"] = f"stopped: --max-cost {max_cost} reached"

    await asyncio.gather(*(one(number, row) for number, row in jobs))
    return state


@llm.hookimpl
def register_commands(cli):
    @cli.group(name="openrouter-decisions")
    def decisions():
        "Commands relating to the llm-openrouter-decisions plugin"

    @decisions.command()
    @click.argument(
        "input_path",
        type=click.Path(exists=True, dir_okay=False, allow_dash=True, readable=True),
    )
    @click.option(
        "model_id", "-m", "--model", required=True, help="Decision model to use"
    )
    @click.option("question", "-s", "--system", help="Question asked about every row")
    @click.option(
        "options",
        "-o",
        "--option",
        type=(str, str),
        multiple=True,
        help="key/value options for the model",
    )
    @click.option(
        "--column", help="Evaluate only this column - default: the whole row as JSON"
    )
    @click.option(
        "--format",
        "format_",
        type=click.Choice(["json", "csv", "tsv", "nl"]),
        help="Format of input file - defaults to the file extension, then auto-detect",
    )
    @click.option(
        "--output",
        type=click.Path(dir_okay=False, path_type=Path),
        help="Write results to this file instead of stdout",
    )
    @click.option(
        "--concurrency",
        type=click.IntRange(1, 32),
        default=8,
        show_default=True,
        help="Requests sent at the same time",
    )
    @click.option("--limit", type=click.IntRange(min=1), help="Only the first N rows")
    @click.option(
        "--max-cost",
        type=click.FloatRange(min=0),
        help="Stop sending requests once the spend in dollars passes this",
    )
    @click.option(
        "--resume", is_flag=True, help="Skip rows already answered in --output"
    )
    @click.option("--log", is_flag=True, help="Log every response to the LLM database")
    def batch(
        input_path,
        model_id,
        question,
        options,
        column,
        format_,
        output,
        concurrency,
        limit,
        max_cost,
        resume,
        log,
    ):
        """Ask the same question about every row of a CSV, TSV, JSON or JSONL file.

        Requests run concurrently. Each output row is the input row plus row
        (its number in the input), answer (the JSON answer), p (the
        probability, for yes/no questions) and error. Rows are written as they
        are answered, so they are not in input order. CSV and TSV input gives
        CSV and TSV output, JSON and JSONL input gives JSONL.

        Every row is a paid request: try --limit 10 first, the summary shows
        the cost per row.

        \b
            llm openrouter-decisions batch titles.csv -m jev14 \\
              -s 'The publication is about public administration.' \\
              --column title --output scored.csv
        """
        if resume and output is None:
            raise click.ClickException("--resume needs --output")
        if not llm.get_key("", "openrouter", "OPENROUTER_KEY"):
            raise click.ClickException(
                "No OpenRouter key: run 'llm keys set openrouter' or set OPENROUTER_KEY"
            )
        try:
            model = llm.get_async_model(model_id)
        except llm.UnknownModelError as ex:
            raise click.ClickException(str(ex))
        if not isinstance(model, AsyncDecision):
            raise click.ClickException(
                f"{model_id} is not an OpenRouter Decisions model"
            )
        try:
            validated = {
                k: v for k, v in model.Options(**dict(options)) if v is not None
            }
        except pydantic.ValidationError as ex:
            raise click.ClickException(str(ex))
        if not question and "questions" not in validated:
            raise click.ClickException("Supply a question with -s or -o questions")

        if format_ is None:
            # Sniffing fails on one-column CSV files, so trust the extension first
            format_ = SUFFIX_FORMATS.get(Path(input_path).suffix.lower())
        with click.open_file(input_path, "rb") as fp:
            rows, detected = rows_from_file(
                fp, Format[format_.upper()] if format_ else None
            )
            rows = list(rows)
        if not rows:
            raise click.ClickException("No rows in the input")
        if column is not None and column not in rows[0]:
            raise click.ClickException(f"No column named {column!r} in the input")
        tabular = detected in (Format.CSV, Format.TSV)
        delimiter = "\t" if detected == Format.TSV else ","
        fields = list(rows[0]) + [f for f in OUTPUT_FIELDS if f not in rows[0]]

        jobs = list(enumerate(rows, 1))[:limit]
        kept = []
        if resume and output.exists():
            kept = read_done_rows(output, tabular, delimiter)
            done = {int(r["row"]) for r in kept}
            jobs = [(n, row) for n, row in jobs if n not in done]
        if output is None:
            out = sys.stdout
        else:
            out = open(output, "w", newline="", encoding="utf-8")  # noqa: SIM115 - closed below
        writer = csv.DictWriter(
            out, fieldnames=fields, delimiter=delimiter, extrasaction="ignore"
        )
        if tabular:
            writer.writeheader()
            writer.writerows(kept)
        else:
            out.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in kept)

        def write(number, row, answer, error):
            p = answer.get("noul") if isinstance(answer, dict) else None
            if tabular:
                writer.writerow(
                    {
                        **row,
                        "row": number,
                        "answer": ""
                        if answer is None
                        else json.dumps(answer, ensure_ascii=False),
                        "p": "" if p is None else p,
                        "error": error or "",
                    }
                )
            else:
                record = {
                    **row,
                    "row": number,
                    "answer": answer,
                    "p": p,
                    "error": error,
                }
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
            out.flush()

        db = None
        if log:
            import sqlite_utils
            from llm.cli import logs_db_path
            from llm.migrations import migrate

            db = sqlite_utils.Database(logs_db_path())
            migrate(db)

        start = time.perf_counter()
        try:
            state = asyncio.run(
                run_batch(
                    model,
                    jobs,
                    question,
                    validated,
                    column,
                    concurrency,
                    max_cost,
                    write,
                    db,
                )
            )
        finally:
            if output is not None:
                out.close()
        if state["fatal"]:
            raise click.ClickException(state["fatal"])
        summary = (
            f"{state['rows']} rows, {state['errors']} errors, "
            f"{time.perf_counter() - start:.1f} seconds, {money(state['cost'])}"
        )
        if state["rows"]:
            summary += f" ({money(state['cost'] / state['rows'])} per row)"
        if kept:
            summary += f", {len(kept)} already done"
        click.echo(summary, err=True)
        if state["stopped"]:
            click.echo(state["stopped"], err=True)
