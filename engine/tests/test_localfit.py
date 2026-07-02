"""Tests for local-model readiness — Ollama probe, llmfit parse, API."""

import json

from fastapi.testclient import TestClient
from sqlmodel import Session

from ai import localfit
from appsettings.store import set_llm_credentials
from tests.conftest import ADMIN_PASSWORD, login

_TAGS = {
    "models": [
        {
            "name": "llama3:8b",
            "size": 4_700_000_000,
            "details": {"parameter_size": "8B", "quantization_level": "Q4_0"},
        }
    ]
}

_LLMFIT = {
    "hardware": {"ram_gb": 32, "cpu_cores": 12, "gpus": [], "backend": "cpu"},
    "models": [
        {"model": "llama3:8b", "quantization": "Q4_K_M", "fit": "Good", "est_speed": "12 tok/s"},
        {"model": "qwen2:72b", "quantization": "Q4_K_M", "fit": "Too Tight"},
    ],
}


def _fetch_ok(url: str) -> dict:
    if url.endswith("/api/version"):
        return {"version": "0.5.1"}
    if url.endswith("/api/tags"):
        return _TAGS
    raise AssertionError(f"unexpected URL {url}")


def test_probe_ollama_reads_version_and_models(session: Session) -> None:
    status = localfit.probe_ollama(session, fetch=_fetch_ok)
    assert status.reachable
    assert status.version == "0.5.1"
    assert status.base_url == localfit.DEFAULT_OLLAMA_URL
    (model,) = status.models
    assert model.name == "llama3:8b"
    assert model.parameter_size == "8B"


def test_probe_ollama_unreachable_is_an_answer(session: Session) -> None:
    def down(_url: str) -> dict:
        raise ConnectionError("refused")

    status = localfit.probe_ollama(session, fetch=down)
    assert not status.reachable
    assert status.models == []


def test_probe_ollama_strips_openai_suffix_from_base_url(
    session: Session,
) -> None:
    set_llm_credentials(
        session, "ollama", base_url="http://host.docker.internal:11434/v1"
    )
    seen: list[str] = []

    def spy(url: str) -> dict:
        seen.append(url)
        return {"version": "x"} if url.endswith("version") else {"models": []}

    localfit.probe_ollama(session, fetch=spy)
    assert seen[0] == "http://host.docker.internal:11434/api/version"


def test_probe_llmfit_parses_fits() -> None:
    status = localfit.probe_llmfit(run=lambda args: json.dumps(_LLMFIT))
    assert status.installed
    assert status.hardware["ram_gb"] == 32
    assert [f.fit for f in status.fits] == ["Good", "Too Tight"]


def test_probe_llmfit_missing_binary() -> None:
    def missing(_args: list[str]) -> str:
        raise FileNotFoundError("llmfit")

    status = localfit.probe_llmfit(run=missing)
    assert not status.installed
    assert status.install_hint == localfit.LLMFIT_INSTALL_HINT


def test_probe_llmfit_falls_back_to_fit_subcommand() -> None:
    def first_fails(args: list[str]) -> str:
        if args[0] == "recommend":
            raise RuntimeError("unknown subcommand")
        return json.dumps(_LLMFIT)

    status = localfit.probe_llmfit(run=first_fails)
    assert status.installed
    assert len(status.fits) == 2


def test_local_api_combines_probes(client: TestClient, session: Session) -> None:
    localfit._cached = None  # isolate from other tests' cache
    localfit.snapshot(session, force=True, fetch=_fetch_ok, run=lambda a: json.dumps(_LLMFIT))
    headers = {"Authorization": f"Bearer {login(client, 'admin', ADMIN_PASSWORD)}"}
    body = client.get("/api/ai/local", headers=headers).json()
    assert body["ollama"]["reachable"] is True
    assert body["ollama"]["models"][0]["name"] == "llama3:8b"
    assert body["llmfit"]["installed"] is True
    assert body["llmfit"]["fits"][0]["fit"] == "Good"
    localfit._cached = None
