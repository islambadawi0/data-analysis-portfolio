# Power BI report build guide

## Data model

1. Run `python download_data.py` and `python analysis.py`.
2. In Power BI Desktop, import `data/processed/payroll_clean.csv` and name the table `Payroll`.
3. Set data types: `fiscal_year` whole number; pay and hour columns decimal; `agency_start_date` date; remaining columns text.
4. Do not create a person-level relationship or attrition measure. The public extract intentionally omits personal identifiers.
5. Copy measures from `measures.dax`. Format the pay measures as USD and the share/growth measures as percentages.

## Dashboard layout

### Page 1 — Executive payroll overview

- KPI cards: Reported Gross Pay, Reported Overtime Pay, Overtime Share %, Payroll Records, Agencies.
- Line chart: Reported Gross Pay and Reported Overtime Pay by fiscal year.
- Bar chart: total gross pay by agency.
- Slicers: fiscal year, agency, borough, pay basis.

### Page 2 — Overtime exposure

- Bar chart: overtime share by agency, with a minimum payroll-record threshold to avoid overreacting to tiny groups.
- Scatter plot: overtime pay versus regular pay by agency.
- Matrix: agency × fiscal year, with gross pay, overtime pay, overtime share and YoY change.

### Page 3 — Job and geography mix

- Ranked table of job titles with employee-record count, median base salary, regular pay and overtime pay.
- Borough comparison, with a note that work location is not necessarily employee residence.
- Drill-through page for agency/title detail.

## Interpretation guardrails

- A row is a payroll record for a fiscal year, not necessarily a distinct unique person across multiple fiscal years.
- `Regular Gross Paid`, `Overtime Pay`, and `Other Pay` are reported payment amounts. `Base Salary` may be annual, hourly or daily depending on `pay_basis`.
- Do not compare average base salary across pay bases without restricting to compatible groups.
- The dataset does not support employee attrition, retention, performance, or causal explanations.
- Fiscal-year comparisons should use the fiscal year field, not calendar year inferred from the agency start date.
