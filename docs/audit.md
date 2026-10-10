# Implementation audit

Baseline inspected 2026-10-10: local four-file plugin wrapper, upstream package 5.4.0, source revision `1a92439c4380cca4d6dfa69f962e41c2c84af692`. This report contains no credentials or personal activity records.

## Findings and disposition

| Finding | Evidence | Disposition |
|---|---|---|
| Nonportable interpreter path | Cached MCP manifest used a user-specific Windows virtualenv | Replaced with uv + plugin-root project + lock |
| Undeclared backend dependency | Four-file wrapper imported a separate local checkout | External exact-version dependency in project manifest |
| Windows-only credential configuration | keyring service launcher and interactive script | Cross-platform secure-backend selection; explicit env fallback |
| Zero/false values dropped | Synthetic ctl=atl=tsb=steps=0 yielded only date; activity duration/load=0 omitted | Replaced activity/wellness raw adapters preserve values |
| Wrong intensity semantic name | API icu_intensity=85 emitted intensity_factor=85 | Old value retained/deprecated; explicit percent/ratio added |
| Weighted power not mapped | Synthetic icu_weighted_avg_watts was absent from activity summary | Wrapper maps raw field; legacy search untouched |
| Server date used | Upstream reads use datetime.now/date.today | Replaced reads/workflows use configured/athlete timezone |
| No completeness signal | Capped activity lists drop oldest rows | Wrapper split fetching and explicit incomplete reasons |
| No preview transaction model | Direct calendar create/bulk/apply | New local preview snapshots and per-item verified commit |
| Binary output and overwrite | Base64 response or open(path,'wb') | Downloads replaced with bounded directory/exclusive writes |
| Mutating verification prompts | verify_setup/multi-athlete included lifecycle writes/deletes | Replaced with read-only prompts |
| Unredacted upstream API errors | HTTP error contains response body | Wrapper middleware redacts secret and omits upstream error body |

## Remaining upstream boundaries

The wrapper deliberately does not fork upstream. Unreplaced search, curve, fitness, calendar, library and management functions keep upstream parsing, date logic, request handling and output rounding. Metadata normalization can clarify intensity units but cannot recover dropped zero values. Rate-limit retries apply to wrapper-owned API calls, not every upstream call. Legacy create/update/bulk/apply tools remain direct writes and do not gain preview guarantees; bundled planning skill selects the new preview/commit tools. These distinctions are public compatibility boundaries, not claimed repairs.

The API's raw fields may evolve. Zone structures are handled when recognizable; no unsupported platform readiness calculation is introduced. Local workout checks validate obvious syntax shape, not the complete platform DSL. UID-upsert prevents retries from duplicating a logical event, but cannot make remote writes transactional. Retained preview history includes old dates when a managed session moves; keep this local history when managing the same plan across machines. A fresh installation cannot discover a matching UID outside the requested date window without that history. Preview checks reduce conflicts; the API does not expose a conditional-write transaction, so changes made by another client between check and POST are a remaining race. The plugin does not bypass subscription or source restrictions.

## Website assessment

Read-only browser review confirmed activities, fitness CTL/ATL/form, running pace/critical speed and best efforts, indoor/outdoor totals and zone time, activity comparison, workout library, annual plan entry, routes, and social/settings navigation. The inspected account showed subscription gates for route matching and annual-plan builder. No paid subscription was purchased and no page settings or training records were intentionally changed.

The public API had 149 documented HTTP operations across activity, athlete, wellness, event, library, sport, gear, custom-item, route, weather and chat groups. MCP tool count is not endpoint coverage: some tools compose multiple calls and some documented operations are intentionally outside v1.

Sources: [OpenAPI](https://intervals.icu/api/v1/docs), [API access and source restrictions](https://forum.intervals.icu/t/api-access-to-intervals-icu/609), [API terms](https://forum.intervals.icu/t/intervals-icu-api-terms-and-conditions/114087), [upstream](https://github.com/hhopke/intervals-icu-mcp), [portable plugin packaging](https://developers.openai.com/plugins/build/plugins).

