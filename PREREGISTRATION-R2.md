# Pseudonymization gateway study: pre-registration

## 1. Header

- **Title:** AI on a support inbox, in three layers. A two-way pseudonymization gateway seeded from the sender's CRM
  record, an exit check, and one model doing triage and reply drafts, on synthetic English support emails.
- **Date of this pre-registration:** 2026-10-06. The test seed below is that date, by rule.
- **Status:** pre-registration, before the test batch exists. No test email has been generated, and no model has
  seen anything built at the test seed (section 5.4).
- **Frozen at:** the 23 script hashes and 9 package versions in `FROZEN.json`, quoted in full in section 11. They
  are committed in the same commit as this file, and they hash the code in that commit. Before a scored step the
  runner hashes its own scripts and reads the installed package versions, and it refuses to run if any of them
  differs from `FROZEN.json` (section 11).
- **What the date shows:** the evidence that this plan preceded the results is the public commit that adds this
  file (push 1). The test batch is generated only after that commit is public (section 5.5). Any change after it
  is a dated amendment (section 12).
- **Design:** a private design document ("the spec" below). It is not published; every passage of it that this
  pre-registration relies on is quoted here, and the frozen code is the rule wherever the two differ.

Every path in this file is relative to this directory. Every person, address, account, card, order and company in
the data is synthetic (spec §3).

---

## 2. Question

From the spec, §1 (quoted):

> **The question.** For a two-way pseudonymization gateway that fills its vault from the sender's CRM
> record, run on synthetic English support emails written by a separate model, with one model doing triage
> and reply drafts:
>
> 1. Does any value the company holds **on record** leave the perimeter?
> 2. Of the values it **does not** hold, how many are caught or held?
> 3. Does the work come back right after restore?
> 4. What does it cost, counted as clean emails held for review?
>
> **"Known" means:** the fields of the *sender's* CRM record, plus the variant list in §4 step 2, which the
> pre-registration fixes. A third party the email mentions is **unknown**, even if that person is another
> customer in the CRM. Matching every CRM name against every email would be unrealistic at scale, and it
> would hit common words ("Will", "Rose").

The variant list the spec refers to is fixed in section 6.1. It is narrower than spec §4 step 2 on initials
(dotted, uppercase, with the final dot), and the first name has its own token.

---

## 3. The three layers

From the spec, §1 (quoted):

> 1. **Contract.** The vendor processes the data as the company's processor, with no training on it,
>    zero retention and a chosen region. This is a deployment choice, and **the PoC does not measure
>    it.** The post names what it should contain and links the vendor's published terms. The PoC uses
>    synthetic data [...].
> 2. **Gateway.** Measured.
> 3. **Exit check.** Measured.

**The contract layer is not measured.** No number in this study describes it. The study uses synthetic data only;
what a deployment owes under data-protection law is outside it.

**What such a contract has to contain** was read at the source on 2026-10-06 (GDPR, Regulation (EU) 2016/679, Art.
28(1) and 28(3), EUR-Lex, OJ L 119, 4.5.2016). Where the vendor acts as a processor, Art. 28(3) requires the
contract to set out: the subject-matter, duration, nature and purpose of the processing; the types of data and the
categories of data subjects; and points (a) to (h), namely documented instructions (including on transfers),
confidentiality, the Art. 32 measures, the conditions for engaging another processor, help with data-subject
requests and with Arts 32 to 36, deletion or return at the end, and information and audits. Art. 28(1) requires a
processor "providing sufficient guarantees".

The **lawful basis** (Art. 6(1)) and **international transfers** (Chapter V) are deployment-specific: they depend on
the operator, its customers, its purpose and where the vendor processes. This study does not settle either.

**The gateway** (section 6.1 to 6.3) replaces what the company holds on the sender with tokens, using the sender's
CRM record and a variant list, then runs a configured detector over the rest. **The exit check** (section 6.4) is a
separate pass over exactly the message that would leave, with no code shared with the gateway; it holds the email
on any known value, any high-risk value and any leftover pattern. After the model call, **calculations** happen
locally (section 6.5) and the **draft check** holds a restored reply with an invented, leftover or malformed token,
a bad expression or a money figure the model typed (section 6.6). A person sends every reply.

---

## 4. Configuration

### 4.1 Bounds

One configuration, measured and described: one model under test (`claude-sonnet-5-5`), one email writer and auditor
(`claude-opus-5-5`), Presidio 2.2.364 configured as below, English only, synthetic data, single-turn, one set of
prompts and call parameters. Every number this study reports is a measurement of this configuration on these
emails. No significance tests are run (spec §6).

### 4.2 Models, as the canaries reported them

- **Model under test:** `claude-sonnet-5-5`, effort `high`. On 2026-10-05 at 15:41:42 UTC the Models API, asked for
  `claude-sonnet-5-5` by ID (`models.retrieve`), returned id `claude-sonnet-5-5`, display name "Claude Sonnet 5.5",
  and a test call reported model `claude-sonnet-5-5`, stop `end_turn` (request `req_011CfjLvsUK8Tqfq3Jsncht2`,
  `notes/canary-r2-2026-10-05.json`).
- **Email writer and auditor:** `claude-opus-5-5`, effort `medium` for both. On 2026-10-05 at 15:41:35 UTC the Models
  API returned id `claude-opus-5-5`, display name "Claude Opus 5.5", and a test call reported model
  `claude-opus-5-5`, stop `end_turn` (request `req_011CfjLvNnA2F4mNG9pUE5zu`, same file).
- **At every launch** of a live step the runner repeats the canary, saves it in the output directory, and refuses
  to call the model if the Models API resolves the ID to a different id (exit 3). Every reply records the model the
  API reported, and `summary.json` counts them (`models_reported`). A reply reporting another ID is not refused by
  the runner; `models_reported` would show it, and the results would name whatever the API reported.

### 4.3 Call parameters

- SDK `anthropic` 1.11.0; client constructed with `max_retries=0`, so the SDK never retries.
- `client.messages.create`, not streamed: the system prompt plus one user message, no tools.
- `max_tokens=16000`; `output_config={"effort": <effort>, "format": <schema>}`, where the schema is the JSON
  schema of section 4.6 (structured output).
- No `thinking` parameter, so each model's default applies. No `temperature`, `top_p` or `top_k`. No
  `fallbacks`: a fallback would answer with a different model.
- **Failures.** An API error stops the run (`ServiceStop`) instead of being scored, and a relaunch resumes at the
  next unfinished call. An `end_turn` with no text is treated as a service error. Any other stop reason (a refusal,
  `max_tokens`) is recorded with its reason, scored as a `no_answer` hold, and never re-asked. A reply that is not
  valid JSON for the schema is scored the same way (`invalid_json`).
- Every reply records the request ID, the reported model, the stop reason, the token counts, the full raw response,
  and the SHA-256 of the exact user message. Restore refuses a reply bound to a different message.

From `pgw/model_call.py` (extracted segments, in file order):

```python
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
```

### 4.4 Presidio: as shipped (contrast row) and configured (detector)

- `presidio-analyzer` 2.2.364 and `presidio-anonymizer` 2.2.364, with spaCy 3.8.16 and the model `en_core_web_lg`
  3.8.0 (loaded by Presidio's default configuration). Other pinned packages: `tldextract` 5.4.0, `phonenumbers`
  9.0.40, `regex` 2026.9.29. Python 3.13.2. The full environment is `requirements.lock`.
- **As shipped (the contrast row):** `AnalyzerEngine()` with no arguments, default recognisers, no threshold, no
  CRM and no exit check, plus one custom operator that writes `[TYPE_n]` tokens. It runs on the same test emails,
  makes no model call, and counts known and high-risk values in what would have been sent (spec §6).
- **Configured (the gateway's step 3):** its own registry, the built-in recognisers listed in `BUILT_IN`, six
  custom pattern recognisers, score threshold 0.4. Organisations and dates stay in clear by design.
- **Ties are settled by rule** before the anonymizer (`_resolve_ties`): for each exact span the highest score wins;
  at equal score our own pattern's entity (`CUSTOM`) wins over a built-in one, then the alphabetically first entity
  type; the results reach the anonymizer in a total order. Presidio 2.2.364 orders its results through
  `list(set(...))`, which varies between processes, and its anonymizer keeps the later of two same-span, same-score
  results, so without this rule a token's type could depend on the process. `detections` are sorted by
  `(start, end, entity_type, score)`. The shipped baseline is left as shipped; a tie there changes only a token's
  type, and the contrast counts values present or not.
- The configured entity list, the threshold and six probe sentences with their masked output are pinned in
  `notes/detector-configured.json` (re-measured identical on 2026-10-06), and `tests/test_presidio_pin.py` asserts
  the installed analyzer's behaviour, so a version change fails a test instead of moving the numbers. Two probe
  outputs show the layer's measured behaviour: "Send it to 4 Mill Lane, Kendal LA9 4RT." becomes "Send it to 4
  [PERSON_1], [LOCATION_1]." (the street read as a person, the house number left), and "Dispatched 2026-09-14 by
  Harrowfield Logistics Ltd." is unchanged.

From `pgw/detector.py` (extracted segments):

```python
BUILT_IN = ("PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "LOCATION", "IBAN_CODE", "CREDIT_CARD")

CUSTOM = (
    ("UK_PHONE", r"(?<![\d+])(?:(?:\+|00)\s?44\s?(?:\(0\)\s?)?|0)7\d{3}[\s-]?\d{3}[\s-]?\d{3}(?!\d)", 0.85),
    ("IBAN_CODE", r"\bGB\d{2}\s?[A-Z]{4}(?:\s?\d{4}){3}\s?\d{2}\b", 0.85),
    ("ORDER_NUMBER", r"\bBW-?\s?\d{6}\b", 0.85),
    ("ACCOUNT_NUMBER", r"\bBWC\s?\d{7}\b", 0.85),
    ("AMOUNT", r"£\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})?(?!\d)", 0.85),
    ("UK_POSTCODE", r"\b[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}\b", 0.6),
)

_CUSTOM_TYPES = frozenset(e for e, _, _ in CUSTOM)

THRESHOLD = 0.4   # fixed on the dev batch before the freeze (spec §4 step 3); a change is a dev-run ruling

def _resolve_ties(results: list) -> list:
    """Presidio hands results over in an order that varies between processes (it builds them through set()), and
    its anonymizer keeps the LAST of two same-span same-score results (has_conflict drops an equal-span result whose
    score is <= a later one's). So the tie is settled here, by rule: per
    exact (start, end) keep the highest score; at equal score prefer our own entity types over built-ins, then the
    alphabetically first entity_type. What is returned has a total order (start, end, -score, entity_type)."""
    best: dict = {}
    for r in results:
        key = (r.start, r.end)
        rank = (-r.score, r.entity_type not in _CUSTOM_TYPES, r.entity_type)
        if key not in best or rank < best[key][0]:
            best[key] = (rank, r)
    return sorted((r for _, r in best.values()), key=lambda r: (r.start, r.end, -r.score, r.entity_type))

class ConfiguredDetector:
    def __init__(self, nlp_engine=None) -> None:
        if nlp_engine is None:
            self.analyzer = AnalyzerEngine()
        else:
            registry = RecognizerRegistry()
            registry.load_predefined_recognizers(languages=["en"])
            self.analyzer = AnalyzerEngine(registry=registry, nlp_engine=nlp_engine, supported_languages=["en"])
        for entity, regex, score in CUSTOM:
            self.analyzer.registry.add_recognizer(PatternRecognizer(
                supported_entity=entity, name=f"pgw_{entity.lower()}",
                patterns=[Pattern(name=entity.lower(), regex=regex, score=score)]))
        self.anonymizer = AnonymizerEngine()
        self.entities = sorted(set(BUILT_IN) | {e for e, _, _ in CUSTOM})

    def mask(self, text: str, vault: Vault) -> Masked:
        taken = [(m.start(), m.end()) for m in TOKEN_RE.finditer(text)]
        results = [r for r in self.analyzer.analyze(text=text, language="en", entities=self.entities,
                                                    score_threshold=THRESHOLD)
                   if all(r.end <= s or r.start >= e for s, e in taken)]
        detections = tuple(sorted((Detection(r.entity_type, r.start, r.end, r.score) for r in results),
                                  key=lambda d: (d.start, d.end, d.entity_type, d.score)))
        operators = {e: OperatorConfig("custom", {"lambda": partial(vault.token, e)}) for e in self.entities}
        operators["DEFAULT"] = OperatorConfig("custom", {"lambda": partial(vault.token, "PII")})
        out = self.anonymizer.anonymize(text=text, analyzer_results=_resolve_ties(results), operators=operators)
        return Masked(out.text, detections)
```

From `pgw/baseline.py`:

```python
class ShippedGateway:
    def __init__(self) -> None:
        self.analyzer = AnalyzerEngine()
        self.anonymizer = AnonymizerEngine()
        self.entities = sorted(self.analyzer.get_supported_entities(language="en"))

    def mask(self, text: str, vault: Vault) -> Masked:
        results = self.analyzer.analyze(text=text, language="en")
        detections = tuple(sorted((Detection(r.entity_type, r.start, r.end, r.score) for r in results),
                                  key=lambda d: (d.start, d.end)))
        operators = {e: OperatorConfig("custom", {"lambda": partial(vault.token, e)}) for e in self.entities}
        operators["DEFAULT"] = OperatorConfig("custom", {"lambda": partial(vault.token, "PII")})
        out = self.anonymizer.anonymize(text=text, analyzer_results=results, operators=operators)
        return Masked(out.text, detections)
```

### 4.5 The model under test: system prompt, verbatim

`prompts.SYSTEM_PROMPT`, as rendered (it embeds the policy text of section 4.7 after "Company policy:"):

```text
You triage customer-support emails for Brightwell Home, an online home-goods retailer, and draft a reply for a support agent to check and send.

Today is 2026-10-05. Beside each date, the customer record gives how many days ago it was: these counts are calculated for you, so use them, not your own date arithmetic, for the policy's day limits.

Personal details in the email and in the customer record have been replaced by placeholders: a type and a number in square brackets, for example the customer's name, an order number, a price or another person's name. Rules for placeholders:
- Use only placeholders that appear in the customer record or in the email, and copy each one exactly as written, brackets and number included.
- Never guess what a placeholder stands for, never invent one, and never write a placeholder with a letter in place of its number.
- Never write a money figure, in digits or in words. To state an amount, use the placeholder that carries it in the customer record.
- When the amount is the sum of two or more placeholders, write them inside curly braces after SUM and a colon, separated by commas: {SUM: [AMOUNT_a], [AMOUNT_b]}, where a and b stand for the numbers of the placeholders you mean. It is calculated for you.
- When the amount is a difference, write {DIFF: [AMOUNT_a], [AMOUNT_b]}; it is calculated as the first minus the second, so the first must be the larger.
- Name the order the email is about by its order placeholder, in the reply as well as in the order field.
- Greet the customer by their first-name placeholder from the customer record.
- Write the reply with line breaks: the greeting, each paragraph and the sign-off on separate lines.
- The customer record holds no payment information: never claim what has already been charged or paid.
- Do not say who or what wrote the reply.
- When the action is full_refund or refund_item, the reply must state the amount refunded: for full_refund, the placeholder shown as that order's Total in the customer record; for refund_item, the placeholder of the item's price, or a SUM of the items' price placeholders when more than one item is refunded.

Company policy:
Categories: refund, late_delivery, damaged_or_wrong, change_of_address, cancellation, billing_question, account_access, complaint.
Actions: refund_item, full_refund, resend, update_address, cancel, explain, escalate.
Urgencies: low, normal, high.

Action, by category:
- refund: if the order was delivered no more than 30 days ago, refund the items the customer asks
  about. If those are all the items in the order, the action is full_refund and the amount is the order
  total; otherwise the action is refund_item and the amount is the sum of those items' prices. If the order
  has not been delivered, or was delivered more than 30 days ago, the action is explain.
- late_delivery: if the order was dispatched more than 7 days ago and has not been delivered, the
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
- normal: everything else.

Return JSON with:
- category: the category of the customer's issue.
- urgency: by the policy.
- order: the order placeholder from the customer record that the email is about, or an empty string if it is about no order.
- action: by the policy.
- reply: the draft reply to the customer, greeting them by their first-name placeholder, in plain text.
```

### 4.6 The model under test: output schema and user message

`prompts.TRIAGE_SCHEMA`, as sent in `output_config["format"]`:

```json
{
  "type": "json_schema",
  "schema": {
    "type": "object",
    "properties": {
      "category": {
        "type": "string",
        "enum": [
          "refund",
          "late_delivery",
          "damaged_or_wrong",
          "change_of_address",
          "cancellation",
          "billing_question",
          "account_access",
          "complaint"
        ]
      },
      "urgency": {
        "type": "string",
        "enum": [
          "low",
          "normal",
          "high"
        ]
      },
      "order": {
        "type": "string"
      },
      "action": {
        "type": "string",
        "enum": [
          "refund_item",
          "full_refund",
          "resend",
          "update_address",
          "cancel",
          "explain",
          "escalate"
        ]
      },
      "reply": {
        "type": "string"
      }
    },
    "required": [
      "category",
      "urgency",
      "order",
      "action",
      "reply"
    ],
    "additionalProperties": false
  }
}
```

The `order` field is a string, and the prompt asks for an empty string when the email is about no order. The spec
(§5) says `null`; the scorer compares against `""` in that case (section 7.2).

The user message is the masked customer record followed by the masked email. From `pgw/prompts.py`:

```python
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
```

Product names and dates stay in clear (spec §5). Every amount is a token. Each date carries its elapsed days,
computed in code, so the model does no date arithmetic for the policy's day limits.

### 4.7 The policy, verbatim

`policy.POLICY_TEXT`, which is also the "Company policy:" block of the system prompt:

```text
Categories: refund, late_delivery, damaged_or_wrong, change_of_address, cancellation, billing_question, account_access, complaint.
Actions: refund_item, full_refund, resend, update_address, cancel, explain, escalate.
Urgencies: low, normal, high.

Action, by category:
- refund: if the order was delivered no more than 30 days ago, refund the items the customer asks
  about. If those are all the items in the order, the action is full_refund and the amount is the order
  total; otherwise the action is refund_item and the amount is the sum of those items' prices. If the order
  has not been delivered, or was delivered more than 30 days ago, the action is explain.
- late_delivery: if the order was dispatched more than 7 days ago and has not been delivered, the
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
- normal: everything else.
```

The briefs' gold comes from the same module, so "correct" means the policy says so. From `pgw/policy.py`:

```python
CATEGORIES = ("refund", "late_delivery", "damaged_or_wrong", "change_of_address", "cancellation",
              "billing_question", "account_access", "complaint")

ACTIONS = ("refund_item", "full_refund", "resend", "update_address", "cancel", "explain", "escalate")

URGENCIES = ("low", "normal", "high")

RETURN_DAYS = 30

LATE_DAYS = 7

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
```

### 4.8 The email writer: system prompt, schema and per-email message, verbatim

`emailgen.GEN_SYSTEM`:

```text
You write realistic synthetic customer emails to the support team of Brightwell Home, an online home-goods retailer, for testing software. Every detail you are given is invented. Write one email that follows the brief.

Rules:
- Include every string listed under "Must include, exactly" character for character.
- Do not add any other names, email addresses, phone numbers, postal addresses, account or order numbers, card numbers, bank details or money amounts.
- Never mention that the email is synthetic or a test.
- Return JSON with "subject" and "body".
```

`emailgen.EMAIL_SCHEMA`:

```json
{
  "type": "json_schema",
  "schema": {
    "type": "object",
    "properties": {
      "subject": {
        "type": "string"
      },
      "body": {
        "type": "string"
      }
    },
    "required": [
      "subject",
      "body"
    ],
    "additionalProperties": false
  }
}
```

The per-email user message is built from the brief and the parts of the sender's record the customer would know.
From `pgw/emailgen.py` (extracted segments, in file order):

```python
GEN_MODEL = "claude-opus-5-5"     # spec §2; its ID is checked against the API's model list (Task 13)

GEN_EFFORT = "medium"

MAX_ATTEMPTS = 3

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
```

An attempt is accepted only if every planted string appears exactly, at word boundaries, in the subject or body
(`check_exact`). A rejected attempt is regenerated, up to `MAX_ATTEMPTS` = 3; every attempt is recorded in
`generation.jsonl` and published. A brief with no accepted attempt is dropped and counted (`generation.dropped`).

### 4.9 The auditor: system prompt and schema, verbatim

`audit.AUDIT_SYSTEM`:

```text
You audit a synthetic customer email for personal and payment details. List every person's name (full or partial, including nicknames and initials), email address, phone number, postal address or part of one (street, town, postcode), account or order number, card number, bank detail and money amount that appears in the email. Copy each exactly as it appears. Do not list the company name "Brightwell Home" or product names. Return JSON with "items", a list of objects with "kind" and "text".
```

`audit.AUDIT_SCHEMA`:

```json
{
  "type": "json_schema",
  "schema": {
    "type": "object",
    "properties": {
      "items": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "kind": {
              "type": "string",
              "enum": [
                "name",
                "email",
                "phone",
                "address",
                "postcode",
                "account",
                "order",
                "card",
                "bank",
                "amount",
                "other"
              ]
            },
            "text": {
              "type": "string"
            }
          },
          "required": [
            "kind",
            "text"
          ],
          "additionalProperties": false
        }
      }
    },
    "required": [
      "items"
    ],
    "additionalProperties": false
  }
}
```

How the audit and a pattern scan become gold is in section 6.7.

---

## 5. Data

### 5.1 The company and its CRM

- One synthetic CRM: `build_crm(CRM_SEED)` with `CRM_SEED` = 1 and 200 customers, C000 to C199. Every customer has
  an account number, title, name, email, phone (UK range reserved for fiction, `07700 900000` to `07700 900999`), a
  street, town and postcode, an IBAN with bank code `SYNT` and valid check digits, and 1 to 3 orders.
- The inbox's today is `REFERENCE_DATE` = 2026-10-05, a Monday.
- **Test senders** are C100 to C199 (`TEST_PIDS`). The test batch draws its senders only from them; the other half of
  the CRM is never a test sender (spec §3's split).
- **Orders, all 200 customers:** 384 orders; 289 delivered, 33 dispatched and not delivered, 62 processing. A
  **late** order (dispatched, not delivered, dispatched more than `LATE_DAYS` = 7 days ago) is 13 of the 198 orders of
  the test senders (6.6%).
- Names, towns, postcodes and the company's name and domain may coincide with real ones. Postcodes use real UK
  outward areas with random inward parts. Card numbers are published test numbers only: the four in
  `names.TEST_CARDS` were each found on Adyen's or Stripe's published test-card page on 2026-10-06.

From `pgw/crm.py` and `pgw/names.py`:

```python
REFERENCE_DATE = date(2026, 10, 5)   # "today" for the inbox; the system prompt states it (spec §5)

CRM_SEED = 1                          # one company, one CRM; dev and test draw different senders (spec §3)

DEV_PIDS = range(0, 100)

TEST_PIDS = range(100, 200)

WORD_NAME_PIDS = (60, 61, 62, 63, 160, 161, 162, 163)
```

```python
"""Static lists for the synthetic CRM (spec §3). No entry appears in two name lists."""

FIRST_NAMES = [
    "Ada", "Ben", "Chloe", "Daniel", "Eleanor", "Farid", "Gemma", "Harry", "Isla", "James",
    "Kofi", "Laura", "Mohammed", "Nina", "Oliver", "Priya", "Quentin", "Ruth", "Samuel", "Tara",
    "Umar", "Vera", "Wesley", "Xenia", "Yusuf", "Zara", "Alistair", "Bethany", "Callum", "Deborah",
    "Ewan", "Fiona", "Gareth", "Hannah", "Imran", "Joanna", "Kieran", "Leah", "Martin", "Niamh",
]

# First names that are also ordinary English words: the gateway matches them only when capitalised.
WORD_FIRST_NAMES = ["Rose", "Mark", "Will", "Grace", "Hope", "Bill", "Faith", "Joy"]

LAST_NAMES = [
    "Okafor", "Hale", "Whitmore", "Patel", "Brennan", "Ashby", "Calloway", "Dunmore", "Ellison",
    "Fairbairn", "Gallagher", "Hargreaves", "Iqbal", "Jennings", "Kavanagh", "Lindqvist", "Mbeki",
    "Nakamura", "Osei", "Pemberton", "Quigley", "Radcliffe", "Sutherland", "Thackeray", "Underwood",
    "Vasquez", "Wainwright", "Yardley", "Zielinski", "Abernethy", "Blackwood", "Carrick", "Delacroix",
    "Esposito", "Forsythe", "Goldsmith", "Holloway", "Ibrahim", "Jarvis", "Kowalski", "Lockhart",
    "Mortimer", "Nightingale", "Ollerenshaw", "Prendergast", "Rahman", "Sinclair", "Trevelyan",
    "Uddin", "Vickers", "Westbrook", "Achebe", "Barraclough", "Cheung", "Dimitriou", "Eriksen",
    "Fitzgerald", "Gunawardena", "Hutchinson", "Ingram",
]

TITLES = ["Mr", "Ms", "Dr", "Mx"]

TOWNS = [
    "Whitby", "Ludlow", "Hexham", "Kendal", "Bude", "Penrith", "Malton", "Totnes", "Frome", "Morpeth",
    "Ripon", "Alnwick", "Bakewell", "Ledbury", "Thirsk", "Beverley", "Skipton", "Dorking", "Romsey",
    "Sherborne", "Tewkesbury", "Kelso", "Oakham", "Lewes", "Bridport", "Keswick", "Buxton", "Stamford",
    "Marlow", "Hythe",
]

# Short forms a customer may sign with. Deliberately NOT in the gateway's variant list (spec §3, §6).
NICKNAMES = {
    "Daniel": "Dan", "Eleanor": "Nell", "James": "Jim", "Mohammed": "Mo", "Oliver": "Ollie",
    "Samuel": "Sam", "Alistair": "Ali", "Bethany": "Beth", "Deborah": "Debs", "Joanna": "Jo",
    "Martin": "Marty", "Fiona": "Fi",
}

# Third parties a customer mentions ("my husband John"): unknown to the gateway (spec §1).
THIRD_PARTY_MALE = ["John", "Peter", "David", "Robert", "Michael"]
THIRD_PARTY_FEMALE = ["Margaret", "Susan", "Helen", "Anne", "Carol"]
THIRD_PARTY_NAMES = THIRD_PARTY_MALE + THIRD_PARTY_FEMALE
RELATIONS = [("my husband", "m"), ("my wife", "f"), ("my neighbour", None), ("my son", "m"), ("my daughter", "f"),
             ("my colleague", None)]

# Why a refund-case customer wants their money back: never damage, never a wrong item (that is damaged_or_wrong).
REFUND_REASONS = ["changed their mind", "it does not fit the space they had in mind", "it was a duplicate gift",
                  "they no longer need it", "the colour does not suit the room"]

STREETS = [
    "Larkspur Road", "Mill Lane", "Church Street", "Station Road", "Orchard Close", "Victoria Terrace",
    "Elm Grove", "Kingsway", "Park Avenue", "Rowan Drive", "Meadow View", "Quarry Hill",
]

# Invented consumer and work domains. They may coincide with real ones; the README says so (spec §3).
MAIL_DOMAINS = ["postbox-mail.co.uk", "letterpost.co.uk", "homemail-uk.co.uk", "inboxly.co.uk"]
WORK_DOMAINS = ["harrowfield-logistics.co.uk", "calderbrook-consulting.co.uk", "northgate-engineering.co.uk",
                "kestrel-health.co.uk", "thornbury-retail.co.uk"]

COMPANY = "Brightwell Home"
COMPANY_DOMAIN = "brightwellhome.co.uk"

# (product, price in pence). Product names stay in clear (spec §5).
PRODUCTS = [
    ("Oak side table", 8900), ("Linen cushion cover", 1800), ("Ceramic table lamp", 4500),
    ("Wool throw", 6500), ("Bamboo bath mat", 2200), ("Glass storage jars, set of 3", 2400),
    ("Cotton duvet cover", 5500), ("Round wall mirror", 7900), ("Jute rug", 12000),
    ("Copper kettle", 6900), ("Stoneware mug set", 3200), ("Rattan laundry basket", 3900),
]

# Published payment-card TEST numbers only (spec §3). Their source is checked in Task 14 (spec §13.4).
TEST_CARDS = ["4111 1111 1111 1111", "5555 5555 5555 4444", "4242 4242 4242 4242", "3782 822463 10005"]

# Initials pairs that are also common dotted abbreviations ("U.K.", "e.g.", "P.S.", "A.I."): a customer with one of
# these initials gets no initials form, or ordinary prose would be masked as the customer (measured 2026-10-05).
DOTTED_ABBREVIATIONS = ("UK", "US", "EG", "IE", "AM", "PM", "NB", "AI", "PS", "OK", "TV", "ID")
```

### 5.2 Briefs: the gold of every email

Every email starts from a brief written by seeded code, never by a model (`pgw/briefs.py`). A brief fixes the case
(category, order, items, what the customer wants, double charge, repeat contact), the gold (category, urgency,
action, amount, order, computed by `policy.decide`), how the customer names themselves, the planted values, and the
style. Briefs and the CRM regenerate byte for byte from their seeds (`tests/test_briefs.py`, `tests/test_crm.py`).

**The mix constants are assignment floors, not realised shares.** From `pgw/briefs.py`:

```python
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
```

`_assign` first reserves `round(0.20 × n)` slots that receive no assigned kind ("clean" slots), then gives each
non-clean kind to `round(MIX[kind] × n)` of the remaining slots, then gives every remaining slot that received no
kind one more kind at random. So each non-clean kind's count is a floor: at least `round(MIX[kind] × n)` briefs carry
it (45, 90, 45 and 30 of 300), and the realised counts are higher. A change of address always plants a new address,
whatever its slot. `round(UNMATCHED × n)` senders are
replaced by an unmatched work address. The realised counts at the test seed are in section 5.3.

**Two definitions of a clean email** (`pgw/score.py`, section 6.8):
- **nothing planted** (`nothing_planted`): the sender is matched, and every plant is known and listed. No third
  party, no new contact, no card or IBAN, no nickname. This is the spec's "nothing planted" set and the
  denominator of `holds.false`.
- **clean** (`is_clean`): nothing planted, and the audit found nothing unplanned. This is the denominator of
  `holds.false_clean`.

Neither is the same as the MIX "clean" slot: a clean slot can still carry a new address (change of address) or an
unmatched sender.

### 5.3 The test batch: size, seed and realised mix

- **Test seed:** `TEST_SEED` = **20261006** (`pgw/run.py`), the date of this pre-registration as an integer
  `YYYYMMDD`, by rule.
- **Size:** 300 briefs, `build_briefs(build_crm(1), 20261006, 300, TEST_PIDS, "test")`, 93 distinct test customers
  of 100.
- **Realised mix**, computed on 2026-10-06 from the briefs only (no email, no model; the computation is
  deterministic, and anyone can repeat it from the code at push 1):

| Item | Count of 300 briefs | Expected to reach the model |
|---|---|---|
| unmatched sender | 30 | 0 (held at step 1) |
| card plant | 31 | 0 (held at the exit check) |
| IBAN plant | 41 | 0 (held at the exit check) |
| any card or IBAN plant, matched sender | 64 | 0 |
| third-party name plant | 114 | |
| new phone plant | 38 | |
| new address plant | 44 (18 of them on change of address) | |
| nickname as self-name | 53 | |
| any unknown plant (third party, new phone, new address, card, IBAN) | 210 | |
| nothing planted (`nothing_planted`) | 49 | |
| **expected to reach the model** (matched sender, no card or IBAN plant) | **206** | 206 |

"Expected to reach the model" counts what the brief alone predicts. An email is also held if the exit check finds a
known value or a leftover pattern, or if its brief has no accepted email.

Known plants: self-name 300 (full name 67, first name 66, title and surname 61, initials 53, nickname 53), order
number 163, account number 45, phone on file 59, an item's price 23.

| Category | All 300 | Expected to reach the model (206) |
|---|---|---|
| refund | 39 | 25 |
| late_delivery | 23 | 15 |
| damaged_or_wrong | 40 | 27 |
| change_of_address | 18 | 12 |
| cancellation | 10 | 8 |
| billing_question | 61 | 41 |
| account_access | 57 | 42 |
| complaint | 52 | 36 |

| Gold action | All 300 | Expected to reach the model (206) |
|---|---|---|
| escalate | 135 | 93 |
| explain | 77 | 52 |
| refund_item | 27 | 15 |
| resend | 27 | 21 |
| update_address | 16 | 11 |
| full_refund | 9 | 7 |
| cancel | 9 | 7 |

- Gold urgency: high 141, normal 115, low 44 (expected to reach the model: 97, 78, 31).
- Gold order: none in 77 briefs (57 expected to reach the model).
- Case order status: delivered 138, processing 54, dispatched and late 20, dispatched and not late 11, no order 77.
- Late-delivery `resend` gold: 6 (3 expected to reach the model). Double charge: 26 (15). Repeat contact: 37 (28).
  Complaints with an order 32, without 20. Damaged items: replacement wanted 21, refund 19.
- Refunds: 17 inside the 30-day window (full_refund or refund_item), 19 on deliveries more than 30 days old, and 3
  on recently dispatched, undelivered orders, which the writer is told "They have not received it yet." (2 expected
  to reach the model).
- Style: tone polite 106, terse 108, angry 86; register formal 105, informal 105, non-native English 90; typos 89;
  quoted earlier reply 6; signature 208.
- Test-half customers with no initials form (initials pair on the dotted-abbreviation stoplist): C129, C145, C194.
  Test-half customers with a word first name (matched case-sensitively): C160 to C163.
- **These counts are restated over the accepted test emails** after generation, beside this table. A dropped brief
  leaves every denominator; `generation` in `summary.json` counts drops.

### 5.4 Who has built briefs at test-half seeds, and what was never done

The test seed is fixed by rule as this pre-registration's date. Seeded code has built test-half **briefs** (no
emails, no model calls) at these seeds before this commit, for measurement only:
- seeds 2, 3 and 4: by the test suite (`tests/test_briefs.py`), on every run since the briefs existed;
- seeds 5 and 6: by a code-review probe (2026-10-06);
- seeds 20261005, 20261006 and 20261007: by a scratch script on 2026-10-05, measuring whether a new address could
  carry the sender's own town. **20261006 is the test seed:** its briefs were built then, by the code as it stood that
  day, and no email was generated from them;
- 20261006 again on 2026-10-06, for section 5.3's counts, with the frozen code.

No email has been generated at the test seed, and no message built at it has been sent to any model.

### 5.5 How the test batch and the scored run will be made

In this order, each step after the one before:
1. This file, `FROZEN.json` and the code they hash are pushed to the public repository (push 1).
2. The test batch is generated once: `python -m pgw.run generate --batch test --out <dir> --writer live --frozen
   FROZEN.json`. The runner refuses a fake writer under `--frozen`, refuses a directory that already holds a batch,
   and records `frozen: true` and `writer: live` in its manifests. `batch.json` records the SHA-256 of every batch
   file.
3. The scored run: `python -m pgw.run run --batch <dir> --out <fresh dir> --model-stage live --frozen FROZEN.json`,
   in one environment. It refuses a batch that is not a live, frozen test batch written by `claude-opus-5-5`, an
   output directory that holds a non-frozen run, and any code or package that differs from `FROZEN.json`.
4. Push 2, on top of push 1: the test batch and its hashes, the generator's rejections, the audit, the raw model
   responses, the scores, the 10 seeded replies with their emails, and the results.

### 5.6 Calls, repeats and the published sample

From `pgw/run.py` (extracted segments):

```python
MODEL_ID = "claude-sonnet-5-5"

EFFORT = "high"

TEST_SEED: int | None = 20261006    # set in Task 14 to the pre-registration's commit date, YYYYMMDD (spec §6)

BATCHES = {"dev": {"seed": 1, "n": 100, "pids": DEV_PIDS},
           "test": {"seed": None, "n": 300, "pids": TEST_PIDS}}

REPEAT_SUBSET, REPEATS, REPEAT_SEED = 50, 3, 7

SAMPLE_SIZE, SAMPLE_SEED = 10, 11

def repeat_subset(ids: list[str]) -> list[str]:
    return sorted(random.Random(REPEAT_SEED).sample(sorted(ids), min(REPEAT_SUBSET, len(ids))))

def sample_ids(ids: list[str]) -> list[str]:
    return sorted(random.Random(SAMPLE_SEED).sample(sorted(ids), min(SAMPLE_SIZE, len(ids))))
```

- **Sendable** emails (a message exists and nothing held it) are called once each, at repeat 0.
- **Repeats:** 50 of the sendable emails, drawn with `REPEAT_SEED` = 7 from the sorted ids, are called
  `REPEATS` = 3 times in all (repeats 0, 1, 2), to show how much answers change from call to call (`variation`).
- **The published sample:** 10 emails drawn with `SAMPLE_SEED` = 11 from the sorted ids of the **handled** emails,
  each with its repeat-0 reply, restored and unedited, beside its original email (`sample_ids`). Drawing from handled
  emails means the sample conditions on the run's holds; hold reasons are published through the summary instead.

### 5.7 Cost

Prices read on Anthropic's pricing page on 2026-10-06: Claude Opus 5.5 $4 / $20 and Claude Sonnet 5.5 $2 / $10 per
million input / output tokens (standard tier). These match spec §10.

- **Scored-run estimate:** writing and auditing the 300 test emails, about $4.73; the model calls, about 2,400 input
  and 340 output tokens each, with 206 sendable emails (section 5.3) plus 100 repeats making 306 calls, about $2.51.
  **About $7.24 in all.** The ceiling, with every email taking 3 generations and 400 calls, is about $14.69.
- The run measures its own cost from token counts.

---

## 6. Rules, verbatim from code

Each block below is cut from the frozen code (extracted segments in file order, or a whole file where stated).

### 6.1 Step 2: the variant list (what "known" covers)

From `pgw/known.py`. Every form maps to one token per field; `FIRST_NAME` has its own token, which restores the first
name. Overlapping matches go to the longest. Every field is tokenised even when the email
does not mention it, so the record summary can use the tokens.

```python
SEP = r"[\s\-.()]*"

def _alnum(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", s)

def _seq(chars: str) -> str:
    return r"(?<![A-Za-z0-9])" + SEP.join(re.escape(ch) for ch in chars) + r"(?![A-Za-z0-9])"

def _words(phrase: str) -> str:
    return r"(?<![\w])" + r"\s+".join(re.escape(w) for w in phrase.split()) + r"(?![\w])"

def amount_regex(pence: int) -> str:
    pounds, p = divmod(pence, 100)
    whole = f"{pounds:,}".replace(",", ",?")
    end = r"(?!\d|\.\d)"
    if p:
        return rf"(?:£\s?)?(?<![\d.,]){whole}\.{p:02d}{end}"
    return rf"£\s?{whole}(?:\.00)?{end}|(?<![\d.,£]){whole}\.00{end}"

def forms(c: Customer) -> list[Form]:
    out: list[Form] = []

    def add(entity: str, canonical: str, regex: str, case_sensitive: bool = False) -> None:
        out.append(Form(entity, canonical, re.compile(regex, 0 if case_sensitive else re.IGNORECASE)))

    local = c.email.split("@")[0]
    add("EMAIL", c.email, re.escape(c.email))
    add("EMAIL", c.email, r"(?<![\w.])" + re.escape(local) + r"(?![\w])")
    for phrase in (c.full, f"{c.title} {c.last}", f"{c.title}. {c.last}", c.last):
        add("CUSTOMER", c.full, _words(phrase))
    add("FIRST_NAME", c.first, _words(c.first), case_sensitive=c.first in names.WORD_FIRST_NAMES)
    F = re.escape(c.first[0])
    L = re.escape(c.last[0])
    # Initials: dotted and uppercase only (final-review ruling, narrowing spec §4 step 2). Undotted pairs are
    # ordinary words for some customers (UK, OR, IF, ID, IT ...); lowercase dotted pairs are a.m., e.g., n.b.
    # The final dot is required (a sentence break "the U.K. I live" is not initials) and customers whose pair is a
    # dotted abbreviation (U.K., e.g., P.S.) get no initials form.
    if c.first[0] + c.last[0] not in names.DOTTED_ABBREVIATIONS:
        add("CUSTOMER", c.full, rf"(?<![A-Za-z]){F}\.\s*{L}\.(?![A-Za-z])", case_sensitive=True)
    digits = _alnum(c.phone)
    add("PHONE", c.phone, r"\(?" + _seq(digits))
    add("PHONE", c.phone, r"(?<![A-Za-z0-9+])(?:\+|00)?" + SEP + "44" + SEP + r"(?:\(0\)" + SEP + ")?"
        + SEP.join(digits[1:]) + r"(?![A-Za-z0-9])")
    add("ACCOUNT", c.account, _seq(_alnum(c.account)))
    add("ACCOUNT", c.account, _seq(c.account[3:]))
    add("IBAN", c.iban, _seq(c.iban))
    add("ADDRESS", c.street, _words(c.street))
    add("POSTCODE", c.postcode, _seq(_alnum(c.postcode)))
    for o in c.orders:
        add("ORDER", o.order_no, _seq(_alnum(o.order_no)))
        add("ORDER", o.order_no, _seq(o.order_no.split("-")[1]))
    amounts = [p for o in c.orders for p in (*(i.price for i in o.items), o.total)]
    for p in dict.fromkeys(amounts):
        add("AMOUNT", money(p), amount_regex(p))
    return out

def mask_known(text: str, c: Customer, vault: Vault) -> tuple[str, list[Hit]]:
    """Replace every listed form of the sender's record. Overlaps go to the longest match. Every field is
    tokenised in the vault even when the text does not mention it, so the record summary can use it."""
    cands = []
    for f in forms(c):
        tok = vault.token(f.entity, f.canonical)
        cands += [Hit(f.entity, m.start(), m.end(), m.group(0), tok) for m in f.pattern.finditer(text)]
    chosen: list[Hit] = []
    for h in sorted(cands, key=lambda h: (-(h.end - h.start), h.start)):
        if all(h.end <= o.start or h.start >= o.end for o in chosen):
            chosen.append(h)
    chosen.sort(key=lambda h: h.start)
    parts, pos = [], 0
    for h in chosen:
        parts += [text[pos:h.start], h.token]
        pos = h.end
    parts.append(text[pos:])
    return "".join(parts), chosen
```

In words: email address and its local part; full name, title + surname (with or without a dot after the title)
and surname, all to one customer token; first name to its own token (matched case-sensitively when it is also an
ordinary word); **initials dotted, uppercase, with the final dot** ("A.O.", "A. O."), and no initials form for a
customer whose pair is on `names.DOTTED_ABBREVIATIONS`; phone, account (with and without its `BWC` prefix), IBAN,
postcode and order numbers (with and without the `BW-` prefix) as character sequences with any spaces, dashes, dots
or brackets between them, and the phone also with a `+44`, `0044` or bare `44` prefix; the street line as words; and
the amounts on the customer's orders (each item's price and each order's total): with the `£`, where a whole-pound
amount may drop its `.00`, or without the `£` when the pence are written ("45.00", "12.50").

**Not in the list** (they reach the model if written, and the scorer counts some of them as unlisted known values,
section 6.8): nicknames; the town; undotted initials ("AO"); lowercase initials ("a.o."); initials without the final
dot; a street written with an abbreviation ("Rd") or without its number; an amount written as "110 pounds", "110
GBP", "GBP 110" or "4500p".

### 6.2 Step 1 and the message: who wrote in, and what is checked

From `pgw/pipeline.py`. An unrecognised sender is held with no message built.

```python
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
```

### 6.3 Step 3: the configured detector

Section 4.4 gives the code. Detected values become `[ENTITY_n]` tokens in the same vault. A detection that overlaps
an existing token at all is dropped whole, so a non-token part of it stays in clear (section 6.9). Where several
detections cover exactly the same span, `_resolve_ties` keeps one: the highest score, then our own pattern's entity,
then the alphabetically first type.

### 6.4 Step 4: the exit check (reasons and rules)

The whole of `pgw/exitcheck.py`. It imports nothing from the package. Its reasons map to the hold groups of section
7 through `HOLD_GROUPS`.

```python
"""Step 4 (spec §4): a separate pass over exactly what would be sent. It shares no code with known.py or
detector.py and imports nothing from this package: it is the verifier behind "0 of N", not a second chance.
check() returns the reasons to hold; an empty list means the message may leave."""
import re
from dataclasses import dataclass

TOKEN = re.compile(r"\[([A-Z][A-Z_]*)_(\d+)\]")
HIGH_RISK_TOKENS = frozenset({"CREDIT_CARD", "IBAN_CODE"})
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
PHONE = re.compile(r"(?<!\d)(?:(?:\+|00)\s?44\s?(?:\(0\)\s?)?|0)\d{2,4}[\s.-]?\d{3,4}[\s.-]?\d{3,4}(?!\d)")
DIGIT_RUN = re.compile(r"\d(?:[^\S\n]{0,2}\d){7,}")   # 8+ digits, contiguous or joined by 1-2 non-newline spaces (incl. nbsp); "-", "/" and "." stay out: dates use them
CARD = re.compile(r"(?<!\d)\d(?:[\s.-]{0,2}\d){12,18}(?!\d)")
IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]){11,30}\b")
NINO = re.compile(r"\b[A-Z]{2} ?\d{2} ?\d{2} ?\d{2} ?[A-D]\b")   # broad on purpose: QQ is the published example
HOLD_GROUPS = {"high_risk_token": "high_risk", "card": "high_risk", "iban": "high_risk", "nino": "high_risk",
               "email": "leftover_pattern", "phone": "leftover_pattern", "digit_run": "leftover_pattern",
               "known_name": "known_value", "known_number": "known_value", "known_phrase": "known_value",
               "known_amount": "known_value", "known_initials": "known_value"}


@dataclass(frozen=True)
class Record:
    """The sender's fields as plain strings, so this module needs nothing from the CRM's types."""
    names: tuple[str, ...]            # first name, surname
    case_sensitive: tuple[str, ...]   # names that are also ordinary words: matched only as written
    sequences: tuple[str, ...]        # phone, account, IBAN, postcode, order numbers, digit-only forms
    phrases: tuple[str, ...]          # email address, its local part, street line
    amounts: tuple[int, ...]          # pence
    initials: tuple[str, ...] = ()    # first and surname initial: matched dotted and uppercase only ("A.O.", "A. O.")


def _luhn(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0


def _iban_ok(s: str) -> bool:
    s = s.replace(" ", "")
    return 15 <= len(s) <= 34 and int("".join(str(int(c, 36)) for c in s[4:] + s[:4])) % 97 == 1


def _spaced(s: str) -> re.Pattern:
    chars = re.sub(r"[^A-Za-z0-9]", "", s)
    return re.compile(r"(?<![A-Za-z0-9])" + r"[\s\-.]*".join(map(re.escape, chars)) + r"(?![A-Za-z0-9])",
                      re.IGNORECASE)


def _amount_found(text: str, pence: int) -> bool:
    pounds, p = divmod(pence, 100)
    for m in re.finditer(r"(£\s?)?(?<![\d.,])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{2}))?(?!\d|\.\d)", text):
        if (m.group(1) or m.group(3)) and int(m.group(2).replace(",", "")) == pounds and int(m.group(3) or 0) == p:
            return True
    return False


def _known(bare: str, rec: Record) -> set[str]:
    found = set()
    for n in rec.names:
        flags = 0 if n in rec.case_sensitive else re.IGNORECASE
        if re.search(r"(?<![\w])" + re.escape(n) + r"(?![\w])", bare, flags):
            found.add("known_name")
    for s in rec.sequences:
        digits = re.sub(r"\D", "", s)
        if _spaced(s).search(bare) or (s.startswith("0") and len(digits) >= 10 and _spaced("44" + digits[1:]).search(bare)):
            found.add("known_number")
    if any(re.search(r"(?<![\w])" + r"\W{1,3}".join(re.escape(w) for w in ph.split()) + r"(?![\w])", bare,
                     re.IGNORECASE) for ph in rec.phrases):
        found.add("known_phrase")
    if any(_amount_found(bare, p) for p in rec.amounts):
        found.add("known_amount")
    if len(rec.initials) == 2:
        F, L = map(re.escape, rec.initials)
        if re.search(rf"(?<![A-Za-z]){F}\.\s*{L}\.(?![A-Za-z])", bare):
            found.add("known_initials")
    return found


def check(message: str, rec: Record | None) -> list[str]:
    reasons: set[str] = set()
    if {m.group(1) for m in TOKEN.finditer(message)} & HIGH_RISK_TOKENS:
        reasons.add("high_risk_token")
    bare = TOKEN.sub(" ", message)
    if any(_luhn(re.sub(r"\D", "", m.group(0))) for m in CARD.finditer(bare)):
        reasons.add("card")
    if any(_iban_ok(m.group(0)) for m in IBAN.finditer(bare.upper())):
        reasons.add("iban")
    if NINO.search(bare.upper()):
        reasons.add("nino")
    if EMAIL.search(bare):
        reasons.add("email")
    if PHONE.search(bare):
        reasons.add("phone")
    if DIGIT_RUN.search(bare):
        reasons.add("digit_run")
    if rec is not None:
        reasons |= _known(bare, rec)
    return sorted(reasons)


def control() -> None:
    """Positive controls run inside every pipeline run (spec §7): a check that misses these tests nothing."""
    rec = Record(("Ada", "Okafor"), (), ("07700 900123",), (), ())
    assert "known_number" in check("call 07700 900123", rec), "exit check missed a known phone number"
    assert "known_name" in check("Okafor", rec), "exit check missed a known surname"
    assert "card" in check("4111 1111 1111 1111", None), "exit check missed a raw card number"
    initials = Record(("Ada", "Okafor"), (), (), (), (), ("A", "O"))
    assert "known_initials" in check("Regards, A.O.", initials), "exit check missed the sender's initials"
    assert check("placed 2026-09-14 [ORDER_1]", rec) == [], "exit check held a clean message"
```

### 6.5 Step 6: the two calculation forms

From `pgw/calc.py`. `{SUM: [AMOUNT_a], [AMOUNT_b], ...}` (two or more operands) and `{DIFF: [AMOUNT_a], [AMOUNT_b]}`
(first minus second) are computed from the vault and written into the restored draft. Any other braced expression,
an operand that is not an amount in this vault, or a negative difference is a bad expression.

```python
BRACES = re.compile(r"\{[^{}]*\}")

SUM = re.compile(r"\{\s*SUM\s*:\s*\[AMOUNT_\d+\](?:\s*,\s*\[AMOUNT_\d+\])+\s*\}")

DIFF = re.compile(r"\{\s*DIFF\s*:\s*\[AMOUNT_\d+\]\s*,\s*\[AMOUNT_\d+\]\s*\}")

OPERAND = re.compile(r"\[AMOUNT_\d+\]")

def pence(figure: str) -> int:
    m = re.fullmatch(r"£\s?(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{2}))?", figure.strip())
    if not m:
        raise ValueError(f"not a £ figure: {figure!r}")
    return int(m.group(1).replace(",", "")) * 100 + int(m.group(2) or 0)

def apply(text: str, vault: Vault) -> tuple[str, list[str], list[str]]:
    """Replace each valid expression with its figure. Returns (text, figures written, bad expressions)."""
    figures: list[str] = []
    bad: list[str] = []

    def one(m: re.Match) -> str:
        expr = m.group(0)
        is_sum, is_diff = bool(SUM.fullmatch(expr)), bool(DIFF.fullmatch(expr))
        values = [vault.value(t) for t in OPERAND.findall(expr)]
        try:
            nums = [pence(v) for v in values] if (is_sum or is_diff) and None not in values else None
        except ValueError:
            nums = None
        result = None if nums is None else (sum(nums) if is_sum else nums[0] - nums[1])
        if result is None or result < 0:
            bad.append(expr)
            return expr
        figures.append(money(result))
        return money(result)

    return BRACES.sub(one, text), figures, bad
```

### 6.6 Step 7: the draft check (reasons)

From `pgw/draftcheck.py`. Reasons: `invented_token` (a token the vault does not hold), `leftover_token` (a token left
after restore), `malformed_token` (a wrong-format variant of a type the vault holds, including a letter in place of
the number and the type in the wrong case), `bad_expression`, and `bare_amount` (a `£` or `￡`, or a worded amount,
not produced by a calculation). Figures are judged by provenance: any figure a token or a calculation did not
produce was typed by the model. Other numbers ("3-5 working days", dates) are allowed.

```python
POUND = re.compile(r"[£￡]")

WORDED = re.compile(r"\d[\d,.]*\s*(?:GBP|pounds?)\b|\bGBP\s*\d", re.IGNORECASE)

LEFTOVER_EXPR = re.compile(r"[{}]|\b(?:SUM|DIFF)\s*:", re.IGNORECASE)

def _malformed(restored: str, types: set[str]) -> bool:
    """Wrong-format variants of the token types this vault actually holds: [TYPE], [TYPE 1], [TYPE-1], TYPE_1,
    and [TYPE_x] where x is anything but the number alone ([AMOUNT_a], [AMOUNT_n]); and a well-shaped [TYPE_1]
    whose type is written in the wrong case ([first_name_1], [Order_1]) - built only from the vault's own types."""
    for t in types:
        n = re.escape(t)
        if any(m.group(0) != m.group(0).upper() for m in re.finditer(rf"\[{n}_\d+\]", restored, re.IGNORECASE)):
            return True
        if re.search(rf"\[{n}\]|\[{n}[ -]\d+\]|(?<![\[\w]){n}_\d+\b(?!\])|\[{n}_(?!\d+\])[^\]]*\]", restored,
                     re.IGNORECASE):
            return True
    return False

def check(raw: str, restored: str, vault: Vault) -> list[str]:
    reasons = set()
    if any(vault.value(m.group(0)) is None for m in TOKEN_RE.finditer(raw)):
        reasons.add("invented_token")
    if TOKEN_RE.search(restored):
        reasons.add("leftover_token")
    if _malformed(restored, {TOKEN_RE.fullmatch(t).group(1) for t in vault.tokens()}):
        reasons.add("malformed_token")
    calculated, figures, bad = apply(raw, vault)
    if bad or LEFTOVER_EXPR.search(calculated):
        reasons.add("bad_expression")
    rest = calculated
    for f in figures:
        rest = rest.replace(f, " ", 1)
    if POUND.search(rest) or WORDED.search(rest):
        reasons.add("bare_amount")
    return sorted(reasons)

def control() -> None:
    """Positive control run inside every pipeline run (spec §7)."""
    v = Vault()
    v.token("CUSTOMER", "Ada Okafor")
    v.token("AMOUNT", "£45.00")
    v.token("AMOUNT", "£65.00")
    for raw, expected in (("Dear [CUSTOMER_9], {MUL: [AMOUNT_1]} and £5.00.",
                           {"invented_token", "leftover_token", "bad_expression", "bare_amount"}),
                          ("Refund of £65.00 and [AMOUNT_1].", {"bare_amount"}),
                          ("{SUM: [AMOUNT_1], [AMOUNT_2]", {"bad_expression"})):
        text, _, _ = apply(raw, v)
        got = set(check(raw, restore(text, v), v))
        assert expected <= got, f"draft check missed {expected - got} in {raw!r}"
```

### 6.7 Gold: the audit, the pattern scan and the skip rule

From `pgw/audit.py`. Gold for an email is: its planted unknown values; every occurrence of the sender's record found
by the scorer's own search (section 6.8), as `record:<field>:<form>`; and every audit or pattern find, either
`skipped:<kind>` (it equals a planted or record value, or is a whole-word part of one, or is the company or a
product) or `unplanned:<kind>`. Skipped finds are recorded and counted (`audit.skipped`), not scored. An unplanned
find is high-risk only if valid: a card only if its 13 to 19 digits pass Luhn, a bank detail only if it is a
check-digit-valid IBAN.

```python
AUDIT_EFFORT = "medium"

KINDS = ("name", "email", "phone", "address", "postcode", "account", "order", "card", "bank", "amount", "other")

PATTERNS = (
    ("email", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+"),
    ("phone", r"(?:\+44\s?|0)7\d{3}[\s-]?\d{3}[\s-]?\d{3}"),
    ("amount", r"£\s?\d[\d,]*(?:\.\d{2})?"),
    ("card", r"\b\d{4}[ -]?\d{4,6}[ -]?\d{4,5}(?:[ -]?\d{4})?\b"),
    ("bank", r"\bGB\d{2}(?: ?[A-Z0-9]{4}){4,5}(?: ?[A-Z0-9]{1,4})?\b"),
    ("postcode", r"\b[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}\b"),
    ("order", r"\bBW-?\d{6}\b"),
)

def pattern_scan(text: str) -> list[tuple[str, str]]:
    return [(kind, m.group(0)) for kind, rx in PATTERNS for m in re.finditer(rx, text)]

def _norm(s: str) -> str:
    s = re.sub(r"['’]s\b", "", s)
    return re.sub(r"[^a-z0-9£]", "", s.lower())

def _words(s: str) -> tuple[str, ...]:
    s = re.sub(r"['’]s\b", "", s)
    return tuple(re.findall(r"[a-z0-9£]+", s.lower()))

def _covered(value: str, sources: list[str]) -> bool:
    n, w = _norm(value), _words(value)
    for s in sources:
        sw = _words(s)
        if n == _norm(s) or (w and any(w == sw[i:i + len(w)] for i in range(len(sw) - len(w) + 1))):
            return True
    return False

def build_gold(b: Brief, text: str, audit_items: list[dict], c: Customer) -> list[GoldItem]:
    scan = known_scan.occurrences(text, c)
    scan_texts = [o.text for o in scan]
    for p in b.plants:
        if p.known:
            assert _covered(p.value, scan_texts), f"{b.email_id}: planted known value {p.value!r} not found by the scan"
    gold = [GoldItem(p.kind, p.value, p.parts, "planted", p.known, p.listed, p.high_risk)
            for p in b.plants if not p.known]
    gold += [GoldItem(f"record:{o.field}:{o.form}", o.text, (o.text,), "record_scan", True, o.listed, False)
             for o in scan]
    sources = [v for p in b.plants for v in (p.value, *p.parts)] + [o.text for o in scan]
    sources += [names.COMPANY] + [n for n, _ in names.PRODUCTS]
    seen: set[str] = set()
    for kind, value in pattern_scan(text) + [(i["kind"], i["text"]) for i in audit_items]:
        n = _norm(value)
        if not n or n in seen:
            continue
        seen.add(n)
        if _covered(value, sources):
            gold.append(GoldItem(f"skipped:{kind}", value, (value,), "skipped", False, False, False))
        else:
            gold.append(GoldItem(f"unplanned:{kind}", value, (value,), "audit", False, False,
                                 _valid_card(value) if kind == "card" else _valid_iban(value) if kind == "bank" else False))
    return gold

def _valid_card(value: str) -> bool:
    d = re.sub(r"\D", "", value)
    if not 13 <= len(d) <= 19:
        return False
    total = 0
    for i, ch in enumerate(reversed(d)):
        n = int(ch)
        if i % 2 == 1:
            n = n * 2 - 9 if n > 4 else n * 2
        total += n
    return total % 10 == 0

def _valid_iban(value: str) -> bool:
    s = re.sub(r"\s", "", value).upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{10,30}", s):
        return False
    return int("".join(str(int(ch, 36)) for ch in s[4:] + s[:4])) % 97 == 1
```

### 6.8 The scorer's own record search, and the `_present` rule

From `pgw/known_scan.py`, written apart from `known.py` with broader separators. It also finds forms the gateway
does **not** list, and marks them unlisted: the **nickname** and the **town**. Digit-only forms (order digits,
account digits) match contiguous digits only.

```python
GAP = r"[^A-Za-z0-9\n]{0,2}"

def _chars(s: str) -> str:
    chars = re.sub(r"[^A-Za-z0-9]", "", s)
    return r"(?<![A-Za-z0-9])" + GAP.join(map(re.escape, chars)) + r"(?![A-Za-z0-9])"

def _solid(digits: str) -> str:
    """Digit-only forms match contiguous digits only: no separators between them."""
    return r"(?<![A-Za-z0-9])" + re.escape(digits) + r"(?![A-Za-z0-9])"

def _phrase(s: str) -> str:
    return r"(?<![\w])" + r"\W{1,3}".join(map(re.escape, s.split())) + r"(?![\w])"

def _patterns(c: Customer) -> list[tuple[str, str, str, bool, int]]:
    """(field, form, regex, listed, flags)."""
    ci, cs = re.IGNORECASE, 0
    word_first = c.first in names.WORD_FIRST_NAMES
    F, L = re.escape(c.first[0]), re.escape(c.last[0])
    pats = [
        ("email", "address", re.escape(c.email), True, ci),
        ("email", "local", r"(?<![\w.])" + re.escape(c.email.split("@")[0]) + r"(?![\w])", True, ci),
        ("name", "full", _phrase(c.full), True, ci),
        ("name", "title_last", _phrase(f"{c.title} {c.last}"), True, ci),
        ("name", "title_last", _phrase(f"{c.title}. {c.last}"), True, ci),
        ("name", "last", _phrase(c.last), True, ci),
        ("name", "first", _phrase(c.first), True, cs if word_first else ci),
        ("phone", "national", _chars(c.phone), True, ci),
        ("phone", "international", r"\+?" + _chars("44" + re.sub(r"\D", "", c.phone)[1:]), True, ci),
        ("account", "account", _chars(c.account), True, ci),
        ("account", "digits", _solid(c.account[3:]), True, ci),
        ("iban", "iban", _chars(c.iban), True, ci),
        ("street", "street", _phrase(c.street), True, ci),
        ("postcode", "postcode", _chars(c.postcode), True, ci),
        ("town", "town", _phrase(c.town), False, ci),
    ]
    if c.first[0] + c.last[0] not in names.DOTTED_ABBREVIATIONS:   # dotted, uppercase, final dot required
        pats.append(("name", "initials", rf"(?<![A-Za-z]){F}\.\s*{L}\.(?![A-Za-z])", True, cs))
    if c.first in names.NICKNAMES:
        pats.append(("name", "nickname", _phrase(names.NICKNAMES[c.first]), False, cs))
    for o in c.orders:
        pats.append(("order", "order", _chars(o.order_no), True, ci))
        pats.append(("order", "digits", _solid(o.order_no.split("-")[1]), True, ci))
    for p in dict.fromkeys(p for o in c.orders for p in (*(i.price for i in o.items), o.total)):
        pounds, pence = divmod(p, 100)
        whole = f"{pounds:,}".replace(",", ",?")
        tail = rf"\.{pence:02d}" if pence else r"(?:\.00)?"
        pats.append(("amount", "amount", rf"£\s?{whole}{tail}(?!\d|\.\d)|(?<![\d.,£]){whole}\.{pence:02d}(?!\d|\.\d)", True, ci))
    return pats

def occurrences(text: str, c: Customer) -> list[Occurrence]:
    cands = [Occurrence(f, form, m.group(0), m.start(), m.end(), listed)
             for f, form, rx, listed, flags in _patterns(c) for m in re.finditer(rx, text, flags)]
    chosen: list[Occurrence] = []
    for o in sorted(cands, key=lambda o: (-(o.end - o.start), o.start)):
        if all(o.end <= x.start or o.start >= x.end for x in chosen):
            chosen.append(o)
    return sorted(chosen, key=lambda o: o.start)
```

From `pgw/score.py`: `_present` decides whether an unknown value reached the model. A part with 4 or more digits is
present if its letters and digits appear, in order and contiguous after removing everything else, in the bare
message (tokens removed). Any other part is present if its words appear word-bounded, joined by 1 to 3 non-word
characters, case-insensitively.

```python
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
```

### 6.9 Known limits of these rules, stated in advance

**What the gateway does not mask** (each reaches the model if written):
1. **Amount forms:** "110 pounds", "110 GBP", "GBP 110", "4500p". The gateway does not mask them and the scorer does not
   count them as known values, so such a leak is invisible to both. In replies, the draft check holds a worded amount.
2. **Street abbreviations** ("Rd") and a street without its number: not masked, not listed; such a leak would surface
   only as an audit find.
3. **Initials:** undotted ("AO"), lowercase ("a.o.") or without the final dot are not masked and not counted. The three
   test-half customers on the stoplist (C129, C145, C194) have no initials form at all, so their initials leak if
   written, counted nowhere.
4. **Partial token overlaps:** a detection that overlaps an existing token is dropped whole, so its non-token part
   stays in clear ("[CUSTOMER_1] Smith" keeps "Smith"). If that part is a known or unknown value, it is measured as a
   leak or as reached.
5. A known name joined to "_" or digits ("Ada_Okafor", "Okafor123") is not matched; an order prefix joined by an en
   dash or an underscore survives (its digits are masked); a third party's email address containing the customer's
   surname is masked in place.
6. The **town** is not in the variant list. The scorer counts the sender's town as an **unlisted** known value. A new
   address's town is never scored: its parts are the street and the postcode only, so town leaks are under-recorded
   for new addresses.
7. **UK_PHONE** covers mobile numbers only; landlines rely on Presidio's built-in phone recogniser.
8. An order number whose digits look like a year and month ("BW-202609") would also mask ISO dates; no order in this
   CRM has such digits. A caveat for reuse.

**Instrument properties:**
9. `detections` in `outbound.jsonl` lists every analyzer result, including those dropped for overlapping a token or
   by the tie rule; it is not "what was masked". Token numbers from the detector run right to left; nothing depends on
   their order.
10. **Possessive dedupe:** when the audit lists "Sarah's" before "Sarah" and the detector masks only the possessive,
    the bare "Sarah" is scored masked. A rare under-count of an unplanned-name leak, in the gateway's favour.
11. Spurious unknowns: a possessive the audit lists after the scan matched "Ms Okafor's" can become an unplanned name,
    and a phone form the audit lists but the text does not hold can become an unplanned phone; both inflate unknowns
    slightly and are visible in the gold. The scorer's first-name form can match inside an unplanned email address (a
    false known occurrence; that email is held anyway).
12. `reply_correct` is a containment check (spec §5 "contains"). A reply can pass it and still be wrong, for example a
    refund the policy does not give, when the gold has no amount. Triage is the scored signal for that failure class.
13. The scorer looks up the customer and first-name tokens on a copy of the vault; the lookup cannot change what was
    sent.
14. Role lines in the writer's message mix grammatical persons; cosmetic.

**What can cause a false hold:**
15. `DIGIT_RUN`: 8 or more digits, contiguous or joined by 1 or 2 spaces. A compact date ("20260914") or an 8-digit
    ticket or tracking number holds the email.
16. `PHONE`: a free-phone line such as "0800 123 456" matches and holds the email.
17. `CARD` can chain a dotted date range ("01.09.2026-14.09.2026") into a Luhn-valid run, about 1 range in 10, which
    holds as high risk. `NINO` can match "BW 123456 A" if the detector missed an order number.

---

## 7. Measurements

### 7.1 Units and denominators

**Every number is k of n with its unit stated.** There is no pooled accuracy. Every number names its configuration:
Presidio 2.2.364 and `en_core_web_lg` 3.8.0, the frozen hashes of section 11, the model's reported ID, English,
synthetic. N below is the number of accepted test emails (300 minus any dropped).

**Value is reported over two denominators** (spec §6), so holding the hard emails cannot inflate it: over handled
emails, and over all test emails. **Handled** means sent, answered with a valid reply, and passed by the draft check.

**Every key is always written,** as `[0, n]` when nothing of that kind occurred, so absence never reads as "nothing
leaked".

From `pgw/score.py`:

```python
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
```

### 7.2 Every `summary.json` key

| Key | Unit | Denominator | What it means |
|---|---|---|---|
| `n_emails` | emails | n/a | N, accepted test emails |
| `value.handled` | emails handled automatically | N | sent, valid reply, draft check passed |
| `value.triage.<field>.over_handled`, `<field>` = category, urgency, order, action | emails with the field equal to gold | handled | each field separately; `order` compares the model's order token with the gold order's token, or `""` when gold has no order |
| `value.triage.<field>.over_all` | same k | N | held emails count as not correct |
| `value.by_action.<action>`, for each of the 7 actions | `{n, handled, action_correct}` | n: emails whose gold action is that action; handled: those handled; action_correct: of the handled, those whose action is right | per-action triage, always written for every action (section 7.4) |
| `value.reply.over_handled` | replies passing `reply_correct` | handled | contains the customer or first-name token; the gold order's token if gold has an order; and, when gold has an amount, that amount in the restored reply. A containment check (section 7.5) |
| `value.reply.over_all` | same k | N | |
| `holds.unrecognised_sender` | emails | N | held at step 1 |
| `holds.high_risk` | emails | N | exit check: a card or IBAN token, a raw Luhn-valid card, a valid IBAN or an NI number pattern |
| `holds.leftover_pattern` | emails | N | exit check: an email address, phone-like pattern or digit run left in the message |
| `holds.known_value` | emails | N | exit check found a known value or variant the gateway missed; **expected 0** |
| `holds.draft_check` | emails | N | the restored reply failed the draft check |
| `holds.no_answer` | emails | N | model failure: a stop reason other than `end_turn`, or invalid JSON |
| `holds.false` | nothing-planted emails held for any reason except `no_answer` | nothing-planted emails | the cost line: clean mail held for review |
| `holds.false_clean` | same, over clean emails | clean emails (also no audit finds) | |
| `holds.false_by_reason` | counts per hold group | nothing-planted emails | |
| `leaks.known.listed.mentions` | listed known-value mentions in what was sent | listed known-value mentions in the original emails, all N emails | **the "0 of N" line**: a held email leaks 0. Counted per field, capped by the original's mentions of that field |
| `leaks.known.unlisted.mentions` | unlisted known-value mentions (nickname, town) sent | unlisted mentions in the originals, all N | **where the list stops** |
| `leaks.known.<listed or unlisted>.mentions_sent` | same k | mentions in the originals of sent emails only | beside the headline |
| `leaks.known.<listed or unlisted>.emails` | emails with at least one such leak | N | per email |
| `leaks.known.<listed or unlisted>.emails_sent` | same | sent emails | |
| `unknown.<kind>`, kind = third_party, new_phone, new_address | planted values: masked / held / reached, and n | planted values of that kind | **reached** = a part of the value is present in what was sent (the residue the design leaves to the contract layer, which is not measured); `n_at_exit` and `held_at_exit` count only values in emails that reached the exit check |
| `unknown.unplanned` and `unknown.unplanned.<audit kind>` (11 kinds) | audit finds that are not high-risk: same outcomes | such finds | pooled, then one line per audit kind |
| `high_risk.card`, `high_risk.iban` | planted card or IBAN values held / masked / reached | planted values | **"held, k of k"**; the exit check's own k of k is `held_at_exit` of `n_at_exit` (excludes unmatched senders, held at step 1) |
| `high_risk.unplanned` and `high_risk.unplanned.<audit kind>` | valid card or IBAN the audit found unplanned | such finds | |
| `audit.skipped` | audit and pattern finds recorded as skipped | n/a | the gold builder's blind spot, counted |
| `contrast.known.listed.mentions`, `contrast.known.unlisted.mentions` | known-value mentions left in Presidio-as-shipped's payload | mentions in the originals, all N | **"out of the box, M of N would have left"**; same denominator as the gateway's headline line |
| `contrast.high_risk` | planted and unplanned high-risk values present in that payload | high-risk gold items | |
| `variation` | per repeat-subset email, `[handled, all four triage fields right, reply_correct]` for each of 3 calls | 50 emails | how much answers change |
| `stops` | replies per stop reason | all replies | |
| `models_reported` | replies per reported model ID | all replies | |
| `generation` | briefs, accepted, attempts, rejected attempts, dropped | n/a | the generator's record |
| `sample_ids` | the 10 published email ids | handled emails | section 5.6 |

### 7.3 What each plausible result would mean

A target is not a result (spec §1). For each headline line, what a result would and would not allow:

| Line | If the result is | It means |
|---|---|---|
| `leaks.known.listed.mentions` | 0 of N | "0 of N customer details on record left the perimeter", for the listed variants, over all test emails, a held email leaking 0 |
| | k > 0 | a listed known value left. It is reported as measured, the "0 of N" sentence cannot be used, and section 9's rule applies: publish as it stands, or fix, amend, generate a fresh test batch and report both runs |
| `holds.known_value` | 0 | the gateway masked every listed value the exit check looks for |
| | k > 0 | the gateway missed a value and the exit check held it: no leak, but a gateway miss, reported with the email ids. The exit check did its job as the verifier |
| `leaks.known.unlisted.mentions` | k > 0 (expected) | where the list stops: nicknames and the town reach the model. This is the line that shows the variant list is the limit |
| | 0 | no unlisted form was written in what was sent; it does not show that the list covers them |
| `high_risk.card`, `high_risk.iban` | held = n | "every card number and IBAN the customer typed in was held: k of k" |
| | reached > 0 | a card number or IBAN went to the model: a defect, under section 9's rule |
| | masked > 0, email sent | the model never saw the value; the exit check did not hold the email, so no agent was alerted: a partial failure of spec §4 step 4, reported as such |
| `unknown.<kind>` reached | any k | the residue the contract layer exists for (spec §1), reported per kind |
| `value.handled` | k of N | the share of this inbox handled automatically. It is bounded by the mix: at the test seed 94 of 300 briefs are held before the model by construction (section 5.3), so it is a property of this mix, not of real inboxes |
| `value.triage.*`, over handled | k of n per field | how often the model's triage matched the policy's gold on the emails it handled; over all, the same k over N |
| `value.reply.*` | near n | the tokens are right (customer, order, amount); it says nothing about quality (section 7.5) |
| `holds.false` | 0 of n | no nothing-planted email was held |
| | k > 0 | the cost of the setup, by reason (`holds.false_by_reason`) |
| `contrast.known.listed.mentions` | M of N | "out of the box, M of N would have left", on the same N as the gateway's line |
| `holds.no_answer` | k > 0 | model failures, reported with their stop reasons (`stops`); never re-asked |
| send-readiness read | SEND k of handled | a labelled judgement of how many drafts an agent could send unchanged; not a scored number |

### 7.4 Per-action numbers, and cost

- **Per gold action** is computed by the frozen code: `summary.json` key `value.by_action.<action>` for each of the 7
  actions, always written, `{n, handled, action_correct}` (section 7.1, `summarise`). `n` counts the emails whose
  brief gold has that action, over all emails; `handled` counts those handled; `action_correct` counts the handled
  ones whose action is right, from the same rows and the same handled definition as `value.triage.action`. Each
  `scores.jsonl` row carries its `gold_action`. Over the 7 actions, `handled` sums to `value.handled`'s k and
  `action_correct` to `value.triage.action.over_handled`'s k. **Every action is reported with its n, and no rate is
  given below n = 10**: below 10 only "k of n" appears; the code writes counts only, and the rule is applied in
  reporting. At the test seed, `cancel` and `full_refund` are expected below 10 among emails
  reaching the model (section 5.3), and late-delivery `resend` has 3 expected to reach the model: late-delivery
  resend is effectively untested.
- **Cost** is derived from the published replies: input and output tokens per stage, and dollars at the prices of
  section 5.7.

### 7.5 The human send-readiness read (pre-registered)

`reply_correct` is a containment and token check. **It is not a quality measure.** The read below is the quality
judgement, labelled as a judgement.

- **Set:** every handled email's repeat-0 reply, one level each, reported over handled and over all test emails.
  Repeats 1 and 2 of the repeat subset are not read; how answers change from call to call is reported by the
  `variation` key (section 7.2).
- **Levels:** SEND (send as is), EDIT (minor edit), REJECT (not sendable).
- **Reader:** Vagelis.
- **Blind:** the read is blind to the gold, the scores and the triage verdict. For each reply the reader sees the
  original email, the customer's record, the restored reply and the company policy (`POLICY_TEXT`, section 4), and
  nothing else.
- **Order:** the handled email ids are sorted, shuffled with Python's `random.Random(20261006).shuffle` (the test
  seed), and read in that order.
- **Reported:** the counts per level as applied; the count under each alternative reading listed below; the levels
  of the 10 published replies; and a 2 × 2 table of the level against `reply_correct`.

**The rubric, in full.** Apply REJECT, then EDIT, then SEND; the conditions decide, and the first sentence of each
level is a summary.

**REJECT: not sendable.** Any of:
1. **Wrong decision:** the action contradicts the policy as applied to the facts in the email and the record. Where
   the email fits two categories that the policy treats differently, either category's action is correct, and the
   case is tagged GOLDAMB (see the table below).
2. **A promise the policy doesn't allow:** a refund, replacement, amount or compensation the policy does not give
   for this case. Saying or implying that something will be offered is a promise.
3. **A wrong fact that matters:** one the customer would act on, or that changes what we owe: an amount, a date, an
   order status, an eligibility.
4. **Not addressing the main request.**

**EDIT: a small edit (one phrase or one fact).** Any of:
1. Ignoring a secondary request, or asking the customer for something they already asked for. A request is anything
   the customer asks us to do, decide or tell them, including process questions (how to return, who pays postage,
   when a refund arrives). A process question that the record and the policy cannot answer is addressed when the
   reply says the answer will follow. Passing over one: EDIT.
2. A date or number of days that cannot be derived from the record and the policy (for example "within 5 working
   days"). A date derived correctly from them is supported.
3. An unsupported statement that is not a wrong fact that matters. Any claim, as the company's own knowledge, about
   what has been charged or paid (for example "only one charge was taken"). Restating the customer's report with
   attribution, and saying that payment details are not visible, are fine.
4. Telling the customer to wait, or to come back after delivery, for an order dispatched more than 7 days ago and not
   delivered. Such an order is overdue under the policy, whatever the email's category.
5. Any statement about who or what wrote the reply (a person, an AI, an agent, a tool).
6. Layout: a reply that needs its greeting, paragraphs and sign-off put on separate lines.
7. A misstatement that the same reply corrects. Judge the reply as a whole.
8. **A commitment, conditional on a check confirming it, to refund a confirmed double charge or a confirmed
   overcharge.** It is EDIT: not REJECT, and not SEND.

**SEND: an agent could send it unchanged.** None of the above, and:
1. It is correct against the record and the policy: no statement or implication the record does not support.
2. It addresses every request in the email: each is answered, actioned or explicitly passed on ("I have passed X to
   Y").
3. It makes no invented promise. Routine process commitments the policy is silent on do not block SEND:
   instructions to follow, refund to the original payment method, return postage for a faulty item, an unspecific
   "shortly" or "a few days". Passing on a request for compensation is SEND.
4. Its tone fits a support reply. A repeated figure or similar mechanical phrasing does not block SEND.

**Where the rubric still leaves a choice.** The reader applies the default below, tags each case, and reports the
count under the alternative:

| Tag | Case | Default | Alternative |
|---|---|---|---|
| PAYCLAIM | a payment claim whose attribution is in the previous sentence | EDIT | SEND (attribution carries across sentences) |
| LATE_SOFT | a remedy named as an option ("we will look at the options, including X") on a timeline the policy does not give | EDIT | REJECT (judged as an eligibility) or SEND |
| PHONE_TRY | a new phone number or address the customer gives without saying "please", not acknowledged | EDIT | SEND |
| REFDEST | on an escalated double charge, a refund destination the customer named, passed on as "put right" | SEND | EDIT |
| ASSURE | "they will confirm that no further charges will be applied" | SEND | EDIT |
| RETURNING | "your earlier loyalty" or "a returning customer" on a one-order record | SEND | EDIT |
| GOLDAMB | an email the reader tags, from the email and the record alone, as fitting two categories that the policy treats differently, where the reply triages one category and promises the other's remedy | judged under REJECT 1 (either category's action and remedies are correct) | REJECT, judged against the scored gold. The read is blind to the gold, so this count is computed after the read, by comparing each GOLDAMB-tagged reply with its email's gold |

---

## 8. Positive controls inside every run

Spec §7: the failure guarded against is an instrument that returns a plausible number while testing nothing. Three
controls run inside every pipeline run, before the start manifest is written; a failing control raises and the run
stops with no output. A run whose start manifest exists passed all three. The controls leave no other trace.

1. **Exit check** (`exitcheck.control`, section 6.4): a known phone number, a known surname, a raw card number and the
   sender's dotted initials must each be held, and a clean message with a date and a token must not be.
2. **Known-value scorer** (`score.control`, below): a planted known value deliberately left unmasked must score as a
   leak, `[1, 1]`.
3. **Restore and draft check** (`draftcheck.control`, section 6.6): a hand-made reply with an invented token, a bad
   expression and a bare figure must receive all four labels spec §7 names: `invented_token`, `leftover_token` (the
   invented token stays in the restored text), `bad_expression` and `bare_amount`. A typed figure beside a token must
   receive `bare_amount`; an unbalanced expression must receive `bad_expression`.

From `pgw/score.py`:

```python
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
```

**Tests.** The suite (`tests/`, 389 tests at the freeze, all passing on 2026-10-06) is hermetic: no network, and model
calls are replayed from recorded fixtures or the fake writer and echo model. It covers the round trip (mask then
restore returns the original exactly), determinism of the CRM and the briefs by hash, the Presidio pin, the
generator's exact-string check and the audit on fixtures with a missing plant and an unplanned detail, the detector's
tie rule on injected results in both input orders, the per-action counts, and the runner's refusals.

---

## 9. One test batch, used once

From the spec, §6 (quoted):

> **One test batch, used once.** If the scored run shows a defect (a known value leaked, a card number got
> through), there are two options:
> - publish the result as it stands; or
> - fix the gateway, record a dated amendment, **generate a fresh test batch**, and report **both runs**.
>
> Re-scoring the same batch after a fix is ruled out, because that is tuning to the test.
>
> **Changes after the pre-registration** are dated amendments, committed before the runs they affect.

The runner enforces part of this: a directory that already holds a batch is never regenerated, and a scored run
needs a fresh output directory. "Used once" across directories is an operating rule, not code: a second `--out`
would generate a second batch, which this rule forbids without an amendment.

---

## 10. What will not be said

From the spec, §1 (quoted). The post must not say:

> - that masking alone makes it safe, or that the PoC tested the contract layer;
> - "anonymous", "GDPR-compliant" or "100% safe";
> - that it works on any data, for agents, for multi-turn conversations, or in other languages;
> - anything on §11's must-not list;
> - any precedence claim ("first", "nobody does this").

> **A target is not a result.** If a known value leaks or a card number gets through, the post reports
> what was measured, under §6's rule on fixing.

From the spec, §11 (quoted). Must not say:

> - that tokenising makes data anonymous, "GDPR-free" or compliant;
> - that the CJEU ruled an LLM vendor (or Deloitte) holds no personal data. The operative part only sets
>   aside and refers back;
> - that EDPB 01/2025 is final, or has been updated since the judgment;
> - that the EDPB endorses "recipients without the key hold no personal data";
> - that invoice amounts are never personal data;
> - that using an LLM in HR is high-risk, or exempt, as a blanket rule;
> - any AI Act application date not re-checked against Regulation (EU) 2026/1744 (§13);
> - any precedence claim.

**Three constraints from the source checks of 2026-10-06** on how the spec's permitted legal statements are worded:
1. **C-413/23 P applies Regulation (EU) 2018/1725, not the GDPR** (para 86: "for the purposes of the application of
   Regulation 2018/1725"). Any sentence citing the judgment names that regulation.
2. **Para 85 is the counterweight to para 86.** Where it "cannot be ruled out" that a recipient can attribute the data,
   "pseudonymised data should be considered to be personal in nature". A sentence citing para 86 cites para 85 with it.
3. **The AI Act's Art. 2(7)** ("shall not affect" the GDPR) is cited "as amended by Regulation (EU) 2026/1744", which
   replaced that paragraph. The Annex III application date under that act is 2 December 2027. Annex III point 4(b)
   of Regulation (EU) 2024/1689 itself was not re-read.

Lawful basis and international transfers stay out of every sentence (section 3).

---

## 11. Frozen scripts

### 11.1 `FROZEN.json`, in full

```json
{
  "scripts": {
    "pgw/__init__.py": "2e39d14d1c54ac933064d36cada1395e3003f5b14567c22b79d636fb7ca162d4",
    "pgw/audit.py": "09f4f5c1fe75e27645c038f0e64221734907dd011a54323f9c5916e332200d46",
    "pgw/baseline.py": "f06ede5fc862732685046a7b3a204325d35f61c43ec3f5edfaeade2d42ae244f",
    "pgw/briefs.py": "9f527693ee55b0e6114b78ab675bce205ddff948bad01284358aa35ace950c90",
    "pgw/calc.py": "fa1192c2690abe3fbde47c2850b7febcba60ad99ec4dde400df0cb66fe171098",
    "pgw/crm.py": "7390c96f5bf202e907dd50fc6785f2f9285fe3f247b4364102e1089ce9801a2f",
    "pgw/detector.py": "e81bee2d07afd21c3098be998ea0419e7810a1f22a1abd04cf1fc82eaf484f99",
    "pgw/draftcheck.py": "3b44d831bedc7e111767da35fc3c1d5a423fcff4d2cdadddd18971c299d82894",
    "pgw/emailgen.py": "8d7bb22a32ab2d5b37d41014e4f845032571c21d60b7cb5d0fcee87257b03b75",
    "pgw/exitcheck.py": "736fcef52e63cc587b4884afe84595bb20818d3bd11fee44349e4a94e12bc6a2",
    "pgw/known.py": "9de8f45c89ed7f12fd2e129b24b0870ac507f9829cac194741b12c1b1840fa1d",
    "pgw/known_scan.py": "141c73bed9dbebbb80279be8ca832ccc9bbbf5286f89ab092e41fceff0a58554",
    "pgw/manifest.py": "d8d9031e6cab8d11328cc81895e1b229223eae7828656b6c21e121dad3e9bb26",
    "pgw/masking.py": "c926f257715177ffbdb4c7cecd121abb45b35fa0c8a92903826c5bb8e5d7f224",
    "pgw/model_call.py": "f50f433f39eeb95e6275ca59bc4f32feaace0ce6ea7bd6debdab0da4cbccf407",
    "pgw/names.py": "6814955261291525e8b7299cec14594883b44c0b48fed8cd8a8f7305caf8f058",
    "pgw/pipeline.py": "22649ae7c0b32876db7c82ebae1915e6a86603c2c0f312fcdaa413d1c6572aef",
    "pgw/policy.py": "f8948e318cefe43fdb543ba7bbab58a6198756c84e823bae344b03316d8760bc",
    "pgw/presidio_probe.py": "5e62b3f0ec7ca7c6678b5052fad670c548b0ac91d0d983d3d5129fd2dc3aff16",
    "pgw/prompts.py": "47f23efaca3644b534534df1b760c0cbf2704c63d9311b1fa90369027bdec303",
    "pgw/run.py": "8444f9632ea402f39b723c07f9c24421362ce62f667941591455711bd71d9d70",
    "pgw/score.py": "2d6bdb31ec8c479c3490b2d9c14485983fbb4a5ce76e1786074aa08dc9e56cb9",
    "pgw/vault.py": "35aa1ee661ec552df28f1a3432b2b57afdb03e2266e36cf2991e1e03c9506fc2"
  },
  "versions": {
    "anthropic": "1.11.0",
    "en-core-web-lg": "3.8.0",
    "phonenumbers": "9.0.40",
    "presidio-analyzer": "2.2.364",
    "presidio-anonymizer": "2.2.364",
    "python": "3.13.2",
    "regex": "2026.9.29",
    "spacy": "3.8.16",
    "tldextract": "5.4.0"
  }
}
```

`scripts` holds the SHA-256 of every `pgw/*.py` file, with CRLF normalised to LF before hashing, so a checkout on any
platform hashes the same. `versions` holds the Python version and every package the code depends on.

### 11.2 How the freeze is enforced

`manifest.check_frozen` compares every script hash and every pinned version with the installed code, in both
directions (a file added or removed is a difference). Any difference refuses a `--frozen` step before any model call
(exit 2, "code or dependencies differ from the freeze record"). Every manifest records the script hashes and versions
it ran with.

### 11.3 The freeze check, 2026-10-06

1. `python -m pgw.run run --batch <a batch that is not a live, frozen test batch> --out <fresh dir> --model-stage
   skip --frozen FROZEN.json` passed the frozen check and then exited **6**: "REFUSING: a scored run needs a live,
   frozen test batch". A frozen run refuses any batch that is not a live, frozen test batch.
2. **Negative control:** the same command with a copy of `FROZEN.json` whose `pgw/exitcheck.py` hash had its first
   character changed, into a different fresh directory, was refused at the frozen check, exit **2**: "REFUSING: code
   or dependencies differ from the freeze record: pgw/exitcheck.py".
3. `manifest.check_frozen("FROZEN.json")` returned `[]`, and the test suite passed (389 tests).

---

## 12. Amendments

Any change after this commit is a dated amendment committed before the runs it affects.

- **2026-10-07, before publication.** Wording only: the sentences that drew legal conclusions (sections 3 and 7.2)
  now state the study's scope instead, and the version labels in the title and the rubric heading are removed. No
  rule, measurement, code, seed or data changed.
