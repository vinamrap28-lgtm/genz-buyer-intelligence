"""Step 1 - Generate SYNTHETIC raw datasets (deliberately a bit messy, so the cleaning step has work to do).

buyers_raw.csv      : synthetic, anonymised Gen-Z buyer/lead data (no names/phones/emails)
properties_raw.csv  : stand-in for the public Kaggle property dataset (fictional projects).
                      To use the real Kaggle file, map its columns to the schema in data_dictionary.md
                      and save it as data/properties_raw.csv.
"""
import numpy as np, pandas as pd

rng = np.random.default_rng(42)

CITIES = {  # city: {locality: price per sq ft (INR)}
    "Gurugram": {"Sector 65": 9500, "Dwarka Expressway": 11000, "Sohna Road": 7500, "New Gurgaon": 8000},
    "Noida": {"Sector 150": 7500, "Sector 137": 6500, "Greater Noida West": 5000, "Sector 94": 11000},
    "Bengaluru": {"Whitefield": 8500, "Sarjapur Road": 7800, "Hebbal": 10500, "Electronic City": 6200},
    "Pune": {"Hinjewadi": 7500, "Wakad": 8200, "Kharadi": 9800, "Baner": 11500},
    "Hyderabad": {"Gachibowli": 9500, "Kokapet": 11000, "Kondapur": 8800, "Miyapur": 6000},
    "Mumbai": {"Thane": 13500, "Navi Mumbai": 11500, "Mulund": 18000, "Kandivali": 22000},
}
AMEN = ["WFH Space", "Gym", "Green Area", "Pet Friendly", "Co-working", "Swimming Pool", "Clubhouse", "EV Charging"]
AMEN_NOISY = {"WFH Space": ["WFH Space", "work from home room", "wfh space"], "Gym": ["Gym", "gym", "Fitness Centre"],
              "Green Area": ["Green Area", "park", "Green area"], "Pet Friendly": ["Pet Friendly", "pet friendly"],
              "Co-working": ["Co-working", "coworking", "co working"], "Swimming Pool": ["Swimming Pool", "pool"],
              "Clubhouse": ["Clubhouse", "club house"], "EV Charging": ["EV Charging", "ev charging"]}

# ------------------------------------------------------------------ properties
N_P = 320
names = ["Skyline Residency", "Green Nest", "Urban Haven", "Lakeview Heights", "Orchid Greens", "The Meridian",
         "Palm Terraces", "Pinnacle Park", "Serene Towers", "Harmony Homes", "Zenith Square", "Aster Court"]
rows = []
for i in range(N_P):
    city = rng.choice(list(CITIES), p=[.2, .15, .22, .17, .15, .11])
    loc = rng.choice(list(CITIES[city]))
    bhk = int(rng.choice([1, 2, 3, 4], p=[.15, .4, .35, .1]))
    area = {1: (480, 700), 2: (850, 1200), 3: (1250, 1750), 4: (1900, 2800)}[bhk]
    area = int(rng.integers(*area))
    ptype = rng.choice(["Apartment", "Builder Floor", "Villa"], p=[.75, .15, .10])
    mult = {"Apartment": 1.0, "Builder Floor": 0.95, "Villa": 1.3}[ptype]
    price = area * CITIES[city][loc] * mult * rng.uniform(.9, 1.15) / 1e5  # lakh
    n_am = int(np.clip(rng.normal(2.5 + price / 90, 1.5), 1, 8))
    am = list(rng.choice(AMEN, n_am, replace=False))
    status = rng.choice(["Ready to Move", "Under Construction", "New Launch"], p=[.4, .45, .15])
    pm = 0 if status == "Ready to Move" else int(rng.integers(6, 37) if status == "Under Construction" else rng.integers(24, 49))
    rows.append(dict(property_id=f"P{i+1:04d}", project_name=f"{rng.choice(names)} {loc.split()[0]}", city=city,
                     locality=loc, property_type=ptype, bhk=bhk, area_sqft=area, price_lakh=price,
                     possession_status=status, possession_months=pm, amenities=am))
P = pd.DataFrame(rows)
P["price_raw"] = [f"₹ {p/100:.2f} Cr" if p >= 100 and rng.random() < .8 else f"{p:.0f} L" for p in P.price_lakh]
P["amenities"] = [";".join(rng.choice(AMEN_NOISY[a]) for a in am) for am in P.amenities]
P["bhk"] = [f"{b} BHK" if rng.random() < .8 else f"{b}bhk" for b in P.bhk]
P = P.drop(columns="price_lakh").rename(columns={"price_raw": "price"})
# inject dirt
ix = rng.choice(P.index, 25, replace=False); P.loc[ix, "city"] = P.loc[ix, "city"].replace({"Gurugram": "Gurgaon", "Bengaluru": "Bangalore"})
ix = rng.choice(P.index, 15, replace=False); P.loc[ix, "city"] = P.loc[ix, "city"].str.lower() + " "
ix = rng.choice(P.index, 20, replace=False); P.loc[ix, "property_type"] = P.loc[ix, "property_type"].replace({"Apartment": "Flat", "Builder Floor": "builder floor"})
ix = rng.choice(P.index, 20, replace=False); P.loc[ix, "possession_status"] = P.loc[ix, "possession_status"].replace({"Ready to Move": "RTM", "Under Construction": "UC"})
P.loc[rng.choice(P.index, 6, replace=False), "price"] = np.nan
P.loc[rng.choice(P.index, 2, replace=False), "price"] = "-50 L"
P.loc[rng.choice(P.index, 10, replace=False), "amenities"] = np.nan
P = pd.concat([P, P.sample(8, random_state=1)], ignore_index=True)
P.to_csv("data/properties_raw.csv", index=False)

# ------------------------------------------------------------------ buyers
N_B = 600
INC = ["<5 LPA", "5-10 LPA", "10-15 LPA", "15-25 LPA", "25+ LPA"]; INC_MID = [3, 7.5, 12.5, 20, 30]
SAV = ["<2 L", "2-5 L", "5-10 L", "10-20 L", "20+ L"]; SAV_MID = [1, 3.5, 7.5, 15, 25]
TL = ["0-3 months", "3-6 months", "6-12 months", "12+ months", "Not sure"]
occ = ["Salaried - IT", "Salaried - Non-IT", "Freelancer / Gig", "Startup / Entrepreneur", "Early Career - Other"]
rows = []
for i in range(N_B):
    o = rng.choice(occ, p=[.32, .25, .15, .1, .18])
    ii = int(rng.choice(5, p={"Salaried - IT": [.03, .25, .35, .27, .10]}.get(o, [.2, .38, .25, .12, .05])))
    si = int(np.clip(ii + rng.integers(-1, 3), 0, 4))
    budget = float(np.clip(INC_MID[ii] * rng.uniform(2.5, 6), 25, 400))
    ratio = SAV_MID[si] / budget
    w = [.3, .28, .2, .12, .1] if ratio >= .2 else ([.05, .1, .25, .35, .25] if ratio < .08 else [.14, .2, .26, .24, .16])
    ti = int(rng.choice(5, p=w)); lam = [3.5, 3, 2, 1, .6][ti]
    city = rng.choice(list(CITIES), p=[.2, .13, .27, .15, .15, .10])
    loc = rng.choice(list(CITIES[city])) if rng.random() < .75 else "Flexible"
    ptype = "Villa" if budget > 220 and rng.random() < .4 else rng.choice(["Apartment", "Builder Floor"], p=[.88, .12])
    bhk = 1 if budget < 50 else 2 if budget < 110 else 3 if budget < 220 else int(rng.choice([3, 4]))
    if rng.random() < .15: bhk = int(np.clip(bhk + rng.choice([-1, 1]), 1, 4))
    wfh_bias = o in ("Salaried - IT", "Freelancer / Gig", "Startup / Entrepreneur")
    pool = AMEN[:]; wts = np.array([3 if wfh_bias else 1, 2, 2, 1.5, 2.5 if wfh_bias else .5, 1, 1.2, 1], float)
    am = list(rng.choice(pool, int(rng.integers(0, 6)), replace=False, p=wts / wts.sum()))
    rows.append(dict(buyer_id=f"B{i+1:04d}", age=int(rng.choice(range(21, 30), p=[.08, .1, .12, .14, .14, .14, .12, .09, .07])),
                     occupation_category=o, income_range=INC[ii], savings_range=SAV[si],
                     property_budget=(f"{budget/100:.2f} Cr" if budget >= 100 and rng.random() < .7 else f"{budget:.0f} L"),
                     purchase_timeline=TL[ti], purchase_motive=rng.choice(["Self-use", "Investment", "Both"], p=[.55, .15, .3]),
                     preferred_city=city, preferred_locality=loc, preferred_property_type=ptype, bhk_requirement=f"{bhk} BHK",
                     lifestyle_preferences=";".join(rng.choice(AMEN_NOISY[a]) for a in am),
                     enquiries_count=int(rng.poisson(lam)), brochure_downloads=int(rng.poisson(lam * .7)),
                     events_attended=int(rng.poisson(.15 + lam * .15)),
                     site_visit_interest="Yes" if rng.random() < [.6, .45, .25, .1, .05][ti] else "No"))
B = pd.DataFrame(rows)
# inject dirt
ix = rng.choice(B.index, 30, replace=False); B.loc[ix, "preferred_city"] = B.loc[ix, "preferred_city"].replace({"Gurugram": "Gurgaon", "Bengaluru": "bangalore"})
ix = rng.choice(B.index, 20, replace=False); B.loc[ix, "preferred_city"] = " " + B.loc[ix, "preferred_city"].str.upper()
ix = rng.choice(B.index, 40, replace=False); B.loc[ix, "bhk_requirement"] = B.loc[ix, "bhk_requirement"].str.replace(" BHK", "bhk")
ix = rng.choice(B.index, 25, replace=False); B.loc[ix, "preferred_property_type"] = B.loc[ix, "preferred_property_type"].replace({"Apartment": "Flat"})
ix = rng.choice(B.index, 30, replace=False); B.loc[ix, "purchase_timeline"] = B.loc[ix, "purchase_timeline"].str.title()
for col, n in [("savings_range", 18), ("income_range", 12), ("preferred_property_type", 20), ("bhk_requirement", 20),
               ("lifestyle_preferences", 25), ("preferred_city", 8), ("enquiries_count", 10), ("purchase_timeline", 10)]:
    B.loc[rng.choice(B.index, n, replace=False), col] = np.nan
B.loc[rng.choice(B.index, 3, replace=False), "income_range"] = "-3 LPA"
B.loc[rng.choice(B.index, 4, replace=False), "age"] = [15, 45, 17, 52]
B = pd.concat([B, B.sample(15, random_state=2)], ignore_index=True)
B.to_csv("data/buyers_raw.csv", index=False)
print("buyers_raw", B.shape, "| properties_raw", P.shape)
