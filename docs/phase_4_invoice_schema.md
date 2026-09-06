# Phase 4 — Invoice Schema

Status: **IMPLEMENTED AND TESTED**  
Date: 2026-09-05

## Objective

Define the stable boundary between future XML parsing and deterministic validation. The parser will preserve values from an invoice candidate in a canonical structure; validators will interpret those values using the verified rule registry.

## Design decision: represent invalid invoices

The canonical schema is intentionally compliance-neutral. Business fields are nullable and values such as an incorrect invoice type or malformed date remain representable. If the schema itself required `388`, `0100000`, or a valid VAT number, invalid cases would be rejected before the appropriate rule validator could produce a traceable finding.

The schema therefore checks structural concepts only:

- known object and field names;
- scalar versus collection shape;
- decimal lexical representation;
- separation of parties, lines, VAT breakdowns, and totals;
- stable schema version.

ZATCA business constraints remain in `kb/rules/verified_mvp_rules.yaml`.

## Canonical sections

| Section | Purpose |
|---|---|
| Header | Invoice ID, UUID, issue date/time, type/subtype, currencies |
| Seller and buyer | Names and VAT identifiers required by selected checks |
| Lines | Quantity, price basis, allowances/charges, net amount, VAT fields |
| VAT breakdowns | Category/rate-level taxable and VAT amounts |
| Totals | BT-106 through BT-115 values needed for reconciliation |

## Numeric policy

All XML decimal values are stored as strings in the canonical object. Future deterministic validators will convert them to `decimal.Decimal`. Binary floating-point must not be used for VAT or monetary calculations.

The lexical schema permits negative values and more than two decimal places so targeted validators can detect violations instead of losing the original evidence during parsing.

## Separation from dataset records

The canonical invoice contains neither raw XML nor dataset metadata. Phase 5 must store these separately:

1. raw invoice XML;
2. normalized canonical invoice, if cached;
3. case metadata;
4. ground-truth labels;
5. error-injection record.

The agent must receive only the raw invoice or canonical parser output—not labels or injection metadata.

## UBL mapping

`src/models/ubl_field_map.yaml` maps every canonical business field to a ZATCA/EN business term and namespace-aware UBL XPath. It is a parser contract, not an XPath implementation. Fields that can occur multiple times—invoice lines and VAT breakdowns—use `[]` in canonical paths.

## Scope boundary

The model includes several zero/default-related fields such as allowances, charges, and prepayments because official total formulas reference them. Initial Phase 5 cases will keep them absent or zero under the frozen scope. Their presence in the schema does not expand the MVP or make unsupported scenarios decision-eligible.

