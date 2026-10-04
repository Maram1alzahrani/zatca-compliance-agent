# External Validation Protocol

## Objective

Define a reproducible protocol for comparing the POC with independently sourced ZATCA/reference invoice fixtures while keeping provenance, labels, and implementation boundaries explicit.

## Primary benchmark source

Preferred order:

1. Official ZATCA SDK/reference invoice fixtures and validation outputs.
2. Official ZATCA example XML documents from current developer materials.
3. Independently authored UBL 2.1 Saudi invoice fixtures reviewed against official ZATCA rules.

Do not describe repository-generated invoices as external evidence.

## Evaluation questions

1. Does the POC agree with the official/reference oracle on the eight selected rule groups?
2. Which externally valid invoices are incorrectly rejected by the frozen profile?
3. Which externally invalid invoices incorrectly pass the selected checks?
4. Which failures are due to missing rule coverage versus incorrect implementation?
5. Does the optional explanation layer remain evidence-grounded when the invoice source is external?

## Required dataset contract

For every external case record:

- stable case ID,
- source type,
- source URL or provenance note,
- SHA-256 of the XML,
- expected official/reference status,
- expected relevant rule identifiers where available,
- whether the case is inside or outside this POC's frozen scope,
- reviewer notes.

Keep external fixtures and labels separate from the validator implementation.

## Metrics

Report:

- rule-level precision, recall, and F1,
- exact selected-rule-set accuracy,
- false-positive and false-negative counts,
- per-rule support,
- Wilson 95% confidence intervals,
- in-scope versus out-of-scope error breakdown,
- agreement with the official/reference oracle,
- correction success only where the source case is eligible.

Do not headline deterministic exact lookup or fixed workflow order as AI-performance metrics.

## Adversarial regression set

Maintain explicit regression tests for previously uncovered frozen-profile failures, including:

- non-SAR document/tax currency,
- standard category with 0% rate,
- line VAT rate differing from the frozen 15% standard rate,
- VAT breakdown rate differing from the frozen standard rate,
- incorrect BT-115 PayableAmount,
- future additions discovered during external-oracle comparison.

## Reporting principle

Report agreement and disagreement cases transparently, with error analysis and provenance for every external fixture. Keep SDK/reference results separate from the POC's own selected-check results.
