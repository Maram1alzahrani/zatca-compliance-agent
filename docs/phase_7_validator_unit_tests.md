# Phase 7 — Deterministic Validator Unit Tests

Status: **STABLE**  
Date: 2026-09-06

## Objective

Verify each Phase 6 deterministic component independently from the synthetic development cases. These tests protect the validator contract and arithmetic behavior; they are not model evaluation and they do not replace the future unseen Final Test Set.

## Files added

- `tests/invoice_factory.py`: small canonical-object factory with synthetic defaults.
- `tests/__init__.py`: enables reliable standard-library test discovery and future CI execution.
- `tests/test_validators_unit.py`: direct tests for all eight rule validators.
- `tests/test_parser_unit.py`: parser mapping, normalization, missing-file, root-element, and external-entity tests.
- `tests/test_orchestrator_unit.py`: result cardinality/order, XSD-unavailable behavior, and fail-closed tests.

## Coverage matrix

| Component | Tested behavior |
|---|---|
| `MVP-XML-001` | Valid UBL Invoice, unparseable input, well-formed XSD-invalid input, unavailable trusted XSD |
| `MVP-ID-001` | Present, missing, empty, whitespace-only |
| `MVP-DATE-001` | Past date, validation day, missing, wrong format, impossible date, future date |
| `MVP-TYPE-001` | Frozen `388` and `0100000`, invalid and missing codes |
| `MVP-SELLER-001` | Name presence, whitespace, VAT length, digit-only form, required first/last digit |
| `MVP-BUYER-001` | Present, missing, empty, whitespace-only name |
| `MVP-LINE-001` | Formula, half-up rounding, base quantity, allowance/charge, multiple lines, zero divisor, missing/malformed/non-finite/extreme decimals, BT-106 |
| `MVP-VAT-TOTAL-001` | Breakdown presence/category/taxable/tax, half-up VAT, BT-109/110/112, allowance/charge, missing totals, malformed/non-finite/extreme decimals |
| Parser | Canonical mapping, whitespace normalization, missing file, wrong root, external entity not expanded |
| Orchestrator | Exactly eight ordered unique results, `NOT_RUN`, independent checks, fail-closed behavior |

## Defects found and fixed

1. Whitespace-only invoice, seller, or buyer names could pass direct canonical validation. The validators now require non-whitespace content.
2. Python `Decimal` accepts `NaN` and infinities. These values are now rejected explicitly.
3. Extreme finite decimals can exceed decimal arithmetic/rounding bounds. Arithmetic exceptions are now converted into structured rule failures instead of escaping the pipeline.

These are implementation-hardening changes only. No new ZATCA rule was added and the frozen MVP scope remains unchanged.

## Verification result

- Phase 7 unit tests: **41 passed**.
- Whole project suite: **63 passed**.
- Python compilation check: **passed**.
- Existing 12-case development prediction/ground-truth smoke check: **passed**.

## Important interpretation

Passing these tests means the selected implementation behaves as specified for the tested cases. It does not mean the invoice is ZATCA-approved, certified, cleared, reported, or fully compliant. ZATCA Schematron/business-rule coverage, security features, QR requirements, signatures, hashes, clearance/reporting, and production integration remain outside this MVP stage.

## Phase boundary

Phase 7 does not generate additional data. Dataset scaling and split design belong to Phase 8. Final metrics must not be reported from the development cases used here.
