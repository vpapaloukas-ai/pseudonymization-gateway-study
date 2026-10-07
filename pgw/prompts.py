"""What the model under test receives (spec §5): one fixed system prompt carrying the company policy, and per
email the masked email plus a masked summary of the customer's record. Product names and dates stay in
clear: the reply needs them, and on their own they identify no one."""
from pgw import names, policy
from pgw.crm import REFERENCE_DATE, Customer, money
from pgw.vault import Vault

SYSTEM_PROMPT = f"""You triage customer-support emails for {names.COMPANY}, an online home-goods retailer, and draft a reply for a support agent to check and send.

Today is {REFERENCE_DATE.isoformat()}. Beside each date, the customer record gives how many days ago it was: these counts are calculated for you, so use them, not your own date arithmetic, for the policy's day limits.

Personal details in the email and in the customer record have been replaced by placeholders: a type and a number in square brackets, for example the customer's name, an order number, a price or another person's name. Rules for placeholders:
- Use only placeholders that appear in the customer record or in the email, and copy each one exactly as written, brackets and number included.
- Never guess what a placeholder stands for, never invent one, and never write a placeholder with a letter in place of its number.
- Never write a money figure, in digits or in words. To state an amount, use the placeholder that carries it in the customer record.
- When the amount is the sum of two or more placeholders, write them inside curly braces after SUM and a colon, separated by commas: {{SUM: [AMOUNT_a], [AMOUNT_b]}}, where a and b stand for the numbers of the placeholders you mean. It is calculated for you.
- When the amount is a difference, write {{DIFF: [AMOUNT_a], [AMOUNT_b]}}; it is calculated as the first minus the second, so the first must be the larger.
- Name the order the email is about by its order placeholder, in the reply as well as in the order field.
- Greet the customer by their first-name placeholder from the customer record.
- Write the reply with line breaks: the greeting, each paragraph and the sign-off on separate lines.
- The customer record holds no payment information: never claim what has already been charged or paid.
- Do not say who or what wrote the reply.
- When the action is full_refund or refund_item, the reply must state the amount refunded: for full_refund, the placeholder shown as that order's Total in the customer record; for refund_item, the placeholder of the item's price, or a SUM of the items' price placeholders when more than one item is refunded.

Company policy:
{policy.POLICY_TEXT}

Return JSON with:
- category: the category of the customer's issue.
- urgency: by the policy.
- order: the order placeholder from the customer record that the email is about, or an empty string if it is about no order.
- action: by the policy.
- reply: the draft reply to the customer, greeting them by their first-name placeholder, in plain text."""

TRIAGE_SCHEMA = {"type": "json_schema", "schema": {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": list(policy.CATEGORIES)},
        "urgency": {"type": "string", "enum": list(policy.URGENCIES)},
        "order": {"type": "string"},
        "action": {"type": "string", "enum": list(policy.ACTIONS)},
        "reply": {"type": "string"},
    },
    "required": ["category", "urgency", "order", "action", "reply"],
    "additionalProperties": False,
}}


def _days(d) -> str:
    n = (REFERENCE_DATE - d).days
    return "today" if n == 0 else "1 day ago" if n == 1 else f"{n} days ago"


def _dated(d) -> str:
    return f"{d.isoformat()} ({_days(d)})"


def record_summary(c: Customer, vault: Vault) -> str:
    """Only tokens already seeded by known.mask_known: the canonical strings match known.forms()."""
    lines = [f"Customer: {vault.token('CUSTOMER', c.full)} (first name: {vault.token('FIRST_NAME', c.first)})"]
    for o in c.orders:
        when = [f"placed {_dated(o.placed)}"]
        if o.dispatched:
            when.append(f"dispatched {_dated(o.dispatched)}")
        if o.delivered:
            when.append(f"delivered {_dated(o.delivered)}")
        items = "; ".join(f"{i.name} {vault.token('AMOUNT', money(i.price))}" for i in o.items)
        lines.append(f"Order {vault.token('ORDER', o.order_no)}: status {o.status}, {', '.join(when)}. "
                     f"Items: {items}. Total {vault.token('AMOUNT', money(o.total))} "
                     f"(the sum of the item prices; no delivery charges or taxes).")
    return "\n".join(lines)


def user_message(masked_email: str, summary: str) -> str:
    return f"Customer record:\n{summary}\n\nEmail:\n<<<\n{masked_email}\n>>>"
