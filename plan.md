# Active plan: Shopify milestone

Target: a demo-ready Shopify seller flow.   

## Previous week — Central history completed

- Migrated 5,586 eBay and 2,859 Chrono24 historical products to Turso.
- Backfilled and validated Chrono24 seller names.
- Added historical CSV exports by seller and for the complete database.
- Added seller selection, scrape timestamps and localized historical dates to the UI/output.
- Skipped known direct-item URLs before making requests or adding duplicate CSV rows.
- Added visible failure rows so unsuccessful URLs remain available for manual review and retry.

## Current baseline

- [x] eBay and Chrono24 scrape into batch CSV files.
- [x] Turso is the central product history.
- [x] Known direct-item URLs are skipped before making a request.
- [x] Historical exports work by seller or for all sellers.
- [x] Historical exports include localized `first_seen` and `Source` columns.
- [ ] Test baseline: 32 passed, 11 failed, 1 deselected. The failures are legacy eBay tests and an outdated column contract.

## Monday — Shopify preparation

### Validate catalog access

- [ ] Select two Shopify sellers from the roadmap.
- [ ] Verify each seller's `/products.json` endpoint.
- [ ] Record product counts, pagination behavior and any redirect/platform mismatch.

### Normalize Shopify URLs
 
- [ ] Accept store, collection and product URLs.
- [ ] Resolve supported inputs to the store origin.
- [ ] Reject unsupported URLs without starting a scrape.
- [ ] Add one focused URL-normalization test.

## Tuesday — Catalog extraction, output, and integration

### Retrieve complete catalogs

- [ ] Fetch `/products.json` pages until pagination ends.
- [ ] Return unique products without a proxy.
- [ ] Validate one multi-page seller and record product/page totals.

### Map products for White Glove

- [ ] Map stable product/variant ID, canonical URL, vendor, title, SKU and price.
- [ ] Return the existing `COLUMNS` in their current order.
- [ ] Use `Missing` for unavailable values; do not guess watch fields.
- [ ] Add one focused multi-variant mapping test.

### Add Shopify to the application

- [ ] Dispatch Shopify URLs from `MainApp.py` without changing eBay or Chrono24 behavior.
- [ ] Include Shopify results in the existing batch CSV flow.
- [ ] Run one seller URL end to end and record the CSV row count.

### Make dedupe source-aware

- [ ] Stop flattening all platform IDs into one global namespace.
- [ ] Keep eBay, Chrono24 and Shopify identities separate through lookup and persistence.
- [ ] Prove that the same stock ID from two sources does not cause a false skip.
- [ ] Repeat the Shopify demo and confirm known products are not duplicated.

## Wednesday — Morning demo

### Pre-demo smoke test and demo gate

- [ ] Application launches.
- [ ] A Shopify seller URL produces a standardized CSV.
- [ ] A repeat run skips known Shopify products.
- [ ] A second validated Shopify seller is ready as backup.
- [ ] Existing focused eBay, Chrono24, dedupe and dispatch tests still pass.
- [ ] Any blocker is recorded with seller, failing step and visible impact.
- [ ] Demonstrate Shopify seller URL → catalog → CSV.
- [ ] Record follow-up questions or requested changes after the demo.


## Thursday — Seller coverage

### Review all 14 Shopify sellers

- [ ] Check every Shopify seller listed in `README.md`.
- [ ] Classify each as supported, redirected/reclassified or blocked.
- [ ] Record endpoint, observed count and evidence.
- [ ] Update public documentation with totals only.

## Friday — Stabilization and handoff

### Make failures visible

- [ ] Handle invalid stores, empty catalogs and request failures through the existing batch failure path.
- [ ] Confirm a bad URL does not stop later URLs in the batch.
- [ ] Confirm failed products are not stored in Turso as successful items.

### Package the milestone

- [ ] Document supported Shopify URL types.
- [ ] Document coverage totals and known exceptions.
- [ ] Run all Shopify tests plus relevant dedupe and dispatch tests.

## Monday — Closeout and next platform

### Close Shopify follow-ups

- [ ] Resolve the highest-impact verified exception, if one remains.
- [ ] Re-run affected sellers.
- [ ] Mark Shopify complete or record the remaining blocker, impact and next action.

### Validate Squarespace before building it

- [ ] Select one Squarespace seller from the roadmap.
- [ ] Verify whether `?format=json` exposes its catalog and required fields.
- [ ] Record sample fields and limitations.
- [ ] Define the smallest confirmed implementation step

## Backlog after Shopify

- [ ] Align or remove the 11 stale eBay tests; establish one current column contract.
- [ ] Add Chrono24 newest-first pagination cutoff using real seller validation.
- [ ] Diagnose remaining `Sin datos` paths using failing page title/HTML evidence.
- [ ] Decide whether normal batch CSVs need `first_seen`; historical exports already provide it.
- [ ] Consider incremental persistence only if interrupted batches are observed in real use.
- [ ] Google Sheets cross-check remains Phase 2; no cloud setup during Shopify work.

## Explicitly closed or removed from the old plan

- Historical retrieval is complete; no open “how to retrieve existing data” question.
- Batch report names are already user-configurable; `{seller}_{date}.csv` is not required.
- A Turso `events` table is deferred; existing logs are sufficient until a concrete reporting need appears.
- Completed migration steps and old pending-commit notes remain available in Git history, not in the active plan.
