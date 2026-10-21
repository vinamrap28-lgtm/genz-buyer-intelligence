# Data Dictionary

**Synthetic** = generated for this academic project. **Derived** = computed by Python. No names, phone numbers, emails or addresses exist anywhere.

## buyers_raw.csv (synthetic) -> buyers_clean.csv
| Field | Type | Description |
|---|---|---|
| buyer_id | str | Anonymous ID (B0001...) |
| age | int | 21-29 (rows outside 18-32 removed as invalid) |
| occupation_category | str | Salaried-IT / Non-IT / Freelancer / Startup / Early career |
| income_range, savings_range | str | Bands e.g. "5-10 LPA", "2-5 L" |
| property_budget | str | e.g. "85 L", "1.2 Cr" -> `budget_lakh` |
| purchase_timeline | str | 0-3, 3-6, 6-12, 12+ months, Not sure |
| purchase_motive | str | Self-use / Investment / Both (added to support the *Future Builder* persona) |
| preferred_city, preferred_locality | str | Locality may be "Flexible" |
| preferred_property_type, bhk_requirement | str | Apartment / Builder Floor / Villa; 1-4 BHK |
| lifestyle_preferences | str | Free text amenities, mapped to 8 standard amenities |
| enquiries_count, brochure_downloads, events_attended, site_visit_interest | int/str | Engagement indicators |

## Derived buyer fields
| Field | Rule |
|---|---|
| income_mid / savings_mid | Range midpoint (<x -> x/2; x+ -> 1.2x) |
| budget_category | Affordable <60L, Mid 60-100L, Premium 100-200L, Luxury 200L+ |
| savings_to_budget | savings_mid / budget_lakh (0.20 ~ 20% down payment) |
| timeline_category | <=6 months Immediate; 6-12 Near-term; 12+/Not sure Exploratory |
| engagement_score (0-100) | enquiries (cap 5) 25 + brochures (cap 3) 25 + events (cap 2) 20 + site-visit 30 |
| budget_to_income / affordability | budget / annual income: <=4 Comfortable, <=5.5 Stretch, else High stretch |
| want_<amenity> | 1 if the buyer wants it (8 amenities) |
| clarity_ratio | Share of 6 requirement fields specified (budget, city, locality, type, BHK, lifestyle) |
| inventory_in_budget | Properties in preferred city priced <= 110% of budget |
| move_in_score, readiness_level | See below |
| persona, suggested_action | See below |

## properties_raw.csv (stand-in for public Kaggle data) -> properties_clean.csv
property_id, project_name (fictional), city, locality, property_type, bhk, area_sqft, price (raw string -> `price_lakh`), possession_status (Ready to Move / Under Construction / New Launch), possession_months, amenities.
Derived: price_band, price_per_sqft, amenity_count.

## Move-In Meter (100 pts)
- Financial capacity **40** = savings readiness 15 (`min(savings_to_budget/0.20,1)`) + affordability 15 (budget/income 3x -> full, 7x -> zero) + inventory alignment 10 (>=3 matching units 10, 1-2 -> 5, 0 -> 0)
- Purchase timeline **25**: 0-3m 25 / 3-6m 20 / 6-12m 12 / 12+m 6 / Not sure 2
- Engagement **20** = engagement_score x 0.2
- Preference clarity **15** = clarity_ratio x 15
- Levels: >=70 High, 40-69 Medium, <40 Early-stage

## Personas (first matching rule wins)
1. Ready-to-Move Maker: score >=70, Immediate timeline, engagement >=50
2. The Smart Saver: savings_to_budget <0.06, or High-stretch affordability with ratio <0.10
3. The Future Builder: motive is Investment/Both and score >=45
4. The Vibe Seeker: >=4 amenities wanted, or >=3 with a specific locality
5. The Active Planner: engagement >=25 and not Exploratory timeline
6. The Early Explorer: everyone else

## Home Match Score (100 pts, each component 0-1 x weight)
- Budget Fit **35**: price <= budget -> 1 (0.8 if under half the budget); above budget drops linearly to 0 at +25%
- Neighbourhood **25**: same locality 1.0; same city + flexible locality 0.8; same city 0.5; other city 0
- Space Fit **15**: property type 0.5 + BHK 0.5 (off by one BHK only 0.1)
- Vibe Fit **15**: share of wanted amenities the property has
- Move Clock **10**: possession months <= target months -> 1, else decays over 18 months
