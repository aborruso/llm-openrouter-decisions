import json
import os

import httpx2
import llm
import pytest

import llm_openrouter_decisions as plugin

CATALOG = {"data": [{"id": "liquid/d1", "architecture": {"input_modalities": ["text"]}}]}


def cache_path():
    return llm.user_dir() / plugin.MODELS_CACHE


def test_fresh_cache_used_without_request(httpx2_mock):
    ids = [m["id"] for m in plugin.get_decision_models()]
    assert "typesafe/jev-1.14" in ids
    assert not httpx2_mock.get_requests()


def test_stale_cache_refreshed(httpx2_mock):
    os.utime(cache_path(), (0, 0))
    httpx2_mock.add_response(url=plugin.MODELS_URL, json=CATALOG)
    assert [m["id"] for m in plugin.get_decision_models()] == ["liquid/d1"]
    assert json.loads(cache_path().read_text()) == CATALOG


def test_download_failure_falls_back_to_stale_cache(httpx2_mock):
    os.utime(cache_path(), (0, 0))
    httpx2_mock.add_exception(httpx2.ConnectError("offline"))
    assert "typesafe/jev-1.14" in [m["id"] for m in plugin.get_decision_models()]


def test_download_failure_without_cache(httpx2_mock):
    cache_path().unlink()
    httpx2_mock.add_response(status_code=500)
    assert plugin.get_decision_models() == []
