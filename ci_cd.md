# CI/CD

### Initial CI: super-linter with many validators disabled
- **Repo**: ansible/metrics-utility
- **Commits**: fe07c0e (#21)
- **What happened**: The first CI workflow added GitHub's super-linter (v4) for static analysis, but disabled many validators: `VALIDATE_GITHUB_ACTIONS`, `VALIDATE_MARKDOWN`, `VALIDATE_PYTHON_MYPY`, `VALIDATE_PYTHON_FLAKE8`, `VALIDATE_NATURAL_LANGUAGE`. A pytest step was added but commented out (`# pytest -s -v tests/`). The workflow also uses jscpd for copy-paste detection with a 5% threshold.
- **Insight**: The initial CI was scaffolding -- disabled validators and commented-out tests indicate the codebase was not yet lint-clean, but the workflow was set up early for incremental adoption.

### Super-linter DEFAULT_BRANCH changed from main to devel, VALIDATE_ALL_CODEBASE set to false
- **Repo**: ansible/metrics-utility
- **Commits**: 6163cae (#38)
- **What happened**: `DEFAULT_BRANCH` was changed from `"main"` to `"devel"` in the super-linter config to match the actual default branch. `VALIDATE_ALL_CODEBASE` was hardcoded to `false` (previously it used `${{ inputs.validate-all }}`), so the linter only checks changed files in PRs rather than the entire codebase.
- **Insight**: The repo's default branch is `devel`, not `main` -- the super-linter must be told this so it only diffs against the correct base. Validating only changed files (not the full codebase) avoids CI failures from pre-existing lint issues in untouched code.

### CI migrated from super-linter to uv+ruff, jscpd removed in favor of SonarCloud
- **Repo**: ansible/metrics-utility
- **Commits**: 243428e (#49), 599fb17 (#59)
- **What happened**: The super-linter (v4) based CI and the `.jscpd.json` copy-paste detection config were removed. The static analysis workflow was replaced with `astral-sh/setup-uv` + `uvx ruff check --output-format=github .`, which provides inline GitHub annotations. SonarCloud was added as a separate workflow for code quality and duplication analysis (`sonar-project.properties` configured with `sonar.cpd.exclusions=**/migrations/*.py`). The Python version was also set to use `python-version-file: "pyproject.toml"` instead of hardcoding.
- **Insight**: Replacing super-linter with ruff eliminated the overhead of many disabled validators and gave faster, more focused Python linting; SonarCloud replaced jscpd for copy-paste detection with richer analysis.

### PR checks workflow validates uv.lock is up-to-date
- **Repo**: ansible/metrics-utility
- **Commits**: 3cfd69d (#46)
- **What happened**: A `pr-checks.yml` workflow was added that runs `uv sync` then `git diff --exit-code uv.lock` to fail the PR if `uv.lock` is out of date with `pyproject.toml`. This catches cases where a developer adds a dependency but forgets to commit the updated lock file.
- **Insight**: Lock file drift checks in CI prevent "works on my machine" dependency issues when `pyproject.toml` changes are not reflected in the committed lock file.

### Ruff configured with project-specific settings
- **Repo**: ansible/metrics-utility
- **Commits**: 0400c94 (#53)
- **What happened**: Ruff configuration in `pyproject.toml` was expanded beyond just `line-length = 150` to include: `indent-width = 4`, `quote-style = "single"`, `indent-style = "space"`, isort with `lines-between-types = 1` and `order-by-type = true`, and lint rules `E` (PEP 8 errors) and `W` (PEP 8 warnings). The `--fix` flag was also run, converting `.format()` calls to f-strings, removing empty parentheses on class definitions (`class Foo():` to `class Foo:`), and replacing `datetime.timezone.utc` with `datetime.UTC`.
- **Insight**: Adding ruff's auto-fix rules (`E`, `W`) and running `--fix` modernized the codebase in a single pass (f-strings, class syntax, UTC constant) while establishing consistent formatting conventions.

### Pytest CI workflow with native PostgreSQL and MinIO services
- **Repo**: ansible/metrics-utility
- **Commits**: e37e7c2 (#72), edfe31c (#74)
- **What happened**: A `pytest.yml` GitHub Actions workflow was added that provisions PostgreSQL and MinIO (S3-compatible) directly on the runner using native packages (not Docker services). PostgreSQL is initialized with the AWX schema dump from `tools/docker/latest.sql`. MinIO is installed via binary download, started as a background process, then configured with `mc` CLI to create buckets and users with static access keys. The workflow uses `timeout-minutes: 1` on wait steps to prevent hanging if services fail. PR #72 set up the infrastructure but left pytest commented out (`env # pytest`); PR #74 enabled it (`uv run pytest -s -v`). SonarCloud was also switched from `pull_request` to `pull_request_target` trigger to access repository secrets.
- **Insight**: Using native services (apt install postgres, download minio binary) instead of Docker service containers in GitHub Actions is simpler and faster for test infrastructure -- no DIND complications, and services share the runner's network directly.

### SonarCloud coverage reporting added with pytest-cov
- **Repo**: ansible/metrics-utility
- **Commits**: 511c1ac (#89), e5d8a7d (#93)
- **What happened**: Code coverage reporting was added to the CI pipeline. The pytest step was updated to use `--cov=. --cov-report=xml` to generate a `coverage.xml` file. A `SonarSource/sonarqube-scan-action@v4` step was added after pytest to upload coverage to SonarCloud. The `.sonarcloud.properties` file was renamed to `sonar-project.properties` (SonarCloud's default file name) and updated: `sonar.sources` was narrowed from `.` to `metrics_utility`, coverage exclusions were added for test files and `debug_utils.py`, and code duplication thresholds were raised (`minimumTokens=150`, `minimumLines=300`) to reduce noise. The workflow trigger had to be changed to `pull_request_target` so the SonarCloud token secret would be accessible. `pytest-cov>=6.0.0` was added as a dev dependency.
- **Insight**: SonarCloud requires `pull_request_target` (not `pull_request`) to access repository secrets for token authentication, but this introduces the checkout-ref pitfall fixed in #106.

### pull_request_target requires explicit PR head checkout
- **Repo**: ansible/metrics-utility
- **Commits**: aefaebb (#106)
- **What happened**: After switching the pytest workflow to `pull_request_target` trigger for SonarCloud access (#89/#93), tests were silently running against the base branch code instead of the PR's changes. The fix added `ref: ${{ github.event.pull_request.head.ref }}` and `repository: ${{ github.event.pull_request.head.repo.full_name }}` to the `actions/checkout@v4` step.
- **Insight**: `pull_request_target` is a common gotcha -- it runs in the context of the base branch for security, so the checkout step must explicitly specify the PR head ref to actually test the PR's code.

### SonarCloud on push (devel branch) requires different args than on PR
- **Repo**: ansible/metrics-utility
- **Commits**: 4cedc6c (#108), 412517a (#109)
- **What happened**: Running pytest on `push` to `devel` was added to collect baseline coverage for SonarCloud. However, SonarCloud's scan action requires different `-D` arguments for push vs PR: PRs need `-Dsonar.pullrequest.key`, `-Dsonar.pullrequest.branch`, `-Dsonar.pullrequest.base`, and `-Dsonar.pullrequest.provider`, while push scans must omit all of these. The solution uses two separate SonarCloud scan steps with `if: ${{ github.base_ref }}` (PR) and `if: ${{ ! github.base_ref }}` (push) conditions. The checkout step also needed conditional logic: on push, check out `github.ref` directly; on PR, check out the PR head ref. The pytest env vars (S3 credentials, DB host) were also moved from the SonarCloud step to the pytest step where they actually belong.
- **Insight**: SonarCloud treats push-to-default-branch as "new code" analysis and PR as "PR decoration" analysis -- they require different scan parameters, so a single workflow supporting both triggers needs two conditional scan steps.

### CI lint check enforces single logger module
- **Repo**: ansible/metrics-utility
- **Commits**: 35194fb (#173)
- **What happened**: A new `pr-checks.yml` step named "One logger to rule them all" was added that greps for `logging.getLogger` calls anywhere in `metrics_utility/` except `logger.py`. If found, the build fails with a message directing developers to use `from metrics_utility.logger import logger` instead. This enforces the unified logger pattern introduced alongside the `metrics_utility/logger.py` module.
- **Insight**: Architectural conventions (like "use the shared logger") that aren't enforced by CI will eventually be violated -- a simple `rgrep` check in PR validation is cheap insurance against logger sprawl.

### Per-PR SonarCloud coverage dropped, workflow reverted from pull_request_target to pull_request
- **Repo**: ansible/metrics-utility
- **Commits**: ea98ff2 (#318)
- **What happened**: The pytest CI workflow was changed back from `pull_request_target` to `pull_request` trigger, and the per-PR SonarCloud coverage reporting step was removed. Coverage reporting is now only done on push to `devel` (merge). The `pull_request_target` trigger had been needed solely for accessing the `CICD_ORG_SONAR_TOKEN_CICD_BOT` secret for SonarCloud PR decoration, but this came with the ongoing maintenance burden of explicit PR head ref checkout (#106) and security concerns. The push-to-devel step was retained for baseline coverage tracking.
- **Insight**: If the only reason for using `pull_request_target` is accessing a secret for a non-critical reporting tool (like SonarCloud PR decoration), it may be simpler to drop the PR-level reporting and only report on merge -- this avoids the `pull_request_target` checkout pitfalls and simplifies the workflow. **Supersedes** the `pull_request_target` approach from #89/#93/#106.

### PwnRequest vulnerability remediated: SonarCloud scan split into separate workflow_run job
- **Repo**: ansible/metrics-utility
- **Commits**: 5654222 (#321)
- **What happened**: The `pull_request` trigger in `pytest.yml` was found vulnerable to PwnRequest attacks -- a malicious PR could inject code via branch names interpolated into `${{ github.event.pull_request.head.ref }}` expressions. The fix separated the SonarCloud PR scan into a new `sonar_checks.yml` workflow triggered by `workflow_run` (runs after the pytest workflow completes). This workflow: (1) downloads the coverage report and PR number as artifacts from the pytest run, (2) validates the PR number with `grep -E '^[0-9]+$'` to prevent injection, (3) uses `gh pr checkout` to check out the PR code safely, and (4) single-quotes all GitHub context references in shell expressions to prevent script injection via branch names. The pytest workflow itself was simplified to a plain `actions/checkout` without conditional PR head ref logic.
- **Insight**: Using `workflow_run` to separate secret-requiring steps (SonarCloud) from untrusted PR code avoids the PwnRequest vulnerability class entirely -- the SonarCloud workflow runs in the context of the base branch with access to secrets, but only processes validated artifacts (coverage XML, numeric PR number) from the PR workflow. **Supersedes** the conditional PR/push checkout logic from #108/#109.

### CI SQL schema requires pre-created functions for read-only mode
- **Repo**: ansible/metrics-utility
- **Commits**: 7d148b9 (#300)
- **What happened**: The CI test database uses a read-only schema import (`latest.sql`), but metrics-utility creates custom PostgreSQL functions (`metrics_utility_is_valid_json`, `metrics_utility_parse_yaml_field`) dynamically via `CREATE OR REPLACE FUNCTION` when running with write access. Older versions of `latest.sql` were captured after running metrics-utility (so they already included the functions), but updating the schema to a fresh dump (2025-12) lost them. A separate `functions.sql` was added to the Docker Compose init scripts to pre-create these functions. Additionally, new non-nullable boolean fields (`event_queries_processed` in `main_job`, `org_unique` in `main_unifiedjobtemplate`) were added to the test data inserts.
- **Insight**: When CI tests run against a read-only database, any runtime-created objects (functions, views) must be included in the schema init scripts -- this is easy to miss when updating the schema dump to a newer version that was captured before the utility ran against it.

### Codecov integration added alongside SonarCloud
- **Repo**: ansible/metrics-utility
- **Commits**: b67aa1e (#407)
- **What happened**: Codecov was added as a second coverage reporting tool alongside SonarCloud. The pytest step was updated with `--cov-branch` for branch coverage (in addition to line coverage). The `codecov/codecov-action` step uploads `coverage.xml` with `flags: unit-tests` and `fail_ci_if_error: false` (non-blocking). A `codecov.yml` config file was added with: `target: auto` (track coverage changes against the default branch baseline), `threshold: 1%` (allow up to 1% coverage decrease), `carryforward: true` (use previous coverage data when not all flags are reported), and ignore patterns for test files. The comment layout includes reach, diff, flags, and files sections.
- **Insight**: Adding `--cov-branch` to pytest-cov captures branch coverage (whether both sides of conditionals are exercised), which is more meaningful than line coverage alone for code with many conditional paths like the report builders and validation logic.

### MinIO download links changed from direct to GitHub redirect
- **Repo**: ansible/metrics-utility
- **Commits**: 280b5f5 (#373)
- **What happened**: The MinIO binary download URLs (`dl.min.io`) changed from returning HTTP redirects to returning HTML redirect pages, breaking the CI workflow's `curl` commands. The fix added `-L` flag (follow redirects) and manual URL following for the HTML redirect case. MD5 checksum verification was also added for both `minio` and `mc` binaries, and `-f` was added to `curl` to fail on 4xx/5xx responses instead of silently downloading error pages.
- **Insight**: CI workflows that download external binaries should always verify checksums and use `curl -fL` -- download URLs can change their redirect behavior without notice, and silently downloading an HTML error page instead of a binary causes confusing test failures.

