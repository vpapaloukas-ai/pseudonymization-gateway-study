import json

import pytest
from helpers import FakeDetector

from pgw import emailgen, manifest, run
from pgw.emailgen import FakeWriter
from pgw.model_call import EchoClient


def batch(tmp_path, n=6):
    out = tmp_path / "batch"
    run.generate_batch(out, "dev", FakeWriter(), n=n)
    return out


def test_live_needs_a_flag(tmp_path):
    assert run.main(["generate", "--batch", "dev", "--out", str(tmp_path / "b"), "--writer", "live"]) == 2
    assert run.main(["run", "--batch", str(tmp_path), "--out", str(tmp_path / "o"), "--model-stage", "live"]) == 2


def test_test_seed_is_the_preregistration_date():
    assert isinstance(run.TEST_SEED, int) and 20261005 <= run.TEST_SEED <= 20271231


def test_a_malformed_freeze_record_refuses(tmp_path):
    bad = tmp_path / "FROZEN.json"
    bad.write_text("{}", encoding="utf-8")
    assert run.main(["run", "--batch", str(tmp_path), "--out", str(tmp_path / "o"), "--model-stage", "skip",
                     "--frozen", str(bad)]) == 2


def test_a_batch_is_generated_once(tmp_path):
    out = batch(tmp_path)
    assert run.generate_batch(out, "dev", FakeWriter(), n=6) == 5


def test_batch_files_and_hashes(tmp_path):
    out = batch(tmp_path)
    meta = json.loads((out / "batch.json").read_text(encoding="utf-8"))
    assert meta["emails"] == 6 and set(meta["sha256"]) == {
        "crm.json", "briefs.jsonl", "generation.jsonl", "audit.jsonl", "emails.jsonl", "gold.jsonl"}


def test_an_edited_batch_refuses(tmp_path):
    out = batch(tmp_path)
    with (out / "emails.jsonl").open("a", encoding="utf-8") as f:
        f.write("\n")
    assert run.run_batch(out, tmp_path / "o", "skip", None, FakeDetector([]), FakeDetector([])) == 6


def test_offline_run_is_deterministic_and_complete(tmp_path):
    out = batch(tmp_path)
    for o in ("o1", "o2"):
        assert run.run_batch(out, tmp_path / o, "fake", EchoClient(), FakeDetector([]), FakeDetector([])) == 0
    a = (tmp_path / "o1" / "outbound.jsonl").read_bytes()
    assert a == (tmp_path / "o2" / "outbound.jsonl").read_bytes()
    s = json.loads((tmp_path / "o1" / "summary.json").read_text(encoding="utf-8"))
    assert s["n_emails"] == 6 and "value.handled" in s and s["generation"]["accepted"] == 6


def test_a_frozen_run_refuses_a_dev_directory(tmp_path):
    out = batch(tmp_path)
    o = tmp_path / "o"
    assert run.run_batch(out, o, "fake", EchoClient(), FakeDetector([]), FakeDetector([]), dev=True) == 0
    assert run.run_batch(out, o, "fake", EchoClient(), FakeDetector([]), FakeDetector([]), frozen=True) == 5


def test_echo_replies_are_never_scored_as_live(tmp_path):
    out = batch(tmp_path)
    o = tmp_path / "o"
    assert run.run_batch(out, o, "fake", EchoClient(), FakeDetector([]), FakeDetector([])) == 0
    assert run.run_batch(out, o, "live", EchoClient(), FakeDetector([]), FakeDetector([]), dev=True) == 4


def test_replay_rescores_saved_replies_without_calls(tmp_path):
    out = batch(tmp_path)
    assert run.run_batch(out, tmp_path / "o1", "fake", EchoClient(), FakeDetector([]), FakeDetector([])) == 0
    (tmp_path / "o2").mkdir()
    (tmp_path / "o2" / "replies.jsonl").write_bytes((tmp_path / "o1" / "replies.jsonl").read_bytes())
    assert run.run_batch(out, tmp_path / "o2", "replay", None, FakeDetector([]), FakeDetector([])) == 0
    assert (tmp_path / "o1" / "scores.jsonl").read_bytes() == (tmp_path / "o2" / "scores.jsonl").read_bytes()
    assert run.run_batch(out, tmp_path / "o3", "replay", None, FakeDetector([]), FakeDetector([])) == 4


def test_replay_refuses_replies_asked_about_another_message(tmp_path):
    out = batch(tmp_path)
    assert run.run_batch(out, tmp_path / "o1", "fake", EchoClient(), FakeDetector([]), FakeDetector([])) == 0
    (tmp_path / "o2").mkdir()
    (tmp_path / "o2" / "replies.jsonl").write_bytes((tmp_path / "o1" / "replies.jsonl").read_bytes())
    assert run.run_batch(out, tmp_path / "o2", "replay", None, FakeDetector(["Hello"]), FakeDetector([])) == 4


def test_repeat_subset_is_seeded_and_sized():
    ids = [f"dev-{i:03d}" for i in range(100)]
    a, b = run.repeat_subset(ids), run.repeat_subset(ids)
    assert a == b and len(a) == run.REPEAT_SUBSET and set(a) <= set(ids)


class RaisingClient:
    def __init__(self):
        self.calls = 0
        self.messages = self
        self.models = self

    def create(self, **kwargs):
        self.calls += 1
        raise AssertionError("called")

    def retrieve(self, *a, **k):
        self.calls += 1
        raise AssertionError("called")


def _two(tmp_path):
    out = batch(tmp_path)
    assert run.run_batch(out, tmp_path / "o1", "fake", EchoClient(), FakeDetector([]), FakeDetector([])) == 0
    (tmp_path / "o2").mkdir()
    return out, tmp_path / "o1", tmp_path / "o2"


def test_stale_replies_refuse_before_any_call(tmp_path):
    out, o1, o2 = _two(tmp_path)
    (o2 / "replies.jsonl").write_bytes((o1 / "replies.jsonl").read_bytes())
    c = RaisingClient()
    assert run.run_batch(out, o2, "fake", c, FakeDetector(["Hello"]), FakeDetector([])) == 4
    assert c.calls == 0


def test_live_refuses_echo_replies_already_on_file(tmp_path):
    out, o1, _ = _two(tmp_path)
    c = RaisingClient()
    assert run.run_batch(out, o1, "live", c, FakeDetector([]), FakeDetector([]), dev=True) == 4
    assert c.calls == 0


def test_replay_refuses_a_foreign_model_under_frozen(tmp_path):
    out, o1, o2 = _two(tmp_path)
    rows = [json.loads(x) for x in (o1 / "replies.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    for r in rows:
        r["model"] = "other-model"
    (o2 / "replies.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    (o2 / "manifest.start-x.json").write_text(json.dumps({"frozen": True, "dev": False}), encoding="utf-8")
    assert run.run_batch(out, o2, "replay", None, FakeDetector([]), FakeDetector([]), frozen=True) == 4


def test_frozen_refuses_replies_without_a_frozen_manifest(tmp_path):
    out, o1, o2 = _two(tmp_path)
    (o2 / "replies.jsonl").write_bytes((o1 / "replies.jsonl").read_bytes())
    assert run.run_batch(out, o2, "replay", None, FakeDetector([]), FakeDetector([]), frozen=True) == 5


def test_replay_refuses_an_incomplete_or_duplicated_replies_file(tmp_path):
    out, o1, o2 = _two(tmp_path)
    lines = (o1 / "replies.jsonl").read_text(encoding="utf-8").splitlines(keepends=True)
    (o2 / "replies.jsonl").write_text("".join(lines[:-1]), encoding="utf-8")
    assert run.run_batch(out, o2, "replay", None, FakeDetector([]), FakeDetector([])) == 4
    o3 = tmp_path / "o3"
    o3.mkdir()
    (o3 / "replies.jsonl").write_text("".join(lines + lines[:1]), encoding="utf-8")
    assert run.run_batch(out, o3, "replay", None, FakeDetector([]), FakeDetector([])) == 4


def test_generate_refuses_before_any_client(tmp_path, monkeypatch):
    out = batch(tmp_path)

    def boom(*a, **k):
        raise AssertionError("client built")

    monkeypatch.setattr("pgw.model_call.make_client", boom)
    assert run.main(["generate", "--batch", "dev", "--out", str(out), "--writer", "live", "--dev"]) == 5


def test_dev_and_frozen_together_refuse(tmp_path):
    assert run.main(["run", "--batch", str(tmp_path), "--out", str(tmp_path / "o"), "--model-stage", "skip",
                     "--dev", "--frozen", str(tmp_path / "F.json")]) == 2


def test_a_damaged_batch_returns_6(tmp_path):
    out = batch(tmp_path)
    (out / "gold.jsonl").unlink()
    assert run.run_batch(out, tmp_path / "o", "skip", None, FakeDetector([]), FakeDetector([])) == 6


def test_generate_manifest_records_frozen(tmp_path):
    out = batch(tmp_path)
    m = json.loads(next(out.glob("manifest.generate-start-*.json")).read_text(encoding="utf-8"))
    assert m["frozen"] is False


def _valid_freeze(tmp_path):
    f = tmp_path / "FROZEN.json"
    f.write_text(json.dumps(manifest.freeze_record()), encoding="utf-8")
    assert manifest.check_frozen(f) == []
    return f


def test_frozen_refuses_fake_writer_and_fake_stage(tmp_path, capsys):
    frozen = str(_valid_freeze(tmp_path))
    assert run.main(["generate", "--batch", "dev", "--out", str(tmp_path / "b"), "--writer", "fake",
                     "--frozen", frozen]) == 2
    assert not (tmp_path / "b").exists()
    assert run.main(["run", "--batch", str(tmp_path / "b"), "--out", str(tmp_path / "o"), "--model-stage", "fake",
                     "--frozen", frozen]) == 2
    assert not (tmp_path / "o").exists()
    assert capsys.readouterr().err.count("fake") >= 2


def test_generate_records_the_writer(tmp_path):
    out = batch(tmp_path)
    assert json.loads((out / "batch.json").read_text(encoding="utf-8"))["writer"] == "fake"
    for p in (*out.glob("manifest.generate-start-*.json"), *out.glob("manifest.generate-end-*.json")):
        assert json.loads(p.read_text(encoding="utf-8"))["writer"] == "fake"


def test_main_passes_the_writer(tmp_path, monkeypatch):
    monkeypatch.setitem(run.BATCHES["dev"], "n", 6)
    monkeypatch.setattr("pgw.model_call.make_client", lambda **k: FakeWriter())
    monkeypatch.setattr("pgw.model_call.canary", lambda client, model: {"models_api_id": model})
    out = tmp_path / "b"
    assert run.main(["generate", "--batch", "dev", "--out", str(out), "--writer", "live", "--dev"]) == 0
    assert json.loads((out / "batch.json").read_text(encoding="utf-8"))["writer"] == "live"


def _forge(out, batch_name="test", writer="live", frozen_manifest=True, gen_model=emailgen.GEN_MODEL):
    """Rewrite a fake batch's provenance; generation.jsonl's hash is re-recorded so only the guard can refuse."""
    meta = json.loads((out / "batch.json").read_text(encoding="utf-8"))
    rows = [json.loads(x) for x in (out / "generation.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    (out / "generation.jsonl").write_text("".join(json.dumps(dict(r, model=gen_model)) + "\n" for r in rows),
                                          encoding="utf-8", newline="\n")
    meta["sha256"]["generation.jsonl"] = run._sha(out / "generation.jsonl")
    meta.update(batch=batch_name, writer=writer)
    (out / "batch.json").write_text(json.dumps(meta), encoding="utf-8")
    if frozen_manifest:
        (out / "manifest.generate-start-forged.json").write_text(json.dumps({"frozen": True}), encoding="utf-8")


def test_a_frozen_run_refuses_a_dev_or_fake_batch(tmp_path):
    out = batch(tmp_path)
    assert run.run_batch(out, tmp_path / "o", "skip", None, FakeDetector([]), FakeDetector([]), frozen=True) == 6
    assert not list((tmp_path / "o").glob("manifest.start-*.json"))


@pytest.mark.parametrize("changes", [dict(batch_name="dev"), dict(writer="fake"), dict(writer=None),
                                     dict(frozen_manifest=False), dict(gen_model="fake"),
                                     dict(gen_model="claude-sonnet-5-5")])
def test_a_frozen_run_refuses_each_fake_or_dev_mark(tmp_path, changes):
    out = batch(tmp_path)
    _forge(out, **changes)
    assert run.run_batch(out, tmp_path / "o", "skip", None, FakeDetector([]), FakeDetector([]), frozen=True) == 6


def test_a_frozen_run_accepts_a_live_frozen_test_batch(tmp_path):
    out = batch(tmp_path)
    _forge(out)
    assert run.run_batch(out, tmp_path / "o", "skip", None, FakeDetector([]), FakeDetector([]), frozen=True) == 0


def test_sample_is_drawn_from_handled_emails(tmp_path):
    out = batch(tmp_path, n=20)
    assert run.run_batch(out, tmp_path / "o", "fake", EchoClient(), FakeDetector([]), FakeDetector([])) == 0
    rows = [json.loads(x) for x in (tmp_path / "o" / "scores.jsonl").read_text(encoding="utf-8").splitlines()]
    handled = {r["email_id"] for r in rows if r["handled"]}
    assert handled and len(handled) < len(rows)      # the batch has unhandled emails to exclude
    sample = json.loads((tmp_path / "o" / "summary.json").read_text(encoding="utf-8"))["sample_ids"]
    assert set(sample) <= handled and len(sample) == min(run.SAMPLE_SIZE, len(handled))
