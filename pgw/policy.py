"""The company's refund and triage policy, as rules (spec §5). The briefs' gold and the system prompt both
come from this module, so "correct" means the policy says so, not that someone judged it."""
from dataclasses import dataclass
from datetime import date

from pgw.crm import REFERENCE_DATE, Item, Order

CATEGORIES = ("refund", "late_delivery", "damaged_or_wrong", "change_of_address", "cancellation",
              "billing_question", "account_access", "complaint")
ACTIONS = ("refund_item", "full_refund", "resend", "update_address", "cancel", "explain", "escalate")
URGENCIES = ("low", "normal", "high")
RETURN_DAYS = 30
LATE_DAYS = 7


@dataclass(frozen=True)
class Case:
    category: str
    order: Order | None
    items: tuple[Item, ...] = ()
    wants: str = ""                 # "refund" or "replacement", for damaged_or_wrong
    double_charge: bool = False
    repeat_contact: bool = False


@dataclass(frozen=True)
class Decision:
    action: str
    urgency: str
    amount: int | None              # pence the reply must state, or None


def _action(c: Case, today: date) -> tuple[str, int | None]:
    o = c.order
    if c.category == "refund":
        if o and o.status == "delivered" and (today - o.delivered).days <= RETURN_DAYS:
            if set(c.items) == set(o.items):
                return "full_refund", o.total
            return "refund_item", sum(i.price for i in c.items)
        return "explain", None
    if c.category == "late_delivery":
        if o and o.status == "dispatched" and (today - o.dispatched).days > LATE_DAYS:
            return "resend", None
        return "explain", None
    if c.category == "damaged_or_wrong":
        if c.wants == "replacement":
            return "resend", None
        return "refund_item", sum(i.price for i in c.items)
    if c.category in ("change_of_address", "cancellation"):
        if o and o.status == "processing":
            return ("update_address" if c.category == "change_of_address" else "cancel"), None
        return "explain", None
    if c.category == "billing_question":
        return ("escalate" if c.double_charge else "explain"), None
    return "escalate", None          # account_access, complaint


def _urgency(c: Case, action: str) -> str:
    if c.category in ("damaged_or_wrong", "account_access") or c.double_charge or c.repeat_contact:
        return "high"
    if action == "update_address" or c.category == "billing_question":
        return "low"
    return "normal"


def decide(c: Case, today: date = REFERENCE_DATE) -> Decision:
    action, amount = _action(c, today)
    return Decision(action, _urgency(c, action), amount)


POLICY_TEXT = f"""\
Categories: {", ".join(CATEGORIES)}.
Actions: {", ".join(ACTIONS)}.
Urgencies: {", ".join(URGENCIES)}.

Action, by category:
- refund: if the order was delivered no more than {RETURN_DAYS} days ago, refund the items the customer asks
  about. If those are all the items in the order, the action is full_refund and the amount is the order
  total; otherwise the action is refund_item and the amount is the sum of those items' prices. If the order
  has not been delivered, or was delivered more than {RETURN_DAYS} days ago, the action is explain.
- late_delivery: if the order was dispatched more than {LATE_DAYS} days ago and has not been delivered, the
  action is resend; otherwise explain.
- damaged_or_wrong: if the customer wants a replacement, resend; otherwise refund_item, and the amount is
  the sum of the affected items' prices.
- change_of_address: if the order is still processing, update_address; otherwise explain.
- cancellation: if the order is still processing, cancel; otherwise explain.
- billing_question: if the customer was charged twice for one order, escalate; otherwise explain.
- account_access and complaint: escalate.

Urgency:
- high: any damaged_or_wrong or account_access email; a double charge; or the customer says they have
  contacted us before about the same issue.
- low, when not high: an address change on an order that is still processing, or any billing_question.
- normal: everything else."""
