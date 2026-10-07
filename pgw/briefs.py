"""Seeded scenario briefs, the gold of every email (spec §3). Written by code, never by a model."""
import random
from dataclasses import dataclass, field

from pgw import names, policy
from pgw.crm import REFERENCE_DATE, Customer, Order, iban_gb, money, postcode, unused_phones

MIX = {"clean": 0.20, "high_risk": 0.15, "third_party": 0.30, "new_contact": 0.15, "nickname": 0.10}
UNMATCHED = 0.10
NONCLEAN = ("high_risk", "third_party", "new_contact", "nickname")
SELF_FORMS = ("full", "first", "initials", "title_last")
ELIGIBLE = {
    "refund": ("delivered", "dispatched"),
    "late_delivery": ("dispatched", "processing"),
    "damaged_or_wrong": ("delivered",),
    "change_of_address": ("processing", "dispatched"),
    "cancellation": ("processing", "dispatched"),
    "billing_question": ("processing", "dispatched", "delivered"),
    "complaint": ("processing", "dispatched", "delivered"),
    "account_access": (),
}


@dataclass(frozen=True)
class Plant:
    kind: str
    value: str                 # the exact string the email must contain
    parts: tuple[str, ...]     # any of these in what was sent means this value reached the model
    known: bool                # in the sender's record
    listed: bool               # a listed variant (known values only)
    high_risk: bool


@dataclass(frozen=True)
class Brief:
    email_id: str
    pid: str
    sender: str
    matched: bool
    case: dict
    gold: dict
    self_name_form: str
    plants: tuple[Plant, ...]
    style: dict
    hints: dict = field(default_factory=dict)


def self_name(c: Customer, form: str) -> str:
    return {"full": c.full, "first": c.first, "initials": f"{c.first[0]}. {c.last[0]}.",
            "title_last": f"{c.title} {c.last}", "nickname": names.NICKNAMES.get(c.first, "")}[form]


def _assign(n: int, rng: random.Random) -> tuple[dict[int, set[str]], set[int]]:
    idx = list(range(n))
    rng.shuffle(idx)
    n_clean = round(MIX["clean"] * n)
    rest = idx[n_clean:]
    kinds: dict[int, set[str]] = {i: set() for i in range(n)}
    for k in NONCLEAN:
        for i in rng.sample(rest, min(round(MIX[k] * n), len(rest))):
            kinds[i].add(k)
    for i in rest:
        if not kinds[i]:
            kinds[i].add(rng.choice(NONCLEAN))
    return kinds, set(rng.sample(range(n), round(UNMATCHED * n)))


def _case(c: Customer, rng: random.Random) -> tuple[policy.Case, str]:
    cats = list(policy.CATEGORIES)
    rng.shuffle(cats)
    for cat in cats:
        repeat = rng.random() < 0.15
        if cat == "account_access" or (cat == "complaint" and rng.random() < 0.5):
            return policy.Case(cat, None, repeat_contact=repeat), ""
        # A late order (dispatched, not yet delivered, and dispatched more than LATE_DAYS ago) is never a refund,
        # cancellation or address-change target: the customer would say it is late, making the email a
        # late_delivery hybrid with arguable gold.
        orders = [o for o in c.orders if o.status in ELIGIBLE[cat]
                  and (cat not in ("cancellation", "change_of_address", "refund") or o.status in ("processing", "delivered")
                       or (REFERENCE_DATE - o.dispatched).days <= policy.LATE_DAYS)]
        if not orders:
            continue
        o = rng.choice(orders)
        items = tuple(rng.sample(o.items, rng.randint(1, len(o.items)))) if cat in ("refund", "damaged_or_wrong") else ()
        reason = rng.choice(names.REFUND_REASONS) if cat == "refund" else ""
        wants = rng.choice(("refund", "replacement")) if cat == "damaged_or_wrong" else ""
        double = cat == "billing_question" and rng.random() < 0.4
        return policy.Case(cat, o, items, wants, double, repeat), reason
    raise AssertionError("unreachable: account_access needs no order")


def case_of(b: Brief, c: Customer) -> policy.Case:
    o: Order | None = next((o for o in c.orders if o.order_no == b.case["order_no"]), None)
    items = tuple(next(i for i in o.items if i.name == n) for n in b.case["items"]) if o else ()
    return policy.Case(b.case["category"], o, items, b.case["wants"], b.case["double_charge"],
                       b.case["repeat_contact"])


def _plants(c: Customer, case: policy.Case, kinds: set[str], form: str, rng: random.Random,
            spare: list[str], streets: set[str], postcodes: set[str], ibans: set[str]) -> tuple[tuple[Plant, ...], dict]:
    me = self_name(c, form)
    hints: dict = {}
    out = [Plant("self_name", me, (me,), True, form != "nickname", False)]
    if case.order and rng.random() < 0.8:
        out.append(Plant("order_no", case.order.order_no, (case.order.order_no,), True, True, False))
    if rng.random() < 0.15:
        out.append(Plant("account", c.account, (c.account,), True, True, False))
    if rng.random() < 0.15:
        out.append(Plant("phone_on_file", c.phone, (c.phone,), True, True, False))
    if case.items and rng.random() < 0.3:
        v = money(case.items[0].price)
        out.append(Plant("amount_on_file", v, (v,), True, True, False))
    if "third_party" in kinds:
        relation, gender = rng.choice(names.RELATIONS)
        pool = {"m": names.THIRD_PARTY_MALE, "f": names.THIRD_PARTY_FEMALE}.get(gender, names.THIRD_PARTY_NAMES)
        v = rng.choice(pool)
        out.append(Plant("third_party", v, (v,), False, False, False))
        hints["third_party_relation"] = relation
    if "new_contact" in kinds or case.category == "change_of_address":
        if case.category == "change_of_address" or rng.random() < 0.5:
            # Draw order street, postcode, town (as before); street and postcode differ from every CRM customer's,
            # the town from the sender's, so the new address carries no known value.
            while True:
                street = f"{rng.randrange(1, 120)} {rng.choice(names.STREETS)}"
                if street not in streets:
                    break
            while True:
                pc = postcode(rng)
                if pc not in postcodes:
                    break
            while True:
                town = rng.choice(names.TOWNS)
                if town != c.town:
                    break
            out.append(Plant("new_address", f"{street}, {town} {pc}", (street, pc), False, False, False))
        else:
            v = spare.pop(rng.randrange(len(spare)))
            out.append(Plant("new_phone", v, (v,), False, False, False))
    if "high_risk" in kinds:
        if rng.random() < 0.5:
            v = rng.choice(names.TEST_CARDS)
            out.append(Plant("card", v, (v,), False, False, True))
        else:
            while True:
                raw = iban_gb("SYNT", f"{rng.randrange(10**6):06d}", f"{rng.randrange(10**8):08d}")
                if raw not in ibans:
                    break
            v = " ".join(raw[i:i + 4] for i in range(0, len(raw), 4))
            out.append(Plant("iban", v, (v,), False, False, True))
    return tuple(out), hints


def _style(rng: random.Random) -> dict:
    return {"tone": rng.choice(("polite", "angry", "terse")),
            "register": rng.choice(("formal", "informal", "non-native English")),
            "typos": rng.random() < 0.3, "quoted_thread": rng.random() < 0.2, "signature": rng.random() < 0.7}


def build_briefs(crm: list[Customer], seed: int, n: int, pids: range, prefix: str) -> list[Brief]:
    rng = random.Random(seed)
    pool = [c for c in crm if int(c.pid[1:]) in pids]
    nick_pool = [c for c in pool if c.first in names.NICKNAMES]
    spare = unused_phones(crm)
    streets, postcodes, ibans = {x.street for x in crm}, {x.postcode for x in crm}, {x.iban for x in crm}
    kinds, unmatched = _assign(n, rng)
    out = []
    for i in range(n):
        k = kinds[i]
        c = rng.choice(nick_pool if "nickname" in k else pool)
        form = "nickname" if "nickname" in k else rng.choice(SELF_FORMS)
        if form == "initials" and c.first[0] + c.last[0] in names.DOTTED_ABBREVIATIONS:
            form = "full"
        case, reason = _case(c, rng)
        d = policy.decide(case)
        matched = i not in unmatched
        sender = c.email if matched else f"{c.first.lower()}.{c.last.lower()}@{rng.choice(names.WORK_DOMAINS)}"
        plants, hints = _plants(c, case, k, form, rng, spare, streets, postcodes, ibans)
        style = _style(rng)
        style["quoted_thread"] = style["quoted_thread"] and case.repeat_contact   # only a repeat contact quotes a reply
        out.append(Brief(
            email_id=f"{prefix}-{i:03d}", pid=c.pid, sender=sender, matched=matched,
            case={"category": case.category, "order_no": case.order.order_no if case.order else None,
                  "order_items": [it.name for it in case.order.items] if case.order else [],
                  "items": [it.name for it in case.items], "wants": case.wants,
                  "double_charge": case.double_charge, "repeat_contact": case.repeat_contact,
                  "reason": reason},
            gold={"category": case.category, "urgency": d.urgency, "action": d.action, "amount": d.amount,
                  "order_no": case.order.order_no if case.order else None},
            self_name_form=form, plants=plants, style=style, hints=hints))
    return out
