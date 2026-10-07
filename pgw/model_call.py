"""Calls to the one model under test. A service error stops the run instead of being scored (the deny-rule
re-run's Amendment 1), nothing is retried silently, and every raw reply is saved so scoring reruns offline.

No `fallbacks`: a fallback would answer with a different model. No sampling parameters: Sonnet 5.5 rejects
non-default values."""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import anthropic

from pgw.vault import TOKEN_RE


class ServiceStop(Exception):
    """The service failed to answer. Stop; a relaunch resumes at the next unfinished call."""


def make_client(**kwargs) -> anthropic.Anthropic:
    return anthropic.Anthropic(max_retries=0, **kwargs)


def ask(client, model: str, system: str, user: str, effort: str, max_tokens: int = 16000,
        output_format: dict | None = None) -> dict:
    output_config = {"effort": effort}
    if output_format is not None:
        output_config["format"] = output_format
    try:
        resp = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config=output_config,
        )
    except anthropic.APIError as e:
        raise ServiceStop(f"{type(e).__name__}: {e}") from e
    text = "".join(b.text for b in resp.content if b.type == "text")
    if resp.stop_reason == "end_turn" and not text.strip():
        raise ServiceStop("end_turn with no text: treated as a service error, not an answer")
    return {
        "request_id": resp._request_id,
        "model": resp.model,
        "stop_reason": resp.stop_reason,
        "text": text,
        "input_tokens": resp.usage.input_tokens,
        "output_tokens": resp.usage.output_tokens,
        "raw": resp.to_dict(),
    }


def read_records(out_path: Path) -> list[dict]:
    """All rows. A partial final line (an interrupted write) is moved to <name>.partial and cut from the
    record, so the evidence survives and the next append starts on a clean line; any other unreadable line
    still raises."""
    if not out_path.exists():
        return []
    data = out_path.read_bytes()
    if data and not data.endswith(b"\n"):
        cut = data.rfind(b"\n") + 1
        with out_path.with_name(out_path.name + ".partial").open("ab") as p:
            p.write(data[cut:] + b"\n")
        out_path.write_bytes(data[:cut])
        print(f"{out_path.name}: moved a partial final line ({len(data) - cut} bytes) to "
              f"{out_path.name}.partial; that call will be asked again", file=sys.stderr)
        data = data[:cut]
    return [json.loads(line) for line in data.decode("utf-8").splitlines() if line.strip()]


def _done(out_path: Path) -> set[tuple[str, int]]:
    return {(r["task_id"], r["repeat"]) for r in read_records(out_path)}


def run_calls(client, model: str, effort: str, system: str, jobs: list[tuple[str, int, str]], out_path: Path,
              output_format: dict | None = None) -> int:
    done = _done(out_path)
    new = 0
    with out_path.open("a", encoding="utf-8", newline="\n") as f:
        for task_id, repeat, user in jobs:
            if (task_id, repeat) in done:
                continue
            rec = ask(client, model, system, user, effort, output_format=output_format)
            rec.update(task_id=task_id, repeat=repeat, at=datetime.now(timezone.utc).isoformat(),
                       user_sha256=hashlib.sha256(user.encode("utf-8")).hexdigest())
            f.write(json.dumps(rec, sort_keys=True, ensure_ascii=False) + "\n")
            f.flush()
            new += 1
    return new


def canary(client, model: str) -> dict:
    """Spec §10.1 and §8: confirm the model ID resolves, and record what the API reports back."""
    info = client.models.retrieve(model)
    rec = ask(client, model, "Reply with exactly one word.", "Reply with the word READY.", "low", max_tokens=2000)
    return {
        "requested": model,
        "models_api_id": info.id,
        "display_name": getattr(info, "display_name", None),
        "reported_model": rec["model"],
        "stop_reason": rec["stop_reason"],
        "text": rec["text"],
        "request_id": rec["request_id"],
        "at": datetime.now(timezone.utc).isoformat(),
    }


class EchoClient:
    """No-network stand-in for plumbing runs: answers in the triage schema with the tokens it was sent."""

    def __init__(self) -> None:
        self.messages = self
        self.models = SimpleNamespace(retrieve=lambda model_id: SimpleNamespace(id=model_id, display_name="echo"))

    def create(self, **kwargs):
        sent = kwargs["messages"][0]["content"]
        toks = [m.group(0) for m in TOKEN_RE.finditer(sent)]
        cust = next((t for t in toks if t.startswith("[CUSTOMER_")), "")
        order = next((t for t in toks if t.startswith("[ORDER_")), "")
        text = json.dumps({"category": "complaint", "urgency": "normal", "order": order, "action": "escalate",
                           "reply": f"Dear {cust}, thank you for your email. An agent will reply shortly."})
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=text)], stop_reason="end_turn", model="echo",
            usage=SimpleNamespace(input_tokens=0, output_tokens=0), _request_id="echo",
            to_dict=lambda: {"echo": True})
