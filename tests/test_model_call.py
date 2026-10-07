import hashlib
import json
from types import SimpleNamespace

import anthropic
import pytest

from pgw.model_call import ServiceStop, ask, canary, make_client, run_calls


def reply(text, stop="end_turn"):
    return SimpleNamespace(
        content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)],
        stop_reason=stop, model="claude-sonnet-5-5",
        usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        _request_id="req_test", to_dict=lambda: {"fake": True})


class Boom(anthropic.APIError):
    def __init__(self):
        Exception.__init__(self, "boom")


class FakeClient:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []
        self.messages = self
        self.models = SimpleNamespace(retrieve=lambda model_id: SimpleNamespace(id=model_id, display_name="Fake"))

    def create(self, **kwargs):
        self.calls.append(kwargs)
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def test_ask_reads_text_blocks_and_sends_effort_without_sampling_params():
    client = FakeClient([reply("1: [PERSON_1]")])
    rec = ask(client, "claude-sonnet-5-5", "SYS", "USER", "high")
    assert rec["text"] == "1: [PERSON_1]" and rec["model"] == "claude-sonnet-5-5"
    sent = client.calls[0]
    assert sent["output_config"] == {"effort": "high"} and sent["system"] == "SYS"
    assert "temperature" not in sent and "top_p" not in sent and "fallbacks" not in sent


def test_api_error_stops_the_run():
    with pytest.raises(ServiceStop):
        ask(FakeClient([Boom()]), "m", "s", "u", "high")


def test_empty_end_turn_stops_the_run():
    with pytest.raises(ServiceStop):
        ask(FakeClient([reply("   ")]), "m", "s", "u", "high")


def test_refusal_is_recorded_not_raised():
    assert ask(FakeClient([reply("", stop="refusal")]), "m", "s", "u", "high")["stop_reason"] == "refusal"


def test_resume_neither_duplicates_nor_skips(tmp_path):
    out = tmp_path / "replies.jsonl"
    jobs = [("t1", 0, "a"), ("t1", 1, "b")]
    with pytest.raises(ServiceStop):
        run_calls(FakeClient([reply("ok"), Boom()]), "m", "high", "s", jobs, out)
    assert run_calls(FakeClient([reply("ok2")]), "m", "high", "s", jobs, out) == 1
    keys = [(r["task_id"], r["repeat"]) for r in map(json.loads, out.read_text(encoding="utf-8").splitlines())]
    assert keys == [("t1", 0), ("t1", 1)]


def test_make_client_never_retries():
    assert make_client(api_key="test-not-a-key").max_retries == 0


def test_canary_records_both_ids():
    out = canary(FakeClient([reply("READY")]), "claude-sonnet-5-5")
    assert out["models_api_id"] == "claude-sonnet-5-5" and out["reported_model"] == "claude-sonnet-5-5"


def test_ask_sends_the_format_inside_output_config():
    client = FakeClient([reply('{"a": 1}')])
    fmt = {"type": "json_schema", "schema": {"type": "object"}}
    ask(client, "m", "s", "u", "high", output_format=fmt)
    assert client.calls[0]["output_config"] == {"effort": "high", "format": fmt}


def test_read_records_returns_rows_and_sets_a_partial_line_aside(tmp_path):
    from pgw.model_call import read_records

    out = tmp_path / "r.jsonl"
    out.write_text('{"task_id": "a", "repeat": 0}\n{"task_id": "b"', encoding="utf-8", newline="\n")
    assert read_records(out) == [{"task_id": "a", "repeat": 0}]
    assert (tmp_path / "r.jsonl.partial").exists()


def test_partial_final_line_is_set_aside_and_the_run_resumes(tmp_path):
    out = tmp_path / "replies.jsonl"
    good = json.dumps({"task_id": "t1", "repeat": 0, "text": "ok"})
    out.write_text(good + "\n" + '{"task_id": "t1", "rep', encoding="utf-8", newline="\n")
    jobs = [("t1", 0, "a"), ("t1", 1, "b")]
    assert run_calls(FakeClient([reply("ok2")]), "m", "high", "s", jobs, out) == 1
    lines = out.read_text(encoding="utf-8").splitlines()
    assert [(json.loads(x)["task_id"], json.loads(x)["repeat"]) for x in lines] == [("t1", 0), ("t1", 1)]
    assert (tmp_path / "replies.jsonl.partial").read_text(encoding="utf-8") == '{"task_id": "t1", "rep\n'


def test_max_tokens_is_recorded_not_raised():
    rec = ask(FakeClient([reply("1: [PERSON_1", stop="max_tokens")]), "m", "s", "u", "high")
    assert rec["stop_reason"] == "max_tokens" and rec["text"] == "1: [PERSON_1"


def test_each_reply_records_the_hash_of_what_was_sent(tmp_path):
    out = tmp_path / "replies.jsonl"
    run_calls(FakeClient([reply("ok")]), "m", "high", "s", [("t1", 0, "hello")], out)
    rec = json.loads(out.read_text(encoding="utf-8"))
    assert rec["user_sha256"] == hashlib.sha256(b"hello").hexdigest()
