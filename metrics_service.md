# metrics-service

Patterns, conventions, and gotchas specific to `ansible/metrics-service`.

### Prometheus metrics endpoint secured behind IsSystemAdminOrAuditor
- **Repo**: ansible/metrics-service
- **Commits**: adde11d (#251)
- **What happened**: The `django_prometheus` metrics endpoint was moved from the unauthenticated `/metrics` path to `/api/metrics` and wrapped in a `PrometheusMetricsView` (AnsibleBaseView subclass) with `permission_classes = [IsSystemAdminOrAuditor]`. A temporary 302 redirect from `/metrics` to `/api/metrics` maintains backwards compatibility for existing Prometheus scrapers during rollout. The nginx location block was also updated. An OpenAPI schema generation script (`tools/generate-openapi.sh`) was added to handle known cross-platform schema differences (macOS vs CI Linux) via deterministic patches.
- **Insight**: django-prometheus's default `ExportToDjangoView` is unauthenticated and leaks operational data (request rates, DB stats, error rates). Always wrap it in a permission-gated view. The backwards-compat redirect (302, not 301) lets scraper configs be updated gradually without data loss.

### Dashboard collection enabled by default with simplified flag management
- **Repo**: ansible/metrics-service
- **Commits**: 13ad18b (#275)
- **What happened**: The `DASHBOARD_COLLECTION` feature flag was promoted from opt-in (default False) to default-on by adding it to the `FEATURE` dict in `defaults.py`. The YAML-based AAPFlag seeding machinery (`feature_flags.yaml`, `load_task_feature_flags`, `sync_flag_values_from_settings`, `post_migrate` signal handler) was deleted entirely (-560 lines). The `metrics_service` management command's `--skip-feature-flag-init` argument was also removed. Opt-out remains available via env var, installer attribute, or Gateway UI toggle.
- **Insight**: Feature flag infrastructure should match the current lifecycle stage. Pre-GA opt-in flags need complex seeding machinery; post-GA default-on flags just need a dict entry with env var override. Deleting 560 lines of flag management code when the flag becomes default-on is a significant simplification.

### Platform auditor access via RBAC property + DAB bypass action flags
- **Repo**: ansible/metrics-service
- **Commits**: c99bfe5 (#302)
- **What happened**: System auditors were getting 401 on dashboard collection_status because DAB's `has_super_permission(user, 'view')` requires `ANSIBLE_BASE_BYPASS_ACTION_FLAGS = {"view": "is_platform_auditor"}` to be configured. The gateway conveys auditor status via JWT `global_roles`, not `user_data`, so no user flag was set. A `User.is_platform_auditor` property was added that queries RBAC assignments for the "Platform Auditor" `RoleDefinition` (no migration needed). The settings change mirrors `aap_gateway_api/defaults.py`.
- **Insight**: Each AAP service must explicitly configure `ANSIBLE_BASE_BYPASS_ACTION_FLAGS` to match the gateway's configuration. Without this, `IsSystemAdminOrAuditor` only checks `is_superuser` (via `BYPASS_SUPERUSER_FLAGS`) and never grants auditor access. The property-based approach on the User model integrates with DAB's `getattr(user, flag_name)` pattern without requiring a database migration.

### Job label sync with key-absent vs key-null distinction
- **Repo**: ansible/metrics-service
- **Commits**: d73d931 (#306)
- **What happened**: The dashboard job sync pipeline gained label support: labels are parsed from the `label_ids` column in collected data and synced via `_sync_labels`. A `label_ids` field was added to `ReportSerializer` and injected into report list responses via a batched post-pagination query. The critical fix distinguishes between key-absent (`"label_ids" not in row`, older collector versions -- preserve existing labels) and key-present-but-null (`row["label_ids"] is None` -- clear stale label records). The `_inject_label_ids` method runs a single `JobLabel` query scoped to `base_qs` (same filters as the report), excludes null `label_id` values, and injects `label_ids: [int]` into each aggregated row without inflating aggregates.
- **Insight**: Data pipeline sync functions must handle schema evolution gracefully. When a new column may be absent in data from older upstream versions, treat absence as "no information" (preserve existing state) rather than "empty" (delete existing state). This requires explicit `key not in dict` checks rather than relying on `dict.get(key)` which collapses both cases into `None`.
