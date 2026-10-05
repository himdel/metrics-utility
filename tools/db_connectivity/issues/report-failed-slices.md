# metrics-utility - report failed collection slices

- Type: Bug
- Component: aap-metrics
- Workstream: Imperial Services

## Problem

Failed collections are skipped before packaging. `data_collection_status.csv`
only describes packaged collections, so failed slices disappear completely.
An incomplete run can exit `0`, log `Analytics collected`, and produce archives
whose status rows are all `ok`. The offline validator accepts these archives.

If every data collector fails, no archive or machine-readable failure report is
produced. The manifest correctly lists existing files, but cannot establish run
completeness.

## Reproduce

With compose running, from the repository root, choose a new output directory:

```bash
uv run python tools/db_connectivity/reproduce.py \
  --output /tmp/gather-report-failed-slices --ship \
  --cases collector-sql-error all-sql-error second-slice-close
```

`collector-sql-error` delivers three of four expected archives and exits `0`;
none of the status CSVs mentions the failed first job-host-summary slice.
`all-sql-error` exits `1` without a failure report. `second-slice-close` delivers
one successful archive before the remaining slices fail.

## Action

Track attempted enabled collectors and their slices independently of package
membership. Produce a final machine-readable outcome covering failures, including
all-failed runs, and log an explicit partial-success summary.

Define where the run-level report is stored or shipped: earlier sliced archives
are already delivered before later failures are known. Align any status payload
change with schemas, the offline validator, and the billing ingestion contract.

## Acceptance criteria

- [ ] Every attempted enabled slice has an observable outcome, including its collector, interval, and failure reason.
- [ ] Failed slices remain observable when no data archive is produced.
- [ ] Missing or partial CSVs are never represented as successfully collected files in the manifest.
- [ ] Partial runs log successful/failed slice counts instead of an unqualified success message.
- [ ] Individual collector failures remain nonfatal when useful data is successfully collected/shipped; an all-failed run exits nonzero.
- [ ] Regression tests cover first-slice failure followed by success, later-slice failure after shipping, and all-failed collection.
- [ ] Tests verify the agreed reporting contract against schemas/validators and supported ingestion behavior.

## References

- [Investigation and captured evidence](../README.md)
- `metrics_utility/base/collector.py`: `_gather_csv_collections()`
- `metrics_utility/base/collection_data_status.py`: `data_collection_status()`
- `metrics_utility/management/commands/gather_automation_controller_billing_data.py`: `handle()`
