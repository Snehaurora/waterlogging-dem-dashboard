import json
import math
import random
import time
from pathlib import Path

import folium
import geopandas as gpd
import pandas as pd
import streamlit as st
from folium.plugins import AntPath, Fullscreen, MiniMap
from streamlit_folium import st_folium

BASE = Path(__file__).parent
st.set_page_config(page_title="Waterlogging hotspots - IIT Roorkee", page_icon="💧", layout="wide")

# =====================================================================
#  LOOKS: colours, CSS and small HTML helpers (change text/colours here)
# =====================================================================
SEV = ["Dry", "Filling", "Half full", "Nearly full"]
COLORS = {"Dry": "#c9b99a", "Filling": "#9ecae1", "Half full": "#4a90b8", "Nearly full": "#14405c"}


def svg_uri(svg):
    return "data:image/svg+xml;utf8," + svg.replace("#", "%23")


def crest(fill, foam=False):
    """Repeating wave top used by the splash, the puddle and the glass gauges."""
    foam_path = ("<path d='M0 20 Q30 4 60 20 T120 20 T180 20 T240 20 V48 H0Z' "
                 "fill='white' fill-opacity='.9'/>") if foam else ""
    return svg_uri(
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 240 48' preserveAspectRatio='none'>"
        + foam_path
        + f"<path d='M0 26 Q30 10 60 26 T120 26 T180 26 T240 26 V48 H0Z' fill='{fill}'/></svg>"
    )


RULE = svg_uri("<svg xmlns='http://www.w3.org/2000/svg' width='120' height='14' viewBox='0 0 120 14'>"
               "<path d='M0 7 Q15 0 30 7 T60 7 T90 7 T120 7' fill='none' stroke='#1f6f8b' stroke-width='1.6'/></svg>")

BASE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,700&family=Caveat:wght@500;600&display=swap');
:root {--card:rgba(127,150,170,.10); --line:rgba(127,150,170,.38);
       --water:#1f6f8b; --deep:#14405c; --sand:#c9b99a; --rust:#b5472f;}

@keyframes fadeUp {from {opacity:0; transform:translateY(16px);} to {opacity:1; transform:translateY(0);}}
@keyframes fadeIn {from {opacity:0;} to {opacity:1;}}
@keyframes rulePan {to {background-position:120px 0;}}
@keyframes crestPan {to {background-position:80px 0;}}
@keyframes fillUp {from {height:0;}}
@keyframes panelIn {0% {opacity:0; transform:translateY(26px); clip-path:inset(100% 0 0 0);}
                    100% {opacity:1; transform:translateY(0); clip-path:inset(0 0 0 0);}}
@property --ac {syntax:'<integer>'; initial-value:0; inherits:false;}
@property --bc {syntax:'<integer>'; initial-value:0; inherits:false;}
@keyframes cntA {from {--ac:0;} to {--ac:var(--a);}}
@keyframes cntB {from {--bc:0;} to {--bc:var(--b);}}

[data-testid="stHeader"] {background:transparent;}
.block-container {padding-top:2.4rem;}
h1, h2, h3, [data-testid="stSidebar"] h2 {font-family:'Fraunces', Georgia, 'Times New Roman', serif !important;}
[data-testid="stSidebar"] {border-right:1px solid var(--line);}
[data-testid="stSidebar"] h2 {font-size:1.1rem !important; margin-top:.6rem;}
button[data-baseweb="tab"] {font-size:1rem; letter-spacing:.02em;}
div[role="tabpanel"] {animation:panelIn .75s cubic-bezier(.2,.7,.2,1) backwards;}

.mast {animation:fadeUp .7s ease both;}
.mast .kicker {font-size:.76rem; letter-spacing:.16em; text-transform:uppercase; color:#2a8bb0; font-weight:600;}
.mast .mtitle {font-family:'Fraunces', Georgia, serif; font-size:2.6rem; line-height:1.1; font-weight:700;
  margin:.15em 0 .25em;}
.mast .mtext {max-width:46rem; opacity:.8; font-size:1.05rem; margin:0;}
.stamp {display:inline-block; margin-left:.8rem; border:2px solid var(--rust); color:var(--rust); padding:1px 9px;
  border-radius:4px; font-size:.7rem; letter-spacing:.12em; text-transform:uppercase; transform:rotate(-2deg);
  vertical-align:middle; font-family:'Source Sans Pro', sans-serif; font-weight:600;}
.rule {height:14px; margin:16px 0 8px; opacity:.6; background:url("RULE") repeat-x; background-size:120px 14px;
  animation:rulePan 9s linear infinite;}

.stat {background:var(--card); border:1px solid var(--line); border-left:5px solid var(--water); border-radius:6px;
  padding:12px 16px; animation:fadeUp .6s ease both;}
.stat .lab {font-size:.72rem; letter-spacing:.12em; text-transform:uppercase; opacity:.7;}
.stat .num {font-family:'Fraunces', Georgia, serif; font-size:2rem; font-weight:700;
  animation:cntA 1.4s ease-out forwards, cntB 1.4s ease-out forwards; counter-reset:ca var(--ac) cb var(--bc);}
.stat .num::before {content:counter(ca);}
.stat .num.dec::after {content:"." counter(cb, decimal-leading-zero);}

.gwrap {text-align:center;}
.glass {position:relative; width:104px; height:136px; margin:0 auto 8px; overflow:hidden; background:var(--card);
  border:2px solid currentColor; border-top:none; border-radius:0 0 22px 22px;}
.glass .fill {position:absolute; bottom:0; left:0; width:100%; background:linear-gradient(#4a90b8,#14405c);
  animation:fillUp 2s ease-out;}
.glass .fill::before {content:""; position:absolute; left:0; top:-9px; width:100%; height:10px;
  background:url("CRESTBLUE") repeat-x; background-size:80px 10px; animation:crestPan 2.4s linear infinite;}
.glass .gv {position:absolute; inset:0; display:flex; align-items:center; justify-content:center;
  font-family:'Fraunces', Georgia, serif; font-size:1.5rem; font-weight:700; color:#fff; text-shadow:0 1px 5px rgba(0,0,0,.5);}
.glabel {font-size:.74rem; letter-spacing:.12em; text-transform:uppercase; opacity:.7;}

.rg {display:flex; gap:16px; align-items:flex-end; margin:6px 0 14px;}
.rg-tube {position:relative; width:34px; height:124px; border:2px solid currentColor; border-top:none;
  border-radius:0 0 12px 12px; background:var(--card);}
.rg-fill {position:absolute; left:0; bottom:0; width:100%; background:var(--water); border-radius:0 0 9px 9px;
  animation:fillUp 1.1s ease;}
.rg-tube i {position:absolute; right:-2px; width:9px; height:1.5px; background:currentColor;}
.rg-tube b {position:absolute; left:46px; font-size:.68rem; font-weight:500; opacity:.7; transform:translateY(50%);}
.rg-read {font-size:.85rem; padding-bottom:4px; margin-left:34px;}
.rg-read small {opacity:.7; font-size:.85rem;}
.rg-read span {font-family:'Fraunces', Georgia, serif; font-size:1.7rem; font-weight:700;}

.foot {text-align:center; opacity:.7; font-size:.85rem; margin:26px 0 4px;}

button[kind="primary"], button[data-testid="stBaseButton-primary"] {background:var(--deep); border:none; color:#fff;
  border-radius:4px; letter-spacing:.06em; padding:.55rem 1.4rem; transition:transform .15s ease, background .15s ease;}
button[kind="primary"]:hover, button[data-testid="stBaseButton-primary"]:hover {background:var(--water); transform:translateY(-2px);}
</style>
""".replace("RULE", RULE).replace("CRESTBLUE", crest("#4a90b8"))

# ---------------- intro page: a rainy bit of campus with a puddle that slowly fills ----------------
INTRO_CSS = """
<style>
@keyframes fall {from {transform:translate3d(0,-30px,0) rotate(10deg);} to {transform:translate3d(-6vw,105vh,0) rotate(10deg);}}
@keyframes drift {from {transform:translateX(-25vw);} to {transform:translateX(110vw);}}
@keyframes pond {from {height:.5vh;} to {height:10.6vh;}}
@keyframes ripple {0% {transform:scale(.2); opacity:0;} 15% {opacity:.9;} 100% {transform:scale(3.4); opacity:0;}}

.stApp {background:linear-gradient(180deg,#b3c1cb 0%,#d3dce1 52%,#e6e5de 100%) !important;}
[data-testid="stToolbar"] {visibility:hidden;}

.cl {position:fixed; left:0; z-index:1; width:10em; height:3em; border-radius:3em; pointer-events:none;
  background:rgba(100,119,136,.72); filter:blur(1px); animation:drift linear infinite;}
.cl::before, .cl::after {content:""; position:absolute; background:inherit; border-radius:50%;}
.cl::before {width:4.6em; height:4.6em; left:1.4em; top:-2.2em;}
.cl::after {width:3.6em; height:3.6em; right:1.6em; top:-1.5em;}

.rd {position:fixed; top:0; width:1.5px; height:20px; z-index:2; pointer-events:none; animation:fall linear infinite;
  background:linear-gradient(to bottom, rgba(70,100,130,0), rgba(70,100,130,.75));}

/* the low spot: ground has a dip cut out of it, the pond sits behind the ground and rises inside the dip */
.pond {position:fixed; left:38vw; width:24vw; bottom:12.9vh; height:.5vh; z-index:3; pointer-events:none;
  background:linear-gradient(#3a8fae,#1b5877); animation:pond 45s ease-out 1s forwards;}
.pond::before {content:""; position:absolute; left:0; top:-10px; width:100%; height:12px;
  background:url("CRESTPOND") repeat-x; background-size:80px 12px; animation:crestPan 3s linear infinite;}
.rip {position:absolute; top:-4px; width:30px; height:8px; margin-left:-15px; border:1.5px solid rgba(255,255,255,.9);
  border-radius:50%; opacity:0; animation:ripple 2.4s ease-out infinite;}

.ground {position:fixed; left:0; bottom:0; width:100vw; height:34vh; z-index:4; pointer-events:none;
  background:linear-gradient(180deg,#86a36a 0%,#86a36a 22%,#8a6f52 22%,#6b5340 100%);
  clip-path:polygon(0% 17%, 8% 15%, 18% 14%, 28% 16%, 34% 20%, 38% 28%, 41% 42%, 44% 54%, 47% 60%, 50% 62%,
                    53% 60%, 56% 54%, 59% 42%, 62% 28%, 66% 20%, 72% 16%, 82% 14%, 92% 15%, 100% 17%, 100% 100%, 0% 100%);}

.note {position:fixed; left:64vw; bottom:31vh; z-index:6; font-family:'Caveat', 'Segoe Print', cursive; font-size:1.55rem;
  color:#33475b; transform:rotate(-5deg); animation:fadeIn 1.2s ease 6s both;}
.i-foot {position:fixed; left:0; bottom:1.6vh; width:100vw; text-align:center; z-index:20; color:#efe6d4; font-size:.95rem;}

.intro-wrap {position:relative; z-index:20; max-width:740px; margin:9vh auto 0; text-align:center;}
.i-kicker {font-size:.78rem; letter-spacing:.18em; text-transform:uppercase; color:#1f4560; font-weight:600; animation:fadeUp .8s ease both;}
.i-title {font-family:'Fraunces', Georgia, serif; font-size:3rem; line-height:1.1; font-weight:700; color:#16222f;
  margin:.3em 0 .45em; animation:fadeUp .9s ease .15s both;}
.i-line {font-size:1.12rem; line-height:1.6; color:#2b3a49; animation:fadeUp .9s ease .35s both;}
.i-guide {margin:1.1rem 0 1.4rem; color:#2b3a49; animation:fadeUp .9s ease .55s both;}
.stButton {position:relative; z-index:20;}
</style>
""".replace("CRESTPOND", crest("#3a8fae"))

INTRO_TEXT = """
<div class="intro-wrap">
<div class="i-kicker">CEC-201 · Geospatial Engineering II · Term Project</div>
<div class="i-title">Waterlogging Hotspot Detection using LiDAR</div>
<div class="i-line">After a heavy shower, a few corners of the IIT Roorkee campus stay under water. We looked for those low spots in LiDAR data and worked out how much water each one can hold.</div>
<div class="i-guide">Under the guidance of <b>Prof. Prakhar Misra</b></div>
</div>
"""


def intro_scene():
    rg = random.Random(11)
    clouds = "".join(
        f'<div class="cl" style="top:{t}px; font-size:{s}px; animation-duration:{d}s; animation-delay:-{o}s;"></div>'
        for t, s, d, o in [(-16, 22, 95, 10), (4, 16, 120, 60), (-10, 26, 110, 35), (10, 14, 140, 90)])
    drops = "".join(
        f'<i class="rd" style="left:{rg.uniform(0, 100):.1f}vw; animation-duration:{rg.uniform(0.8, 1.4):.2f}s; '
        f'animation-delay:-{rg.uniform(0, 1.4):.2f}s; opacity:{rg.uniform(0.35, 0.8):.2f};"></i>' for _ in range(70))
    ripples = "".join(f'<i class="rip" style="left:{x}%; animation-delay:{d}s;"></i>'
                      for x, d in [(18, 0), (45, 0.7), (70, 1.3), (30, 1.9), (58, 0.35), (82, 1.1)])
    return (f'<div class="scene">{clouds}{drops}<div class="pond">{ripples}</div><div class="ground"></div>'
            '<div class="note">the water collects here ↙</div>'
            '<div class="i-foot">Made with ❤️ by Team 11</div></div>')


# ---------------- the splash: a wave surges up over the page, then drains away on the other side ----------------
SPLASH_CSS = """
<style>
@keyframes swRise {from {height:0;} to {height:114vh;}}
@keyframes swDrain {0% {height:114vh; opacity:1;} 90% {opacity:1;} 100% {height:0; opacity:0;}}
@keyframes crestL {to {background-position:-240px 0;}}
@keyframes crestR {to {background-position:240px 0;}}
@keyframes spray {0% {transform:translate(0,0) scale(.3); opacity:0;} 12% {opacity:1;}
                  55% {transform:translate(var(--dx), calc(-1 * var(--h))) scale(1);}
                  100% {transform:translate(calc(var(--dx) * 1.5), 12vh) scale(.6); opacity:0;}}
@keyframes fadeIn {from {opacity:0;} to {opacity:1;}}
.sw {position:fixed; left:0; bottom:0; width:100vw; pointer-events:none;}
.sw::before {content:""; position:absolute; left:0; top:-47px; width:100%; height:48px; background-repeat:repeat-x;
  background-size:240px 48px;}
.sw.back {background:#14405c; z-index:999990;}
.sw.back::before {background-image:url("W_BACK"); animation:crestL 2.4s linear infinite;}
.sw.mid {background:#1f6f8b; z-index:999991;}
.sw.mid::before {background-image:url("W_MID"); animation:crestR 1.9s linear infinite;}
.sw.front {background:#2f86a6; z-index:999992;}
.sw.front::before {background-image:url("W_FRONT"); animation:crestL 1.5s linear infinite;}
.sw.rise {animation:swRise 3s cubic-bezier(.4,.05,.25,1) forwards;}
.sw.drain {animation:swDrain 1.8s ease-in forwards;}
.spl {position:fixed; bottom:0; border-radius:50% 50% 50% 50% / 60% 60% 40% 40%; background:#eef9fd; z-index:999993;
  pointer-events:none; animation:spray 2.2s ease-out both;}
.sw-text {position:fixed; top:44%; left:0; width:100vw; text-align:center; z-index:999994; color:#f5f0e6;
  font-family:'Fraunces', Georgia, serif; font-size:2.1rem; opacity:0; animation:fadeIn .7s ease 1.3s forwards;}
</style>
""".replace("W_BACK", crest("#14405c")).replace("W_MID", crest("#1f6f8b")).replace("W_FRONT", crest("#2f86a6", foam=True))


def splash_rise():
    rg = random.Random(5)
    layers = "".join(f'<div class="sw {c} rise" style="animation-delay:{d}s;"></div>'
                     for c, d in [("back", 0), ("mid", 0.15), ("front", 0.3)])
    spray = "".join(
        f'<i class="spl" style="left:{rg.uniform(3, 97):.1f}vw; width:{(s := rg.uniform(10, 24)):.0f}px; height:{s * 1.3:.0f}px; '
        f'animation-delay:{rg.uniform(0.2, 1.7):.2f}s; --dx:{rg.uniform(-9, 9):.1f}vw; --h:{rg.uniform(35, 85):.0f}vh;"></i>'
        for _ in range(22))
    return SPLASH_CSS + layers + spray + '<div class="sw-text">Following the water downhill…</div>'


def splash_drain():
    layers = "".join(f'<div class="sw {c} drain" style="animation-delay:{d}s;"></div>'
                     for c, d in [("front", 0), ("mid", 0.2), ("back", 0.4)])
    return SPLASH_CSS + layers


# ---------------- small HTML helpers for the dashboard ----------------
def card(label, value, dec=False):
    a = int(value)
    b = int(round((value - a) * 100)) if dec else 0
    return (f'<div class="stat"><div class="lab">{label}</div>'
            f'<div class="num {"dec" if dec else ""}" style="--a:{a}; --b:{b};"></div></div>')


def gauge(label, v):
    return (f'<div class="gwrap"><div class="glass"><div class="fill" style="height:{v * 100:.0f}%"></div>'
            f'<div class="gv">{v:.2f}</div></div><div class="glabel">{label}</div></div>')


def rain_gauge(mm, top=200):
    ticks = "".join(f'<i style="bottom:{t / top * 100:.0f}%"></i><b style="bottom:{t / top * 100:.0f}%">{t}</b>'
                    for t in range(0, top + 1, 50))
    return (f'<div class="rg"><div class="rg-tube"><div class="rg-fill" style="height:{mm / top * 100:.0f}%"></div>{ticks}</div>'
            f'<div class="rg-read"><span>{mm}</span><small> mm<br>of rain</small></div></div>')


def severity(frac):
    return "Dry" if frac < 0.05 else "Filling" if frac < 0.35 else "Half full" if frac < 0.7 else "Nearly full"


# ===== END OF LOOKS (everything below is the app logic) =====

st.markdown(BASE_CSS, unsafe_allow_html=True)

for _k, _v in {"entered": False, "flooding": False, "just_entered": False}.items():
    st.session_state.setdefault(_k, _v)

# ================= INTRO PAGE =================
if not st.session_state.entered:
    st.markdown(INTRO_CSS + intro_scene(), unsafe_allow_html=True)
    st.markdown(INTRO_TEXT, unsafe_allow_html=True)
    _, mid, _ = st.columns([2, 1, 2])
    if mid.button("Open the map  →", type="primary", use_container_width=True):
        st.session_state.flooding = True
        st.rerun()
    if st.session_state.flooding:
        st.markdown(splash_rise(), unsafe_allow_html=True)
        time.sleep(3.7)  # let the wave finish in the browser
        st.session_state.update(flooding=False, entered=True, just_entered=True)
        st.rerun()
    st.stop()

if st.session_state.just_entered:
    st.markdown(splash_drain(), unsafe_allow_html=True)
    st.session_state.just_entered = False

# ================= DATA (read once, reloaded only when the file changes) =================
HOT = BASE / "data" / "hotspots.geojson"


@st.cache_data
def load_hotspots(mtime):
    return gpd.read_file(HOT)


gdf = load_hotspots(HOT.stat().st_mtime).copy()
with open(BASE / "data" / "metrics.json") as f:
    metrics = json.load(f)
is_sample = bool(gdf["is_sample"].any()) if "is_sample" in gdf.columns else False

# ================= HEADER =================
stamp = '<span class="stamp">sample data</span>' if is_sample else ""
st.markdown(
    f"""<div class="mast">
<div class="kicker">IIT Roorkee · CEC-201 term project</div>
<div class="mtitle">Where rainwater collects on campus{stamp}</div>
<p class="mtext">Low spots found in the LiDAR-derived elevation model. Each outline is a hollow where water can stand; the colour shows how full it gets for the rainfall you pick on the left.</p>
</div>
<div class="rule"></div>""",
    unsafe_allow_html=True,
)

# ================= SIDEBAR =================
if st.sidebar.button("← Back to introduction"):
    st.session_state.entered = False
    st.rerun()

st.sidebar.header("Rainfall scenario")
rain = st.sidebar.slider("Rainfall (mm)", 0, 200, 100, 10,
                         help="Illustrative scenario: hotspot locations are fixed, only how full they are changes.")
st.sidebar.markdown(rain_gauge(rain), unsafe_allow_html=True)
catch = st.sidebar.slider("Catchment ratio", 5, 100, 30,
                          help="Assumed catchment area as a multiple of each hotspot's area (illustrative).")

full_depth = gdf["depth_m"].copy()
full_vol = gdf["volume_m3"].copy()
inflow = (rain / 1000.0) * gdf["area_m2"] * catch          # m3 of rain reaching each hotspot
frac = (inflow / full_vol.clip(lower=0.01)).clip(0, 1)     # 0 = empty, 1 = full
gdf["volume_m3"] = (full_vol * frac).round(1)
gdf["depth_m"] = (full_depth * frac ** 0.5).round(2)
gdf["fill_pct"] = (frac * 100).round(0)
gdf["severity"] = frac.apply(severity)

st.sidebar.header("Filters")
min_depth = st.sidebar.slider("Minimum full depth (m)", 0.0, 5.0, 0.0, 0.01)
min_area = st.sidebar.slider("Minimum area (m2)", 0, 1000, 0, 1)
levels = st.sidebar.multiselect("How full", SEV, default=SEV)
if len(gdf) > 50:
    max_show = st.sidebar.slider(
        "Hotspots to draw on map (largest first)", 50, len(gdf), min(300, len(gdf)), 50,
        help="Every hotspot stays in the counts, charts and table. Drawing thousands makes the map slow.")
else:
    max_show = len(gdf)

st.sidebar.header("Map options")
style = st.sidebar.radio("Base map", ["Clean", "Street", "Satellite"])
show_pulse = st.sidebar.checkbox("Ripple markers (only up to 300 hotspots)", value=True)
show_flow = st.sidebar.checkbox("Flowing water lines (illustrative, slow with many hotspots)", value=False)

filtered = gdf[(full_depth >= min_depth) & (gdf["area_m2"] >= min_area) & (gdf["severity"].isin(levels))]
if filtered.empty:
    st.info("No hotspots match these filters. Lower the sliders or add more fill levels.")
    st.stop()

drawn = filtered.sort_values("rank").head(max_show)
focus = st.sidebar.selectbox("Focus on hotspot", ["All hotspots"] + drawn["id"].tolist())

# ================= TABS =================
tab_map, tab_chart, tab_table, tab_metrics = st.tabs(["Map", "Charts", "Ranked table", "Accuracy"])

with tab_map:
    c = st.columns(4)
    c[0].markdown(card("Hotspots matching filters", len(filtered)), unsafe_allow_html=True)
    c[1].markdown(card("Water held now (m3)", round(filtered["volume_m3"].sum())), unsafe_allow_html=True)
    c[2].markdown(card("Deepest now (m)", float(filtered["depth_m"].max()), dec=True), unsafe_allow_html=True)
    c[3].markdown(card("Nearly full", int((filtered["severity"] == "Nearly full").sum())), unsafe_allow_html=True)
    st.write("")

    tiles = {
        "Clean": ("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", "CartoDB"),
        "Street": ("OpenStreetMap", "OpenStreetMap"),
        "Satellite": ("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                      "Esri World Imagery"),
    }
    tile_url, tile_attr = tiles[style]
    b = drawn.total_bounds
    centre, zoom = [(b[1] + b[3]) / 2, (b[0] + b[2]) / 2], 16
    if focus != "All hotspots":
        p = drawn[drawn["id"] == focus].iloc[0].geometry.representative_point()
        centre, zoom = [p.y, p.x], 18

    m = folium.Map(location=centre, zoom_start=zoom, tiles=tile_url, attr=tile_attr)
    if focus == "All hotspots" and len(drawn) > 1:
        m.fit_bounds([[b[1], b[0]], [b[3], b[2]]], max_zoom=17)

    m.get_root().header.add_child(folium.Element("""
<style>
.pulse {position:relative; width:12px; height:12px; border-radius:50%; background:var(--c);
        border:2px solid white; box-sizing:border-box;}
.pulse::before, .pulse::after {content:""; position:absolute; left:-2px; top:-2px; width:12px; height:12px;
        border-radius:50%; border:1.5px solid var(--c); box-sizing:border-box; animation:ring 2.4s ease-out infinite;}
.pulse::after {animation-delay:1.2s;}
@keyframes ring {0% {transform:scale(1); opacity:.9;} 100% {transform:scale(3.8); opacity:0;}}
</style>"""))
    m.get_root().html.add_child(folium.Element("""
<div style="position:fixed; bottom:25px; left:25px; z-index:9999; background:rgba(251,248,241,.95);
     padding:10px 14px; border-radius:6px; font-size:13px; color:#1d2b3a; border:1px solid #d8cfbd;">
<b>How full</b><br>
<span style="color:#c9b99a">&#9679;</span> Dry (&lt; 5%)<br>
<span style="color:#9ecae1">&#9679;</span> Filling (&lt; 35%)<br>
<span style="color:#4a90b8">&#9679;</span> Half full (&lt; 70%)<br>
<span style="color:#14405c">&#9679;</span> Nearly full (&ge; 70%)</div>"""))

    folium.GeoJson(
        drawn[["id", "rank", "depth_m", "area_m2", "volume_m3", "fill_pct", "severity", "geometry"]],
        style_function=lambda ft: {"fillColor": COLORS[ft["properties"]["severity"]], "color": "#ffffff",
                                   "weight": 1, "fillOpacity": 0.75},
        highlight_function=lambda ft: {"weight": 3, "fillOpacity": 0.95},
        tooltip=folium.GeoJsonTooltip(fields=["id", "rank", "fill_pct", "depth_m", "area_m2", "volume_m3"],
                                      aliases=["ID", "Rank", "Filled (%)", "Depth now (m)", "Area (m2)",
                                               "Volume now (m3)"]),
    ).add_to(m)

    for _, r in drawn.iterrows():
        pt = r.geometry.representative_point()
        if show_flow:  # illustrative: replace with real flow-accumulation lines from the pipeline
            rg = random.Random(r["id"])
            for _i in range(3):
                ang, dist = rg.uniform(0, 6.28), rg.uniform(0.0004, 0.0008)
                s = [pt.y + dist * math.sin(ang), pt.x + dist * math.cos(ang)]
                mid = [(s[0] + pt.y) / 2 + rg.uniform(-1, 1) * 8e-5, (s[1] + pt.x) / 2 + rg.uniform(-1, 1) * 8e-5]
                AntPath([s, mid, [pt.y, pt.x]], color="#1f6f8b", weight=3, delay=900,
                        dash_array=[8, 18], pulse_color="#ffffff").add_to(m)
        if show_pulse and len(drawn) <= 300:
            folium.Marker(
                [pt.y, pt.x],
                icon=folium.DivIcon(html=f'<div class="pulse" style="--c:{COLORS[r["severity"]]};"></div>',
                                    icon_size=(12, 12), icon_anchor=(6, 6)),
                tooltip=(f"<b>{r['id']}</b> - Rank {r['rank']}<br>Filled: {r['fill_pct']:.0f}%"
                         f"<br>Depth now: {r['depth_m']} m<br>Volume now: {r['volume_m3']} m3"),
            ).add_to(m)

    Fullscreen().add_to(m)
    MiniMap(toggle_display=True).add_to(m)
    st_folium(m, height=560, use_container_width=True, returned_objects=[])
    st.caption(f"Drawing the {len(drawn):,} largest of {len(filtered):,} hotspots that match the filters "
               "(change this in the sidebar). Colour shows how full each one is for the chosen rainfall "
               "scenario (illustrative: assumed catchment, no infiltration or drainage).")
    if show_flow:
        st.caption("Flowing lines are illustrative until real flow-accumulation results replace them.")

with tab_chart:
    top = drawn.head(40)
    left, right = st.columns(2)
    with left:
        st.subheader("Water held now - top 40 (m3)")
        st.bar_chart(pd.DataFrame(top[["id", "volume_m3"]]).set_index("id"), color="#1f6f8b")
    with right:
        st.subheader("Depth now - top 40 (m)")
        st.bar_chart(pd.DataFrame(top[["id", "depth_m"]]).set_index("id"), color="#14405c")
    st.subheader("Hotspots by how full they are (all matching)")
    counts = filtered["severity"].value_counts().reindex(SEV).fillna(0)
    st.bar_chart(counts.to_frame("hotspots"), color="#4a90b8")

with tab_table:
    table = pd.DataFrame(filtered.drop(columns=["geometry", "is_sample"], errors="ignore"))
    table = table.sort_values("volume_m3", ascending=False)
    st.dataframe(
        table, hide_index=True,
        column_config={
            "volume_m3": st.column_config.ProgressColumn(
                "Volume now (m3)", min_value=0.0, max_value=max(float(full_vol.max()), 1.0), format="%.1f"),
            "depth_m": st.column_config.NumberColumn("Depth now (m)", format="%.2f"),
            "fill_pct": st.column_config.NumberColumn("Filled (%)", format="%.0f"),
        },
    )
    d1, d2 = st.columns(2)
    d1.download_button("Download table, all matching (CSV)", table.to_csv(index=False), "hotspots.csv", "text/csv")
    d2.download_button("Download drawn hotspots (GeoJSON)", drawn.to_json(), "hotspots_drawn.geojson",
                       "application/geo+json")

with tab_metrics:
    if metrics.get("is_sample"):
        st.warning("These accuracy numbers are placeholders. Replace them with real results before submission.")
    g = st.columns(5)
    for col, (lab, key) in zip(g[:4], [("Precision", "precision"), ("Recall", "recall"), ("F1", "f1"), ("IoU", "iou")]):
        val = metrics.get(key)
        if val is None:
            col.markdown(f'<div class="gwrap"><div class="glass"><div class="gv" style="text-shadow:none; opacity:.4;">–</div></div>'
                         f'<div class="glabel">{lab}</div></div>', unsafe_allow_html=True)
        else:
            col.markdown(gauge(lab, float(val)), unsafe_allow_html=True)
    g[4].markdown(card("DEM vs DTM RMSE (m)", float(metrics["dtm_rmse_m"]), dec=True), unsafe_allow_html=True)
    if any(metrics.get(k) is None for k in ["precision", "recall", "f1", "iou"]):
        st.info("Precision, recall, F1 and IoU are not measured yet. They need field-marked waterlogged spots to compare against.")
    if "dtm_nmad_m" in metrics:
        st.caption(
            f"Elevation check: the point-cloud DEM was compared with the reference DTM on {metrics['cells_compared']:,} "
            f"1 m cells after removing a constant offset of {metrics['dtm_offset_m']} m (likely a height-datum difference). "
            f"Typical error (NMAD) {metrics['dtm_nmad_m']} m; {metrics['within_25cm_pct']}% of cells within 25 cm, "
            f"{metrics['within_50cm_pct']}% within 50 cm; RMSE without the outlier cells {metrics['rmse_without_outliers_m']} m. "
            "This shows how closely two surfaces agree, not an independent survey.")

st.markdown('<div class="foot">Made with ❤️ by Team 11 · CEC-201, IIT Roorkee</div>', unsafe_allow_html=True)