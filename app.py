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
.tl-header { background:#0f0d0b; padding:14px 28px; border-bottom:3px solid #c41e2a; display:flex; align-items:center; gap:16px; margin:-1rem -1rem 1.5rem -1rem; }
.tl-logo { font-family:'Barlow Condensed',sans-serif; font-weight:900; font-size:1.6rem; letter-spacing:8px; color:#fff; text-transform:uppercase; }
.tl-logo em { color:#c41e2a; font-style:normal; }
.tl-logo-sub { font-family:'Barlow Condensed',sans-serif; font-size:0.5rem; letter-spacing:4px; color:#444; }
.pos-card-img-placeholder { width:100%; aspect-ratio:4/3; background:#ede8e1; display:flex; align-items:center; justify-content:center; font-family:'Barlow Condensed',sans-serif; font-size:2rem; color:#ccc; }
.pos-card-body { padding:10px 12px; }
.pos-card-name { font-family:'Barlow Condensed',sans-serif; font-weight:900; font-size:0.85rem; letter-spacing:2px; text-transform:uppercase; color:#0f0d0b; }
.pos-card-verdict { font-family:'Barlow Condensed',sans-serif; font-weight:700; font-size:0.5rem; letter-spacing:2px; padding:2px 7px; display:inline-block; margin-top:3px; }
.verdict-good  { background:rgba(26,92,58,.12);  color:#1a5c3a; border:1px solid rgba(26,92,58,.25); }
.verdict-warn  { background:rgba(196,30,42,.1);  color:#c41e2a; border:1px solid rgba(196,30,42,.2); }
.verdict-ok    { background:rgba(15,52,96,.08);  color:#0f3460; border:1px solid rgba(15,52,96,.15); }
.verdict-pending { background:#f0ece6; color:#8a7d6e; border:1px solid #d4cabf; }
.pos-card-note { font-size:0.55rem; color:#555; line-height:1.6; margin-top:5px; }
.pos-card-time { font-size:0.45rem; color:#aaa; letter-spacing:1px; margin-top:2px; }
.check-row { display:flex; gap:8px; align-items:flex-start; font-size:0.6rem; line-height:1.6; padding:3px 0; border-bottom:1px solid #f0ece6; }
.check-icon { font-size:0.75rem; flex-shrink:0; width:16px; }
.check-pass { color:#1a5c3a; }
.check-warn { color:#c8920a; }
.check-fail { color:#c41e2a; }
.metric-card { background:#fff; border:1px solid #d4cabf; padding:12px 14px; border-left:3px solid #d4cabf; margin-bottom:8px; }
.metric-card.vel { border-left-color:#0f3460; }
.metric-card.ang { border-left-color:#c8920a; }
.metric-card.dst { border-left-color:#1a5c3a; }
.metric-card.grd { border-left-color:#c41e2a; }
.metric-label { font-size:0.45rem; letter-spacing:2px; color:#8a7d6e; text-transform:uppercase; }
.metric-val { font-family:'Barlow Condensed',sans-serif; font-weight:900; font-size:1.8rem; line-height:1.1; color:#0f0d0b; }
.metric-unit { font-size:0.4rem; color:#8a7d6e; letter-spacing:1px; }
.section-title { font-family:'Barlow Condensed',sans-serif; font-weight:700; font-size:0.6rem; letter-spacing:5px; text-transform:uppercase; color:#8a7d6e; border-bottom:1px solid #d4cabf; padding-bottom:5px; margin-bottom:14px; margin-top:20px; }
.coaching-box { background:#f7f3ee; border-left:4px solid #0f3460; padding:16px 18px; font-size:0.65rem; line-height:2; white-space:pre-wrap; color:#0f0d0b; }
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


# ── HELPERS ──

def extract_frames(video_path: str) -> list:
    frames = []
    try:
        import cv2
        cap   = cv2.VideoCapture(video_path)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps   = cap.get(cv2.CAP_PROP_FPS) or 30
        dur   = total / fps
        count = min(12, max(6, int(dur * 4)))
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


def call_claude(client, content: list, max_tokens: int = 1000) -> str:
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": content}],
    )
    return response.content[0].text


def identify_positions(client, frames: list, positions: list, event_type: str) -> list:
    """Pass 1 — send ALL frames, no subsampling, for accurate position mapping."""
    tn = {"discus": "discus", "shot_glide": "shot put (glide)", "shot_spin": "shot put (rotational/spin)"}[event_type]
    pos_names = "\n".join(f"{i+1}. {p['name']}" for i, p in enumerate(positions))

    content = [
        *[{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": f["b64"]}}
          for f in frames],
        {"type": "text", "text": f"""These are {len(frames)} sequential frames (0 to {len(frames)-1}) from a {tn} throw video, in chronological order.

Identify the 6 technical positions:
{pos_names}

Rules:
- Earlier positions (Setup, Entry) belong to lower-numbered frames; later positions (Release, Follow-Through) to higher-numbered frames.
- Do NOT assign the same frame index to two positions.
- If a position is not clearly visible, return null.

Return ONLY a JSON array of exactly {len(positions)} integers or nulls. Example: [0,2,4,7,9,11]
No explanation, no markdown."""}
    ]

    raw = call_claude(client, content, max_tokens=150)
    txt = raw.strip().replace("```json", "").replace("```", "").strip()
    try:
        indices = json.loads(txt)
        return [
            frames[idx] if idx is not None and isinstance(idx, int) and 0 <= idx < len(frames)
            else None
            for idx in indices
        ]
    except Exception:
        n = len(positions)
        return [frames[round(i / (n - 1) * (len(frames) - 1))] for i in range(n)]


def analyze_position(client, frame: dict, pos: dict, event_type: str) -> dict:
    tn = {"discus": "discus", "shot_glide": "shot put glide", "shot_spin": "shot put rotational spin"}[event_type]
    criteria_list = "\n".join(f"{i+1}. {c}" for i, c in enumerate(pos["criteria"]))

    prompt = f"""You are an elite throws coach analyzing a {tn} athlete.
This frame shows the "{pos['name']}" position.

Evaluate:
{criteria_list}

Return ONLY valid JSON (no markdown):
{{
  "verdict": "good|ok|warn",
  "verdict_label": "EXCELLENT|SOLID|NEEDS WORK|FAULT DETECTED",
  "checks": [{{"criterion":"...","status":"pass|warn|fail","note":"brief observation"}}],
  "one_line": "most important observation, max 15 words",
  "cue": "field coaching cue, max 12 words",
  "release_angle": null,
  "velocity_estimate": null
}}
For the release position only, fill release_angle (degrees) and velocity_estimate (m/s, conservative)."""

    raw = call_claude(client, [
        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": frame["b64"]}},
        {"type": "text", "text": prompt},
    ], max_tokens=700)

    try:
        return json.loads(raw.strip().replace("```json", "").replace("```", "").strip())
    except Exception:
        return {"verdict": "ok", "verdict_label": "ANALYZED", "checks": [],
                "one_line": "Analysis complete.", "cue": "Keep working on fundamentals.",
                "release_angle": None, "velocity_estimate": None}


def get_coaching(client, analysis_data: list, physics: dict, event_type: str, athlete: str, pr: str) -> str:
    tn = {"discus": "discus", "shot_glide": "shot put (glide)", "shot_spin": "shot put (spin)"}[event_type]
    summary = "\n".join(f"{d['posName']}: {d.get('verdict_label','—')} — {d.get('one_line','')}" for d in analysis_data if d)
    faults  = "\n".join(
        f"[{d['posName']}] {c['criterion']}: {c.get('note','')}"
        for d in analysis_data if d
        for c in d.get("checks", []) if c.get("status") in ("fail", "warn")
    ) or "None detected"

    prompt = f"""Elite throws coach writing a session report for {athlete}, {tn}.{f' Current PR: {pr}.' if pr else ''}

Position analysis:
{summary}

Faults identified:
{faults}

Physics: velocity {physics['velocity']} m/s, angle {physics['angle']}°, predicted {physics['dist_ft']} ft.

Write a report with these sections:

STRENGTHS:
FAULTS TO FIX:
SESSION CUES:
NEXT SESSION FOCUS:
PROJECTION:

Direct coach voice. Reference positions by name."""

    raw = call_claude(client, [{"type": "text", "text": prompt}], max_tokens=900)
    return re.sub(r'\*{1,2}(.*?)\*{1,2}', r'\1', raw)


def compute_physics(analysis_data: list, event_type: str) -> dict:
    rel = next((d for d in analysis_data if d and d.get("posId") == "release"), None)
    defaults = {"discus": (37, 17), "shot_spin": (39, 10), "shot_glide": (39, 10)}
    def_angle, def_vel = defaults[event_type]
    try:
        angle = float(rel["release_angle"]) if rel and rel.get("release_angle") is not None else def_angle
    except (TypeError, ValueError):
        angle = def_angle
    try:
        velocity = float(rel["velocity_estimate"]) if rel and rel.get("velocity_estimate") is not None else def_vel
    except (TypeError, ValueError):
        velocity = def_vel

    h0 = 1.8 if event_type == "discus" else 2.1
    g  = 9.81
    ar = math.radians(angle)
    dist_m  = (velocity * math.cos(ar) / g) * (velocity * math.sin(ar) + math.sqrt((velocity * math.sin(ar))**2 + 2 * g * h0))
    dist_ft = round(dist_m * 3.28084, 1)
    verdicts = [d.get("verdict") for d in analysis_data if d]
    score    = round((verdicts.count("good") / max(1, len(verdicts))) * 10 - verdicts.count("warn") * 0.5)
    grade    = "A" if score >= 8 else "B" if score >= 6 else "C" if score >= 4 else "D"
    return {"velocity": round(velocity, 1), "angle": round(angle, 1),
            "dist_m": round(dist_m, 2), "dist_ft": dist_ft, "grade": grade}


# ── SIDEBAR ──
with st.sidebar:
    st.markdown('<div class="section-title">API KEY</div>', unsafe_allow_html=True)
    api_key = st.text_input("Anthropic API Key", type="password", placeholder="sk-ant-...", help="Session only — never stored")

    st.markdown('<div class="section-title">EVENT</div>', unsafe_allow_html=True)
    event_type = st.radio("Event", ["shot_spin", "shot_glide", "discus"],
                          format_func=lambda x: EVENT_LABELS[x], label_visibility="collapsed")

    st.markdown('<div class="section-title">ATHLETE</div>', unsafe_allow_html=True)
    athlete_name  = st.text_input("Name", placeholder="Athlete name...")
    athlete_date  = st.date_input("Session Date")
    athlete_pr    = st.text_input("Current PR", placeholder="e.g. 42ft / 130ft")
    athlete_notes = st.text_area("Notes", placeholder="Meet, drill, conditions...", height=68)

    st.markdown('<div class="section-title">VIDEO</div>', unsafe_allow_html=True)
    uploaded = st.file_uploader("Upload throw video", type=["mp4", "mov", "webm", "avi"])

    st.markdown('<div class="section-title">METRICS</div>', unsafe_allow_html=True)
    if "physics" in st.session_state:
        p = st.session_state.physics
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f'<div class="metric-card vel"><div class="metric-label">Velocity</div><div class="metric-val">{p["velocity"]}</div><div class="metric-unit">m/s</div></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-card dst"><div class="metric-label">Distance</div><div class="metric-val">{p["dist_ft"]}</div><div class="metric-unit">feet</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="metric-card ang"><div class="metric-label">Angle</div><div class="metric-val">{p["angle"]}°</div><div class="metric-unit">deg</div></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-card grd"><div class="metric-label">Grade</div><div class="metric-val">{p["grade"]}</div><div class="metric-unit">technique</div></div>', unsafe_allow_html=True)
    else:
        st.caption("Run analysis to see metrics.")


# ── MAIN ──
positions = POSITIONS[event_type]

hcol1, hcol2 = st.columns([3, 1])
with hcol1:
    st.markdown(f"""
    <div style="border-bottom:2px solid #0f0d0b;padding-bottom:8px;margin-bottom:16px;">
      <span style="font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:1.5rem;letter-spacing:4px;text-transform:uppercase;">Position Breakdown</span>
      <span style="font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:0.65rem;letter-spacing:3px;color:#c41e2a;border:1px solid #c41e2a;padding:2px 8px;margin-left:12px;">{EVENT_LABELS[event_type]}</span>
      <span style="font-size:0.55rem;color:#8a7d6e;margin-left:12px;">{athlete_name or 'No athlete loaded'}</span>
    </div>
    """, unsafe_allow_html=True)
with hcol2:
    run_btn    = st.button("⚡ ANALYZE", type="primary", disabled=not uploaded or not api_key, use_container_width=True)
    report_btn = st.button("↓ REPORT",  disabled="analysis" not in st.session_state, use_container_width=True)


# ── FULL ANALYSIS ──
if run_btn and uploaded and api_key:
    client = anthropic.Anthropic(api_key=api_key)
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded.name)[1]) as tmp:
        tmp.write(uploaded.read())
        tmp_path = tmp.name

    progress = st.progress(0, text="Extracting frames...")
    log_area = st.empty()
    logs: list = []

    def log(msg, kind=""):
        logs.append(("✓ " if kind == "ok" else "⚠ " if kind == "warn" else "› ") + msg)
        log_area.code("\n".join(logs[-8:]), language=None)

    try:
        frames = extract_frames(tmp_path)
        if not frames:
            st.error("Frame extraction failed. Ensure opencv-python-headless is installed.")
            st.stop()

        log(f"{len(frames)} frames extracted", "ok")
        progress.progress(10, text=f"Pass 1 — sending all {len(frames)} frames to Claude...")

        identified = identify_positions(client, frames, positions, event_type)
        log(f"Identified {sum(1 for x in identified if x)}/{len(positions)} positions", "ok")
        progress.progress(35, text="Pass 2 — analyzing each position...")

        analysis_data = []
        for i, (frame, pos) in enumerate(zip(identified, positions)):
            log(f"Analyzing: {pos['name']}...")
            progress.progress(35 + int(i / len(positions) * 50), text=f"Analyzing {pos['name']}...")
            if frame is None:
                analysis_data.append(None)
                log(f"No frame found for {pos['name']}", "warn")
                continue
            result = analyze_position(client, frame, pos, event_type)
            result.update({"frame": frame, "posName": pos["name"], "posId": pos["id"]})
            analysis_data.append(result)
            log(f"{pos['name']}: {result.get('verdict_label','—')}", "ok")

        progress.progress(90, text="Generating coaching report...")
        physics  = compute_physics(analysis_data, event_type)
        coaching = get_coaching(client, analysis_data, physics, event_type,
                                athlete_name or "Athlete", athlete_pr)

        st.session_state.update({
            "analysis": analysis_data, "physics": physics, "coaching": coaching,
            "event_type": event_type, "athlete": athlete_name or "Athlete", "frames": frames,
        })
        # Clear stale override selections
        for k in [k for k in st.session_state if k.startswith("sel_frame_")]:
            del st.session_state[k]

        progress.progress(100, text="Analysis complete ✓")
        log("Analysis complete", "ok")

    except Exception as e:
        st.error(f"Analysis failed: {e}")
        import traceback; traceback.print_exc()
    finally:
        try: os.unlink(tmp_path)
        except Exception: pass
    st.rerun()


# ── SINGLE-POSITION RE-ANALYSIS (after frame override) ──
trigger = st.session_state.pop("_reanalyze_trigger", None)
if trigger and "analysis" in st.session_state and api_key:
    pos_idx = st.session_state.pop(trigger + "_pos_idx", None)
    frame   = st.session_state.pop(trigger + "_frame", None)
    if pos_idx is not None and frame is not None:
        pos = positions[pos_idx]
        ev  = st.session_state.get("event_type", event_type)
        with st.spinner(f"Re-analyzing {pos['name']}..."):
            try:
                client   = anthropic.Anthropic(api_key=api_key)
                result   = analyze_position(client, frame, pos, ev)
                result.update({"frame": frame, "posName": pos["name"], "posId": pos["id"]})
                ad       = list(st.session_state.analysis)
                ad[pos_idx] = result
                physics  = compute_physics(ad, ev)
                coaching = get_coaching(client, ad, physics, ev,
                                        st.session_state.get("athlete", "Athlete"), athlete_pr)
                st.session_state.update({"analysis": ad, "physics": physics, "coaching": coaching})
            except Exception as e:
                st.error(f"Re-analysis failed: {e}")
        st.rerun()


# ── 6-POSITION GRID ──
analysis_data = st.session_state.get("analysis") or [None] * 6
all_frames    = st.session_state.get("frames", [])
grid_cols     = st.columns(3)

for i, pos in enumerate(positions):
    data          = analysis_data[i] if i < len(analysis_data) else None
    verdict       = (data or {}).get("verdict", "pending")
    verdict_label = (data or {}).get("verdict_label", "PENDING")
    one_line      = (data or {}).get("one_line", "Awaiting analysis")
    current_frame = (data or {}).get("frame")
    frame_time    = f"t={current_frame['time']:.2f}s" if current_frame else "—"
    verdict_cls   = {"good": "verdict-good", "warn": "verdict-warn", "ok": "verdict-ok"}.get(verdict, "verdict-pending")

    with grid_cols[i % 3]:
        # Thumbnail
        if current_frame and current_frame.get("img"):
            st.image(current_frame["img"], use_container_width=True)
        else:
            st.markdown(f'<div class="pos-card-img-placeholder">{pos["icon"]}</div>', unsafe_allow_html=True)

        # Info
        st.markdown(f"""
        <div class="pos-card-body">
          <div class="pos-card-name">{pos['icon']} {pos['name']}</div>
          <div class="pos-card-verdict {verdict_cls}">{verdict_label}</div>
          <div class="pos-card-time">{frame_time}</div>
          <div class="pos-card-note">{one_line}</div>
        </div>
        """, unsafe_allow_html=True)

        # Checklist
        if data and data.get("checks"):
            with st.expander("View checklist"):
                for c in data["checks"]:
                    s    = c.get("status", "")
                    icon = "✓" if s == "pass" else "✗" if s == "fail" else "⚠"
                    cls  = "check-pass" if s == "pass" else "check-fail" if s == "fail" else "check-warn"
                    note = f" — <em style='color:#8a7d6e'>{c['note']}</em>" if c.get("note") else ""
                    st.markdown(f'<div class="check-row"><span class="check-icon {cls}">{icon}</span><span>{c["criterion"]}{note}</span></div>', unsafe_allow_html=True)
                if data.get("cue"):
                    st.markdown(f"**Cue:** *{data['cue']}*")
        else:
            with st.expander("Criteria"):
                for c in pos["criteria"]:
                    st.markdown(f'<div class="check-row"><span class="check-icon" style="color:#ccc">·</span><span>{c}</span></div>', unsafe_allow_html=True)

        # ── Frame override picker ──
        if all_frames:
            with st.expander("🔄 Change Frame"):
                st.caption(f"Select the correct frame for **{pos['name']}**, then click Re-analyze.")

                # Default selection = whichever frame matches the current assigned one
                default_sel = next(
                    (j for j, f in enumerate(all_frames) if current_frame and f["time"] == current_frame["time"]), 0
                )
                sel_key = f"sel_frame_{i}"
                selected_idx = st.session_state.get(sel_key, default_sel)

                # Thumbnail strip — 4 per row
                ROW = 4
                for row_start in range(0, len(all_frames), ROW):
                    row_frames = all_frames[row_start:row_start + ROW]
                    cols = st.columns(len(row_frames))
                    for j_rel, fr in enumerate(row_frames):
                        j_abs = row_start + j_rel
                        with cols[j_rel]:
                            border = "border:3px solid #c41e2a;" if j_abs == selected_idx else "border:2px solid #d4cabf;"
                            st.image(fr["img"], use_container_width=True)
                            st.caption(f"{fr['time']}s")
                            if st.button("✓", key=f"pick_{i}_{j_abs}",
                                         help=f"Use frame at {fr['time']}s",
                                         use_container_width=True,
                                         type="primary" if j_abs == selected_idx else "secondary"):
                                st.session_state[sel_key] = j_abs
                                st.rerun()

                chosen = all_frames[st.session_state.get(sel_key, default_sel)]
                st.info(f"Selected: **t={chosen['time']}s**", icon="🎯")

                if st.button(f"⚡ Re-analyze {pos['name']}", key=f"reanalyze_{i}", type="primary"):
                    tk = f"_tk_{i}"
                    st.session_state["_reanalyze_trigger"] = tk
                    st.session_state[tk + "_pos_idx"]      = i
                    st.session_state[tk + "_frame"]        = chosen
                    st.rerun()


# ── COACHING REPORT ──
st.markdown('<div class="section-title">COACHING ASSESSMENT</div>', unsafe_allow_html=True)
if "coaching" in st.session_state:
    st.markdown(f'<div class="coaching-box">{st.session_state.coaching}</div>', unsafe_allow_html=True)
else:
    st.caption("Load a video and run analysis to generate the coaching report.")


# ── DOWNLOAD REPORT ──
if report_btn and "analysis" in st.session_state:
    p             = st.session_state.physics
    data_list     = st.session_state.analysis
    coaching_text = st.session_state.coaching
    ev            = st.session_state.get("event_type", event_type)
    ath           = st.session_state.get("athlete", athlete_name or "Athlete")
    pos_list      = POSITIONS[ev]

    cells_html = ""
    for i, pos in enumerate(pos_list):
        d     = data_list[i] if i < len(data_list) else None
        v     = (d or {}).get("verdict", "ok")
        vl    = (d or {}).get("verdict_label", "PENDING")
        ol    = (d or {}).get("one_line", "—")
        col   = {"good": "#1a5c3a", "warn": "#c41e2a"}.get(v, "#0f3460")
        img   = (f'<img src="data:image/jpeg;base64,{d["frame"]["b64"]}" style="width:100%;aspect-ratio:4/3;object-fit:cover;display:block;">'
                 if d and d.get("frame") and d["frame"].get("b64")
                 else f'<div style="width:100%;aspect-ratio:4/3;background:#ede8e1;display:flex;align-items:center;justify-content:center;color:#ccc;font-size:1.5rem;">{pos["icon"]}</div>')
        cells_html += f'<div style="border:1px solid #d4cabf;overflow:hidden;">{img}<div style="padding:8px 10px;"><div style="font-family:\'Barlow Condensed\',sans-serif;font-weight:900;font-size:0.85rem;letter-spacing:2px;text-transform:uppercase;">{pos["name"]}</div><div style="font-size:0.45rem;font-family:\'Barlow Condensed\',sans-serif;font-weight:700;letter-spacing:2px;padding:1px 6px;background:{col}18;color:{col};border:1px solid {col}40;display:inline-block;margin-top:3px;">{vl}</div><div style="font-size:0.5rem;color:#555;line-height:1.6;margin-top:4px;">{ol}</div></div></div>'

    faults_html = ""
    for i, pos in enumerate(pos_list):
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
  <div style="font-size:0.55rem;text-align:right;line-height:2;color:#666;"><strong>{ath.upper()}</strong><br>{EVENT_LABELS[ev]}<br>{athlete_date}{"<br>PR: "+athlete_pr if athlete_pr else ""}{"<br><em>"+athlete_notes+"</em>" if athlete_notes else ""}</div>
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
<div class="footer"><span>THROWSLAB — POSITION BREAKDOWN SYSTEM</span><span>GENERATED {str(athlete_date).upper()}</span></div>
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
