import pandas as pd

df = pd.read_csv("data/processed/vehicles_clean.csv",
                 usecols=["price", "vehicle_age_at_listing", "odometer", "manufacturer"])
lines = []
lines.append(f"rows: {len(df):,}")
lines.append(f"median price: {df.price.median():,.0f} | mean price: {df.price.mean():,.0f}")
age = df.groupby(pd.cut(df.vehicle_age_at_listing, [-1, 2, 5, 10, 15, 20, 100])).price.agg(["median", "size"])
lines.append("\nmedian price by vehicle age:\n" + age.to_string())
odo = df.groupby(pd.cut(df.odometer, [-1, 25000, 75000, 125000, 175000, 250000, 2000000])).price.agg(["median", "size"])
lines.append("\nmedian price by odometer:\n" + odo.to_string())
pr = df.price.rank()
lines.append("\nSpearman price~age: %.3f | price~odometer: %.3f" % (
    pr.corr(df.vehicle_age_at_listing.rank()),
    pr.corr(df.odometer.rank())))
m = df[df.manufacturer != "Unknown"].groupby("manufacturer").price.agg(["median", "size"])
m = m[m["size"] >= 1000].sort_values("median", ascending=False)
lines.append("\ntop 8 manufacturers by median price (>=1000 listings):\n" + m.head(8).to_string())
lines.append("\nbottom 5:\n" + m.tail(5).to_string())
text = "\n".join(lines)
print(text)
open("outputs/p3_summary.txt", "w", encoding="utf-8").write(text)
