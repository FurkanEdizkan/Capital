"""Local-model readiness — what's deployed (Ollama) and deployable (llmfit).

Two independent probes, combined into one cached snapshot:

- *Deployed*: the configured Ollama endpoint is asked for its version and
  installed models (`/api/version`, `/api/tags`).
- *Deployable*: the optional `llmfit` CLI (https://github.com/AlexsJones/llmfit)
  scans the host hardware and scores which models would run well. When the
  binary is missing the snapshot simply says so — it is never auto-installed.

Both probes are best-effort and never raise; the Settings page renders
whatever could be learned. Hardware scans are slow, so the snapshot is cached
in-process for a few minutes.
"""

import json
import logging
import subprocess
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field

import httpx
from sqlmodel import Session

from appsettings.store import get_llm_credentials

log = logging.getLogger("capital.ai.localfit")

DEFAULT_OLLAMA_URL = "http://localhost:11434"
LLMFIT_INSTALL_HINT = "uv tool install llmfit"

_CACHE_TTL_SECONDS = 300.0
_LLMFIT_TIMEOUT_SECONDS = 60

#: Injectable JSON-over-HTTP getter — returns the parsed body. Tests fake it.
JsonFetcher = Callable[[str], dict]

#: Injectable llmfit runner — returns the CLI's stdout. Tests fake it.
LlmfitRunner = Callable[[list[str]], str]


def _http_json(url: str) -> dict:
    resp = httpx.get(url, timeout=5.0)
    resp.raise_for_status()
    body = resp.json()
    return body if isinstance(body, dict) else {}


def _run_llmfit(args: list[str]) -> str:
    """Run the llmfit CLI. Raises FileNotFoundError when not installed."""
    result = subprocess.run(  # noqa: S603 — fixed argv, no shell
        ["llmfit", *args],
        capture_output=True,
        text=True,
        timeout=_LLMFIT_TIMEOUT_SECONDS,
        check=True,
    )
    return result.stdout


@dataclass
class OllamaModel:
    """One model installed on the Ollama endpoint."""

    name: str
    size_bytes: int = 0
    parameter_size: str = ""
    quantization: str = ""


@dataclass
class OllamaStatus:
    """Whether local models are already deployed and which ones."""

    reachable: bool = False
    base_url: str = DEFAULT_OLLAMA_URL
    version: str = ""
    models: list[OllamaModel] = field(default_factory=list)


@dataclass
class ModelFit:
    """One llmfit row — a model the host hardware could run."""

    model: str
    quantization: str = ""
    fit: str = ""  # Perfect | Good | Marginal | Too Tight (llmfit's classes)
    est_speed: str = ""
    memory_gb: str = ""


@dataclass
class LlmfitStatus:
    """Whether the hardware was scanned and what would fit."""

    installed: bool = False
    install_hint: str = LLMFIT_INSTALL_HINT
    hardware: dict = field(default_factory=dict)
    fits: list[ModelFit] = field(default_factory=list)
    error: str = ""


@dataclass
class LocalAISnapshot:
    """The combined local-model readiness picture."""

    ollama: OllamaStatus = field(default_factory=OllamaStatus)
    llmfit: LlmfitStatus = field(default_factory=LlmfitStatus)
    checked_at: float = 0.0

    def as_dict(self) -> dict:
        data = asdict(self)
        data.pop("checked_at")
        return data


def _ollama_base_url(session: Session) -> str:
    configured = get_llm_credentials(session, "ollama")["base_url"].strip()
    if not configured:
        return DEFAULT_OLLAMA_URL
    # The chat adapter stores an OpenAI-compatible URL (…/v1); the native
    # status endpoints live at the server root.
    return configured.removesuffix("/").removesuffix("/v1").removesuffix("/")


def probe_ollama(
    session: Session, *, fetch: JsonFetcher = _http_json
) -> OllamaStatus:
    """Ask the configured Ollama endpoint what is deployed."""
    base = _ollama_base_url(session)
    status = OllamaStatus(base_url=base)
    try:
        status.version = str(fetch(f"{base}/api/version").get("version", ""))
        status.reachable = True
    except Exception:  # noqa: BLE001 — unreachable is an answer, not an error
        return status
    try:
        tags = fetch(f"{base}/api/tags")
        for item in tags.get("models", []) or []:
            details = item.get("details") or {}
            status.models.append(
                OllamaModel(
                    name=str(item.get("name", "")),
                    size_bytes=int(item.get("size", 0) or 0),
                    parameter_size=str(details.get("parameter_size", "")),
                    quantization=str(details.get("quantization_level", "")),
                )
            )
    except Exception:  # noqa: BLE001 — version answered; tags are best-effort
        log.warning("ollama /api/tags failed", exc_info=True)
    return status


def _parse_fits(payload: object) -> tuple[dict, list[ModelFit]]:
    """Pull hardware + fit rows out of llmfit's JSON, tolerating shape drift."""
    if isinstance(payload, dict):
        hardware = payload.get("hardware") or payload.get("system") or {}
        rows = (
            payload.get("models")
            or payload.get("results")
            or payload.get("recommendations")
            or []
        )
    elif isinstance(payload, list):  # some subcommands emit a bare array
        hardware, rows = {}, payload
    else:
        return {}, []
    fits: list[ModelFit] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        fits.append(
            ModelFit(
                model=str(row.get("model") or row.get("name") or ""),
                quantization=str(row.get("quantization") or row.get("quant") or ""),
                fit=str(row.get("fit") or row.get("fit_class") or row.get("rating") or ""),
                est_speed=str(
                    row.get("est_speed")
                    or row.get("speed")
                    or row.get("tokens_per_second")
                    or ""
                ),
                memory_gb=str(row.get("memory_gb") or row.get("memory") or ""),
            )
        )
    return (hardware if isinstance(hardware, dict) else {}), fits


def probe_llmfit(*, run: LlmfitRunner = _run_llmfit) -> LlmfitStatus:
    """Scan the host with llmfit, if it is installed."""
    status = LlmfitStatus()
    for args in (["recommend", "--json"], ["fit", "--json"]):
        try:
            payload = json.loads(run(args))
        except FileNotFoundError:
            status.error = "llmfit is not installed"
            return status
        except Exception as exc:  # noqa: BLE001 — try the fallback subcommand
            status.error = str(exc)[:200]
            continue
        status.installed = True
        status.error = ""
        status.hardware, status.fits = _parse_fits(payload)
        return status
    # Both subcommands ran but failed — the binary exists.
    status.installed = True
    return status


_cached: LocalAISnapshot | None = None


def snapshot(
    session: Session,
    *,
    force: bool = False,
    fetch: JsonFetcher = _http_json,
    run: LlmfitRunner = _run_llmfit,
) -> LocalAISnapshot:
    """The cached local-AI readiness snapshot (refreshed every ~5 minutes)."""
    global _cached
    now = time.monotonic()
    if not force and _cached is not None and now - _cached.checked_at < _CACHE_TTL_SECONDS:
        return _cached
    _cached = LocalAISnapshot(
        ollama=probe_ollama(session, fetch=fetch),
        llmfit=probe_llmfit(run=run),
        checked_at=now,
    )
    return _cached
