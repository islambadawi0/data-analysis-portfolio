# Data Analysis Portfolio

Four reproducible projects on **real public datasets**, covering SQL, Python, Excel, Power BI and machine learning. Every project downloads its data from the original publisher, keeps raw files untouched, documents its cleaning, and reports limitations next to the results.

**Author:** Islam Badawi · [GitHub @islambadawi0](https://github.com/islambadawi0)

**Live portfolio:** [data-analysis-portfolio-sooty.vercel.app](https://data-analysis-portfolio-sooty.vercel.app/)

---

## Projects

| Project | Question it answers | Stack | Headline result |
|---|---|---|---|
| [**P1 — E-commerce Sales Analytics**](p1-sales-analysis-excel-sql/) | What drives sales, and where are the customer and delivery problems? | SQL (SQLite), Python, Excel | R$ 13.2M delivered sales across 96K orders; 5 of 74 categories give ~40% of sales; **97% of customers buy only once** |
| [**P2 — NYC Workforce & Payroll Analytics**](p2-hr-analytics-powerbi/) | How is pay composed, and where does overtime concentrate? | Python, Power BI, DAX | 1.67M payroll records, $34.6B gross pay in FY2025; **5 agencies hold 83% of overtime dollars** |
| [**P3 — Used Vehicle Listings EDA**](p3-used-cars-eda-python/) | What drives used-car asking prices? | Python (pandas, seaborn) | 375K clean listings; median price falls ~85% from new to 16–20-year-old cars (age correlation −0.69) |
| [**P4 — Customer Churn Prediction**](p4-churn-prediction-sklearn/) | Which subscribers will churn next month? | Python, scikit-learn | **ROC-AUC 0.876** on a later-month holdout of 971K members; ~6.5× better than chance in average precision |

---

## Skills demonstrated

- **SQL:** CTEs, window functions (`LAG`, running shares), grain-safe joins, integrity checks
- **Python:** pandas, chunked processing of multi-GB files, scikit-learn pipelines, matplotlib/seaborn, pytest
- **BI:** Excel summary workbook, Power BI model with DAX measures
- **Analytics practice:** cleaning ledgers, leakage-aware temporal validation, metric definitions, honest limitations

---

## Data sources

Raw data is not stored in this repository. See [DATA_SOURCES.md](DATA_SOURCES.md) for each dataset, access method and license caveat.

---

## Running a project

Each project folder has its own `requirements.txt` and a README with the exact commands. Typical flow:

```bash
cd p1-sales-analysis-excel-sql
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
python download_data.py
```

Generated outputs (tables, charts, models) are reproducible from the scripts.
