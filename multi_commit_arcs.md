# Notable Multi-Commit Arcs

Sequences where an approach was tried, revised, and sometimes revised again across multiple PRs — showing the evolution of a decision.

## Cross-repo arcs

### SonarCloud CI (parallel evolution)
- **Files**: ci_cd.md
- **Evolution**: both repos independently hit the same pitfalls with `pull_request_target` and PwnRequest vulnerabilities, arriving at similar `workflow_run`-based solutions. m-u went through 6 PRs (#89 -> #321), m-s through ~8 PRs (ee93077 -> #193).

### Collector architecture (interlocking halves)
- **Files**: architecture.md, metrics_collection.md
- **Evolution**: m-u extracted collectors from monolithic CLI code into `library/` with env-var-free interfaces (#248, #339). m-s independently evolved from individual collector files (#79) through legacy removal (#92) to a registry-based `collect_hourly`/`collect_snapshot` design (#109) that consumes the library collectors.

### Segment delivery pipeline (send side + receive side)
- **Files**: architecture.md, metrics_collection.md, bugs_and_pitfalls.md
- **Evolution**: m-u owns the send side — chunking at 32KB (#249) -> metadata fix (#281) -> trial-serialization sizing (#372) -> `sync_mode=True` (#383). m-s owns the scheduling side — fixed cron -> jittered task (#183) -> `use_bulk` removed (#195) -> truly random jitter (#201). Both repos independently removed `use_bulk` after discovering it didn't work.

## metrics-service arcs

### Serializer base classes
- **Files**: api_design.md, architecture.md
- **Evolution**: ModelSerializer (initial) -> HyperlinkedModelSerializer (ad01618) -> custom BaseModelSerializer with auto read-only fields and CountFieldMixin (#9) -> replaced by DAB's NamedCommonModelSerializer/CommonUserSerializer (#73)
- **PRs**: ~4

### Container architecture flip-flop
- **Files**: docker_and_deployment.md
- **Evolution**: separate web + dispatcher containers (initial) -> merged into single container (#45) -> split back into 4 containers (init+web+dispatcher+scheduler) (#117) -> production architecture with Nginx+Gunicorn (#129)
- **PRs**: ~4

### Scheduler evolution
- **Files**: task_system.md
- **Evolution**: polling-based TaskScheduler (141801c) -> APScheduler attempted, rolled back to polling (#25) -> CronTaskScheduler renamed to UnifiedTaskScheduler, simple_scheduler removed (#56) -> moved to separate process (#57) -> management command rewritten from threads to processes (#85)
- **PRs**: ~5

### Docker dependency management
- **Files**: docker_and_deployment.md, dependencies_and_packaging.md
- **Evolution**: pip + requirements.txt (initial) -> uv inside container (#18) -> uv removed, back to plain pip (#45), Konflux uses requirements-build.txt
- **PRs**: 3

### Pytest workflow trigger
- **Files**: ci_cd.md
- **Evolution**: initial with `pull_request_target` (ee93077) -> moved to future-workflow dir to disable (#7) -> restored with `pull_request_target` (#11) -> switched to `pull_request` (#27)
- **PRs**: ~4

### SonarCloud integration saga
- **Files**: ci_cd.md
- **Evolution**: added initially (ee93077) -> removed from pytest (#17) -> re-added via `workflow_run` pattern (#93) -> hardened with PR validation (#101) -> reorganized scan split (#127/#128/#134) -> exclusions expanded (#193)
- **PRs**: ~7-8

### URL prefix
- **Files**: settings_and_configuration.md
- **Evolution**: env var -> renamed env var -> Django setting -> proper prefix interpretation (4 iterations)

### Validation saga
- **Files**: settings_and_configuration.md
- **Evolution**: added -> broke -> turned off -> re-enabled with proper messages (5 PRs over 3 months)

### Migration history rewrites
- **Files**: database_and_migrations.md
- **Evolution**: tasks migrations rewritten during core-to-tasks extraction (#14) -> rewritten again during retrofit prep (#73) -> squashed for the third time (#140)
- **PRs**: 3

### Dispatcherd DB config
- **Files**: docker_and_deployment.md, bugs_and_pitfalls.md, settings_and_configuration.md
- **Evolution**: hardcoded YAML credentials -> `use_django_db=true` (broke, reverted next day #45/#48) -> back to hardcoded YAML -> runtime injection from Django settings via `_load_config_with_django_db` (#66)
- **PRs**: ~3

### Worker count
- **Files**: task_system.md, docker_and_deployment.md
- **Evolution**: 4 -> 1 (band-aid) -> 4 (real fix with atomic updates and advisory locks)

### Feature flag evolution
- **Files**: task_system.md, settings_and_configuration.md
- **Evolution**: single flag -> overly broad scope -> three independent flags -> FEATURE_ENABLED renamed to FEATURE, DB seeding removed in favor of env-var-driven defaults (#250)

### Settings API lifecycle
- **Files**: api_design.md, settings_and_configuration.md
- **Evolution**: ConfigView with DYNACONF.merge (#26) -> RESTful SettingView with DB persistence (#31) -> SettingSerializer broken after retrofit (#74, fixed) -> entire endpoint removed for security (#185)
- **PRs**: ~4

### Django signals for task routing
- **Files**: task_system.md, bugs_and_pitfalls.md, testing.md
- **Evolution**: post_save signal added for auto-routing (#25) -> caused widespread test failures, `_skip_signals` workaround (#54) -> signals removed entirely because cross-process (#57), replaced by APScheduler polling
- **PRs**: ~3

### Dockerfile labels
- **Files**: docker_and_deployment.md, bugs_and_pitfalls.md
- **Evolution**: copied from metrics-utility with wrong product name -> corrected to metrics-service (#94) -> updated to Konflux tech-preview format but CPE reverted to metrics_utility (#99)
- **PRs**: ~3

### Konflux hermetic builds
- **Files**: docker_and_deployment.md, dependencies_and_packaging.md
- **Evolution**: blanket `--no-binary :all:` in Dockerfile (#95) -> removed to unblock (#98) -> re-added in requirements-build.txt (#100/#102) -> targeted `--no-binary` for only crypto/psycopg with Dockerfile.dev split (#104)
- **PRs**: 7 in 4 days (#98-#104)

### Collector architecture
- **Files**: metrics_collection.md, task_system.md
- **Evolution**: individual collector files per type (#79) -> legacy system removed, tasks reorganized into subdirectory (#92) -> consolidated into two generic functions (collect_hourly/collect_snapshot) with registry-based design (#109) -> daily collector type added for service DB queries (#165) -> post_collect_hook added to registry for dashboard sync (#210)
- **PRs**: 4+

### Dashboard collection scheduling
- **Files**: metrics_collection.md, task_system.md
- **Evolution**: standalone 6-hourly `daily_dashboard_collection` cron task (initial) -> merged into hourly collector pipeline via `post_collect_hook` on unified_jobs (#210), with initial backfill via cursor-paginated batches
- **PRs**: 2+

### Secrets management
- **Files**: settings_and_configuration.md
- **Evolution**: SEGMENT_WRITE_KEY from config -> from file with base64 -> from file without base64

### CodeQL
- **Files**: ci_cd.md
- **Evolution**: created then immediately reverted (wrong file contents, 5 minutes apart)

### Task API permission evolution
- **Files**: api_design.md, settings_and_configuration.md
- **Evolution**: AllowAny (initial, marked "temporary") -> DeveloperModeRequired checking DEVELOPER_MODE_ENABLED (#65) -> DeveloperModeRequired checking settings.MODE (#87) -> IsSystemAdminOrAuditor from DAB RBAC (#253)
- **PRs**: 4 (#65, #87, #253 plus initial)

### Dashboard app lifecycle
- **Files**: architecture.md, settings_and_configuration.md
- **Evolution**: monolithic inline HTML template in apps/dashboard/ (#14) -> enhanced to ~1400 lines (#25) -> URL moved from /dashboard/ to /api/dashboard/ (#184) -> embedded app deleted, production UI externalized (#253) -> standalone tools/tasks/dashboard.html added for dev use with Basic auth and inline CORS middleware (#254)
- **PRs**: 5 (#14, #25, #184, #253, #254)

### DRF Spectacular / OpenAPI
- **Files**: api_design.md, dependencies_and_packaging.md
- **Evolution**: added initially -> removed during DAB retrofit (#73, API docs to be handled by `ansible_base.api_documentation`) -> re-added with comprehensive OpenAPI documentation and auto-sync workflow (#196)
- **PRs**: 3

### Segment send scheduling and jitter
- **Files**: metrics_collection.md
- **Evolution**: fixed cron at 3:30 AM -> jittered one-time task with deterministic seed (#183) -> `use_bulk` removed (didn't work) (#195) -> jitter changed from deterministic to truly random (timing fingerprint concern) (#201)
- **PRs**: ~3-4

### Task timeout consolidation
- **Files**: task_system.md
- **Evolution**: per-task `timeout_seconds` DB field + hardcoded `STUCK_TASK_TIMEOUT_SECONDS` constant + CLI `--timeout` flag -> stuck detection added (#211) -> exponential backoff (#220) -> all consolidated into single TASK_TIMEOUT Dynaconf setting (#218/#228)
- **PRs**: ~4

### Task system resilience (connection, retry, locks)
- **Files**: task_system.md, bugs_and_pitfalls.md, database_and_migrations.md
- **Evolution**: stale psycopg3 connections not detected by `ensure_connection()` -- SELECT 1 probe added (#273) -> retry base delay changed from 10 to 8 min (coprime with 5-min task spacing) to avoid retry collisions, SEGMENT_MAX_ATTEMPTS removed from local-only task (#276) -> stale advisory locks from dead workers cleaned up via `pg_terminate_backend()` in scheduler periodic sync (#277) -> argparse None vs empty string for task description fixed (#278)
- **PRs**: 4 (#273, #276, #277, #278)

### Retry timing, location, and coprime intervals
- **Files**: task_system.md, bugs_and_pitfalls.md
- **Evolution**: fixed 10-min retry delay with 3 max attempts (#167) -> exponential backoff with 7 max attempts for Segment tasks (#220) -> base delay changed from 600s to 480s (coprime with 5-min spacing), SEGMENT_MAX_ATTEMPTS removed from wrong task (#276) -> Renovate cron wildcard minute fix (#281, later reverted in #341 -- Renovate requires wildcard minutes, not standard cron) -> retry moved from execution-time to scheduler periodic sync, Task.retry() redesigned as pure atomic state writer, submit_task_to_dispatcher simplified to raise on failure (#355)
- **PRs**: 5 (#167, #220, #276, #281, #355)

### Framework alignment (platform-service-framework compliance)
- **Files**: architecture.md, ci_cd.md, settings_and_configuration.md
- **Evolution**: framework-validation workflow added (#84) -> removed, too strict for custom service (#88) -> settings restructured to single `metrics_service/settings.py` with `apps/settings/` layer (#77) -> framework validation re-added using PSF's own `validate` command, all project-specific code moved out of protected files to Dynaconf post-hooks (#267)
- **PRs**: 4 (#77, #84, #88, #267)

## metrics-utility arcs

### Schema validation and schema packaging
- **Files**: ci_cd.md, bugs_and_pitfalls.md, metrics_utility.md, testing.md
- **Evolution**: JSON schema validation tests added with CI workflow (#428) -> schema-review CI enhanced with stricter checks (#434) -> schema-review workflow iterated through three rounds of fixes (#436, #438, #440) -> schemas moved from standalone files into the pip-installable package (#444) -> validator `SCHEMAS_DIR` path broken by the move, fixed (#447)
- **PRs**: 7 (#428, #434, #436, #438, #440, #444, #447)

### psycopg2/psycopg3 compatibility
- **Files**: dependencies_and_packaging.md, architecture.md
- **Evolution**: duck-typing `hasattr(cursor, 'copy_expert')` for COPY operations (#7) -> `UndefinedTable` exception mismatch between psycopg versions (#261) -> library `copy_table` switched to `cursor.fetchall()` + DataFrame return, dropping psycopg2 support entirely (#327)
- **PRs**: 3 (#7, #261, #327)

### Missing `__init__.py` (recurring bug)
- **Files**: bugs_and_pitfalls.md
- **Evolution**: forgot in #9 -> fixed in #10 -> forgot again in #24 -> fixed in #25 -> forgot again in #215/#239/#250 -> fixed in #278
- **PRs**: ~6

### insights-analytics-collector vendoring and cleanup
- **Files**: architecture.md, dependencies_and_packaging.md
- **Evolution**: external dependency (#5) -> vendored into `metrics_utility/base/` (#92) -> unused extension points removed (#111) -> dead code removed from base Collector (#265)
- **PRs**: 4 (#5, #92, #111, #265)

### Dataframe engines: monolith to library
- **Files**: architecture.md
- **Evolution**: monolithic `DataframeSummarizedByOrgAndHost` -> Base class extracted, CCSPv2 engine added (#17) -> deduplication extracted as separate pipeline step (#162) -> dataframes moved to library with loading/transform split (#237)
- **PRs**: 3 (#17, #162, #237)

### Python version bounds
- **Files**: dependencies_and_packaging.md
- **Evolution**: `>=3.12` -> `>=3.11` (match AWX, #45) -> `>=3.11, <3.13` (upper bound, #49) -> `>=3.11` (removed upper bound for 3.13, #96) -> `>=3.12` (for PyPI library, #271)
- **PRs**: 4 (#45, #49, #96, #271)

### SonarCloud CI integration
- **Files**: ci_cd.md
- **Evolution**: added with `pull_request_target` (#89/#93) -> PR head checkout fix (#106) -> dual push/PR conditional scan (#108/#109) -> per-PR dropped, reverted to `pull_request` (#318) -> PwnRequest remediation via `workflow_run` split (#321)
- **PRs**: 6 (#89, #93, #106, #108, #318, #321)

### Indirect nodes collector naming and error handling
- **Files**: settings_and_configuration.md, metrics_collection.md
- **Evolution**: `indirect_nodes` with `INCLUDE_INDIRECT` module constant (#75) -> renamed to `main_indirectmanagednodeaudit`, switched to `get_optional_collectors()` (#78) -> `ProgrammingError` catch for AAP 2.4 (#172) -> `UndefinedTable` also caught for psycopg3 (#261)
- **PRs**: 4 (#75, #78, #172, #261)

### `get_optional_collectors()` location
- **Files**: settings_and_configuration.md
- **Evolution**: local to `collectors.py` (original) -> moved to `metric_utils.py` (#75) -> moved back to `collectors.py` (#153) -> moved to `base/utils.py` (#185)
- **PRs**: 3 (#75, #153, #185)

### Tarball naming and filtering
- **Files**: architecture.md
- **Evolution**: anonymous tarball names -> collection name added to filename (#226) -> extractors filter tarballs and files by collection name (#227) -> build report only extracts needed CSVs (#86/#91)
- **PRs**: 3-4 (#86, #91, #226, #227)

### Advisory lock saga
- **Files**: architecture.md, dependencies_and_packaging.md, bugs_and_pitfalls.md
- **Evolution**: AWX import -> `find_spec` detection for AWX vs ansible_base (#51) -> `find_spec` broke, switched to try/except (#94) -> custom `library/lock.py` with raw PostgreSQL hashtext (#259) -> django-ansible-base dep removed (#395)
- **PRs**: 4 (#51, #94, #259, #395)

### Date parser unification
- **Files**: architecture.md, bugs_and_pitfalls.md
- **Evolution**: bare numbers accepted silently (#114 fix) -> separate parsers for gather vs build (#128) -> `_handle_datelike` extracted (#156) -> three parsers merged into one `parse_date_param` (#157)
- **PRs**: 4 (#114, #128, #156, #157)

### `self.help` shadowing Django's BaseCommand.help
- **Files**: bugs_and_pitfalls.md
- **Evolution**: refactored help text into `self.help = {...}` dict (#128) -> shadowed Django's help string, caused dict repr in `--help` -> fixed by renaming to `self.help_texts` (#141) -> moved from constructor to class-level attributes (#156)
- **PRs**: 3 (#128, #141, #156)

### Env validation ordering
- **Files**: bugs_and_pitfalls.md, settings_and_configuration.md
- **Evolution**: validation placed in `add_arguments()` (#137) -> broke `--help`, moved to `handle()` (#141) -> placed before `init_logging`, errors invisible (#141) -> moved after `init_logging` (#146)
- **PRs**: 3 (#137, #141, #146)

### Gather `--until` inclusive vs exclusive
- **Files**: bugs_and_pitfalls.md
- **Evolution**: exclusive upper bound (original) -> changed to inclusive end-of-day (#175) -> reverted back to exclusive because it broke `since == until` and conflicted with daily_slicing (#192)
- **PRs**: 2 (#175, #192)

### `METRICS_UTILITY_OPTIONAL_COLLECTORS` empty string handling
- **Files**: settings_and_configuration.md, bugs_and_pitfalls.md
- **Evolution**: whitespace caused validation failure (#178) -> added `''` to VALID_COLLECTORS as workaround (#178) -> replaced with `filter(bool, ...)` for clean parsing (#263)
- **PRs**: 2 (#178, #263)

### MAX_GATHER_PERIOD: constant to configurable
- **Files**: metrics_collection.md, settings_and_configuration.md
- **Evolution**: hardcoded `timedelta(weeks=4)` in 3 places -> centralized as `MAX_GATHER_PERIOD_WEEKS = 4` class constant (#168) -> replaced with `METRICS_UTILITY_MAX_GATHER_PERIOD_DAYS` env var defaulting to 28 (#181)
- **PRs**: 2 (#168, #181)

### Anonymization strategy evolution
- **Files**: architecture.md, metrics_collection.md, metrics_utility.md
- **Evolution**: SHA-512 hashing of unknown values (#239) -> SHA-256 for shorter hashes (#250) -> "Unknown" replaced with literal string instead of hash (#319) -> "Unknown" renamed to "Custom" (#343) -> salt parameter and hash function removed entirely (#399)
- **PRs**: 5 (#239, #250, #319, #343, #399)

### Anonymized rollup data structure evolution
- **Files**: architecture.md, metrics_utility.md
- **Evolution**: nested JSON structure (#239) -> flattened with `flatten_json_report()` (#250) -> flat DataFrame changed to dict with totals (#288) -> JSON round-trip verification after each batch (#331) -> field names changed from DB columns to descriptive names (#343)
- **PRs**: 5 (#239, #250, #288, #331, #343)

### `anonymize_rollups()` signature evolution
- **Files**: metrics_utility.md
- **Evolution**: basic positional params (#239) -> `feature_flags_rollup` added as positional (#357) -> changed to keyword-only (#362) -> `salt` removed (#399) -> `task_executions_rollup` added as keyword-only (#399) -> `**kwargs` added for forwards compatibility (#513)
- **PRs**: 5 (#357, #362, #399, #513, plus original #239)

### Library/CLI collector split
- **Files**: architecture.md, metrics_utility.md
- **Evolution**: all collectors in CLI `collectors.py` (original) -> library collectors with env-var-free interfaces (#248) -> CLI collectors replaced with thin wrappers delegating to library (#339) -> `copy_table` returns DataFrame instead of files (#327)
- **PRs**: 3 (#248, #327, #339)

### StorageSegment chunking and delivery reliability
- **Files**: architecture.md, bugs_and_pitfalls.md
- **Evolution**: basic chunking at 32KB limit (#249) -> metadata overhead and dict-vs-list handling fixed, limit reduced to 24KB (#281) -> `use_bulk` removed, trial-serialization sizing (#372) -> `sync_mode=True` as only reliable delivery method after silent event loss (#383)
- **PRs**: 4 (#249, #281, #372, #383)

### AWX imports removal from collectors
- **Files**: architecture.md, metrics_collection.md
- **Evolution**: collectors imported AWX Python modules directly (original) -> replaced with direct SQL against `conf_setting` (#242) -> `config_django` fallback collector added for fields only available via Django settings (#354) -> controller version simplified to `main_instance` only (#257)
- **PRs**: 3-4 (#242, #245, #257, #354)

### Pandas version evolution and NaN compatibility
- **Files**: dependencies_and_packaging.md, bugs_and_pitfalls.md
- **Evolution**: `pandas==2.2.1` exact pin to match AWX (#45) -> relaxed to `>=2.2.3` for Python 3.13 wheels (#96) -> upgraded to `~=3.0` with four breaking-change fixes for NaN-as-float-in-string-columns, plus openpyxl bumped to `~=3.1.5` (#431)
- **PRs**: 3 (#45, #96, #431)

### Cross-repo CI testing
- **Files**: ci_cd.md
- **Evolution**: metrics-utility and metrics-service tested independently in their own CI (original) -> metrics-utility CI now also clones metrics-service@devel and runs its tests with the local metrics-utility checkout installed as editable (#427)
- **PRs**: 1 (#427), likely to be extended

### Docker Compose port flip-flop
- **Files**: bugs_and_pitfalls.md
- **Evolution**: 5432 (original) -> changed to 5433 to avoid local conflicts (#274) -> reverted 15 minutes later because it broke CI (#276)
- **PRs**: 2 (#274, #276)

### pyasn1 pin add/fix/revert cycle
- **Files**: dependencies_and_packaging.md
- **Evolution**: `pyasn1>=0.6.4` added (#368) -> corrected to `~=0.6.4` (#369) -> `~=` reverted to `>=` (#372) -> dependency line removed entirely (#373), all on same day
- **PRs**: 4 (#368, #369, #372, #373)

### Indirect managed nodes: prototype to feature-gated group to collection-grouped daily
- **Files**: architecture.md, metrics_collection.md, task_system.md, settings_and_configuration.md, metrics_utility.md, bugs_and_pitfalls.md
- **Evolution**: Collector added to METRICS_COLLECTION_GROUP (#274) -> integrated into daily anonymization pipeline (#296) -> extracted into own INDIRECT_NODE_COLLECTION_GROUP with INDIRECT_NODE_COLLECTION feature flag, default off (#301) -> fix: task function was never registered, silently never ran (#315) -> m-u rollup added with host_remote_id dedup (#446, #453, #457) -> moved hourly->snapshot on service side (#331) -> briefly converted to snapshot/until_slicing on library side (m-u #464) -> converted to daily slicing by job.finished with collection grouping, version bumped to 2.0 (m-u #475) -> moved snapshot->daily on service side with per-collector DB routing (#332). The rollup now groups by (org, collection_name) using events JSON parsing, and base() strips PII by removing host_names and org_name. -> dead code removal: by_organizations and by_collections computed in prepare()/merge() but never read by base() (#479) -> module-level breakdown added as parallel module_groups structure (#482) -> collection_name/module_name renamed to collection/module for Segment compatibility (#484)
- **PRs**: 14+ (m-s #274, #296, #301, #315, #331, #332; m-u #446, #453, #457, #464, #475, #479, #482, #484)

### Events collector: disabled, re-enabled with limits
- **Files**: metrics_collection.md, settings_and_configuration.md
- **Evolution**: main_jobevent_service disabled by default (enabled=False) for performance -> re-enabled (enabled=True) with JOBEVENT_ROW_LIMIT=1M (#295) -> row limit reduced to 200K, JOBEVENT_JOB_LIMIT=1K added (#300)
- **PRs**: 2 (#295, #300)

### Dashboard collection feature flag lifecycle
- **Files**: settings_and_configuration.md, architecture.md, metrics_service.md
- **Evolution**: Default-off opt-in with YAML-based AAPFlag seeding (#168, #184) -> five-tier lookup formalized (#189, #191, #199) -> promoted to default-on, YAML seeding machinery deleted (-560 lines) (#275)
- **PRs**: 5+ (#168, #184, #189, #191, #199, #275)

### Dashboard retention window derivation
- **Files**: settings_and_configuration.md, metrics_service.md
- **Evolution**: static `INITIAL_BACKFILL_DAYS` setting (#319 initial) -> dynamic `get_retention_days()` querying Controller's active cleanup_jobs schedules (#319) -> gated behind `DASHBOARD_COLLECTION['USE_CONTROLLER_RETENTION']` (default False), hardcoded to 90-day `DEFAULT_RETENTION_DAYS` until opt-in (#340)
- **PRs**: 2 (#319, #340)

### Renovate cron schedule
- **Files**: ci_cd.md, bugs_and_pitfalls.md
- **Evolution**: wildcard minutes `"* */12 * * 1-5"` (runs every minute, #271) -> fixed to `"0 */12 * * 1-5"` with PR check preventing wildcards (#281) -> reverted: Renovate requires wildcard minutes, PR check flipped to enforce wildcards (#341)
- **PRs**: 3 (#271, #281, #341)

### CI fork handling: secrets checks
- **Files**: ci_cd.md, bugs_and_pitfalls.md
- **Evolution**: No fork handling -> secrets context used directly in if: conditions (#303, broke immediately) -> fixed via job-level env var bridge pattern (#305)
- **PRs**: 2 (#303, #305)

### Jira PR linking action: rapid iterative fixes
- **Files**: ci_cd.md
- **Evolution**: Initial action with BOT_GITHUB_TOKEN + pull_request trigger (#304) -> fix: use github.token instead of BOT_GITHUB_TOKEN (#308) -> fix: pull_request_target + marker-based comment management + trailing whitespace (#309) -> fix: remove backticks from ticket name in comment (#310) -> rewrite from curl/API v2 (overwriting) to Python/API v3 with ADF-aware append (m-s #347) -> ported to m-u (#494), now identical between both repos
- **PRs**: 6 (m-u #304, #308, #309, #310, m-s #347, m-u #494)

### Segment payload field naming: "name" keyword filtering
- **Files**: metrics_utility.md, bugs_and_pitfalls.md, testing.md
- **Evolution**: Fields named `collection_name` and `module_name` used in indirect nodes rollup (#475, #482) and events modules rollup (various) -> discovered Segment downstream destinations silently drop properties whose key contains "name" -> indirect nodes rollup renamed to `collection`/`module` (m-u #484) -> events modules rollup renamed to `collection`/`module` via `_normalize_stats_item()` helper (m-u #485). Rename applied at output time in `base()` so internal DataFrame column names are unchanged. -> metrics-service test mock updated to match renamed field (m-s #350)
- **PRs**: 3 (m-u #484, m-u #485, m-s #350) -- cross-repo rename cascade

### External service telemetry ingest POC: pushed and reverted
- **Files**: bugs_and_pitfalls.md, architecture.md
- **Evolution**: Full `service_ingest` Django app pushed directly to devel without PR (3fe5d45) -> immediate fix for ServiceUser/CommonModel runtime issues (eccada7) -> CI workflow fix (#347) accidentally included service_ingest-related changes -> entire app reverted because it bypassed PR review process (#349). The jira-pr-link workflow fix from #347 was carefully preserved during the revert.
- **PRs**: 1 (#349 revert) -- the original commits had no PR numbers, which was the problem

### AWX schema update workflow: CI hardening
- **Files**: ci_cd.md
- **Evolution**: Initial extraction script and weekly cron workflow (#461) -> backports-zstd filtered on Python 3.14+ (#487) -> pg_dump auth fix, empty-dump validation, Slack notifications, PR creation via peter-evans + gh cli fallback (#497) -> PR creation dropped (permissions issues), branch push + Slack compare link, webhook variable fixed (#499)
- **PRs**: 4 (#461, #487, #497, #499)

### Events rollup counting strategy
- **Files**: metrics_utility.md, architecture.md, performance.md
- **Evolution**: inferred task outcomes (success, failed with retries, skipped, ignored) via event sequence analysis (original) -> direct 1-to-1 event type counters (runner_on_ok_total, runner_on_failed_total, etc.) with no task-outcome inference (#480). Old task-level columns removed: task_ok_total, task_ok_with_retries_total, task_failed_total, task_unreachable_total, task_skipped_total, task_failed_and_ignored_total. New columns added: runner_on_async_ok_total, runner_on_async_failed_total, runner_item_on_ok_total, runner_item_on_failed_total, runner_retry_total, ignore_errors_total, event_data_size_total. unique_hosts_total removed for performance. playbook_on_stats removed (high volume, redundant).
- **PRs**: 1 (#480) -- major reshape in single PR

### NULL host_id in job_host_summary: fix and immediate revert
- **Files**: bugs_and_pitfalls.md, metrics_collection.md
- **Evolution**: NULL host_id causes silent JOIN failure on SaaS (#532) -> name-based fallback JOIN added -> reverted 2 days later (#533), likely due to many-to-many match risk or performance concerns
- **PRs**: 2 (#532, #533)

### host_metric SQL parameterization
- **Files**: metrics_collection.md, bugs_and_pitfalls.md
- **Evolution**: f-string SQL interpolation with CONCAT-based keyset pagination (original) -> parameterized queries with multi-column keyset comparison, method returns (query, params) tuple (#530)
- **PRs**: 1 (#530) -- security hardening requested by controller team (AAP-85766)

### S3-compatible dev/CI storage
- **Files**: docker_and_deployment.md
- **Evolution**: MinIO with separate mc init container for bucket/user/key creation (original) -> SeaweedFS with zero-setup env-var-only config (#488)
- **PRs**: 1 (#488)

### AWX label dedup: fix, revert, replace
- **Files**: metrics_service.md, bugs_and_pitfalls.md
- **Evolution**: Labels showed duplicates because AWX labels are org-scoped (unique by name+org). Fix #387 used `GROUP BY name / MIN(id)` to collapse "duplicates" -> reverted next day in #390 because it destroyed legitimate per-org labels -> replacement fix #389 joins main_organization and disambiguates by appending org name only to labels whose name occurs more than once, preserving all distinct labels
- **PRs**: 3 (#387, #390, #389)

### Dashboard data consistency: card counts and workflow child exclusion
- **Files**: metrics_service.md, bugs_and_pitfalls.md, metrics_collection.md
- **Evolution**: Card counts (total/successful/failed) disagreed with job listing because they were computed from `_build_aggregated_queryset()` which filters out jobs without template_metadata -> fixed in #386 by computing card counts directly on filtered_qs. Separately, workflow child jobs (`launch_type='workflow'`) had NULL launched_by_id, inflating card counts without appearing in Top 5 Users -> batch collector fixed in m-u #525, hourly sync hook fixed independently in m-s #388 by extending the `isin` filter. Both fixes part of the same AAP-74848/AAP-85129 cluster.
- **PRs**: 2 m-s (#386, #388) + 1 m-u (#525)

### Dependabot grouping (cross-repo)
- **Files**: ci_cd.md
- **Evolution**: Individual dependabot PRs per dependency bump (original) -> m-u added `groups: monthly-batch: patterns: ['*']` for github-actions, uv, gomod, docker ecosystems (#512) -> m-s added same pattern for github-actions and uv ecosystems (#376)
- **PRs**: 2 (m-u #512, m-s #376)

### sync-openapi-specs workflow (three-iteration fix)
- **Files**: ci_cd.md
- **Evolution**: the cross-repo OpenAPI spec-sync workflow added in #196 never ran. #394 made the generator work headless (correct `metrics_service.settings` module, `METRICS_SERVICE_` Dynaconf env vars, per-db SQLite so no Postgres, flat `metrics.json` output, versioned-branch targeting) and split it into generate + sync jobs -> #396 aligned it to the eng handbook drift-detection standard (artifact `openapi-schema`, `component-spec/` path, `diff -q` instead of `git diff`, `OPENAPI_SPEC_SYNC_TOKEN` secret, short-SHA branches, handbook PR template) and fixed a critical shell-injection by routing all `github.*` context through step `env` vars -> #397 added GPG signing with the shared `aap-api-bot` key for verified downstream commits (matching the Controller pattern).
- **PRs**: 3 (#394, #396, #397), following broken #196
