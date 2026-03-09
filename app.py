import streamlit as st
import anthropic
import base64
import json
import math
import tempfile
import os
import re
from PIL import Image
import io

# ── PAGE CONFIG ──
st.set_page_config(
    page_title="ThrowsLab — Position Breakdown",
    page_icon="🥏",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── POSITIONS ──
POSITIONS = [
    {
        "id": "prep",
        "name": "Preparation / Wind-up",
        "icon": "①",
        "short": "PREP",
        "desc": "Setting up balance and loading",
        "criteria": {
            "shot_spin":  ["Feet shoulder-width, back to sector", "Shot tucked at neck/jaw", "Throwing arm elbow up", "Weight centered and balanced", "Mental focus — eyes down-sector"],
            "shot_glide": ["Back to sector, feet hip-width", "Shot at neck/jaw, elbow up", "Weight on right foot", "Knees slightly bent and loaded", "Body relaxed but coiled"],
            "discus":     ["Feet shoulder-width, back to sector", "Discus rests on finger pads — not palm", "Arms relaxed, preliminary swing building", "Weight balanced and centered", "Eyes focused down-sector"],
        },
    },
    {
        "id": "entry",
        "name": "Entry",
        "icon": "②",
        "short": "ENTRY",
        "desc": "Beginning rotation from the back",
        "criteria": {
            "shot_spin":  ["Deep knee bend on pivot foot", "Free leg sweeps low and wide", "Hips low — jackknife position achieved", "Back still facing sector", "Shot stays at neck throughout"],
            "shot_glide": ["Right foot drives powerfully back", "Low glide — not a hop", "Left leg extends long toward board", "Hips stay low throughout", "Shot stays loaded at neck"],
            "discus":     ["Preliminary swing builds angular momentum", "Discus tracks back and high on backswing", "Weight shifts decisively to right foot", "Pivot foot heel begins to rise", "Body coiling — shoulders lag hips"],
        },
    },
    {
        "id": "flight",
        "name": "Airborne / Flight",
        "icon": "③",
        "short": "FLIGHT",
        "desc": "Moving across the circle",
        "criteria": {
            "shot_spin":  ["Back fully facing sector at mid-rotation", "Left leg driving through aggressively", "Hips ahead of shoulders — separation maintained", "Low center of gravity throughout", "Not opening shoulders too early"],
            "shot_glide": ["Body near parallel to ground", "Both feet briefly off surface", "Low flat trajectory across circle", "Left foot tracking toward toe board", "Shot still loaded at neck"],
            "discus":     ["Back fully facing sector mid-rotation", "Left leg driving wide and low", "Discus trails well behind throwing shoulder", "Hips clearly ahead of shoulders", "Low and wide — not upright"],
        },
    },
    {
        "id": "transition",
        "name": "Transition / Landing",
        "icon": "④",
        "short": "LAND",
        "desc": "Grounding the right foot",
        "criteria": {
            "shot_spin":  ["Right foot lands near circle center", "Left foot beginning to reach for plant", "Hips still ahead of shoulders", "Weight loaded on right side", "Shot still at neck — not drifting"],
            "shot_glide": ["Right foot lands under hips at center", "Left foot contacts toe board simultaneously", "Hip-shoulder separation maintained at landing", "Knees bent and loaded on contact", "Shot still at neck"],
            "discus":     ["Right foot plants firmly near circle center", "Left foot sweeping toward front", "Hip-shoulder separation preserved on landing", "Knees bent — body stays low", "Discus still trailing behind shoulder"],
        },
    },
    {
        "id": "power",
        "name": "Power Position",
        "icon": "⑤",
        "short": "POWER",
        "desc": "Setting up the final throw",
        "criteria": {
            "shot_spin":  ["Left foot plants near toe board", "Right foot behind center — wide base", "Hip-shoulder separation 45°+ at set", "Shot still at neck — no early release", "Knees loaded — ready to drive"],
            "shot_glide": ["Left foot firm at toe board", "Right foot behind center, wide stance", "Hip-shoulder separation clearly visible", "Knees bent and coiled", "Shot at neck, elbow up"],
            "discus":     ["Left foot plants firmly near front of circle", "Discus at or above shoulder height", "Hip-shoulder separation 45°+ clearly visible", "Throwing arm fully extended behind body", "Weight loaded on right — ready to fire"],
        },
    },
    {
        "id": "release",
        "name": "Delivery / Release",
        "icon": "⑥",
        "short": "RELEASE",
        "desc": "Explosive final throwing action",
        "criteria": {
            "shot_spin":  ["Elbow at or above shoulder at release", "Release angle 38-42°", "Full leg and hip extension through release", "Left arm blocks hard and short", "Chin-wrist-elbow aligned at release point"],
            "shot_glide": ["Elbow at or above shoulder", "Release angle 38-42°", "Full leg extension through throw", "Left arm blocks firmly", "Complete follow-through after release"],
            "discus":     ["Discus leaves from index finger last", "Release angle 35-40°", "Throwing arm sweeps up — not flat", "Left arm blocks hard at the hip", "Disc attitude flat — good gyroscopic spin"],
        },
    },
]

EVENT_LABELS = {
    "shot_spin":  "SHOT PUT — SPIN",
    "shot_glide": "SHOT PUT — GLIDE",
    "discus":     "DISCUS",
}

# ── CSS ──
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@300;600;700;900&family=Courier+Prime:wght@400;700&display=swap');
html, body, [class*="css"] { font-family: 'Courier Prime', monospace; }

.tl-header { background:#0f0d0b; padding:14px 28px; border-bottom:3px solid #c41e2a;
             display:flex; align-items:center; gap:16px; margin:-1rem -1rem 1.5rem -1rem; }
.tl-logo { font-family:'Barlow Condensed',sans-serif; font-weight:900; font-size:1.6rem;
           letter-spacing:8px; color:#fff; text-transform:uppercase; }
.tl-logo em { color:#c41e2a; font-style:normal; }
.tl-logo-sub { font-family:'Barlow Condensed',sans-serif; font-size:0.5rem; letter-spacing:4px; color:#444; }

.section-title { font-family:'Barlow Condensed',sans-serif; font-weight:700; font-size:0.6rem;
                 letter-spacing:5px; text-transform:uppercase; color:#8a7d6e;
                 border-bottom:1px solid #d4cabf; padding-bottom:5px;
                 margin-bottom:14px; margin-top:20px; }

/* Carousel / assignment */
.carousel-frame-label {
    font-family:'Barlow Condensed',sans-serif; font-weight:700;
    font-size:0.55rem; letter-spacing:2px; text-align:center;
    margin-top:3px; color:#8a7d6e;
}
.pos-slot {
    border:1px solid #d4cabf; border-top:3px solid #d4cabf;
    padding:8px 10px; margin-bottom:6px; background:#fff;
}
.pos-slot.filled { border-top-color:#1a5c3a; }
.pos-slot.active  { border-top-color:#c41e2a; background:#fffaf8; }
.pos-slot-name { font-family:'Barlow Condensed',sans-serif; font-weight:900;
                 font-size:0.8rem; letter-spacing:2px; text-transform:uppercase; }
.pos-slot-desc { font-size:0.5rem; color:#8a7d6e; margin-top:1px; }
.pos-slot-status { font-size:0.48rem; margin-top:4px; }
.pos-slot-status.ok   { color:#1a5c3a; font-weight:700; }
.pos-slot-status.miss { color:#c41e2a; }

/* Result cards */
.pos-card-name { font-family:'Barlow Condensed',sans-serif; font-weight:900; font-size:0.85rem;
                 letter-spacing:2px; text-transform:uppercase; color:#0f0d0b; }
.pos-card-verdict { font-family:'Barlow Condensed',sans-serif; font-weight:700; font-size:0.5rem;
                    letter-spacing:2px; padding:2px 7px; display:inline-block; margin-top:3px; }
.verdict-good    { background:rgba(26,92,58,.12);  color:#1a5c3a; border:1px solid rgba(26,92,58,.25); }
.verdict-warn    { background:rgba(196,30,42,.1);  color:#c41e2a; border:1px solid rgba(196,30,42,.2); }
.verdict-ok      { background:rgba(15,52,96,.08);  color:#0f3460; border:1px solid rgba(15,52,96,.15); }
.verdict-pending { background:#f0ece6; color:#8a7d6e; border:1px solid #d4cabf; }
.pos-card-note { font-size:0.55rem; color:#555; line-height:1.6; margin-top:5px; }
.pos-card-time { font-size:0.45rem; color:#aaa; letter-spacing:1px; margin-top:2px; }

.check-row { display:flex; gap:8px; align-items:flex-start; font-size:0.6rem;
             line-height:1.6; padding:3px 0; border-bottom:1px solid #f0ece6; }
.check-icon { font-size:0.75rem; flex-shrink:0; width:16px; }
.check-pass { color:#1a5c3a; }
.check-warn { color:#c8920a; }
.check-fail { color:#c41e2a; }

.metric-card { background:#fff; border:1px solid #d4cabf; padding:12px 14px;
               border-left:3px solid #d4cabf; margin-bottom:8px; }
.metric-card.vel { border-left-color:#0f3460; }
.metric-card.ang { border-left-color:#c8920a; }
.metric-card.dst { border-left-color:#1a5c3a; }
.metric-card.grd { border-left-color:#c41e2a; }
.metric-label { font-size:0.45rem; letter-spacing:2px; color:#8a7d6e; text-transform:uppercase; }
.metric-val { font-family:'Barlow Condensed',sans-serif; font-weight:900; font-size:1.8rem; line-height:1.1; color:#0f0d0b; }
.metric-unit { font-size:0.4rem; color:#8a7d6e; letter-spacing:1px; }

.coaching-box { background:#f7f3ee; border-left:4px solid #0f3460; padding:16px 18px;
                font-size:0.65rem; line-height:2; white-space:pre-wrap; color:#0f0d0b; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="tl-header">
  <div>
    <div class="tl-logo">THROWS<em>LAB</em></div>
    <div class="tl-logo-sub">POSITION BREAKDOWN SYSTEM</div>
  </div>
</div>
""", unsafe_allow_html=True)


# ── FRAME EXTRACTION ──
def extract_frames(video_path: str) -> list:
    frames = []
    try:
        import cv2
        cap   = cv2.VideoCapture(video_path)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps   = cap.get(cv2.CAP_PROP_FPS) or 30
        dur   = total / fps
        count = min(48, max(16, int(dur * 12)))
        indices = [round(i / (count - 1) * (total - 1)) for i in range(count)] if count > 1 else [total // 2]
        MAX_W = 640
        for idx in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if not ret:
                continue
            h, w = frame.shape[:2]
            if w > MAX_W:
                frame = cv2.resize(frame, (MAX_W, int(h * MAX_W / w)))
            img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=75)
            b64 = base64.b64encode(buf.getvalue()).decode()
            frames.append({"time": round(idx / fps, 2), "b64": b64, "img": img})
        cap.release()
    except ImportError:
        st.error("opencv-python-headless is required — add it to requirements.txt.")
    return frames


# ── CLAUDE CALLS ──
def call_claude(client, content: list, max_tokens: int = 1000) -> str:
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": content}],
    )
    return response.content[0].text


def analyze_position(client, frame: dict, pos: dict, event_type: str) -> dict:
    tn = {"discus": "discus", "shot_glide": "shot put glide", "shot_spin": "shot put rotational spin"}[event_type]
    criteria_list = "\n".join(f"{i+1}. {c}" for i, c in enumerate(pos["criteria"][event_type]))
    prompt = f"""You are an elite throws coach analyzing a {tn} athlete.
This frame shows the "{pos['name']}" position ({pos['desc']}).

Evaluate:
{criteria_list}

Return ONLY valid JSON (no markdown, no explanation):
{{
  "verdict": "good|ok|warn",
  "verdict_label": "EXCELLENT|SOLID|NEEDS WORK|FAULT DETECTED",
  "checks": [{{"criterion":"...","status":"pass|warn|fail","note":"brief specific observation"}}],
  "one_line": "most important observation, max 15 words",
  "cue": "one field coaching cue, max 12 words",
  "release_angle": null,
  "velocity_estimate": null
}}
For the Delivery/Release position only, estimate release_angle (degrees) and velocity_estimate (m/s, conservative)."""

    raw = call_claude(client, [
        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": frame["b64"]}},
        {"type": "text", "text": prompt},
    ], max_tokens=700)
    try:
        return json.loads(raw.strip().replace("```json","").replace("```","").strip())
    except Exception:
        return {"verdict":"ok","verdict_label":"ANALYZED","checks":[],"one_line":"Analysis complete.",
                "cue":"Keep working on fundamentals.","release_angle":None,"velocity_estimate":None}


def get_coaching(client, analysis_data: list, physics: dict, event_type: str, athlete: str, pr: str) -> str:
    tn = {"discus":"discus","shot_glide":"shot put (glide)","shot_spin":"shot put (spin)"}[event_type]
    summary = "\n".join(f"{d['posName']}: {d.get('verdict_label','—')} — {d.get('one_line','')}" for d in analysis_data if d)
    faults  = "\n".join(
        f"[{d['posName']}] {c['criterion']}: {c.get('note','')}"
        for d in analysis_data if d
        for c in d.get("checks",[]) if c.get("status") in ("fail","warn")
    ) or "None detected"
    prompt = f"""Elite throws coach writing a session report for {athlete}, {tn}.{f' Current PR: {pr}.' if pr else ''}

Position analysis:
{summary}

Faults identified:
{faults}

Physics: velocity {physics['velocity']} m/s, angle {physics['angle']}°, predicted {physics['dist_ft']} ft.

Write a report with these exact sections:
STRENGTHS:
FAULTS TO FIX:
SESSION CUES:
NEXT SESSION FOCUS:
PROJECTION:

Direct coach voice. Reference positions by name."""
    raw = call_claude(client, [{"type":"text","text":prompt}], max_tokens=900)
    return re.sub(r'\*{1,2}(.*?)\*{1,2}', r'\1', raw)


def compute_physics(analysis_data: list, event_type: str) -> dict:
    rel = next((d for d in analysis_data if d and d.get("posId") == "release"), None)
    defaults = {"discus":(37,17),"shot_spin":(39,10),"shot_glide":(39,10)}
    def_angle, def_vel = defaults[event_type]
    try:    angle    = float(rel["release_angle"])    if rel and rel.get("release_angle")    is not None else def_angle
    except: angle    = def_angle
    try:    velocity = float(rel["velocity_estimate"]) if rel and rel.get("velocity_estimate") is not None else def_vel
    except: velocity = def_vel
    h0 = 1.8 if event_type == "discus" else 2.1
    g  = 9.81; ar = math.radians(angle)
    dist_m  = (velocity*math.cos(ar)/g)*(velocity*math.sin(ar)+math.sqrt((velocity*math.sin(ar))**2+2*g*h0))
    dist_ft = round(dist_m*3.28084,1)
    verdicts = [d.get("verdict") for d in analysis_data if d]
    score    = round((verdicts.count("good")/max(1,len(verdicts)))*10 - verdicts.count("warn")*0.5)
    grade    = "A" if score>=8 else "B" if score>=6 else "C" if score>=4 else "D"
    return {"velocity":round(velocity,1),"angle":round(angle,1),"dist_m":round(dist_m,2),"dist_ft":dist_ft,"grade":grade}


# ── SIDEBAR ──
with st.sidebar:
    st.markdown('<div class="section-title">API KEY</div>', unsafe_allow_html=True)
    api_key = st.text_input("Anthropic API Key", type="password", placeholder="sk-ant-...", help="Session only")

    st.markdown('<div class="section-title">EVENT</div>', unsafe_allow_html=True)
    event_type = st.radio("Event", ["shot_spin","shot_glide","discus"],
                          format_func=lambda x: EVENT_LABELS[x], label_visibility="collapsed")

    st.markdown('<div class="section-title">ATHLETE</div>', unsafe_allow_html=True)
    athlete_name  = st.text_input("Name", placeholder="Athlete name...")
    athlete_date  = st.date_input("Session Date")
    athlete_pr    = st.text_input("Current PR", placeholder="e.g. 42ft / 130ft")
    athlete_notes = st.text_area("Notes", placeholder="Meet, drill, conditions...", height=68)

    st.markdown('<div class="section-title">VIDEO</div>', unsafe_allow_html=True)
    uploaded = st.file_uploader("Upload throw video", type=["mp4","mov","webm","avi"])

    st.markdown('<div class="section-title">METRICS</div>', unsafe_allow_html=True)
    if "physics" in st.session_state:
        p = st.session_state.physics
        c1,c2 = st.columns(2)
        with c1:
            st.markdown(f'<div class="metric-card vel"><div class="metric-label">Velocity</div><div class="metric-val">{p["velocity"]}</div><div class="metric-unit">m/s</div></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-card dst"><div class="metric-label">Distance</div><div class="metric-val">{p["dist_ft"]}</div><div class="metric-unit">feet</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="metric-card ang"><div class="metric-label">Angle</div><div class="metric-val">{p["angle"]}°</div><div class="metric-unit">deg</div></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-card grd"><div class="metric-label">Grade</div><div class="metric-val">{p["grade"]}</div><div class="metric-unit">technique</div></div>', unsafe_allow_html=True)
    else:
        st.caption("Complete frame assignment and run analysis to see metrics.")


# ── EXTRACT FRAMES ON UPLOAD ──
# When a new video is uploaded, extract frames and store them. Clear old assignments.
if uploaded:
    uploaded_name = uploaded.name
    if st.session_state.get("_last_upload") != uploaded_name:
        st.session_state["_last_upload"] = uploaded_name
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded.name)[1]) as tmp:
            tmp.write(uploaded.read())
            tmp_path = tmp.name
        with st.spinner("Extracting frames..."):
            frames = extract_frames(tmp_path)
        try: os.unlink(tmp_path)
        except: pass
        st.session_state["frames"]       = frames
        st.session_state["assignments"]  = {}   # pos_id -> frame index
        st.session_state["active_pos"]   = 0    # which position slot is being assigned
        # Clear any previous analysis
        for k in ["analysis","physics","coaching"]:
            st.session_state.pop(k, None)
        st.rerun()
else:
    # No video — clear frames if previously set
    if "frames" in st.session_state and st.session_state.get("_last_upload"):
        st.session_state.pop("frames", None)
        st.session_state.pop("assignments", None)
        st.session_state.pop("active_pos", None)
        st.session_state.pop("_last_upload", None)


# ── MAIN HEADER ──
hcol1, hcol2 = st.columns([3,1])
with hcol1:
    st.markdown(f"""
    <div style="border-bottom:2px solid #0f0d0b;padding-bottom:8px;margin-bottom:16px;">
      <span style="font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:1.5rem;letter-spacing:4px;text-transform:uppercase;">Position Breakdown</span>
      <span style="font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:0.65rem;letter-spacing:3px;color:#c41e2a;border:1px solid #c41e2a;padding:2px 8px;margin-left:12px;">{EVENT_LABELS[event_type]}</span>
      <span style="font-size:0.55rem;color:#8a7d6e;margin-left:12px;">{athlete_name or 'No athlete loaded'}</span>
    </div>
    """, unsafe_allow_html=True)

all_frames   = st.session_state.get("frames", [])
assignments  = st.session_state.get("assignments", {})
active_pos   = st.session_state.get("active_pos", 0)
n_assigned   = sum(1 for p in POSITIONS if p["id"] in assignments)

with hcol2:
    all_assigned = n_assigned == len(POSITIONS)
    can_analyze  = all_assigned and api_key and bool(all_frames)
    analyze_btn  = st.button("⚡ ANALYZE", type="primary",
                             disabled=not can_analyze, use_container_width=True,
                             help="Assign all 6 positions first" if not all_assigned else "")
    report_btn   = st.button("↓ REPORT", disabled="analysis" not in st.session_state, use_container_width=True)


# ════════════════════════════════════════════
# STEP 1 — FRAME ASSIGNMENT UI
# ════════════════════════════════════════════
if all_frames and "analysis" not in st.session_state:

    st.markdown('<div class="section-title">STEP 1 — ASSIGN FRAMES TO POSITIONS</div>', unsafe_allow_html=True)
    st.caption(f"Click a position slot on the left, then click a frame on the right to assign it. "
               f"**{n_assigned}/6 assigned.**")

    left_col, right_col = st.columns([1, 3])

    # ── Left: position slot list ──
    with left_col:
        for i, pos in enumerate(POSITIONS):
            is_active  = (i == active_pos)
            is_filled  = pos["id"] in assignments
            slot_class = "pos-slot active" if is_active else ("pos-slot filled" if is_filled else "pos-slot")

            if is_filled:
                fi = assignments[pos["id"]]
                assigned_time = all_frames[fi]["time"] if fi < len(all_frames) else "?"
                status_html = f'<div class="pos-slot-status ok">✓ t={assigned_time}s assigned</div>'
            else:
                status_html = f'<div class="pos-slot-status miss">— not assigned</div>'

            st.markdown(f"""
            <div class="{slot_class}">
              <div class="pos-slot-name">{pos['icon']} {pos['short']}</div>
              <div class="pos-slot-desc">{pos['desc']}</div>
              {status_html}
            </div>
            """, unsafe_allow_html=True)

            btn_label = "▶ Editing" if is_active else ("✎ Change" if is_filled else "Select")
            btn_type  = "primary" if is_active else "secondary"
            if st.button(btn_label, key=f"slot_btn_{i}", use_container_width=True, type=btn_type):
                st.session_state["active_pos"] = i
                st.rerun()

    # ── Right: frame carousel ──
    with right_col:
        active_pos_obj = POSITIONS[active_pos]
        st.markdown(f"""
        <div style="font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:0.75rem;
                    letter-spacing:3px;text-transform:uppercase;color:#c41e2a;margin-bottom:8px;">
          Assigning: {active_pos_obj['icon']} {active_pos_obj['name']}
          <span style="font-weight:400;color:#8a7d6e;margin-left:8px;font-size:0.6rem;">{active_pos_obj['desc']}</span>
        </div>
        """, unsafe_allow_html=True)

        # Show frames in rows of 4
        ROW_SIZE = 4
        current_assignment = assignments.get(active_pos_obj["id"])

        for row_start in range(0, len(all_frames), ROW_SIZE):
            row_frames = all_frames[row_start : row_start + ROW_SIZE]
            cols = st.columns(len(row_frames))
            for j_rel, fr in enumerate(row_frames):
                j_abs = row_start + j_rel
                with cols[j_rel]:
                    is_selected = (j_abs == current_assignment)

                    # Check if this frame is assigned to another position
                    other_pos = next(
                        (POSITIONS[k]["short"] for k, p in enumerate(POSITIONS)
                         if p["id"] != active_pos_obj["id"] and assignments.get(p["id"]) == j_abs),
                        None
                    )

                    st.image(fr["img"], use_container_width=True)

                    if is_selected:
                        label = f"✓ {fr['time']}s"
                        btn_t = "primary"
                    elif other_pos:
                        label = f"[{other_pos}] {fr['time']}s"
                        btn_t = "secondary"
                    else:
                        label = f"{fr['time']}s"
                        btn_t = "secondary"

                    if st.button(label, key=f"frame_{active_pos}_{j_abs}",
                                 use_container_width=True, type=btn_t):
                        st.session_state["assignments"][active_pos_obj["id"]] = j_abs
                        # Auto-advance to next unassigned position
                        next_unassigned = next(
                            (k for k in range(len(POSITIONS))
                             if POSITIONS[k]["id"] not in st.session_state["assignments"]),
                            None
                        )
                        if next_unassigned is not None:
                            st.session_state["active_pos"] = next_unassigned
                        st.rerun()

    # Progress bar
    if n_assigned > 0:
        st.progress(n_assigned / len(POSITIONS), text=f"{n_assigned}/6 positions assigned")
    if all_assigned:
        st.success("All 6 positions assigned. Hit **⚡ ANALYZE** to run the breakdown.", icon="✓")


# ════════════════════════════════════════════
# STEP 2 — RUN ANALYSIS
# ════════════════════════════════════════════
if analyze_btn and can_analyze:
    client = anthropic.Anthropic(api_key=api_key)
    progress = st.progress(0, text="Starting analysis...")
    log_area = st.empty()
    logs: list = []

    def log(msg, kind=""):
        logs.append(("✓ " if kind=="ok" else "⚠ " if kind=="warn" else "› ") + msg)
        log_area.code("\n".join(logs[-8:]), language=None)

    try:
        analysis_data = []
        for i, pos in enumerate(POSITIONS):
            frame_idx = assignments[pos["id"]]
            frame     = all_frames[frame_idx]
            log(f"Analyzing {pos['name']} (t={frame['time']}s)...")
            progress.progress(int(i / len(POSITIONS) * 85), text=f"Analyzing {pos['name']}...")

            result = analyze_position(client, frame, pos, event_type)
            result.update({"frame": frame, "posName": pos["name"], "posId": pos["id"]})
            analysis_data.append(result)
            log(f"{pos['name']}: {result.get('verdict_label','—')}", "ok")

        progress.progress(90, text="Generating coaching report...")
        log("Generating coaching report...")
        physics  = compute_physics(analysis_data, event_type)
        coaching = get_coaching(client, analysis_data, physics, event_type,
                                athlete_name or "Athlete", athlete_pr)

        st.session_state.update({
            "analysis":   analysis_data,
            "physics":    physics,
            "coaching":   coaching,
            "event_type": event_type,
            "athlete":    athlete_name or "Athlete",
        })
        progress.progress(100, text="Analysis complete ✓")
        log("Analysis complete", "ok")

    except Exception as e:
        st.error(f"Analysis failed: {e}")
        import traceback; traceback.print_exc()

    st.rerun()


# ════════════════════════════════════════════
# STEP 3 — DISPLAY RESULTS
# ════════════════════════════════════════════
if "analysis" in st.session_state:
    analysis_data = st.session_state.analysis
    ev            = st.session_state.get("event_type", event_type)

    # Re-assign button to go back and change frames
    if all_frames:
        if st.button("← Re-assign Frames", type="secondary"):
            st.session_state.pop("analysis", None)
            st.session_state.pop("physics", None)
            st.session_state.pop("coaching", None)
            st.rerun()

    st.markdown('<div class="section-title">6-POSITION BREAKDOWN</div>', unsafe_allow_html=True)
    grid_cols = st.columns(3)

    for i, pos in enumerate(POSITIONS):
        data          = analysis_data[i] if i < len(analysis_data) else None
        verdict       = (data or {}).get("verdict", "pending")
        verdict_label = (data or {}).get("verdict_label", "PENDING")
        one_line      = (data or {}).get("one_line", "Awaiting analysis")
        current_frame = (data or {}).get("frame")
        frame_time    = f"t={current_frame['time']:.2f}s" if current_frame else "—"
        verdict_cls   = {"good":"verdict-good","warn":"verdict-warn","ok":"verdict-ok"}.get(verdict,"verdict-pending")

        with grid_cols[i % 3]:
            if current_frame and current_frame.get("img"):
                st.image(current_frame["img"], use_container_width=True)
            else:
                st.markdown(f'<div style="width:100%;aspect-ratio:4/3;background:#ede8e1;display:flex;align-items:center;justify-content:center;font-size:2rem;color:#ccc;">{pos["icon"]}</div>', unsafe_allow_html=True)

            st.markdown(f"""
            <div style="padding:10px 4px 4px 4px;">
              <div class="pos-card-name">{pos['icon']} {pos['name']}</div>
              <div class="pos-card-verdict {verdict_cls}">{verdict_label}</div>
              <div class="pos-card-time">{frame_time}</div>
              <div class="pos-card-note">{one_line}</div>
            </div>
            """, unsafe_allow_html=True)

            if data and data.get("checks"):
                with st.expander("View checklist"):
                    for c in data["checks"]:
                        s    = c.get("status","")
                        icon = "✓" if s=="pass" else "✗" if s=="fail" else "⚠"
                        cls  = "check-pass" if s=="pass" else "check-fail" if s=="fail" else "check-warn"
                        note = f" — <em style='color:#8a7d6e'>{c['note']}</em>" if c.get("note") else ""
                        st.markdown(f'<div class="check-row"><span class="check-icon {cls}">{icon}</span><span>{c["criterion"]}{note}</span></div>', unsafe_allow_html=True)
                    if data.get("cue"):
                        st.markdown(f"**Cue:** *{data['cue']}*")
            else:
                with st.expander("Criteria"):
                    for c in pos["criteria"][ev]:
                        st.markdown(f'<div class="check-row"><span class="check-icon" style="color:#ccc">·</span><span>{c}</span></div>', unsafe_allow_html=True)

    st.markdown('<div class="section-title">COACHING ASSESSMENT</div>', unsafe_allow_html=True)
    if "coaching" in st.session_state:
        st.markdown(f'<div class="coaching-box">{st.session_state.coaching}</div>', unsafe_allow_html=True)


# ════════════════════════════════════════════
# DOWNLOAD REPORT
# ════════════════════════════════════════════
if report_btn and "analysis" in st.session_state:
    p             = st.session_state.physics
    data_list     = st.session_state.analysis
    coaching_text = st.session_state.coaching
    ev            = st.session_state.get("event_type", event_type)
    ath           = st.session_state.get("athlete", athlete_name or "Athlete")

    cells_html = ""
    for i, pos in enumerate(POSITIONS):
        d   = data_list[i] if i < len(data_list) else None
        v   = (d or {}).get("verdict","ok")
        vl  = (d or {}).get("verdict_label","PENDING")
        ol  = (d or {}).get("one_line","—")
        col = {"good":"#1a5c3a","warn":"#c41e2a"}.get(v,"#0f3460")
        img = (f'<img src="data:image/jpeg;base64,{d["frame"]["b64"]}" style="width:100%;aspect-ratio:4/3;object-fit:cover;display:block;">'
               if d and d.get("frame") and d["frame"].get("b64")
               else f'<div style="width:100%;aspect-ratio:4/3;background:#ede8e1;display:flex;align-items:center;justify-content:center;color:#ccc;font-size:1.5rem;">{pos["icon"]}</div>')
        cells_html += (f'<div style="border:1px solid #d4cabf;overflow:hidden;">{img}'
                       f'<div style="padding:8px 10px;">'
                       f'<div style="font-family:\'Barlow Condensed\',sans-serif;font-weight:900;font-size:0.85rem;letter-spacing:2px;text-transform:uppercase;">{pos["name"]}</div>'
                       f'<div style="font-size:0.45rem;font-family:\'Barlow Condensed\',sans-serif;font-weight:700;letter-spacing:2px;padding:1px 6px;background:{col}18;color:{col};border:1px solid {col}40;display:inline-block;margin-top:3px;">{vl}</div>'
                       f'<div style="font-size:0.5rem;color:#555;line-height:1.6;margin-top:4px;">{ol}</div>'
                       f'</div></div>')

    faults_html = ""
    for i, pos in enumerate(POSITIONS):
        d = data_list[i] if i < len(data_list) else None
        if not d or not d.get("checks"): continue
        faults = [c for c in d["checks"] if c.get("status") != "pass"]
        if not faults: continue
        faults_html += f'<div style="margin-bottom:10px;"><div style="font-weight:700;font-size:0.75rem;letter-spacing:2px;">{pos["name"].upper()}</div>'
        for c in faults:
            faults_html += f'<div style="font-size:0.55rem;color:#555;padding-left:12px;">⚠ {c["criterion"]} — {c.get("note","")}</div>'
        faults_html += "</div>"

    report_html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@700;900&family=Courier+Prime:wght@400;700&display=swap');
body{{font-family:'Courier Prime',monospace;background:#fff;color:#0f0d0b;padding:32px;max-width:900px;margin:0 auto;}}
.hdr{{border-bottom:3px solid #c41e2a;padding-bottom:12px;margin-bottom:20px;display:flex;justify-content:space-between;align-items:flex-end;}}
.logo{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:2rem;letter-spacing:8px;text-transform:uppercase;}}
.logo em{{color:#c41e2a;font-style:normal;}}
.bar{{background:#0f0d0b;color:#fff;padding:8px 16px;margin-bottom:20px;font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:0.9rem;letter-spacing:4px;display:flex;gap:32px;}}
.bar em{{color:#c41e2a;font-style:normal;}}
.sec{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:0.6rem;letter-spacing:5px;text-transform:uppercase;color:#8a7d6e;border-bottom:1px solid #d4cabf;padding-bottom:4px;margin-bottom:14px;margin-top:20px;}}
.mets{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px;}}
.met{{border:1px solid #d4cabf;padding:12px;border-top:3px solid #d4cabf;}}
.met.v{{border-top-color:#0f3460;}}.met.a{{border-top-color:#c8920a;}}.met.d{{border-top-color:#1a5c3a;}}.met.f{{border-top-color:#c41e2a;}}
.ml{{font-size:0.42rem;letter-spacing:2px;color:#8a7d6e;margin-bottom:4px;}}
.mv{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:2rem;line-height:1;}}
.mu{{font-size:0.4rem;color:#8a7d6e;}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:24px;}}
.coaching{{background:#f7f3ee;border-left:4px solid #0f3460;padding:14px 16px;font-size:0.6rem;line-height:2;white-space:pre-wrap;margin-bottom:24px;}}
.notes{{border:1px solid #d4cabf;padding:14px;min-height:70px;margin-bottom:24px;font-size:0.6rem;color:#aaa;font-style:italic;}}
.footer{{border-top:1px solid #d4cabf;padding-top:10px;font-size:0.42rem;color:#aaa;letter-spacing:2px;display:flex;justify-content:space-between;}}
@media print{{.noprint{{display:none!important;}}}}
</style></head><body>
<div class="hdr">
  <div><div class="logo">THROWS<em>LAB</em></div><div style="font-size:0.45rem;letter-spacing:4px;color:#aaa;">POSITION BREAKDOWN REPORT</div></div>
  <div style="font-size:0.55rem;text-align:right;line-height:2;color:#666;">
    <strong>{ath.upper()}</strong><br>{EVENT_LABELS[ev]}<br>{athlete_date}
    {"<br>PR: "+athlete_pr if athlete_pr else ""}{"<br><em>"+athlete_notes+"</em>" if athlete_notes else ""}
  </div>
</div>
<div class="bar"><span>{ath.upper()}</span><span><em>{EVENT_LABELS[ev]}</em></span><span>THROWSLAB ANALYSIS</span></div>
<div class="sec">Performance Metrics</div>
<div class="mets">
  <div class="met v"><div class="ml">Est. Release Velocity</div><div class="mv">{p['velocity']}</div><div class="mu">m/s</div></div>
  <div class="met a"><div class="ml">Release Angle</div><div class="mv">{p['angle']}°</div><div class="mu">degrees</div></div>
  <div class="met d"><div class="ml">Predicted Distance</div><div class="mv">{p['dist_ft']}</div><div class="mu">feet</div></div>
  <div class="met f"><div class="ml">Technique Grade</div><div class="mv">{p['grade']}</div><div class="mu">overall</div></div>
</div>
<div class="sec">6-Position Breakdown</div>
<div class="grid">{cells_html}</div>
{"<div class='sec'>Issues Flagged</div><div style='margin-bottom:24px;'>"+faults_html+"</div>" if faults_html.strip() else ""}
<div class="sec">Coaching Assessment</div>
<div class="coaching">{coaching_text}</div>
<div class="sec">Coach Notes</div>
<div class="notes" contenteditable="true">Click to add session notes...</div>
<div class="footer">
  <span>THROWSLAB — POSITION BREAKDOWN SYSTEM</span>
  <span>GENERATED {str(athlete_date).upper()}</span>
</div>
<div class="noprint" style="margin-top:20px;text-align:right;">
  <button onclick="window.print()" style="font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:0.8rem;letter-spacing:2px;padding:10px 24px;background:#0f0d0b;color:#fff;border:none;cursor:pointer;">🖨 PRINT / SAVE PDF</button>
</div>
</body></html>"""

    st.download_button(
        label="⬇ Download Report HTML",
        data=report_html,
        file_name=f"throwslab_{(athlete_name or 'athlete').lower().replace(' ','_')}_{athlete_date}.html",
        mime="text/html",
        use_container_width=True,
    )
    st.info("Download → open in browser → File → Print → Save as PDF", icon="💡")
