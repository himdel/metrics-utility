# Report definition and BI compatibility analysis

This is a source-derived design draft for expressing the reports produced by
`build_report` independently of their current XLSX presentation. It records the
report semantics first, then assesses how well candidate formats can represent
them. The concrete definitions are [CCSPv2](ccspv2.yaml) and
[CCSP v1](ccsp.yaml), [Renewal Guidance](renewal-guidance.yaml), and the
[Segment payload](segment-payload.yaml) with its [JSON Schema](segment-payload.schema.json).
The three report definitions have Tableau and Power BI target profiles; the
Segment payload is a separate JSON analytics contract.

The YAML is **descriptive, not executable**. The existing Python dataframe and
report builders remain the behavior source of truth. A future generator would
need to define and validate a formal expression vocabulary before treating this
file as an executable contract.

## Report pipeline and data sources

`build_report` selects an input adapter, processes inputs into named
dataframes, runs report-specific deduplication, and builds an XLSX workbook.
The report definition should refer to these logical prepared datasets and
record their raw lineage; it should not conflate a Tableau/Power BI connection
with the storage adapter used by the CLI.

| Report | Raw source(s) | Prepared datasets used by report | Special processing |
|---|---|---|---|
| `CCSP` | Daily collected tarballs: `job_host_summary.csv` or `main_indirectmanagednodeaudit.csv`, `main_jobevent.csv`, `main_host.csv` or `main_host_daily.csv`, plus `config.json` metadata | `job_host_summary`, `main_jobevent`, `main_host` | Daily rollups; CCSP deduplication; direct/indirect managed-node split; optional content and inventory tables |
| `CCSPv2` | Same tarball inputs as CCSP, plus `data_collection_status.csv` | `job_host_summary`, `main_jobevent`, `main_host`, `data_collection_status` | Same rollups and deduplication; adds job summary, infrastructure summary, collection-gap analysis, organization detail tabs |
| `RENEWAL_GUIDANCE` | Controller database query over `main_hostmetric`, left-joined to `main_host` | `host_metric` | Query filters by automation or deletion timestamps; dataframe processing then filters on `last_automation`; computes lifecycle and optional ephemeral-host windows |

For the two CCSP reports, the `job_host_summary` dataframe uses
`job_host_summary.csv`; when that file is empty for a batch it falls back to
`main_indirectmanagednodeaudit.csv`. `config.json` supplies `install_uuid` for
the per-install/per-job composite key. The inventory dataframe prefers
`main_host.csv` and falls back to `main_host_daily.csv`. These are separate
logical sources even when one output sheet combines or filters their prepared
rows.

### Requirements visible in the current reports

The report-definition format needs to represent:

- Multiple named data sources, source lineage, per-source availability, and
  report parameters. CCSP uses date-partitioned tarballs; Renewal Guidance reads
  from the Controller database.
- Prepared/derived datasets and their metrics: joins or composite keys,
  deduplication, `count_distinct`, `count`, `sum`, `min`, `max`, grouping,
  filtering, pivots, and calculations.
- Multiple static report pages/tabs, each with its own table(s), column order,
  labels, data types, and display formatting.
- Optional content selected by stable option IDs, including dependencies
  between options. A data-derived fan-out is also needed for one worksheet per
  organization in CCSPv2.
- Runtime labels and values (report period, customer details, SKU, price,
  purchase order, and update date), plus conditional rows and empty-data
  behavior.
- Structured/multi-valued data such as facts, events, and organization sets;
  these are currently JSON-serialized for XLSX output.
- Specialized calculations: the billing-form calculations, indirect-content
  attribution, infrastructure-fact grouping, and collection-status gap/window
  calculations.
- Presentation hints for the existing XLSX form: merged headings, fixed
  widths, row heights, colors, borders, number formats, blank entry rows,
  worksheet names, and formulas. These are materially different from an
  interactive BI dashboard layout.

The current pipeline computes most complex aggregation and deduplication in
Python before the report builder sees the data. To keep Tableau and Power BI
results consistent, a portable definition should declare those semantics once
and either consume the same prepared datasets or compile the semantics into
each platform's model. Re-implementing formulas independently in Tableau
calculations and DAX risks drift.

## Candidate-format compatibility

Legend: **Yes** = the format is designed to express it; **Partial** = possible
with a different representation or custom work; **No** = not a reasonable
fit for this requirement.

| Format | Multiple sources / prepared datasets | Multiple tables and static pages | Data-driven one-tab-per-organization | Aggregations, calculations, filters | Exact XLSX-style form layout | Product-generation and licensing notes |
|---|---|---|---|---|---|---|
| Existing XLSX output | Yes | Yes | Yes | Yes, currently computed in Python/XLSX formulas | Yes | Current behavior baseline; the format doesn’t provide a semantic report definition by itself |
| Microsoft RDL | Yes | Yes | Yes, via grouped/page-broken reports with implementation work | Yes | Yes; strongest fit for paginated/form reports | RDL schemas/docs are public; the Microsoft renderer/authoring products are not an OSS reporting engine |
| JasperReports / JRXML | Yes | Yes | Yes, with report groups/subreports and export setup | Yes | Yes; strong paginated-report fit | [JasperReports Library](https://github.com/Jaspersoft/jasperreports) is LGPL-3.0; review linking, notices, and distribution obligations |
| Eclipse BIRT | Yes | Yes | Partial; depends on report grouping and spreadsheet export behavior | Yes | Yes; strong paginated-report fit | [BIRT](https://github.com/eclipse-birt/birt) is EPL-2.0; review obligations for modified/distributed components |
| Tableau workbook | Yes, through workbook data sources/relationships (with platform constraints) | Yes | Partial: separate worksheets can exist in a generated workbook, but the known vendor library cannot create arbitrary sheets/workbooks; a filter is the product-safe fallback without another supported authoring path | Yes | Partial; table views are not a cell-grid form | [Tableau Document API](https://github.com/tableau/document-api-python) is MIT but officially unsupported and cannot create workbooks from scratch; direct XML generation would be a product risk |
| Power BI project: PBIR + semantic model (TMDL or another supported model source) | Yes, in the semantic model | Yes, as report pages with table visuals | Partial: a generator can expand one static PBIR page per organization; pages don’t appear dynamically after data refresh | Yes, via model measures and report filters | Partial; visuals approximate the form but do not preserve its cell-level layout/formulas | [PBIR is publicly documented](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-report); Microsoft’s [schema repository](https://github.com/microsoft/json-schemas) is MIT. Check the exact model SDK/package terms separately |
| LookML / Looker | Partial; model/explore and connection boundaries apply | Yes, as Looks/dashboard tiles | No as runtime-generated workbook tabs | Yes for a semantic model and dashboard queries | No | Vendor-specific/proprietary platform; not a general report interchange format or an OSS generation library |
| Apache Superset | Partial; charts can use different configured databases, but cross-source modeling is limited | Yes, as dashboard charts | No; use a filter instead | Yes, within configured datasets/charts | No | [Apache Superset](https://github.com/apache/superset) is Apache-2.0; saved dashboard definitions remain Superset-specific |
| Metabase | Partial; cards can use different databases, but a card query is generally source-bound | Yes, as dashboard cards | No; use a filter instead | Yes, within questions/models | No | [Metabase](https://github.com/metabase/metabase) has AGPL source plus separately licensed enterprise code; review embedding/distribution terms |
| XBRL | No for report composition | No | No | Partial for structured financial/business facts and taxonomies | No | A business-facts reporting standard, not a BI layout or dashboard definition |

For the initial Tableau + Power BI scope, the basic CCSPv2 tabular views and
their calculations can be represented in both products. PBIR can also support
generation-time organization-page fan-out using its public schemas; Tableau's
current MIT library does not provide the workbook-authoring operations needed
for that. The PBIR starter uses one long-form organization table. Both BI
products approximate the billing form as visual elements rather than
reproducing its merged cells, fixed blank input rows, and formulas.

### Report-by-target compatibility

| Report | Tableau | Power BI | Main issue to resolve |
|---|---|---|---|
| `CCSP` | Model the organization-level billing table and available detail tables as worksheets/views | Model the billing summary and detail tables as pages/visuals | Exact billing-form layout and the accepted-but-unrendered legacy options |
| `CCSPv2` | Model all views; use an organization filter for detail unless a supported workbook-generation route is found | Model all views; starter uses one organization-filterable detail page | Twelve optional views, conditional columns, structured facts/events, collection-gap calculations, and the external semantic-model binding |
| `RENEWAL_GUIDANCE` | Model summary and node detail; precompute or carefully implement lifecycle/window logic | Model summary and node detail; precompute or implement measures in the semantic model | Direct DB source and the query-vs-dataframe `last_automation` filtering behavior noted below |

## CCSPv2 report contract

The full definition is in [`ccspv2.yaml`](ccspv2.yaml). It includes every
CCSPv2 option accepted by `VALID_SHEETS`, even though the current command default
enables only six options. The default is:

```text
ccsp_summary,managed_nodes,usage_by_organizations,
usage_by_collections,usage_by_roles,usage_by_modules
```

CCSPv2 has 12 option IDs. With all enabled, the builder attempts 11
named/static views plus one additional view for each organization found in
`job_host_summary`:

| Option ID | Current XLSX output | Data / behavior |
|---|---|---|
| `ccsp_summary` | `Usage Reporting` | Billing form; count distinct direct managed hosts and calculate extended price |
| `jobs` | `Jobs` | Group by organization and job template; distinct jobs by `(install_uuid, job_remote_id)` |
| `managed_nodes` | `Managed nodes` | Direct managed-node rollup; includes per-organization last-automation columns when `managed_nodes_by_organizations` is also enabled |
| `indirectly_managed_nodes` | `Indirectly Managed nodes` | Indirect node rollup, including facts, managed-node types, and events |
| `inventory_scope` | `Inventory Scope` | Inventory/host snapshot, including structured facts and optional experimental-dedup fields |
| `infrastructure_summary` | `Infrastructure Summary` | Indirect nodes grouped by infrastructure type, bucket, and device type |
| `usage_by_organizations` | `Usage by organizations` | Direct usage metrics; indirect metrics are added only when `indirectly_managed_nodes` is also enabled |
| `usage_by_collections` | `Usage by collections` | Collection usage; indirect events are attributed to collections when indirect reporting is enabled |
| `usage_by_roles` | `Usage by roles` | Role usage metrics |
| `usage_by_modules` | `Usage by modules` | Module usage metrics |
| `managed_nodes_by_organizations` | One sheet per organization | Per-organization node detail across rows for that org; also changes the `Managed nodes` columns when that option is enabled |
| `data_collection_status` | `Data collection status` | Two tables: missing collection intervals and collection status/timing |

The content-usage sheets are guarded by the builder's `main_jobevent` dataframe
check; the dataframe factory normally supplies an empty dataframe rather than
`None`, so an enabled sheet can still be created with no event rows. The
definition records that distinction as source/empty-state behavior.

### Power BI PBIR starter

[`powerbi/CCSPv2.pbip`](powerbi/CCSPv2.pbip) opens the PBIR report project in
Power BI Desktop. It contains a page for every CCSPv2 option, including
optional views; the data-collection-status page contains both of its tables.
The organization-specific XLSX tabs are represented as one long-form table
with an organization column and filter.

This is a report-only project:
[`definition.pbir`](powerbi/CCSPv2.Report/definition.pbir) contains
workspace, semantic-model name, and ID placeholders in its connection string.
Replace them with a Power BI semantic model that exposes the prepared-view
entities and fields named in `ccspv2.yaml` (for example `ccspv2_jobs` and
`ccspv2_managed_nodes`). This keeps business calculations in the shared
prepared-view layer; PBIR supplies the pages and table visuals. No report data
or semantic model is bundled in this starter.

## Remaining report types

### CCSP

The v1 definition is [`ccsp.yaml`](ccsp.yaml). It reuses three prepared dataset
definitions and six compatible table-view definitions from `ccspv2.yaml`:
`Managed nodes`, `Indirectly Managed nodes`, `Inventory Scope`, `Usage by
collections`, `Usage by roles`, and `Usage by modules`. The reference mechanism
is descriptive for now; it documents which definitions should stay aligned
until a generator or resolver is designed.

CCSP shares the tarball sources and prepared usage/inventory datasets with
CCSPv2, but has a different billing table: its `Usage Reporting` sheet groups
direct managed-node usage by organization and calculates an extended monthly
price per organization. The current report outputs are:

| Option / behavior | Current XLSX output | Data / behavior |
|---|---|---|
| Always built | `Usage Reporting` | Direct rows grouped by organization; managed-node quantity and extended price per organization |
| `managed_nodes` | `Managed nodes` | Direct managed-node detail |
| `indirectly_managed_nodes` | `Indirectly Managed nodes` | Indirect managed-node detail |
| `inventory_scope` | `Inventory Scope` | Host and inventory snapshot |
| `usage_by_collections` | `Usage by collections` | Grouped from `main_jobevent` |
| `usage_by_roles` | `Usage by roles` | Grouped from `main_jobevent` |
| `usage_by_modules` | `Usage by modules` | Grouped from `main_jobevent` |

There are option/output mismatches in the current implementation that the
definition should not hide:

- `infrastructure_summary` is accepted but logs a warning and is skipped.
- `usage_by_organizations` and `managed_nodes_by_organizations` are accepted by
  validation but are not rendered by `ReportCCSP`.
- The main `Usage Reporting` sheet is always built by `ReportCCSP`; its
  `ccsp_summary` option affects extraction selection, not the builder's
  worksheet creation.
- `data_collection_status` is not in the CCSP valid-option set.

The default option list includes `usage_by_organizations`, but that option
does not produce a v1 worksheet. With the current defaults, the outputs are
`Usage Reporting`, `Managed nodes`, `Usage by collections`, `Usage by roles`,
and `Usage by modules` (assuming the inputs are available). V1 does not apply
the organization filter or generate organization-specific sheets.

The shared multi-source and table requirements are compatible with both BI
products; the grouped per-organization billing form and spreadsheet styling
would still need a dashboard/table adaptation.

### Renewal Guidance

Renewal Guidance has one database-backed source: `main_hostmetric` joined to
`main_host`. The collector query selects rows changed within the reporting
window by either `last_automation` or `last_deleted`, but
`DBDataframeHostMetric` then filters the returned dataframe on
`last_automation >= since`. A deletion-only row with an older/null
`last_automation` can therefore be discarded before reporting; this behavior
should be confirmed before translating the renewal report.

The default `DedupRenewal` stage runs after that dataframe filter. It merges
related host-metric rows through hostname, `ansible_host_variable`, product
serial, and machine-ID matches (up to the configured iteration count), then
derives the record-count and comma-separated identity fields used by the detail
sheets. The `renewal-hostname` and `renewal-experimental` strategies are also
available.

Its always-present `Usage Reporting` view summarizes active, deleted, and
optionally ephemeral hosts. `--ephemeral` adds threshold-based classification
and a maximum-concurrent-ephemeral-host calculation over overlapping windows.
When the `managed_nodes` option is enabled, the report also includes node-level
details and deleted-node details; with an ephemeral threshold, it splits active
node details into regular, ephemeral, and ephemeral-usage views.

| Condition | Current XLSX output | Data / behavior |
|---|---|---|
| Always built | `Usage Reporting` | Summary quantities for active hosts, deleted hosts, and—when configured—ephemeral hosts and their maximum concurrent usage |
| `managed_nodes`, without `--ephemeral` | `Managed nodes` | Non-deleted host metrics |
| `managed_nodes`, with `--ephemeral` | `Managed nodes`, `Managed nodes ephemeral`, `Managed nodes ephemeral usage` | Non-ephemeral hosts, ephemeral hosts, and overlapping-window concurrent usage |
| `managed_nodes` | `Deleted Managed nodes` | Deleted host metrics; included whether or not `--ephemeral` is set |

The database query returns hostname, automation/deletion timestamps and
counters, deletion state, inventory-use metadata, serial/machine identifiers,
and selected host variables. The default `DedupRenewal` stage derives the
report fields for hostmetric record counts, host-name lists, host-variable
lists, serial lists, and machine-ID lists; these are not direct SQL columns.
The report derives `days_automated` from the first
and last automation timestamps (clamped to zero) and uses `--ephemeral` as a
day threshold. The threshold classification also compares first automation to
an `now - (threshold - 1 days)` boundary; the concurrent-usage metric scans
overlapping threshold-sized windows beginning at each day in the requested
period.

This report needs date arithmetic, deleted/active classification, structured
host metadata, and a sliding-window maximum. Tableau and Power BI can represent
the calculations, but reproducing current window semantics requires an explicit
model/calculation implementation. A common prepared dataset would be safer
than re-implementing those rules independently in each target.

### Segment payload

The definition and JSON Schema are [`segment-payload.yaml`](segment-payload.yaml)
and [`segment-payload.schema.json`](segment-payload.schema.json). This is a
JSON analytics contract, not a BI report. It captures both the pre-final daily
rollup stored in `DailyMetricsSummary.aggregated_metrics` and the final
`AnonymizedMetricsPayload.anonymized_data` sent through `StorageSegment`.

The production payload extends utility's `AnonymizedPayload` with
`summary_metadata`, `dashboard_telemetry`, and `analytics_usage`. The daily
summary's `config_data`, raw dashboard job records, and raw analytics request
details are not sent. The Segment event/chunk wrapper is described separately
from the JSON Schema, which validates the stored payload before transport
splitting.

## Segment payload contract

`segment-payload.yaml` records the production path discovered across
metrics-utility and metrics-service: collector outputs are prepared and merged
into `DailyMetricsSummary.aggregated_metrics`, passed through
`anonymize_rollups()`, extended by metrics-service with `summary_metadata`,
`dashboard_telemetry`, and `analytics_usage`, then stored as
`AnonymizedMetricsPayload.anonymized_data`. The schema describes this persisted
JSON object before Segment transport chunks it into `track` events.

The precursor is useful to keep beside the payload definition because the daily
rollup is aggregated but not yet the final privacy boundary. It can still
contain values such as host IDs or custom event-content names that are removed
or filtered before transmission. `config_data`, raw dashboard job records, and
analytics request details are outside the Segment payload.

The production wiring is in `metrics-service`; utility `AnonymizedPayload` is
the base type, while the three service-added fields extend the actual stored
payload. The JSON Schema is draft 2020-12 and deliberately allows additional
properties for forward compatibility.

## Source references

- [`build_report.py`](../../metrics_utility/management/commands/build_report.py)
- [`report_ccsp_v2.py`](../../metrics_utility/automation_controller_billing/report/report_ccsp_v2.py)
- [`report_ccsp.py`](../../metrics_utility/automation_controller_billing/report/report_ccsp.py)
- [`report_renewal_guidance.py`](../../metrics_utility/automation_controller_billing/report/report_renewal_guidance.py)
- [`dataframe_engine/factory.py`](../../metrics_utility/automation_controller_billing/dataframe_engine/factory.py)
- [`extract/base.py`](../../metrics_utility/automation_controller_billing/extract/base.py)
- [`management/validation.py`](../../metrics_utility/management/validation.py)
- [`anonymized_rollups.py`](../../metrics_utility/anonymized_rollups/anonymized_rollups.py)
- [`AnonymizedPayload`](../../metrics_utility/anonymized_rollups/types.py)
- [`StorageSegment`](../../metrics_utility/library/storage/segment.py)

Production wiring is in the sibling `metrics-service` repository:
`apps/tasks/collectors/daily_metrics_rollup.py`,
`apps/tasks/collectors/daily_anonymize_and_prepare.py`, and
`apps/tasks/collectors/send_anonymized_to_segment.py`.
- [`anonymization-and-transmission.md`](../../../metrics-service/docs/anonymization-and-transmission.md)
