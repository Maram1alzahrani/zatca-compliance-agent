# Synthetic Dataset v1

This dataset contains fully synthetic UBL 2.1 invoices for the selected ZATCA educational POC checks.

## Split policy

| Split | Cases | Permitted use before Phase 13 |
|---|---:|---|
| Development | 48 | Validator and pipeline development |
| Validation | 32 | Design verification and tuning checks |
| Final Test | 32 | No validator, prompt, RAG, or agent tuning |

Invoice XML, metadata, error-injection records, and ground truth are stored separately. Invoice filenames and XML payloads do not contain labels. All companies, identifiers, items, and monetary values are synthetic.

The Final Test control files are hashed in `final_test_seal.json`. The Phase 8 audit script accepts only Development and Validation. Final Test evaluation is intentionally deferred to Phase 13.

Passing this dataset's selected checks does not imply ZATCA approval, certification, clearance, reporting, or full compliance.
