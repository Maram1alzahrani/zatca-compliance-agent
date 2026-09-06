# Phase 6 — Deterministic Validators

Status: **STABLE; VERIFIED BY PHASE 7 UNIT TESTS**  
Date: 2026-09-06

## Objective

Parse UBL Invoice XML securely and execute the eight selected checks without an LLM. The output is structured and keyed by the same internal rule IDs used by the Knowledge Base and Ground Truth.

## Pipeline

1. Parse with `lxml` using entity resolution, DTD loading, and network access disabled.
2. Validate the parsed document against UBL Invoice 2.1 XSD.
3. Normalize supported fields into `CanonicalInvoice`.
4. Execute seven content/calculation validators.
5. Return exactly one result per internal rule: `PASS`, `FAIL`, or `NOT_RUN`.

If XML cannot be parsed, the XML check fails and all dependent checks return `NOT_RUN`. The system does not manufacture business findings from an unavailable document.

## Implemented checks

| Internal ID | Deterministic behavior |
|---|---|
| `MVP-XML-001` | Well-formed XML plus UBL Invoice 2.1 XSD |
| `MVP-ID-001` | Non-empty invoice number |
| `MVP-DATE-001` | Exact date format, real date, not after injected validation date |
| `MVP-TYPE-001` | Frozen code `388` and transaction code `0100000` |
| `MVP-SELLER-001` | Seller name plus VAT regex `^3\\d{13}3$` |
| `MVP-BUYER-001` | Buyer name required for selected Tax Invoice profile |
| `MVP-LINE-001` | Line formula and BT-106 reconciliation using `Decimal` |
| `MVP-VAT-TOTAL-001` | Standard VAT breakdown and BT-109/110/112 reconciliation |

## XSD provenance

The XML standard published by ZATCA identifies UBL Invoice 2.1 and OASIS common schemas in section 12. The retained XSD subset comes from the official OASIS UBL 2.1 package. Package and main-schema checksums are recorded in `resources/ubl21/README.md`.

UBL XSD validation is not equivalent to ZATCA Schematron, Security Features, SDK verification, clearance, reporting, or approval.

## Arithmetic policy

- Values are parsed with `decimal.Decimal`.
- Half-up rounding is applied to two decimals.
- Missing or non-decimal operands produce explicit failures rather than implicit zeroes, except optional allowance/charge/prepayment values defined as zero under the frozen profile.
- The validation date is an explicit parameter; tests do not depend on the machine clock.

## Ground Truth correction

Actual XSD execution showed that deleting `cbc:ID` and replacing the ISO date with `01/09/2026` each violates both the explicit content rule and UBL XSD. The Phase 5 Ground Truth now records both expected rule IDs for those cases while retaining one deterministic injection per case.

## Phase boundary

Phase 7 added direct unit coverage for boundary values, missing operands, rounding, malformed and non-finite decimals, multiple lines, parser safety, result ordering, and fail-closed behavior. See `docs/phase_7_validator_unit_tests.md`.
