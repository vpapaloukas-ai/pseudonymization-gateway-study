"""Scoring rules (spec §6), fixed before the test batch exists. Every number is k of n with its unit; value
is reported over handled emails AND over all emails; every key is always written, as [0, n] when nothing of
that kind occurred, so absence never reads as "nothing leaked"."""
import re
from collections import Counter

from pgw import audit, exitcheck, known_scan
from pgw.audit import GoldItem
from pgw.briefs import Brief
from pgw.crm import Customer, money
from pgw.policy import ACTIONS
from pgw.vault import TOKEN_RE, Vault

HOLD_GROUPS_ALL = ("unrecognised_sender", "high_risk", "leftover_pattern", "known_value", "draft_check", "no_answer")
TRIAGE_FIELDS = ("category", "urgency", "order", "action")
UNKNOWN_KINDS = ("third_party", "new_phone", "new_address", "unplanned")
HIGH_RISK_KINDS = ("card", "iban", "unplanned")


def _bare(message: str) -> str:
    return TOKEN_RE.sub(" ", message)


def _present(part: str, bare: str) -> bool:
    if sum(ch.isdigit() for ch in part) >= 4:
        digits = re.sub(r"[^0-9a-z]", "", part.lower())
        return digits in re.sub(r"[^0-9a-z]", "", bare.lower())
    return re.search(r"(?<![\w])" + r"\W{1,3}".join(map(re.escape, part.split())) + r"(?![\w])", bare,
                     re.IGNORECASE) is not None


def _nothing_planted(b: Brief) -> bool:
    return b.matched and all(p.known and p.listed for p in b.plants)


def is_clean(b: Brief, gold: list[GoldItem]) -> bool:
    return _nothing_planted(b) and not any(g.origin == "audit" for g in gold)


def _field_counts(text: str, c: Customer) -> Counter:
    return Counter((o.field, o.listed) for o in known_scan.occurrences(text, c))


def _leak(orig: Counter, payload: Counter) -> dict:
    return {lst: [sum(min(v, payload[k]) for k, v in orig.items() if k[1] == lst),
                  sum(v for k, v in orig.items() if k[1] == lst)] for lst in (True, False)}


def _order_token(vault: Vault, order_no: str | None) -> str:
    if order_no is None:
        return ""
    return next((t for t, v in vault.tokens().items() if t.startswith("[ORDER_") and v == order_no), "")


def score_email(b: Brief, gold: list[GoldItem], c: Customer, out, inb, contrast_payload: str) -> dict:
    sent = out.message is not None and not out.held
    holds = []
    if out.message is None:
        holds.append("unrecognised_sender")
    groups = set()
    for r in out.held:
        if r == "unrecognised_sender":
            continue
        if r not in exitcheck.HOLD_GROUPS:
            raise ValueError(f"unmapped exit-check reason {r!r}")
        groups.add(exitcheck.HOLD_GROUPS[r])
    holds += sorted(groups)
    if sent and inb is not None and not inb.ok:
        holds.append("no_answer")
    if sent and inb is not None and inb.ok and inb.draft:
        holds.append("draft_check")
    handled = sent and inb is not None and inb.ok and not inb.draft
    vault = Vault.from_json(out.vault) if out.vault else Vault()
    triage = {f: False for f in TRIAGE_FIELDS}
    reply_correct = False
    if inb is not None and inb.ok:
        expected_order = _order_token(vault, b.gold["order_no"])
        triage = {"category": inb.triage["category"] == b.gold["category"],
                  "urgency": inb.triage["urgency"] == b.gold["urgency"],
                  "order": inb.triage["order"] == expected_order,
                  "action": inb.triage["action"] == b.gold["action"]}
        cust = vault.token("CUSTOMER", c.full) if out.vault else ""
        first = vault.token("FIRST_NAME", c.first) if out.vault else ""
        reply_correct = (handled and (cust in inb.raw_reply or first in inb.raw_reply)
                         and (not expected_order or expected_order in inb.raw_reply)
                         and (b.gold["amount"] is None or money(b.gold["amount"]) in inb.restored))
    original = Counter()
    for g in gold:
        if g.origin == "record_scan":
            original[(g.kind.split(":")[1], g.listed)] += 1
    known_leak = _leak(original, _field_counts(_bare(out.message), c) if sent else Counter())
    stage = "sender" if out.message is None else "exit"
    unknown, high = [], []
    for g in gold:
        if g.known or g.origin == "skipped":
            continue
        outcome = "held" if not sent else ("reached" if any(_present(p, _bare(out.message)) for p in g.parts) else "masked")
        # planted kinds as they are; audit finds as "unplanned:<kind>", pooled and per kind in summarise()
        (high if g.high_risk else unknown).append({"kind": g.kind, "outcome": outcome, "stage": stage})
    contrast_bare = _bare(contrast_payload)
    contrast_leak = _leak(original, _field_counts(contrast_bare, c))
    contrast_high = sum(any(_present(p, contrast_bare) for p in g.parts) for g in gold if g.high_risk)
    nothing_planted = _nothing_planted(b)
    return {"email_id": b.email_id, "nothing_planted": nothing_planted, "clean": is_clean(b, gold), "sent": sent,
            "holds": holds, "handled": handled, "gold_action": b.gold["action"],
            "triage": triage, "reply_correct": reply_correct, "draft": list(inb.draft) if inb else [],
            "failure": inb.failure if inb else "",
            "known": {"listed": known_leak[True], "unlisted": known_leak[False]},
            "unknown": unknown, "high_risk": high,
            "skipped": sum(g.origin == "skipped" for g in gold),
            "contrast": {"known": {"listed": contrast_leak[True], "unlisted": contrast_leak[False]},
                         "high_risk": [contrast_high, sum(g.high_risk for g in gold)]}}


def summarise(rows: list[dict], variation_rows: list[dict], gen_stats: dict, replies: list[dict]) -> dict:
    n = len(rows)
    handled = [r for r in rows if r["handled"]]
    sent = [r for r in rows if r["sent"]]
    s: dict = {"n_emails": n, "value.handled": [len(handled), n]}
    for f in TRIAGE_FIELDS:
        k = sum(r["triage"][f] for r in handled)
        s[f"value.triage.{f}.over_handled"] = [k, len(handled)]
        s[f"value.triage.{f}.over_all"] = [k, n]
    for a in ACTIONS:   # per-action figures, always written; rates are the reporting's job (n >= 10 rule)
        of_a = [r for r in rows if r["gold_action"] == a]
        s[f"value.by_action.{a}"] = {"n": len(of_a), "handled": sum(r["handled"] for r in of_a),
                                     "action_correct": sum(r["triage"]["action"] for r in of_a if r["handled"])}
    k = sum(r["reply_correct"] for r in handled)
    s["value.reply.over_handled"] = [k, len(handled)]
    s["value.reply.over_all"] = [k, n]
    for g in HOLD_GROUPS_ALL:
        s[f"holds.{g}"] = [sum(g in r["holds"] for r in rows), n]
    planted_free = [r for r in rows if r["nothing_planted"]]
    clean = [r for r in rows if r["clean"]]

    def false_hold(r):
        return any(h != "no_answer" for h in r["holds"])
    s["holds.false"] = [sum(false_hold(r) for r in planted_free), len(planted_free)]
    s["holds.false_clean"] = [sum(false_hold(r) for r in clean), len(clean)]
    s["holds.false_by_reason"] = {g: sum(g in r["holds"] for r in planted_free)
                                  for g in HOLD_GROUPS_ALL if g != "no_answer"}
    for lst in ("listed", "unlisted"):
        s[f"leaks.known.{lst}.mentions"] = [sum(r["known"][lst][0] for r in rows), sum(r["known"][lst][1] for r in rows)]
        s[f"leaks.known.{lst}.mentions_sent"] = [sum(r["known"][lst][0] for r in sent), sum(r["known"][lst][1] for r in sent)]
        s[f"leaks.known.{lst}.emails"] = [sum(r["known"][lst][0] > 0 for r in rows), n]
        s[f"leaks.known.{lst}.emails_sent"] = [sum(r["known"][lst][0] > 0 for r in sent), len(sent)]

    def line(items: list[dict]) -> dict:
        at_exit = [x for x in items if x["stage"] == "exit"]
        return {"masked": sum(x["outcome"] == "masked" for x in items),
                "held": sum(x["outcome"] == "held" for x in items),
                "reached": sum(x["outcome"] == "reached" for x in items), "n": len(items),
                "n_at_exit": len(at_exit),
                "held_at_exit": sum(x["outcome"] == "held" for x in at_exit)}
    for key, kinds in (("unknown", UNKNOWN_KINDS), ("high_risk", HIGH_RISK_KINDS)):
        for k in kinds:
            if k == "unplanned":   # pooled over every audit kind
                s[f"{key}.{k}"] = line([x for r in rows for x in r[key] if x["kind"].startswith("unplanned")])
            else:
                s[f"{key}.{k}"] = line([x for r in rows for x in r[key] if x["kind"] == k])
        for k in audit.KINDS:      # one line per audit kind, always written
            s[f"{key}.unplanned.{k}"] = line([x for r in rows for x in r[key] if x["kind"] == f"unplanned:{k}"])
    s["audit.skipped"] = sum(r["skipped"] for r in rows)
    for lst in ("listed", "unlisted"):
        s[f"contrast.known.{lst}.mentions"] = [sum(r["contrast"]["known"][lst][0] for r in rows),
                                               sum(r["contrast"]["known"][lst][1] for r in rows)]
    s["contrast.high_risk"] = [sum(r["contrast"]["high_risk"][0] for r in rows), sum(r["contrast"]["high_risk"][1] for r in rows)]
    variation: dict[str, list] = {}
    for r in sorted(variation_rows, key=lambda r: (r["email_id"], r["repeat"])):
        variation.setdefault(r["email_id"], []).append([r["handled"], all(r["triage"].values()), r["reply_correct"]])
    s["variation"] = variation
    s["stops"] = dict(Counter(r["stop_reason"] for r in replies))
    s["models_reported"] = dict(Counter(r["model"] for r in replies))
    s["generation"] = gen_stats
    return s


def control() -> None:
    """Positive control run inside every pipeline run (spec §7): a planted known value deliberately left in
    the message must score as a leak."""
    from types import SimpleNamespace

    from pgw.briefs import Plant
    from pgw.crm import Customer as _C, Item, Order
    from datetime import date

    c = _C("C999", "Ms", "Ada", "Okafor", "ada.okafor@postbox-mail.co.uk", "07700 900123", "1 Mill Lane", "Whitby",
           "YO21 3XX", "BWC1234567", "GB00SYNT00000000000000",
           (Order("BW-000001", date(2026, 9, 1), "processing", None, None, (Item("Jute rug", 12000),)),))
    me = Plant("self_name", "Ada Okafor", ("Ada Okafor",), True, True, False)
    b = Brief("ctl", c.pid, c.email, True, {"category": "complaint", "order_no": None, "order_items": [], "items": [],
              "wants": "", "double_charge": False, "repeat_contact": False},
              {"category": "complaint", "urgency": "normal", "action": "escalate", "amount": None, "order_no": None},
              "full", (me,), {}, {})
    gold = [GoldItem("record:name:full", "Ada Okafor", ("Ada Okafor",), "record_scan", True, True, False)]
    out = SimpleNamespace(message="<<<\nAda Okafor\n>>>", held=(), vault=Vault().to_json())
    row = score_email(b, gold, c, out, None, "")
    assert row["known"]["listed"] == [1, 1], f"known-value scorer missed a planted leak: {row['known']}"
