"""Streamlit interface with two views.   Run: streamlit run app.py
Buyer view  : a Gen-Z buyer enters details -> live Move-In Meter, persona, top-3 homes, what-if simulator -> optional 'share with builder'.
Builder view: dashboard on the synthetic lead base + the live leads captured from the Buyer view.
"""
import datetime as dt
import os
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import streamlit as st
import pipeline as pl

st.set_page_config(page_title="Gen-Z Buyer Intelligence", layout="wide")
LEADS = "data/live_leads.csv"
BLURB = {
    "Ready-to-Move Maker": "You're financially and mentally ready. The next step is a shortlist and a site visit.",
    "The Active Planner": "You're actively researching. Comparing options, pricing and payment plans will help most.",
    "The Smart Saver": "You want to own a home but there's a savings gap. Budget-friendly options and a savings plan fit best.",
    "The Vibe Seeker": "Neighbourhood, amenities and lifestyle fit matter most to you.",
    "The Future Builder": "You're thinking long-term: appreciation and locality growth matter.",
    "The Early Explorer": "You're early in your journey. Take your time; there's no pressure to decide yet.",
}


@st.cache_data
def load():
    return pl.run_all("data/buyers_raw.csv", "data/properties_raw.csv")


R = load()
b, p, m = R["buyers"], R["properties"], R["matches"]
st.sidebar.title("🏠 Gen-Z Buyer Intelligence")
mode = st.sidebar.radio("View", ["Buyer view", "Builder view"])
st.sidebar.caption("Synthetic data. Decision-support only: not credit scoring, loan approval or purchase prediction.")


# =========================================================== BUYER VIEW
def buyer_view():
    st.title("Find your first home 🏡")
    st.caption("Change any answer and your results update instantly. No contact details are asked.")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("1. Your money")
        age = st.slider("Age", 21, 30, 25)
        income = st.slider("Annual income (LPA)", 2, 40, 12)
        savings = st.slider("Savings for down payment (₹ lakh)", 0, 60, 12)
        budget = st.slider("Home budget (₹ lakh)", 25, 400, 80, step=5)
        st.caption(f"Down-payment cover: **{savings / budget:.0%}** of budget · Budget = **{budget / income:.1f}x** annual income")
        timeline = st.select_slider("When do you want to buy?", ["0-3 months", "3-6 months", "6-12 months", "12+ months", "Not sure"], "6-12 months")
        motive = st.radio("Why are you buying?", ["Self-use", "Investment", "Both"], horizontal=True)
    with c2:
        st.subheader("2. Your home")
        city = st.selectbox("City", ["Not sure yet"] + sorted(p.city.unique()))
        locs = ["Flexible"] + (sorted(p[p.city == city].locality.unique()) if city != "Not sure yet" else [])
        locality = st.selectbox("Locality", locs)
        ptype = st.selectbox("Property type", ["Any", "Apartment", "Builder Floor", "Villa"])
        bhk = st.selectbox("BHK", ["Any", 1, 2, 3, 4], index=2)
        amen = st.multiselect("Lifestyle must-haves", pl.AMENITIES, ["WFH Space", "Gym"])
        st.subheader("3. Interest")
        site = st.checkbox("I'd like a site visit")
        brochure = st.checkbox("Send me a brochure")
    prof = dict(age=age, income_lpa=income, savings_lakh=savings, budget_lakh=budget, timeline=timeline, motive=motive, city=city,
                locality=locality, ptype=ptype, bhk=bhk, amenities=amen, site_visit=site, brochure=brochure)

    r, mm = pl.score_single(prof, p)
    st.divider()
    k = st.columns(3)
    k[0].metric("Move-In Meter", f"{r.move_in_score:.0f}/100", str(r.readiness_level) + " readiness", delta_color="off")
    k[1].metric("Your buyer type", r.persona)
    k[2].metric("Affordability", str(r.affordability))
    st.progress(min(int(r.move_in_score), 100) / 100)
    st.info(f"**{r.persona}:** {BLURB[r.persona]}")
    with st.expander("How your Move-In score is built"):
        st.dataframe(pd.DataFrame({"You": [r.pts_financial, r.pts_timeline, r.pts_engagement, r.pts_clarity],
                                   "Max": [40, 25, 20, 15]}, index=["Financial capacity", "Purchase timeline", "Interest shown", "Preference clarity"]), width="stretch")

    st.subheader("Your top 3 homes")
    only_ready = st.toggle("Only ready-to-move homes")
    show = pl.match_buyers(pd.DataFrame([r]), p[p.possession_months == 0] if only_ready else p, 3) if only_ready else mm
    for _, x in show.iterrows():
        with st.container(border=True):
            st.markdown(f"**#{x['rank']} {x.project_name}** · {x.locality}, {x.city} · {x.bhk} BHK {x.property_type} · {pl.fmt_lakh(x.price_lakh)} · "
                        f"{x.possession_status} → **{x.home_match_score:.0f}% match**")
            st.caption(f"Budget {x.budget_fit:.0f}/35 · Area {x.neighbourhood_match:.0f}/25 · Space {x.space_fit:.0f}/15 · Lifestyle {x.vibe_fit:.0f}/15 · Timing {x.move_clock_fit:.0f}/10")
            st.write(x.why)

    st.subheader("What if…? 🔮")
    st.caption("See which changes would move your score or your best match.")
    wi = pl.what_if(prof, p)
    st.dataframe(wi, width="stretch", hide_index=True)

    st.subheader("Share with the builder")
    ok = st.checkbox("I agree to share this anonymous profile and results with the builder's sales team")
    if st.button("Send my profile", disabled=not ok, type="primary"):
        row = {"lead_id": f"LIVE-{dt.datetime.now():%m%d%H%M%S}", "submitted_at": dt.datetime.now().isoformat(timespec="seconds"),
               **{k_: (";".join(v) if isinstance(v, list) else v) for k_, v in prof.items()},
               "persona": r.persona, "move_in_score": r.move_in_score, "readiness_level": str(r.readiness_level),
               "top_match": f"{mm.project_name.iloc[0]} ({mm.property_id.iloc[0]})", "top_match_score": mm.home_match_score.iloc[0],
               "suggested_action": r.suggested_action}
        pd.DataFrame([row]).to_csv(LEADS, mode="a", header=not os.path.exists(LEADS), index=False)
        st.success("Sent! The sales team will see your profile and best-fit homes, so you won't get generic brochures.")


# =========================================================== BUILDER VIEW
def builder_view():
    f_persona = st.sidebar.multiselect("Persona", sorted(b.persona.unique()))
    f_ready = st.sidebar.multiselect("Readiness", ["High", "Medium", "Early-stage"])
    f_city = st.sidebar.multiselect("Preferred city", sorted(b.preferred_city.unique()))
    fb = b.copy()
    if f_persona: fb = fb[fb.persona.isin(f_persona)]
    if f_ready: fb = fb[fb.readiness_level.isin(f_ready)]
    if f_city: fb = fb[fb.preferred_city.isin(f_city)]
    st.sidebar.metric("Buyers in view", len(fb))
    t0, t1, t2, t3, t4 = st.tabs(["📥 Live leads", "📊 Overview", "👤 Buyer profile", "🏗️ Demand vs inventory", "🗂️ Data & method"])

    with t0:
        if os.path.exists(LEADS):
            L = pd.read_csv(LEADS).sort_values("move_in_score", ascending=False)
            c = st.columns(3); c[0].metric("Leads received", len(L)); c[1].metric("High readiness", int((L.readiness_level == "High").sum()))
            c[2].metric("Avg Move-In", f"{L.move_in_score.mean():.0f}")
            st.dataframe(L[["lead_id", "submitted_at", "persona", "move_in_score", "readiness_level", "city", "budget_lakh", "timeline",
                            "top_match", "top_match_score", "suggested_action"]], width="stretch", hide_index=True)
            st.download_button("Download leads CSV", L.to_csv(index=False), "live_leads.csv")
        else:
            st.info("No live leads yet. Switch to Buyer view, fill the form and press 'Send my profile'.")

    with t1:
        c = st.columns(4)
        c[0].metric("Buyers", len(fb)); c[1].metric("High readiness", int((fb.readiness_level == "High").sum()))
        c[2].metric("Avg Move-In score", f"{fb.move_in_score.mean():.1f}"); c[3].metric("Avg engagement", f"{fb.engagement_score.mean():.1f}")
        a, z = st.columns(2)
        with a: st.subheader("Personas"); st.bar_chart(fb.persona.value_counts())
        with z: st.subheader("Readiness level"); st.bar_chart(fb.readiness_level.value_counts())
        st.subheader("Persona playbook")
        pb = fb.groupby("persona").agg(buyers=("buyer_id", "count"), avg_move_in=("move_in_score", "mean"),
                                       avg_budget_lakh=("budget_lakh", "mean"), avg_engagement=("engagement_score", "mean")).round(1)
        pb["suggested_builder_response"] = pb.index.map(pl.PERSONA_RESPONSE)
        st.dataframe(pb, width="stretch")
        a, z = st.columns(2)
        with a:
            st.subheader("Top wanted amenities")
            s = fb[[f"want_{x}" for x in pl.AMENITIES]].sum(); s.index = pl.AMENITIES; st.bar_chart(s.sort_values())
        with z:
            st.subheader("Persona x amenity preference")
            h = fb.groupby("persona")[[f"want_{x}" for x in pl.AMENITIES]].mean(); h.columns = pl.AMENITIES
            fig, ax = plt.subplots(figsize=(6, 3.5)); sns.heatmap(h, annot=True, fmt=".2f", cmap="YlGnBu", ax=ax, cbar=False); st.pyplot(fig)
        st.subheader("Priority follow-up list")
        st.dataframe(fb.sort_values("move_in_score", ascending=False)[["buyer_id", "persona", "move_in_score", "readiness_level", "budget_lakh",
                     "preferred_city", "purchase_timeline", "suggested_action"]].head(25), width="stretch")

    with t2:
        if fb.empty:
            st.warning("No buyers match the filters.")
        else:
            bid = st.selectbox("Buyer ID", fb.sort_values("move_in_score", ascending=False).buyer_id)
            r = b[b.buyer_id == bid].iloc[0]
            c = st.columns(4)
            c[0].metric("Persona", r.persona); c[1].metric("Move-In Meter", f"{r.move_in_score:.0f}/100")
            c[2].metric("Readiness", str(r.readiness_level)); c[3].metric("Engagement", f"{r.engagement_score:.0f}/100")
            st.progress(min(int(r.move_in_score), 100) / 100)
            st.info(f"**Suggested next action:** {r.suggested_action}")
            st.write(f"Age {r.age}, {r.occupation_category}; income ≈ {r.income_mid:.1f} LPA; savings ≈ ₹{r.savings_mid:.1f} L; budget {pl.fmt_lakh(r.budget_lakh)}; "
                     f"{r.timeline_category} timeline; amenities: {', '.join(r.amenity_list) or 'none stated'}.")
            for _, x in m[m.buyer_id == bid].iterrows():
                with st.container(border=True):
                    st.markdown(f"**#{x['rank']} {x.project_name}** · {x.locality}, {x.city} · {x.bhk} BHK · {pl.fmt_lakh(x.price_lakh)} → **{x.home_match_score:.0f}/100**")
                    st.write(x.why)

    with t3:
        st.caption("Positive gap = more buyer demand than inventory share (under-supplied).")
        for k_, v in R["gaps"].items():
            st.subheader(k_); a, z = st.columns([2, 3]); a.dataframe(v, width="stretch"); z.bar_chart(v[["demand_share", "inventory_share"]])
        st.subheader("Most-recommended properties")
        st.dataframe(m.groupby(["property_id", "project_name", "city", "locality"]).agg(times_in_top3=("buyer_id", "count"),
                     avg_match=("home_match_score", "mean")).sort_values("times_in_top3", ascending=False).head(15).round(1), width="stretch")

    with t4:
        st.json({"buyers": R["buyer_log"], "properties": R["property_log"]})
        st.markdown("**Move-In Meter** = Financial capacity (40) + Timeline (25) + Engagement (20) + Clarity (15). High ≥70, Medium 40–69, Early <40.")
        st.markdown("**Home Match Score** = 0.35 Budget + 0.25 Neighbourhood + 0.15 Space + 0.15 Vibe + 0.10 Move Clock.")
        st.markdown("Buyer data is **synthetic**; Personas, Move-In Meter and Home Match Score are **Python-derived** fields.")


def builder_gate():
    if st.session_state.get("builder_ok"):
        return True
    try:
        secret = st.secrets["BUILDER_PASSWORD"]
    except Exception:
        secret = None
    st.title("Builder view 🔒")
    if not secret:
        st.error("Password not configured.")
        return False
    pwd = st.text_input("Password", type="password")
    if st.button("Unlock"):
        if pwd == secret:
            st.session_state["builder_ok"] = True
            st.rerun()
        else:
            st.error("Wrong password")
    return False


if mode == "Buyer view":
    buyer_view()
elif builder_gate():
    builder_view()

