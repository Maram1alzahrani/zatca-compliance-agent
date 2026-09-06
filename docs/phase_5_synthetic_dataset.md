# Phase 5 — Small Synthetic Dataset

Status: **IMPLEMENTED AND TESTED**  
Date: 2026-09-06

## Objective

Create a small deterministic development set that proves the data layout, error-injection method, and ground-truth separation before building validators or scaling the dataset.

## Dataset composition

The development split contains 12 fully synthetic invoices:

- one baseline expected to pass the eight selected POC checks;
- one deliberately malformed XML document;
- missing invoice number;
- malformed issue date;
- invalid invoice type code;
- missing seller name;
- invalid seller VAT-number format;
- missing buyer name;
- incorrect invoice-line net amount;
- incorrect document line-net sum;
- incorrect VAT-breakdown amount;
- incorrect VAT-inclusive total.

Each faulty case has exactly one deterministic injection. One injection may legitimately violate more than one verified check. For example, a missing UBL-mandatory invoice ID violates both XSD validation and the explicit invoice-number rule; Ground Truth records both expected rule IDs.

## Storage separation

| Plane | Path | Visible to future Agent? |
|---|---|---|
| Raw invoice XML | `data/synthetic/dev/invoices/` | Yes |
| Neutral metadata | `data/synthetic/metadata/dev.jsonl` | No by default |
| Ground Truth | `data/ground_truth/dev.jsonl` | Never during inference |
| Error-injection audit | `data/synthetic/error_injections/dev.jsonl` | Never during inference |
| Integrity manifest | `data/synthetic/manifests/dev_manifest.json` | Evaluation harness only |

Invoice filenames are neutral sequential identifiers and contain no error class or expected result.

## Numeric generation

All monetary values are produced with Python `Decimal` and `ROUND_HALF_UP`. The baseline contains two ordinary standard-rated lines:

- SAR 100.00 net + SAR 15.00 VAT;
- SAR 40.00 net + SAR 6.00 VAT;
- document totals: SAR 140.00 net, SAR 21.00 VAT, SAR 161.00 inclusive.

## Correction-safety labels

Ground Truth distinguishes a known expected value from permission to auto-correct it. Missing identifiers, dates, names, invoice types, and VAT numbers are not safe for automatic correction even though the synthetic generator knows the baseline value. Pure deterministic arithmetic mismatches are marked as candidates for later safe correction and re-validation.

## Current limitation

Phase 5 verifies XML well-formedness for all cases except the intentional syntax-error case. Full UBL XSD and official SDK validation belong to Phase 6 and must not be claimed at this stage. The baseline is therefore a selected-check fixture, not an officially compliant ZATCA invoice.
