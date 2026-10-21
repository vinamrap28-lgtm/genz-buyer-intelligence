"""Run the full pipeline, save cleaned data + EDA charts.   Usage: python run_analysis.py"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import pipeline as pl

sns.set_theme(style="whitegrid", palette="deep")
R = pl.run_all()
b, p, m = R["buyers"], R["properties"], R["matches"]
OUT = "outputs/charts/"

# ---- save cleaned data with derived fields
b.drop(columns=["amenity_list"]).to_csv("data/buyers_clean.csv", index=False)
p.assign(amenities=p.amenity_list.map(";".join)).drop(columns=["amenity_list"]).to_csv("data/properties_clean.csv", index=False)
m.to_csv("data/top3_recommendations.csv", index=False)
print("Cleaning log (buyers):", R["buyer_log"]); print("Cleaning log (properties):", R["property_log"])


def save(name):
    plt.tight_layout(); plt.savefig(OUT + name, dpi=130); plt.close()


# ---- EDA (section 7.4 of the proposal)
fig, ax = plt.subplots(1, 3, figsize=(14, 4))
sns.histplot(b.income_mid, bins=15, ax=ax[0]).set(title="Income (LPA, range midpoint)")
sns.histplot(b.savings_mid, bins=15, ax=ax[1]).set(title="Savings (lakh, range midpoint)")
sns.histplot(b.budget_lakh, bins=20, ax=ax[2]).set(title="Property budget (lakh)")
save("01_income_savings_budget.png")

sns.scatterplot(data=b, x="income_mid", y="budget_lakh", hue="savings_to_budget", size="savings_mid", palette="viridis")
plt.title("Income vs housing budget (colour = savings-to-budget)"); save("02_income_vs_budget.png")

fig, ax = plt.subplots(1, 3, figsize=(15, 4))
b.preferred_city.value_counts().plot.bar(ax=ax[0], title="Preferred city")
b.bhk.value_counts().sort_index().plot.bar(ax=ax[1], title="BHK requirement")
b.purchase_timeline.value_counts().reindex(list(pl.TIMELINE_MONTHS)).plot.bar(ax=ax[2], title="Purchase timeline")
save("03_city_bhk_timeline.png")

am = b[[f"want_{a}" for a in pl.AMENITIES]].sum(); am.index = pl.AMENITIES
am.sort_values().plot.barh(title="Most wanted lifestyle amenities"); save("04_amenity_demand.png")

sns.boxplot(data=b, x="readiness_level", y="engagement_score", order=["Early-stage", "Medium", "High"])
plt.title("Engagement score by readiness level"); save("05_engagement_by_readiness.png")

ct = pd.crosstab(b.budget_category, b.preferred_property_type)
sns.heatmap(ct, annot=True, fmt="d", cmap="Blues"); plt.title("Budget category x property type"); save("06_budget_vs_type_heatmap.png")

# ---- personas / readiness / matching
b.persona.value_counts().plot.barh(title="Buyer personas"); save("07_personas.png")
sns.histplot(data=b, x="move_in_score", hue="readiness_level", bins=25, multiple="stack")
plt.title("Move-In Meter distribution"); save("08_move_in_meter.png")
heat = b.groupby("persona")[[f"want_{a}" for a in pl.AMENITIES]].mean(); heat.columns = pl.AMENITIES
sns.heatmap(heat, annot=True, fmt=".2f", cmap="YlGnBu"); plt.title("Amenity preference by persona"); save("09_persona_amenity_heatmap.png")
sns.boxplot(data=m, x="rank", y="home_match_score"); plt.title("Home Match Score of top-3 recommendations"); save("10_match_scores.png")

fig, ax = plt.subplots(1, 4, figsize=(18, 4))
for a, (k, v) in zip(ax, list(R["gaps"].items())[:4]):
    v[["demand_share", "inventory_share"]].plot.bar(ax=a, title=f"{k}: demand vs inventory")
save("11_demand_vs_inventory.png")

print("\nPersonas:\n", b.persona.value_counts().to_string())
print("\nReadiness:\n", b.readiness_level.value_counts().to_string())
print("\nMost under-supplied (demand share - inventory share):")
for k, v in R["gaps"].items():
    print(f"  {k}: {v.gap.idxmax()} ({v.gap.max():+.1%})")
print("\nProperties most often in top-3:\n", m.groupby(["property_id", "project_name"]).size().nlargest(5).to_string())
