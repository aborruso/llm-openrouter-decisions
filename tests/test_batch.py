import csv
import io
import json

import httpx2
import pytest
from click.testing import CliRunner
from llm.cli import cli
from test_openrouter_decisions import ANSWERS, MODEL, URL, payload

import llm_openrouter_decisions

QUESTION = "Is it about government transparency?"


@pytest.fixture(autouse=True)
def no_retry_delay(monkeypatch):
    monkeypatch.setattr(llm_openrouter_decisions, "RETRY_DELAYS", (0, 0, 0))


def answer_by_state(request):
    """Echo back an answer; the state text decides the HTTP status."""
    state = json.loads(request.content)["state"]
    for word, status in [("unauthorized", 401), ("nocredit", 402), ("broken", 500)]:
        if state == word:
            return httpx2.Response(status, json={"error": {"message": word}})
    return httpx2.Response(200, json=payload())


def batch(*args, input=None):
    return CliRunner().invoke(
        cli, ["openrouter-decisions", "batch", *args], input=input
    )


def write_csv(path, rows):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path):
    return list(csv.DictReader(open(path, newline="")))


TITLES = [
    {"title": "Transparency in local government", "doi": "10.1/a"},
    {"title": "Optical transparency of films", "doi": "10.1/b"},
    {"title": "Open budgets in municipalities", "doi": "10.1/c"},
]


def test_csv_column(tmp_path, httpx2_mock):
    httpx2_mock.add_callback(answer_by_state, url=URL, is_reusable=True)
    write_csv(tmp_path / "in.csv", TITLES)
    out = tmp_path / "out.csv"
    result = batch(
        str(tmp_path / "in.csv"),
        "-m",
        MODEL,
        "-s",
        QUESTION,
        "--column",
        "title",
        "--output",
        str(out),
    )
    assert result.exit_code == 0, result.output
    rows = read_csv(out)
    assert list(rows[0]) == ["title", "doi", "row", "answer", "p", "error"]
    assert sorted(r["row"] for r in rows) == ["1", "2", "3"]
    for r in rows:
        assert json.loads(r["answer"]) == ANSWERS["noul"]
        assert r["p"] == "0.8" and r["error"] == ""
    sent = sorted(json.loads(q.content)["state"] for q in httpx2_mock.get_requests())
    assert sent == sorted(t["title"] for t in TITLES)
    assert all(
        json.loads(q.content)["questions"]["evaluation"]["instructions"] == QUESTION
        for q in httpx2_mock.get_requests()
    )
    assert "3 rows, 0 errors" in result.stderr
    assert "$0.0000036" in result.stderr


def test_jsonl_whole_row_to_stdout(httpx2_mock):
    httpx2_mock.add_callback(answer_by_state, url=URL, is_reusable=True)
    lines = "\n".join(json.dumps({"id": i, "text": f"report {i}"}) for i in (1, 2))
    result = batch("-", "-m", MODEL, "-s", QUESTION, "--format", "nl", input=lines)
    assert result.exit_code == 0, result.output
    out = [json.loads(line) for line in result.stdout.splitlines()]
    assert sorted(o["row"] for o in out) == [1, 2]
    assert all(o["answer"] == ANSWERS["noul"] and o["p"] == 0.8 for o in out)
    states = [json.loads(q.content)["state"] for q in httpx2_mock.get_requests()]
    assert sorted(s["id"] for s in states) == [1, 2]


def test_model_options(tmp_path, httpx2_mock):
    httpx2_mock.add_response(url=URL, json=payload("choice"), is_reusable=True)
    write_csv(tmp_path / "in.csv", TITLES[:1])
    result = batch(
        str(tmp_path / "in.csv"),
        "-m",
        MODEL,
        "-s",
        "Which topic?",
        "--column",
        "title",
        "-o",
        "answer_type",
        "choice",
        "-o",
        "criteria",
        '{"billing": null, "other": null}',
    )
    assert result.exit_code == 0, result.output
    row = next(csv.DictReader(io.StringIO(result.stdout)))
    assert json.loads(row["answer"])["choice"] == "billing"
    assert row["p"] == ""
    question = json.loads(httpx2_mock.get_requests()[0].content)["questions"][
        "evaluation"
    ]
    assert question["type"] == "choice"


def test_invalid_option(tmp_path):
    write_csv(tmp_path / "in.csv", TITLES[:1])
    result = batch(
        str(tmp_path / "in.csv"), "-m", MODEL, "-s", "Q", "-o", "answer_type", "nope"
    )
    assert result.exit_code != 0
    assert "answer_type" in result.output


def test_row_errors_do_not_stop_the_batch(tmp_path, httpx2_mock):
    httpx2_mock.add_callback(answer_by_state, url=URL, is_reusable=True)
    write_csv(
        tmp_path / "in.csv", [{"title": "ok"}, {"title": ""}, {"title": "broken"}]
    )
    out = tmp_path / "out.csv"
    result = batch(
        str(tmp_path / "in.csv"),
        "-m",
        MODEL,
        "-s",
        QUESTION,
        "--column",
        "title",
        "--output",
        str(out),
    )
    assert result.exit_code == 0, result.output
    rows = {r["row"]: r for r in read_csv(out)}
    assert rows["1"]["error"] == "" and rows["1"]["p"] == "0.8"
    assert "Supply input data" in rows["2"]["error"]
    assert "500" in rows["3"]["error"] and rows["3"]["answer"] == ""
    # The 500 is retried three times after the first attempt
    assert len(httpx2_mock.get_requests()) == 5
    assert "3 rows, 2 errors" in result.stderr


def test_retry_after_429(tmp_path, httpx2_mock):
    httpx2_mock.add_response(
        url=URL, status_code=429, json={"error": {"message": "slow down"}}
    )
    httpx2_mock.add_response(url=URL, json=payload())
    write_csv(tmp_path / "in.csv", TITLES[:1])
    result = batch(
        str(tmp_path / "in.csv"), "-m", MODEL, "-s", QUESTION, "--column", "title"
    )
    assert result.exit_code == 0, result.output
    row = next(csv.DictReader(io.StringIO(result.stdout)))
    assert row["p"] == "0.8" and row["error"] == ""
    assert len(httpx2_mock.get_requests()) == 2


@pytest.mark.parametrize("word,status", [("unauthorized", 401), ("nocredit", 402)])
def test_stop_on_key_or_credit_error(tmp_path, word, status, httpx2_mock):
    httpx2_mock.add_callback(answer_by_state, url=URL, is_reusable=True)
    write_csv(tmp_path / "in.csv", [{"title": word}] + [{"title": "ok"}] * 5)
    result = batch(
        str(tmp_path / "in.csv"),
        "-m",
        MODEL,
        "-s",
        QUESTION,
        "--column",
        "title",
        "--concurrency",
        "1",
    )
    assert result.exit_code != 0
    assert f"HTTP {status}" in result.output
    assert len(httpx2_mock.get_requests()) == 1


def test_max_cost(tmp_path, httpx2_mock):
    # Each response costs $0.0000012
    httpx2_mock.add_callback(answer_by_state, url=URL, is_reusable=True)
    write_csv(tmp_path / "in.csv", [{"title": f"t{i}"} for i in range(5)])
    result = batch(
        str(tmp_path / "in.csv"),
        "-m",
        MODEL,
        "-s",
        QUESTION,
        "--column",
        "title",
        "--concurrency",
        "1",
        "--max-cost",
        "0.000002",
    )
    assert result.exit_code == 0, result.output
    assert len(list(csv.DictReader(io.StringIO(result.stdout)))) == 2
    assert len(httpx2_mock.get_requests()) == 2
    assert "--max-cost" in result.stderr


def test_limit(tmp_path, httpx2_mock):
    httpx2_mock.add_callback(answer_by_state, url=URL, is_reusable=True)
    write_csv(tmp_path / "in.csv", [{"title": f"t{i}"} for i in range(5)])
    result = batch(
        str(tmp_path / "in.csv"),
        "-m",
        MODEL,
        "-s",
        QUESTION,
        "--column",
        "title",
        "--limit",
        "2",
    )
    assert result.exit_code == 0, result.output
    assert len(httpx2_mock.get_requests()) == 2
    assert "2 rows" in result.stderr and "per row" in result.stderr


def test_resume_skips_done_rows_and_drops_truncated_line(tmp_path, httpx2_mock):
    httpx2_mock.add_callback(answer_by_state, url=URL, is_reusable=True)
    write_csv(tmp_path / "in.csv", TITLES)
    out = tmp_path / "out.csv"
    answer = json.dumps(ANSWERS["noul"]).replace('"', '""')
    out.write_text(
        "title,doi,row,answer,p,error\r\n"
        f'Transparency in local government,10.1/a,1,"{answer}",0.8,\r\n'
        "Optical transparency of films,10.1/b,2,,,HTTP 500\r\n"
        "Open budgets in municip"
    )
    result = batch(
        str(tmp_path / "in.csv"),
        "-m",
        MODEL,
        "-s",
        QUESTION,
        "--column",
        "title",
        "--output",
        str(out),
        "--resume",
    )
    assert result.exit_code == 0, result.output
    rows = read_csv(out)
    assert sorted(r["row"] for r in rows) == ["1", "2", "3"]
    assert all(r["error"] == "" for r in rows)
    sent = sorted(json.loads(q.content)["state"] for q in httpx2_mock.get_requests())
    assert sent == ["Open budgets in municipalities", "Optical transparency of films"]
    assert "1 already done" in result.stderr


def test_resume_needs_output(tmp_path):
    write_csv(tmp_path / "in.csv", TITLES)
    result = batch(str(tmp_path / "in.csv"), "-m", MODEL, "-s", QUESTION, "--resume")
    assert result.exit_code != 0
    assert "--output" in result.output


def test_no_question(tmp_path, httpx2_mock):
    write_csv(tmp_path / "in.csv", TITLES)
    result = batch(str(tmp_path / "in.csv"), "-m", MODEL, "--column", "title")
    assert result.exit_code != 0
    assert "Supply a question" in result.output
    assert not httpx2_mock.get_requests()


def test_no_key(tmp_path, monkeypatch, httpx2_mock):
    monkeypatch.delenv("OPENROUTER_KEY")
    write_csv(tmp_path / "in.csv", TITLES)
    result = batch(str(tmp_path / "in.csv"), "-m", MODEL, "-s", QUESTION)
    assert result.exit_code != 0
    assert "llm keys set openrouter" in result.output
    assert not httpx2_mock.get_requests()


@pytest.mark.parametrize("log", [False, True])
def test_logging_only_with_flag(tmp_path, log, httpx2_mock):
    httpx2_mock.add_callback(answer_by_state, url=URL, is_reusable=True)
    write_csv(tmp_path / "in.csv", TITLES)
    args = [str(tmp_path / "in.csv"), "-m", MODEL, "-s", QUESTION, "--column", "title"]
    result = batch(*args, *(["--log"] if log else []))
    assert result.exit_code == 0, result.output
    if not log:
        assert not (llm_openrouter_decisions.llm.user_dir() / "logs.db").exists()
        return
    logs = CliRunner().invoke(cli, ["logs", "--json", "-n", "0"])
    assert logs.exit_code == 0, logs.output
    assert len(json.loads(logs.stdout)) == 3
