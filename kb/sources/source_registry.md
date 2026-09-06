# Official Source Registry — Phase 2

Verification date: 2026-09-05

Only ZATCA-hosted sources below are accepted as normative evidence for the MVP. The website page-update date is not treated as a new document version.

| Source ID | Official title | Version/date | Role in this POC | Official URL |
|---|---|---|---|---|
| `SRC-XML-1.2` | Electronic Invoice XML Implementation Standard | Version 1.2, 19 May 2023 | Syntax, calculation rules, code lists, KSA rules, validation sequence | https://zatca.gov.sa/ar/E-Invoicing/SystemsDevelopers/Documents/20230519_ZATCA_Electronic_Invoice_XML_Implementation_Standard_%20vF.pdf |
| `SRC-DD-2023-05-19` | Electronic Invoice Data Dictionary | 19 May 2023 | Business-term definitions, UBL paths, cardinalities, per-document KSA status, examples | https://zatca.gov.sa/ar/E-Invoicing/SystemsDevelopers/Documents/20230519_EInvoice_Data_Dictionary%20vF.xlsx |
| `SRC-SPECS-PAGE` | E-Invoice specifications | Page last updated 12 Jan 2026; page lists both documents as 19 May 2023 | Confirms the currently published specification downloads | https://zatca.gov.sa/en/E-Invoicing/SystemsDevelopers/Pages/E-Invoice-specifications.aspx |
| `SRC-RESOLUTION` | Controls, Requirements, Technical Specifications and Procedural Rules for Implementing the Provisions of the E-Invoicing Regulation | Official English translation published by ZATCA; PDF currently hosted by ZATCA | Legal/implementation context and Annex requirements; Arabic prevails on discrepancy | https://zatca.gov.sa/en/E-Invoicing/Introduction/LawsAndRegulations/Documents/E-Invoicing%20Implementation%20Resolution_EN.pdf |
| `SRC-SDK-PAGE` | Compliance and Enablement Toolbox — Download SDK | Page last updated 28 May 2025 | Official operational verification reference and limitation language | https://zatca.gov.sa/en/E-Invoicing/SystemsDevelopers/ComplianceEnablementToolbox/Pages/DownloadSDK.aspx |

## Currency finding

As of the verification date, ZATCA's current E-Invoice Specifications page still identifies the Data Dictionary and XML Implementation Standard as the 19 May 2023 editions. No later specification version was listed on that page. This is a bounded claim about the official publication page checked on the date above, not a claim that ZATCA can never publish a newer release.

## Source precedence used

1. ZATCA KSA-specific rules and business requirements.
2. Customized EN 16931 business rules incorporated by ZATCA.
3. UBL 2.1 schema/syntax.

The XML Implementation Standard itself describes KSA requirements as overriding EN 16931 in case of conflict, and EN 16931 as overriding base UBL specifications.

## Operational verification policy

Our Python validators will produce POC findings. When the official SDK can be packaged reproducibly in the project environment, its result will be retained as a separate comparison/oracle field; our output must never imply that passing our subset equals passing the official SDK or receiving ZATCA approval.

