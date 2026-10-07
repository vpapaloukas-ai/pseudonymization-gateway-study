# Pseudonymization gateway study

A pre-registered test of a customer-support pipeline designed to keep customers' details away from the AI model
that reads their emails. Known values from the customer's record, in the forms the gateway lists, are replaced by
placeholders; a configured detector runs over the rest; an exit check holds the email on any known value on its
list, any high-risk value (a card or bank number, for example) and any leftover pattern. Sections 6.1 and 6.9 of
the pre-registration list what these layers do not catch. The model (Claude Sonnet 5.5) triages each email that
passes the exit check and drafts a reply using the placeholders; code puts the details back and does the
arithmetic.

**Status: results added.** Push 1 (commit `af63f1ce`) holds the pre-registration and the frozen code, and the test
batch was generated after it was public (see "Order of events" for the clocks behind that). A dated amendment
(commit `3a7b2c05`, pre-registration section 12) then withdrew the human send-readiness read; section 12 records it
as made before any result was read. This commit adds the test batch, the scored run and the results on top of those
two commits. Of the files they hold, only this README changes.

## Results

Every figure below is a key of `results/run/summary.json`, defined in pre-registration section 7, unless it is
marked "(not pre-registered)". Those few are summed from `results/run/scores.jsonl` or read from another file that
the sentence names. The per-email rows behind every figure are in `results/run/scores.jsonl`. Every count is
"k of n" with its unit, over 300 synthetic English test emails, none dropped (`generation`: 300 briefs, 300
accepted at the first attempt). One configuration: Claude Sonnet 5.5 as the model under test (306 of 306 replies
reported `claude-sonnet-5-5` and stopped on `end_turn`: `models_reported`, `stops`), Presidio 2.2.364 with
`en_core_web_lg` 3.8.0, the frozen code of `FROZEN.json`, single-turn. The contract layer is not measured (section 3).

**There is no human read.** The send-readiness read of section 7.5 was withdrawn before completion (section 12), and
none of its figures appear here.

### Escalated: every hold, by reason

In the design, a held email is held for review by a person: section 2 (question 4) counts clean emails "held for
review", and `holds.false` in section 7.2 is "clean mail held for review". A person also sends every reply (section
3). This study records which emails are held and why; it does not measure what the person then does.

| Hold reason | Where | Emails |
|---|---|---|
| unrecognised sender | step 1, before the gateway | 30 of 300 (`holds.unrecognised_sender`) |
| high risk: a card or IBAN, as a token or raw, or an NI number pattern | exit check | 64 of 300 (`holds.high_risk`) |
| leftover pattern | exit check | 0 of 300 (`holds.leftover_pattern`) |
| known value | exit check | 0 of 300 (`holds.known_value`) |
| draft check | after the reply | 0 of 300 (`holds.draft_check`) |
| no answer | the model | 0 of 300 (`holds.no_answer`) |

**94 of 300 emails were escalated, all of them held by construction of this test's mix.** Section 5.3 counts, from
the briefs alone, 30 unmatched senders and 64 matched senders with a card or IBAN planted: 94 of 300 held before the
model by construction. The 30 and the 64 held here are those emails (`results/batch/briefs.jsonl`, fields `matched`
and `plants`, against `scores.jsonl`, field `holds`). The escalated share is therefore a property of this mix, not
of real inboxes (section 7.3). No email was held for more than one reason.

**False holds:** 0 of 49 emails with nothing planted were held (`holds.false`).

"Escalated" here means held for a person. It is not the policy's action `escalate`, one of the seven triage actions.

### Handled: a draft that passed every check

**206 of 300 emails were handled** (`value.handled`): sent to the model, answered with a valid reply, and passed by
the draft check. 206 is also the number section 5.3 expected to reach the model, so every email the mix let through
was handled. The share is bounded by the same mix: 94 of the 300 were held before the model by construction.

A handled draft is one that passed every check, not one that is right. The measurements of the handled drafts
follow.

### Measurements of the handled

**Triage**, each field against the policy's answer (the gold):

| Field | Over handled | Over all emails |
|---|---|---|
| category | 200 of 206 | 200 of 300 |
| urgency | 206 of 206 | 206 of 300 |
| order | 206 of 206 | 206 of 300 |
| action | 201 of 206 | 201 of 300 |

Keys: `value.triage.<field>.over_handled` and `.over_all`; over all emails, a held email counts as not correct. The
five wrong actions are `test-056`, `test-079`, `test-104`, `test-223` and `test-259` (`scores.jsonl`, field
`triage`), all with the gold action `escalate` (the policy's action, not a hold). No check in the pipeline flags a
wrong triage, so all five are handled drafts.

**By gold action** (`value.by_action.<action>`, counts only; section 7.4 allows no rate below n = 10, and this table
gives none). Here `escalate` is the policy's action `escalate`, not "escalated" as in the holds above:

| Gold action | Emails | Handled | Action right, of handled |
|---|---|---|---|
| escalate | 135 | 93 | 88 of 93 |
| explain | 77 | 52 | 52 of 52 |
| refund_item | 27 | 15 | 15 of 15 |
| resend | 27 | 21 | 21 of 21 |
| update_address | 16 | 11 | 11 of 11 |
| full_refund | 9 | 7 | 7 of 7 |
| cancel | 9 | 7 | 7 of 7 |

Section 7.4 calls late-delivery `resend` effectively untested: 3 such emails were expected to reach the model.

**Reply check:** 206 of 206 handled replies pass `reply_correct` (`value.reply.over_handled`; 206 of 300 over all
emails). It checks that the reply contains the customer's or the first-name token, the gold order's token when the
gold has an order, and, when the gold has an amount, that amount as a figure in the restored reply (not a token).
**It is a containment check, not a quality measure**
(section 7.5): a reply can pass it and still be wrong (section 6.9, item 12).

**Repeats:** 50 handled emails were called three times each (section 5.6). For each of the 50, the three calls gave
the same handled flag, the same all-four-triage-fields result and the same reply check (`variation`). That key does
not compare the reply texts.

**The quality evidence** is the 10 replies in `SAMPLES.md`, drawn by the pre-registered seed from the handled
emails and published unedited beside their emails. Readers judge them for themselves. Drawing from handled emails
means the sample conditions on the run's holds (section 5.6).

### Details the company holds: the known values

- **0 of 733** mentions of the sender's own record, in the forms the gateway lists, were in what was sent
  (`leaks.known.listed.mentions`). The denominator counts every such mention in the 300 original emails, and a held
  email leaks 0. In the 206 emails sent: **0 of 488** (`leaks.known.listed.mentions_sent`). The exit check held no
  email for a known value (0 of 300, `holds.known_value`), so the zero in the sent emails is the gateway's masking,
  not the exit check holding emails back. The other 245 mentions (733 minus 488) are in the 94 emails held for the
  reasons above, and count as 0 because those emails were held.
- **Out of the box, for contrast:** Presidio as shipped, with its default recognisers and no CRM and no exit check
  (section 4.4), would have left **133 of 733** in its payload (`contrast.known.listed.mentions`), on the same
  denominator. 50 of those 133 are in the 94 emails held before the model (not pre-registered). On the 206 sent
  emails the comparison is **83 of 488** out of the box against 0 of 488 (not pre-registered: summed from
  `scores.jsonl`, field `contrast`, over the rows with `sent` true).
- **Where the list stops:** **5 of 54** mentions in forms the list does not cover reached the model
  (`leaks.known.unlisted.mentions`; 5 of 46 in sent emails, `leaks.known.unlisted.mentions_sent`). All five are
  nicknames of the customer (`test-053`, `test-080`, `test-110`, `test-171`, `test-182`; the forms are in
  `results/run/outbound.jsonl` and `results/batch/gold.jsonl`). Presidio as shipped: 9 of 54 over all emails
  (`contrast.known.unlisted.mentions`), and 5 of 46 over the 206 sent emails (not pre-registered: summed from
  `scores.jsonl`). Over the sent emails, the gateway left as many unlisted mentions as the shipped detector would
  have: 5 of 46 each.

### High-risk values

- **Every card number and IBAN typed into an email was held:** cards 31 of 31 (`high_risk.card`), IBANs 41 of 41
  (`high_risk.iban`); none masked and sent, none reached the model. The exit check's own count is 27 of 27 cards and
  37 of 37 IBANs (`held_at_exit` of `n_at_exit`); the other 4 cards and 4 IBANs were in emails from unrecognised
  senders, held at step 1.
- **Out of the box, for contrast:** Presidio as shipped left 0 of the 72 high-risk values in its payload
  (`contrast.high_risk`). In this run, catching card numbers and IBANs did not separate the gateway from the shipped
  detector.

### Details the company does not hold

| Kind | Values | Masked | Held | Reached the model |
|---|---|---|---|---|
| third-party name | 114 | 81 | 32 | 1 (`test-291`) |
| new phone number | 38 | 28 | 10 | 0 |
| new address | 44 | 27 | 12 | 5 (`test-057`, `test-101`, `test-124`, `test-245`, `test-276`) |

Keys: `unknown.third_party`, `unknown.new_phone`, `unknown.new_address`. "Reached" means a part of the value is in
what was sent (section 7.2): the residue the design leaves to the contract layer, which is not measured. In each of
the five addresses the part that reached the model was the street line; the postcode did not
(`results/run/outbound.jsonl`, `results/batch/gold.jsonl`).

**The held column is the mix bound again.** Every held value in the table lies in one of the 94 emails held by
construction (section 5.3), and none was held for itself: no email was held because of a value the company does not
hold (`scores.jsonl`, fields `unknown` and `holds`, against `results/batch/briefs.jsonl`). Of the 54 held values, 18
are in emails held at step 1 and 36 in emails the exit check held for a card or IBAN (not pre-registered: the sums
of `held` minus `held_at_exit`, and of `held_at_exit`). Over the sent emails only (not pre-registered: `n` minus
`held`), the values that reached the model are 1 of 82 third-party names, 0 of 28 new phone numbers and 5 of 32 new
addresses.

Every detail the auditor or the pattern scan found was a planted or record value, a whole-word part of one, the
company's name or a product: `unknown.unplanned` and `high_risk.unplanned` both have n = 0. Those 1,002 finds are
counted as skipped, not scored (`audit.skipped`, section 6.7).

## How to quote these numbers

The binding forms. Each sentence names its file and key; each escalated or handled share carries the mix bound.
Quote every number with its denominator and its set, never pooled, and nothing from the withdrawn human read. None of
these numbers describes the contract layer, real data, other languages, multi-turn conversations or agents
(pre-registration section 10).

1. **Escalated.** "Of 300 synthetic support emails, 94 were escalated to a person: 30 because the sender was not on
   record and 64 because they contained a card or bank number. All 94 were held by construction of the test's own
   mix, so the share describes this mix, not a real inbox." (`summary.json`: `holds.unrecognised_sender`,
   `holds.high_risk`; pre-registration section 5.3)
2. **No other hold.** "No email was held for a leftover pattern, a known value, a failed draft check or a missing
   answer: 0 of 300 each, and 0 of the 49 emails with nothing planted." (`holds.leftover_pattern`,
   `holds.known_value`, `holds.draft_check`, `holds.no_answer`, `holds.false`)
3. **Handled.** "206 of 300 were handled: the model's draft passed every check, for a person to send. The other 94
   were held before the model by construction." (`value.handled`)
4. **Handled: triage.** "On the 206 handled emails the model's triage matched the policy's answer for the category
   in 200, the urgency in 206, the order in 206 and the action in 201." (`value.triage.<field>.over_handled`)
5. **Handled: by action.** "Handled, with the action right, by the policy's action: escalate 88 of 93 handled (135
   emails), explain 52 of 52 (77), refund_item 15 of 15 (27), resend 21 of 21 (27), update_address 11 of 11 (16),
   full_refund 7 of 7 (9), cancel 7 of 7 (9). Here escalate is the policy's action `escalate`, not 'escalated' as in
   form 1." (`value.by_action.<action>`; no rate below n = 10)
6. **Handled: reply check.** "206 of 206 handled replies contained the customer's or the first-name token, the gold
   order's token when the gold has an order, and, when the gold has an amount, that amount as a figure in the
   restored reply. This is a containment check, not a measure of quality." (`value.reply.over_handled`)
7. **Known values.** "0 of 733 mentions of the sender's own record, in the forms the gateway lists, reached the
   model, a held email counting as 0; in the 206 emails sent, 0 of 488. Presidio as shipped would have let 133 of
   733 through, and 83 of 488 in those 206 emails (not pre-registered)." (`leaks.known.listed.mentions`,
   `leaks.known.listed.mentions_sent`, `contrast.known.listed.mentions`; the 83 is summed from `scores.jsonl`)
8. **Where the list stops.** "Over all 300 emails, 5 of 54 mentions in forms the list does not cover reached the
   model, all of them nicknames. Over the 206 sent emails, 5 of 46 reached the model, and Presidio as shipped would
   also have left 5 of 46 (not pre-registered)." (`leaks.known.unlisted.mentions`,
   `leaks.known.unlisted.mentions_sent`; the shipped 5 of 46 is summed from `scores.jsonl`)
9. **High risk.** "Every card number and IBAN typed into an email was held: 31 of 31 and 41 of 41. Presidio as
   shipped also left none of the 72 in its payload." (`high_risk.card`, `high_risk.iban`, `contrast.high_risk`)
10. **Not on record.** "Of details the company does not hold, a part reached the model for 1 of 114 third-party
    names, 0 of 38 new phone numbers and 5 of 44 new addresses; in all five addresses that part was the street
    line. Every held value among them lies in one of the 94 emails held by construction, and none was held for
    itself. Over the sent emails only: 1 of 82, 0 of 28 and 5 of 32 (not pre-registered)." (`unknown.third_party`,
    `unknown.new_phone`, `unknown.new_address`; "reached" as section 7.2 defines it; the street line from
    `results/run/outbound.jsonl` and `results/batch/gold.jsonl`; the held set from `scores.jsonl` against
    `results/batch/briefs.jsonl`)
11. **Cost.** "$7.06 in model calls for the whole test, from token counts: writing and auditing 300 emails, and 306
    replies. The canary calls and the call that stopped the first launch are not counted." (`input_tokens` and
    `output_tokens` in `results/batch/generation.jsonl`, `results/batch/audit.jsonl` and `results/run/replies.jsonl`,
    at the prices of pre-registration section 5.7; the Cost section below)

## What the flags point to

The method is a loop: a check flags an email, the email goes to a person, and a rule is added or changed so that
people no longer handle that kind of email. This run's flags show where a next iteration would start.

**Every candidate below is an unmeasured proposal.** None has been built or run, and nothing here claims that any of
them would reduce the work people do: measuring that needs a new pre-registered run on a fresh test batch (section 9).
Each is derived only from this run's hold reasons (`holds.*` in `summary.json`, field `holds` in `scores.jsonl`) and
cites the emails it comes from. Both reasons that held anything are the ones this test's mix put there by
construction (section 5.3), so the candidates answer the test's design as much as the gateway's behaviour.

**C1. Unrecognised sender** (`unrecognised_sender`, 30 of 300: `test-043`, `test-045`, `test-048`, `test-050`,
`test-065`, `test-069`, `test-073`, `test-075`, `test-076`, `test-084`, `test-088`, `test-089`, `test-103`,
`test-118`, `test-176`, `test-181`, `test-187`, `test-191`, `test-197`, `test-204`, `test-205`, `test-207`,
`test-212`, `test-217`, `test-220`, `test-225`, `test-234`, `test-240`, `test-257`, `test-258`). Step 1 holds an
email whose sender address matches no record, before the gateway runs. Candidate rule: code, not the model, answers
with a fixed text asking the sender to write again from the address on their account, and the held email goes to a
person only if no email from a known address follows.

**C2. Card number or IBAN** (`high_risk`, 64 of 300: `test-003`, `test-010`, `test-011`, `test-012`, `test-018`,
`test-022`, `test-025`, `test-032`, `test-036`, `test-047`, `test-051`, `test-063`, `test-070`, `test-078`,
`test-091`, `test-094`, `test-095`, `test-106`, `test-111`, `test-115`, `test-121`, `test-129`, `test-132`,
`test-134`, `test-135`, `test-136`, `test-137`, `test-138`, `test-139`, `test-146`, `test-148`, `test-151`,
`test-155`, `test-161`, `test-163`, `test-168`, `test-169`, `test-170`, `test-175`, `test-177`, `test-178`,
`test-180`, `test-183`, `test-186`, `test-189`, `test-192`, `test-196`, `test-198`, `test-216`, `test-228`,
`test-237`, `test-238`, `test-242`, `test-247`, `test-248`, `test-253`, `test-256`, `test-265`, `test-269`,
`test-274`, `test-281`, `test-289`, `test-297`, `test-298`). The exit check holds an email with a card number or IBAN
in it, or with a token the gateway put in place of one, or with an NI number pattern. Candidate rule: where the only
exit-check reason is that token (`high_risk_token`), the masked email goes on to the model as usual, and the person
gets a separate task: remove the number from the mailbox and ask the customer not to send card or bank details by
email. Where the exit check finds the raw number itself (`card`, `iban` or `nino`), the email stays held. In this
run the field `held` in `results/run/outbound.jsonl` reads `["high_risk_token"]` for 64 of the 64 high-risk holds
(not pre-registered): in none of them did the exit check find a raw card number, IBAN or NI number pattern.
Section 7.3 counts a masked card number in a sent email as a partial failure of the registered design, because no
person is alerted; this candidate changes that design and would need its own registration.

**No candidate from the other four reasons.** Leftover pattern, known value, draft check and no answer each held 0 of
300 emails, so this run's flags show nothing for a prompt rule or a draft-check pattern to fix. A wrong triage on a
handled email raises no flag in this pipeline, so the triage results above are not a source for this section.

## Order of events

| UTC, 2026-10-07 | Event | Clock and tier | Source |
|---|---|---|---|
| 13:15:44 | Push 1 reaches GitHub: the `branch_creation` of commit `af63f1ce`, the pre-registration and the frozen code | GitHub's repository activity (Linkable) | GitHub's activity API (below); `results/push1-anchor.json` |
| 13:22:45 | Test batch: generation starts | the study's machine (Checkable) | `results/batch/manifest.generate-start-20261007T132245Z.json` |
| 13:22:50 to 13:53:34 | 300 emails written, one attempt each | the study's machine (Checkable) | `at` in `results/batch/generation.jsonl` |
| 13:53:37 to 14:09:20 | 300 audits | the study's machine (Checkable) | `at` in `results/batch/audit.jsonl` |
| 14:09:22 | Test batch complete | the study's machine (Checkable) | `results/batch/manifest.generate-end-20261007T132245Z.json` |
| 14:09:46 | Scored run, first launch | the study's machine (Checkable) | `results/run/manifest.start-20261007T140946Z.json` |
| 14:10:15 to 14:24:10 | 201 replies, then the launch stops (below) | the study's machine (Checkable) | `at` in `results/run/replies.jsonl` |
| 14:25:09 | Scored run, second launch, same directory | the study's machine (Checkable) | `results/run/manifest.start-20261007T142509Z.json` |
| 14:25:38 to 14:32:47 | 105 replies, from `test-208` repeat 1 on | the study's machine (Checkable) | `at` in `results/run/replies.jsonl` |
| 14:32:50 | Scored run complete | the study's machine (Checkable) | `results/run/manifest.end-20261007T142509Z.json` |
| 15:16:36 | The amendment reaches GitHub: the `push` to commit `3a7b2c05`, which withdraws the human read | GitHub's repository activity (Linkable) | GitHub's activity API (below); `results/amendment-anchor.json` |

**Linkable: the two GitHub times.** They are GitHub's own clock, the third party in this table. GitHub's repository
activity API keeps a record of each push, and a later push does not overwrite an earlier record. Push 1 is the
`branch_creation` record whose `after` is `af63f1ce`, at 13:15:44Z; the amendment is the `push` record from
`af63f1ce` to `3a7b2c05`, at 15:16:36Z. Both are read with
`gh api repos/vpapaloukas-ai/pseudonymization-gateway-study/activity`, or at
`https://api.github.com/repos/vpapaloukas-ai/pseudonymization-gateway-study/activity`, and each anchor file keeps its
record as read, with that command. The anchor files also keep the repository's `pushed_at` as it was read right
after each push, which is Checkable: a value read at the time.

**Checkable: every other time.** It is the clock of the machine that ran the study, written into the published files
by the code; no third party recorded it. So the order of the batch and the run against the two pushes rests on that
machine's clock. Section 12 records the amendment as made after the scored run and before any of its results were
read; that is the study's own statement, and no file here can show when a result was first read. The amendment's
first push attempt was refused by GitHub with HTTP 500 during a GitHub incident, and a retry succeeded at the time
above (the operator's record).

`data/test-briefs.jsonl` and `data/crm.json`, published in push 1, have the SHA-256 that `results/batch/batch.json`
records for the batch's `briefs.jsonl` and `crm.json`: the batch's briefs and records are the ones push 1 published,
byte for byte.

**The scored run was launched twice.** The first launch stopped on an API error after 201 replies. Under the
pre-registration's Failures rule (section 4.3: an API error stops the run instead of being scored, and a relaunch
resumes at the next unfinished call), the second launch ran in the same directory and made the remaining 105. Both
start manifests and both canaries are in `results/run/`, and `replies.jsonl` holds 306 rows with no email and repeat
pair twice. The error was an overload (`OverloadedError`, HTTP 529, request `req_011Cfo2dqJHTVimxzDM7cwPM`). A
stopped call writes no row, so that detail comes from the operator's record, not from a file here.

## Cost

From the token counts in the published rows (`input_tokens`, `output_tokens`), at the prices of pre-registration
section 5.7, read on 2026-10-06: Claude Opus 5.5 at $4 / $20 and Claude Sonnet 5.5 at $2 / $10 per million input /
output tokens.

| Step | File | Model | Calls | Input tokens | Output tokens | Cost |
|---|---|---|---|---|---|---|
| Writing the 300 test emails | `results/batch/generation.jsonl` | `claude-opus-5-5` | 300 | 219,924 | 113,293 | $3.15 |
| Auditing them | `results/batch/audit.jsonl` | `claude-opus-5-5` | 300 | 239,359 | 21,150 | $1.38 |
| The scored run's replies | `results/run/replies.jsonl` | `claude-sonnet-5-5` | 306 | 729,141 | 107,195 | $2.53 |
| **Total** | | | | | | **$7.06** |

The canary call at each launch and the call that stopped the first launch are not counted: none of these files
records their tokens. The pre-registered estimate was about $7.24 (section 5.7).

## What is here

- `PREREGISTRATION-R2.md`: the question, the rules, every measurement and what each result would mean, and what
  will not be claimed. Section 12 holds the amendments.
- `pgw/`: the frozen code. `FROZEN.json` pins every script's SHA-256 and the versions of Python and eight packages.
- `tests/`: the test suite.
- `data/crm.json`: the synthetic customer records. `data/test-briefs.jsonl`: the 300 test briefs, each with its
  expected answer. The code in `pgw/` writes both from fixed seeds (`CRM_SEED` = 1 in `pgw/crm.py`, `TEST_SEED` =
  20261006 in `pgw/run.py`).
- `notes/`: the model-ID check, and the recorded behaviour of the configured detector and of Presidio as shipped,
  cited by the pre-registration and its tests.
- `results/batch/`: the test batch as generated: the emails, the briefs, the gold, the audit, the writer's raw
  responses (`generation.jsonl`), the CRM, `batch.json` with the SHA-256 of every batch file, and the manifests and
  canary of the generation step.
- `results/run/`: the scored run: what was sent (`outbound.jsonl`), the Presidio-as-shipped payloads
  (`contrast.jsonl`), the model's raw responses (`replies.jsonl`), the restored replies (`inbound.jsonl`), the
  per-email scores (`scores.jsonl`), `summary.json`, both start manifests, the end manifest and both canaries.
- `results/push1-anchor.json`, `results/amendment-anchor.json`: GitHub's records of push 1 and of the amendment: the
  repository-activity record of each push, and the repository and commit fields read back from GitHub's API right
  after each push, with the `gh api` commands that return those fields (`read_back_with`).
- `SAMPLES.md`: the 10 published replies beside their emails, unedited.

## Check it yourself

With Python 3.13.2, the version `FROZEN.json` records (on another version `check_frozen` lists the difference):

```text
python -m pip install -r requirements.lock
python -m pytest -q
python -c "from pathlib import Path; from pgw.manifest import check_frozen; print(check_frozen(Path('FROZEN.json')) or 'matches FROZEN.json')"
```

To re-score the published run from its published replies, with no model call: the runner checks the batch against
`batch.json`, runs the gateway, the exit check and the scorer again, and writes into `rescore/`.

```text
python -c "import pathlib, shutil; pathlib.Path('rescore').mkdir(); shutil.copy('results/run/replies.jsonl', 'rescore')"
python -m pgw.run run --batch results/batch --out rescore --model-stage replay
python -c "import filecmp; print(all(filecmp.cmp('rescore/' + f, 'results/run/' + f, shallow=False) for f in ('outbound.jsonl', 'contrast.jsonl', 'inbound.jsonl', 'scores.jsonl', 'summary.json')))"
```

The last line prints `True` when the re-scored files equal the published ones byte for byte. On 2026-10-07 it
printed `True` on a copy of this tree.

## Synthetic data

Every person, address, account, order and company in the data is invented; the card numbers are payment providers'
published test numbers. Names, streets, towns, postcodes, the company's name and the email domains may coincide
with real ones. A record's title (Mr, Ms, Dr or Mx) is drawn independently of its first name (`pgw/crm.py`), so
pairings such as Ms Daniel Ashby (record C159, the sender of test-194 in `SAMPLES.md`) are in the data as generated.
`results/` and `SAMPLES.md` hold the synthetic emails and the models' responses as they were produced, unedited.

## Licence

MIT. See `LICENSE`.
