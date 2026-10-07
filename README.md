# Pseudonymization gateway study

A pre-registered test of a customer-support pipeline designed to keep customers' details away from the AI model
that reads their emails. Known values from the customer's record, in the forms the gateway lists, are replaced by
placeholders; a configured detector runs over the rest; an exit check holds the email on any known value on its
list, any high-risk value (a card or bank number, for example) and any leftover pattern. Sections 6.1 and 6.9 of
the pre-registration list what these layers do not catch. The model (Claude Sonnet 5.5) triages each email that
passes the exit check and drafts a reply using the placeholders; code puts the details back and does the
arithmetic.

**Status: pre-registered. The test emails do not exist yet.** This commit holds the plan and the frozen code. The
test batch will be generated only after this commit is public, and the results will be added on top of it in a
later commit, without changing this one.

## What is here

- `PREREGISTRATION-R2.md`: the question, the rules, every measurement and what each result would mean, and what
  will not be claimed.
- `pgw/`: the frozen code. `FROZEN.json` pins every script's SHA-256 and the versions of Python and eight packages.
- `tests/`: the test suite.
- `data/crm.json`: the synthetic customer records. `data/test-briefs.jsonl`: the 300 test briefs, each with its
  expected answer. The code in `pgw/` writes both from fixed seeds (`CRM_SEED` = 1 in `pgw/crm.py`, `TEST_SEED` =
  20261006 in `pgw/run.py`).
- `notes/`: the model-ID check, and the recorded behaviour of the configured detector and of Presidio as shipped,
  cited by the pre-registration and its tests.

## Check it yourself

With Python 3.13.2, the version `FROZEN.json` records (on another version `check_frozen` lists the difference):

```text
python -m pip install -r requirements.lock
python -m pytest -q
python -c "from pathlib import Path; from pgw.manifest import check_frozen; print(check_frozen(Path('FROZEN.json')) or 'matches FROZEN.json')"
```

## Synthetic data

Every person, address, account, order and company in the data is invented; the card numbers are payment providers'
published test numbers. Names, streets, towns, postcodes, the company's name and the email domains may coincide
with real ones.

## Licence

MIT. See `LICENSE`.
