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

# ── POSITIONS CONFIG ──
POSITIONS = {
    "shot_spin": [
        {"id": "setup",      "name": "Setup",             "icon": "①", "criteria": ["Feet shoulder-width apart", "Shot tucked at neck/jaw", "Throwing arm elbow up", "Back to sector", "Weight centered"]},
        {"id": "entry",      "name": "Entry / Jackknife", "icon": "②", "criteria": ["Deep knee bend on pivot foot", "Free leg sweeps low and wide", "Hips low — jackknife position", "Back still to sector", "Shot stays at neck"]},
        {"id": "mid",        "name": "Mid-Rotation",      "icon": "③", "criteria": ["Back fully facing sector", "Left leg driving through", "Hips ahead of shoulders", "Low center of gravity", "Not opening too early"]},
        {"id": "power",      "name": "Power Position",    "icon": "④", "criteria": ["Left foot plants near center", "Right foot behind center", "Hip-shoulder separation 45°+", "Shot still at neck", "Knees bent — loaded"]},
        {"id": "release",    "name": "Release",           "icon": "⑤", "criteria": ["Elbow at or above shoulder", "Release angle 38-42°", "Full leg extension", "Left arm blocks hard", "Chin-wrist-elbow aligned"]},
        {"id": "followthru", "name": "Follow-Through",    "icon": "⑥", "criteria": ["Reverse completes", "Right foot replaces left", "Does not foul", "Full rotation through", "Balance maintained"]},
    ],
    "shot_glide": [
        {"id": "setup",      "name": "Setup",          "icon": "①", "criteria": ["Back to sector", "Shot at neck/jaw", "Feet hip-width", "Knee bend comfortable", "Weight on right foot"]},
        {"id": "entry",      "name": "Glide Entry",    "icon": "②", "criteria": ["Right foot drives back", "Low glide — not a hop", "Left leg extends toward board", "Hips stay low", "Shot stays at neck"]},
        {"id": "mid",        "name": "Flight Phase",   "icon": "③", "criteria": ["Body parallel to ground", "Both feet briefly off surface", "Low trajectory", "Left foot heading to board", "Shot still loaded"]},
        {"id": "power",      "name": "Power Position", "icon": "④", "criteria": ["Left foot at toe board", "Right foot behind center", "Hip-shoulder separation", "Knees bent and loaded", "Shot at neck"]},
        {"id": "release",    "name": "Release",        "icon": "⑤", "criteria": ["Elbow at or above shoulder", "Release angle 38-42°", "Full leg extension", "Left arm blocks", "Chin-wrist-elbow aligned"]},
        {"id": "followthru", "name": "Follow-Through", "icon": "⑥", "criteria": ["Reverse completes", "Right foot replaces left", "No foul", "Balance maintained", "Full extension shown"]},
    ],
    "discus": [
        {"id": "setup",      "name": "Setup",          "icon": "①", "criteria": ["Feet shoulder-width", "Discus rests on fingers — not palm", "Weight centered", "Back to sector", "Arms relaxed"]},
        {"id": "entry",      "name": "Wind / Entry",   "icon": "②", "criteria": ["Preliminary swing builds momentum", "Discus tracks back high", "Weight shifts right", "Pivot foot heel rises", "Body coiling"]},
        {"id": "mid",        "name": "Mid-Rotation",   "icon": "③", "criteria": ["Back fully to sector", "Left leg driving", "Discus trails behind shoulder", "Hips ahead of shoulders", "Low and wide — not upright"]},
        {"id": "power",      "name": "Power Position", "icon": "④", "criteria": ["Left foot plants", "Discus at shoulder height", "Hip-shoulder separation 45°+", "Throwing arm extended back", "Weight loaded right"]},
        {"id": "release",    "name": "Release",        "icon": "⑤", "criteria": ["Discus leaves index finger", "Release angle 35-40°", "Arm sweeps up — not flat", "Left arm blocks", "Disc flies flat — good attitude"]},
        {"id": "followthru", "name": "Follow-Through", "icon": "⑥", "criteria": ["Full rotation through", "Reverse if needed", "Disc attitude stable in air", "No foul", "Balance in circle"]},
    ],
}

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

.tl-header {
    background: #0f0d0b;
    padding: 14px 28px;
    border-bottom: 3px solid #c41e2a;
    display: flex;
    align-items: center;
    gap: 16px;
    margin: -1rem -1rem 1.5rem -1rem;
}
.tl-logo {
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 900;
    font-size: 1.6rem;
    letter-spacing: 8px;
    color: #fff;
    text-transform: uppercase;
}
.tl-logo em { color: #c41e2a; font-style: normal; }
.tl-logo-sub {
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 0.5rem;
    letter-spacing: 4px;
    color: #444;
}

.pos-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 4px;
    margin-bottom: 1.5rem;
}
.pos-card {
    background: #fff;
    border: 1px solid #d4cabf;
    border-top: 3px solid #d4cabf;
    padding: 0;
    overflow: hidden;
    font-family: 'Courier Prime', monospace;
}
.pos-card.good  { border-top-color: #1a5c3a; }
.pos-card.warn  { border-top-color: #c41e2a; }
.pos-card.ok    { border-top-color: #0f3460; }
.pos-card.pending { border-top-color: #d4cabf; }

.pos-card-img { width: 100%; aspect-ratio: 4/3; object-fit: cover; display: block; background: #ede8e1; }
.pos-card-img-placeholder {
    width: 100%; aspect-ratio: 4/3;
    background: #ede8e1;
    display: flex; align-items: center; justify-content: center;
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 2rem; color: #ccc;
}
.pos-card-body { padding: 10px 12px; }
.pos-card-name {
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 900; font-size: 0.85rem;
    letter-spacing: 2px; text-transform: uppercase;
    color: #0f0d0b;
}
.pos-card-verdict {
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 700; font-size: 0.5rem;
    letter-spacing: 2px; padding: 2px 7px;
    display: inline-block; margin-top: 3px;
}
.verdict-good  { background: rgba(26,92,58,.12);  color: #1a5c3a; border: 1px solid rgba(26,92,58,.25); }
.verdict-warn  { background: rgba(196,30,42,.1);  color: #c41e2a; border: 1px solid rgba(196,30,42,.2); }
.verdict-ok    { background: rgba(15,52,96,.08);  color: #0f3460; border: 1px solid rgba(15,52,96,.15); }
.verdict-pending { background: #f0ece6; color: #8a7d6e; border: 1px solid #d4cabf; }

.pos-card-note { font-size: 0.55rem; color: #555; line-height: 1.6; margin-top: 5px; }
.pos-card-time { font-size: 0.45rem; color: #aaa; letter-spacing: 1px; margin-top: 2px; }

.check-row { display: flex; gap: 8px; align-items: flex-start; font-size: 0.6rem; line-height: 1.6; padding: 3px 0; border-bottom: 1px solid #f0ece6; }
.check-icon { font-size: 0.75rem; flex-shrink: 0; width: 16px; }
.check-pass { color: #1a5c3a; }
.check-warn { color: #c8920a; }
.check-fail { color: #c41e2a; }

.metric-card {
    background: #fff;
    border: 1px solid #d4cabf;
    padding: 12px 14px;
    border-left: 3px solid #d4cabf;
}
.metric-card.vel { border-left-color: #0f3460; }
.metric-card.ang { border-left-color: #c8920a; }
.metric-card.dst { border-left-color: #1a5c3a; }
.metric-card.grd { border-left-color: #c41e2a; }
.metric-label { font-size: 0.45rem; letter-spacing: 2px; color: #8a7d6e; text-transform: uppercase; }
.metric-val {
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 900; font-size: 1.8rem; line-height: 1.1; color: #0f0d0b;
}
.metric-unit { font-size: 0.4rem; color: #8a7d6e; letter-spacing: 1px; }

.section-title {
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 700; font-size: 0.6rem;
    letter-spacing: 5px; text-transform: uppercase;
    color: #8a7d6e; border-bottom: 1px solid #d4cabf;
    padding-bottom: 5px; margin-bottom: 14px; margin-top: 20px;
}

.coaching-box {
    background: #f7f3ee;
    border-left: 4px solid #0f3460;
    padding: 16px 18px;
    font-size: 0.65rem;
    line-height: 2;
    white-space: pre-wrap;
    color: #0f0d0b;
}

.report-page {
    font-family: 'Courier Prime', monospace;
    background: #fff; padding: 40px;
    max-width: 900px; margin: 0 auto;
    color: #0f0d0b;
}
</style>
""", unsafe_allow_html=True)

# ── HEADER ──
st.markdown("""
<div class="tl-header">
  <div>
    <div class="tl-logo">THROWS<em>LAB</em></div>
    <div class="tl-logo-sub">POSITION BREAKDOWN SYSTEM</div>
  </div>
</div>
""", unsafe_allow_html=True)


# ── HELPERS ──

def extract_frames(video_path: str, num_frames: int = 10) -> list[dict]:
    """Extract evenly-spaced frames from video using ffmpeg via PIL fallback or cv2."""
    frames = []
    try:
        import cv2
        cap = cv2.VideoCapture(video_path)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        duration = total / fps

        count = min(12, max(6, int(duration * 4)))
        count = max(count, num_frames)
        count = min(count, 12)

        indices = [round(i / (count - 1) * (total - 1)) for i in range(count)] if count > 1 else [total // 2]

        MAX_W = 640
        for idx in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if not ret:
                continue
            h, w = frame.shape[:2]
            if w > MAX_W:
                scale = MAX_W / w
                frame = cv2.resize(frame, (MAX_W, int(h * scale)))
            # cv2 is BGR — convert to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=75)
            b64 = base64.b64encode(buf.getvalue()).decode()
            frames.append({
                "time": round(idx / fps, 2),
                "b64": b64,
                "img": img,
            })
        cap.release()

    except ImportError:
        st.warning("opencv-python not installed — install it for best frame extraction. Falling back to single-frame mode.")
        # Fallback: just read the file bytes and treat as single image (won't work for video)

    return frames


def img_to_b64(img: Image.Image, quality: int = 75) -> str:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode()


def call_claude(client: anthropic.Anthropic, content: list, max_tokens: int = 1000) -> str:
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": content}],
    )
    return response.content[0].text


def identify_positions(client, frames: list, positions: list, event_type: str) -> list:
    """Pass 1: ask Claude which frame best represents each position."""
    sample_count = min(8, len(frames))
    sample = [frames[round(i / (sample_count - 1) * (len(frames) - 1))] for i in range(sample_count)] if sample_count > 1 else frames[:1]

    tn_map = {"discus": "discus", "shot_glide": "shot put (glide technique)", "shot_spin": "shot put (rotational/spin technique)"}
    tn = tn_map[event_type]
    pos_names = "\n".join(f"{i+1}. {p['name']}" for i, p in enumerate(positions))

    content = [
        *[{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": f["b64"]}} for f in sample],
        {"type": "text", "text": f"""These are {len(sample)} sequential frames from a {tn} throw video.

The 6 positions I need identified are:
{pos_names}

For each position (1-6), return the index (0-{len(sample)-1}) of the frame that best represents it, or null if not clearly visible.

Return ONLY a JSON array of {len(positions)} numbers/nulls. Example: [0,1,2,3,5,6]
No explanation, just the array."""}
    ]

    raw = call_claude(client, content, max_tokens=300)
    txt = raw.strip().replace("```json", "").replace("```", "").strip()
    try:
        indices = json.loads(txt)
        return [sample[idx] if idx is not None and isinstance(idx, int) and 0 <= idx < len(sample) else None for idx in indices]
    except Exception:
        # Fallback: evenly distribute
        return [sample[round(i / (len(positions) - 1) * (len(sample) - 1))] if len(positions) > 1 else sample[0] for i in range(len(positions))]


def analyze_position(client, frame: dict, pos: dict, event_type: str) -> dict:
    """Pass 2: deep analysis of a single position frame."""
    tn_map = {"discus": "discus", "shot_glide": "shot put glide", "shot_spin": "shot put rotational spin"}
    tn = tn_map[event_type]
    criteria_list = "\n".join(f"{i+1}. {c}" for i, c in enumerate(pos["criteria"]))

    prompt = f"""You are an elite throws coach analyzing a {tn} athlete.

This frame shows the "{pos['name']}" position.

Evaluate these specific criteria:
{criteria_list}

Return ONLY valid JSON:
{{
  "verdict": "good|ok|warn",
  "verdict_label": "one of: EXCELLENT|SOLID|NEEDS WORK|FAULT DETECTED",
  "checks": [
    {{"criterion": "...", "status": "pass|warn|fail", "note": "brief specific observation"}}
  ],
  "one_line": "single most important observation about this position (max 15 words)",
  "cue": "the one coaching cue you would say right now on the field (max 12 words)",
  "release_angle": null,
  "velocity_estimate": null
}}

For the release position only, fill in release_angle (degrees) and velocity_estimate (m/s, be conservative)."""

    content = [
        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": frame["b64"]}},
        {"type": "text", "text": prompt},
    ]

    raw = call_claude(client, content, max_tokens=600)
    try:
        return json.loads(raw.strip().replace("```json", "").replace("```", "").strip())
    except Exception:
        return {"verdict": "ok", "verdict_label": "ANALYZED", "checks": [], "one_line": "Analysis complete.", "cue": "Keep working on fundamentals.", "release_angle": None, "velocity_estimate": None}


def get_coaching(client, analysis_data: list, physics: dict, event_type: str, athlete: str, pr: str) -> str:
    tn_map = {"discus": "discus", "shot_glide": "shot put (glide)", "shot_spin": "shot put (spin)"}
    tn = tn_map[event_type]

    summary = "\n".join(f"{d['posName']}: {d.get('verdict_label','—')} — {d.get('one_line','')}" for d in analysis_data if d)
    faults_list = []
    for d in analysis_data:
        if not d:
            continue
        for c in d.get("checks", []):
            if c.get("status") in ("fail", "warn"):
                faults_list.append(f"[{d['posName']}] {c['criterion']}: {c.get('note','')}")
    faults = "\n".join(faults_list) or "None detected"

    prompt = f"""Elite throws coach writing a session report for {athlete}, {tn}.{f" Current PR: {pr}." if pr else ""}

Position analysis:
{summary}

Technical faults identified:
{faults}

Physics estimates:
- Release velocity: {physics['velocity']} m/s
- Release angle: {physics['angle']}°
- Predicted distance: {physics['dist_ft']} feet

Write a coaching report with these exact sections (use the headers as written):

STRENGTHS:
(2-3 specific things working well, reference positions)

FAULTS TO FIX:
(ranked by priority — most impactful first, with position reference)

SESSION CUES:
(3-4 field cues, short and memorable, the kind you shout from the infield)

NEXT SESSION FOCUS:
(1-2 specific drills or priorities for next practice)

PROJECTION:
(realistic distance gain if top fault is fixed, and timeline)

Direct, specific, coach voice. Reference positions by name."""

    raw = call_claude(client, [{"type": "text", "text": prompt}], max_tokens=900)
    # Strip markdown bold/italic
    return re.sub(r'\*{1,2}(.*?)\*{1,2}', r'\1', raw)


def compute_physics(analysis_data: list, event_type: str) -> dict:
    rel = next((d for d in analysis_data if d and d.get("posId") == "release"), None)
    raw_angle = rel.get("release_angle") if rel else None
    raw_vel   = rel.get("velocity_estimate") if rel else None

    defaults = {"discus": (37, 17), "shot_spin": (39, 10), "shot_glide": (39, 10)}
    def_angle, def_vel = defaults[event_type]

    try:
        angle = float(raw_angle) if raw_angle is not None else def_angle
    except (TypeError, ValueError):
        angle = def_angle
    try:
        velocity = float(raw_vel) if raw_vel is not None else def_vel
    except (TypeError, ValueError):
        velocity = def_vel

    h0 = 1.8 if event_type == "discus" else 2.1
    g = 9.81
    ar = math.radians(angle)
    dist_m = (velocity * math.cos(ar) / g) * (velocity * math.sin(ar) + math.sqrt((velocity * math.sin(ar))**2 + 2 * g * h0))
    dist_ft = round(dist_m * 3.28084, 1)

    verdicts = [d.get("verdict") for d in analysis_data if d]
    goods = verdicts.count("good")
    warns = verdicts.count("warn")
    score = round((goods / max(1, len(verdicts))) * 10 - warns * 0.5)
    grade = "A" if score >= 8 else "B" if score >= 6 else "C" if score >= 4 else "D"

    return {
        "velocity": round(velocity, 1),
        "angle":    round(angle, 1),
        "dist_m":   round(dist_m, 2),
        "dist_ft":  dist_ft,
        "grade":    grade,
    }


# ── SIDEBAR ──
with st.sidebar:
    st.markdown('<div class="section-title">API KEY</div>', unsafe_allow_html=True)
    api_key = st.text_input("Anthropic API Key", type="password", placeholder="sk-ant-...", help="Never stored — session only")

    st.markdown('<div class="section-title">EVENT</div>', unsafe_allow_html=True)
    event_type = st.radio(
        "Event",
        options=["shot_spin", "shot_glide", "discus"],
        format_func=lambda x: EVENT_LABELS[x],
        label_visibility="collapsed",
    )

    st.markdown('<div class="section-title">ATHLETE</div>', unsafe_allow_html=True)
    athlete_name = st.text_input("Name", placeholder="Athlete name...")
    athlete_date = st.date_input("Session Date")
    athlete_pr   = st.text_input("Current PR", placeholder="e.g. 42ft / 130ft")
    athlete_notes = st.text_area("Notes", placeholder="Meet, drill, conditions...", height=68)

    st.markdown('<div class="section-title">VIDEO</div>', unsafe_allow_html=True)
    uploaded = st.file_uploader("Upload throw video", type=["mp4", "mov", "webm", "avi"])

    st.markdown('<div class="section-title">METRICS</div>', unsafe_allow_html=True)
    if "physics" in st.session_state:
        p = st.session_state.physics
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f'<div class="metric-card vel"><div class="metric-label">Velocity</div><div class="metric-val">{p["velocity"]}</div><div class="metric-unit">m/s</div></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-card dst"><div class="metric-label">Distance</div><div class="metric-val">{p["dist_ft"]}</div><div class="metric-unit">feet</div></div>', unsafe_allow_html=True)
        with col2:
            st.markdown(f'<div class="metric-card ang"><div class="metric-label">Angle</div><div class="metric-val">{p["angle"]}°</div><div class="metric-unit">deg</div></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-card grd"><div class="metric-label">Grade</div><div class="metric-val">{p["grade"]}</div><div class="metric-unit">technique</div></div>', unsafe_allow_html=True)
    else:
        st.caption("Run analysis to see metrics.")


# ── MAIN AREA ──
positions = POSITIONS[event_type]

# Header row
hcol1, hcol2 = st.columns([3, 1])
with hcol1:
    st.markdown(f"""
    <div style="border-bottom: 2px solid #0f0d0b; padding-bottom: 8px; margin-bottom: 16px;">
      <span style="font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:1.5rem;letter-spacing:4px;text-transform:uppercase;">Position Breakdown</span>
      <span style="font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:0.65rem;letter-spacing:3px;color:#c41e2a;border:1px solid #c41e2a;padding:2px 8px;margin-left:12px;">{EVENT_LABELS[event_type]}</span>
      <span style="font-size:0.55rem;color:#8a7d6e;margin-left:12px;">{athlete_name or 'No athlete loaded'}</span>
    </div>
    """, unsafe_allow_html=True)
with hcol2:
    run_btn = st.button("⚡ ANALYZE", type="primary", disabled=not uploaded or not api_key, use_container_width=True)
    report_btn = st.button("↓ REPORT", disabled="analysis" not in st.session_state, use_container_width=True)


# ── RUN ANALYSIS ──
if run_btn and uploaded and api_key:
    client = anthropic.Anthropic(api_key=api_key)

    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded.name)[1]) as tmp:
        tmp.write(uploaded.read())
        tmp_path = tmp.name

    progress = st.progress(0, text="Extracting frames...")
    log_area = st.empty()
    logs = []

    def log(msg, kind=""):
        logs.append(("✓ " + msg) if kind == "ok" else ("⚠ " + msg) if kind == "warn" else ("› " + msg))
        log_area.code("\n".join(logs[-8:]), language=None)

    try:
        frames = extract_frames(tmp_path)
        if not frames:
            st.error("Could not extract frames. Make sure opencv-python is installed.")
            st.stop()

        log(f"{len(frames)} frames extracted", "ok")
        progress.progress(10, text="Pass 1 — identifying positions...")

        identified = identify_positions(client, frames, positions, event_type)
        log(f"Identified {sum(1 for x in identified if x)}/{len(positions)} positions", "ok")
        progress.progress(35, text="Pass 2 — analyzing each position...")

        analysis_data = []
        for i, (frame, pos) in enumerate(zip(identified, positions)):
            log(f"Analyzing: {pos['name']}...")
            progress.progress(35 + int((i / len(positions)) * 50), text=f"Analyzing {pos['name']}...")

            if frame is None:
                analysis_data.append(None)
                log(f"No frame found for {pos['name']}", "warn")
                continue

            result = analyze_position(client, frame, pos, event_type)
            result["frame"] = frame
            result["posName"] = pos["name"]
            result["posId"] = pos["id"]
            analysis_data.append(result)
            log(f"{pos['name']}: {result.get('verdict_label','—')}", "ok")

        progress.progress(90, text="Generating coaching report...")
        log("Generating coaching report...")

        physics = compute_physics(analysis_data, event_type)
        coaching = get_coaching(client, analysis_data, physics, event_type,
                                athlete_name or "Athlete", athlete_pr)

        st.session_state.analysis    = analysis_data
        st.session_state.physics     = physics
        st.session_state.coaching    = coaching
        st.session_state.event_type  = event_type
        st.session_state.athlete     = athlete_name or "Athlete"
        st.session_state.frames      = frames

        progress.progress(100, text="Analysis complete ✓")
        log("Analysis complete", "ok")

    except Exception as e:
        st.error(f"Analysis failed: {e}")
        import traceback; traceback.print_exc()
    finally:
        os.unlink(tmp_path)

    st.rerun()


# ── DISPLAY RESULTS ──
analysis_data = st.session_state.get("analysis", [None] * 6)
if not analysis_data:
    analysis_data = [None] * 6

# Build the 6-position grid
grid_cols = st.columns(3)
for i, pos in enumerate(positions):
    data = analysis_data[i] if i < len(analysis_data) else None
    verdict = data.get("verdict", "pending") if data else "pending"
    verdict_label = data.get("verdict_label", "PENDING") if data else "PENDING"
    one_line = data.get("one_line", "Awaiting analysis") if data else "Awaiting analysis"
    frame_time = f"t={data['frame']['time']:.2f}s" if data and data.get("frame") else "—"

    with grid_cols[i % 3]:
        # Thumbnail
        if data and data.get("frame") and data["frame"].get("img"):
            st.image(data["frame"]["img"], use_container_width=True)
        else:
            st.markdown(f'<div class="pos-card-img-placeholder">{pos["icon"]}</div>', unsafe_allow_html=True)

        # Status badge
        verdict_cls = {"good": "verdict-good", "warn": "verdict-warn", "ok": "verdict-ok"}.get(verdict, "verdict-pending")
        st.markdown(f"""
        <div class="pos-card-body">
          <div class="pos-card-name">{pos['icon']} {pos['name']}</div>
          <div class="pos-card-verdict {verdict_cls}">{verdict_label}</div>
          <div class="pos-card-time">{frame_time}</div>
          <div class="pos-card-note">{one_line}</div>
        </div>
        """, unsafe_allow_html=True)

        # Expandable checklist
        if data and data.get("checks"):
            with st.expander("View checklist"):
                for c in data["checks"]:
                    status = c.get("status", "")
                    icon = "✓" if status == "pass" else "✗" if status == "fail" else "⚠"
                    cls  = "check-pass" if status == "pass" else "check-fail" if status == "fail" else "check-warn"
                    note = f" — <em style='color:#8a7d6e'>{c['note']}</em>" if c.get("note") else ""
                    st.markdown(f'<div class="check-row"><span class="check-icon {cls}">{icon}</span><span>{c["criterion"]}{note}</span></div>', unsafe_allow_html=True)
                if data.get("cue"):
                    st.markdown(f"**Cue:** *{data['cue']}*")
        else:
            with st.expander("Criteria"):
                for c in pos["criteria"]:
                    st.markdown(f'<div class="check-row"><span class="check-icon" style="color:#ccc">·</span><span>{c}</span></div>', unsafe_allow_html=True)


# ── COACHING REPORT ──
st.markdown('<div class="section-title">COACHING ASSESSMENT</div>', unsafe_allow_html=True)
if "coaching" in st.session_state:
    st.markdown(f'<div class="coaching-box">{st.session_state.coaching}</div>', unsafe_allow_html=True)
else:
    st.caption("Load a video and run analysis to generate the coaching report.")


# ── PRINT REPORT ──
if report_btn and "analysis" in st.session_state:
    p = st.session_state.physics
    data_list = st.session_state.analysis
    coaching_text = st.session_state.coaching
    ev = st.session_state.get("event_type", event_type)
    ath = st.session_state.get("athlete", athlete_name or "Athlete")
    pos_list = POSITIONS[ev]

    # Build position cells HTML
    cells_html = ""
    for i, pos in enumerate(pos_list):
        d = data_list[i] if i < len(data_list) else None
        verdict = d.get("verdict", "ok") if d else "ok"
        verdict_label = d.get("verdict_label", "PENDING") if d else "PENDING"
        one_line = d.get("one_line", "—") if d else "—"
        color = {"good": "#1a5c3a", "warn": "#c41e2a"}.get(verdict, "#0f3460")

        img_tag = ""
        if d and d.get("frame") and d["frame"].get("b64"):
            img_tag = f'<img src="data:image/jpeg;base64,{d["frame"]["b64"]}" style="width:100%;aspect-ratio:4/3;object-fit:cover;display:block;">'
        else:
            img_tag = f'<div style="width:100%;aspect-ratio:4/3;background:#ede8e1;display:flex;align-items:center;justify-content:center;color:#ccc;font-size:1.5rem;">{pos["icon"]}</div>'

        cells_html += f"""
        <div style="border:1px solid #d4cabf;overflow:hidden;break-inside:avoid;">
          {img_tag}
          <div style="padding:8px 10px;">
            <div style="font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:0.85rem;letter-spacing:2px;text-transform:uppercase;">{pos['name']}</div>
            <div style="font-size:0.45rem;font-family:'Barlow Condensed',sans-serif;font-weight:700;letter-spacing:2px;padding:1px 6px;background:{color}18;color:{color};border:1px solid {color}40;display:inline-block;margin-top:3px;">{verdict_label}</div>
            <div style="font-size:0.5rem;color:#555;line-height:1.6;margin-top:4px;">{one_line}</div>
          </div>
        </div>"""

    # Faults section
    faults_html = ""
    for i, pos in enumerate(pos_list):
        d = data_list[i] if i < len(data_list) else None
        if not d or not d.get("checks"):
            continue
        faults = [c for c in d["checks"] if c.get("status") != "pass"]
        if not faults:
            continue
        faults_html += f'<div style="margin-bottom:10px;"><div style="font-family:\'Barlow Condensed\',sans-serif;font-weight:700;font-size:0.75rem;letter-spacing:2px;color:#0f0d0b;margin-bottom:4px;">{pos["name"].upper()}</div>'
        for c in faults:
            faults_html += f'<div style="font-size:0.55rem;color:#555;line-height:1.8;padding-left:12px;">⚠ {c["criterion"]} — {c.get("note","")}</div>'
        faults_html += "</div>"

    report_html = f"""
    <!DOCTYPE html><html><head>
    <meta charset="UTF-8">
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@700;900&family=Courier+Prime:wght@400;700&display=swap');
    body{{font-family:'Courier Prime',monospace;background:#fff;color:#0f0d0b;padding:32px;max-width:900px;margin:0 auto;}}
    .header{{border-bottom:3px solid #c41e2a;padding-bottom:12px;margin-bottom:20px;display:flex;justify-content:space-between;align-items:flex-end;}}
    .logo{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:2rem;letter-spacing:8px;text-transform:uppercase;}}
    .logo em{{color:#c41e2a;font-style:normal;}}
    .meta{{font-size:0.55rem;text-align:right;line-height:2;color:#666;}}
    .bar{{background:#0f0d0b;color:#fff;padding:8px 16px;margin-bottom:20px;font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:0.9rem;letter-spacing:4px;display:flex;gap:32px;}}
    .bar em{{color:#c41e2a;font-style:normal;}}
    .sec{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:0.6rem;letter-spacing:5px;text-transform:uppercase;color:#8a7d6e;border-bottom:1px solid #d4cabf;padding-bottom:4px;margin-bottom:14px;margin-top:20px;}}
    .metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px;}}
    .met{{border:1px solid #d4cabf;padding:12px;border-top:3px solid #d4cabf;}}
    .met.v{{border-top-color:#0f3460;}}.met.a{{border-top-color:#c8920a;}}.met.d{{border-top-color:#1a5c3a;}}.met.f{{border-top-color:#c41e2a;}}
    .met-lbl{{font-size:0.42rem;letter-spacing:2px;color:#8a7d6e;margin-bottom:4px;}}
    .met-val{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:2rem;line-height:1;}}
    .met-unit{{font-size:0.4rem;color:#8a7d6e;margin-top:2px;}}
    .grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:24px;}}
    .coaching{{background:#f7f3ee;border-left:4px solid #0f3460;padding:14px 16px;font-size:0.6rem;line-height:2;white-space:pre-wrap;margin-bottom:24px;}}
    .notes{{border:1px solid #d4cabf;padding:14px;min-height:70px;margin-bottom:24px;font-size:0.6rem;color:#aaa;font-style:italic;}}
    .footer{{border-top:1px solid #d4cabf;padding-top:10px;font-size:0.42rem;color:#aaa;letter-spacing:2px;display:flex;justify-content:space-between;}}
    @media print{{.no-print{{display:none!important;}}}}
    </style></head><body>
    <div class="header">
      <div><div class="logo">THROWS<em>LAB</em></div><div style="font-size:0.45rem;letter-spacing:4px;color:#aaa;">POSITION BREAKDOWN REPORT</div></div>
      <div class="meta"><strong>{ath.upper()}</strong><br>{EVENT_LABELS[ev]}<br>{athlete_date}<br>{"PR: "+athlete_pr+"<br>" if athlete_pr else ""}{"<em>"+athlete_notes+"</em>" if athlete_notes else ""}</div>
    </div>
    <div class="bar"><span>{ath.upper()}</span><span><em>{EVENT_LABELS[ev]}</em></span><span>THROWSLAB ANALYSIS</span></div>
    <div class="sec">Performance Metrics</div>
    <div class="metrics">
      <div class="met v"><div class="met-lbl">Est. Release Velocity</div><div class="met-val">{p['velocity']}</div><div class="met-unit">m/s</div></div>
      <div class="met a"><div class="met-lbl">Release Angle</div><div class="met-val">{p['angle']}°</div><div class="met-unit">degrees</div></div>
      <div class="met d"><div class="met-lbl">Predicted Distance</div><div class="met-val">{p['dist_ft']}</div><div class="met-unit">feet</div></div>
      <div class="met f"><div class="met-lbl">Technique Grade</div><div class="met-val">{p['grade']}</div><div class="met-unit">overall</div></div>
    </div>
    <div class="sec">6-Position Breakdown</div>
    <div class="grid">{cells_html}</div>
    {"<div class='sec'>Issues Flagged</div><div style='margin-bottom:24px;'>"+faults_html+"</div>" if faults_html.strip() else ""}
    <div class="sec">Coaching Assessment</div>
    <div class="coaching">{coaching_text}</div>
    <div class="sec">Coach Notes</div>
    <div class="notes" contenteditable="true">Click to add session notes, goals, or corrections for next practice...</div>
    <div class="footer">
      <span>THROWSLAB — POSITION BREAKDOWN SYSTEM</span>
      <span>GENERATED {str(athlete_date).upper()}</span>
    </div>
    <div class="no-print" style="margin-top:20px;text-align:right;">
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
    st.info("Download the HTML file and open it in your browser, then use **File → Print → Save as PDF** to get a printable report.", icon="💡")
