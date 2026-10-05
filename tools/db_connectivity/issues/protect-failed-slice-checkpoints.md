# metrics-utility - prevent checkpoints skipping failed slices

- Type: Bug
- Component: aap-metrics
- Workstream: Imperial Services

## Problem

Checkpoint updates iterate successfully shipped packages. Failed slices are
omitted from packages, so their `Collection.update_last_gathered_entries()` method
never sets the existing failure barrier. A later successful slice can therefore
advance the collector's timestamp beyond an earlier failed interval, preventing
automatic retry of missing data.

**Evidence level: source-inspected risk.** The investigation reproduced an earlier
failed slice followed by a successfully delivered later slice. Persistent
checkpoint behavior was not exercised because compose uses mock Django settings,
not AWX's persistent settings backend.

## Reproduce and confirm

With compose running, from the repository root, choose a new output directory:

```bash
uv run python tools/db_connectivity/reproduce.py \
  --output /tmp/gather-protect-checkpoints --ship \
  --cases collector-sql-error
```

This fails the June 13-14 job-host-summary slice and delivers June 14-15. Add a
regression test that inspects the resulting checkpoint update, then verify that
a subsequent incremental gather requests the missing interval. Include coverage
of persistence through a real AWX settings backend or an integration equivalent.

## Action

Calculate checkpoint progress from all attempted slices and delivery outcomes,
not just the collections present in successful packages. Advance each collector
only through its contiguous completed-and-delivered prefix; stop at the first
failed slice while allowing unrelated collectors to progress.

## Acceptance criteria

- [ ] A successful later slice cannot advance a checkpoint past an earlier collection failure.
- [ ] Delivery failure also prevents advancement past the affected slice.
- [ ] Successful slices preceding the first failure may advance the checkpoint.
- [ ] Failure in one collector does not block an unrelated collector's safe progress.
- [ ] A subsequent gather without an explicit `--since` includes the failed interval.
- [ ] Full-sync checkpoint handling obeys the same failure barrier where applicable.
- [ ] Tests cover first-slice failure/later success, success/later failure, delivery failure, and retry after persistence.
- [ ] The persistent checkpoint risk is confirmed or ruled out with a failing regression test before changing behavior.

## References

- [Investigation and captured evidence](../README.md)
- `metrics_utility/base/collector.py`: `_update_last_gathered_entries()`
- `metrics_utility/base/package.py`: `update_last_gathered_entries()`
- `metrics_utility/base/collection.py`: `update_last_gathered_entries()`
- `metrics_utility/automation_controller_billing/collector.py`: `_gather_finalize()`, `_save_last_gathered_entries()`
