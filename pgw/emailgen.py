"""Writing the emails (spec §3): Opus 5.5 writes each email from its brief and the parts of the record the
customer would know. Every planted string must appear EXACTLY; an email missing one is regenerated, up to
MAX_ATTEMPTS, and every attempt is recorded and published."""
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from pgw import model_call, names
from pgw.briefs import Brief
from pgw.crm import REFERENCE_DATE, Customer

if f"{REFERENCE_DATE:%A %B}" != "Monday October":
    raise RuntimeError("emailgen needs English day and month names (LC_TIME); got " + f"{REFERENCE_DATE:%A %B}")

GEN_MODEL = "claude-opus-5-5"     # spec §2; its ID is checked against the API's model list (Task 13)
GEN_EFFORT = "medium"
MAX_ATTEMPTS = 3

GEN_SYSTEM = f"""You write realistic synthetic customer emails to the support team of {names.COMPANY}, an online home-goods retailer, for testing software. Every detail you are given is invented. Write one email that follows the brief.

Rules:
- Include every string listed under "Must include, exactly" character for character.
- Do not add any other names, email addresses, phone numbers, postal addresses, account or order numbers, card numbers, bank details or money amounts.
- Never mention that the email is synthetic or a test.
- Return JSON with "subject" and "body"."""

EMAIL_SCHEMA = {"type": "json_schema", "schema": {
    "type": "object", "properties": {"subject": {"type": "string"}, "body": {"type": "string"}},
    "required": ["subject", "body"], "additionalProperties": False}}

ISSUE = {
    "refund": "wants a refund for {items}",
    "late_delivery": "their order with {items} has not arrived",
    "damaged_or_wrong": "{items} arrived damaged or was the wrong item, and they want a {wants}",
    "change_of_address": "wants the delivery address of their order with {items} changed to the new address below",
    "cancellation": "wants to cancel their order with {items}",
    "billing_question": "has a question about what they were charged for their order with {items}",
    "account_access": "cannot log in to their online account; do not mention an order",
    "complaint": "is unhappy with how their order with {items} has been handled and wants to complain",
    "complaint_no_order": "is unhappy with the service in general, not with any particular order, and wants to "
                          "complain; do not mention an order",
}


def _when(d) -> str:
    return f"{d.day} {d:%B %Y}"


def _ago(d) -> str:
    """How long before the inbox's today an order event was, as a rounded phrase computed here so the writer does
    no date arithmetic. Every phrase is true of its whole band and never asserts the wrong side of a policy line
    (RETURN_DAYS 30, LATE_DAYS 7). The two bands that contain a line, "about a week ago" (7 days) and "about a month
    ago" (30 days), assert neither side, so the record decides."""
    n = (REFERENCE_DATE - d).days
    if n == 0:
        return "today"
    if n == 1:
        return "yesterday"
    if n <= 6:
        monday = REFERENCE_DATE - timedelta(days=REFERENCE_DATE.weekday())
        return f"on {d:%A}" if d >= monday else f"last {d:%A}"
    for top, phrase in ((10, "about a week ago"), (17, "about two weeks ago"), (24, "about three weeks ago"),
                        (38, "about a month ago"), (52, "about six weeks ago"), (75, "about two months ago")):
        if n <= top:
            return phrase
    return "a few months ago"


def _gap(a, b) -> str:
    """The interval between two order events, as a rounded phrase."""
    n = (b - a).days
    if n == 0:
        return "the same day"
    if n == 1:
        return "the next day"
    if n == 2:
        return "a couple of days later"
    if n <= 4:
        return "a few days later"
    if n <= 9:
        return "about a week later"
    if n <= 17:
        return "about two weeks later"
    return "several weeks later"


def describe(b: Brief) -> str:
    case = b.case
    items = " and ".join(case["items"] or case["order_items"]) or "their order"
    key = "complaint_no_order" if case["category"] == "complaint" and not case["order_no"] else case["category"]
    text = ISSUE[key].format(items=items, wants=case["wants"] or "refund")
    if case["double_charge"]:
        text += "; they were charged twice for it"
    return text + "."


def _role(b: Brief, p) -> str:
    """What a plant is to the customer, so the writer cannot repurpose it (the self name has no role line)."""
    v = p.value
    item = (b.case["items"] or b.case["order_items"] or ["their order"])[0]
    return {
        "order_no": f"{v} is their order number",
        "account": f"{v} is their account number (not an order number)",
        "phone_on_file": f"{v} is their own phone number",
        "amount_on_file": f"{v} is the price they paid for {item}",
        "third_party": f"{v} is {b.hints.get('third_party_relation', 'someone they know')} "
                       "(a member of their household or circle, not a member of staff)",
        "new_phone": f"{v} is a new phone number of theirs",
        "new_address": (f"{v} is the new delivery address for this order" if b.case["category"] == "change_of_address"
                        else f"{v} is their new home address (they have moved; it is not the delivery address of this order)"
                        if b.case["order_no"] else f"{v} is their new home address (they have moved)"),
        "card": f"{v} is their payment card number, which they include although they should not",
        "iban": (f"{v} is their bank account for a refund" if b.case["category"] in ("refund", "damaged_or_wrong")
                 else f"{v} is their bank account number, which they include although they should not"),
    }.get(p.kind, "")


def generator_message(b: Brief, c: Customer) -> str:
    lines = [f"The customer is {c.full}. In the email they refer to themselves as: {b.plants[0].value}"
             + ("" if b.plants[0].value.endswith(".") else "."),
             f"Their issue: the customer {describe(b)}",
             f"Tone: {b.style['tone']}. Register: {b.style['register']}."]
    if b.style["typos"]:
        lines.append("Include a few natural typing mistakes, but never inside the strings that must be included.")
    if b.case["repeat_contact"]:
        lines.append("This is not their first contact: they say they have already contacted support about this.")
    else:
        lines.append("This is their first contact about this issue: do not mention any earlier message, call or reply.")
    order = next((o for o in c.orders if o.order_no == b.case["order_no"]), None) if b.case["order_no"] else None
    if b.case["category"] == "refund":
        lines.append(f"Their reason for the refund: {b.case['reason']}. "
                     + ("The item is fine and is what they ordered; they need not say so."
                        if order and order.status == "delivered" else "They have not received it yet."))
        lines.append("Do not describe any item as damaged, broken, faulty or wrong.")
    elif b.case["category"] == "complaint" and b.case["order_no"]:
        lines.append("Do not describe any item as damaged, broken, faulty or wrong; they need not say the items are fine.")
    if order:
        def paren(x, y) -> str:
            return f" ({_ago(x)})" if _ago(x) != _ago(y) else ""
        facts = f"the order was placed {_ago(order.placed)}"
        if order.dispatched:
            facts += f"; it was dispatched {_gap(order.placed, order.dispatched)}"
            # the latest event carries its own phrase (the policy's day limits read it); an earlier one only when it differs
            facts += paren(order.dispatched, order.placed) if order.delivered else f" ({_ago(order.dispatched)})"
        if order.delivered:
            facts += f" and delivered {_gap(order.dispatched, order.delivered)} ({_ago(order.delivered)})"
        facts += f"; it is now {order.status}"
        lines.append(f"Today is {REFERENCE_DATE:%A} {_when(REFERENCE_DATE)}. "
                     "Background the customer knows (they may refer to these facts in these words or their own, "
                     "or leave out when things happened; they must not list dates, give a count of days, "
                     "be more precise than these phrases, or state today's date): "
                     f"{facts}. Any time phrase in the email must agree with these. "
                     "Do not contradict these facts.")
    if b.style["quoted_thread"]:
        lines.append("Below the message, quote a short earlier reply from the support team, as an email client would. "
            "The quoted reply only acknowledges their earlier message: it promises nothing (no refund, replacement, amount or date).")
    lines.append("End with a signature." if b.style["signature"] else "Do not add a signature block.")
    if "third_party_relation" in b.hints:
        third = next(p.value for p in b.plants if p.kind == "third_party")
        lines.append(f"Mention {b.hints['third_party_relation']}, {third}, by first name.")
    lines.append("Must include, exactly:\n" + "\n".join(f"- {p.value}" for p in b.plants))
    roles = [r for r in (_role(b, p) for p in b.plants) if r]
    if roles:
        lines.append("What each of these is (background for you; do not restate these descriptions in the email):\n" + "\n".join(f"\u2022 {r}" for r in roles))
    return "\n".join(lines)


def check_exact(b: Brief, subject: str, body: str) -> list[str]:
    text = f"{subject}\n{body}"
    return [p.value for p in b.plants if not re.search(r"(?<!\w)" + re.escape(p.value) + r"(?!\w)", text)]


def email_text(row: dict) -> str:
    return f"Subject: {row['subject']}\n\n{row['body']}"


def generate(client, briefs: list[Brief], by_pid: dict[str, Customer], out_path: Path) -> None:
    prior: dict[str, list[dict]] = {}
    for r in model_call.read_records(out_path):
        prior.setdefault(r["email_id"], []).append(r)
    with out_path.open("a", encoding="utf-8", newline="\n") as f:
        for b in briefs:
            done = prior.get(b.email_id, [])
            if any(r["ok"] for r in done):
                continue
            for attempt in range(len(done), MAX_ATTEMPTS):
                user = generator_message(b, by_pid[b.pid])
                rec = model_call.ask(client, GEN_MODEL, GEN_SYSTEM, user, GEN_EFFORT, output_format=EMAIL_SCHEMA)
                subject, body, missing = "", "", [p.value for p in b.plants]
                if rec["stop_reason"] == "end_turn":
                    try:
                        data = json.loads(rec["text"])
                        subject, body = data["subject"], data["body"]
                        missing = check_exact(b, subject, body)
                    except (json.JSONDecodeError, KeyError, TypeError):
                        pass
                rec.update(email_id=b.email_id, attempt=attempt, ok=not missing, missing=missing, subject=subject,
                           body=body, at=datetime.now(timezone.utc).isoformat(),
                           user_sha256=hashlib.sha256(user.encode("utf-8")).hexdigest())
                f.write(json.dumps(rec, sort_keys=True, ensure_ascii=False) + "\n")
                f.flush()
                if not missing:
                    break


def accepted(out_path: Path) -> dict[str, dict]:
    return {r["email_id"]: r for r in model_call.read_records(out_path) if r["ok"]}


def stats(out_path: Path) -> dict:
    rows = model_call.read_records(out_path)
    ids = {r["email_id"] for r in rows}
    ok = {r["email_id"] for r in rows if r["ok"]}
    return {"briefs": len(ids), "accepted": len(ok), "attempts": len(rows),
            "rejected_attempts": sum(not r["ok"] for r in rows), "dropped": len(ids - ok)}


class FakeWriter:
    """No-network stand-in: writes every must-include string; answers audits with no items."""

    def __init__(self) -> None:
        self.messages = self
        self.models = SimpleNamespace(retrieve=lambda model_id: SimpleNamespace(id=model_id, display_name="fake"))

    def create(self, **kwargs):
        user = kwargs["messages"][0]["content"]
        if "Must include, exactly:" in user:
            must = re.findall(r"^- (.+)$", user.split("Must include, exactly:")[1], re.MULTILINE)
            text = json.dumps({"subject": "About my order", "body": "Hello,\n" + "\n".join(must) + "\nThanks"})
        else:
            text = json.dumps({"items": []})
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)], stop_reason="end_turn",
                               model="fake", usage=SimpleNamespace(input_tokens=0, output_tokens=0),
                               _request_id="fake", to_dict=lambda: {"fake": True})
