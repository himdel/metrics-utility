# Testing

> Default repo: metrics-service

## Learnings

### Test fixtures configured Django settings via conftest.py
- **Commits**: e64f482
- **What happened**: `tests/conftest.py` was updated to configure Django settings in test fixtures, ensuring `DJANGO_SETTINGS_MODULE` is set before any Django imports happen.
- **Insight**: With split settings, tests need to explicitly set which settings module to use. This was later handled by `pyproject.toml`'s `[tool.pytest.ini_options]` with `DJANGO_SETTINGS_MODULE`.

### Unused imports accumulated rapidly and needed cleanup
- **Commits**: d828d60
- **What happened**: A dedicated commit removed unused imports from 7 test files in one pass: `json`, `TestCase`, `patch`, `Mock`, `ValidationError`, multiple model imports, and command class imports. These had accumulated over just a few days of development.
- **Insight**: Rapid development with copy-paste between test files leads to import bloat. Running ruff's `F401` rule (unused imports) as part of CI catches this automatically -- which is exactly what happened when ruff was later added to CI.

### Test coverage setup included both XML and HTML reports
- **Commits**: ee93077
- **What happened**: pytest was configured to generate both XML coverage reports (for SonarCloud upload) and the default terminal output. The CI runs `uv run pytest -s -v --cov=. --cov-report=xml`.
- **Insight**: Using `--cov=.` (coverage of everything) in CI means third-party code in `.venv` could be measured too unless properly excluded. The later configuration switched to explicit module coverage (`--cov=apps --cov=metrics_service`).

### Massive test expansion in the task refactor commit
- **Commits**: c6947ce (#14)
- **What happened**: The big refactor commit added 15+ new test files in one PR, including `test_access_control_mixin.py`, `test_api_views_extended.py`, `test_base_views_comprehensive.py`, `test_core_permissions.py`, `test_core_utils.py`, `test_dashboard_views.py`, `test_final_coverage.py`, `test_init_service_id_command.py`, `test_metrics_service_command.py`, `test_run_dispatcherd_comprehensive.py`, `test_tasks_api_comprehensive.py`, `test_tasks_views_extended.py`, and `test_urls_basic.py`. Some empty test files were also committed (`test_models_extended.py`, `test_task_management_extended.py`, `test_tasks_utils.py`).
- **Insight**: Committing empty test files suggests a "placeholder" approach to test planning, but it also creates noise. The test coverage went from minimal to 35%+ in a single commit, which makes reviewing test quality difficult. Several tests were later commented out or removed in follow-up commits within the same PR.

### Tests reorganized into subdirectories by domain
- **Commits**: edb4626 (#25)
- **What happened**: Tests under `tests/unit/` were moved into subdirectories: `tests/unit/api/`, `tests/unit/core/`, `tests/unit/dashboard/`, `tests/unit/general/`, and `tests/unit/tasks/`. Each subdirectory got an `__init__.py` file. Existing test files were moved without renaming (e.g., `test_api_views.py` moved from `tests/unit/` to `tests/unit/api/`). Many new test files were added for the new service layer and task system components.
- **Insight**: The subdirectory organization mirrors the app structure, making it easy to find tests for a specific component. The 80% coverage target was achieved in this commit, with comprehensive tests for the new service layer classes.

### Some tests committed commented out
- **Commits**: c6947ce (#14)
- **What happened**: One of the squashed commit messages is literally "Commenting out tests." Some test classes and methods were wrapped in comments or skipped to get the CI passing, with the intention of fixing them later.
- **Insight**: Commenting out tests to get CI green is a red flag -- it hides real failures. Using `@pytest.mark.skip(reason="...")` is better because it's visible in test reports. The commented-out tests were partially restored in edb4626 (#25).

### Test database switched from SQLite in-memory to PostgreSQL
- **Commits**: c8e5f0d (#36)
- **What happened**: `metrics_service/settings/test.py` was rewritten to use PostgreSQL instead of SQLite in-memory (`:memory:`). The `DisableMigrations` class hack was removed, migrations now run normally against PostgreSQL, and `--reuse-db` was added to pytest default options. The test database name was changed from `test_metrics_service` to `metrics_service` in both the CI workflow and Django settings. The `TEST.NAME` is set to `None` to let Django auto-generate test database names.
- **Insight**: Running tests against SQLite was causing divergence from production behavior (e.g., different constraint handling, no LISTEN/NOTIFY). The switch to PostgreSQL with `--reuse-db` (pytest-django feature) minimizes the performance penalty by reusing the test database between runs. The `DisableMigrations` trick was needed for SQLite speed but is counterproductive with PostgreSQL since schema must match production.

### Test settings INSTALLED_APPS aligned with production
- **Commits**: c8e5f0d (#36)
- **What happened**: The test settings `INSTALLED_APPS` was updated to include `DAB_APPS` (which was previously missing) and added several third-party apps that the test config was missing (`rest_framework.authtoken`, `drf_spectacular`, `corsheaders`, `social_django`). This aligned the test installed apps with the production `defaults.py` config.
- **Insight**: Tests running with a different set of installed apps than production can pass even when production would fail (e.g., missing URL routes, missing middleware, missing model registrations). Aligning the test `INSTALLED_APPS` prevents this class of bugs.

### _create_task_safely pattern to suppress Django signals in tests
- **Commits**: a044bd7 (#54)
- **What happened**: Tests were refactored to use a `_create_task_safely()` helper method instead of `Task.objects.create()`. The helper creates a `Task` instance, sets `task._skip_signals = True`, then calls `task.save()`. This was applied across 5 test files (api, task_system, tasks_comprehensive, tasks_utils, tasks_views). Some tests also gained `@pytest.mark.django_db(transaction=True)` where actual DB interactions with signal-driven side effects were being tested.
- **Insight**: The `post_save` signal on the Task model (added in edb4626 #25) automatically routes tasks to dispatcherd when created. In tests, this causes failures because dispatcherd isn't running. The `_skip_signals` attribute is a convention where the signal handler checks for it and skips processing. The pattern is duplicated as a method on each test class rather than being a shared fixture/utility, which is pragmatic but introduces repetition.

### Redundant django.setup() removed from test files -- conftest handles it
- **Commits**: 78fdf9f (#61)
- **What happened**: `tests/test_common.py` had a `setup_django_for_tests()` function that manually configured Django settings (with `settings.configure()`, `sys.path.insert`, and `django.setup()`). Both `test_coverage.py` and `test_simple.py` imported and called this function at module level. Since `conftest.py` already handles Django setup (and pytest-django sets `DJANGO_SETTINGS_MODULE`), these manual setups were redundant. The function was deleted and the import/calls removed from both test files.
- **Insight**: Having redundant Django setup code is a maintenance burden and can cause subtle issues if the manual `settings.configure()` conflicts with the pytest-django setup. When using pytest-django with `DJANGO_SETTINGS_MODULE` in `pyproject.toml`, no test file should ever call `settings.configure()` or `django.setup()` manually. The conftest.py is the single source of truth for test environment setup.

### METRICS_UTILITY_AVAILABLE patching pattern for testing without optional dependency
- **Commits**: 7b39f53 (#56)
- **What happened**: Integration tests for collector tasks patch `METRICS_UTILITY_AVAILABLE` (a module-level boolean in `tasks_collector.py`) to control whether the metrics-utility library appears available. Combined with the `None` fallback attributes for collector objects, this allows tests to exercise both the "library available" and "library not available" code paths without actually installing the dependency.
- **Insight**: For optional dependencies that may not be present in CI, defining a module-level availability flag and providing `None` fallbacks allows comprehensive testing. The flag can be patched per-test to exercise error handling paths.

### Developer mode must be enabled in test settings
- **Commits**: dbf6fb1 (#65)
- **What happened**: When `DEVELOPER_MODE_ENABLED` was added (defaulting to `False`) to gate the tasks API and dashboard, `DEVELOPER_MODE_ENABLED = True` was added to `test.py` settings. Without this, all task API tests would get 403 Forbidden responses and fail.
- **Insight**: Any new feature gate or permission check that defaults to restrictive must be explicitly enabled in test settings. Forgetting this causes mass test failures that are confusing because the tests "used to work." Adding a dedicated test for the disabled case (as was done with `test_developer_mode_permissions.py`) verifies the gate works without breaking the rest of the suite.

### Tests use override_settings(MODE="development") for dev-gated endpoints
- **Commits**: 7db9971 (#87)
- **What happened**: When `DEVELOPER_MODE_ENABLED` was replaced by `settings.MODE == "development"` for gating the tasks API and dashboard, tests switched from `DEVELOPER_MODE_ENABLED = True` in test settings to `@override_settings(MODE="development")` on individual test methods. This was necessary because `METRICS_SERVICE_MODE=test` is set in CI, and tests shouldn't globally override MODE.
- **Insight**: Using `@override_settings` per-test is more precise than setting a global test setting. It documents which tests depend on development mode and doesn't affect tests that should work in non-development mode. The test file `test_developer_mode_permissions.py` was renamed to `test_development_mode_permissions.py` to match the new terminology.

### Large test reorganization for metrics collection
- **Commits**: 3a58426 (#79)
- **What happened**: A significant test reorganization accompanied the metrics collection feature: old test files were renamed or replaced (e.g., `test_models_edge_cases.py` -> `test_models.py`), deprecated test files were removed (e.g., `test_tasks_collector_complete_coverage.py`, `test_tasks_comprehensive.py`, `test_task_retry_bug.py`), and new comprehensive test files were added (`test_tasks_collector_advanced.py`, `test_tasks_collector_full_coverage.py`, `test_tasks_system.py`, `test_tasks_api_views.py`, `test_v1_base_serializers.py`, `test_v1_urls.py`, `test_mixins.py`). New conftest fixtures were added for task creation and scheduler mocking.
- **Insight**: The PR's 28 squashed commits show that tests were written iteratively during development, with multiple rounds of "fix tests" commits. This pattern of writing tests alongside feature code in a large PR makes it hard to review test quality. The conftest fixtures for task creation centralize what was previously duplicated across test classes.

### Massive test cleanup removed 2000+ lines of obsolete tests
- **Commits**: e137d39 (#92)
- **What happened**: Over 2000 lines of test code were removed for deleted functions, models, and classes: tests for CronManager, ServiceConfig, SystemInitializer, TaskManager services; tests for TaskDependency, TaskChain, TaskChainMembership models; tests for deleted utility functions (get_count_safely, trigger_dependent_tasks, schedule_next_occurrence); tests for deleted mixins (TimestampMixin, mark_started, mark_completed); tests for deleted task functions (collect_single_collector, full_process, etc.). Test files for removed service classes were deleted entirely. The test suite went from 842 tests with import errors to 794 passing tests with 0 skips. Also fixed multiple bugs found during cleanup: typo in Task.retry() (`cronjob_expression` -> `cron_expression`), router registration order in tasks/v1/urls.py, and `test_cron_scheduler.py` merged with `test_unified_scheduler.py` (36+17 tests -> 58 deduplicated).
- **Insight**: This demonstrates the cost of not cleaning up tests alongside code changes. The obsolete tests had accumulated over multiple PRs, creating import errors and silent failures. The router registration order bug (TaskViewSet's catch-all pattern matching `/tasks/executions/` as a detail view with pk='executions') was discovered by un-skipping tests that had been skipped to work around it.

## Superseded / Semi-Obsolete

### Tests in tests/unit/ alongside tests/test_*.py
- The early test structure had both `tests/unit/` subdirectory tests and top-level `tests/test_*.py` files. In edb4626 (#25), tests were reorganized into `tests/unit/{api,core,dashboard,general,tasks}/` subdirectories.

### SQLite in-memory test database
- The `"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"` test config and the `DisableMigrations` class were removed in c8e5f0d (#36). Tests now use PostgreSQL with `--reuse-db`.

### _create_task_safely pattern to suppress signals
- The `_skip_signals` workaround from a044bd7 (#54) is no longer needed after signals were removed in 85d2cbb (#57). Tests now use plain `Task.objects.create()`.

### Manual setup_django_for_tests() in test files
- Removed in 78fdf9f (#61). The conftest.py and pytest-django handle Django setup; no test file should call `django.setup()` manually.

### DEVELOPER_MODE_ENABLED = True in test settings
- Replaced in 7db9971 (#87) by per-test `@override_settings(MODE="development")`. Tests that need dashboard/task API access explicitly opt in rather than globally setting a flag.
