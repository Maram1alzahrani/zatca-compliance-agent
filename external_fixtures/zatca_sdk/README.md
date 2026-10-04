# External SDK benchmark fixtures

This directory is intentionally empty.

Place only **independently sourced** XML invoices here when running the external benchmark, for example:

- official ZATCA SDK/reference samples obtained under the applicable download terms,
- official ZATCA example XML documents, or
- independently authored fixtures whose expected status was not defined by this repository.

Do not copy files from `data/synthetic/` into this directory and call them external validation.

## Run

After installing/downloading the official SDK locally, inspect its local help output and provide the exact command as a template containing one `{invoice}` placeholder:

```bash
python3 scripts/run_external_sdk_benchmark.py external_fixtures/zatca_sdk \
  --sdk-command 'YOUR_SDK_COMMAND {invoice}' \
  --validation-date 2026-10-04
```

The script never uses `shell=True`. It executes the supplied command as an argument vector, parses the SDK's `GLOBAL VALIDATION RESULT - PASSED|FAILED` line, runs this POC's selected validators, and writes an agreement/disagreement report.

The benchmark result must be interpreted carefully: the official SDK covers more requirements than this POC, so an SDK failure with a POC pass may reflect intentionally missing POC coverage rather than an SDK error.
