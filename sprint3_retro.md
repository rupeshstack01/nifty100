# Sprint 3 Retrospective — Screener & Peer Comparison

## Sprint
Sprint 3 — Screener & Peer Comparison

## Status
COMPLETED

## Sprint Duration
Days 15–21

---

## 1. Sprint Objective

Sprint 3 focused on building the company screening, ranking, peer comparison,
and visualization capabilities for the Nifty100 financial analytics project.

The sprint delivered:

- Analyst-configurable screener filters
- Six screener presets
- Composite company ranking
- Sector-relative normalization
- Peer-group percentile analysis
- Peer radar charts
- Peer comparison Excel workbook
- Final validation and automated tests

---

## 2. Deliverables Completed

### D15 — Custom Filter Engine

Implemented:

`src/screener/engine.py`

The screener reads thresholds from:

`config/screener_config.yaml`

The configuration contains 15 analyst-editable filter fields.

The engine supports threshold-based filtering without requiring code changes
for threshold modifications.

Status: PASS

---

### D16 — Preset Screeners

Six presets were implemented.

#### Project-specified presets

1. Quality
   - ROE > 15%
   - D/E < 1
   - FCF > 0

2. Value
   - P/E < 20
   - P/B < 3

3. Growth
   - PAT CAGR > 20% over 5 years

4. Dividend
   - Dividend Yield > 2%

#### Engineering-defined presets

5. FCF Quality
   - FCF > 1,000 Cr

6. Profitability
   - NPM > 15%
   - OPM > 20%

The project specification explicitly provided criteria for four named presets.
The remaining two presets were therefore defined from the available dataset
and are documented as engineering-defined rather than project-specified.

Preset results were validated against their configured thresholds.

Status: PASS

---

## 3. D17 — Ranking Engine

Implemented:

`src/screener/ranking.py`

The ranking engine calculates:

- Profitability score
- Growth score
- Valuation score
- Composite score
- Sector rank
- Overall rank
- Score completeness
- Ranking status

Composite weighting:

- Profitability: 50%
- Growth: 30%
- Valuation: 20%

Percentile-based normalization was used to make different financial metrics
comparable.

The engine handles missing component data without fabricating values.

A minimum of two available ranking components is required for a composite
ranking. Records with insufficient information are explicitly labelled.

Status: PASS

---

## 4. D18 — Peer Percentile Engine

Implemented:

`src/analytics/peer.py`

Output:

`data/processed/analytical/peer_percentiles.csv`

Validation results:

- Rows: 56
- Peer groups: 11
- Companies: 56
- Duplicate memberships: 0
- Percentile columns: 14
- Invalid percentile values: 0
- Peer groups with exactly one benchmark: 11/11

Status: PASS

---

## 5. D19 — Radar Charts

Implemented:

`src/analytics/radar.py`

Output:

`reports/radar_charts/`

The radar visualization uses eight axes:

1. ROE
2. NPM
3. OPM
4. Revenue CAGR
5. PAT CAGR
6. EPS CAGR
7. FCF
8. Dividend Yield

Each chart compares the company against its peer-group average.

Validation:

- Peer-group companies: 56
- Charts prepared: 55
- Charts generated: 55
- Charts skipped: 1

The supplied peer-group dataset contains 56 companies rather than the full
92-company universe. One company was skipped because its radar metrics were
insufficient.

The remaining 36 companies do not have supplied peer-group membership.
Peer relationships were not invented to artificially reach 92 charts.

Status: PASS

---

## 6. D20 — Peer Comparison Workbook

Implemented:

`src/analytics/peer_export.py`

Output:

`output/peer_comparison.xlsx`

Workbook validation:

- Sheets: 11
- Companies covered: 56
- Columns per sheet: 30
- Benchmark identification: included
- Percentile colour scales: included

Peer groups:

- Automobiles
- Consumer Finance
- FMCG
- IT Services
- Life Insurance
- Oil & Gas
- Pharmaceuticals
- Power & Utilities
- Private Banks
- Public Sector Banks
- Steel

Status: PASS

---

## 7. D21 — Final Validation

Automated test suite:

`63 passed`

No test failures were reported.

Final output validation confirmed:

- `screener_output.xlsx` exists
- `peer_comparison.xlsx` exists
- `peer_percentiles.csv` exists
- `screener_config.yaml` exists
- 55 radar PNG files exist
- 56 peer companies are represented
- 11 peer groups are represented
- No duplicate company/group memberships exist
- All 14 percentile columns are present
- No invalid percentile values exist
- Every peer group has exactly one benchmark

Status: PASS

---

## 8. What Went Well

- Screener thresholds are configuration-driven.
- Preset filtering was validated against the actual configured rules.
- Ranking uses percentile normalization rather than directly combining
  incompatible financial units.
- Missing data is explicitly handled instead of being silently imputed.
- Peer membership was validated before percentile calculation.
- Radar charts use actual supplied peer groups.
- Excel output was generated with formatting and percentile colour scales.
- Automated tests remained green with 63 passing tests.
- Data limitations were preserved rather than hidden.

---

## 9. Challenges Encountered

### Radar rendering

Initial Plotly/Kaleido rendering required adjustment because the installed
Plotly version did not expose `pio.Kaleido()`.

The implementation was changed to use `pio.write_image()`, after which all
55 eligible radar charts were successfully generated.

### Peer-group coverage

The peer-group source contains 56 companies rather than the complete
92-company universe.

As a result, 55 valid peer radar charts were generated instead of fabricating
peer relationships for companies without supplied peer membership.

### Missing financial metrics

Some companies do not have all financial or market metrics required by every
ranking component.

The ranking engine therefore records data completeness and avoids producing
misleading fully-complete scores when insufficient components are available.

---

## 10. Improvements for Future Sprints

1. Expand peer-group coverage to all 92 companies using an authoritative
   peer-group source or a formally approved methodology.

2. Add additional automated acceptance tests specifically for:
   - all six screener presets
   - ranking weight calculations
   - sector-relative ranking
   - Excel workbook structure
   - radar chart counts

3. Add a formal screener API endpoint as specified by the project roadmap.

4. Add more historical trend-based screening capabilities.

5. Add stronger validation around missing market valuation metrics.

6. Add a formal data-quality report to the final analyst-facing output.

---

## 11. Sprint 3 Final Assessment

Sprint 3 objectives were achieved for the data and peer relationships actually
provided by the project sources.

All implemented Sprint 3 modules passed the available automated and output
validation checks.

### Final Test Result

63 tests passed.

### Final Sprint Status

**SPRINT 3 — COMPLETE**

**Overall Status: PASS**
