"""Core logic: cleaning -> features -> personas -> Move-In Meter -> Home Match Score -> insights.
Every rule is explicit and rule-based (no black-box model) so each classification can be explained.
"""
import re
import numpy as np
import pandas as pd

AMENITIES = ["WFH Space", "Gym", "Green Area", "Pet Friendly", "Co-working", "Swimming Pool", "Clubhouse", "EV Charging"]
BAND_LABELS = ["Affordable (<60L)", "Mid (60-100L)", "Premium (100-200L)", "Luxury (200L+)"]
BAND_EDGES = [0, 60, 100, 200, np.inf]
TIMELINE_MONTHS = {"0-3 months": 3, "3-6 months": 6, "6-12 months": 12, "12+ months": 24, "Not sure": np.nan}
TIMELINE_PTS = {"0-3 months": 25, "3-6 months": 20, "6-12 months": 12, "12+ months": 6, "Not sure": 2}
TIMELINE_CAT = {"0-3 months": "Immediate", "3-6 months": "Immediate", "6-12 months": "Near-term",
                "12+ months": "Exploratory", "Not sure": "Exploratory"}
CITY_ALIASES = {"gurgaon": "Gurugram", "bangalore": "Bengaluru", "bengalore": "Bengaluru", "bombay": "Mumbai"}
PERSONA_RESPONSE = {
    "Ready-to-Move Maker": "Prioritise for a call, property shortlist and site-visit discussion",
    "The Active Planner": "Share personalised options, pricing, possession details and payment plans",
    "The Smart Saver": "Present suitable budget options and basic financial-planning information",
    "The Vibe Seeker": "Highlight relevant amenities, project environment and neighbourhood benefits",
    "The Future Builder": "Share long-term project and locality information",
    "The Early Explorer": "Provide information and maintain low-pressure future engagement",
}


# ------------------------------------------------------------------ parsing helpers
def parse_range(s):
    """'5-10 LPA' / '<5 LPA' / '25+ LPA' -> (min, mid, max). Negative or unparseable -> NaNs."""
    if pd.isna(s):
        return (np.nan,) * 3
    s = str(s).strip().lower()
    if s.startswith("-"):
        return (np.nan,) * 3
    nums = [float(x) for x in re.findall(r"\d+\.?\d*", s)]
    if not nums:
        return (np.nan,) * 3
    if "<" in s:
        return 0.0, nums[0] / 2, nums[0]
    if "+" in s:
        return nums[0], nums[0] * 1.2, nums[0] * 1.5
    if len(nums) >= 2:
        return nums[0], (nums[0] + nums[1]) / 2, nums[1]
    return nums[0], nums[0], nums[0]


def parse_money_lakh(s):
    """'₹ 1.25 Cr' / '85 L' / '85 Lac' -> lakhs (float). Negative -> NaN."""
    if pd.isna(s):
        return np.nan
    t = str(s).lower().replace("₹", "").replace(",", "").strip()
    m = re.search(r"-?\d+\.?\d*", t)
    if not m:
        return np.nan
    v = float(m.group())
    if v <= 0:
        return np.nan
    return v * 100 if "cr" in t else v


def std_city(s):
    if pd.isna(s) or not str(s).strip():
        return "Not Specified"
    k = str(s).strip().lower()
    return CITY_ALIASES.get(k, k.title())


def std_bhk(s):
    if pd.isna(s):
        return np.nan
    m = re.search(r"\d", str(s))
    return float(m.group()) if m else np.nan


def std_ptype(s):
    if pd.isna(s):
        return "Any"
    k = str(s).strip().lower()
    if "villa" in k:
        return "Villa"
    if "floor" in k:
        return "Builder Floor"
    if k in ("flat", "apartment", "apt"):
        return "Apartment"
    return k.title()


def std_possession(s):
    k = str(s).strip().lower()
    if k in ("rtm", "ready", "ready to move", "ready-to-move"):
        return "Ready to Move"
    if k in ("uc", "under construction"):
        return "Under Construction"
    if "launch" in k:
        return "New Launch"
    return k.title()


def std_timeline(s):
    if pd.isna(s):
        return "Not sure"
    k = str(s).strip().lower()
    for key in ("0-3", "3-6", "6-12"):
        if key in k:
            return f"{key} months"
    return "12+ months" if "12" in k else "Not sure"


def parse_amenities(s):
    """Map messy free text to the standard amenity vocabulary."""
    if pd.isna(s):
        return []
    out = set()
    for tok in re.split(r"[;,]", str(s).lower()):
        t = re.sub(r"[^a-z0-9]", "", tok)
        if not t:
            continue
        if "wfh" in t or "workfromhome" in t: out.add("WFH Space")
        elif "gym" in t or "fitness" in t: out.add("Gym")
        elif "green" in t or "park" in t: out.add("Green Area")
        elif "pet" in t: out.add("Pet Friendly")
        elif "cowork" in t: out.add("Co-working")
        elif "pool" in t or "swimming" in t: out.add("Swimming Pool")
        elif "club" in t: out.add("Clubhouse")
        elif t.startswith("ev"): out.add("EV Charging")
    return sorted(out)


def amenity_matrix(series):
    return np.array([[a in lst for a in AMENITIES] for lst in series], dtype=float)


# ------------------------------------------------------------------ cleaning
def clean_properties(raw):
    log = {"rows_raw": len(raw)}
    df = raw.copy()
    df = df.drop_duplicates().drop_duplicates(subset="property_id")
    log["duplicates_removed"] = log["rows_raw"] - len(df)
    df["city"] = df["city"].map(std_city)
    df["locality"] = df["locality"].astype(str).str.strip()
    df["property_type"] = df["property_type"].map(std_ptype)
    df["bhk"] = df["bhk"].map(std_bhk)
    df["possession_status"] = df["possession_status"].map(std_possession)
    df["price_lakh"] = df["price"].map(parse_money_lakh)
    n = len(df)
    df = df.dropna(subset=["price_lakh"])
    log["invalid_or_missing_price_removed"] = n - len(df)
    df["possession_months"] = np.where(df.possession_status == "Ready to Move", 0,
                                       df.possession_months.fillna(df.possession_months.median()))
    df["amenity_list"] = df["amenities"].map(parse_amenities)
    df["price_band"] = pd.cut(df.price_lakh, BAND_EDGES, labels=BAND_LABELS, right=False)
    df["price_per_sqft"] = (df.price_lakh * 1e5 / df.area_sqft).round(0)
    df["amenity_count"] = df.amenity_list.str.len()
    log["rows_clean"] = len(df)
    return df.drop(columns=["price", "amenities"]).reset_index(drop=True), log


def clean_buyers(raw):
    log = {"rows_raw": len(raw)}
    df = raw.copy()
    df = df.drop_duplicates().drop_duplicates(subset="buyer_id")
    log["duplicates_removed"] = log["rows_raw"] - len(df)
    n = len(df)
    df = df[df.age.between(18, 32)]
    log["invalid_age_removed"] = n - len(df)
    for col, pre in (("income_range", "income"), ("savings_range", "savings")):
        r = df[col].map(parse_range)
        for j, suf in enumerate(("min", "mid", "max")):
            df[f"{pre}_{suf}"] = r.map(lambda t: t[j])
    log["invalid_income_set_missing"] = int((df.income_range.astype(str).str.startswith("-")).sum())
    df["budget_lakh"] = df.property_budget.map(parse_money_lakh)
    n = len(df)
    df = df.dropna(subset=["budget_lakh"])
    log["missing_budget_removed"] = n - len(df)
    df["preferred_city"] = df.preferred_city.map(std_city)
    df["preferred_locality"] = df.preferred_locality.fillna("Flexible").astype(str).str.strip()
    df["preferred_property_type"] = df.preferred_property_type.map(std_ptype)
    df["bhk"] = df.bhk_requirement.map(std_bhk)
    df["purchase_timeline"] = df.purchase_timeline.map(std_timeline)
    df["amenity_list"] = df.lifestyle_preferences.map(parse_amenities)
    # preference clarity BEFORE imputation: how many of 6 requirement fields did the buyer actually specify?
    df["clarity_ratio"] = (
        1 + (df.preferred_city != "Not Specified") + (df.preferred_locality != "Flexible")
        + (df.preferred_property_type != "Any") + df.bhk.notna() + (df.amenity_list.str.len() > 0)) / 6
    # imputation (documented in the report)
    for c in ("income_mid", "savings_mid"):
        log[f"{c}_imputed"] = int(df[c].isna().sum())
        df[c] = df[c].fillna(df[c].median())
    for c in ("enquiries_count", "brochure_downloads", "events_attended"):
        df[c] = df[c].fillna(df[c].median()).astype(int)
    df["site_visit_interest"] = df.site_visit_interest.fillna("No")
    log["rows_clean"] = len(df)
    return df.drop(columns=["property_budget", "bhk_requirement"]).reset_index(drop=True), log


# ------------------------------------------------------------------ features
def add_features(b, p):
    b = b.copy()
    b["budget_category"] = pd.cut(b.budget_lakh, BAND_EDGES, labels=BAND_LABELS, right=False)
    b["savings_to_budget"] = (b.savings_mid / b.budget_lakh).round(3)
    b["timeline_category"] = b.purchase_timeline.map(TIMELINE_CAT)
    b["engagement_score"] = (np.minimum(b.enquiries_count, 5) / 5 * 25 + np.minimum(b.brochure_downloads, 3) / 3 * 25
                             + np.minimum(b.events_attended, 2) / 2 * 20 + (b.site_visit_interest == "Yes") * 30).round(1)
    b["budget_to_income"] = (b.budget_lakh / b.income_mid).round(2)  # budget as multiple of annual income
    b["affordability"] = pd.cut(b.budget_to_income, [0, 4, 5.5, np.inf], labels=["Comfortable", "Stretch", "High stretch"])
    for a in AMENITIES:
        b["want_" + a] = b.amenity_list.map(lambda l: int(a in l))
    b["lifestyle_count"] = b.amenity_list.str.len()
    # inventory availability: properties in preferred city (any city if unspecified) priced <= 110% of budget
    avail = []
    for _, r in b.iterrows():
        pool = p if r.preferred_city == "Not Specified" else p[p.city == r.preferred_city]
        avail.append(int((pool.price_lakh <= r.budget_lakh * 1.1).sum()))
    b["inventory_in_budget"] = avail
    return b


# ------------------------------------------------------------------ Move-In Meter + personas
def move_in_meter(b):
    b = b.copy()
    b["fin_savings"] = (15 * np.minimum(b.savings_to_budget / 0.20, 1)).round(1)             # down-payment readiness
    b["fin_afford"] = (15 * np.clip((7 - b.budget_to_income) / 4, 0, 1)).round(1)            # budget vs income
    b["fin_inventory"] = np.select([b.inventory_in_budget >= 3, b.inventory_in_budget >= 1], [10, 5], 0)
    b["pts_financial"] = b.fin_savings + b.fin_afford + b.fin_inventory                     # /40
    b["pts_timeline"] = b.purchase_timeline.map(TIMELINE_PTS)                               # /25
    b["pts_engagement"] = (b.engagement_score / 100 * 20).round(1)                          # /20
    b["pts_clarity"] = (b.clarity_ratio * 15).round(1)                                      # /15
    b["move_in_score"] = (b.pts_financial + b.pts_timeline + b.pts_engagement + b.pts_clarity).round(1)
    b["readiness_level"] = pd.cut(b.move_in_score, [-1, 39.999, 69.999, 101],
                                  labels=["Early-stage", "Medium", "High"])
    return b


def assign_persona(b):
    """First matching rule wins (order matters and is documented in the README)."""
    b = b.copy()
    conds = [
        (b.move_in_score >= 70) & (b.timeline_category == "Immediate") & (b.engagement_score >= 50),
        (b.savings_to_budget < 0.06) | ((b.affordability == "High stretch") & (b.savings_to_budget < 0.10)),
        (b.purchase_motive != "Self-use") & (b.move_in_score >= 45),
        (b.lifestyle_count >= 3) & (b.preferred_locality != "Flexible") | (b.lifestyle_count >= 4),
        (b.engagement_score >= 25) & (b.timeline_category != "Exploratory"),
    ]
    names = ["Ready-to-Move Maker", "The Smart Saver", "The Future Builder", "The Vibe Seeker", "The Active Planner"]
    b["persona"] = np.select(conds, names, "The Early Explorer")
    b["suggested_action"] = b.persona.map(PERSONA_RESPONSE)
    return b


# ------------------------------------------------------------------ Home Match Score
def match_buyers(b, p, top_n=3):
    """Home Match Score = .35 Budget + .25 Neighbourhood + .15 Space + .15 Vibe + .10 Move-clock (each 0-1, x100)."""
    B = b.budget_lakh.to_numpy(dtype=float)[:, None]; P = p.price_lakh.to_numpy(dtype=float)[None, :]
    budget = np.where(P > B, np.clip(1 - (P / B - 1) / 0.25, 0, 1), np.where(P < 0.5 * B, 0.8, 1.0))
    bc = b.preferred_city.to_numpy(dtype=object)[:, None]; pc = p.city.to_numpy(dtype=object)[None, :]
    bl = b.preferred_locality.to_numpy(dtype=object)[:, None]; pl = p.locality.to_numpy(dtype=object)[None, :]
    same_city = bc == pc
    hood = np.where(bc == "Not Specified", 0.5,
                    np.where(same_city & (bl == pl), 1.0, np.where(same_city & (bl == "Flexible"), 0.8, np.where(same_city, 0.5, 0.0))))
    bt = b.preferred_property_type.to_numpy(dtype=object)[:, None]; pt = p.property_type.to_numpy(dtype=object)[None, :]
    type_fit = np.where(bt == "Any", 0.5, (bt == pt) * 0.5)
    bb = b.bhk.to_numpy(dtype=float)[:, None]; pb = p.bhk.to_numpy(dtype=float)[None, :]
    diff = np.abs(bb - pb)
    bhk_fit = np.where(np.isnan(bb), 0.35, np.where(diff == 0, 0.5, np.where(diff == 1, 0.1, 0.0)))
    space = type_fit + bhk_fit
    W = amenity_matrix(b.amenity_list); A = amenity_matrix(p.amenity_list)
    nw = W.sum(1)[:, None]
    vibe = np.where(nw == 0, 0.5, (W @ A.T) / np.maximum(nw, 1))
    T = b.purchase_timeline.map(TIMELINE_MONTHS).to_numpy(dtype=float)[:, None]; pm = p.possession_months.to_numpy(dtype=float)[None, :]
    clock = np.where(np.isnan(T), 0.7, np.where(pm <= T, 1.0, np.clip(1 - (pm - T) / 18, 0, 1)))
    comps = {"budget_fit": budget * 35, "neighbourhood_match": hood * 25, "space_fit": space * 15,
             "vibe_fit": vibe * 15, "move_clock_fit": clock * 10}
    total = sum(comps.values())
    rows = []
    for i in range(len(b)):
        for rank, j in enumerate(np.argsort(-total[i])[:top_n], 1):
            r = {"buyer_id": b.buyer_id.iloc[i], "rank": rank, "property_id": p.property_id.iloc[j],
                 "project_name": p.project_name.iloc[j], "city": p.city.iloc[j], "locality": p.locality.iloc[j],
                 "property_type": p.property_type.iloc[j], "bhk": int(p.bhk.iloc[j]), "price_lakh": p.price_lakh.iloc[j],
                 "possession_status": p.possession_status.iloc[j], "possession_months": p.possession_months.iloc[j],
                 **{k: round(float(v[i, j]), 1) for k, v in comps.items()}, "home_match_score": round(float(total[i, j]), 1)}
            r["why"] = explain(b.iloc[i], p.iloc[j], r)
            rows.append(r)
    return pd.DataFrame(rows)


def fmt_lakh(x):
    return f"₹{x/100:.2f} Cr" if x >= 100 else f"₹{x:.0f} L"


def explain(buyer, prop, r):
    parts = []
    over = prop.price_lakh / buyer.budget_lakh - 1
    parts.append(f"Price {fmt_lakh(prop.price_lakh)} is within your {fmt_lakh(buyer.budget_lakh)} budget" if over <= 0
                 else f"Price {fmt_lakh(prop.price_lakh)} is {over:.0%} above the {fmt_lakh(buyer.budget_lakh)} budget")
    if buyer.preferred_city == "Not Specified":
        parts.append("no city preference stated")
    elif prop.city == buyer.preferred_city:
        parts.append(f"{prop.locality} is your preferred locality" if prop.locality == buyer.preferred_locality
                     else f"in your preferred city ({prop.city})")
    else:
        parts.append(f"different city ({prop.city} vs {buyer.preferred_city})")
    parts.append(f"{int(prop.bhk)} BHK {prop.property_type}" + (" matches your BHK need" if prop.bhk == buyer.bhk else (f" (you asked for {int(buyer.bhk)} BHK)" if pd.notna(buyer.bhk) else "")))
    wanted = [a for a in buyer.amenity_list]
    got = [a for a in wanted if a in prop.amenity_list]
    if wanted:
        parts.append(f"has {len(got)}/{len(wanted)} wanted amenities" + (f" ({', '.join(got)})" if got else ""))
    parts.append("ready to move" if prop.possession_months == 0 else f"possession in ~{int(prop.possession_months)} months")
    return "; ".join(parts) + "."


# ------------------------------------------------------------------ insights
def demand_vs_inventory(b, p):
    """Share of buyer demand vs share of inventory for the same category: positive gap = under-supplied."""
    out = {}
    for name, bcol, pcol in (("City", "preferred_city", "city"), ("Budget band", "budget_category", "price_band"),
                             ("BHK", "bhk", "bhk"), ("Property type", "preferred_property_type", "property_type")):
        d = b[bcol].value_counts(normalize=True).rename("demand_share")
        s = p[pcol].value_counts(normalize=True).rename("inventory_share")
        t = pd.concat([d, s], axis=1).fillna(0)
        t["gap"] = (t.demand_share - t.inventory_share).round(3)
        t.index = t.index.astype(str)
        out[name] = t.drop(index=["Any", "Not Specified", "nan"], errors="ignore").round(3)
    dem = b[[f"want_{a}" for a in AMENITIES]].mean(); dem.index = AMENITIES
    sup = pd.Series({a: p.amenity_list.map(lambda l: a in l).mean() for a in AMENITIES})
    t = pd.concat([dem.rename("demand_share"), sup.rename("inventory_share")], axis=1); t["gap"] = (t.demand_share - t.inventory_share).round(3)
    out["Amenity"] = t.round(3)
    return out


def run_all(buyers_path="data/buyers_raw.csv", props_path="data/properties_raw.csv"):
    pr, plog = clean_properties(pd.read_csv(props_path))
    br, blog = clean_buyers(pd.read_csv(buyers_path))
    b = assign_persona(move_in_meter(add_features(br, pr)))
    m = match_buyers(b, pr)
    return {"buyers": b, "properties": pr, "matches": m, "buyer_log": blog, "property_log": plog,
            "gaps": demand_vs_inventory(b, pr)}


# ------------------------------------------------------------------ buyer-facing helpers
def build_raw(p):
    """Turn a buyer's form answers (numeric/clean) into one raw-style row the normal pipeline can process."""
    nan = np.nan
    return pd.DataFrame([{
        "buyer_id": p.get("buyer_id", "LIVE-0000"), "age": p["age"], "occupation_category": p.get("occupation", "Not stated"),
        "income_range": f"{p['income_lpa']} LPA", "savings_range": f"{p['savings_lakh']} L",
        "property_budget": f"{p['budget_lakh']} L", "purchase_timeline": p["timeline"],
        "purchase_motive": p.get("motive", "Self-use"),
        "preferred_city": nan if p["city"] in (None, "Not sure yet") else p["city"],
        "preferred_locality": "Flexible" if p["locality"] in (None, "Flexible") else p["locality"],
        "preferred_property_type": nan if p["ptype"] == "Any" else p["ptype"],
        "bhk_requirement": nan if p["bhk"] == "Any" else f"{p['bhk']} BHK",
        "lifestyle_preferences": ";".join(p["amenities"]) if p["amenities"] else nan,
        "enquiries_count": 1, "brochure_downloads": int(bool(p.get("brochure"))), "events_attended": 0,
        "site_visit_interest": "Yes" if p.get("site_visit") else "No"}])


def score_single(p, props, top_n=3):
    """Run ONE buyer through the exact same pipeline as the batch. Returns (buyer_row, top_matches_df)."""
    b, _ = clean_buyers(build_raw(p))
    b = assign_persona(move_in_meter(add_features(b, props)))
    return b.iloc[0], match_buyers(b, props, top_n=top_n)


def what_if(p, props):
    """Re-score the buyer under small changes so they (and the builder) see which levers matter."""
    base, bm = score_single(p, props)
    scen = {
        "Add ₹5 L to savings": {"savings_lakh": p["savings_lakh"] + 5},
        "Add ₹10 L to savings": {"savings_lakh": p["savings_lakh"] + 10},
        "Raise budget by 15%": {"budget_lakh": round(p["budget_lakh"] * 1.15)},
        "Lower budget by 15%": {"budget_lakh": round(p["budget_lakh"] * 0.85)},
        "Book a site visit + get brochure": {"site_visit": True, "brochure": True},
        "Choose a specific locality": {"locality": _first_locality(p, props)},
    }
    rows = [{"Scenario": "Today (your answers)", "Move-In score": base.move_in_score, "Δ score": 0.0,
             "Best match": bm.home_match_score.iloc[0], "Δ match": 0.0, "Persona": base.persona}]
    for name, chg in scen.items():
        s, m = score_single({**p, **chg}, props)
        rows.append({"Scenario": name, "Move-In score": s.move_in_score, "Δ score": round(s.move_in_score - base.move_in_score, 1),
                     "Best match": m.home_match_score.iloc[0], "Δ match": round(m.home_match_score.iloc[0] - bm.home_match_score.iloc[0], 1),
                     "Persona": s.persona})
    return pd.DataFrame(rows)


def _first_locality(p, props):
    pool = props[props.city == p["city"]] if p["city"] not in (None, "Not sure yet") else props
    return pool.locality.value_counts().index[0]
