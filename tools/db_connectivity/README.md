# Gather behavior when DB connectivity is lost

Investigated on 2026-10-05 against revision
`f237bf37426882cfc0ca113fee760a5a2ddcbd8f`, using the running Podman compose
PostgreSQL and the real `manage.py` CLI in standalone mode.

**Collector exceptions are caught, but network failure is not handled reliably
end-to-end.** A closed DB connection causes a fatal exception during finalization
or advisory-lock release. Silently discarded traffic can leave collection waiting
without a collector-error log. Failed collections are omitted from status
reporting, even when other data is successfully delivered.

## Actionable issue drafts

- [Report failed collection slices](issues/report-failed-slices.md)
- [Handle DB disconnects through finalization](issues/handle-disconnects-and-cleanup.md)
- [Bound DB network waits during gather](issues/bound-network-waits.md)
- [Prevent checkpoints skipping failed slices](issues/protect-failed-slice-checkpoints.md)

## Reproduce

With compose PostgreSQL already running, from the repository root:

```bash
uv run python tools/db_connectivity/reproduce.py --output /tmp/gather-db-dry-run
uv run python tools/db_connectivity/reproduce.py --output /tmp/gather-db-ship --ship
```

Choose new output directories. The tool refuses to overwrite an existing case
directory. Use `--cases` to select scenarios, `--since`/`--until` to select data,
and `--timeout` to change the process deadline. The defaults use June 13-15,
2025, with two daily slices; the compose fixture had 12 job-host-summary rows
in the first slice and a header-only CSV in the second slice. `streaming-close`
requires at least one data row and verifies that the fault was exercised.

Each case starts a private loopback PostgreSQL TCP proxy and a fresh CLI process.
It points the CLI at the proxy using `METRICS_UTILITY_DB_*`, with no production
collector monkeypatches. TLS/GSS encryption is disabled on this local probe so
the proxy can identify SQL message boundaries. The compose container's network,
configuration, and lifecycle are untouched. Closing the proxy restores the
probe's access path; ordinary connections to compose remain available throughout.

The tool clears inherited `METRICS_UTILITY_*` configuration. With the optional
collector variable absent, `get_optional_collectors()` defaults to
`main_jobevent`. The effective default data collectors are therefore:

- `config` (copied into every produced tarball);
- `job_host_summary` (daily CSV);
- `main_jobevent` (daily CSV).

`data_collection_status.csv` and `manifest.json` are generated during packaging.
Other registered collectors return no data when disabled.

For `collector-close-with-vcpu`, the optional list is explicitly replaced with
`total_workers_vcpu`, so `main_jobevent` is disabled. Metering is disabled and the
vCPU collector returns its 1-CPU stub without needing DB or Prometheus access.

### Faults

- `startup-close`: accepts and immediately closes the initial connection.
- `startup-drop`: accepts but never completes PostgreSQL startup. The probe sets
  `PGCONNECT_TIMEOUT=3`, producing a connection-timeout error.
- `startup-drop-default`: the same startup stall with `PGCONNECT_TIMEOUT` unset.
- `collector-close`: closes both proxy sockets at the first job-host-summary
  COPY request, after setup/config have succeeded.
- `collector-drop`: stops forwarding that COPY request but holds TCP open.
- `streaming-close`: forwards the COPY header and first data row, then closes.
- `second-slice-close`: closes at the second job-host-summary COPY request,
  after the first slice was packaged and, with `--ship`, delivered.
- `collector-sql-error` / `second-slice-sql-error`: substitutes
  `COPY (SELECT 1 / 0) TO STDOUT WITH CSV HEADER` for the selected COPY request.
  PostgreSQL really returns a statement error while the session remains usable.
  These are controls for ordinary collector failure, not network-policy emulation.
- `all-sql-error`: substitutes that failing SQL for every CSV COPY request.
- `collector-close-with-vcpu`: a DB disconnect with a successful non-DB collection.

A TCP close represents a detected disconnect. Holding sockets open without
forwarding models the application-visible stall from silently dropped traffic;
this does not reproduce any particular OpenShift CNI or policy implementation.
The compose mock's config collector succeeds using in-process Django settings;
this experiment does not exercise DB failures while fetching real AWX config.

## Observed results

Counts below are logical tarballs: a delivered tarball and its retained temporary
copy count as one. Both dry-run and directory-shipping modes were exercised for
all cases except `startup-drop-default`, which was exercised in dry-run mode.

| Case | CLI result | Tarballs | Artifact/status result |
| --- | --- | --- | --- |
| baseline | `0`, `Analytics collected` | 4 | Two CSV collectors x two days; all status rows `ok` |
| startup-close | `1`, connection error traceback | 0 | No staging initialization, CSV, status, or manifest |
| startup-drop | `1`, `connection timeout expired` | 0 | Same; timeout supplied by the probe |
| startup-drop-default | Still waiting at 12s; harness killed it | 0 | No collector progress/error or artifacts |
| collector-close | `1`, collector tracebacks then lock/finalization traceback | 0 | No packaged CSV, status, or manifest |
| collector-drop | Still waiting at 12s; harness killed it | 0 | Last progress: `Now gathering job_host_summary`; no collector-error log |
| streaming-close | `1`, collector and lock/finalization tracebacks | 0 | Partial staged CSV, never packaged |
| second-slice-close | `1`, collector and lock/finalization tracebacks | 1 | First day's job-host-summary tarball survives; status only `ok`; failed/later slices absent |
| collector-sql-error | `0`, error traceback then `Analytics collected` | 3 | Failed first job-host-summary slice completely omitted; all surviving status rows `ok` |
| second-slice-sql-error | `0`, error traceback then `Analytics collected` | 3 | Failed second job-host-summary slice completely omitted; all surviving status rows `ok` |
| all-sql-error | `1`, collector tracebacks then `No analytics collected` | 0 | No failure-only tarball/status/manifest |
| collector-close-with-vcpu | `1`, DB collector and lock/finalization tracebacks | 1 | vCPU tarball survives; status only vCPU `ok`; failed CSV collection absent |

All CLI output was on **stderr** (logger and the standalone AWX fallback notice).
The captured stdout files were empty. Default logging includes full exception
tracebacks without requiring `--verbose`. A typical disconnect sequence was:

```text
Progress info: Now gathering job_host_summary
Could not generate metric job_host_summary.csv: consuming input failed: server closed the connection unexpectedly
... psycopg.OperationalError traceback ...
Could not generate metric job_host_summary.csv: the connection is closed
... later main_jobevent failures ...
the connection is lost
... traceback ending in library/lock.py, cursor.execute(command) ...
```

In ship mode, the traceback also shows `_gather_finalize()` failing while obtaining
the analytics lock, followed by another exception during release of the outer
billing lock. `No analytics collected` is not reached in these network-close
cases, even when no tarball was created.

For killed processes, Python reports return code `-9` (SIGKILL; a shell typically
reports `137`). This is the harness's action, **not a natural CLI exit status**.
The 12-second deadline is measured from process launch, including about 2.4
seconds of imports. Neither the startup-default stall nor the established-session
stall had completed by that deadline. `PGCONNECT_TIMEOUT=3` does not bound queries
on an already-established connection. OS/libpq timeouts may eventually detect a
real network loss; there is no application-level collection deadline here.

### Status and manifest example

The only surviving tarball after `second-slice-close` contained:

```text
./job_host_summary.csv
./config.json
./data_collection_status.csv
./manifest.json
```

Its manifest was:

```json
{
  "job_host_summary.csv": "1.2",
  "config.json": "2.0",
  "data_collection_status.csv": "1.0"
}
```

Its status CSV contained exactly one row for `job_host_summary.csv`, status `ok`,
since `2025-06-13 00:00:00+00:00`, until `2025-06-14 00:00:00+00:00`. There was
no `failed` row for June 14-15 and no row for either attempted `main_jobevent`
slice. The manifest accurately lists present files, but does not describe the
requested run or its missing data. `config.json` is not represented by a status
row either.

All **12 delivered tarballs** across the ship scenarios passed the existing
offline validator. Files without schemas (`main_jobevent.csv`) were skipped as
usual. Thus a structurally valid archive and all-`ok` status CSV do not establish
collection completeness.

### Cleanup and checkpoints

- Detected disconnects in dry-run reached normal staging cleanup before failing
  on outer lock release. Already-created tarballs remained outside the staging
  directory, in the probe's `tmp/` directory.
- Ship mode failed in finalization before `_gather_cleanup()`: staging remained,
  including a **634-byte partial CSV** for `streaming-close`. For
  `second-slice-close` the delivered first-day tarball and its temporary copy both
  remained. The vCPU case likewise retained a delivered and temporary copy.
- A process killed while waiting also left staging behind. Startup failures
  occurred before staging was created.
- With an ordinary SQL error, later slices and other collectors ran successfully;
  normal cleanup completed. When every data collection failed, the command raised
  `NoAnalyticsCollected` and exited `1` without producing a failure-only archive.
- Checkpoint risk from source inspection: checkpoint updates iterate packaged
  collections only. Failed slices never reach `Collection.update_last_gathered_entries()`
  to set its failure barrier. A later successful slice can therefore advance a
  collector's timestamp beyond a failed earlier slice. Persistent real-AWX
  checkpoint behavior was not tested: compose's mock Django settings do not
  provide AWX's persistent settings backend.

## Why this happens

Relevant source locations in the investigated revision:

- [`Collection.gather()`](../../metrics_utility/base/collection.py) catches
  collector exceptions, logs a traceback, and sets `gathering_successful=False`.
- [`Collector._gather_csv_collections()`](../../metrics_utility/base/collector.py)
  skips failed/empty collections **before** adding them to any package.
- [`CollectionDataStatus`](../../metrics_utility/base/collection_data_status.py)
  iterates `package.collections`, so failed collections never produce its intended
  `status=failed` rows. No package is created solely to report failures.
- [`Package`](../../metrics_utility/base/package.py) lists only files actually
  added in the manifest. Sliced collections are packaged/shipped immediately.
- [`billing Collector.gather()`](../../metrics_utility/automation_controller_billing/collector.py)
  finalizes before cleanup, with no `try/finally` protecting that cleanup.
- [`lock()`](../../metrics_utility/library/lock.py) unconditionally tries to release
  an acquired lock with its original cursor. A dead connection raises from that
  `finally`, even if collection failure was caught. PostgreSQL session locks are
  already released when the backend connection closes.
- [`Command.handle()`](../../metrics_utility/management/commands/gather_automation_controller_billing_data.py)
  regards any returned tarball path as collection success; it does not inspect
  per-collector failures.

The intended nonfatal collector behavior works for individual SQL errors, but
observability is incomplete. To make it reliable requires run-level failed-slice
reporting independent of successful packages, bounded network waits, dead-session
lock handling, guaranteed staging cleanup, and checkpoint updates that cannot
skip failed slices.

## Captured investigation artifacts

The original runs retained full logs, tarballs, archive members, parsed manifests,
status CSV rows, proxy fault events, process status, and leftover-stage listings:

- `/tmp/opencode/db-connectivity-dry-run/` - initial dry-run scenarios;
- `/tmp/opencode/db-connectivity-ship/` - shipping scenarios;
- `/tmp/opencode/db-connectivity-extra/` - mid-stream/all-failed dry-run controls;
- `/tmp/opencode/db-connectivity-default-timeout/` - unconfigured startup timeout.

Each case has `stdout.log`, `stderr.log`, and `result.json`; each run has
`results.json`. The initial exploratory `config-close` case did not trigger a fault
because mock config uses in-process settings, and is excluded from the conclusions
and current tool's case list.

After the probes, compose Postgres still accepted connections, the fixture still
had 84 job-host-summary records, and there were no advisory locks owned by `awx`.
The Postgres, mock Segment, and mock Prometheus containers remained running, as
did the original `compose` tmux session.
