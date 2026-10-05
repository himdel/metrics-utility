# metrics-utility - bound DB network waits during gather

- Type: Bug
- Component: aap-metrics
- Workstream: Imperial Services

## Problem

When PostgreSQL traffic is silently discarded, collection can wait without
producing a collector-error log or a final outcome. Both initial connection
startup with the default configuration and an established-session COPY were
still waiting when the reproduction harness killed them after 12 seconds.

Setting `PGCONNECT_TIMEOUT=3` bounded connection startup, but did not bound the
COPY on an already-established session. A server-side statement timeout alone
cannot guarantee delivery of an error through a blocked network.

## Reproduce

With compose running, from the repository root, choose a new output directory:

```bash
uv run python tools/db_connectivity/reproduce.py \
  --output /tmp/gather-bound-network-waits \
  --cases startup-drop-default startup-drop collector-drop
```

`startup-drop` exits `1` with `connection timeout expired`. The other two cases
reach the harness deadline. For `collector-drop`, the last log is
`Progress info: Now gathering job_host_summary`; there is no failure message.
Return code `-9` records the harness SIGKILL, not a natural CLI exit.

## Action

Provide configurable, documented bounds for initial DB connectivity and loss of
connectivity during active collection, with defaults suitable for large streamed
datasets. Ensure the chosen mechanism actually detects blocked traffic on an
established session, rather than only bounding connection establishment.

Feed detected timeouts into the collector/run failure path so logging, failure
reporting, lock handling, and cleanup complete predictably. Cover both standalone
DB configuration and execution inside Controller's Django environment.

## Acceptance criteria

- [ ] Initial DB connectivity failure has a documented finite bound.
- [ ] Silent traffic loss during an established COPY has a documented finite bound.
- [ ] Timeout logs identify the phase, collector/slice when applicable, and configured limit.
- [ ] The CLI reaches a defined outcome without an external harness kill when the configured deadline is exceeded.
- [ ] Timeouts preserve nonfatal per-collector behavior where other useful collection can succeed, and invoke normal failure reporting/cleanup.
- [ ] Healthy long-running COPY streams remain supported under the documented timeout semantics.
- [ ] Integration tests distinguish startup stalls from established-session stalls and verify both paths.
- [ ] Configuration and behavior are verified for standalone and Controller-hosted execution.

## References

- [Investigation and captured evidence](../README.md)
- [Handle disconnects through finalization](handle-disconnects-and-cleanup.md)
- [Report failed collection slices](report-failed-slices.md)
- `mock_awx/settings/__init__.py`: standalone DB configuration
- `metrics_utility/library/collectors/util.py`: `_copy_table_files()`
