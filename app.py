"""Personalized Travel Itinerary Planner - Skill Wallet Capstone Project 4.

Single-file Streamlit app: LLM (Gemini or Groq) with a built-in demo mode,
JSON-file persistence (no external DB), and ReportLab PDF export.
"""
import json
import os
import re
import uuid
from datetime import date, datetime, timedelta
from io import BytesIO

import streamlit as st

# ----------------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------------
st.set_page_config(page_title="Personalized Travel Itinerary Planner", page_icon="🧭", layout="wide")

DATA_FILE = "trips.json"
SLOTS = ["Morning Sightseeing", "Lunch Recommendation", "Afternoon Leisure", "Evening Dining & Entertainment"]
USD_INR = 83.0

CSS = """
<style>
.stApp {background: linear-gradient(180deg,#fff7ed 0%,#ecfeff 100%);}
h1,h2,h3 {font-family: 'Georgia', serif; color:#0f4c5c;}
.hero {background: linear-gradient(120deg,#0f4c5c,#e36414); color:white; padding:1.6rem 2rem;
       border-radius:18px; margin-bottom:1rem;}
.hero h1 {color:white; margin:0;} .hero p {margin:.3rem 0 0 0; opacity:.92;}
.card {background:white; border-radius:16px; padding:1rem 1.2rem; box-shadow:0 4px 14px rgba(0,0,0,.08);
       border-left:6px solid #e36414; margin-bottom:.8rem;}
.tag {display:inline-block; background:#fb8b24; color:white; border-radius:999px; padding:2px 10px;
      margin:2px 4px 2px 0; font-size:.78rem;}
.slot {background:#fff; border-radius:12px; padding:.7rem 1rem; margin:.4rem 0; border-left:5px solid #0f4c5c;}
.cost {color:#9a031e; font-weight:600;}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)
st.markdown(
    '<div class="hero"><h1>🧭 Personalized Travel Itinerary Planner</h1>'
    "<p>Vibe-based destinations, geographically clustered day plans, swaps and offline PDF guides.</p></div>",
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# Persistence (JSON file + session fallback)
# ----------------------------------------------------------------------------
def load_trips():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return st.session_state.get("trips_mem", [])


def save_trips(trips):
    st.session_state["trips_mem"] = trips
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(trips, f, indent=2)
    except Exception:
        pass  # read-only FS: session memory still works


# ----------------------------------------------------------------------------
# LLM layer
# ----------------------------------------------------------------------------
def extract_json(text):
    text = re.sub(r"```(?:json)?", "", text).strip()
    start = min([i for i in (text.find("{"), text.find("[")) if i != -1], default=-1)
    if start == -1:
        raise ValueError("No JSON found in model output")
    end = max(text.rfind("}"), text.rfind("]"))
    return json.loads(text[start : end + 1])


def call_llm(provider, api_key, prompt):
    system = "You are a senior travel planner. Respond with valid JSON only, no prose, no markdown."
    if provider == "Gemini":
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash", system_instruction=system)
        return model.generate_content(prompt).text
    from groq import Groq

    client = Groq(api_key=api_key)
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        temperature=0.7,
    )
    return resp.choices[0].message.content


# ----------------------------------------------------------------------------
# Demo-mode data (works with no API key)
# ----------------------------------------------------------------------------
DEMO_DESTS = {
    "Beach": [
        ("Goa, India", ["Beaches", "Nightlife", "Seafood"], "Nov-Feb", "Budget", "Laid-back shores, shacks and sunsets."),
        ("Bali, Indonesia", ["Surf", "Temples", "Wellness"], "Apr-Oct", "Moderate", "Rice terraces meet surf breaks."),
        ("Phuket, Thailand", ["Islands", "Street Food", "Diving"], "Nov-Apr", "Moderate", "Island hopping on a budget."),
    ],
    "Mountains": [
        ("Manali, India", ["Adventure", "Snow", "Cafes"], "Mar-Jun", "Budget", "Himalayan treks and riverside cafes."),
        ("Interlaken, Switzerland", ["Alps", "Paragliding", "Scenic Trains"], "Jun-Sep", "Luxury", "Postcard Alps between two lakes."),
        ("Queenstown, New Zealand", ["Adventure", "Wine", "Lakes"], "Dec-Mar", "Luxury", "Adventure capital of the world."),
    ],
    "Cultural": [
        ("Kyoto, Japan", ["Temples", "Tea", "Geisha District"], "Mar-May", "Moderate", "Timeless temples and gardens."),
        ("Rome, Italy", ["History", "Food", "Art"], "Apr-Jun", "Moderate", "Two thousand years in walking distance."),
        ("Jaipur, India", ["Forts", "Bazaars", "Cuisine"], "Oct-Mar", "Budget", "The Pink City of palaces."),
    ],
    "Urban": [
        ("Tokyo, Japan", ["Food", "Tech", "Nightlife"], "Mar-May", "Moderate", "Neon, noodles and nonstop energy."),
        ("Singapore", ["Hawker Food", "Gardens", "Skyline"], "Feb-Apr", "Moderate", "Clean, compact, delicious."),
        ("New York, USA", ["Museums", "Broadway", "Food"], "Sep-Nov", "Luxury", "The city that never sleeps."),
    ],
}

DEMO_SPOTS = {
    "default": [
        ("Old Town Walking Tour", "Historic centre", 15, "History"),
        ("Central Museum", "Historic centre", 12, "History"),
        ("Local Food Market", "Market district", 10, "Food"),
        ("Riverside Promenade", "Waterfront", 0, "Relaxed"),
        ("Sunset Viewpoint", "Hilltop", 5, "Adventure"),
        ("Street Food Trail", "Market district", 14, "Food"),
        ("Night Bazaar", "Market district", 8, "Nightlife"),
        ("Rooftop Lounge", "Downtown", 25, "Nightlife"),
        ("Botanical Garden", "Green belt", 6, "Relaxed"),
        ("Adventure Park", "Green belt", 30, "Adventure"),
        ("Cooking Class", "Downtown", 35, "Food"),
        ("Heritage Fort", "Historic centre", 9, "History"),
    ]
}


def mult(budget):
    return {"Budget": 0.6, "Moderate": 1.0, "Luxury": 2.2}.get(budget, 1.0)


def demo_destinations(vibe):
    return [
        {"city": c, "tags": t, "best_season": s, "budget_fit": b, "why": w}
        for c, t, s, b, w in DEMO_DESTS.get(vibe, DEMO_DESTS["Cultural"])
    ]


def demo_day(day_no, prefs, offset=0):
    spots = DEMO_SPOTS["default"]
    interests = prefs["interests"]
    ranked = sorted(spots, key=lambda s: (s[3] not in interests, s[1]))
    area_groups = {}
    for s in ranked:
        area_groups.setdefault(s[1], []).append(s)
    areas = list(area_groups)
    area = areas[(day_no - 1 + offset) % len(areas)]
    pool = area_groups[area] + [s for s in ranked if s[1] != area]
    m = mult(prefs["budget"])
    day_slots = []
    for i, slot in enumerate(SLOTS):
        name, a, cost, _ = pool[i % len(pool)]
        if slot == "Lunch Recommendation":
            name, cost = f"Local lunch near {area}", 8
        if slot == "Evening Dining & Entertainment":
            name, cost = f"Dinner & show in {area}", 20
        day_slots.append(
            {"slot": slot, "activity": name, "area": area, "description": f"Enjoy {name} in the {area.lower()} zone.",
             "cost_usd": round(cost * m, 1), "duration_hours": 2}
        )
    return {"day": day_no, "theme": f"{area} Day", "area_cluster": area, "slots": day_slots}


# ----------------------------------------------------------------------------
# Generators
# ----------------------------------------------------------------------------
def prefs_summary(p):
    return (
        f"Destination: {p['destination']}; Duration: {p['days']} days; Dates: {p['start']}; Budget: {p['budget']}; "
        f"Party: {p['party']}; Pace: {p['pace']}; Interests: {', '.join(p['interests']) or 'general'}"
    )


def recommend(p, provider, key, demo):
    if demo or not key:
        return demo_destinations(p["vibe"])
    prompt = (
        f"Recommend the top 3 cities for a {p['vibe']} trip. Budget {p['budget']}, travelling {p['party']}, "
        f"interests {', '.join(p['interests'])}, travel month {p['start']:%B}. Return JSON list of objects with keys: "
        "city, tags (3 short strings), best_season, budget_fit, why (one sentence)."
    )
    return extract_json(call_llm(provider, key, prompt))


def generate_itinerary(p, provider, key, demo):
    if demo or not key:
        return [demo_day(d, p) for d in range(1, p["days"] + 1)]
    prompt = (
        f"Create a {p['days']}-day itinerary. {prefs_summary(p)}. RULES: group nearby attractions on the same day, "
        "no backtracking across the city, one neighbourhood cluster per day. Each day has exactly these 4 slots in order: "
        f"{SLOTS}. Return a JSON list of days: {{day, theme, area_cluster, slots:[{{slot, activity, area, description, "
        "cost_usd (number, per person estimate), duration_hours}}]}}. Costs must match the budget level."
    )
    return extract_json(call_llm(provider, key, prompt))


def regenerate_day(p, itin, day_no, instruction, provider, key, demo):
    if demo or not key:
        new = demo_day(day_no, p, offset=1 + len(instruction) % 3)
        if instruction:
            new["slots"][0]["activity"] = f"{instruction.strip().capitalize()} (custom)"
        return new
    prompt = (
        f"Regenerate ONLY day {day_no} of a trip. {prefs_summary(p)}. User request: '{instruction}'. "
        f"Other days already planned (avoid repeating): {json.dumps([d['theme'] for d in itin])}. "
        f"Keep the 4 slots {SLOTS} and geographic clustering. Return one JSON object: "
        "{day, theme, area_cluster, slots:[{slot, activity, area, description, cost_usd, duration_hours}]}."
    )
    out = extract_json(call_llm(provider, key, prompt))
    out["day"] = day_no
    return out


def swap_slot(p, itin, day_no, slot_idx, instruction, provider, key, demo):
    day = itin[day_no - 1]
    old = day["slots"][slot_idx]
    if demo or not key:
        old["activity"] = f"{instruction.strip().capitalize()} in {day['area_cluster']}"
        old["description"] = f"Swapped per request: {instruction}"
        return
    prompt = (
        f"In {p['destination']}, replace this activity: {json.dumps(old)} with one matching: '{instruction}'. "
        f"Stay in the same area cluster ({day['area_cluster']}). Return one JSON object with keys "
        "slot, activity, area, description, cost_usd, duration_hours."
    )
    new = extract_json(call_llm(provider, key, prompt))
    new["slot"] = old["slot"]
    day["slots"][slot_idx] = new


# ----------------------------------------------------------------------------
# Cost helpers and PDF
# ----------------------------------------------------------------------------
def day_cost(day):
    return sum(float(s.get("cost_usd", 0) or 0) for s in day["slots"])


def money(usd):
    return f"${usd:,.0f} / ₹{usd * USD_INR:,.0f}"


def build_pdf(trip):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm)
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Title"], textColor=colors.HexColor("#0f4c5c"))
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], textColor=colors.HexColor("#e36414"))
    body = ss["BodyText"]
    safe = lambda s: str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    p = trip["prefs"]
    el = [Paragraph(f"Travel Guide: {safe(p['destination'])}", h1),
          Paragraph(safe(prefs_summary({**p, 'start': p['start']})), body), Spacer(1, 12)]
    total = 0
    for d in trip["itinerary"]:
        c = day_cost(d)
        total += c
        el.append(Paragraph(f"Day {d['day']}: {safe(d.get('theme', ''))}", h2))
        rows = [["Time slot", "Activity", "Est. cost"]]
        for s in d["slots"]:
            rows.append([Paragraph(safe(s["slot"]), body), Paragraph(f"<b>{safe(s['activity'])}</b><br/>{safe(s.get('description',''))}", body),
                         f"${float(s.get('cost_usd', 0)):.0f}"])
        rows.append(["", "Day total", f"${c:.0f}"])
        t = Table(rows, colWidths=[4 * cm, 10 * cm, 2.5 * cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f4c5c")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey), ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#fff1e0"))]))
        el += [t, Spacer(1, 12)]
    el.append(Paragraph(f"Estimated trip total per person: ${total:,.0f} (approx. INR {total * USD_INR:,.0f})", h2))
    el.append(PageBreak())
    el.append(Paragraph("Emergency Contact Checklist", h2))
    for item in ["Local emergency number (police/ambulance/fire) saved offline", "Embassy / consulate address and phone",
                 "Nearest hospital to hotel", "Travel insurance policy number and helpline", "Hotel address and phone",
                 "Family contact back home", "Passport and visa copies stored offline", "Bank card block hotline"]:
        el.append(Paragraph(f"[&nbsp;&nbsp;] {item}", body))
    doc.build(el)
    return buf.getvalue()


# ----------------------------------------------------------------------------
# Sidebar: configuration & preferences
# ----------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Configuration")
    demo = st.toggle("Demo mode (no API key)", value=True)
    provider = st.selectbox("LLM provider", ["Gemini", "Groq"], disabled=demo)
    api_key = st.text_input("API key", type="password", disabled=demo) or os.environ.get("LLM_API_KEY", "")
    st.divider()
    st.header("🧳 Trip Preferences")
    dest_mode = st.radio("Destination", ["I know where I'm going", "Suggest by vibe"])
    destination = st.text_input("City / destination", "Jaipur, India") if dest_mode.startswith("I know") else "TBD"
    vibe = st.selectbox("Vibe", ["Beach", "Mountains", "Cultural", "Urban"])
    days = st.slider("Trip duration (days)", 1, 10, 3)
    start = st.date_input("Start date", date.today() + timedelta(days=30))
    budget = st.select_slider("Budget", ["Budget", "Moderate", "Luxury"], value="Moderate")
    party = st.selectbox("Travel party", ["Solo", "Couple", "Family", "Friends"])
    pace = st.select_slider("Pace", ["Relaxed", "Moderate", "Fast-Paced"], value="Moderate")
    interests = st.multiselect("Interests", ["Food", "Adventure", "History", "Nightlife", "Relaxed"], default=["Food", "History"])

prefs = dict(destination=destination, vibe=vibe, days=days, start=start, budget=budget, party=party, pace=pace, interests=interests)
S = st.session_state
S.setdefault("itinerary", [])
S.setdefault("prefs", None)
S.setdefault("recs", [])

tab1, tab2, tab3, tab4 = st.tabs(["🌍 Destination Recommender", "🗓️ Day-by-Day Itinerary", "🎨 Vibe Customization", "💾 Trips & PDF Export"])

# ---- Tab 1
with tab1:
    st.subheader("Where should you go?")
    if st.button("✨ Recommend top 3 cities", type="primary"):
        try:
            with st.spinner("Scanning the globe..."):
                S.recs = recommend(prefs, provider, api_key, demo)
        except Exception as e:
            st.error(f"Could not get recommendations: {e}")
    for r in S.recs:
        tags = "".join(f'<span class="tag">{t}</span>' for t in r.get("tags", []))
        st.markdown(
            f'<div class="card"><h3>{r["city"]}</h3>{tags}<p>{r.get("why","")}</p>'
            f'<small>Best season: <b>{r.get("best_season","-")}</b> &nbsp;|&nbsp; Budget fit: <b>{r.get("budget_fit","-")}</b></small></div>',
            unsafe_allow_html=True,
        )
        if st.button(f"Plan a trip to {r['city']}", key=f"pick_{r['city']}"):
            st.session_state["picked"] = r["city"]
            st.info(f"Set destination to **{r['city']}** in the sidebar (choose 'I know where I'm going') and generate the itinerary.")

# ---- Tab 2
with tab2:
    st.subheader("Optimized itinerary")
    if st.button("🚀 Generate itinerary", type="primary"):
        try:
            with st.spinner("Clustering attractions and routing days..."):
                S.itinerary = generate_itinerary(prefs, provider, api_key, demo)
                S.prefs = prefs
        except Exception as e:
            st.error(f"Generation failed: {e}. Try Demo mode or check your key.")
    if S.itinerary:
        running = 0.0
        for d in S.itinerary:
            dc = day_cost(d)
            running += dc
            st.markdown(f"### Day {d['day']}: {d.get('theme','')}  \n📍 Cluster: **{d.get('area_cluster','')}**")
            for s in d["slots"]:
                st.markdown(
                    f'<div class="slot"><b>{s["slot"]}</b>: {s["activity"]}<br/><small>{s.get("description","")}</small>'
                    f'<br/><span class="cost">${float(s.get("cost_usd",0)):.0f} / ₹{float(s.get("cost_usd",0))*USD_INR:,.0f}</span></div>',
                    unsafe_allow_html=True,
                )
            c1, c2 = st.columns(2)
            c1.metric("Day total", money(dc))
            c2.metric("Running total", money(running))
        st.success(f"Estimated total per person: {money(running)}")
    else:
        st.info("Set your preferences in the sidebar and generate your plan.")

# ---- Tab 3
with tab3:
    st.subheader("Customize without wiping the plan")
    if not S.itinerary:
        st.info("Generate an itinerary first.")
    else:
        p = S.prefs or prefs
        day_no = st.selectbox("Day", [d["day"] for d in S.itinerary])
        day = S.itinerary[day_no - 1]
        st.caption(f"Theme: {day.get('theme','')}")
        slot_name = st.selectbox("Slot to swap", [s["slot"] for s in day["slots"]])
        presets = ["Swap museum for outdoor market", "Find vegetarian lunch spot", "Something more adventurous", "Romantic evening", "Custom..."]
        choice = st.selectbox("Quick vibe", presets)
        custom = st.text_input("Your request", "" if choice != "Custom..." else "") if choice == "Custom..." else choice
        c1, c2 = st.columns(2)
        if c1.button("🔄 Swap this slot"):
            try:
                idx = [s["slot"] for s in day["slots"]].index(slot_name)
                swap_slot(p, S.itinerary, day_no, idx, custom, provider, api_key, demo)
                st.success("Slot updated.")
            except Exception as e:
                st.error(f"Swap failed: {e}")
        if c2.button("♻️ Regenerate whole day"):
            try:
                S.itinerary[day_no - 1] = regenerate_day(p, S.itinerary, day_no, custom, provider, api_key, demo)
                st.success(f"Day {day_no} regenerated. Other days untouched.")
            except Exception as e:
                st.error(f"Regeneration failed: {e}")
        for s in S.itinerary[day_no - 1]["slots"]:
            st.markdown(f"- **{s['slot']}**: {s['activity']} (${float(s.get('cost_usd',0)):.0f})")

# ---- Tab 4
with tab4:
    st.subheader("Save, revisit and export")
    trips = load_trips()
    if S.itinerary:
        name = st.text_input("Trip name", f"{(S.prefs or prefs)['destination']} getaway")
        if st.button("💾 Save trip"):
            sp = dict((S.prefs or prefs))
            sp["start"] = str(sp["start"])
            trips.append({"id": uuid.uuid4().hex[:8], "name": name, "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                          "prefs": sp, "itinerary": S.itinerary})
            save_trips(trips)
            st.success("Trip saved.")
        try:
            cur = {"prefs": {**(S.prefs or prefs), "start": str((S.prefs or prefs)["start"])}, "itinerary": S.itinerary}
            st.download_button("📄 Export current plan as PDF", build_pdf(cur), file_name="itinerary.pdf", mime="application/pdf")
        except Exception as e:
            st.error(f"PDF export failed: {e}")
    else:
        st.info("Generate an itinerary to save or export it.")
    st.markdown("#### Trip history")
    if not trips:
        st.caption("No saved trips yet.")
    for t in reversed(trips):
        with st.expander(f"{t['name']}  ·  {t['saved_at']}"):
            st.write(prefs_summary(t["prefs"]))
            for d in t["itinerary"]:
                st.markdown(f"**Day {d['day']}**: {d.get('theme','')} (${day_cost(d):.0f})")
            c1, c2, c3 = st.columns(3)
            if c1.button("Load", key=f"l{t['id']}"):
                S.itinerary = t["itinerary"]
                S.prefs = {**t["prefs"], "start": datetime.strptime(t["prefs"]["start"], "%Y-%m-%d").date()}
                st.rerun()
            try:
                c2.download_button("PDF", build_pdf(t), file_name=f"{t['name']}.pdf", mime="application/pdf", key=f"p{t['id']}")
            except Exception:
                c2.caption("PDF unavailable")
            if c3.button("Delete", key=f"d{t['id']}"):
                save_trips([x for x in trips if x["id"] != t["id"]])
                st.rerun()
