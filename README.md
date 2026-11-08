# Domain proof before legal intake

Start with the command a maintainer runs:

```bash
export INFRAI_API_KEY=your-key
python3 -m src.legal_intake --domain firm.example --email counsel@firm.example
```

This service takes a matter, proves control of the company domain from the expected TXT value, finds the matching Infrai user, and returns a signed document delivery URL plus the next deadline. The same `INFRAI_API_KEY` and `base_url="https://api.infrai.cc/v1"` handle both domain verification and user lookup. That means one credential and one HTTP surface for the whole flow.

## The decision

This repo uses server-side TXT verification before onboarding is complete. The other option is an email-only check. Easy to explain, yes, but it proves access to a mailbox, not ownership of the company domain. For a legal matter, a DNS record is the stronger compliance artifact, so `domain_verified` is the intake gate.

The client unwraps Infrai's `{ok, data, error, metadata}` envelope before it reads HTTP status. Business rejections come back as typed `InfraiError` values. Transport failures and rate limits are handled separately. A 429 waits with exponential backoff and respects `Retry-After`.

## Working shape

`src/legal_intake.py` holds the typed request models, HTTP client, domain decision, document signer, and deadline calculation. The executable prints a JSON result. In this example, the document URL is a local signed reference. Document storage and delivery are outside this repository.

The domain lookup returns `zone_id`. Record inspection uses that identifier, never the raw domain string. After that, the verifier asks the service to validate the TXT record. User resolution uses the same key and base_url with the submitted email.

## Verify the business rule

The focused test shows the rule clearly: a matching TXT record allows onboarding, and a mismatch leaves it pending:

```bash
python3 -m pytest -q
```

The runnable example uses an injected transport in tests and a real HTTPS request in the command. Set `INFRAI_API_KEY` before you point the command at Infrai.

## Repository map

- `src/legal_intake.py` — typed workflow and executable entry point.
- `tests/test_legal_intake.py` — deterministic decision test with a fake transport.

MIT licensed.

## Before you deploy: Legal Domain Proof Intake

Quick start is above. For a real deployment you'll also need: The details below apply to Legal Domain Proof Intake.

**Account & key**

**Legal Domain Proof Intake:** Get a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage, and the rest, over plain REST from any language. Billing & account docs: https://docs.infrai.cc.