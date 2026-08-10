# Bugs and Pitfalls
### Leftover `print()` statement shipped in production code
- **Repo**: ansible/metrics-utility
- **Commits**: ba08a25 (#6)
- **What happened**: The billing feature PR (#5) included a `print(since, until)` debugging statement in the gather command. It was caught and removed in a follow-up PR the same day.
- **Insight**: Debug print statements in CLI tools are particularly visible since the output goes directly to users; review for stray prints before merging.

### SQL query used `<=` instead of `<` for the upper time bound
- **Repo**: ansible/metrics-utility
- **Commits**: 6e60790 (#9)
- **What happened**: The job_host_summary SQL query originally used `modified <= until` for the upper bound. PR #9 changed this to `modified < until` to correctly implement exclusive upper bounds, preventing records from being included in two adjacent daily slices.
- **Insight**: Time-range queries with daily slicing must use exclusive upper bounds (`<`) to avoid double-counting records at slice boundaries.

### Missing `__init__.py` files when adding new subpackages
- **Repo**: ansible/metrics-utility
- **Commits**: 858b2e5 (#10)
- **What happened**: PR #9 added several new subdirectories (`dataframe_engine/`, `extract/`, `package/`, `report/`) but forgot to include `__init__.py` files. PR #10 was an immediate follow-up fix adding the four missing init files. The `package/` directory was created by refactoring a single `package.py` file into a `package/` subpackage.
- **Insight**: When converting a module file (e.g. `package.py`) into a subpackage directory (`package/`), always remember the `__init__.py` -- this is easy to miss since the old single-file module didn't need one.

### Report generation crashes on empty billing data
- **Repo**: ansible/metrics-utility
- **Commits**: 958e924 (#11)
- **What happened**: The `build_report` command did not check for `None` or empty dataframes before passing them to the report engine, causing crashes when no billing data existed for the requested month. The fix added an early return with an informational log message.
- **Insight**: Always guard against empty result sets when building reports from collected data -- months with no automation activity are a valid scenario.

### Multipart dataframe merges lost data when columns existed in both halves
- **Repo**: ansible/metrics-utility
- **Commits**: 1974c57 (#13)
- **What happened**: When billing data was split across multiple CSV files (multipart collection), merging the dataframes via `pd.merge` created `_x` and `_y` suffixed columns for overlapping data columns. The code was not summing these back together, losing data from one side. The fix added `summarize_merged_dataframes()` which sums `col_x` + `col_y` and removes the suffixed columns.
- **Insight**: Pandas outer merges on overlapping numeric columns silently create `_x`/`_y` suffixed columns -- always post-process these to recombine the data.

### Missing `__init__.py` in `renewal_guidance/` subpackage (second occurrence)
- **Repo**: ansible/metrics-utility
- **Commits**: 99775c1 (#25)
- **What happened**: PR #24 added the `report/renewal_guidance/` directory with `dedup.py` but forgot `__init__.py`, causing `ModuleNotFoundError` when running `build_report`. This is the second time this exact bug occurred (first was PR #10 fixing PR #9's missing init files).
- **Insight**: This is a recurring pattern in the project -- new subpackages are created without `__init__.py`. The same bug class has now happened twice across different contributors.

### Uninitialized variable when ephemeral option not passed to renewal report
- **Repo**: ansible/metrics-utility
- **Commits**: c57f58b
- **What happened**: The renewal guidance report referenced `ephemeral_usage_dataframe` in the sheet-building code, but this variable was only set inside an `if self.extra_params.get("opt_ephemeral")` block. When `--ephemeral` was not passed, the variable was undefined, causing a crash. Fix: initialize `ephemeral_usage_dataframe = None` before the conditional.
- **Insight**: Variables assigned inside conditional blocks must be initialized beforehand when they are referenced unconditionally later.

### `ansible_board_serial` replaced by `ansible_product_serial` for more reliable dedup
- **Repo**: ansible/metrics-utility
- **Commits**: 1236de5
- **What happened**: The renewal guidance host deduplication originally used `ansible_board_serial` (motherboard serial) as one of the dedup keys. This was changed to `ansible_product_serial` (chassis serial) because product serial is more reliable and consistent across systems. The column name changed throughout the SQL queries, dedup logic, and report output.
- **Insight**: When using hardware identifiers for deduplication, chassis/product serial is more reliable than motherboard serial -- the latter can vary across identical machines.

### Dedup hostname selection was arbitrary, now picks most-recently-active non-deleted host
- **Repo**: ansible/metrics-utility
- **Commits**: 78bcb95
- **What happened**: When multiple host metric records were collapsed into one deduplicated row, the representative hostname was whichever row was iterated first. The fix sorts the duplicate group by `deleted` (False first) then `last_automation` (descending) and picks the first result, preferring active hosts with recent automation.
- **Insight**: When deduplicating records into a representative row, the choice of which record represents the group should be deterministic and prefer the most "alive" and recent record.

### Report crashes on data collected before `job_created` column was added
- **Repo**: ansible/metrics-utility
- **Commits**: 7cdf2fc (#39)
- **What happened**: Commit b721f52 added `job_created` as a new column to the dataframe engine and collected data. But when `build_report` processed tarballs collected before that change (e.g. 2024 data), the CSV files lacked the `job_created` column. The code unconditionally called `pd.to_datetime(billing_data['job_created']).dt.tz_localize(None)`, which raised a `KeyError`. The fix checks `if 'job_created' in billing_data` before processing and sets the column to `pd.NaT` if missing.
- **Insight**: When adding new columns to collected data, the report/dataframe engine must handle older tarballs that lack those columns -- always guard with a column-existence check and provide a sensible default (like `pd.NaT` for datetime columns).

### Pandas boolean negation: `not df["col"]` raises ValueError, use `~df["col"]`
- **Repo**: ansible/metrics-utility
- **Commits**: 88db198 (#58)
- **What happened**: The renewal guidance report's `df_managed_nodes_query` method used `not dataframe["deleted"]` to filter non-deleted hosts. This raises `ValueError: The truth value of a Series is ambiguous` because Python's `not` operator tries to evaluate the entire Series as a single boolean. The fix was to use the bitwise negation operator `~dataframe["deleted"]` instead, which correctly inverts each element of the boolean Series.
- **Insight**: Never use Python's `not` operator on pandas Series/DataFrames for boolean filtering -- always use the bitwise `~` operator for element-wise negation.

### Copy-paste doc comments in extractor factory described wrong class
- **Repo**: ansible/metrics-utility
- **Commits**: 3c1dc4d (#63)
- **What happened**: The `_get_extractor_directory()` and `_get_extractor_controller_db()` methods in the extractor factory both had the comment `# Return default S3 loader`, which was copy-pasted from `_get_extractor_s3()`. These were corrected to `# Return default directory loader` and `# Return default DB loader` respectively.
- **Insight**: Copy-pasted comments that describe the wrong behavior are worse than no comments at all -- they actively mislead during debugging.

### build_report error message didn't distinguish month vs date range
- **Repo**: ansible/metrics-utility
- **Commits**: 3c1dc4d (#63)
- **What happened**: When no billing data was found, `build_report` always logged "No billing data for month: {opt_month}" even when `--since`/`--until` date range parameters were used (in which case `opt_month` would be `None` or misleading). The fix checks whether `opt_since` was provided and formats the message accordingly: either "No billing data for input date range {since}--{until}" or "No billing data for month {month}".
- **Insight**: Error messages should reflect the actual input mode used -- a generic message that assumes one calling convention confuses users of another.

### Tests used hardcoded absolute paths from a specific developer's environment
- **Repo**: ansible/metrics-utility
- **Commits**: edfe31c (#74)
- **What happened**: All CCSP/CCSPv2 report tests (including the newly added complex test from PR #70) hardcoded paths like `/awx_devel/awx-dev/metrics-utility/metrics_utility/test/test_data` for `METRICS_UTILITY_SHIP_PATH` and expected output files. These paths only existed in one developer's AWX development environment. The fix changed them to relative paths (`./metrics_utility/test/test_data`). Additionally, the complex CCSPv2 test was named `complex_test_CCSPv2.py` which pytest doesn't discover by default (requires `test_` prefix); it was renamed to `test_complex_CCSPv2.py`.
- **Insight**: Hardcoded absolute paths from a development environment are a silent CI failure risk -- tests appear to be added but never actually run until someone tries to enable them in a different environment.

### Unreachable hosts were being counted as managed nodes in CCSP billing
- **Repo**: ansible/metrics-utility
- **Commits**: db4eeea (#79)
- **What happened**: When a host had all tasks in `unreachable`/`dark` state (no successful, failed, skipped, ignored, or rescued tasks), it was still being counted as a managed node in the CCSP billing report. The fix adds a `reachable_task_runs` column that sums all task counters except `dark`, then filters out rows where `reachable_task_runs == 0`. This changed all snapshot test reference files since some test data included unreachable hosts.
- **Insight**: For billing purposes, a host that was never actually reached by any task should not count as a "managed node" -- the `dark` counter in Ansible represents connection failures, not automation.

### advisory_lock import using find_spec was fragile, switched to try/except
- **Repo**: ansible/metrics-utility
- **Commits**: 0bacb2f (#94)
- **What happened**: The earlier approach (from #51) used `importlib.util.find_spec('ansible_base')` to decide whether to import `advisory_lock` from `awx.main.utils.pglock` (AAP 2.4) or `ansible_base.lib.utils.db` (AAP 2.5). This broke because early AAP 2.5 versions still had `advisory_lock` in `awx.main.utils.pglock` even though `ansible_base` was already importable (the move happened in awx PR #15676). The fix switched to `try: from awx.main.utils.pglock import advisory_lock / except ImportError: from ansible_base.lib.utils.db import advisory_lock`, which handles the transitional period where both packages exist but the function hasn't moved yet.
- **Insight**: When detecting which package provides a function, `try/except ImportError` on the actual import is more reliable than checking package availability with `find_spec` -- the package can exist without yet providing the function you need. **Supersedes** the earlier `find_spec` approach from commit 33d428e (#51).

### Indirect managed nodes sheet got wrong columns depending on other optional sheets
- **Repo**: ansible/metrics-utility
- **Commits**: 9618be0 (#99)
- **What happened**: The CCSPv2 report used a `func` variable (set earlier based on whether `managed_nodes_by_organizations` was in the optional sheets) to build the "Indirectly Managed nodes" sheet. When `managed_nodes_by_organizations` was also enabled, `func` pointed to `_build_data_section_usage_by_node_with_org_details` which produces different columns than the correct `_build_data_section_usage_by_node`. The fix hardcoded the call to `self._build_data_section_usage_by_node()` instead of using the `func` variable.
- **Insight**: Reusing a function-pointer variable (`func`) across multiple sheet-building blocks is fragile -- when sheets have different column requirements, each sheet should explicitly call its own builder rather than relying on a shared variable that may have been reassigned.

### CCSP billing quantity counted both direct and indirect hosts
- **Repo**: ansible/metrics-utility
- **Commits**: dab7661 (#117)
- **What happened**: The CCSP and CCSPv2 billing summary sheets passed the full `job_host_summary_dataframe` (containing both direct and indirect managed nodes) to `_build_data_section()`, which computed `quantity_consumed` as `dataframe['host_name'].nunique()`. This inflated the billing quantity by including indirect nodes. The fix filters to `DIRECT` nodes before passing to the summary builder, and splits the direct/indirect filtering to happen once at the top of `build_spreadsheet()` rather than repeated inside each sheet block. Also fixed a typo: `manage_node_type` was renamed to `managed_node_types_set` throughout the dataframe pipeline.
- **Insight**: Billing quantity must count only direct managed nodes -- indirect nodes (network devices managed through jump hosts) are tracked separately and should not inflate the host count used for pricing.

### Since/until bare numbers accepted without unit suffix, causing silent misinterpretation
- **Repo**: ansible/metrics-utility
- **Commits**: 45c345e (#114)
- **What happened**: The `--since` and `--until` parameters in the gather command accepted bare numbers (e.g., `--since=5`) without a `d` or `m` suffix. These would fall through to `dateutil.parser.parse()` which would interpret `"5"` as a date in unpredictable ways. The fix added a new `_handle_datelike()` method with explicit validation: bare numbers raise `UnparsableParameter` with a helpful message. The duplicated since/until parsing logic was also DRYed into this single method.
- **Insight**: When a parameter supports multiple formats (ISO date, relative days `Xd`, relative minutes `Xm`), validate that the input matches one of the expected formats rather than falling through to a permissive parser that silently accepts nonsense.

### build_dataframe returning None on empty data caused downstream crashes
- **Repo**: ansible/metrics-utility
- **Commits**: 9978da2 (#118)
- **What happened**: All three dataframe engines (`DataframeJobhostSummaryUsage`, `DataframeContentUsage`, `DataframeInventoryScope`) returned `None` when no data was found. Downstream code (report builders, filters, sheet generators) then crashed with `AttributeError` or `TypeError` when trying to operate on `None`. The fix changed all engines to return `pd.DataFrame(columns=self.data_columns() + self.unique_index_columns())` instead of `None`, providing an empty DataFrame with the correct schema. This also simplified downstream checks from `if df is not None and not df.empty` to just `if not df.empty`. A comprehensive test (`test_empty_data_for_CCSP_and_CCSPv2.py`) was added that runs every combination of report type, date range, and optional sheet with empty data.
- **Insight**: Returning `None` to signal "no data" from a function that normally returns a DataFrame forces every caller to check for `None` -- returning an empty DataFrame with the correct columns is safer and enables uniform downstream handling.

### `self.help` dict in Command.__init__ shadowed Django BaseCommand's `help` class attribute
- **Repo**: ansible/metrics-utility
- **Commits**: f2b5a83 (#128), 81b3744 (#141)
- **What happened**: PR #128 refactored help text into `self.help = {...}` dict for build_report and gather commands. This shadowed Django's `BaseCommand.help` class attribute (a string used by `--help` output), causing `manage.py build_report --help` to display the dict repr instead of the help string. PR #141 fixed it by renaming `self.help` to `self.help_texts` and restoring the class-level `help = 'Build Report'` string. The build_report help text was also corrected from the copy-pasted "Gather Automation Controller billing data" to the actual "Build Report".
- **Insight**: Django's `BaseCommand.help` is a reserved class attribute used for `--help` output -- never shadow it with instance attributes, especially with a dict instead of a string.

### `handle_env_validation` called in `add_arguments` ran too early, moved to `handle`
- **Repo**: ansible/metrics-utility
- **Commits**: 560c62d (#137), 81b3744 (#141)
- **What happened**: PR #137 placed `handle_env_validation('build')` and `handle_env_validation('gather')` inside `add_arguments()`, which Django calls during command discovery and `--help` processing. This meant env var validation ran even when just asking for help text, causing crashes if env vars weren't set. PR #141 moved the call to `handle()` (inside the try/except block), so validation only runs when the command is actually executed.
- **Insight**: Django's `add_arguments()` is called during command discovery and `--help` -- never put runtime validation or side effects there; put them in `handle()` instead.

### SQL `NOW()` in test data scripts produced non-deterministic timestamps
- **Repo**: ansible/metrics-utility
- **Commits**: e65b320 (#145)
- **What happened**: The `main_jobhostsummary.sql` test data script used `NOW()` for `created`, `modified`, and other timestamp columns. This caused non-deterministic test data -- each time the script ran, timestamps changed, making gather tests flaky (they filter by time range). The fix replaced all `NOW()` calls with fixed timestamps (`TIMESTAMP WITH TIME ZONE '2025-06-13 10:00:00+00'`).
- **Insight**: Test data SQL scripts must use fixed timestamps, not `NOW()` -- gather collectors filter by time range, so non-deterministic timestamps cause the same data to appear or disappear depending on when the test runs.

### `logger.propagate = True` caused duplicate log output after adding custom handler
- **Repo**: ansible/metrics-utility
- **Commits**: 42464e0 (#142)
- **What happened**: The `build_report` command's `init_logging` added a custom `StreamHandler` to the `awx.main.analytics` logger but left `propagate = True` (set in an earlier PR). This caused log messages to be emitted twice -- once by the custom handler and once by the root logger. The fix set `propagate = False`, matching the pre-#128 behavior.
- **Insight**: When adding a custom handler to a named logger, set `propagate = False` to prevent the parent/root logger from also emitting the same messages.

### `handle_env_validation` ran before `init_logging`, so validation errors were invisible
- **Repo**: ansible/metrics-utility
- **Commits**: a3dbd4f (#146)
- **What happened**: After #141 moved `handle_env_validation` into `handle()`, it was placed at the top of `handle()` before `init_logging()`. Since the logger wasn't initialized yet, any validation error messages would not be properly logged. PR #146 moved `handle_env_validation` *after* `init_logging()` inside `_handle()`, ensuring the logger is set up before validation runs.
- **Insight**: Validation that reports errors via logging must run after the logger is initialized -- ordering within `handle()` matters just as much as being in `handle()` at all. **Supersedes** the ordering from #141.

### `report_period` vs `report_period_range` confusion caused KeyError for renewal guidance
- **Repo**: ansible/metrics-utility
- **Commits**: cda736f (#149)
- **What happened**: The report system had two separate date range params: `report_period` (set to `opt_month`) passed as a constructor arg to Report classes, and `report_period_range` (set to `"since, until"`) inside `extra_params`. `ReportFactory` would overwrite `report_period` with `report_period_range` when present. But `ReportRenewalGuidance` used `extra_params['report_period_range']` directly, which didn't exist when `--month` was used, causing a KeyError. The fix unified both into a single `extra_params['report_period']`, set to `opt_month` for `--month` or `"since, until"` for `--since`.
- **Insight**: Having two overlapping config keys for the same concept (`report_period` as constructor arg and `report_period_range` in extra_params) creates confusion and KeyError bugs -- unify to a single key.

### `fetch_command` import errors were silently swallowed, now logged and re-raised
- **Repo**: ansible/metrics-utility
- **Commits**: aebc6d9 (#170)
- **What happened**: The `ManagementUtility.fetch_command()` method called `import_module(f'metrics_utility.management.commands.{subcommand}')` without any error handling. If the import failed (e.g., missing dependency, syntax error in command module), the exception would propagate with a confusing traceback that didn't mention the command name. A try/except was added that writes the command name and error to `sys.stdout` before re-raising, making it clear which command failed to load and why.
- **Insight**: When dynamically importing modules by name, wrapping the import in try/except with a descriptive message saves significant debugging time -- the raw ImportError alone doesn't identify which command triggered it.

### Indirect managed node collector crashes on AAP 2.4 where table doesn't exist
- **Repo**: ansible/metrics-utility
- **Commits**: 376352b (#172)
- **What happened**: The `main_indirectmanagednodeaudit` table only exists in AAP 2.5+. When `METRICS_UTILITY_OPTIONAL_COLLECTORS` included `main_indirectmanagednodeaudit` on AAP 2.4, the `COPY` query would crash with a `ProgrammingError` because the table didn't exist in the database schema. A try/except for `ProgrammingError` was added around the query, logging a warning and returning `None` to gracefully fall back. Unit tests were added covering success, ProgrammingError, and not-in-optional-collectors cases.
- **Insight**: Collectors that query tables introduced in newer product versions must catch `ProgrammingError` and degrade gracefully -- the same metrics-utility codebase runs across multiple AAP versions with different DB schemas.

### Gather `--until` date was exclusive at day boundary, causing missed data
- **Repo**: ansible/metrics-utility
- **Commits**: c6f9d0c (#175)
- **What happened**: When `--until` was set to a specific date (e.g., `2025-07-23`), it was parsed as midnight (start of day), meaning the entire last day's data was excluded. The fix adds `until.replace(hour=23, minute=59, second=59, microsecond=999999)` in `_calculate_collection_interval()` to extend the until boundary to end-of-day, ensuring all data from the specified date is included.
- **Insight**: When users specify `--until=2025-07-23`, they expect data from July 23 to be included -- setting the time to end-of-day matches user expectations for date-only parameters.

### METRICS_UTILITY_OPTIONAL_COLLECTORS set to whitespace caused validation failure
- **Repo**: ansible/metrics-utility
- **Commits**: c050e54 (#178)
- **What happened**: When `METRICS_UTILITY_OPTIONAL_COLLECTORS` was set to a whitespace string (e.g., `" "` or `""`), the validation split it by comma resulting in `['']`, and empty string was not in `VALID_COLLECTORS`. Since empty string is a valid edge case that should default to "all collectors", the fix added `''` to the `VALID_COLLECTORS` set.
- **Insight**: When an env var uses comma-separated values, always consider the empty/whitespace case -- `"".split(",")` returns `[""]` not `[]`, so empty string must be a valid value if the env var can be set to blank.

### Dockerfile referenced non-existent paths
- **Repo**: ansible/metrics-service
- **Commits**: dd5603f
- **What happened**: The initial Dockerfile had `COPY requirements/requirements.in /tmp/requirements.in` but the repo had `requirements.txt` at the root, not `requirements/requirements.in`. The Docker build would fail at this step.
- **Insight**: Template Dockerfiles must be tested with `docker build` before the initial commit. This was fixed two days later in e0bfd65.

### Environment variable casing inconsistency persisted across multiple files
- **Repo**: ansible/metrics-service
- **Commits**: be51903, 5e05775
- **What happened**: When renaming from `my_service` to `metrics_service`, the env vars were initially lowercased (`metrics_service_DB_HOST`) instead of uppercased (`METRICS_SERVICE_DB_HOST`). A follow-up commit fixed the most important ones but left several still lowercase (e.g., `metrics_service_REDIS_URL`, `metrics_service_ALLOWED_HOSTS` in docker-compose.yml and k8s manifests).
- **Insight**: A find-and-replace renaming operation across a codebase is error-prone when the original naming was ALL_CAPS and the new name is mixed_case. The inconsistency means some env vars work and others silently don't, since `metrics_service_FOO` and `METRICS_SERVICE_FOO` are different variables.

### Docker port variable used wrong casing
- **Repo**: ansible/metrics-service
- **Commits**: be51903
- **What happened**: `docker-compose.yml` used `${metrics_service_PORT:-8000}` instead of `${METRICS_SERVICE_PORT:-8000}` for the port mapping. Shell variables are case-sensitive, so this would only work if the lowercase version was set.
- **Insight**: Docker Compose variable interpolation (`${VAR}`) is case-sensitive. Using inconsistent casing between documentation and actual config means the documented env vars won't work.

### JSON collector returning None still generated an empty tarball
- **Repo**: ansible/metrics-utility
- **Commits**: f4242f4 (#189)
- **What happened**: When a JSON collector was disabled (returned `None`), `CollectionJSON.is_empty()` only checked `self.data is None`, but the collector code in `_gather_json_collections()` unconditionally called `_add_collection_to_package()` after gathering, without checking `is_empty()` or `gathering_successful`. This caused empty tarballs to be generated and shipped even when the collector produced no data. The `is_empty()` check was also extended to treat `'null'` as empty. The fix added an `if collection.is_empty() or not collection.gathering_successful: continue` guard before adding the collection to the package.
- **Insight**: The CSV collection path already had empty/failed checks before packaging, but the JSON collection path was missing them -- when adding a new collection type, ensure all guard conditions from existing types are replicated.

### Gather `--until` reverted from inclusive back to exclusive
- **Repo**: ansible/metrics-utility
- **Commits**: 5e61c22 (#192)
- **What happened**: PR #175 changed `--until` to be inclusive by setting `until.replace(hour=23, minute=59, second=59, microsecond=999999)` so that `--until=2025-07-23` would include all of July 23. However, this caused issues: it broke the `since == until` case (which should be valid and collect no data), and it was inconsistent with how `daily_slicing` and other time-range logic expected exclusive upper bounds. The fix reverted `--until` to be exclusive again, removed the end-of-day replacement, changed the since/until overlap check from `since >= until` to `since > until` (allowing `since == until`), and updated the help text to say "excluding."
- **Insight**: Exclusive upper bounds are the safer default for time-range parameters in collection systems -- inclusive bounds introduced edge cases with `since == until` and conflicted with existing slicing logic that assumed exclusive upper bounds. **Reverses** the inclusive change from #175.

### ExtractorS3 `process_tarballs()` passed `self` as explicit argument after method refactoring
- **Repo**: ansible/metrics-utility
- **Commits**: 2451c45 (#193)
- **What happened**: In #86, `process_tarballs` was refactored from a standalone function (taking `self` as a regular parameter) to a method on the Base class. `ExtractorDirectory` was updated to call `self.process_tarballs(path, temp_dir)`, but `ExtractorS3` was missed and still called `self.process_tarballs(self, s3_path, temp_dir)`, passing `self` twice (once implicit, once explicit), causing `TypeError: process_tarballs() takes 3 positional arguments but 4 were given`. The S3 code path was presumably untested at the time.
- **Insight**: When refactoring a function into a method, search for all call sites across every subclass -- callers that pass `self` explicitly will only fail at runtime for the specific subclass that was missed, and only if that code path is exercised.

### Renewal guidance dedup classes crashed on None dataframe instead of empty result
- **Repo**: ansible/metrics-utility
- **Commits**: 6467590 (#194)
- **What happened**: `DedupRenewal.run()` assumed `self.dataframe` was always a valid DataFrame and called `self._cleanup_null_values()` on it directly. When `ExtractorControllerDB` returned `None` or an empty DataFrame, the dedup would crash with `AttributeError`. `DedupRenewalHostname` and `DedupRenewalExperimental` already had `if self.dataframe.empty` guards, but these would still crash on `None`. The fix added `if self.dataframe is None or self.dataframe.empty` checks to all three dedup classes, returning `{'host_metric': pd.DataFrame()}` for the empty case.
- **Insight**: All code that receives a dataframe from an extractor or factory must handle both `None` and empty DataFrame -- even if the upstream was "fixed" to return empty DataFrames (#118), defensive checks in consumers prevent regression if upstream behavior changes.

### Sonar fix introduced copy-paste bug in "Result Data" label
- **Repo**: ansible/metrics-service
- **Commits**: cc2ac77, 5b12d74 (#7)
- **What happened**: When extracting `_show_dependencies` and `_show_dependents` helper methods from `show_task`, the "Result Data" label was accidentally changed to "Task Data" (duplicating the label from two lines above). Fixed one commit later.
- **Insight**: Method extraction refactors that are done to satisfy code complexity metrics (Sonar) without careful review can introduce bugs. The fix was trivial but the bug was a classic copy-paste error.

### Exception chaining missing (bare raise from)
- **Repo**: ansible/metrics-service
- **Commits**: 5b12d74 (#7)
- **What happened**: Multiple `except` blocks in `manage_tasks.py` raised new `CommandError` exceptions without chaining from the original exception. The ruff fix added `from e` to preserve the exception chain (e.g., `raise CommandError(f"Invalid JSON data: {e}") from e`).
- **Insight**: Python's exception chaining (`raise X from Y`) preserves the traceback of the original exception. Without it, the original traceback is lost, making debugging harder. Ruff's `B904` rule catches this automatically.

### ExtractorS3 passed S3 remote path to local tarball extraction, causing FileNotFoundError
- **Repo**: ansible/metrics-utility
- **Commits**: 9bf249d (#206)
- **What happened**: `ExtractorS3.iter_batches()` downloaded the tarball from S3 to a local temp file (`local_path`), but then passed the S3 remote path (`s3_path`) to `self.process_tarballs()` instead of the local path. The `_safe_extract` function then tried to open the S3 key as a local file path, raising `FileNotFoundError`. The bug originated in #75 when tarball extraction was refactored into shared code. The fix simply changed `yield self.process_tarballs(s3_path, temp_dir)` to `yield self.process_tarballs(local_path, temp_dir)`. Unused `batch_size()` static methods were also removed from both extractors.
- **Insight**: When a method takes a file path, ensure it receives a local filesystem path -- not a remote storage key that happens to look like a path. This is especially easy to miss in S3 code where both the remote key and local temp path are strings in the same scope.

### Gather validation incorrectly validated report_type, blocking valid gather commands
- **Repo**: ansible/metrics-utility
- **Commits**: a0b683f (#205)
- **What happened**: After #194 added validation that `RENEWAL_GUIDANCE` requires `controller_db` ship target, the validation ran for both `build` and `gather` commands. But `METRICS_UTILITY_REPORT_TYPE` is only meaningful for `build_report` -- gather collects raw data regardless of report type. Setting `METRICS_UTILITY_REPORT_TYPE=RENEWAL_GUIDANCE` with `METRICS_UTILITY_SHIP_TARGET=directory` would fail gather with "Only controller_db is allowed for RENEWAL_GUIDANCE", even though gather doesn't use report_type at all. The fix made `validate_report_type` return `None` immediately when `method == 'gather'`, skipping all report type validation for the gather command.
- **Insight**: When adding cross-cutting validation that references one command's settings (report_type is build-only), always check whether the validation is appropriate for other commands -- env vars used by one command may be set in the environment but irrelevant to other commands.

### PostgreSQL port mapping mismatch in CI
- **Repo**: ansible/metrics-service
- **Commits**: cb58dc0 (#11), e9ff8c9 (#27)
- **What happened**: The initial pytest workflow mapped PostgreSQL port `55432:55432` but the PostgreSQL container internally listens on 5432 by default, not 55432. This was eventually fixed in e9ff8c9 to use the standard `5432:5432` mapping. Meanwhile, the Django test settings used `METRICS_SERVICE_DB_PORT: 5432` (the internal port), which worked because GitHub Actions services expose ports on localhost.
- **Insight**: The non-standard port 55432 was used in docker-compose to avoid conflicts with local PostgreSQL, but in CI there's no local PostgreSQL to conflict with. Using standard ports in CI is simpler and less error-prone. The mismatch between the port mapping (`55432:55432`) and the Django env var (`5432`) worked accidentally because Docker network routing still connected to the container's 5432 internal port.

### CodeQL workflow was actually a copy of the pytest workflow
- **Repo**: ansible/metrics-service
- **Commits**: 7e90a26 (#15), cc53a70 (#16)
- **What happened**: A file named `codeql.yml` was committed but its contents were a complete copy of the pytest workflow. Reverted 5 minutes later.
- **Insight**: Copy-paste error in CI workflow creation. See `ci_cd.md` for the full entry.

### config.json billing_provider_params were saved to tarball before being updated
- **Repo**: ansible/metrics-utility
- **Commits**: a88a277 (#217)
- **What happened**: The billing collector's `gather()` method called `_gather_json_collections()` (which writes config.json into the tarball) and only afterward appended `billing_provider_params` to the config collection data. This meant the config.json inside tarballs shipped to CRC was missing the billing provider params (account ID, org ID, etc.). The fix moved the billing_provider_params injection into an overridden `_gather_config()` method that runs *during* JSON collection gathering (before the data is saved to tarball), by calling `super()._gather_config()` first and then extending the config data.
- **Insight**: When extending collected data with additional fields, the extension must happen during the collection phase (by overriding the appropriate gather method), not after -- otherwise the data is already serialized to the tarball without the extensions.

### GitHub Actions workflow permissions missing on initial creation
- **Repo**: ansible/metrics-service
- **Commits**: f848024 (#24), e5eba36 (#30)
- **What happened**: The sync-requirements workflow was created without explicit permissions in f848024. A follow-up commit e5eba36 (next day, different author) had to add `permissions: contents: write` and `pull-requests: write` because the workflow needed to commit changes and comment on PRs.
- **Insight**: GitHub Actions workflows that write to the repo or interact with PRs need explicit permissions. This is easy to miss because permissions errors only surface at runtime, not during PR review. Always test CI workflows that do write operations on a real push/PR before merging.

### Sonar-driven refactoring of task validation created unnecessary complexity
- **Repo**: ansible/metrics-service
- **Commits**: da91648 (#29)
- **What happened**: The `validate_task_groups()` function in `task_groups.py` was refactored from a simple inline loop into two extracted helper functions (`_validate_task_id` and `_validate_required_fields`) to satisfy Sonar's complexity/cognitive-complexity metrics. The refactored code is more lines and arguably harder to follow than the original inline validation.
- **Insight**: Code complexity metrics (Sonar's cognitive complexity) can incentivize extracting functions that don't need extraction. Simple validation loops don't benefit from being split into multiple functions when the original is clear and self-contained.

### Organization model extra_field changed from null=True to default=""
- **Repo**: ansible/metrics-service
- **Commits**: da91648 (#29)
- **What happened**: The `extra_field` on `Organization` was changed from `CharField(max_length=100, null=True, blank=True)` to `CharField(max_length=100, blank=True, default="")`. This required a new migration.
- **Insight**: This follows the Django convention that CharField should use `default=""` instead of `null=True`, because having two possible "empty" values (NULL and "") for a text field is confusing. Sonar likely flagged this as a code smell.

### Double JSON encoding of AUTOMATION_ANALYTICS_LAST_ENTRIES caused AttributeError
- **Repo**: ansible/metrics-utility
- **Commits**: 489b1ce (#258)
- **What happened**: The `get_last_entries_from_db()` function read the `AUTOMATION_ANALYTICS_LAST_ENTRIES` value from the `conf_setting` table and called `json.loads()` on it. But the AWX settings model JSON-encodes everything when saving, and the value was already `json.dumps()` output -- so the DB contained a JSON string wrapping a JSON object (e.g., `"{\"config\": \"2024-01-01T10:00:00Z\"}"` instead of `{"config": "2024-01-01T10:00:00Z"}`). A single `json.loads()` returned a string, not a dict, causing `AttributeError: 'str' object has no attribute 'get'` downstream. The fix added a second `json.loads()`: first decode unwraps the outer string, second decode parses the inner JSON object with `datetime_hook`.
- **Insight**: When reading values from a settings model that JSON-encodes on save, check whether the value is already JSON-encoded before saving -- if so, reading requires double decoding. This is easy to miss in development where test data may not have the double encoding.

### `UndefinedTable` exception from psycopg3 not caught alongside `ProgrammingError` from psycopg2
- **Repo**: ansible/metrics-utility
- **Commits**: 3395b94 (#261)
- **What happened**: The `main_indirectmanagednodeaudit` collector caught `ProgrammingError` when the table didn't exist (AAP 2.4). But psycopg3 (used in AAP 2.5+) raises `psycopg.errors.UndefinedTable` instead, which is a subclass of `ProgrammingError` in psycopg3 but does not exist in psycopg2. The fix imports `UndefinedTable` from `psycopg.errors` inside a `try/except ImportError` (defining a stub class for psycopg2 environments) and catches both `(ProgrammingError, UndefinedTable)`. This ensures graceful degradation regardless of psycopg version.
- **Insight**: When catching database exceptions across psycopg2/psycopg3, the exception hierarchy differs between versions -- psycopg3 has more specific exception types that may not be subclasses of the same base you're catching from psycopg2. **Extends** the AAP 2.4 compatibility fix from #172.

### NaN and infinity values in anonymized rollup JSON output
- **Repo**: ansible/metrics-utility
- **Commits**: 07cd17c (#250)
- **What happened**: Anonymized rollup computations (division by zero, null durations) could produce `float('nan')` or `float('inf')` values in the output. These are valid Python floats but not valid JSON, causing `json.dumps()` to produce non-standard output that downstream consumers could not parse. A `sanitize_json()` helper was added that recursively traverses the output and replaces NaN/infinity with `None` (which becomes JSON `null`).
- **Insight**: When producing JSON from pandas/numpy computations, always sanitize the output for NaN/infinity -- these arise naturally from division, duration calculations with null timestamps, and aggregation over empty groups, but are not valid JSON values.

### Docker Compose port change reverted immediately -- conflicts with CI and existing setups
- **Repo**: ansible/metrics-utility
- **Commits**: f68178e (#274), 36e0784 (#276)
- **What happened**: PR #274 changed the Docker Compose PostgreSQL exposed port from `5432:5432` to `5433:5432` and added a `METRICS_UTILITY_DB_PORT` env var (defaulting to `5433`) to avoid conflicting with a locally running PostgreSQL instance. This broke CI (which uses native PostgreSQL on port 5432) and changed the default for all existing users. The change was reverted 15 minutes later in PR #276.
- **Insight**: Changing default ports in shared development infrastructure requires coordination -- a default that works for one developer's local setup (avoiding port conflicts) breaks CI and other developers who expect the standard port. If port configurability is needed, keep the default at the standard port and let the developer who needs a different port set the env var.

### metrics-utility collector import paths changed with temporary aliases
- **Repo**: ansible/metrics-service
- **Commits**: 10581e9 (#42)
- **What happened**: When upgrading to `metrics-utility==0.7.20251112`, the import paths changed from `metrics_utility.library.collectors` to `metrics_utility.library.collectors.controller`. The collector function names also changed (e.g., `anonymous` became `job_host_summary`), requiring `as` aliases to maintain backward compatibility. A TODO comment was added: "The AS is just a filler till this is corrected with a later PR."
- **Insight**: Dependency upgrades that change public APIs create confusing alias layers. The aliases mean the code says `anonymous` but actually calls `job_host_summary` -- a debugging nightmare. The TODO suggests this was a quick fix to unblock the Django upgrade, with a proper refactor planned later.

### dispatcherd use_django_db broke local testing and was reverted next day
- **Repo**: ansible/metrics-service
- **Commits**: 6059d8c (#45), 3a8f7d5 (#48)
- **What happened**: `config/dispatcherd.yaml` changed to `use_django_db: true`, reverted next day because it didn't work for local development testing.
- **Insight**: See `docker_and_deployment.md` for the full three-iteration saga of dispatcherd DB config. The PR was titled just "Fix" with no description, making it hard to find later.

### Missing `__init__.py` in `anonymized_rollups/` subpackage (third occurrence)
- **Repo**: ansible/metrics-utility
- **Commits**: dbb7426 (#278)
- **What happened**: The `metrics_utility/anonymized_rollups/` directory was created across multiple PRs (#215, #239, #250) but never received an `__init__.py` file. PR #278 added it with explicit `__all__` exports for all rollup classes and functions. Additionally, a `metrics_utility/library/anonymize/` package was added with an `__init__.py` exposing `anonymized_rollups_processor` as the library entry point.
- **Insight**: This is the third time this exact bug occurred in the project (after #10 and #25) -- new subpackages are created without `__init__.py`. The pattern persists because the code works in development (where the directory is on `sys.path`) but fails when imported as a package.

### Segment chunking algorithm broke on real data: metadata overhead and dict-vs-list handling
- **Repo**: ansible/metrics-utility
- **Commits**: 4692757 (#281)
- **Superseded by**: 6109745 (#510) -- header overhead is now calculated dynamically instead of using a hardcoded conservative limit
- **What happened**: The `StorageSegment._split_into_chunks()` method had multiple issues with real anonymized rollup data: (1) The 32KB `REGULAR_MESSAGE_LIMIT` was the raw Segment limit, but the actual message includes metadata (anonymous_id, event_name, timestamp, chunk_info) that consumes space. The limit was reduced from 32KB to 24KB (and 512MB to 500MB) to leave room. (2) The chunking algorithm handled lists and dicts with separate code paths (`_split_dict_into_chunks`) that didn't match the actual data shape -- the anonymized rollup data is a dict whose values are either dicts (statistics, small) or lists (module_stats, potentially large). The rewrite iterates dict entries: dict values become one chunk each, list values are split item-by-item into size-limited chunks, and the entire payload is returned as a single chunk if it fits. (3) The old code had a `_split_dict_into_chunks` fallback that printed warnings to stderr instead of raising errors -- the rewrite raises on unexpected types. The test data was moved to a separate `testing_data_for_segment.py` file.
- **Insight**: Size-limited chunking for API payloads must account for the envelope metadata overhead (auth tokens, timestamps, chunk metadata) -- using the raw API limit as the chunk size causes the final serialized message to exceed the limit. **Extends** the chunking from #249 with practical fixes.

### Django signals on Task model caused widespread test failures
- **Repo**: ansible/metrics-service
- **Commits**: a044bd7 (#54)
- **What happened**: The `post_save` signal added in edb4626 (#25) automatically routes newly saved Task objects to dispatcherd. In tests, `Task.objects.create()` triggered this signal, causing failures because dispatcherd wasn't running. Five test files needed refactoring to use `_create_task_safely()` which sets `_skip_signals = True` before saving.
- **Insight**: Adding Django signals to models creates implicit side effects that affect every code path that creates/saves the model, including tests. The `_skip_signals` convention is a pragmatic workaround, but it means tests don't exercise the actual save behavior. A better pattern might be to check for a "testing" mode or use a factory function that explicitly opts into or out of signals.

### `collections.json` loaded with hardcoded relative path, broke when CWD changed
- **Repo**: ansible/metrics-utility
- **Commits**: 0118135 (#287)
- **What happened**: `EventModulesAnonymizedRollup.__init__` opened `collections.json` using a hardcoded relative path: `open('metrics_utility/anonymized_rollups/collections.json')`. This worked when running from the project root but broke when the current working directory was different (e.g., when called from the metrics service or from within a tempdir). The fix used `os.path.join(os.path.dirname(__file__), 'collections.json')` to load the file relative to the module's own location.
- **Insight**: Never use hardcoded relative paths to load package data files -- use `os.path.dirname(__file__)` or `importlib.resources` to resolve paths relative to the module, since the working directory is not guaranteed to be the project root.

### Recurring task dependent tasks never triggered due to status reset ordering
- **Repo**: ansible/metrics-service
- **Commits**: e43d59d (#59)
- **What happened**: In `execute_db_task()`, `handle_post_execution()` was called *after* the recurring task status was reset from "completed" to "pending". Since `handle_post_execution` checks `task.status == 'completed'` to trigger dependent tasks, they would never fire for recurring tasks. The fix moved `handle_post_execution()` before the status reset.
- **Insight**: State machine bugs where operations happen in the wrong order relative to a status change are subtle and hard to catch in code review. The fix is a simple line reorder, but discovering the bug requires understanding the full call chain and what each function checks.

### dispatcherd YAML had hardcoded database credentials instead of using Django settings
- **Repo**: ansible/metrics-service
- **Commits**: 0e15cbd (#66)
- **What happened**: `config/dispatcherd.yaml` had hardcoded `dbname`, `user`, `password`, `host`, `port` values. A new `_load_config_with_django_db()` function was added to `dispatcherd_config.py` that loads the YAML config file but overrides the database broker section with values from `django.conf.settings.DATABASES["default"]`. This is the third iteration of solving the dispatcherd DB config problem (after `use_django_db: true` which was reverted, and explicit YAML values which hardcoded credentials).
- **Insight**: The correct solution combines both approaches: load non-DB config from the YAML file (channels, queue routing, logging) but always inject DB connection from Django settings. This way, `METRICS_SERVICE_DATABASES__default__*` env vars work correctly through Dynaconf -> Django settings -> dispatcherd config, providing a single source of truth for database configuration.

### Immediate tasks submitted multiple times due to missing tracking before execution
- **Repo**: ansible/metrics-service
- **Commits**: 3100514 (#64)
- **What happened**: The unified scheduler's periodic DB sync found pending immediate tasks and executed them, but didn't add them to `_db_task_jobs` tracking dict until after execution. The next polling cycle would see the same pending task (not yet completed by dispatcherd) and submit it again, causing duplicates. The fix was a single line: `self._db_task_jobs[task.id] = f"db_immediate_{task.id}"` added before the execution call.
- **Insight**: When switching from an event-driven architecture (signals, triggered once) to a polling architecture (periodic check), you must track what you've already processed *before* processing it, not after. The polling loop doesn't know whether a previous iteration already handled a given item unless it checks a tracking set.

### URL prefix env var named inconsistently, fixed in follow-up PR
- **Repo**: ansible/metrics-service
- **Commits**: 2efdae3 (#69), a64071c (#70)
- **What happened**: PR #69 added a `METRICS_URL_PREFIX` env var to the dashboard view so the API base URL could include a gateway prefix. PR #70 (two days later, same author) renamed it to `METRICS_SERVICE_URL_PREFIX` for consistency with the project's env var naming convention (`METRICS_SERVICE_*`). The fix was a one-line change.
- **Insight**: The project's Dynaconf convention is that all env vars use the `METRICS_SERVICE_` prefix. A raw `os.getenv("METRICS_URL_PREFIX")` bypass doesn't follow this convention and would confuse operators. This was the kind of quick fix that should have been caught in code review -- naming consistency is a systematic concern, not a one-off decision.

### SettingSerializer referenced non-existent view after retrofit
- **Repo**: ansible/metrics-service
- **Commits**: d180ae8 (#74)
- **What happened**: After the platform-service-framework retrofit (#73), `SettingSerializer` was still a `HyperlinkedModelSerializer` with `extra_kwargs = {"url": {"view_name": "api:v1:settings-detail"}}`. But the dynamic_settings API uses a singleton pattern without individual detail endpoints, so the referenced view didn't exist. The fix changed it to a plain `ModelSerializer` and removed the `url` field entirely.
- **Insight**: When migrating from `HyperlinkedModelSerializer` to app-owned URL patterns, every serializer that references a `view_name` must be audited. The retrofit changed URL namespacing but didn't catch this serializer, causing runtime errors when the `url` field was rendered. Singleton/non-CRUD resources shouldn't use `HyperlinkedModelSerializer` since they lack detail endpoints.

### Missing utf-8 encoding on CSV read/write caused Unicode errors with non-ASCII data
- **Repo**: ansible/metrics-utility
- **Commits**: a3f00ba (#302)
- **What happened**: Several `pd.read_csv()` and `df.to_csv()` calls throughout the codebase did not specify `encoding='utf-8'`. While Python 3 defaults to the system locale encoding (usually UTF-8 on Linux), this could cause `UnicodeDecodeError` in environments with different locale settings, or when CSV data contained non-ASCII characters (e.g., organization names, hostnames with special characters). The fix added `encoding='utf-8'` to `pd.read_csv()` in `load_anonymized_rollup_data()`, `_read_csv()` in the extract base, and to `df.to_csv()` in test helpers. A variable name bug from a merge conflict in `load_anonymized_rollup_data` was also fixed.
- **Insight**: Always specify `encoding='utf-8'` explicitly on CSV operations in data pipelines that handle user-generated content (hostnames, org names, template names) -- relying on the system default encoding is fragile across deployment environments.

### Framework validation workflow too strict, removed immediately
- **Repo**: ansible/metrics-service
- **Commits**: 00e68ad (#84), 5be118c (#88)
- **What happened**: PR #84 added a `framework-validation.yml` GitHub Actions workflow that runs the platform-service-framework's CLI validator, which compares repo files against the framework template. PR #88 (the very next business day, different author) deleted the workflow because it compared files like `.gitignore`, `manage.py`, `pyproject.toml`, and `settings.local.py` against the template and failed on any differences. Since the service had legitimately customized these files, the validator was impractical.
- **Insight**: Framework compliance validators that do exact file-content comparison are too brittle for real services. Any service-specific customization causes false failures. Validation should check structural patterns (presence of required files, import paths) rather than file identity.

### vCPU timestamps lacked UTC timezone indicator, causing ambiguous time interpretation
- **Repo**: ansible/metrics-utility
- **Commits**: d90801d (#314)
- **What happened**: The `total_workers_vcpu` collector produced ISO 8601 timestamps with `+00:00` suffix (e.g., `2023-01-01T10:00:00+00:00`), but downstream consumers expected the `Z` suffix for UTC (e.g., `2023-01-01T10:00:00.000Z`). The fix changed all `datetime.fromtimestamp().isoformat()` calls to use `isoformat(timespec='milliseconds').replace('+00:00', 'Z')`. Additionally, the hour boundary calculation was changed from `current_hour_start - 1` (ending at `:59:59`) to `current_hour_start - 0.001` (ending at `:59:59.999`), and the PromQL query range was extended from `59m59s` to `59m59s999ms` to match the millisecond precision.
- **Insight**: When producing timestamps for external APIs that expect RFC 3339 / ISO 8601, use `Z` suffix instead of `+00:00` for UTC -- while semantically equivalent, many consumers only recognize the `Z` form. Also ensure timestamp precision is consistent across boundaries (milliseconds in timestamps should match milliseconds in query ranges).

### Dockerfile labels referenced wrong product name (metrics-utility instead of metrics-service)
- **Repo**: ansible/metrics-service
- **Commits**: 4b2bc5e (#94), 7c8c0c0 (#99)
- **What happened**: Labels had `com.redhat.component="metrics-utility"` from copy-paste. Fixed in #94, then the CPE regressed back to `metrics_utility` in #99 during Konflux label reformatting.
- **Insight**: See `docker_and_deployment.md` for the full label evolution. Labels don't affect build/runtime behavior, so errors aren't caught by CI. Each label field should be reviewed independently during updates.

### AppConfig.ready() writing to database causes RuntimeWarning on every Django invocation
- **Repo**: ansible/metrics-service
- **Commits**: e137d39 (#92)
- **What happened**: `DynamicSettingsConfig.ready()` was initializing default feature flag settings by writing to the database. Django emits a `RuntimeWarning` about this: "Accessing the database during app initialization is discouraged." The `ready()` method runs on every Django invocation -- not just server start, but also management commands, `shell`, `migrate`, tests, etc. This caused unnecessary DB writes and warnings during migrations and test runs.
- **Insight**: `AppConfig.ready()` is for signal registration and lightweight setup, not database writes. Use an explicit management command (like `init-default-settings`) for DB initialization. This ensures initialization happens exactly when intended (in entrypoints, after migrations) rather than on every Django process start.

### DRF router registration order caused URL conflict for /tasks/executions/
- **Repo**: ansible/metrics-service
- **Commits**: e137d39 (#92)
- **What happened**: In `apps/tasks/v1/urls.py`, `TaskViewSet` was registered before `TaskExecutionViewSet`. Since `TaskViewSet` used a catch-all pattern (`r""`), DRF's router matched `/tasks/executions/` as a TaskViewSet detail view with `pk='executions'` instead of routing to `TaskExecutionViewSet`. The fix was to register `TaskExecutionViewSet` before `TaskViewSet`. Two tests had been skipped (via `@pytest.mark.skip`) to work around this bug rather than fixing it.
- **Insight**: DRF routers match patterns in registration order, so more specific patterns must be registered first. This is the router equivalent of the "most specific route first" rule in URL configuration. The skipped tests were actually correct and identifying a real bug.

### generic_collect_metrics status not reset on update_or_create
- **Repo**: ansible/metrics-service
- **Commits**: 1580ff2 (#109)
- **What happened**: When re-collecting metrics for a previously processed time slot, `update_or_create` only set `raw_data` in `defaults` but not `status="collected"`. If the record already existed with `status="processed"`, the update kept the old status. The daily rollup then couldn't see the re-collected data because it filters by `status="collected"`.
- **Insight**: Django's `update_or_create` applies `defaults` on both create and update, but only for the fields listed in `defaults`. Omitting state machine fields like `status` means they retain their previous value on update, which can break downstream processes that filter by state.

### `pg_class.reltuples` unreliable for row count estimation, switched to `pg_stat_user_tables.n_live_tup`
- **Repo**: ansible/metrics-utility
- **Commits**: c225bdf (#329)
- **What happened**: The `table_metadata` collector initially used `pg_class.reltuples` for estimated row counts. This was unreliable: `reltuples` returns -1 for tables that have never been analyzed, returns stale values between ANALYZE runs, and for partitioned tables required summing across partitions via `pg_inherits`. The fix switched to `pg_stat_user_tables.n_live_tup` which is maintained by PostgreSQL's statistics collector continuously and provides more current estimates. The join was changed from `pg_class` directly to `pg_class LEFT JOIN pg_stat_user_tables ON st.relid = p.oid`.
- **Insight**: When querying PostgreSQL system catalogs for row count estimates, prefer `pg_stat_user_tables.n_live_tup` over `pg_class.reltuples` -- the former is updated by the background statistics collector while the latter is only updated by ANALYZE/VACUUM, making it stale or -1 on never-analyzed tables.

### NumPy types and numeric IDs caused JSON serialization failures in anonymized rollups
- **Repo**: ansible/metrics-utility
- **Commits**: d941ecd (#330)
- **What happened**: The anonymized rollup JSON output contained non-serializable types from pandas/NumPy computations: `numpy.int64`, `numpy.float64`, and `numpy.ndarray` values would cause `json.dumps()` to raise `TypeError`. Additionally, numeric ID columns (`id`, `job_id`, `host_id`, `job_remote_id`) were being serialized as floats (e.g., `42.0` instead of `"42"`) due to pandas nullable integer handling. The fixes: (1) `sanitize_json()` was extended to detect NumPy types via `isinstance(obj, (np.integer, np.floating))` and convert them to native Python types using `.item()`, with a `try/except ImportError` guard for environments without NumPy. NumPy arrays are recursively converted to lists. (2) A `_convert_id_columns_to_strings()` method was added to `BaseAnonymizedRollup` that converts ID columns to string format (`str(int(x))`) at the start of `prepare()`, ensuring consistent JSON serialization. This was applied to both `BaseAnonymizedRollup` and `JobsAnonymizedRollup` (which has additional ID columns like `unified_job_template_id`, `inventory_id`).
- **Insight**: When producing JSON from pandas DataFrames, always handle NumPy type conversion -- pandas operations silently produce NumPy scalars (`np.int64`, `np.float64`) that look like Python numbers but cause `json.dumps()` to fail. Converting IDs to strings early in the pipeline prevents the float representation issue that arises from pandas nullable integer columns. **Extends** the `sanitize_json()` NaN/infinity handling from #250.

### `unique_hosts_total` was double-counted when summed from per-grouping unique counts
- **Repo**: ansible/metrics-utility
- **Commits**: dd2639a (#331)
- **What happened**: The anonymized rollup's `unique_hosts_total` statistic was computed by summing `unique_hosts_total` from each job-type grouping. But a host that appeared in multiple job types (e.g., both `job` and `workflow_job`) would be counted once per grouping, inflating the total. The fix moved `unique_hosts_total` to be computed only at the top level from a `host_ids` list that collects all host IDs across all groupings, then takes `len(set(host_ids))` for the true unique count. The per-grouping `unique_hosts_total` field was removed from `_get_default_host_summary_fields()` and `_extract_host_summary_fields()`.
- **Insight**: Unique counts (nunique/len(set)) cannot be correctly computed by summing pre-computed unique counts from sub-groupings -- the same entity can appear in multiple groups. Always compute unique counts from the union of all raw IDs, not from summing per-group unique counts.

### SQL injection vulnerability in `_get_controller_settings` fixed by Snyk scan
- **Repo**: ansible/metrics-utility
- **Commits**: fd0e80f (#342)
- **What happened**: The `_get_controller_settings()` function in `library/collectors/controller/config.py` built an SQL `IN` clause by concatenating keys directly into the query string: `in_sql = "'" + "', '".join(keys) + "'"` followed by `cursor.execute(f'SELECT key, value FROM conf_setting WHERE key IN ({in_sql})')`. While the keys were internal strings (not user input), this was flagged by Snyk as an SQL injection risk. The fix replaced string concatenation with parameterized queries: `placeholders = ', '.join(['%s'] * len(keys))` and passing `keys` as the second argument to `cursor.execute()`. The `FIXME: psycopg.sql` comment was also resolved.
- **Insight**: Even when SQL parameters are internal strings (not user-controlled), use parameterized queries -- static analysis tools will flag string interpolation as injection risks, and internal-only assumptions can break as code evolves.

### Catastrophic backtracking (reDOS) vulnerability in collection name regex
- **Repo**: ansible/metrics-utility
- **Commits**: fd0e80f (#342)
- **What happened**: The `COLLECTION_REGEXP` in `library/dataframes/main_jobevent.py` was `r'^(\w+)\.(\w+)\.((\w+)(\.|$))+'` which contains nested quantifiers (`((\w+)(\.|$))+`) that cause catastrophic backtracking on certain inputs (e.g., very long strings without a match). Snyk flagged this as a reDOS vulnerability. The fix simplified the regex to `r'^(\w+)\.(\w+)\.(\w+)(?:\.\w+)*$'` which uses non-capturing groups and non-nested quantifiers. In the CLI-side `events_modules_anonymized_rollup.py`, the duplicate inline regex was replaced with a module-level `_COLLECTION_PATTERN` constant to ensure consistency.
- **Insight**: Regex patterns with nested quantifiers (`(a+)+`, `(a|b+)+`) are vulnerable to catastrophic backtracking -- always use non-capturing groups `(?:...)` and avoid nesting quantifiers. When the same regex is used in multiple places, extract it as a constant.

### `_calculate_sum_from_list` returned None for empty lists, causing downstream null propagation
- **Repo**: ansible/metrics-utility
- **Commits**: e35a93b (#343)
- **What happened**: The `_calculate_sum_from_list()` helper function returned `None` when given an empty list, which propagated null values into statistics fields like `rollup_period_organizations_total` and `rollup_period_forks_total`. Similarly, `jobs.get('organizations_total')` and `jobs.get('forks_total')` could be `None`. The fixes: (1) changed `_calculate_sum_from_list` to return `0` instead of `None` for empty lists, and (2) added `or 0` fallbacks at the call sites for fields read from the jobs dict.
- **Insight**: Aggregation helper functions should return `0` (not `None`) for empty inputs when the result is a count or sum -- `None` propagates through arithmetic and comparisons in unexpected ways, while `0` is the correct identity element for addition.

### DailyMetricsRollup missing base() call after merge
- **Repo**: ansible/metrics-service
- **Commits**: 35c3db5 (#138)
- **What happened**: The daily metrics rollup was merging hourly rollup JSON via `rollup_processor.merge()` but never calling `rollup_processor.base()` on the merged result. The `base()` method performs post-merge cleanup and extra computation that some collectors require. The function was refactored: `_merge_rollup_json` and `_aggregate_collector_rollups` were consolidated into a single `_merge_collects` function that calls `merge()` in a loop, then `base()` on the result, extracting the `"json"` key from the base output. Tests were updated to assert `base()` is called and the `"json"` key is extracted.
- **Insight**: The rollup API contract is `merge(json, json) -> json` followed by `base(merged) -> {"json": result}`. Missing the `base()` call meant collectors that need post-processing (e.g., computing derived fields from merged data) would produce incomplete rollups. This bug could go unnoticed because the merged data still looks valid -- it's just missing the final transformations that `base()` provides.

### Dispatcherd max workers reduced to 1 was a band-aid; real fix was atomic claims and advisory locks
- **Repo**: ansible/metrics-service
- **Commits**: 9a0feaa (#148), ccf9494 (#167)
- **What happened**: Workers reduced from 4 to 1 as band-aid for race conditions (#148), then restored to 4 with proper atomic claims, advisory locks, and retry delays (#167).
- **Insight**: See `task_system.md` "Workers restored to 4 with atomic task claiming and advisory locks" for the full arc. Reducing concurrency is a valid emergency measure but should always be treated as temporary.

### ID column conversion used `apply(lambda)` per row, replaced with vectorized `pd.to_numeric`
- **Repo**: ansible/metrics-utility
- **Commits**: b7037cf (#350)
- **What happened**: The `JobsAnonymizedRollup._convert_id_columns_to_strings()` method used `dataframe[col].apply(lambda x: str(int(x)) if pd.notna(x) and isinstance(x, (int, float)) and x == int(x) else x)` to convert ID columns to strings. This was slow for large DataFrames and raised `SettingWithCopyWarning` in some cases. The fix replaced it with vectorized pandas operations: `pd.to_numeric(errors='coerce')` to coerce values, a boolean mask for non-null rows, then `astype(int).astype(str)` on the masked subset. Similarly, filtering unfinished jobs changed from `dataframe[dataframe['finished'].notna()]` (which may return a view) to `dataframe.dropna(subset=['finished'])` (which always returns a new DataFrame), avoiding `SettingWithCopyWarning` on subsequent mutations.
- **Insight**: When converting DataFrame columns, prefer vectorized pandas operations (`pd.to_numeric`, `astype`, `dropna`) over `apply(lambda)` -- vectorized operations are 10-100x faster and avoid `SettingWithCopyWarning` issues with DataFrame views vs copies.

### Titlecased task names in logs made them harder to search
- **Repo**: ansible/metrics-service
- **Commits**: 26614c4 (#113)
- **What happened**: The `task_execution_wrapper` in `apps/tasks/utils.py` was calling `.title()` on task names in error messages (e.g., `f"{task_name.title()} task failed: ..."`). This was changed to use the raw task name (e.g., `f"{task_name} task failed: ..."`).
- **Insight**: Titlecasing identifiers in log messages breaks grep-based log searching. If a task is named `cleanup_old_tasks`, searching for that string in logs won't find the titlecased `Cleanup_Old_Tasks` variant. Log messages should use the canonical identifier exactly as it appears in code and configuration.

### Pandas 3.0: float('nan') replaces None in string-dtype columns, breaking identity checks and truthiness
- **Repo**: ansible/metrics-utility
- **Commits**: 3fc4c25 (#431)
- **What happened**: Upgrading pandas from 2.x to 3.0 introduced a breaking behavior change: missing values in string-dtype columns are stored as `float('nan')` instead of `None`. This broke four distinct code patterns: (1) `if x is None: return None` in `extract_collection_name()` and `extract_role_name()` (in `dataframe_content_usage.py` and `main_jobevent.py`) -- `float('nan')` is not `None`, so the guard was bypassed and NaN was passed to regex matching. Fix: `if not isinstance(x, str): return None`. (2) `v is not None` filter in `renewal_guidance.py`'s `stringify()` -- `float('nan')` passed the filter and was joined into output strings. Fix: `isinstance(v, str)`. (3) `if serial:` truthiness check in `DedupCCSP.df_to_mapping()` -- `bool(float('nan'))` is `True`, so all no-serial hosts were grouped into a single `serial_to_hosts[nan]` bucket, merging unrelated hosts. Fix evolved through several iterations: first `serial is not None and not pd.isna(serial)`, then simplified to `isinstance(serial, str) and serial`. (4) The outer `if serials:` check on the row's serials list was replaced with `isinstance(serials, Iterable)` because a cell containing `float('nan')` (a scalar) would pass the truthiness check but fail iteration. (5) The `'H'` hour frequency alias was removed in pandas 3.0; replaced with lowercase `'h'`. (6) Excel duration cells are now read as `datetime.timedelta` instead of `datetime.time` / `datetime.datetime(1900, 1, 1, ...)`.
- **Insight**: When upgrading pandas major versions, audit every `is None` check, `is not None` filter, and bare truthiness test (`if x:`) on DataFrame values -- pandas 3.0's switch from `None` to `float('nan')` for missing string values breaks all three patterns. The safest guard is `isinstance(x, str)` which handles None, NaN, and other non-string types in one expression.

### Pandas 2.2+/3.x: assigning string values to int64 column triggers StringArray coercion error
- **Repo**: ansible/metrics-utility
- **Commits**: 6e3d653 (#351)
- **What happened**: The `JobsAnonymizedRollup._convert_id_columns_to_strings()` method assigned `numeric[mask].astype(int).astype(str)` into `dataframe.loc[mask, col]` where the column was originally int64. In pandas 2.2+/3.x, this produced a StringArray which pandas then tried to cast back to int64, causing a coercion error. The fix: (1) cast the column to `object` dtype first with `dataframe[col] = dataframe[col].astype(object)`, and (2) use `numeric[mask].to_numpy(dtype=float).astype(int).astype(str)` to produce a plain numpy array instead of a StringArray. Additionally, the `_get_collection_cache_key` NaN check was simplified from `isinstance(ee_id, float) and pd.isna(ee_id)` to just `pd.isna(ee_id)`, since `pd.isna()` handles all nullable types.
- **Insight**: When assigning string values back into a DataFrame column that was originally numeric, first cast the column to `object` dtype to prevent pandas from trying to coerce the new StringArray values back to the original numeric dtype. **Extends** the vectorized ID conversion from #350.

### `date_where()` double-quoting broke qualified column names in PostgreSQL
- **Repo**: ansible/metrics-utility
- **Commits**: 04e583a (#353)
- **What happened**: The `date_where()` utility wrapped field names in double quotes (`"table.column"`), but in PostgreSQL `"table.column"` is treated as a single identifier (a column literally named `table.column`), not as a qualified reference. Six collectors manually interpolated since/until timestamps instead of using `date_where()` because of this bug. The fix removed the quoting (all callers pass hardcoded internal strings, so SQL injection is not a concern here) and added runtime validation that since/until are timezone-aware datetimes, catching naive datetimes or wrong types early rather than generating incorrect SQL.
- **Insight**: In PostgreSQL, `"table.column"` is a single quoted identifier, not a table-qualified column reference -- never wrap qualified column names in double quotes. When a utility function has a known bug, callers work around it by duplicating the logic inline, creating a hidden maintenance cost.

### Retry of hourly collection collected wrong hour because it used timezone.now()
- **Repo**: ansible/metrics-service
- **Commits**: da19df3 (#160)
- **What happened**: If a collector task failed and was retried hours later, `timezone.now()` shifted the "previous hour" calculation, silently collecting the wrong time window.
- **Insight**: Time-sensitive tasks must capture their target time window at dispatch time, not execution time. See `metrics_collection.md` "Collection timestamps pinned at dispatch time" for the fix pattern.

### Task execution records stuck in "pending" because execution_id not propagated
- **Repo**: ansible/metrics-service
- **Commits**: d81dfb3 (#162)
- **What happened**: `submit_task_to_dispatcher` created a `TaskExecution` record but only passed `task_id` (not `execution_id`) in the dispatcherd kwargs. The worker received `execution_id=None` and never updated the execution record. Fix: capture the execution object and pass `execution_id=execution.id` in kwargs.
- **Insight**: When creating a tracking record in one process and updating it in another, the record's ID must be explicitly passed across the boundary. This is easy to miss when the "create" and "update" happen in different functions with different authors.

### Cron schedule collision: cleanup and rollup both ran at 2:00 AM
- **Repo**: ansible/metrics-service
- **Commits**: d24e7dc (#163)
- **What happened**: `daily_task_cleanup` (deletes old TaskExecution records) and `daily_metrics_rollup` (writes to TaskExecution via FK) both ran at `0 2 * * *`. When simultaneous, cleanup could delete records that rollup was actively referencing, causing integrity errors. Cleanup moved to 5:00 AM. A test was added to verify all cron expressions are unique across all task groups.
- **Insight**: When multiple cron tasks touch overlapping database records, schedule collisions can cause data integrity failures. Adding a test that asserts cron expression uniqueness across all task groups prevents future collisions.

### ANONYMIZED_DATA_COLLECTION flag had overly broad scope
- **Repo**: ansible/metrics-service
- **Commits**: d3fb802 (#168)
- **What happened**: The flag was applied to the entire collection pipeline (12 tasks) instead of just the 2 anonymization/send tasks. Operators who opted out had permanent data gaps.
- **Insight**: Feature flag scoping must match the flag's name. See `task_system.md` for the full feature flag evolution arc (single flag -> overly broad -> three independent flags).

### Segment send failures were silent -- no error status, no health signal
- **Repo**: ansible/metrics-service
- **Commits**: 4e2a18e (#175)
- **What happened**: `send_to_segment` returned bare strings, failed payloads were always marked "retry" (never "failed"), and the health endpoint didn't check payload status.
- **Insight**: Silent failures in data pipelines are worse than crashes. See `metrics_collection.md` "Segment send failures made observable" for the fix. Rule: every external integration needs structured error returns, finite retry with escalation, and health check integration.

### post_migrate signal connected to class instead of instance -- handler never called
- **Repo**: ansible/metrics-service
- **Commits**: 8007509 (#189)
- **What happened**: `TasksConfig.ready()` was connecting `load_task_feature_flags` to the `post_migrate` signal using `sender=FeatureFlagsConfig` (the class). But Django's `post_migrate` dispatches with `sender=<AppConfig instance>`, and signal dispatch matches by `id()`. Since `id(class) != id(instance)`, the handler was never called, meaning task-specific AAPFlags were never seeded after migrations. The fix: use `django_apps.get_app_config("dab_feature_flags")` to get the live instance.
- **Insight**: Django signals match senders by identity (`id()`), not by type or equality. When using `sender=` with `post_migrate`, you must pass the live AppConfig instance (from `django.apps.apps.get_app_config()`), not the AppConfig class itself. This is a subtle Django signal pitfall that produces no error -- the handler simply never fires.

### Stale task.save() after submit_task overwrote atomic attempts increment
- **Repo**: ansible/metrics-service
- **Commits**: 4892777 (#187)
- **What happened**: `submit_task_to_dispatcher()` called `task.save()` after `submit_task()`, overwriting the worker's atomic `F("attempts") + 1` increment with stale in-memory `attempts=0`. Tasks appeared stuck at 0/3 attempts despite failing.
- **Insight**: When using Django's `F()` expressions for atomic field updates, any subsequent bare `save()` on the same model instance will overwrite the atomic update with the stale in-memory value. See `task_system.md` for the full fix (narrowing all saves to `update_fields=[...]`).

### Dashboard HTML template vulnerable to XSS via template literals
- **Repo**: ansible/metrics-service
- **Commits**: 4892777 (#187)
- **What happened**: The dashboard's inline JavaScript used ES6 template literals (backtick strings) to render task data (names, function names, error messages, cron expressions) directly into HTML without escaping. Any user-controlled data stored in task fields could inject arbitrary HTML/JavaScript. The fix introduced an `html` tagged template literal function that auto-escapes all interpolated values via `escapeHtml()` (replacing `&`, `<`, `>`, `"`, `'`), with a `RawHtml` wrapper class for values that are intentionally HTML (like nested `html` calls). All ~30 template literal usages in `dashboard.html` were converted from plain backtick strings to `html` tagged templates.
- **Insight**: The tagged template literal pattern (`html\`...\``) is an elegant solution for HTML escaping in client-side JavaScript -- it provides automatic escaping by default with explicit opt-in for raw HTML via a wrapper class. This is the same pattern used by libraries like lit-html. The dashboard's single-file architecture (all JS inline in the HTML template) made this a localized fix rather than requiring a framework-level change.

### Dashboard cleanup task schedule collision at 5:00 AM
- **Repo**: ansible/metrics-service
- **Commits**: 4892777 (#187)
- **What happened**: `cleanup_dashboard_reports_old_data` was scheduled at `0 5 * * *`, colliding with `daily_task_cleanup` at the same time. This is the same class of bug as the earlier collision between cleanup and rollup at 2:00 AM (#163). The fix moved dashboard cleanup to 5:30 AM. The existing test that verifies no two tasks share the same cron expression caught this.
- **Insight**: The cron uniqueness test added in #163 proved its value here. Without it, another schedule collision would have been introduced. Any new task added to task_groups.py should be checked against the existing schedule.

### Shared Django DB connection manually closed in finally blocks -- broke concurrent tasks
- **Repo**: ansible/metrics-service
- **Commits**: 258547a (#194)
- **What happened**: `_collect_data()` in dashboard_reports and `FilterOptionsViewSet.list()`/`.retrieve()` had `finally` blocks that called `db_connection.close()` on the raw psycopg connection returned by `get_db_connection("awx")`. This connection is Django's singleton object (`connections["awx"].connection`), shared across all tasks in the same worker process. When one task closed it, any concurrent task using the same connection got `psycopg.OperationalError: the connection is closed`. Django's wrapper didn't know the raw socket was dead, so `ensure_connection()` was skipped on the next call. The fix removed all manual `close()` calls and added `close_old_connections()` at safe boundaries (in `run_with_lock()` before acquiring advisory locks, and in `HealthView.get()` before `ensure_connection()`).
- **Insight**: Never manually close a raw connection obtained from Django's `connections[]` API -- it is a singleton shared across the process. Django manages connection lifecycle; manual closing creates race conditions between concurrent tasks. Call `close_old_connections()` only at task entry points (before any locks are held), not inside utility functions like `get_db_connection()`, because it closes ALL connections including those holding advisory locks.

### close_old_connections() placed in get_db_connection() broke advisory locks
- **Repo**: ansible/metrics-service
- **Commits**: 258547a (#194)
- **What happened**: An intermediate fix tried adding `close_old_connections()` inside `get_db_connection()` to handle stale connections. But `close_old_connections()` closes ALL Django connections, including the default connection that `run_with_lock()` uses to hold PostgreSQL advisory locks. This caused lock release failures. The final fix moved `close_old_connections()` to `run_with_lock()` (before lock acquisition, when no locks are held) and explicitly documented in `get_db_connection()` that it must NOT call `close_old_connections()`.
- **Insight**: `close_old_connections()` is a global operation that affects ALL database connections, not just one. It must only be called at safe boundaries where no connections are actively in use (e.g., at the very start of a task, before acquiring any locks). The iterative fix process (5 squashed commits) shows how tricky Django connection lifecycle management is in concurrent worker environments.

### Scheduler spammed skip logs every 30s for disabled feature flag tasks
- **Repo**: ansible/metrics-service
- **Commits**: babf061 (#199)
- **What happened**: When a feature flag like `DASHBOARD_COLLECTION` was disabled, the 30-second `_periodic_database_sync` loop would: (1) find the task via `Task.immediate_tasks()` (still `status="pending"` in DB), (2) call `_execute_database_task` which checked the flag and logged an INFO "Skipping task..." message, (3) call `_remove_database_task` to remove from in-memory tracking, but leave the DB row as `status="pending"`. Next cycle, the task was rediscovered and the loop repeated indefinitely. The fix gates task pickup behind a feature flag check *before* adding to the scheduler, so disabled tasks are silently bypassed. The skip log in `_execute_database_task` was downgraded from INFO to DEBUG as a safety net.
- **Insight**: In polling-based architectures, if you remove an item from the in-memory tracking set without changing its DB state, the next poll will rediscover it. The correct approach for feature-flag-disabled tasks is to not pick them up at all, rather than picking them up and then skipping them. This also means the task automatically starts when the flag is re-enabled -- no manual `init-system-tasks` needed.

### DispatcherdReconnectFilter added then reverted (direct commit without PR)
- **Repo**: ansible/metrics-service
- **Commits**: 8bd2a5c, 48397c8 (#208)
- **What happened**: A `DispatcherdReconnectFilter` logging filter was added directly to the `devel` branch (without a PR) to suppress transient asyncio ERROR logs from dispatcherd's pg_notify reconnection attempts. The filter checked `record.name == "asyncio"` and matched on `"CallbackHolder.done_callback"` in the message. It was added to the console handler in `metrics_service/settings.py`. The next day, it was reverted via PR #208 because it was committed "by Claude without going through a PR." The revert PR explicitly notes that if the fix is still needed, it should be re-proposed via a proper PR with review.
- **Insight**: This is a process pitfall, not a technical one. AI-assisted coding tools (Claude, Cursor) can commit directly to branches without human review. The fix itself was technically sound (targeted filter, only suppressed asyncio errors containing a dispatcherd-specific callback name), but bypassing the PR process means no peer review of the approach. Notably, commit 932467a (#206, OCP test results) also touched the same `DispatcherdReconnectFilter` code in the brief window it existed, simplifying the if/return to a single `return not (...)` expression.

### Segment event loss: sync_mode=True is the only reliable delivery method
- **Repo**: ansible/metrics-utility
- **Commits**: 4474a6c (#383)
- **What happened**: Segment's Python SDK batches `track()` calls into background HTTP POSTs, and silently drops events from batches exceeding 500KB (returning HTTP 200 with no error callback). Three approaches were tried: (1) `time.sleep` after flush -- race condition, process exits before background thread finishes; (2) batch size tracking with mid-loop `flush()` at 450KB -- still dropped events because the SDK adds 2-3KB of per-event metadata (context, timestamps, messageId, integrations) that the data-size estimate couldn't account for; (3) `analytics.sync_mode = True` -- sends each `track()` as a separate blocking HTTP request (~25KB each), eliminating both the batch-size and background-thread problems. End-to-end testing confirmed 15/15 chunks delivered reliably. Gzip compression was also tried but Segment silently rejects gzip-encoded bodies (HTTP 200, 0 events received).
- **Insight**: When a third-party analytics SDK silently drops events from oversized batches and provides no reliable way to estimate the true per-event overhead, sync_mode (one HTTP request per event) is the only reliable delivery method, even at the cost of higher latency.

### Subscription cost calculation was dividing monthly cost by 86400 instead of by actual elapsed seconds
- **Repo**: ansible/metrics-service
- **Commits**: 417d3f4 (#214)
- **What happened**: `SubscriptionCost.cost_per_second()` computed the per-second cost as `daily_subscription_cost / 86400` (seconds in a day), meaning the cost was distributed uniformly across all seconds regardless of actual job activity. This gave misleading per-job costs: a day with 1 hour of jobs and a day with 24 hours of jobs produced the same per-second rate. The fix rewrote the method to distribute the monthly cost proportionally: `period_cost / sum(elapsed_seconds_in_period)`, where elapsed seconds are summed from all successful/failed jobs in the date range. Multi-month ranges use `_month_range_iter` to prorate the monthly cost by overlap days per month. When no jobs exist in the period, the method returns a near-zero sentinel (`Decimal("0.0000000001")`) to avoid `ZeroDivisionError` at call sites.
- **Insight**: Subscription cost per second should be weighted by actual usage (total job elapsed time), not distributed uniformly across wall-clock time. The old formula overcharged idle periods and undercharged busy ones. The near-zero sentinel is pragmatic: the rate is only multiplied by job elapsed times, and when there are no jobs, no multiplication happens.

### Logger.error() fired on every task failure even when retries remained
- **Repo**: ansible/metrics-service
- **Commits**: 4867d01 (#226)
- **What happened**: Two `logger.error()` calls in the task system fired unconditionally on any task failure: one in `handle_task_error()` (apps/tasks/utils.py) and one in `submit_task_to_dispatcher()` (apps/tasks/tasks_system.py). When a task had remaining retry attempts, these ERROR logs caused false alarms in monitoring and broke the `no_error_logs` integration test. The fix: in `handle_task_error()`, the log is deferred until after the transaction that updates task status and increments attempts, then logs at WARNING if `can_retry()` is True, ERROR only on final failure. In `submit_task_to_dispatcher()`, `task.status = 'failed'` is set before calling `can_retry()` so the retry check is accurate. Helper functions `_fetch_task_by_id` and `_fetch_execution_by_id` were extracted for clarity.
- **Insight**: Log level must reflect whether a failure is transient (WARNING -- will be retried) or terminal (ERROR -- retries exhausted). The ordering matters: task status must be updated and attempts incremented *before* checking `can_retry()`, otherwise the check uses stale state and always allows retry.

### Schema nullability over-applied then partially reverted (config-1.0 and total_workers_vcpu-1.0)
- **Repo**: ansible/metrics-utility
- **Commits**: 7873f07 (#492), 56bcf5a (#495)
- **What happened**: PR #492 made several schema fields nullable to fix downstream validation failures (AAP-82505): four fields in `config-1.0` (`automated_since`, `date_expired`, `date_warning`, `license_date`) and `cluster_name` in `total_workers_vcpu-1.0`. The `config-1.0` changes were correct (these fields can legitimately be null in production), but `cluster_name` was wrong: the CLI wrapper raises `MissingRequiredEnvVar` when `METRICS_UTILITY_CLUSTER_NAME` is unset, so null can never appear in a valid tarball. The downstream consumer (`automation-analytics-backend`) stores it as `VARCHAR(255) NOT NULL` with a uniqueness constraint that depends on it being non-null. PR #495 reverted just the `cluster_name` change the same day.
- **Insight**: When making batch nullability changes to JSON schemas, evaluate each field individually against both the producer (does the code ever emit null?) and consumer (does the DB/handler accept null?). A field that is already enforced non-null at the producer level should stay non-null in the schema -- the schema is a safety net for misconfigured deployments, not just a description of what the consumer can handle.

### Private/custom Ansible collections leaked into anonymized Segment payload for indirect nodes
- **Repo**: ansible/metrics-utility
- **Commits**: a8fa4c1 (#496)
- **What happened**: The `anonymize_data()` function in `anonymized_rollups.py` already filtered custom collections from `module_stats`, `collection_stats`, `role_stats`, and `jobs_by_installed_collections_versions`, but the newer `indirect_nodes_by_collection` and `indirect_nodes_by_module` arrays were added without equivalent filtering. Private/custom collection names flowed through unfiltered into the Segment payload. The fix added filtering for both arrays in `anonymize_data()`: `by_collection` checks directly against `collections.json`, while `by_module` uses `DataframeContentUsage.extract_collection_name()` to derive the `namespace.collection` prefix from the FQCN before checking. The `_no_collection` and `_no_module` sentinels are also excluded.
- **Insight**: When adding a new data section to an anonymized payload, always check whether existing anonymization filters need to be extended to cover the new section. The `anonymize_data()` function acts as a final sanitization gate before Segment delivery, and new data paths bypass it unless explicitly added.

### Manual execution time estimate had a 30-minute floor that inflated short-job ROI
- **Repo**: ansible/metrics-service
- **Commits**: 4c9ef3a (#375)
- **What happened**: `TemplateMetadata._apply_time_estimate_defaults()` estimated manual execution time as `max(2x_elapsed_in_minutes, 30)`, capping at a minimum of 30 minutes. For very short jobs (e.g., 10 seconds elapsed = 0.33 minutes at 2x), this inflated the estimate to 30 minutes instead of rounding up to 1 minute. The 30-minute floor was removed, leaving only the pure `2x elapsed` calculation with `ROUND_UP` quantization and the existing 1,000,000-minute upper cap. This directly affected ROI/time-savings calculations because `time_savings = manual_time - elapsed - creation_time`.
- **Insight**: Artificial minimums on estimated values can cause misleading ROI reports. A 10-second automation job being credited as saving 30 minutes of manual work makes the ROI dashboard untrustworthy. Let the data reflect reality -- the upper cap (1M minutes) guards against overflow, but the lower bound should follow the formula without an artificial floor.

### Django APPEND_SLASH redirect does not survive gateway round-trip
- **Repo**: ansible/metrics-service
- **Commits**: 1cb4e5e (#364)
- **What happened**: The `PrometheusMetricsView` was registered only at `api/v1/metrics` (no trailing slash). When a client requested `/api/v1/metrics/` through the AAP Gateway, Django's `APPEND_SLASH` middleware issued a 301 redirect -- but the redirect URL used the internal service path, not the gateway-prefixed path. The gateway couldn't follow the redirect, and the client received a broken response. The fix registered `PrometheusMetricsView` at both `path("api/v1/metrics", ...)` and `path("api/v1/metrics/", ...)`, eliminating the need for a redirect entirely. Stale legacy `RedirectView` entries for `api/metrics` and `metrics` (from the original unauthenticated prometheus endpoint, #251) were also removed.
- **Insight**: When a Django service runs behind a reverse proxy or API gateway that rewrites paths, `APPEND_SLASH` redirects break because the 301 Location header contains the internal path, not the external gateway-prefixed path. The fix is to register views at both the slashed and unslashed URL paths. This is simpler and more reliable than trying to make `APPEND_SLASH` gateway-aware. Remove stale redirect entries when the original endpoint they pointed to has moved.

## Superseded / Semi-Obsolete

### Django signals on Task model caused widespread test failures
- **Repo**: ansible/metrics-service
- The `_skip_signals` workaround from a044bd7 (#54) is no longer needed. Signals were removed entirely in 85d2cbb (#57) because they don't work across process boundaries.

### dispatcherd config hardcoded database credentials
- **Repo**: ansible/metrics-service
- The hardcoded credentials in `config/dispatcherd.yaml` (from the `use_django_db` revert in 3a8f7d5 #48) were replaced in 0e15cbd (#66) with runtime injection from Django settings via `_load_config_with_django_db()`.

### URL prefix env var named inconsistently, fixed in follow-up PR
- **Repo**: ansible/metrics-service
- The `METRICS_URL_PREFIX` -> `METRICS_SERVICE_URL_PREFIX` rename from #69/#70 was superseded by #87 which moved URL prefix to a Django setting (`settings.URL_PREFIX`), and then by #91 which added proper prefix interpretation as an actual URL path prefix with slash sanitization.

### Dispatcherd max workers reduced from 4 to 1 as a band-aid
- **Repo**: ansible/metrics-service
- Workers 4->1 (#148), then 1->4 (#167) with real fixes. See the main entries above and `task_system.md`.

### Validator tool SCHEMAS_DIR not updated when schemas moved into package
- **Repo**: ansible/metrics-utility
- **Commits**: 14ee699 (#444), 154b633 (#447)
- **What happened**: PR #444 moved schemas from `schemas/` to `metrics_utility/schemas/` and updated the test file and CI workflow, but didn't update the hardcoded `SCHEMAS_DIR` in `tools/validator/validate.py`. The standalone validator uses `Path(__file__).resolve().parent.parent.parent / 'schemas'` which no longer pointed to any directory. PR #447 (same day follow-up) fixed it to `... / 'metrics_utility' / 'schemas'`.
- **Insight**: When moving package data files, standalone tools that reference the old path are easy to miss because they aren't part of the package import graph -- tests only caught this because the validator was exercised manually, not via CI.

### test_json_schema.py cleanup fixture missing `yield` -- cleanup ran before tests, not after
- **Repo**: ansible/metrics-utility
- **Commits**: eb853d8 (#448)
- **What happened**: The `cleanup_glob` fixture in `test_json_schema.py` (added in #428) removed files at the start of the fixture but never yielded, so pytest treated the fixture as setup-only -- it cleaned up before the test ran but not after. This left actual tarballs behind after test execution, potentially interfering with subsequent test runs. The fix added `yield` and moved cleanup to after the yield (teardown phase).
- **Insight**: A pytest fixture that performs cleanup must use `yield` to separate setup from teardown -- without `yield`, the entire fixture body runs before the test, and no teardown occurs. This is a common pytest fixture authoring mistake, especially when copying cleanup patterns from other test files.

### argparse None vs empty string for optional arguments
- **Repo**: ansible/metrics-service
- **Commits**: 686dfee (#278)
- **What happened**: The `metrics_service tasks create` management command had `add_argument("--description", help="...")` without a `default`. When `--description` was omitted, argparse set the value to `None`. The code used `options.get("description", "")` but the fallback never triggered because the key exists (its value is just `None`). This passed `NULL` to the DB's description column. Fix: `add_argument("--description", default="", ...)`.
- **Insight**: `dict.get(key, default)` only uses the default when the key is absent, not when the value is `None`. For argparse optional arguments that should default to empty string, always set `default=""` explicitly.

### Retry base delay must not be a multiple of task cron spacing
- **Repo**: ansible/metrics-service
- **Commits**: 9c6ed6f (#276)
- See [task_system.md](task_system.md#retry-base-delay-changed-from-10-to-8-minutes-to-avoid-collision-with-5-minute-task-spacing) for the full entry. Summary: `RETRY_BASE_DELAY_SECONDS` changed from 600 (10 min) to 480 (8 min) because 10 minutes is a multiple of the 5-minute task cron spacing, causing retry collisions. Coprime intervals eliminate systematic collisions.

### SEGMENT_MAX_ATTEMPTS mistakenly applied to local-only anonymize task
- **Repo**: ansible/metrics-service
- **Commits**: 9c6ed6f (#276)
- **What happened**: `SEGMENT_MAX_ATTEMPTS` (7) was mistakenly applied to the `daily_anonymize_and_prepare` task group entry in #220. This task only does local DB work (anonymize + create payload); the dynamically created `send_to_segment` task already gets `max_attempts=7` correctly in `daily_anonymize_and_prepare.py:123`. Reverted to the model default (3) by removing the `"max_attempts": SEGMENT_MAX_ATTEMPTS` line.
- **Insight**: Extended retry attempts should only be applied to tasks that interact with external services (where multi-hour outages are expected). Local DB-only tasks should use the default retry count.

### Renovate cron wildcard minute ran every minute instead of once per interval
- **Repo**: ansible/metrics-service
- **Commits**: 7e78597 (#281)
- **What happened**: The `renovate.json` Tekton schedule was `"* */12 * * 1-5"` -- the `*` in the minute position meant "run every minute for each matching hour", not "run once at each matching hour". This would fire 60 Renovate PRs per 12-hour window. Fixed to `"0 */12 * * 1-5"`. A PR check was also added to `pr-checks.yml` that greps for `"schedule".*"\* ` in `renovate.json` to prevent future wildcard-minute regressions.
- **Insight**: Cron's `*` in the minute field means "every minute", not "any minute" -- always specify a minute value (typically `0`) when using step expressions like `*/12` for hours. Adding a CI check for this pattern prevents the mistake from recurring.

### Stale psycopg3 connections not detected by Django's ensure_connection()
- **Repo**: ansible/metrics-service
- **Commits**: 33db88a (#273)
- **What happened**: `get_db_connection()` called `django_connection.ensure_connection()` to get the raw psycopg connection, but `ensure_connection()` only reconnects when `self.connection is None`. A connection dropped by the server (network partition, server restart) is not `None` -- it's a stale psycopg3 object. The fix adds a `SELECT 1` probe before `ensure_connection()`: if the probe raises (either because `.closed` is True or from a silent network drop), the connection is closed (setting it to None) so `ensure_connection()` will reconnect. The `close_old_connections()` approach cannot be used here because it closes ALL connections including ones holding advisory locks.
- **Insight**: Django's `ensure_connection()` does not detect dead connections -- it only reconnects when the connection attribute is `None`. For long-lived processes that use raw DB connections (not ORM), probe with `SELECT 1` before use. This is especially important for psycopg3 where a server-side disconnect leaves a stale object rather than setting it to `None`.

### Prometheus metrics endpoint exposed without authentication at /metrics
- **Repo**: ansible/metrics-service
- **Commits**: adde11d (#251)
- **What happened**: The `django_prometheus.urls` include was mounted at `path("")` which placed the endpoint at `/metrics` rather than under the `/api/` prefix used by all other metrics-service endpoints. More critically, the endpoint was unauthenticated, allowing any caller to scrape internal request rates, DB query counts, and error metrics. The fix moved the endpoint to `/api/metrics`, wrapped `ExportToDjangoView` in a `PrometheusMetricsView` (AnsibleBaseView subclass) with `permission_classes = [IsSystemAdminOrAuditor]`, added a temporary 302 redirect from `/metrics` for backwards compatibility during rollout, and updated the nginx location block.
- **Insight**: Third-party Django app URL includes (like `django_prometheus.urls`) mount at whatever path you give them -- they don't respect any project-wide URL prefix convention. Always check that (a) the path matches your API prefix convention and (b) the endpoint is not accidentally unauthenticated. Prometheus metrics leak operational data (request rates, error rates, DB stats) that should be restricted to admins.

### pytz usage surviving via transitive pandas 2.x dependency
- **Repo**: ansible/metrics-service
- **Commits**: e02d7c8 (#297), 250055f (#298)
- **What happened**: Dashboard reports test files used `pytz.UTC` and `pytz.utc` for timezone-aware datetimes, but `pytz` was never a declared dependency of metrics-service. It was available at runtime only because `pandas 2.x` pulled it in transitively. When `pandas 3.0` dropped its `pytz` dependency, these tests would break. Two quick-succession PRs replaced all `pytz.UTC`/`pytz.utc` references with `datetime.UTC` (stdlib, available since Python 3.11) across three test files: `test_tasks.py`, `test_models.py`, and `test_report_view_data.py`.
- **Insight**: Relying on transitive dependencies for test utilities creates a time bomb -- the transitive dependency can be dropped at any time (as pandas did with pytz in v3.0). Always import from declared dependencies or the stdlib. For timezone-aware datetimes in Python 3.11+, `datetime.UTC` is the stdlib replacement for `pytz.UTC`.

### GitHub Actions secrets context unavailable in `if` conditions
- **Repo**: ansible/metrics-service
- **Commits**: b583841 (#303), 395916f (#305)
- **What happened**: PR #303 added `secrets.CICD_ORG_SONAR_TOKEN_CICD_BOT != ''` directly in step-level `if:` conditions to skip SonarCloud/Codecov steps when secrets are missing (fork PRs). This caused workflow parse errors because the `secrets` context is not available in `if:` conditions at the job or step level. PR #305 fixed this within hours by introducing job-level `env` vars (`HAS_SONAR_TOKEN`, `HAS_CODECOV_TOKEN`) that evaluate the secrets expression at env-var assignment time, then checking `env.HAS_SONAR_TOKEN == 'true'` in step `if:` conditions.
- **Insight**: GitHub Actions `secrets` context cannot be used directly in `if:` expressions. The workaround is to assign the secret check result to a job-level `env:` variable (which CAN evaluate `secrets.*`), then reference the env var in `if:` conditions. This pattern is also useful for making fork PRs work gracefully -- they have no access to org secrets, so steps that need secrets should be skipped rather than failing.

### Startup race: collector tasks fail because AWX migrations haven't run yet
- **Repo**: ansible/metrics-service
- **Commits**: a559e33 (#280)
- **What happened**: On fresh installs, metrics-service collectors failed with ERROR-level stack traces because the AWX controller database tables (e.g., `main_unifiedjob`) didn't exist yet -- controller migrations were still running. The fix adds an `awx_db_ready()` check that probes `information_schema.tables` for known AWX tables before scheduling collector tasks. The scheduler's `_periodic_database_sync()` now calls this check and skips task scheduling if the DB isn't ready, logging WARNING during a 10-minute grace period and escalating to ERROR after (indicating controller migrations likely failed rather than just being slow). Stuck task detection (`_fail_stuck_tasks`) was moved BEFORE the readiness check so it always runs, even during startup.
- **Insight**: In multi-service deployments where services share databases, assume migration order is not guaranteed. Rather than failing immediately and losing the current collection window, poll for table existence with a grace period. The grace period + escalation pattern avoids both false-positive alerts (during normal startup) and silent suppression of genuine failures (broken migrations).

### Indirect nodes task silently never ran: unregistered function name in TASK_FUNCTIONS
- **Repo**: ansible/metrics-service
- **Commits**: f73fd16 (#315)
- **What happened**: The `INDIRECT_NODE_COLLECTION_GROUP` task was configured with `"function": "collect_indirect_nodes"`, but this function was never registered in `TASK_FUNCTIONS`. The cron scheduler dispatches tasks by looking up the function name in that registry, so `hourly_collect_indirect_nodes` would fail at execution time. The fix changed the function to `"collect_hourly_metrics"` with `"args": {"collector_type": "indirect_managed_nodes"}`, reusing the existing generic collector. Also removed `"collect_indirect_nodes"` from `_PREVIOUS_HOUR_FUNCTIONS`.
- **Insight**: When adding a new task group, always verify the `"function"` value exists in the `TASK_FUNCTIONS` registry. This failure was silent -- the task appeared correctly configured in the DB but silently failed when the scheduler tried to dispatch it.

### NaN string fields produce invalid JSON in dashboard serializer
- **Repo**: ansible/metrics-service
- **Commits**: aca0683 (#314)
- **What happened**: `_serialize_dashboard_record` guarded `_INT_FIELDS` and datetime fields against pandas NaN but not string columns. Nullable string columns (`organization_name`, `project_name`, `launched_by_username`, `label_ids`) arrived as `float('nan')` when the entire column was null. `DjangoJSONEncoder` serialised them as the token `NaN` (invalid JSON), causing `Task.task_data` writes to silently produce corrupt data and the `post_collect_hook` to fail -- no `sync_dashboard_job_records` tasks were created for those hours.
- **Insight**: Pandas coerces any column with mixed nulls to float64. Every field type (int, string, datetime, float) needs explicit NaN-to-None coercion before JSON serialisation. Missing one type causes silent data loss in downstream pipeline stages.

### Silent label deletion when label_ids column absent from collected data
- **Repo**: ansible/metrics-service
- **Commits**: d73d931 (#306)
- **What happened**: `sync_dashboard_job_records` used `row.get("label_ids")` which returned `None` when the key was absent (older metrics_utility versions without label support). This `None` was treated as "job has no labels", causing `_sync_labels` to delete all existing `JobLabel` records. The fix distinguishes between key-absent (`labels=None`, skip sync, preserve existing records) and key-present-but-null (`labels=[]`, clear stale records). This mirrors the existing `host_summaries=None` guard pattern already used in `create_or_update_from_awx`.
- **Insight**: When processing data from upstream sources that evolve their schema, distinguish between "column not present" (preserve existing data) and "column present with null/empty value" (data genuinely empty). Using `dict.get(key)` collapses both cases into `None`. Instead, check `key not in dict` for absence vs `dict[key] is None` for explicit null.

### DYNACONF._post_hooks AttributeError depending on dynaconf version
- **Repo**: ansible/metrics-service
- **Commits**: 266e199 (#343)
- **What happened**: The framework-managed `metrics_service/settings.py` accessed `DYNACONF._post_hooks` directly in a list comprehension that filters and executes post-hooks. Some dynaconf versions don't set the `_post_hooks` attribute on the instance, causing an `AttributeError` at startup. Fixed by changing to `getattr(DYNACONF, "_post_hooks", [])`.
- **Insight**: When accessing internal/private attributes on third-party objects (prefixed with `_`), always use `getattr()` with a default -- internal APIs can change between versions without notice. This is especially important in framework-managed files that must work across multiple dynaconf versions.

### TASK_METADATA example placed under wrong collector group
- **Repo**: ansible/metrics-service
- **Commits**: 2b3457f (#335)
- **What happened**: The `indirect_managed_nodes` collector is registered in `_get_daily_collectors()`, but its TASK_METADATA example entry was placed under `collect_hourly_metrics`. The example showed incorrect usage for users or tools referencing the metadata to build API calls. Moved to `collect_daily_metrics` metadata where it belongs.
- **Insight**: TASK_METADATA examples serve as documentation and as inputs for API tooling -- placing an example under the wrong task function is misleading even though it doesn't affect runtime behavior. When moving a collector between pipeline groups, update metadata examples too.

### macOS bash 3.2 incompatible with `wait -n`
- **Repo**: ansible/metrics-service
- **Commits**: 4e00776 (#317)
- **What happened**: `tools/dev.sh` used `wait -n` (wait for any one child process to exit) to detect when any of the three dev services (runserver, dispatcherd, scheduler) crashed. `wait -n` requires bash 4.3+, but macOS ships with bash 3.2 due to GPL v3 licensing. The script crashed with "invalid option" immediately after starting all services. Fixed with a `BASH_VERSINFO` version check that falls back to a `kill -0` polling loop on older bash versions.
- **Insight**: Dev scripts that target both Linux and macOS must avoid bash 4.x features (`wait -n`, associative arrays, `|&` pipe-stderr, `${var,,}` case modification) or detect the version and fall back. macOS bash is permanently stuck at 3.2 unless users install a newer one via Homebrew.

### Renovate requires wildcard minutes in cron schedules
- **Repo**: ansible/metrics-service
- **Commits**: 425138c (#341)
- **What happened**: PR #281 previously fixed a Renovate cron schedule that had `"* */12 * * 1-5"` (wildcard minute = runs every minute) by changing it to `"0 */12 * * 1-5"`. But Renovate doesn't support minute granularity at all -- it requires `*` for the minutes field. The fix broke the config entirely, causing Renovate to reject the schedule. Reverted to `"* */12 * * 1-5"` with a comment explaining why, and the PR check was flipped to enforce wildcard minutes (the opposite of what #281 enforced).
- **Insight**: Renovate's cron format is not standard cron -- it ignores the minutes field and requires `*` there. The same "wildcard minutes = runs every minute" logic that's correct for system cron is wrong for Renovate. Always check a tool's cron documentation before applying general cron best practices.

### IndirectManagedNodeAudit has no `modified` column (inherits BaseModel, not CreatedModifiedModel)
- **Repo**: ansible/metrics-utility
- **Commits**: 0fdebe3 (#483)
- **What happened**: The perf harness `create_indirect_managed_node_audits()` INSERT included a `modified` column, which worked against the local mock database but failed on a real AWX instance. `IndirectManagedNodeAudit` inherits directly from `BaseModel` rather than AWX's standard `CreatedModifiedModel` chain, so the table has only `created` but no `modified` column. This is intentional design -- audit records are append-only (created but never updated). Removed `modified` from both the VALUES and column list.
- **Insight**: AWX models don't all share the same base -- `IndirectManagedNodeAudit` uses `BaseModel` (created-only) while most models use `CreatedModifiedModel` (created + modified). Performance harness INSERTs must match the actual table schema, which may differ from the common pattern. Testing only against mocks can miss schema mismatches.

### Naive datetime raises ValueError in date_where utility
- **Repo**: ansible/metrics-utility
- **Commits**: 0fdebe3 (#483)
- **What happened**: The perf harness `rollup_performance_test.py` parsed `--since`/`--until` via `datetime.strptime()` which produces timezone-naive datetimes. The `date_where()` utility raises `ValueError` on naive datetime inputs. This worked against the local mock but failed on real instances because `unified_jobs` and `job_host_summary_service` collectors both call `date_where()` directly. Fixed by adding `.replace(tzinfo=timezone.utc)` after parsing.
- **Insight**: Always produce timezone-aware datetimes when working with the metrics pipeline -- `date_where()` rejects naive datetimes, and this only surfaces against real instances where the collector code path is exercised end-to-end.

### Perf harness fill and rollup used coincidentally matching dates
- **Repo**: ansible/metrics-utility
- **Commits**: 0fdebe3 (#483)
- **What happened**: The `run_all_dataset_sizes.py` script ran the fill step without explicit `--since`/`--until` flags (defaulting to January 2024) while the rollup queried January 2024 via `test_since`/`test_until` config. They matched, but only by coincidence. Fixed by passing explicit `--since`/`--until` from the config to the fill step, making the date coupling explicit and robust.
- **Insight**: When two pipeline steps must agree on a date range, pass it explicitly to both rather than relying on defaults that happen to match -- defaults can change independently, silently breaking the pipeline.

### Segment silently drops properties whose key contains "name"
- **Repo**: ansible/metrics-utility
- **Commits**: 44d165c (#484), 0b85f12 (#485)
- **What happened**: Segment downstream destinations filter out any property whose key contains the substring `name`. Fields like `collection_name`, `module_name` in `module_stats`, `collection_stats`, `role_stats`, and `by_collection`/`by_module` arrays were being silently dropped -- no error, no warning, just absent in analytics queries. Discovered only after checking downstream data. Renamed to `collection` and `module` across both indirect nodes (#484) and events modules (#485) rollups.
- **Insight**: Segment's property-name filtering is completely silent -- data is accepted by the Segment API but filtered out before reaching downstream destinations. This is a unique class of bug where the write succeeds and the data appears to be sent, but downstream queries return nothing. Always check Segment's reserved words and key-name restrictions before defining payload field names.

### Sonar S5779: assert inside bare except hides test failures
- **Repo**: ansible/metrics-utility
- **Commits**: c3d6e55 (#486)
- **What happened**: A test's CSV validation had `assert len(df) > 0` inside a `try/except Exception` block. If the assert failed, the `except` caught `AssertionError` and called `pytest.fail()` with a generic "Failed to read" message, hiding the actual assertion failure. Fixed by narrowing the `except` to `(IOError, UnicodeDecodeError, pandas.errors.ParserError)` -- specific I/O and parsing exceptions that the try block is actually guarding against.
- **Insight**: Never place `assert` inside a broad `except` block -- `AssertionError` is an `Exception` subclass, so bare `except Exception` catches test assertion failures and masks them behind a different error message. Use specific exception types in test try/except blocks.

### POC pushed direct to devel without PR — reverted
- **Repo**: ansible/metrics-service
- **Commits**: 3fe5d45, eccada7, dfe6110 (#349)
- **What happened**: Two commits adding a full `service_ingest` Django app (external service telemetry ingest pipeline with models, views, authentication, migrations, tasks, and settings) were pushed directly to the `devel` branch without going through a pull request. The second commit (eccada7) was an immediate fix for runtime issues found during local testing (missing `is_anonymous`/`is_active` on ServiceUser, DAB CommonModel.save() FK constraint via crum thread-local). The entire app was reverted two days later in PR #349 because it bypassed the PR review process. The revert carefully preserved the unrelated jira-pr-link workflow fix from #347 that had been interleaved.
- **Insight**: Never push feature work directly to the default branch, even for POCs. The two commits illustrate the risk: the first commit had runtime bugs (ServiceUser incompatible with DRF, CommonModel FK constraint), and the fix commit also bypassed review. The revert was surgically clean because the code was isolated in its own `apps/service_ingest/` directory -- good app isolation made the rollback straightforward.

### DAB CommonModel.save() reads crum thread-local user for created_by FK
- **Repo**: ansible/metrics-service
- **Commits**: eccada7 (reverted in dfe6110 #349)
- **What happened**: When a DRF view using a non-Django user (ServiceUser for token auth) created a Task via `Task.objects.create()`, DAB's `CommonModel.save()` read the request user from crum's thread-local storage and tried to set `created_by` as a FK to auth.User. Since ServiceUser is not a Django User model, this caused an FK constraint violation. The workaround was `crum.impersonate(None)` to temporarily clear the thread-local. A second fix switched ExternalEvent from CommonModel to plain `models.Model` to avoid the same issue entirely.
- **Insight**: Any model inheriting from DAB's CommonModel will attempt to set `created_by`/`modified_by` FKs via crum thread-local user. Service-to-service endpoints using non-Django auth users must either wrap model creation in `crum.impersonate(None)` or avoid CommonModel for models that don't need user audit trails.

### CSV cost rows exported as raw numbers instead of formatted currency strings
- **Repo**: ansible/metrics-service
- **Commits**: e93a1ba (#353)
- **What happened**: Dashboard report CSV exports wrote cost values (automated_costs, manual_costs, savings, automation_value) as raw `round(value, 2)` floats. This meant negative savings appeared as `-123.45` rather than `-$123.45`, and values lacked thousand separators or currency symbols. A `_format_currency()` static method was added that formats as `$1,234.56` for positive values and `-$1,234.56` for negative values (using Python's `f"${value:,.2f}"` format spec). Applied to both the summary CSV (`_write_summary_csv`) and the ROI CSV (`_write_roi_csv`).
- **Insight**: CSV exports consumed by non-technical users (finance, procurement) should format currency values with symbols and thousand separators, not raw floats. The negative-value case (`-$X` not `$-X`) requires explicit handling since Python's format spec puts the sign before the dollar sign.

### Null byte in query parameters caused unhandled PostgreSQL DataError (500)
- **Repo**: ansible/metrics-service
- **Commits**: 2fe0080 (#358)
- **What happened**: A request like `GET /api/v1/activitystream/?operation=%E2%80%99%00%E2%80%99` passed a null byte (`%00`) through to PostgreSQL via DAB's FieldLookupBackend. PostgreSQL rejects null bytes in string queries with a DataError, which is not in DAB's caught exception set (only ValueError/TypeError/ValidationError), resulting in an unhandled 500. A `NullByteQueryParamMiddleware` was added that inspects the raw `QUERY_STRING` for `%00` or literal `\x00` and returns 400 with a JSON error body before any view or filter backend runs. The middleware sits between `ServicePrefixMiddleware` and `APIRootViewMiddleware` to cover all endpoints.
- **Insight**: Input validation for characters that are illegal at the database level (null bytes for PostgreSQL, certain Unicode for other DBs) should happen in middleware, not in individual views or filter backends. This ensures coverage for all endpoints including third-party ones (DAB views) that the project doesn't control. The middleware inspects the raw QUERY_STRING rather than parsed query params to catch the bytes before URL decoding.

### Swagger UI schema URL missing gateway service prefix
- **Repo**: ansible/metrics-service
- **Commits**: d483b0a (#359)
- **What happened**: When metrics-service runs behind the AAP Gateway (which proxies under `/api/metrics/`), the Swagger UI fetched its OpenAPI schema from `/api/v1/docs/schema/` -- a bare internal path unreachable through the gateway. Django's `reverse()` generates paths without the gateway prefix because the prefix is stripped by `ServicePrefixMiddleware` before Django's URL resolver sees it. Fix: a `MetricsSpectacularSwaggerView` subclass overrides `_get_schema_url()` to prepend `request._api_service_prefix` (set by `ServicePrefixMiddleware`). DAB's `api_documentation` app was excluded from URL registration via `ANSIBLE_BASE_APPS_EXCLUDE_VIEW_LIST` so the custom view takes precedence. A related bug: the `feature_flags` redirect pointed to `/api/v1/feature_flags/states/` instead of `/api/metrics/v1/feature_flags/states/`, also unreachable through the gateway.
- **Insight**: When a service runs behind a reverse proxy that adds a path prefix, any URL generated by Django's `reverse()` will be missing that prefix. Views that emit URLs to the client (Swagger UI schema URL, redirect Location headers) must explicitly reconstruct the full external path using the prefix stored on the request by the prefix-stripping middleware. DAB-provided views can be excluded from URL registration via `ANSIBLE_BASE_APPS_EXCLUDE_VIEW_LIST` without disabling the app itself.

### CLI indirect nodes collector lost daily_slicing and since/until passthrough
- **Repo**: ansible/metrics-utility
- **Commits**: e6640a3 (#508)
- **What happened**: The CLI collector for `main_indirectmanagednodeaudit` was registered with `fnc_slicing=until_slicing` (full-table snapshot) instead of `fnc_slicing=daily_slicing`, and did not pass `since`/`until` to the underlying `main_indirectmanagednodeaudit()` function. This meant the CLI collector was doing a full-table scan instead of filtering by `main_unifiedjob.finished` within the time window, causing double-counting across daily runs and inconsistent results compared to the service collector (which already used daily_slicing with since/until). The fix restored `fnc_slicing=daily_slicing` on the `@register` decorator and added `since=since, until=until` to the collector function call. An `ORDER BY main_indirectmanagednodeaudit.created ASC` clause was also added to the SQL query for deterministic output ordering. The test was updated to assert that `since` and `until` are passed through.
- **Insight**: When the same collector has two registration paths (CLI via `@register` decorator in `collectors.py` and service via direct function call), they must use the same slicing strategy and pass the same parameters. The CLI path was left behind when the service path was updated in #475 to use `daily_slicing` with `date_where()` -- always update both call sites when changing a collector's time-window behavior.

### NULL host_id fix for job_host_summary SQL collector reverted -- needed more analysis
- **Repo**: ansible/metrics-utility
- **Commits**: 87b61bf (#532), b11fd5a (#533)
- **What happened**: On SaaS operator deployments, `main_jobhostsummary.host_id` can be NULL. The existing `job_host_summary` collector JOINed to `main_host` using `ON main_host.id = filtered_hosts.host_id`, which silently fails for NULL host_id rows because `NULL = NULL` is false in SQL. This left `ansible_host_variable` as NULL, breaking hostname-based deduplication. PR #532 added `host_name` to the `filtered_hosts` CTE and used a two-branch JOIN: when `host_id IS NOT NULL`, JOIN by ID (unchanged); when `host_id IS NULL`, fall back to JOIN by `host_name`. However, PR #533 reverted this fix two days later. The revert suggests the name-based fallback JOIN may have had unintended consequences (e.g., many-to-many matches when multiple hosts share a name across inventories, or performance regression from the OR-based JOIN condition on large tables).
- **Insight**: SQL `NULL = NULL` is false, so LEFT JOIN conditions on nullable columns silently produce no match. A name-based fallback JOIN is conceptually correct but risky without careful analysis of uniqueness constraints -- `host_name` is not guaranteed unique across inventories, so the fallback could produce incorrect many-to-many matches. Quick reverts like this (2 days later) indicate the fix needs more analysis of edge cases before re-attempting.

### Segment header overhead calculated dynamically instead of hardcoded conservative limit
- **Repo**: ansible/metrics-utility
- **Commits**: 6109745 (#510)
- **What happened**: The `REGULAR_MESSAGE_LIMIT` was restored from the conservative 24KB (set in #281) back to the actual Segment SDK limit of 32KB. Instead of subtracting a fixed safety margin, the `put()` method now dynamically calculates the header overhead by constructing a representative header object containing all non-data fields (envelope: type, messageId, timestamp, integrations, context; properties: artifact_name, upload_timestamp, chunk_info; plus segment_meta fields like message_id, integrations, context) and measuring its serialized JSON size. The available space for data chunks is `REGULAR_MESSAGE_LIMIT - overhead`. For hashed message IDs, a 64-char placeholder is used in the overhead calculation (since the actual hash is not known until send time). A `_build_properties()` helper was extracted to share the properties structure between the overhead calculation and the actual `analytics.track()` call, ensuring they stay in sync. Guards were added to `_split_into_chunks()`: `ValueError` on non-positive `max_size`, warnings on oversized dict values and single list items that exceed `max_size`. Datetime values in segment_meta are converted to ISO format strings before serialization to prevent `TypeError` from `json.dumps()`.
- **Insight**: When chunking payloads for a size-limited API, calculate the envelope overhead dynamically from the actual header structure rather than using a hardcoded safety margin. A fixed margin (like subtracting 8KB from 32KB) either wastes capacity when the header is small or fails when the header grows (e.g., longer segment_meta fields). Building a representative header object and measuring it ensures the budget adapts to any header changes. **Supersedes** the conservative 24KB limit from #281.

### AWX label dedup via GROUP BY collapsed org-scoped labels -- reverted next day
- **Repo**: ansible/metrics-service
- **Commits**: fd7ba37e (#387), d7a776cf (#390), d3ce5e63 (#389)
- **What happened**: Labels in AWX have `unique_together = (name, organization)`, meaning the same label name can be distinct labels in different organizations. The initial fix (#387) used `SELECT MIN(id) as id, name FROM main_label GROUP BY name` to collapse "duplicates" -- but this was wrong: it treated org-scoped labels as true duplicates and silently dropped all but one. The approach also required a separate `GROUP_BY_CLAUSES` dict to compose SQL in the correct clause order (WHERE must precede GROUP BY). The fix was reverted the next day (#390) and replaced with #389, which joins `main_organization` and disambiguates by appending the org name only to labels whose name occurs more than once (e.g., "production (Org A)", "production (Org B)").
- **Insight**: When entity names are scoped by a parent (org, team, project), `GROUP BY name` is the wrong dedup strategy -- it destroys legitimate data. The correct approach is disambiguation (show the scope when there is ambiguity), not dedup (collapse to one). The rapid fix-revert-replace cycle (3 PRs in 2 days) shows the value of reverting first and fixing properly rather than patching the broken fix. See [metrics_service.md](metrics_service.md#dashboard-label-disambiguation-by-organization-instead-of-dedup) for the final correct implementation details.

### Dashboard card counts disagreed with job listing due to template_metadata filter
- **Repo**: ansible/metrics-service
- **Commits**: 17a3cd12 (#386)
- **What happened**: `DashboardReportViewSet.details()` computed total_runs/total_successful_runs/total_failed_runs from `_build_aggregated_queryset()`, which joins and filters by `template_metadata_id IS NOT NULL`. Jobs without template metadata (orphan rows) appeared in the raw job listing but were excluded from the card counts, causing a persistent mismatch. The fix separates card counts (computed on `filtered_qs` with `Count("id", filter=Q(status=...))`) from cost/time annotations (still use the aggregated queryset that needs TemplateMetadata fields).
- **Insight**: When an aggregation requires a JOIN or filter that excludes rows, counts derived from the same queryset will be undercounted relative to the unfiltered listing. Always compute simple counts (total, successful, failed) on the broadest applicable queryset, even if other aggregations need narrower filters.
