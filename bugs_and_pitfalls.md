# Bugs and Pitfalls

### Missing `__init__.py` files when adding new subpackages
- **Repo**: ansible/metrics-utility
- **Commits**: 858b2e5 (#10)
- **What happened**: PR #9 added several new subdirectories (`dataframe_engine/`, `extract/`, `package/`, `report/`) but forgot to include `__init__.py` files. PR #10 was an immediate follow-up fix adding the four missing init files. The `package/` directory was created by refactoring a single `package.py` file into a `package/` subpackage.
- **Insight**: When converting a module file (e.g. `package.py`) into a subpackage directory (`package/`), always remember the `__init__.py` -- this is easy to miss since the old single-file module didn't need one.

### Leftover `print()` statement shipped in production code
- **Repo**: ansible/metrics-utility
- **Commits**: ba08a25 (#6)
- **What happened**: The billing feature PR (#5) included a `print(since, until)` debugging statement in the gather command. It was caught and removed in a follow-up PR the same day.
- **Insight**: Debug print statements in CLI tools are particularly visible since the output goes directly to users; review for stray prints before merging.

### Report generation crashes on empty billing data
- **Repo**: ansible/metrics-utility
- **Commits**: 958e924 (#11)
- **What happened**: The `build_report` command did not check for `None` or empty dataframes before passing them to the report engine, causing crashes when no billing data existed for the requested month. The fix added an early return with an informational log message.
- **Insight**: Always guard against empty result sets when building reports from collected data -- months with no automation activity are a valid scenario.

### SQL query used `<=` instead of `<` for the upper time bound
- **Repo**: ansible/metrics-utility
- **Commits**: 6e60790 (#9)
- **What happened**: The job_host_summary SQL query originally used `modified <= until` for the upper bound. PR #9 changed this to `modified < until` to correctly implement exclusive upper bounds, preventing records from being included in two adjacent daily slices.
- **Insight**: Time-range queries with daily slicing must use exclusive upper bounds (`<`) to avoid double-counting records at slice boundaries.

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

### Unreachable hosts were being counted as managed nodes in CCSP billing
- **Repo**: ansible/metrics-utility
- **Commits**: db4eeea (#79)
- **What happened**: When a host had all tasks in `unreachable`/`dark` state (no successful, failed, skipped, ignored, or rescued tasks), it was still being counted as a managed node in the CCSP billing report. The fix adds a `reachable_task_runs` column that sums all task counters except `dark`, then filters out rows where `reachable_task_runs == 0`. This changed all snapshot test reference files since some test data included unreachable hosts.
- **Insight**: For billing purposes, a host that was never actually reached by any task should not count as a "managed node" -- the `dark` counter in Ansible represents connection failures, not automation.

### build_report error message didn't distinguish month vs date range
- **Repo**: ansible/metrics-utility
- **Commits**: 3c1dc4d (#63)
- **What happened**: When no billing data was found, `build_report` always logged "No billing data for month: {opt_month}" even when `--since`/`--until` date range parameters were used (in which case `opt_month` would be `None` or misleading). The fix checks whether `opt_since` was provided and formats the message accordingly: either "No billing data for input date range {since}--{until}" or "No billing data for month {month}".
- **Insight**: Error messages should reflect the actual input mode used -- a generic message that assumes one calling convention confuses users of another.

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

### Tests used hardcoded absolute paths from a specific developer's environment
- **Repo**: ansible/metrics-utility
- **Commits**: edfe31c (#74)
- **What happened**: All CCSP/CCSPv2 report tests (including the newly added complex test from PR #70) hardcoded paths like `/awx_devel/awx-dev/metrics-utility/metrics_utility/test/test_data` for `METRICS_UTILITY_SHIP_PATH` and expected output files. These paths only existed in one developer's AWX development environment. The fix changed them to relative paths (`./metrics_utility/test/test_data`). Additionally, the complex CCSPv2 test was named `complex_test_CCSPv2.py` which pytest doesn't discover by default (requires `test_` prefix); it was renamed to `test_complex_CCSPv2.py`.
- **Insight**: Hardcoded absolute paths from a development environment are a silent CI failure risk -- tests appear to be added but never actually run until someone tries to enable them in a different environment.

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

### `handle_env_validation` ran before `init_logging`, so validation errors were invisible
- **Repo**: ansible/metrics-utility
- **Commits**: a3dbd4f (#146)
- **What happened**: After #141 moved `handle_env_validation` into `handle()`, it was placed at the top of `handle()` before `init_logging()`. Since the logger wasn't initialized yet, any validation error messages would not be properly logged. PR #146 moved `handle_env_validation` *after* `init_logging()` inside `_handle()`, ensuring the logger is set up before validation runs.
- **Insight**: Validation that reports errors via logging must run after the logger is initialized -- ordering within `handle()` matters just as much as being in `handle()` at all. **Supersedes** the ordering from #141.

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

### `logger.propagate = True` caused duplicate log output after adding custom handler
- **Repo**: ansible/metrics-utility
- **Commits**: 42464e0 (#142)
- **What happened**: The `build_report` command's `init_logging` added a custom `StreamHandler` to the `awx.main.analytics` logger but left `propagate = True` (set in an earlier PR). This caused log messages to be emitted twice -- once by the custom handler and once by the root logger. The fix set `propagate = False`, matching the pre-#128 behavior.
- **Insight**: When adding a custom handler to a named logger, set `propagate = False` to prevent the parent/root logger from also emitting the same messages.

### SQL `NOW()` in test data scripts produced non-deterministic timestamps
- **Repo**: ansible/metrics-utility
- **Commits**: e65b320 (#145)
- **What happened**: The `main_jobhostsummary.sql` test data script used `NOW()` for `created`, `modified`, and other timestamp columns. This caused non-deterministic test data -- each time the script ran, timestamps changed, making gather tests flaky (they filter by time range). The fix replaced all `NOW()` calls with fixed timestamps (`TIMESTAMP WITH TIME ZONE '2025-06-13 10:00:00+00'`).
- **Insight**: Test data SQL scripts must use fixed timestamps, not `NOW()` -- gather collectors filter by time range, so non-deterministic timestamps cause the same data to appear or disappear depending on when the test runs.

### `report_period` vs `report_period_range` confusion caused KeyError for renewal guidance
- **Repo**: ansible/metrics-utility
- **Commits**: cda736f (#149)
- **What happened**: The report system had two separate date range params: `report_period` (set to `opt_month`) passed as a constructor arg to Report classes, and `report_period_range` (set to `"since, until"`) inside `extra_params`. `ReportFactory` would overwrite `report_period` with `report_period_range` when present. But `ReportRenewalGuidance` used `extra_params['report_period_range']` directly, which didn't exist when `--month` was used, causing a KeyError. The fix unified both into a single `extra_params['report_period']`, set to `opt_month` for `--month` or `"since, until"` for `--since`.
- **Insight**: Having two overlapping config keys for the same concept (`report_period` as constructor arg and `report_period_range` in extra_params) creates confusion and KeyError bugs -- unify to a single key.

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

### Renewal guidance dedup classes crashed on None dataframe instead of empty result
- **Repo**: ansible/metrics-utility
- **Commits**: 6467590 (#194)
- **What happened**: `DedupRenewal.run()` assumed `self.dataframe` was always a valid DataFrame and called `self._cleanup_null_values()` on it directly. When `ExtractorControllerDB` returned `None` or an empty DataFrame, the dedup would crash with `AttributeError`. `DedupRenewalHostname` and `DedupRenewalExperimental` already had `if self.dataframe.empty` guards, but these would still crash on `None`. The fix added `if self.dataframe is None or self.dataframe.empty` checks to all three dedup classes, returning `{'host_metric': pd.DataFrame()}` for the empty case.
- **Insight**: All code that receives a dataframe from an extractor or factory must handle both `None` and empty DataFrame -- even if the upstream was "fixed" to return empty DataFrames (#118), defensive checks in consumers prevent regression if upstream behavior changes.

### config.json billing_provider_params were saved to tarball before being updated
- **Repo**: ansible/metrics-utility
- **Commits**: a88a277 (#217)
- **What happened**: The billing collector's `gather()` method called `_gather_json_collections()` (which writes config.json into the tarball) and only afterward appended `billing_provider_params` to the config collection data. This meant the config.json inside tarballs shipped to CRC was missing the billing provider params (account ID, org ID, etc.). The fix moved the billing_provider_params injection into an overridden `_gather_config()` method that runs *during* JSON collection gathering (before the data is saved to tarball), by calling `super()._gather_config()` first and then extending the config data.
- **Insight**: When extending collected data with additional fields, the extension must happen during the collection phase (by overriding the appropriate gather method), not after -- otherwise the data is already serialized to the tarball without the extensions.

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

### Missing `__init__.py` in `anonymized_rollups/` subpackage (third occurrence)
- **Repo**: ansible/metrics-utility
- **Commits**: dbb7426 (#278)
- **What happened**: The `metrics_utility/anonymized_rollups/` directory was created across multiple PRs (#215, #239, #250) but never received an `__init__.py` file. PR #278 added it with explicit `__all__` exports for all rollup classes and functions. Additionally, a `metrics_utility/library/anonymize/` package was added with an `__init__.py` exposing `anonymized_rollups_processor` as the library entry point.
- **Insight**: This is the third time this exact bug occurred in the project (after #10 and #25) -- new subpackages are created without `__init__.py`. The pattern persists because the code works in development (where the directory is on `sys.path`) but fails when imported as a package.

### `collections.json` loaded with hardcoded relative path, broke when CWD changed
- **Repo**: ansible/metrics-utility
- **Commits**: 0118135 (#287)
- **What happened**: `EventModulesAnonymizedRollup.__init__` opened `collections.json` using a hardcoded relative path: `open('metrics_utility/anonymized_rollups/collections.json')`. This worked when running from the project root but broke when the current working directory was different (e.g., when called from the metrics service or from within a tempdir). The fix used `os.path.join(os.path.dirname(__file__), 'collections.json')` to load the file relative to the module's own location.
- **Insight**: Never use hardcoded relative paths to load package data files -- use `os.path.dirname(__file__)` or `importlib.resources` to resolve paths relative to the module, since the working directory is not guaranteed to be the project root.

### Segment chunking algorithm broke on real data: metadata overhead and dict-vs-list handling
- **Repo**: ansible/metrics-utility
- **Commits**: 4692757 (#281)
- **What happened**: The `StorageSegment._split_into_chunks()` method had multiple issues with real anonymized rollup data: (1) The 32KB `REGULAR_MESSAGE_LIMIT` was the raw Segment limit, but the actual message includes metadata (anonymous_id, event_name, timestamp, chunk_info) that consumes space. The limit was reduced from 32KB to 24KB (and 512MB to 500MB) to leave room. (2) The chunking algorithm handled lists and dicts with separate code paths (`_split_dict_into_chunks`) that didn't match the actual data shape -- the anonymized rollup data is a dict whose values are either dicts (statistics, small) or lists (module_stats, potentially large). The rewrite iterates dict entries: dict values become one chunk each, list values are split item-by-item into size-limited chunks, and the entire payload is returned as a single chunk if it fits. (3) The old code had a `_split_dict_into_chunks` fallback that printed warnings to stderr instead of raising errors -- the rewrite raises on unexpected types. The test data was moved to a separate `testing_data_for_segment.py` file.
- **Insight**: Size-limited chunking for API payloads must account for the envelope metadata overhead (auth tokens, timestamps, chunk metadata) -- using the raw API limit as the chunk size causes the final serialized message to exceed the limit. **Extends** the chunking from #249 with practical fixes.

### Missing utf-8 encoding on CSV read/write caused Unicode errors with non-ASCII data
- **Repo**: ansible/metrics-utility
- **Commits**: a3f00ba (#302)
- **What happened**: Several `pd.read_csv()` and `df.to_csv()` calls throughout the codebase did not specify `encoding='utf-8'`. While Python 3 defaults to the system locale encoding (usually UTF-8 on Linux), this could cause `UnicodeDecodeError` in environments with different locale settings, or when CSV data contained non-ASCII characters (e.g., organization names, hostnames with special characters). The fix added `encoding='utf-8'` to `pd.read_csv()` in `load_anonymized_rollup_data()`, `_read_csv()` in the extract base, and to `df.to_csv()` in test helpers. A variable name bug from a merge conflict in `load_anonymized_rollup_data` was also fixed.
- **Insight**: Always specify `encoding='utf-8'` explicitly on CSV operations in data pipelines that handle user-generated content (hostnames, org names, template names) -- relying on the system default encoding is fragile across deployment environments.

### vCPU timestamps lacked UTC timezone indicator, causing ambiguous time interpretation
- **Repo**: ansible/metrics-utility
- **Commits**: d90801d (#314)
- **What happened**: The `total_workers_vcpu` collector produced ISO 8601 timestamps with `+00:00` suffix (e.g., `2023-01-01T10:00:00+00:00`), but downstream consumers expected the `Z` suffix for UTC (e.g., `2023-01-01T10:00:00.000Z`). The fix changed all `datetime.fromtimestamp().isoformat()` calls to use `isoformat(timespec='milliseconds').replace('+00:00', 'Z')`. Additionally, the hour boundary calculation was changed from `current_hour_start - 1` (ending at `:59:59`) to `current_hour_start - 0.001` (ending at `:59:59.999`), and the PromQL query range was extended from `59m59s` to `59m59s999ms` to match the millisecond precision.
- **Insight**: When producing timestamps for external APIs that expect RFC 3339 / ISO 8601, use `Z` suffix instead of `+00:00` for UTC -- while semantically equivalent, many consumers only recognize the `Z` form. Also ensure timestamp precision is consistent across boundaries (milliseconds in timestamps should match milliseconds in query ranges).

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

### ID column conversion used `apply(lambda)` per row, replaced with vectorized `pd.to_numeric`
- **Repo**: ansible/metrics-utility
- **Commits**: b7037cf (#350)
- **What happened**: The `JobsAnonymizedRollup._convert_id_columns_to_strings()` method used `dataframe[col].apply(lambda x: str(int(x)) if pd.notna(x) and isinstance(x, (int, float)) and x == int(x) else x)` to convert ID columns to strings. This was slow for large DataFrames and raised `SettingWithCopyWarning` in some cases. The fix replaced it with vectorized pandas operations: `pd.to_numeric(errors='coerce')` to coerce values, a boolean mask for non-null rows, then `astype(int).astype(str)` on the masked subset. Similarly, filtering unfinished jobs changed from `dataframe[dataframe['finished'].notna()]` (which may return a view) to `dataframe.dropna(subset=['finished'])` (which always returns a new DataFrame), avoiding `SettingWithCopyWarning` on subsequent mutations.
- **Insight**: When converting DataFrame columns, prefer vectorized pandas operations (`pd.to_numeric`, `astype`, `dropna`) over `apply(lambda)` -- vectorized operations are 10-100x faster and avoid `SettingWithCopyWarning` issues with DataFrame views vs copies.

### Pandas 2.2+/3.x: assigning string values to int64 column triggers StringArray coercion error
- **Repo**: ansible/metrics-utility
- **Commits**: 6e3d653 (#351)
- **What happened**: The `JobsAnonymizedRollup._convert_id_columns_to_strings()` method assigned `numeric[mask].astype(int).astype(str)` into `dataframe.loc[mask, col]` where the column was originally int64. In pandas 2.2+/3.x, this produced a StringArray which pandas then tried to cast back to int64, causing a coercion error. The fix: (1) cast the column to `object` dtype first with `dataframe[col] = dataframe[col].astype(object)`, and (2) use `numeric[mask].to_numpy(dtype=float).astype(int).astype(str)` to produce a plain numpy array instead of a StringArray. Additionally, the `_get_collection_cache_key` NaN check was simplified from `isinstance(ee_id, float) and pd.isna(ee_id)` to just `pd.isna(ee_id)`, since `pd.isna()` handles all nullable types.
- **Insight**: When assigning string values back into a DataFrame column that was originally numeric, first cast the column to `object` dtype to prevent pandas from trying to coerce the new StringArray values back to the original numeric dtype. **Extends** the vectorized ID conversion from #350.

### Segment event loss: sync_mode=True is the only reliable delivery method
- **Repo**: ansible/metrics-utility
- **Commits**: 4474a6c (#383)
- **What happened**: Segment's Python SDK batches `track()` calls into background HTTP POSTs, and silently drops events from batches exceeding 500KB (returning HTTP 200 with no error callback). Three approaches were tried: (1) `time.sleep` after flush -- race condition, process exits before background thread finishes; (2) batch size tracking with mid-loop `flush()` at 450KB -- still dropped events because the SDK adds 2-3KB of per-event metadata (context, timestamps, messageId, integrations) that the data-size estimate couldn't account for; (3) `analytics.sync_mode = True` -- sends each `track()` as a separate blocking HTTP request (~25KB each), eliminating both the batch-size and background-thread problems. End-to-end testing confirmed 15/15 chunks delivered reliably. Gzip compression was also tried but Segment silently rejects gzip-encoded bodies (HTTP 200, 0 events received).
- **Insight**: When a third-party analytics SDK silently drops events from oversized batches and provides no reliable way to estimate the true per-event overhead, sync_mode (one HTTP request per event) is the only reliable delivery method, even at the cost of higher latency.

### `date_where()` double-quoting broke qualified column names in PostgreSQL
- **Repo**: ansible/metrics-utility
- **Commits**: 04e583a (#353)
- **What happened**: The `date_where()` utility wrapped field names in double quotes (`"table.column"`), but in PostgreSQL `"table.column"` is treated as a single identifier (a column literally named `table.column`), not as a qualified reference. Six collectors manually interpolated since/until timestamps instead of using `date_where()` because of this bug. The fix removed the quoting (all callers pass hardcoded internal strings, so SQL injection is not a concern here) and added runtime validation that since/until are timezone-aware datetimes, catching naive datetimes or wrong types early rather than generating incorrect SQL.
- **Insight**: In PostgreSQL, `"table.column"` is a single quoted identifier, not a table-qualified column reference -- never wrap qualified column names in double quotes. When a utility function has a known bug, callers work around it by duplicating the logic inline, creating a hidden maintenance cost.

