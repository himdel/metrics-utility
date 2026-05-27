# API Design

> Default repo: metrics-service

## Learnings

### Serializers migrated from ModelSerializer to HyperlinkedModelSerializer
- **Commits**: ad01618
- **What happened**: All four serializers (User, Organization, Team, Animal) were changed from `serializers.ModelSerializer` to `serializers.HyperlinkedModelSerializer`. At the same time, `resource` field was removed from all serializers (it was a DAB-specific field that may not have been stable yet), and `description` was dropped from AnimalSerializer.
- **Insight**: `HyperlinkedModelSerializer` uses URLs instead of primary keys for relationships, making the API more RESTful and self-documenting. The trade-off is that `url` fields require properly configured `view_name` kwargs, which adds maintenance burden.

### API views use AnsibleBaseDjangoAppApiView as base
- **Commits**: dd5603f
- **What happened**: All viewsets inherit from both `AnsibleBaseDjangoAppApiView` (from DAB) and `viewsets.ModelViewSet`. This dual inheritance provides DAB's authentication/authorization integration while keeping DRF's standard CRUD operations.
- **Insight**: The DAB integration is done via mixin-style multiple inheritance. The permission classes combine `OAuth2ScopePermission` and `AnsibleBaseObjectPermissions`, meaning both OAuth2 scope and object-level RBAC must be satisfied.

### Code duplication reduction through base classes and mixins
- **Commits**: 2a1c481 (#9)
- **What happened**: Introduced `BaseViewSet` (handles `get_queryset` via `access_qs`, `perform_create` with auto `created_by`, standardized exception handling), `UserManagementMixin` (generic `_add_user_to_field`/`_remove_user_from_field`), `BaseModelSerializer` (auto marks common fields as read-only, inherits `CountFieldMixin`), and `CountFieldMixin` (provides `get_users_count`, `get_admins_count`, etc. using `get_count_safely` utility).
- **Insight**: The refactoring reduced per-viewset boilerplate significantly, but introduced implicit behavior (e.g., `BaseModelSerializer.__init__` modifying `Meta.read_only_fields` at runtime). This can make debugging serializer behavior harder since the field configuration isn't visible in the concrete serializer class.

### Utility module created for cross-cutting concerns
- **Commits**: 2a1c481 (#9)
- **What happened**: `apps/core/utils.py` was created with helper functions like `get_count_safely()`, `build_error_response()`, `log_task_execution()`, and various other utilities. These were used by both the API layer (views, serializers) and the task system.
- **Insight**: Centralizing utilities like `get_count_safely(getattr(obj, "users", None))` prevents AttributeError crashes when related managers aren't available, which is important given the conditional DAB availability.

### RBAC established with system auditor and superuser roles
- **Commits**: fd6745d (#10)
- **What happened**: Real RBAC was implemented for organizations. `Organization.access_qs()` was overridden to filter by user permissions: superusers see everything, system auditors see everything (read-only), regular users see only organizations they belong to. A custom `apps/core/permissions.py` module was added with permission classes. The `is_system_auditor` field was added to User model. The `OrganizationSerializer` gained `get_related()` and `get_object_role()` methods that use Django's permission system (which DAB extends) to report per-object permissions.
- **Insight**: The RBAC implementation follows a graduated access pattern: superuser > system_auditor > regular user. The `get_object_role()` method returning `{add, edit, delete}` booleans per object is the DAB convention for communicating permissions to the frontend.

### Task API endpoints added under apps/api/v1/tasks/
- **Commits**: c6947ce (#14)
- **What happened**: A new `apps/api/v1/tasks/` package was created with `serializers.py` (290 lines, covering Task, TaskExecution, TaskChain), `views.py` (365 lines, with comprehensive CRUD + execution monitoring endpoints), and `urls.py` (57 lines). The task API includes specialized endpoints for task execution history, status updates, and chain management.
- **Insight**: Placing task API endpoints in `apps/api/v1/tasks/` rather than in `apps/tasks/v1/` reflects the initial architecture where API code lived in a centralized `apps/api/` app. This was later migrated so each app owns its own `v1/` directory.

### User serializer password handling made more flexible for API usage
- **Commits**: c6947ce (#14)
- **What happened**: Password field was made optional for updates, password confirmation validation was relaxed (no `confirm_password` required), and user creation was allowed with just a password field. The `BaseViewSet.perform_create()` was updated to check `request.user.is_authenticated` in addition to checking for user presence, preventing `AnonymousUser` from being set as `created_by`.
- **Insight**: The authentication check (`request.user and request.user.is_authenticated`) is important because DRF's `request.user` is never None -- it returns `AnonymousUser` when unauthenticated, which is truthy. Without the `is_authenticated` check, anonymous users would be set as `created_by`.

### Settings API evolved from ConfigView to RESTful SettingView
- **Commits**: 8b4aa31 (#26), f4b136e (#31)
- **What happened**: Phase 1 added a `ConfigView` ViewSet with `list` (GET all config), `update_config` (POST to merge), `reload` (POST to reload from files), and a duplicate `config` method. Phase 2 replaced it with `SettingView` using proper HTTP methods: GET for list, PUT for full update, PATCH for partial update, plus custom actions for reload and rollback. The URL changed from `/api/v1/config/` to `/api/v1/settings/`. Settings updates now validate that keys exist (no creating new settings via API) and log every change with old/new values via `log_setting_change()`.
- **Insight**: The evolution from `ConfigView` (arbitrary config mutation) to `SettingView` (guarded, audited changes with rollback) shows the progressive hardening of a configuration API. The "guard against new setting keys" commit message in #31 reflects a security decision -- the API should only modify existing settings, not create arbitrary new Django settings at runtime.

### SettingSerializer with explicit URL view_name for routed views
- **Commits**: f4b136e (#31)
- **What happened**: The `SettingSerializer` was created as a `BaseModelSerializer` subclass with `extra_kwargs` specifying `"url": {"view_name": "api:v1:settings-detail"}`. The URL routing for settings uses manual `path()` declarations instead of the router's `register()` because settings is treated as a singleton resource requiring custom method mappings (GET list, PUT update, PATCH partial_update on the same endpoint).
- **Insight**: DRF routers assume standard CRUD patterns that don't fit singleton resources well. Manual URL configuration with explicit `as_view()` mappings gives fine-grained control over which HTTP methods map to which viewset actions, at the cost of more verbose URL configuration.

### Tasks API gated behind DEVELOPER_MODE_ENABLED permission
- **Commits**: dbf6fb1 (#65)
- **What happened**: `TaskViewSet` and `TaskExecutionViewSet` switched from `permission_classes = [AllowAny]` (which was marked "Temporary for dashboard access") to `[DeveloperModeRequired]`. The `DeveloperModeRequired` permission class checks `getattr(settings, "DEVELOPER_MODE_ENABLED", False)` and returns 403 with a descriptive message when disabled. The dashboard view got a matching `@require_developer_mode` decorator.
- **Insight**: The `AllowAny` permission on task endpoints was originally a quick fix for dashboard access but persisted for months, creating a security risk. The `DeveloperModeRequired` pattern is a clean way to gate development endpoints: a single setting controls all debug-related access, and the 403 message tells operators how to enable it.

### DAB serializers adopted for core models
- **Commits**: 5fb6ead (#73)
- **What happened**: User/Org/Team serializers were rewritten to use DAB's base serializer classes: `CommonUserSerializer` for User, `NamedCommonModelSerializer` for Organization and Team. The `RelatedAccessMixin` was added to Org and Team serializers for RBAC-aware related links. The custom `BaseModelSerializer` (with auto read-only fields, `CountFieldMixin`) was removed.
- **Insight**: Using DAB's serializer classes instead of custom base classes ensures compatibility with the platform-service-framework patterns and reduces maintenance. The old custom `BaseModelSerializer.__init__` that modified `Meta.read_only_fields` at runtime was replaced by explicit serializer class definitions.

### AssociationResourceRouter for related views
- **Commits**: 5fb6ead (#73)
- **What happened**: The core API router switched from DRF's `DefaultRouter` to DAB's `AssociationResourceRouter`. This router supports `related_views` parameter to auto-generate related resource endpoints (e.g., `/api/v1/organizations/{pk}/teams/`). The URL pattern uses DAB's format rather than custom nested URL definitions.
- **Insight**: DAB's `AssociationResourceRouter` eliminates the need for manual nested router configuration. Declaring `related_views={"teams": (TeamViewSet, "teams")}` on the Organization registration automatically creates the nested endpoint.

### APIRootView for dynamic endpoint discovery
- **Commits**: 52c8fb5 (#75)
- **What happened**: An `APIRootView` class was added that uses Django's `get_resolver()` to introspect URL patterns and dynamically list available API endpoints. It shows only direct children under the current path (not all descendants), skips parameterized paths (containing `<pk>`), and sorts alphabetically. The view is mounted at `/`, `/api/`, and `/api/v1/` via explicit URL patterns that override DAB's empty router views. The `APIRootViewMiddleware` extends this by intercepting 404s on `/`-terminated paths and serving the index if child routes exist.
- **Insight**: Dynamic endpoint discovery means adding a new API app automatically makes it visible in the root endpoint listing without manual registration. The middleware approach (serving index on 404 if children exist) eliminates the need to register root views for every URL prefix level.

### LOADED_APPS dynamic URL loading replaces manual URL registration
- **Commits**: dab7fc1 (#76), b04c0fa (#78)
- **What happened**: App-level `urls.py` files were updated so each app owns its full URL path (e.g., `path("api/v1/tasks/", ...)` instead of being mounted under `path("api/", ...)`). The main `urls.py` iterates `settings.LOADED_APPS` and auto-imports each app's `urls.py`. The test `urls.py` was simplified to use the same pattern. Documentation about the LOADED_APPS mechanism was consolidated into `metrics_service/urls.py` (PR #78), with app-level files referencing back to it.
- **Insight**: Having apps own their full paths (including the `api/v1/` prefix) makes each app's URL structure self-contained and visible in the app's own code. The trade-off is that URL prefix changes require updating every app's `urls.py`, but this is acceptable since the prefix is stable.

### Settings API endpoint removed for security
- **Commits**: 2be6a60 (#185)
- **What happened**: The entire `/api/v1/settings/` endpoint was removed: `SettingViewSet` (122 lines, supported GET/PUT/PATCH/reload/rollback), `SettingSerializer`, `v1/urls.py`, and all associated tests were deleted. The `apps/dynamic_settings/urls.py` was reduced to an empty `urlpatterns = []`. The `apps/dynamic_settings/` app retains its `Setting` model, `utils.py`, and management commands -- only the HTTP API surface was removed.
- **Insight**: Runtime settings endpoints that allow modifying Django settings via HTTP are a security risk in production, especially for a service that runs behind a gateway. Settings are now managed exclusively via management commands (`init-default-settings`, `remove-default-settings`), environment variables, and the DAB feature flags API. Removing the endpoint eliminates an entire attack surface while the underlying model and utilities remain for internal use.

### Dashboard collection status endpoint added
- **Commits**: f539986, fc2815a (no PR numbers -- pushed directly)
- **What happened**: A new `GET /api/v1/dashboard_reports/collection_status/` endpoint was added as `DashboardCollectionStatusViewSet`. It returns three fields: `enabled` (from `get_feature_enabled_from_db("DASHBOARD_COLLECTION")`), `next_run` (from the incremental collection task's `get_next_run_time()`), and `initial_collection_status` (status of the one-shot initial collection task). When `enabled` is false, both `next_run` and `initial_collection_status` are null (task queries are skipped). The viewset uses `BaseAdminViewSet` with `IsSystemAdminOrAuditor` permissions. In a follow-up commit (fc2815a), the dashboard_reports URL routing was refactored to use a version namespace (`v1`), changing URL reversal from `dashboard_reports:collection_status-list` to `v1:collection_status-list`.
- **Insight**: This endpoint gives the UI a single call to check whether dashboard collection is active and what state it's in, avoiding multiple API calls. Notably, both commits were pushed directly without PR numbers, suggesting rapid iteration on a feature branch or direct commits to devel.

### CSV export endpoint added for dashboard reports
- **Commits**: a190ca8 (#182)
- **What happened**: A new `GET /api/v1/dashboard_reports/report/export/` endpoint was added to `DashboardReportViewSet` as a custom `@action`. It supports `export_format` (currently only `csv`, extensible to `pdf`) and `report_type` (`summary`, `roi`, `trends`) query parameters, reusing all existing dashboard filter parameters. The implementation uses a `PassthroughRenderer` (DRF `BaseRenderer` subclass with `media_type="text/csv"`) to bypass DRF serialization and return an `HttpResponse` with `Content-Disposition: attachment`. The `sec2time()` utility was moved from `serializers.py` to a new `apps/dashboard_reports/utils.py` for reuse by both the serializer and the CSV export logic. Pagination query parameters were extracted into a reusable `PAGINATION_QUERY_PARAMETERS` list shared by the `details` and `export` actions.
- **Insight**: Using a `PassthroughRenderer` that returns data as-is is the cleanest DRF pattern for file download endpoints. It avoids fighting DRF's content negotiation while keeping the endpoint inside the viewset (with its permission classes and filter logic). Extracting shared OpenAPI parameter definitions into module-level lists reduces duplication between actions.

## Superseded / Semi-Obsolete

### Monolithic apps/api/ as single API app
- The initial structure had a single `apps/api/` app with all endpoints. This was later reorganized so each domain app (`apps/tasks/`, `apps/core/`, `apps/dynamic_settings/`) owns its own `v1/` API subdirectory.

### ConfigView for runtime configuration
- The `ConfigView` from 8b4aa31 (#26) was replaced by `SettingView` in f4b136e (#31) with DB-backed change tracking, input validation, and rollback capability.

### AllowAny permission on TaskViewSet
- The temporary `AllowAny` permission was replaced by `DeveloperModeRequired` in dbf6fb1 (#65), gating task API access behind the `DEVELOPER_MODE_ENABLED` setting.

### Custom BaseModelSerializer with auto read-only fields and CountFieldMixin
- Replaced in 5fb6ead (#73) by DAB's `NamedCommonModelSerializer` and `CommonUserSerializer` for core models. The tasks app retained a simpler custom `BaseModelSerializer`.

### Manual nested URL configuration for related resources
- Replaced in 5fb6ead (#73) by DAB's `AssociationResourceRouter` which auto-generates related resource endpoints via `related_views` parameter.

### DRF Spectacular @extend_schema decorators on API views
- DRF Spectacular was removed in 5fb6ead (#73). The `@extend_schema` decorators on task views were retained (they're no-ops without drf-spectacular installed) pending migration to `ansible_base.api_documentation`.

### SettingSerializer with HyperlinkedModelSerializer and url field
- Changed to plain `ModelSerializer` in d180ae8 (#74) because the dynamic_settings API uses a singleton pattern without detail endpoints, making the `url` field (which referenced non-existent `api:v1:settings-detail`) unnecessary and broken.

### Settings API (SettingViewSet) at /api/v1/settings/
- The entire settings API surface (SettingViewSet, SettingSerializer, v1 URLs) was removed in 2be6a60 (#185) for security. Settings are now managed via management commands and environment variables only. The Setting model and utils remain for internal use.
