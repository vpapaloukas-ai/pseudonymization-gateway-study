"""Runner.

  python -m pgw.run generate --batch dev|test --out DIR --writer fake|live [--dev | --frozen FROZEN.json]
  python -m pgw.run run --batch DIR --out DIR --model-stage skip|fake|live|replay [--dev | --frozen FROZEN.json]
  python -m pgw.run canary --model ID

`replay` re-scores a replies.jsonl copied into --out, with no calls; replies bound to another message refuse.
`fake` uses no network. `live` spends money: it needs --dev or --frozen and the operator's go (plan Task 13).
A scored (--frozen) step never uses fake artefacts: it refuses `--writer fake` and `--model-stage fake`, and a
scored run refuses any batch that is not a test batch written live under a frozen generate."""
import argparse
import dataclasses
import hashlib
import json
import random
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from pgw import audit, briefs, draftcheck, emailgen, exitcheck, manifest, model_call, pipeline, prompts, score
from pgw.briefs import Brief, Plant
from pgw.crm import CRM_SEED, DEV_PIDS, TEST_PIDS, build_crm

MODEL_ID = "claude-sonnet-5-5"
EFFORT = "high"
TEST_SEED: int | None = 20261006    # set in Task 14 to the pre-registration's commit date, YYYYMMDD (spec §6)
BATCHES = {"dev": {"seed": 1, "n": 100, "pids": DEV_PIDS},
           "test": {"seed": None, "n": 300, "pids": TEST_PIDS}}
REPEAT_SUBSET, REPEATS, REPEAT_SEED = 50, 3, 7
SAMPLE_SIZE, SAMPLE_SEED = 10, 11
BATCH_FILES = ("crm.json", "briefs.jsonl", "generation.jsonl", "audit.jsonl", "emails.jsonl", "gold.jsonl")


def _default(o):
    if isinstance(o, date):
        return o.isoformat()
    raise TypeError(type(o))


def _jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True, ensure_ascii=False, default=_default) + "\n")


def _read(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _brief(d: dict) -> Brief:
    return Brief(**{**d, "plants": tuple(Plant(**{**p, "parts": tuple(p["parts"])}) for p in d["plants"])})


def repeat_subset(ids: list[str]) -> list[str]:
    return sorted(random.Random(REPEAT_SEED).sample(sorted(ids), min(REPEAT_SUBSET, len(ids))))


def sample_ids(ids: list[str]) -> list[str]:
    return sorted(random.Random(SAMPLE_SEED).sample(sorted(ids), min(SAMPLE_SIZE, len(ids))))


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def generate_batch(out: Path, name: str, client, n: int | None = None, dev: bool = False,
                   frozen: bool = False, writer: str = "fake") -> int:
    spec = dict(BATCHES[name], seed=TEST_SEED if name == "test" else BATCHES[name]["seed"])
    if spec["seed"] is None:
        print("REFUSING: the test seed is set only when the pre-registration is committed (Task 14)", file=sys.stderr)
        return 2
    if (out / "emails.jsonl").exists():
        print(f"REFUSING: {out} already holds a generated batch; a batch is generated once", file=sys.stderr)
        return 5
    out.mkdir(parents=True, exist_ok=True)
    crm = build_crm(CRM_SEED)
    by_pid = {c.pid: c for c in crm}
    bs = briefs.build_briefs(crm, spec["seed"], n or spec["n"], spec["pids"], name)
    stamp = _stamp()
    fields = {"batch": name, "seed": spec["seed"], "n": len(bs), "generator": emailgen.GEN_MODEL, "dev": dev,
              "frozen": bool(frozen), "writer": writer}
    manifest.write_manifest(out / f"manifest.generate-start-{stamp}.json", **fields)
    (out / "crm.json").write_text(json.dumps([dataclasses.asdict(c) for c in crm], default=_default, indent=1) + "\n",
                                  encoding="utf-8", newline="\n")
    _jsonl(out / "briefs.jsonl", [dataclasses.asdict(b) for b in bs])
    emailgen.generate(client, bs, by_pid, out / "generation.jsonl")
    acc = emailgen.accepted(out / "generation.jsonl")
    emails = [{"email_id": b.email_id, "sender": b.sender, "text": emailgen.email_text(acc[b.email_id])}
              for b in bs if b.email_id in acc]
    model_call.run_calls(client, emailgen.GEN_MODEL, audit.AUDIT_EFFORT, audit.AUDIT_SYSTEM,
                         [(e["email_id"], 0, e["text"]) for e in emails], out / "audit.jsonl",
                         output_format=audit.AUDIT_SCHEMA)
    audits = {r["task_id"]: r for r in model_call.read_records(out / "audit.jsonl")}
    gold = []
    for b in bs:
        if b.email_id not in acc:
            continue
        a = audits[b.email_id]
        items = json.loads(a["text"])["items"] if a["stop_reason"] == "end_turn" else []
        text = next(e["text"] for e in emails if e["email_id"] == b.email_id)
        gold.append({"email_id": b.email_id, "audit_stop": a["stop_reason"],
                     "items": [dataclasses.asdict(g) for g in audit.build_gold(b, text, items, by_pid[b.pid])]})
    _jsonl(out / "emails.jsonl", emails)
    _jsonl(out / "gold.jsonl", gold)
    meta = {"batch": name, "seed": spec["seed"], "emails": len(emails), "generation": emailgen.stats(out / "generation.jsonl"),
            "sha256": {f: _sha(out / f) for f in BATCH_FILES}, "writer": writer}
    (out / "batch.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    manifest.write_manifest(out / f"manifest.generate-end-{stamp}.json", **fields)
    return 0


def _batch_ok(batch_dir: Path) -> str | None:
    try:
        meta = json.loads((batch_dir / "batch.json").read_text(encoding="utf-8"))
        bad = [f for f in BATCH_FILES if _sha(batch_dir / f) != meta["sha256"][f]]
        crm_now = json.dumps([dataclasses.asdict(c) for c in build_crm(CRM_SEED)], default=_default, indent=1) + "\n"
        if (batch_dir / "crm.json").read_text(encoding="utf-8") != crm_now:
            bad.append("crm.json (does not regenerate from CRM_SEED)")
    except (OSError, json.JSONDecodeError, KeyError) as e:
        return f"unreadable or incomplete ({type(e).__name__}: {e})"
    return ", ".join(bad) or None


def _not_scorable(batch_dir: Path) -> str | None:
    """A scored run reads only a test batch written live under a frozen generate, by the generator model."""
    meta = json.loads((batch_dir / "batch.json").read_text(encoding="utf-8"))
    if meta.get("batch") != "test":
        return f"is a {meta.get('batch')!r} batch, not 'test'"
    if meta.get("writer") != "live":
        return f"was written by {meta.get('writer')!r}, not 'live'"
    starts = [json.loads(p.read_text(encoding="utf-8")) for p in batch_dir.glob("manifest.generate-start-*.json")]
    if not any(m.get("frozen") is True for m in starts):
        return "has no generate-start manifest with frozen true"
    models = sorted({str(r.get("model")) for r in _read(batch_dir / "generation.jsonl")})
    foreign = [m for m in models if not m.startswith(emailgen.GEN_MODEL)]
    if foreign:
        return f"has generation rows from {foreign}, not {emailgen.GEN_MODEL}"
    return None


def _out_conflict(out: Path, dev: bool, frozen: bool, model_stage: str) -> tuple[int, str] | None:
    starts = [json.loads(p.read_text(encoding="utf-8")) for p in out.glob("manifest.start-*.json")]
    has_replies = (out / "replies.jsonl").exists()
    if frozen and (any(m.get("dev") or not m.get("frozen") for m in starts)
                   or (has_replies and not any(m.get("frozen") for m in starts))):
        return 5, f"{out} holds a non-frozen run or replies with no frozen run; a scored run needs a fresh directory"
    rows = model_call.read_records(out / "replies.jsonl") if has_replies else []
    models = {r["model"] for r in rows}
    if model_stage != "skip":
        keys = [(r["task_id"], r["repeat"]) for r in rows]
        if len(keys) != len(set(keys)):
            return 4, f"{out / 'replies.jsonl'} holds duplicate (task_id, repeat) rows"
    where = f"{out / 'replies.jsonl'} holds replies from another model stage: {sorted(models)}"
    if model_stage == "live" and any(not m.startswith(MODEL_ID) for m in models):
        return 4, where
    if model_stage == "fake" and models - {"echo"}:
        return 4, where
    if model_stage == "replay" and (len(models) > 1 or (frozen and any(not m.startswith(MODEL_ID) for m in models))):
        return 4, where
    return None


def run_batch(batch_dir: Path, out: Path, model_stage: str, client, detector, shipped,
              dev: bool = False, frozen: bool = False) -> int:
    bad = _batch_ok(batch_dir)
    if bad:
        print(f"REFUSING: batch {batch_dir} fails its hashes: {bad}", file=sys.stderr)
        return 6
    out.mkdir(parents=True, exist_ok=True)
    conflict = _out_conflict(out, dev, frozen, model_stage)
    if conflict:
        print(f"REFUSING: {conflict[1]}", file=sys.stderr)
        return conflict[0]
    if frozen:
        why = _not_scorable(batch_dir)
        if why:
            print(f"REFUSING: a scored run needs a live, frozen test batch; {batch_dir} {why}", file=sys.stderr)
            return 6
    exitcheck.control()
    score.control()
    draftcheck.control()
    crm = build_crm(CRM_SEED)
    by_email, by_pid = {c.email: c for c in crm}, {c.pid: c for c in crm}
    bs = {b["email_id"]: _brief(b) for b in _read(batch_dir / "briefs.jsonl")}
    emails = _read(batch_dir / "emails.jsonl")
    gold = {g["email_id"]: [audit.GoldItem(**{**i, "parts": tuple(i["parts"])}) for i in g["items"]]
            for g in _read(batch_dir / "gold.jsonl")}
    stamp = _stamp()
    batch_meta = json.loads((batch_dir / "batch.json").read_text(encoding="utf-8"))
    fields = {"batch": str(batch_dir), "model": MODEL_ID, "effort": EFFORT, "model_stage": model_stage,
              "dev": dev, "frozen": frozen, "batch_sha256": batch_meta["sha256"]}
    manifest.write_manifest(out / f"manifest.start-{stamp}.json", **fields)
    outs = {e["email_id"]: pipeline.outbound(e["email_id"], e["sender"], e["text"], by_email, detector) for e in emails}
    contrasts = {e["email_id"]: pipeline.contrast(e["text"], shipped) for e in emails}
    _jsonl(out / "outbound.jsonl", [dataclasses.asdict(o) for o in outs.values()])
    _jsonl(out / "contrast.jsonl", [{"email_id": k, "payload": v} for k, v in contrasts.items()])
    replies: list[dict] = []
    inbs: dict[tuple[str, int], pipeline.Inbound] = {}
    if model_stage == "replay" and not (out / "replies.jsonl").exists():
        print(f"REFUSING: replay needs {out / 'replies.jsonl'} copied in from an earlier run", file=sys.stderr)
        return 4
    sendable = [o for o in outs.values() if o.message and not o.held]
    subset = set(repeat_subset([o.email_id for o in sendable]))
    expected = {(o.email_id, r) for o in sendable for r in range(REPEATS if o.email_id in subset else 1)}
    if model_stage != "skip":
        by_id = {o.email_id: o for o in sendable}
        existing = model_call.read_records(out / "replies.jsonl")
        for rep in existing:
            o = by_id.get(rep["task_id"])
            if o is None or rep["user_sha256"] != hashlib.sha256(o.message.encode("utf-8")).hexdigest():
                print(f"REFUSING: reply {rep['task_id']}/{rep['repeat']} on file is not bound to a sendable "
                      "message of this run", file=sys.stderr)
                return 4
        if model_stage == "replay" and {(r["task_id"], r["repeat"]) for r in existing} != expected:
            print("REFUSING: the replies on file are not exactly the jobs this batch needs", file=sys.stderr)
            return 4
    if model_stage in ("fake", "live"):
        if model_stage == "live":
            c = model_call.canary(client, MODEL_ID)
            (out / f"canary-{stamp}.json").write_text(json.dumps(c, indent=2) + "\n", encoding="utf-8", newline="\n")
            if c["models_api_id"] != MODEL_ID:
                print(f"REFUSING: the API resolved {MODEL_ID} as {c['models_api_id']}", file=sys.stderr)
                return 3
        jobs = [(o.email_id, r, o.message) for o in sendable for r in range(REPEATS if o.email_id in subset else 1)]
        model_call.run_calls(client, MODEL_ID, EFFORT, prompts.SYSTEM_PROMPT, jobs, out / "replies.jsonl",
                             output_format=prompts.TRIAGE_SCHEMA)
    if model_stage != "skip":
        replies = model_call.read_records(out / "replies.jsonl")
        for rep in replies:
            o = outs[rep["task_id"]]
            if rep["user_sha256"] != hashlib.sha256(o.message.encode("utf-8")).hexdigest():
                print(f"REFUSING: reply {rep['task_id']}/{rep['repeat']} was asked about a different message",
                      file=sys.stderr)
                return 4
            inbs[(rep["task_id"], rep["repeat"])] = pipeline.inbound(rep["task_id"], rep["repeat"], rep, o.vault)
        _jsonl(out / "inbound.jsonl", [dataclasses.asdict(i) for i in inbs.values()])
    rows, variation = [], []
    for e in emails:
        b = bs[e["email_id"]]
        row = score.score_email(b, gold[b.email_id], by_pid[b.pid], outs[b.email_id], inbs.get((b.email_id, 0)),
                                contrasts[b.email_id])
        rows.append(row)
        for (eid, r), inb in inbs.items():
            if eid == b.email_id and len([k for k in inbs if k[0] == eid]) > 1:
                variation.append(score.score_email(b, gold[eid], by_pid[b.pid], outs[eid], inb, contrasts[eid]) | {"repeat": r})
    _jsonl(out / "scores.jsonl", rows)
    gen_stats = json.loads((batch_dir / "batch.json").read_text(encoding="utf-8"))["generation"]
    summary = score.summarise(rows, variation, gen_stats, replies) | {
        "sample_ids": sample_ids([r["email_id"] for r in rows if r["handled"]])}   # published replies: handled, repeat 0
    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    manifest.write_manifest(out / f"manifest.end-{stamp}.json", **fields)
    return 0


def _frozen_ok(path: Path | None) -> bool:
    if path is None:
        return True
    try:
        bad = manifest.check_frozen(path)
    except (ValueError, OSError) as e:
        print(f"REFUSING: {e}", file=sys.stderr)
        return False
    if bad:
        print("REFUSING: code or dependencies differ from the freeze record: " + ", ".join(bad), file=sys.stderr)
    return not bad


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pgw.run")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--batch", choices=("dev", "test"), required=True)
    g.add_argument("--out", type=Path, required=True)
    g.add_argument("--writer", choices=("fake", "live"), required=True)
    r = sub.add_parser("run")
    r.add_argument("--batch", type=Path, required=True)
    r.add_argument("--out", type=Path, required=True)
    r.add_argument("--model-stage", choices=("skip", "fake", "live", "replay"), default="skip")
    for p in (g, r):
        p.add_argument("--frozen", type=Path)
        p.add_argument("--dev", action="store_true")
    c = sub.add_parser("canary")
    c.add_argument("--model", required=True)
    a = ap.parse_args(argv)

    if a.cmd == "canary":
        print(json.dumps(model_call.canary(model_call.make_client(), a.model), indent=2))
        return 0
    live = (a.cmd == "generate" and a.writer == "live") or (a.cmd == "run" and a.model_stage == "live")
    if live and not a.frozen and not a.dev:
        print("REFUSING: a live step needs --frozen (scored) or --dev (development)", file=sys.stderr)
        return 2
    fake = (a.cmd == "generate" and a.writer == "fake") or (a.cmd == "run" and a.model_stage == "fake")
    if fake and a.frozen:
        print("REFUSING: a scored (--frozen) step never uses the fake writer or the fake model stage", file=sys.stderr)
        return 2
    if not _frozen_ok(a.frozen):
        return 2
    if a.dev and a.frozen:
        print("REFUSING: --dev and --frozen together", file=sys.stderr)
        return 2
    if a.cmd == "generate":
        if a.batch == "test" and TEST_SEED is None:
            print("REFUSING: the test seed is set only when the pre-registration is committed", file=sys.stderr)
            return 2
        if (a.out / "emails.jsonl").exists():
            print(f"REFUSING: {a.out} already holds a generated batch; a batch is generated once", file=sys.stderr)
            return 5
        client = model_call.make_client() if a.writer == "live" else emailgen.FakeWriter()
        if a.writer == "live":
            cn = model_call.canary(client, emailgen.GEN_MODEL)
            a.out.mkdir(parents=True, exist_ok=True)
            (a.out / f"canary-{_stamp()}.json").write_text(json.dumps(cn, indent=2) + "\n", encoding="utf-8", newline="\n")
            if cn["models_api_id"] != emailgen.GEN_MODEL:
                print(f"REFUSING: the API resolved {emailgen.GEN_MODEL} as {cn['models_api_id']}", file=sys.stderr)
                return 3
        return generate_batch(a.out, a.batch, client, dev=a.dev, frozen=bool(a.frozen), writer=a.writer)
    from pgw.baseline import ShippedGateway   # loads spaCy; imported here so refusals stay fast
    from pgw.detector import ConfiguredDetector

    shipped = ShippedGateway()
    detector = ConfiguredDetector(nlp_engine=shipped.analyzer.nlp_engine)
    client = (model_call.make_client() if a.model_stage == "live"
              else model_call.EchoClient() if a.model_stage == "fake" else None)
    return run_batch(a.batch, a.out, a.model_stage, client, detector, shipped, dev=a.dev, frozen=bool(a.frozen))


if __name__ == "__main__":
    sys.exit(main())
