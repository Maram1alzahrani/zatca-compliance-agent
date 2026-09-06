# Phase 1 — MVP Scope Decision

Status: **FROZEN FOR PHASES 3–7**  
Decision date: 2026-09-05  
Project: ZATCA E-Invoicing Compliance Agent (Educational / Portfolio POC)

## 1. Goal

Build a pre-submission assistant that evaluates a deliberately narrow set of deterministic checks against synthetic Saudi electronic invoices, retrieves the official evidence behind each finding, and produces an evidence-grounded report.

The POC does **not** certify an invoice, submit it to ZATCA, replace ZATCA's SDK, or provide tax/legal advice.

## 2. Frozen document profile

| Dimension | MVP decision |
|---|---|
| Document | UBL 2.1 `Invoice` XML |
| Saudi invoice class | Standard Tax Invoice (B2B) |
| Invoice type | `cbc:InvoiceTypeCode = 388` |
| Saudi subtype | First two positions of `@name` are `01`; base case `name="0100000"` |
| Transaction flags | Base cases only: third-party, nominal, export, summary, and self-billing flags are off |
| VAT scenario | Domestic Saudi supply, standard-rated (`S`) VAT only |
| Currency | Document currency `SAR`; VAT accounting currency `SAR` |
| Lines | One or more ordinary positive invoice lines |
| Allowances/charges | Excluded from initial dataset and validator behavior |
| Prepayments | Excluded |
| Credit/debit notes | Excluded |
| Exempt/zero-rated/out-of-scope VAT | Excluded |
| Security lifecycle | No signing, stamping, clearance/reporting, or API submission |
| Data | Fully synthetic only |

## 3. Eight implemented check groups

The internal check is a testable bundle. It may cite more than one official business rule; official rule IDs are never replaced by our internal IDs.

1. `MVP-XML-001` — XML well-formedness and UBL 2.1 schema validity.
2. `MVP-ID-001` — invoice number exists and is non-empty.
3. `MVP-DATE-001` — issue date exists, uses `YYYY-MM-DD`, and is not in the future.
4. `MVP-TYPE-001` — standard Tax Invoice code/subtype is the frozen profile (`388`, subtype `01`).
5. `MVP-SELLER-001` — seller name and seller VAT identifier exist; VAT identifier is 15 digits and begins/ends with `3`.
6. `MVP-BUYER-001` — buyer name exists for the Tax Invoice profile.
7. `MVP-LINE-001` — each line net amount follows the official line-net formula; document line-net sum equals the sum of line net amounts.
8. `MVP-VAT-TOTAL-001` — standard-rate VAT breakdown and document totals reconcile using official two-decimal calculation rules.

Detailed evidence, applicability, examples, and planned validation logic are in `kb/rules/verified_mvp_rules.yaml`.

## 4. Explicitly excluded from the MVP compliance decision

- QR payload generation or cryptographic validation.
- Cryptographic stamp/signature, certificate, invoice hash, previous invoice hash, and invoice counter.
- ZATCA clearance/reporting APIs and production credentials.
- Human-readable PDF/A-3 generation.
- Seller/buyer national-address completeness beyond the selected checks.
- Code-list coverage beyond the frozen profile.
- Allowances, charges, prepayments, multiple VAT categories, exemption reasons, export, nominal, summary, self-billing, third-party invoicing, and notes.
- Tax interpretation, commercial validation, fraud detection, or legal conclusions.

## 5. Why QR is deferred

The XML standard points QR construction to the Security Features Implementation Standards. QR content and responsibility interact with the invoice subtype, cryptographic stamp, and ZATCA integration lifecycle. A shallow “QR exists” check would create a strong-looking but misleading claim. QR will be reconsidered only after a separate security-profile phase using official security specifications and SDK fixtures.

## 6. Output language constraint

Permitted conclusion:

> Passed the selected checks implemented in this proof of concept.

Forbidden conclusions include “ZATCA Approved”, “Officially Compliant”, “ZATCA Certified”, or equivalent wording.

## 7. Gate to Phase 3

Phase 3 may start only when:

- every active internal check is `VERIFIED` in the rule registry;
- each check has official identifiers and a stable source reference;
- the distinction between official severity and internal POC severity is explicit;
- all deferred ideas remain excluded from evaluation labels and compliance decisions.
