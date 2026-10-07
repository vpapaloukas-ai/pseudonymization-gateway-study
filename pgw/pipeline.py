"""One email through the gateway (spec §4). outbound(): steps 1-4, ending in exactly the message that would
leave, or a hold. inbound(): steps 6-7 on the model's reply. contrast(): Presidio as shipped, payload only."""
import json
from dataclasses import asdict, dataclass

from pgw import calc, draftcheck, exitcheck, known, names, prompts
from pgw.crm import Customer
from pgw.vault import Vault, restore


@dataclass(frozen=True)
class Outbound:
    email_id: str
    held: tuple[str, ...]
    message: str | None          # the exact user message that would leave (None when step 1 holds)
    vault: dict | None
    known_hits: list[dict]
    detections: list[dict]


@dataclass(frozen=True)
class Inbound:
    email_id: str
    repeat: int
    ok: bool
    failure: str                 # "" | "stop:<reason>" | "invalid_json"
    triage: dict
    raw_reply: str
    restored: str
    draft: tuple[str, ...]


def exit_record(c: Customer) -> exitcheck.Record:
    seqs = [c.phone, c.account, c.account[3:], c.iban, c.postcode]
    for o in c.orders:
        seqs += [o.order_no, o.order_no.split("-")[1]]
    amounts = tuple(dict.fromkeys(p for o in c.orders for p in (*(i.price for i in o.items), o.total)))
    return exitcheck.Record(names=(c.first, c.last),
                            case_sensitive=(c.first,) if c.first in names.WORD_FIRST_NAMES else (),
                            sequences=tuple(seqs), phrases=(c.email, c.email.split("@")[0], c.street),
                            amounts=amounts, initials=() if c.first[0] + c.last[0] in names.DOTTED_ABBREVIATIONS else (c.first[0], c.last[0]))


def outbound(email_id: str, sender: str, text: str, crm_by_email: dict[str, Customer], detector) -> Outbound:
    c = crm_by_email.get(sender.lower())
    if c is None:
        return Outbound(email_id, ("unrecognised_sender",), None, None, [], [])
    vault = Vault()
    masked, hits = known.mask_known(text, c, vault)
    m = detector.mask(masked, vault)
    message = prompts.user_message(m.payload, prompts.record_summary(c, vault))
    return Outbound(email_id, tuple(exitcheck.check(message, exit_record(c))), message, vault.to_json(),
                    [asdict(h) for h in hits], [asdict(d) for d in m.detections])


def inbound(email_id: str, repeat: int, reply_rec: dict, vault_json: dict) -> Inbound:
    vault = Vault.from_json(vault_json)
    if reply_rec["stop_reason"] != "end_turn":
        return Inbound(email_id, repeat, False, f"stop:{reply_rec['stop_reason']}", {}, "", "", ())
    try:
        data = json.loads(reply_rec["text"])
        triage = {k: data[k] for k in ("category", "urgency", "order", "action")}
        raw = data["reply"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return Inbound(email_id, repeat, False, "invalid_json", {}, "", "", ())
    text, _, _ = calc.apply(raw, vault)
    restored = restore(text, vault)
    return Inbound(email_id, repeat, True, "", triage, raw, restored,
                   tuple(draftcheck.check(raw, restored, vault)))


def contrast(text: str, shipped) -> str:
    return shipped.mask(text, Vault()).payload
