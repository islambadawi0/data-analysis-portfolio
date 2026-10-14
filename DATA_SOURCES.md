# Data provenance and licensing

| Project | Source / citation | Access | Important caveat |
|---|---|---|---|
| P1 Sales | Olist, *Brazilian E-Commerce Public Dataset by Olist*, Kaggle: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce | Kaggle CLI; a Kaggle account/API token may be required | Published license is CC BY-NC-SA 4.0. Attribute the dataset; review the non-commercial and share-alike terms before commercial use or redistribution. |
| P2 Workforce | NYC Open Data, *Citywide Payroll Data (Fiscal Year)*, dataset ID `k397-673e`: https://data.cityofnewyork.us/City-Government/Citywide-Payroll-Data-Fiscal-Year-/k397-673e | Public Socrata API | This records payroll snapshots, not attrition or employee performance. Person names and identifiers are not selected by the downloader. Review NYC Open Data terms for intended reuse. |
| P3 Used cars | Austin Reese, *Craigslist Cars & Trucks*, Kaggle: https://www.kaggle.com/datasets/austinreese/craigslist-carstrucks-data | Kaggle CLI; dataset is large | Listings are scraped marketplace advertisements; asking price is not verified transaction price. Check the current Kaggle dataset license and source-site terms. |
| P4 Churn | Kaggle, *WSDM — KKBox’s Churn Prediction Challenge*: https://www.kaggle.com/competitions/kkbox-churn-prediction-challenge/data | Kaggle competition download; account/API access and acceptance of competition rules required | The source supplies an explicit `is_churn` target and historical transactions/member records. Follow the competition rules and source terms; do not redistribute raw data. |

## Reproducibility and interpretation

The raw source files are not included in this Git repository because some downloads are large, require account-based access, or have source-specific reuse conditions. Run each project's download script to obtain the data from its named publisher. The scripts fail visibly if source files are absent rather than generating replacement observations.

Every analysis should be rerun when its source data changes. Reports must identify the data extraction date, source-period coverage, filters, row counts before/after filtering, and known limitations. Avoid publishing private Kaggle tokens, employee identifiers, or raw data that you are not licensed to redistribute.
