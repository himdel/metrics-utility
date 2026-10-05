# metrics-utility - handle DB disconnects through finalization

- Type: Bug
- Component: aap-metrics
- Workstream: Imperial Services

## Problem

Collector exceptions are caught, but a dead DB connection subsequently raises
during finalization and advisory-lock release. The CLI exits `1` even when an
independent collector successfully delivered data. The lock-release exception
can also obscure the original finalization exception.

In ship mode, finalization runs before cleanup without a protective `finally`.
A mid-stream disconnect left a 634-byte partial CSV in staging; later-slice
failure also left temporary copies of already-delivered archives.

## Reproduce

With compose running, from the repository root, choose a new output directory:

```bash
uv run python tools/db_connectivity/reproduce.py \
  --output /tmp/gather-handle-disconnects --ship \
  --cases streaming-close second-slice-close collector-close-with-vcpu
```

Inspect `stderr.log`, `remaining_stage_files`, and archive paths in each
`result.json`. The vCPU case delivers its archive, then exits `1` because DB
finalization/lock cleanup fails.

## Action

Make dead-session lock release safe without suppressing unrelated database
errors. PostgreSQL releases session advisory locks when that session ends.
Handle DB-dependent finalization failures explicitly and guarantee staging
cleanup on ordinary exceptions and detected disconnects.

If connection recovery is introduced, account for loss of the original advisory
lock before resuming DB work. Preserve the primary failure and describe delivered
data and finalization failures in the final run outcome.

## Acceptance criteria

- [ ] Releasing an advisory lock on a confirmed dead session does not introduce a secondary fatal exception.
- [ ] Finalization failure is logged explicitly and does not mask the original collection failure.
- [ ] Successfully delivered independent data is recognized as partial success, consistent with the failure-reporting issue.
- [ ] Runs with no useful collected data still return a clear nonzero outcome.
- [ ] Staging and disposable temporary archives are cleaned on detected disconnects and finalization exceptions; promised dry-run evidence remains inspectable.
- [ ] Partial CSVs are never packaged as successful output.
- [ ] Any reconnection path reacquires the required lock before resuming protected DB work.
- [ ] Regression tests cover lock release on a dead session, finalization failure after delivery, and mid-stream cleanup.

## References

- [Investigation and captured evidence](../README.md)
- [Report failed collection slices](report-failed-slices.md)
- `metrics_utility/library/lock.py`: `lock()`
- `metrics_utility/automation_controller_billing/collector.py`: `gather()`, `_gather_finalize()`
- `metrics_utility/base/collector.py`: `_gather_cleanup()`
- `metrics_utility/library/collectors/util.py`: `_copy_table_files()`
