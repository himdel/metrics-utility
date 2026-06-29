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

### PR checks workflow validates uv.lock is up-to-date
- **Repo**: ansible/metrics-utility
- **Commits**: 3cfd69d (#46)
- **What happened**: A `pr-checks.yml` workflow was added that runs `uv sync` then `git diff --exit-code uv.lock` to fail the PR if `uv.lock` is out of date with `pyproject.toml`. This catches cases where a developer adds a dependency but forgets to commit the updated lock file.
- **Insight**: Lock file drift checks in CI prevent "works on my machine" dependency issues when `pyproject.toml` changes are not reflected in the committed lock file.

### CI migrated from super-linter to uv+ruff, jscpd removed in favor of SonarCloud
- **Repo**: ansible/metrics-utility
- **Commits**: 243428e (#49), 599fb17 (#59)
- **What happened**: The super-linter (v4) based CI and the `.jscpd.json` copy-paste detection config were removed. The static analysis workflow was replaced with `astral-sh/setup-uv` + `uvx ruff check --output-format=github .`, which provides inline GitHub annotations. SonarCloud was added as a separate workflow for code quality and duplication analysis (`sonar-project.properties` configured with `sonar.cpd.exclusions=**/migrations/*.py`). The Python version was also set to use `python-version-file: "pyproject.toml"` instead of hardcoding.
- **Insight**: Replacing super-linter with ruff eliminated the overhead of many disabled validators and gave faster, more focused Python linting; SonarCloud replaced jscpd for copy-paste detection with richer analysis.

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

### CI pipeline established with two workflows: pr-checks and pytest
- **Repo**: ansible/metrics-service
- **Commits**: ee93077
- **What happened**: Two GitHub Actions workflows were added. `pr-checks.yml` runs on PRs and does: uv.lock freshness check (fails if `uv sync` would change it), `ruff check` with GitHub output format, and `ruff format --check`. `pytest.yml` runs on push to main and `pull_request_target`, sets up PostgreSQL, runs `uv run pytest` with coverage, and sends coverage to SonarCloud.
- **Insight**: The `uv.lock` freshness check is a good pattern -- it ensures developers run `uv sync` locally and commit the lockfile, preventing "works on my machine" dependency issues.

### pytest workflow uses pull_request_target (security consideration)
- **Repo**: ansible/metrics-service
- **Commits**: ee93077
- **What happened**: The pytest workflow triggers on `pull_request_target` rather than `pull_request`. This runs the workflow in the context of the base branch, which has access to secrets (needed for SonarCloud token), but means it runs the base branch's workflow file against the PR's code.
- **Insight**: `pull_request_target` is needed when workflows require secrets (like `CICD_ORG_SONAR_TOKEN_CICD_BOT`), but it's a security risk for public repos because it runs potentially untrusted PR code with access to secrets. The workflow mitigates this by checking out the PR branch explicitly.

### SonarCloud integration with custom exclusions
- **Repo**: ansible/metrics-service
- **Commits**: ee93077
- **What happened**: `sonar-project.properties` was added with: coverage exclusions for test directories, code duplication sensitivity tuned high (150 tokens, 300 lines), string literal duplication rule (S1192) ignored in migrations and tests, and Python version set to 3.11/3.12.
- **Insight**: The high duplication thresholds (150 tokens, 300 lines) indicate the team expected significant structural similarity in the codebase and didn't want false positives. This is reasonable for a Django project where models/serializers/views follow repetitive patterns.

### One-logger enforcement rule in pr-checks
- **Repo**: ansible/metrics-service
- **Commits**: ee93077
- **What happened**: The `pr-checks.yml` workflow includes a step called "One logger to rule them all" that greps for `logging.getLogger(` in `metrics_utility/` and fails if any file other than `logger.py` creates its own logger.
- **Insight**: This check references `metrics_utility` (a different package), suggesting it was copied from the metrics-utility repo's CI config. It would be a no-op in this repo since the directory doesn't exist, but reveals the team's pattern of enforcing a single logger factory.

### pytest workflow moved to "future-workflow" directory
- **Repo**: ansible/metrics-service
- **Commits**: 5b12d74 (#7)
- **What happened**: The pytest workflow was moved from `.github/workflows/pytest.yml` to `.github/workflows/future-workflow/pytest.yml`, effectively disabling it. The PR comment says "Moving pytest workflow into future folder as it isn't required right now."
- **Insight**: The pytest CI wasn't ready for prime time (likely due to database/migration dependencies not being fully set up in CI). Rather than deleting it, it was parked in a subdirectory. GitHub Actions only runs workflows directly in `.github/workflows/`, so subdirectories effectively disable them.

### pytest workflow restored and SonarCloud integration removed
- **Repo**: ansible/metrics-service
- **Commits**: cb58dc0 (#11), 8481170 (#17)
- **What happened**: In cb58dc0, the pytest workflow was moved back from the `future-workflow/` directory to `.github/workflows/pytest.yml`, with PostgreSQL as a CI service. In 8481170 (same day as the CodeQL revert), the SonarCloud reporting steps were removed from the pytest workflow, keeping only the test execution. This simplified the workflow from ~90 lines to ~55 lines.
- **Insight**: Removing SonarCloud from the pytest workflow decoupled testing from code quality reporting. SonarCloud was likely failing or requiring secrets that weren't available in all PR contexts, making the workflow unreliable. Keeping CI green is more important than having integrated code quality metrics.

### CodeQL workflow created and immediately reverted (5 minutes apart)
- **Repo**: ansible/metrics-service
- **Commits**: 7e90a26 (#15), cc53a70 (#16)
- **What happened**: A `codeql.yml` workflow was created in commit 7e90a26, then reverted just 5 minutes later in cc53a70. The file named `codeql.yml` actually contained a copy of the pytest workflow (name: "Pytest tests", running pytest, not CodeQL analysis). It was likely created by mistake -- either the wrong file was committed, or the intention was to add CodeQL but the template was wrong.
- **Insight**: This is a cautionary tale about premature CI tooling adoption and not verifying file contents before merging. The file was named `codeql.yml` but contained pytest configuration, suggesting a copy-paste error. The immediate revert (same day, same author) indicates it was caught quickly, possibly because CI started running duplicate pytest jobs or because the incorrect content was noticed in review.

### Konflux Tekton pipelines added for Red Hat CI/CD
- **Repo**: ansible/metrics-service
- **Commits**: c31e746 (#21)
- **What happened**: Two large Tekton PipelineRun YAML files (~640 lines each) were added under `.tekton/` for pull-request and push pipelines. These pipelines use hermetic builds, multi-platform support (x86_64 + arm64), source image building, and prefetch dependencies from `requirements-build.txt`. The pipelines target the `konflux-configs` branch specifically.
- **Insight**: Konflux pipelines are significantly more complex than GitHub Actions workflows, with explicit task chaining, OCI artifact storage, and enterprise scanning (SAST, SBOMs). The `prefetch-input` parameter requires pip-format requirements files, driving the need for the sync-requirements system.

### Automated dependency sync system with GitHub Actions + pre-commit
- **Repo**: ansible/metrics-service
- **Commits**: f848024 (#24), e5eba36 (#30)
- **What happened**: A `sync-requirements.sh` script was added that uses `uv export` and `uv pip compile` to generate `requirements-pinned.txt`, `dev-requirements.txt`, and `requirements-build.txt` from `uv.lock`. A GitHub Actions workflow (`sync-requirements.yml`) runs this on push to devel (auto-committing changes) and on PRs (failing if files are out of sync). A pre-commit hook was also added to auto-sync locally. In e5eba36, the workflow needed `permissions: contents: write` and `pull-requests: write` added because the default permissions were insufficient.
- **Insight**: The sync-requirements system bridges the gap between uv (development) and Konflux (pip-based builds). The CI workflow has two modes: on push it auto-commits updated requirements, on PRs it fails if they're out of sync. The follow-up permissions fix (e5eba36) is a common pattern -- GitHub Actions workflows with write operations need explicit permissions that aren't obvious until the workflow fails.

### pytest workflow switched from pull_request_target to pull_request
- **Repo**: ansible/metrics-service
- **Commits**: e9ff8c9 (#27)
- **What happened**: The pytest workflow trigger was changed from `pull_request_target` to `pull_request`, the complex dual-checkout logic (with conditional `if: ${{ ! github.base_ref }}` steps) was simplified to a single `actions/checkout@v5` step, and explicit read-only `permissions: contents: read` was added. The PostgreSQL port was also normalized from 55432 to 5432.
- **Insight**: The switch from `pull_request_target` to `pull_request` eliminated the security risk of running untrusted PR code with access to secrets. This was possible because SonarCloud integration (which needed secrets) had been removed earlier in 8481170. Adding explicit permissions follows the principle of least privilege for GitHub Actions.

### Batch of GitHub Actions dependency bumps (node20 to node24)
- **Repo**: ansible/metrics-service
- **Commits**: 3a68583 (#32), d2f46f6 (#34), 9b9da8c (#33)
- **What happened**: Three dependabot PRs bumped `astral-sh/setup-uv` from 6 to 7, `actions/github-script` from 7 to 8, and `actions/setup-python` from 5 to 6, all on the same day. All three were major version bumps driven by the Node.js 20 to 24 transition in GitHub Actions.
- **Insight**: Major version bumps in GitHub Actions are often trivial (just the node runtime upgrade) but can break self-hosted runners that aren't updated. The team merges dependabot PRs promptly, which is good practice for staying current with CI infrastructure.

### CI test database name changed and --reuse-db added
- **Repo**: ansible/metrics-service
- **Commits**: c8e5f0d (#36)
- **What happened**: The CI pytest workflow changed `POSTGRES_DB` from `test_metrics_service` to `metrics_service` and added `--reuse-db` to pytest options. This aligned with the broader switch from SQLite in-memory tests to PostgreSQL tests.
- **Insight**: The database name change was necessary because `--reuse-db` reuses the actual database between test runs, and the name needed to match what Django's test runner expects. This speeds up CI significantly by avoiding database recreation on every run.

### actions/checkout bumped from v5 to v6
- **Repo**: ansible/metrics-service
- **Commits**: a939642 (#58)
- **What happened**: Dependabot bumped `actions/checkout` from v5 to v6 across all three workflows (`pr-checks.yml`, `pytest.yml`, `sync-requirements.yml`). This is part of the ongoing Node.js runtime upgrades in GitHub Actions.
- **Insight**: Keeping checkout action current avoids eventual deprecation warnings. The v5->v6 bump (like v4->v5 before it) is typically transparent with no breaking changes for standard usage.

### Framework automation workflows added
- **Repo**: ansible/metrics-service
- **Commits**: 00e68ad (#84), 5be118c (#88)
- **What happened**: Two framework workflows were added in #84: `framework-update.yml` (for automated template updates from platform-service-framework) and `framework-validation.yml` (for validating files match the template). A branch protection ruleset was also added. The validation workflow was removed in #88 because it compared files like `.gitignore`, `manage.py`, and `pyproject.toml` against the template and failed on legitimate customizations.
- **Insight**: The framework-update workflow enables automated template syncing, which is valuable for keeping the service aligned with the platform. The validation workflow was too strict -- it assumed files would be identical to the template, which isn't realistic for a service that needs project-specific configuration.

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

### SonarCloud re-integrated via workflow_run pattern
- **Repo**: ansible/metrics-service
- **Commits**: d4996ef (#93)
- **What happened**: SonarCloud scanning was re-added (it had been removed in 8481170 #17) using a two-workflow pattern. The `pytest.yml` workflow now uploads `coverage.xml` as an artifact and saves the PR number to a text file artifact. A new `sonar_checks.yml` workflow triggers on `workflow_run` completion of the pytest workflow, downloads the coverage artifact, validates the PR number against the workflow run's commit (preventing artifact substitution attacks), and runs the SonarCloud scan with PR-specific parameters. For push events (non-PR), SonarCloud runs directly in the pytest workflow. The checkout now uses `fetch-depth: 0` for full git history (required by SonarCloud for blame analysis).
- **Insight**: The `workflow_run` pattern solves the secrets-in-PRs problem: the pytest workflow runs on `pull_request` (no secrets), uploads artifacts, then the Sonar workflow runs on `workflow_run` (has secrets) and downloads them. The PR number validation step (checking that the artifact's PR number matches the actual PR for the commit) is a security measure against malicious artifact substitution.

### CI SQL schema requires pre-created functions for read-only mode
- **Repo**: ansible/metrics-utility
- **Commits**: 7d148b9 (#300)
- **What happened**: The CI test database uses a read-only schema import (`latest.sql`), but metrics-utility creates custom PostgreSQL functions (`metrics_utility_is_valid_json`, `metrics_utility_parse_yaml_field`) dynamically via `CREATE OR REPLACE FUNCTION` when running with write access. Older versions of `latest.sql` were captured after running metrics-utility (so they already included the functions), but updating the schema to a fresh dump (2025-12) lost them. A separate `functions.sql` was added to the Docker Compose init scripts to pre-create these functions. Additionally, new non-nullable boolean fields (`event_queries_processed` in `main_job`, `org_unique` in `main_unifiedjobtemplate`) were added to the test data inserts.
- **Insight**: When CI tests run against a read-only database, any runtime-created objects (functions, views) must be included in the schema init scripts -- this is easy to miss when updating the schema dump to a newer version that was captured before the utility ran against it.

### SonarCloud workflow hardened with PR state validation and HTTP error checking
- **Repo**: ansible/metrics-service
- **Commits**: 8ba3c14 (#101)
- **What happened**: The `sonar_checks.yml` workflow was updated to add PR state validation (checks if the PR is still `open` before running SonarCloud scan), HTTP status code checking for GitHub API calls (failing on non-200 responses instead of silently proceeding), and early exit if the commit-to-PR association list is empty. Redundant Sonar parameters (`sonar.host.url`, `sonar.organization`, `sonar.projectKey`) were removed from `pytest.yml` since they're set via env vars. All subsequent steps are gated with `if: steps.pr_state_check.outputs.state == 'open'`.
- **Insight**: The original workflow would silently succeed on closed PRs or when the GitHub API returned errors, potentially missing legitimate scan failures. This hardening prevents wasted CI resources on closed PRs and ensures API errors are caught rather than producing confusing downstream failures.

### Makemigrations check added to PR CI
- **Repo**: ansible/metrics-service
- **Commits**: e137d39 (#92)
- **What happened**: A `python manage.py makemigrations --check` step was added to the `pr-checks.yml` workflow. This detects when model changes are committed without corresponding migrations.
- **Insight**: Without this check, developers could merge model changes without migrations, which would only be discovered when someone tries to run `migrate`. The `--check` flag makes `makemigrations` exit with non-zero if any new migrations would be created, catching the oversight early.

### Coverage config moved from pytest addopts to declarative pyproject sections
- **Repo**: ansible/metrics-service
- **Commits**: e137d39 (#92)
- **What happened**: Coverage options (`--cov`, `--cov-report`, etc.) were removed from `[tool.pytest.ini_options].addopts` and moved to `[tool.coverage.run]` and `[tool.coverage.report]` sections in pyproject.toml. CI was updated to explicitly pass `--cov` to pytest.
- **Insight**: Having `--cov` in addopts forces coverage measurement on every pytest run, including when running a single test file during development. This is slow and can cause failures when individual tests are run (the coverage threshold won't be met). Moving to declarative config means `pytest` runs fast by default, and `pytest --cov` explicitly enables coverage when needed (CI).

### CodeRabbit configured to not edit PR descriptions
- **Repo**: ansible/metrics-service
- **Commits**: 80a2ce6 (#116)
- **What happened**: A `.coderabbit.yaml` was added with `inheritance: true` (inherits org-level config), `reviews.high_level_summary: false` (don't put summary in PR description), and `reviews.high_level_summary_in_walkthrough: true` (put it in the walkthrough comment instead).
- **Insight**: CodeRabbit's default behavior of editing PR descriptions overwrites manually-written context. Moving the auto-generated summary to a comment preserves the author's original PR description while still providing the AI-generated overview. The `inheritance: true` means most config comes from the org level, with this repo only overriding the summary placement.

### CodeRabbit configured for additional feature branches
- **Repo**: ansible/metrics-service
- **Commits**: e6fff2c (#125)
- **What happened**: The `.coderabbit.yaml` was updated to add `auto_review.base_branches: [FB-Automation-Dashboard]`, enabling CodeRabbit auto-reviews on PRs targeting the `FB-Automation-Dashboard` feature branch (in addition to the default main/devel branches).
- **Insight**: For long-lived feature branches with their own PR flow, CodeRabbit needs explicit branch configuration. The `auto_review.base_branches` setting controls which target branches trigger automated code review.

### SonarCloud workflow reorganized: scan removed from pytest, dedicated to sonar_checks
- **Repo**: ansible/metrics-service
- **Commits**: 24681be (#127), 1dedd90 (#128), c4add8a (#134)
- **What happened**: Three related changes reorganized SonarCloud integration. #127 expanded `sonar.sources` from just `metrics_service` to `metrics_service,apps` (so the `apps/` directory is scanned too) and simplified the coverage exclusion pattern from `metrics_service/tests/**, tests/**` to `**/tests/**`. #128 removed the on-push SonarCloud scan step from `pytest.yml` entirely -- push-based SonarCloud was duplicating the PR-based scan. #134 re-added the push-based SonarCloud scan to `pytest.yml` (gated with `if: github.event_name == 'push'`) because devel branch pushes need coverage published without the PR workflow. The PR SonarCloud workflow (`sonar_checks.yml`) was also hardened: the unreliable `commits/{sha}/pulls` API validation was replaced with direct branch/SHA/repo matching against the triggering workflow_run, and all downstream steps now gate on a `should_scan` output instead of checking PR state separately. The `octokit/request-action` dependency was removed in favor of direct curl/jq.
- **Insight**: The SonarCloud setup settled on a clear split: push events (devel/main) get scanned inline in `pytest.yml`, while PR events use the two-workflow `workflow_run` pattern in `sonar_checks.yml`. The PR validation was fragile because the `commits/{sha}/pulls` API can return empty results for recently pushed commits due to GitHub's eventual consistency -- validating branch name + SHA + repo is more reliable.

### pr-checks workflow gained PostgreSQL service for makemigrations check
- **Repo**: ansible/metrics-service
- **Commits**: e941270 (#126)
- **What happened**: The `pr-checks.yml` workflow was updated to include a PostgreSQL service container (same pattern as the pytest workflow) with Dynaconf-style database env vars (`METRICS_SERVICE_DATABASES__default__HOST`, etc.) on the "Check for missing migrations" step. Previously, `makemigrations --check` ran without a database, which would fail for any migration that references database-specific features.
- **Insight**: Django's `makemigrations` needs a database connection when using PostgreSQL-specific features (like `JSONField` default validation). Adding PostgreSQL to `pr-checks` mirrors the `pytest.yml` setup and ensures the migration check runs against the same database engine as production.

### Ruff pre-commit hooks added for auto-fixing lint and format
- **Repo**: ansible/metrics-service
- **Commits**: 284f919 (#151)
- **What happened**: The `.pre-commit-config.yaml` was updated to add ruff pre-commit hooks for both linting (`ruff check --fix`) and formatting (`ruff format`). The old requirements sync hook was removed. CLAUDE.md and README.md were heavily streamlined to standardize commands around `uv` and `poe`. The `CONTRIBUTING.md` governance model reference was corrected.
- **Insight**: Adding `--fix` to the ruff pre-commit hook means formatting and fixable lint issues are auto-corrected on commit, reducing CI failures from trivial style issues. Removing the requirements sync hook reflects the earlier deletion of the sync-requirements system in #129.

### SonarCloud exclusions expanded to include settings directories
- **Repo**: ansible/metrics-service
- **Commits**: 956923d (#193)
- **What happened**: `sonar-project.properties` was updated to add `**/settings/**` to both `sonar.exclusions` (source scan) and `sonar.coverage.exclusions` (coverage). This excludes `apps/settings/` and `metrics_service/settings.py` from SonarCloud analysis.
- **Insight**: Settings files contain Dynaconf validators, environment-specific overrides, and configuration constants that are inherently difficult to unit test directly (they run at import time and depend on specific environment state). Excluding them from coverage requirements avoids inflating coverage targets while keeping the coverage signal meaningful for business logic.

### MinIO download links changed from direct to GitHub redirect
- **Repo**: ansible/metrics-utility
- **Commits**: 280b5f5 (#373)
- **What happened**: The MinIO binary download URLs (`dl.min.io`) changed from returning HTTP redirects to returning HTML redirect pages, breaking the CI workflow's `curl` commands. The fix added `-L` flag (follow redirects) and manual URL following for the HTML redirect case. MD5 checksum verification was also added for both `minio` and `mc` binaries, and `-f` was added to `curl` to fail on 4xx/5xx responses instead of silently downloading error pages.
- **Insight**: CI workflows that download external binaries should always verify checksums and use `curl -fL` -- download URLs can change their redirect behavior without notice, and silently downloading an HTML error page instead of a binary causes confusing test failures.

### PR target branch validation added to pr-checks
- **Repo**: ansible/metrics-service
- **Commits**: 590ccc9 (#249)
- **What happened**: A "Check PR target" step was added to `pr-checks.yml` that validates the PR's base branch before running any other checks. On upstream (`ansible/metrics-service`), PRs must target `devel`; downstream forks may target `stable-2.*` branches. The check uses shell conditionals against `github.event.pull_request.base.repo.full_name` and `github.event.pull_request.base.ref`, failing with a descriptive `::error::` message if the target is invalid.
- **Insight**: Target branch validation in CI prevents accidental PRs to `main` or other non-standard branches, which is especially useful when the default branch is `devel` (not `main`) and contributors may not know the convention.

### SonarCloud exclusions expanded for boilerplate files
- **Repo**: ansible/metrics-service
- **Commits**: 651db2b (#217)
- **What happened**: `sonar-project.properties` coverage exclusions were expanded to include `metrics_service/asgi.py`, `metrics_service/wsgi.py`, `metrics_service/test_urls.py`, and `metrics_service/settings.py`. These are boilerplate/configuration files that are inherently difficult to unit test (ASGI/WSGI entrypoints, Dynaconf constants, test-only URL config).
- **Insight**: Excluding genuinely untestable boilerplate from Sonar coverage analysis prevents the coverage metric from being diluted by files that can never realistically reach high coverage. This is complementary to the earlier `**/settings/**` exclusion (956923d #193) which covered settings directories.

### Codecov integration added alongside SonarCloud
- **Repo**: ansible/metrics-service
- **Commits**: 527ca15 (#221), b2ac31f (#222)
- **What happened**: Codecov was added to the pytest workflow in two steps. #221 added `--cov-branch` to the pytest command (for branch coverage) and the `codecov/codecov-action` step to upload `coverage.xml`. #222 enhanced the integration: added `flags: unit-tests` to the upload (for flag-based coverage tracking), `fail_ci_if_error: false` (so Codecov outages don't break CI), and `verbose: true`. A `codecov.yml` configuration file was added with: coverage precision (2 decimal), auto target with 1% threshold for both project and patch coverage, comprehensive ignore patterns (migrations, tests, settings, tools, scripts, .venv), a `unit-tests` flag with `carryforward: true` scoped to `apps/` and `metrics_service/`, and a comment layout with reach/diff/flags/files.
- **Insight**: Running both Codecov and SonarCloud provides redundancy (different coverage visualization and PR comment styles) and serves different audiences (Codecov for developers via PR comments, SonarCloud for quality gate enforcement). The `carryforward: true` flag means partial test runs still show coverage for untouched files from previous uploads, preventing misleading drops. The 1% threshold prevents CI from failing on minor coverage fluctuations.

### Codecov integration added alongside SonarCloud
- **Repo**: ansible/metrics-utility
- **Commits**: b67aa1e (#407)
- **What happened**: Codecov was added as a second coverage reporting tool alongside SonarCloud. The pytest step was updated with `--cov-branch` for branch coverage (in addition to line coverage). The `codecov/codecov-action` step uploads `coverage.xml` with `flags: unit-tests` and `fail_ci_if_error: false` (non-blocking). A `codecov.yml` config file was added with: `target: auto` (track coverage changes against the default branch baseline), `threshold: 1%` (allow up to 1% coverage decrease), `carryforward: true` (use previous coverage data when not all flags are reported), and ignore patterns for test files. The comment layout includes reach, diff, flags, and files sections.
- **Insight**: Adding `--cov-branch` to pytest-cov captures branch coverage (whether both sides of conditionals are exercised), which is more meaningful than line coverage alone for code with many conditional paths like the report builders and validation logic.

### OpenAPI schema generation, validation, and auto-sync to downstream repo
- **Repo**: ansible/metrics-service
- **Commits**: 6ee2d93 (#196)
- **What happened**: Three CI additions: (1) `pr-checks.yml` gained "Generate OpenAPI schema" and "Validate OpenAPI schema" steps that regenerate the spec via `drf-spectacular`, diff against committed files, and validate with `openapi-spec-validator`. (2) A new `sync-openapi-specs.yml` workflow triggers on push to devel (when `apps/**/*.py` files change) and auto-creates a PR in `ansible-automation-platform/aap-openapi-specs` with the updated spec. Uses `AAP_OPENAPI_SPECS_PAT` secret for cross-repo push. (3) Makefile targets `generate-openapi-schema` and `validate-openapi-schema` for local dev.
- **Insight**: The two-tier CI approach (PR validation + push-triggered sync) ensures the committed spec stays current while automating downstream publication. The PR validation catches schema drift (developer changes an endpoint but forgets to regenerate), while the push workflow ensures the central specs repo is always in sync with devel.

### Cross-repo CI: metrics-service tests run against local metrics-utility checkout
- **Repo**: ansible/metrics-utility
- **Commits**: 6b6a2d8 (#427)
- **What happened**: A new `pytest-service` job was added to the `pytest.yml` workflow that clones `ansible/metrics-service@devel` and runs its test suite with the current checkout of metrics-utility installed via `uv add --editable "${GITHUB_WORKSPACE}"`. This catches utility changes that break the service before they are merged. The job reuses the same SQL dump setup as the utility test job (the `roles.sql` script already creates the `metrics_service` role and database). The job runs migrations via `uv run python manage.py migrate --noinput` and then `uv run pytest -s -v` with Dynaconf-style env vars for both the `default` and `awx` database connections.
- **Insight**: Running a downstream consumer's test suite against the current PR's code (via editable install) is a lightweight way to detect API-breaking changes before merge -- it requires no coordination between repos and uses existing CI infrastructure (same SQL dump, same PostgreSQL setup).

### Go build step added to CI for mock Segment server
- **Repo**: ansible/metrics-utility
- **Commits**: df497c3 (#409)
- **What happened**: The `pytest.yml` workflow gained `actions/setup-go@v5` (with `go-version-file: tools/mock-segment-server/go.mod`) and a "Start mock Segment server" step that builds the Go binary, runs it in the background, and waits (with a 1-minute timeout) for the `/requests` endpoint to become available before running pytest. This is the first use of Go in the metrics-utility CI pipeline.
- **Insight**: Using a compiled Go binary as a test fixture server avoids Python dependency conflicts (no need to install a mock HTTP framework) and starts faster than a Python HTTP server. The `timeout-minutes: 1` on the wait step prevents CI from hanging if the server fails to start.

### Tekton PipelineRun added for tier-1 ATF tests as PR check
- **Repo**: ansible/metrics-service
- **Commits**: c37c4c2 (#255)
- **What happened**: A Tekton PipelineRun manifest (`.tekton/run-atf-tests-pull-request.yaml`) was added to run marked tier-1 tests from the AAP test framework (ATF) as a PR check. The pipeline triggers on PR comments matching `^/run-atf-tests$` (via `pipelinesascode.tekton.dev/on-comment`), runs in the `ansible-ci-tenant` namespace, and references the `aap-api-tests` pipeline bundle from `quay.io/aap-ci/tekton-catalog`. It has generous timeouts (8h pipeline, 7h tasks, 1h finally) for the integration test suite. The pipeline passes the PR's source URL, org, repo, branch, revision, and PR number as parameters. A `renovate.json` was also added with `enabledManagers: ["tekton"]` and `automerge: true` on a twice-daily weekday schedule, so Tekton bundle digest updates are automatically applied.
- **Insight**: This is a separate Tekton pipeline from the earlier Konflux build pipelines (which were deleted in #129). Unlike those, this pipeline runs integration tests (not container builds) and is triggered on-demand via PR comments rather than automatically on every PR. The Renovate config specifically targets Tekton bundle references (OCI image digests in PipelineRun YAML), auto-merging these updates because they are low-risk and frequent.

### JSON schema validation and tarball validator tool added
- **Repo**: ansible/metrics-utility
- **Commits**: eb4bcfd (#428), e0e7e8a (#434)
- **What happened**: Two complementary schema validation capabilities were added. (1) PR #428 added versioned JSON schemas under `schemas/` for config (v1.0 and v2.0), data_collection_status, job_host_summary (v1.2), total_workers_vcpu (v1.0), and manifest files. Integration tests in `test_json_schema.py` run `gather` to produce tarballs, extract each file, and validate against the corresponding schema using `jsonschema.validate()`. A custom `validate_with_datetime` function extends the JSON Schema validator with a `datetime` type check via `fromisoformat()`. The `jsonschema>=4.26.0` dev dependency was added. (2) PR #434 added a standalone `tools/validator/validate.py` script that validates tarballs against schemas with checks for: required files, manifest version format, DCS row status, schema validation per file type, unknown file warnings, and a `--strict-billing-files` flag that fails on files not accepted by the backend billing pipeline. Schema types for config fields were corrected based on actual AWX output (`automated_since` is int not string, `date_expired`/`date_warning` are bool not string, `license_date` is int not string).
- **Insight**: Versioned JSON schemas serve as a machine-readable contract between metrics-utility (producer) and the billing backend (consumer) -- schema mismatches that would previously only surface in production can now be caught by CI tests and the standalone validator tool.

### Schema-review workflow: pull_request_target for fork write permissions
- **Repo**: ansible/metrics-utility
- **Commits**: 4d8487d (#436), 7039a5e (#438), 96ec277 (#440)
- **What happened**: A `schema-review.yml` GitHub Actions workflow was added to auto-request reviewers and post a warning comment when PRs modify files in `schemas/` (later `metrics_utility/schemas/`). Three quick iterations refined it: (1) #436 consolidated split triggers (pull_request_target + pull_request) into a single `pull_request_target` trigger because `pull_request` on forks has a read-only token, making `pulls.requestReviewers()` and `issues.createComment()` API calls fail. (2) #438 added `synchronize` and `edited` event types, and filtered out the PR author from the reviewer list to avoid the GitHub API error of requesting review from the PR creator. (3) #440 removed HCC Analytics team members from the reviewer assignment list (kept them in the comment @-mention) because they aren't direct GitHub collaborators and the `requestReviewers` API would fail for non-collaborators.
- **Insight**: Workflows that need write permissions (requesting reviewers, posting comments) must use `pull_request_target` to work on fork PRs -- but filter out the PR author from reviewer requests (GitHub rejects self-review requests) and only assign reviewers who are actual repository collaborators.

### GitHub Actions pinned to commit SHAs with version comments
- **Repo**: ansible/metrics-utility
- **Commits**: 1c53c4b (#449)
- **What happened**: All GitHub Actions references across 6 workflow files were changed from tag-based versions (e.g., `actions/checkout@v6`) to commit SHA pins with version comments (e.g., `actions/checkout@df4cb1c069e1874edd31b4311f1884172cec0e10 # v6`). This covers `actions/checkout`, `astral-sh/setup-uv`, `actions/setup-python`, `actions/setup-go`, `actions/upload-artifact`, `actions/download-artifact`, `SonarSource/sonarqube-scan-action`, `codecov/codecov-action`, `actions/github-script`, and `snyk/actions/setup`. Dependabot will continue proposing updates in the same SHA+comment format.
- **Insight**: Pinning GitHub Actions to commit SHAs prevents supply chain attacks where a tag is moved to point to malicious code -- the version comment preserves human readability while the SHA ensures immutability. Dependabot understands this format and proposes updates with both the new SHA and version comment.

### PR target branch validation added for metrics-utility
- **Repo**: ansible/metrics-utility
- **Commits**: ba7ad32 (#458)
- **What happened**: A "Check PR target" step was added to `pr-checks.yml` that validates the PR's base branch before running any other checks. On upstream (`ansible/metrics-utility`), PRs must target `devel`; forks may target `stable-*` branches. This mirrors the pattern from `ansible/metrics-service` (#249) but uses `stable-*` (no `2.` prefix) to match metrics-utility's branch naming convention. The check uses shell conditionals with `[[ "$BASE_BRANCH" == stable-* ]]` for glob matching.
- **Insight**: Target branch validation patterns must be adapted per repo -- metrics-utility uses `stable-*` branches while metrics-service uses `stable-2.*` branches, so the glob pattern differs even though the CI logic is structurally identical.

### Jira ticket tagging GitHub Action auto-links PRs to Jira issues
- **Repo**: ansible/metrics-utility
- **Commits**: b73d38a (#462)
- **What happened**: A `jira-pr-link.yml` workflow was added that runs on `pull_request_target` (opened, edited, reopened). It searches for `AAP-\d+` ticket numbers in three places in order: (1) PR title, (2) PR body, (3) commit messages (via `gh pr view --json commits`). When found, it updates the Jira ticket's custom field `customfield_10875` (Git Pull Request) with the PR URL via the Jira REST API (`PUT /rest/api/2/issue/{ticket}`). The workflow posts a comment on the PR with idempotent marker (`<!-- jira-pr-link-bot -->`) -- either confirming the link or warning about a missing ticket. Comments are updated (not duplicated) on subsequent PR edits via the marker-based comment lookup pattern. Uses `JIRA_BASE_URL` (vars), `BOT_JIRA_EMAIL` and `BOT_JIRA_API_TOKEN` (secrets). All API failures emit `::warning::` instead of failing the workflow.
- **Insight**: Auto-linking PRs to Jira via a custom field update (rather than just commenting) creates bidirectional traceability -- the Jira ticket shows the PR link without manual effort. Using `::warning::` instead of `exit 1` for API failures ensures the workflow degrades gracefully when Jira credentials aren't configured (e.g., on forks).

### SonarCloud scan action bumped from 7.2.1 to 8.2.0
- **Repo**: ansible/metrics-utility
- **Commits**: 6a34a05 (#393)
- **What happened**: Dependabot bumped `SonarSource/sonarqube-scan-action` from 7.2.1 to 8.2.0 across both `pytest.yml` and `sonar_checks.yml`. This is a major version bump (7 to 8).
- **Insight**: SonarCloud action major version bumps are generally transparent for projects that don't use advanced scanner configuration -- the action's interface (env vars, inputs) has remained stable across major versions.

## Superseded / Semi-Obsolete

### pytest workflow was disabled in this batch (m-s)
- **Repo**: ansible/metrics-service
- Moved to `future-workflow/` directory in commit 5b12d74, then restored in cb58dc0 (#11). It is now actively running in `.github/workflows/pytest.yml`.

### SonarCloud integration in pytest workflow (m-s)
- **Repo**: ansible/metrics-service
- SonarCloud reporting was removed from the pytest workflow in 8481170 (#17), then partially re-added in c4add8a (#134) for push events only. The full PR-based scan now lives in `sonar_checks.yml` via `workflow_run`.

### SonarCloud PR validation via commits/{sha}/pulls API (m-s)
- **Repo**: ansible/metrics-service
- The `commits/{sha}/pulls` approach from 8ba3c14 (#101) was replaced in c4add8a (#134) with direct branch/SHA/repo matching. The old API was unreliable due to GitHub's eventual consistency -- recently pushed commits sometimes returned empty PR lists, causing false validation failures.

### Renovate cron wildcard-minute prevention PR check
- **Repo**: ansible/metrics-service
- **Commits**: 7e78597 (#281)
- **What happened**: The Renovate config's Tekton schedule had `"* */12 * * 1-5"` -- wildcard minute meant "every minute during matching hours" (60 PRs per window). Fixed to `"0 */12 * * 1-5"`. A new PR check step was added to `pr-checks.yml` that greps for `"schedule".*"\* ` in `renovate.json` and fails with an error annotation if found: "Cron schedules in renovate.json must not use * for minutes (runs every minute). Use a specific minute like 0."
- **Insight**: Cron wildcard-minute is an easy mistake in Renovate/Dependabot schedule configs where the intent is "once per interval" but `*` means "every minute". A CI check prevents this from recurring.

### Tekton pipeline bundle digest update and Renovate config fix
- **Repo**: ansible/metrics-service
- **Commits**: 8f78a44 (#271)
- **What happened**: Updated the Tekton pipeline bundle digest in `.tekton/run-atf-tests-pull-request.yaml` to unblock pipeline runs failing in `report-test-results-to-pr` task. Also fixed a Renovate configuration error and removed AWS spot instance usage from the pipeline. This was a manual update ahead of mint maker automation.
- **Insight**: Tekton pipeline bundle digests are OCI image references that must be updated when the upstream pipeline image changes. Renovate is configured to auto-merge these updates, but manual intervention is needed when the pipeline is broken and blocking.

### UV ecosystem added to Dependabot config
- **Repo**: ansible/metrics-service
- **Commits**: 76f179e (#284)
- **What happened**: Added `package-ecosystem: 'uv'` to `.github/dependabot.yml` alongside the existing `github-actions` ecosystem. Both use monthly schedule. This enables Dependabot to track Python dependencies in `pyproject.toml` / `uv.lock` and propose version bumps as PRs (the first batch produced PRs #288-#294).
- **Insight**: With the project using uv for dependency management, Dependabot's `uv` ecosystem support (relatively new) provides automated dependency update PRs for Python packages, complementing the existing `github-actions` ecosystem for CI action version bumps.

### Framework validation workflow re-added using PSF validate command
- **Repo**: ansible/metrics-service
- **Commits**: 6c01004 (#267)
- **What happened**: A `framework-validation.yml` workflow was re-added (previously added in #84 and removed in #88 for being too strict). The new version uses the PSF's own validate command (`uvx --refresh git+https://github.com/${ORG}/platform-service-framework@${BRANCH} validate`) instead of a custom template-comparison approach. It runs on PRs and pushes to devel/main/stable/release branches, dynamically determining the org and branch from the PR context.
- **Insight**: Framework validation is back, but now uses the framework's own validation tool rather than a rigid file-comparison approach. This is more maintainable because the framework team controls what passes validation.

### GitHub Actions SHA pinning with version comments
- **Repo**: ansible/metrics-service
- **Commits**: 9e5f887 (#283), 958edf8 (#287)
- **What happened**: All GitHub Actions `uses:` references in project-owned workflows (pr-checks, pytest, sonar_checks, sync-openapi-specs) were changed from tag references (e.g., `actions/checkout@v6`) to commit SHA references with version comments (e.g., `actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0 # v7.0.0`). Framework-managed workflows (framework-*.yml) were left unchanged since they're validated by the PSF and pinning there causes validation conflicts. Dependabot continues to propose updates in the same SHA+comment format.
- **Insight**: SHA pinning prevents supply-chain attacks where a malicious actor could re-tag a GitHub Action to inject code. The `# vX.Y.Z` comment preserves human readability. Framework-managed workflow files must NOT be modified with SHA pins since they need to match the PSF template exactly -- pin only project-owned workflows.

### Fork PRs: skip SonarCloud/Codecov when secrets are missing
- **Repo**: ansible/metrics-service
- **Commits**: b583841 (#303), 395916f (#305)
- **What happened**: Fork PRs in public repos don't have access to org secrets (`CICD_ORG_SONAR_TOKEN_CICD_BOT`, `CODECOV_TOKEN`). Previously, SonarCloud and Codecov steps would fail silently or with confusing errors on fork PRs. The fix uses job-level env vars (`HAS_SONAR_TOKEN: ${{ secrets.CICD_ORG_SONAR_TOKEN_CICD_BOT != '' }}`) to detect secret availability, then skips affected steps with `if: env.HAS_SONAR_TOKEN == 'true'`. The sonar_checks workflow also adds the token check at the scan step level. This makes fork PRs work cleanly -- tests run, but code quality reporting is skipped.
- **Insight**: For open-source repos that accept fork PRs, every workflow step that uses org secrets must have a guard. The `secrets` -> `env` -> `if` bridge pattern is the canonical GitHub Actions approach. Apply it to: artifact uploads (coverage reports), external service integrations (SonarCloud, Codecov), and any step using bot tokens.

### Jira PR linking GitHub Action with iterative fixes
- **Repo**: ansible/metrics-service
- **Commits**: 8fa4253 (#304), dc017f0 (#308), 5120327 (#309), 45ee4c5 (#310)
- **What happened**: A `jira-pr-link.yml` workflow was added to automatically extract Jira ticket numbers (AAP-NNNNN) from PR titles, descriptions, and commit messages, then update the Jira issue's "Git Pull Request" custom field (`customfield_10875`) via the Jira REST API. Four rapid-fire follow-up PRs fixed issues: #308 replaced `secrets.BOT_GITHUB_TOKEN` with `github.token` for `gh` CLI calls (commit checking and PR commenting don't need a bot PAT); #309 switched from `pull_request` to `pull_request_target` trigger (allows writing comments on fork PRs), replaced `gh pr comment --edit-last` with explicit marker-based comment management (`<!-- jira-pr-link-bot -->` prefix + API-based find-and-update), and fixed a trailing whitespace in a shell heredoc; #310 removed backticks from the Jira ticket name in the success comment.
- **Insight**: (1) Use `pull_request_target` (not `pull_request`) for workflows that need write access to fork PRs -- `pull_request` events from forks run with read-only permissions. (2) For idempotent bot comments, use an HTML comment marker (`<!-- bot-name -->`) at the start of the comment body, then find existing comments by that marker via the API and update them rather than posting duplicates. (3) `github.token` is sufficient for reading PR commit data and posting comments -- don't use a bot PAT unless you need cross-repo or elevated permissions. (4) Jira REST API for custom fields uses `PUT /rest/api/2/issue/{key}` with `{"fields": {"customfield_XXXXX": "value"}}`.
