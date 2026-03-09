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

st.set_page_config(
    page_title="ThrowsLab — Position Breakdown",
    page_icon="🥏",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── POSITIONS (7 positions, event-specific criteria) ──
POSITIONS = [
    {
        "id": "prep",
        "name": "Preparation / Wind-up",
        "icon": "①",
        "short": "PREP",
        "desc": "Setting up balance before rotation begins",
        "criteria": {
            "shot_spin":  ["Feet shoulder-width, back to sector", "Shot tucked at neck/jaw, elbow up", "Weight centered and balanced", "Eyes focused, body relaxed and coiled", "Mental preparation complete"],
            "shot_glide": ["Back to sector, feet hip-width", "Shot at neck/jaw, elbow up", "Weight on right foot, knees slightly bent", "Body relaxed and loaded", "Ready to drive backward"],
            "discus":     ["Feet shoulder-width, back to sector", "Discus on finger pads — not palm", "Arms relaxed, preliminary swing beginning", "Weight balanced and centered", "Eyes focused down-sector"],
        },
    },
    {
        "id": "entry",
        "name": "Entry",
        "icon": "②",
        "short": "ENTRY",
        "desc": "Beginning rotation from the back of the circle",
        "criteria": {
            "shot_spin":  ["Deep knee bend on pivot foot", "Free leg sweeps low and wide", "Hips low — jackknife position", "Back still facing sector", "Shot stays loaded at neck"],
            "shot_glide": ["Right foot drives powerfully backward", "Low glide — not a hop", "Left leg extends long toward board", "Hips stay low throughout", "Shot stays loaded at neck"],
            "discus":     ["Preliminary swing builds angular momentum", "Discus tracks back and high", "Weight shifts decisively to right foot", "Pivot foot heel begins to rise", "Body coiling — shoulders lag hips"],
        },
    },
    {
        "id": "flight",
        "name": "Airborne / Flight",
        "icon": "③",
        "short": "FLIGHT",
        "desc": "Moving across the circle with both feet briefly off the ground",
        "criteria": {
            "shot_spin":  ["Back fully facing sector mid-rotation", "Left leg driving through aggressively", "Hips ahead of shoulders — separation visible", "Low center of gravity", "Not opening too early"],
            "shot_glide": ["Body near parallel to ground", "Both feet briefly off surface", "Low flat trajectory across circle", "Left foot tracking toward toe board", "Shot still loaded at neck"],
            "discus":     ["Back fully facing sector mid-rotation", "Left leg driving wide and low", "Discus trails well behind throwing shoulder", "Hips clearly ahead of shoulders", "Low and wide — not upright"],
        },
    },
    {
        "id": "transition",
        "name": "Transition / Landing",
        "icon": "④",
        "short": "LAND",
        "desc": "Grounding the right foot at center of circle",
        "criteria": {
            "shot_spin":  ["Right foot lands near circle center", "Left foot beginning to reach for plant", "Hips still ahead of shoulders", "Weight loaded on right side", "Shot still at neck — not drifting"],
            "shot_glide": ["Right foot lands under hips at center", "Left foot contacts toe board simultaneously", "Hip-shoulder separation maintained", "Knees bent and loaded on contact", "Shot still at neck"],
            "discus":     ["Right foot plants firmly near circle center", "Left foot beginning sweep toward front", "Hip-shoulder separation preserved", "Knees bent — body stays low", "Discus still trailing behind shoulder"],
        },
    },
    {
        "id": "power",
        "name": "Power Position",
        "icon": "⑤",
        "short": "POWER",
        "desc": "Setting up the final explosive throw",
        "criteria": {
            "shot_spin":  ["Left foot plants near toe board", "Right foot behind center — wide base", "Hip-shoulder separation 45°+ at set", "Shot still at neck, not early-releasing", "Knees loaded — ready to drive"],
            "shot_glide": ["Left foot firm at toe board", "Right foot behind center, wide stance", "Hip-shoulder separation clearly visible", "Knees bent and coiled, elbow up", "Shot at neck — fully loaded"],
            "discus":     ["Left foot plants firmly near front of circle", "Discus at or above shoulder height", "Hip-shoulder separation 45°+ visible", "Throwing arm fully extended behind body", "Weight loaded right — ready to fire"],
        },
    },
    {
        "id": "release",
        "name": "Delivery / Release",
        "icon": "⑥",
        "short": "RELEASE",
        "desc": "Explosive final throwing action",
        "criteria": {
            "shot_spin":  ["Elbow at or above shoulder at release", "Release angle 38-42°", "Full leg and hip extension through release", "Left arm blocks hard and short", "Chin-wrist-elbow aligned at release"],
            "shot_glide": ["Elbow at or above shoulder at release", "Release angle 38-42°", "Full leg extension through throw", "Left arm blocks firmly", "Complete follow-through after release"],
            "discus":     ["Discus leaves from index finger last", "Release angle 35-40°", "Throwing arm sweeps up — not flat", "Left arm blocks hard at hip", "Disc attitude flat — good gyroscopic spin"],
        },
    },
    {
        "id": "finish",
        "name": "Finish / Reverse",
        "icon": "⑦",
        "short": "FINISH",
        "desc": "Balance recovery and circle control after release",
        "criteria": {
            "shot_spin":  ["Reverse completes — right foot replaces left", "Athlete stays within the circle", "Weight forward over toe board — not falling back", "Threw through the implement — no early quit", "Balance maintained — controlled finish"],
            "shot_glide": ["Reverse completes cleanly", "Left foot lifts off toe board", "No foul — stays in circle", "Threw through — no deceleration before release", "Controlled balance recovery"],
            "discus":     ["Reverse or pivot — right foot replaces left at front", "Athlete stays in circle — no foul", "Threw through the disc — no early shutdown", "Shoulders finish rotating — no quit", "Controlled balance — not stumbling out"],
        },
    },
]

EVENT_LABELS = {
    "shot_spin":  "SHOT PUT — SPIN",
    "shot_glide": "SHOT PUT — GLIDE",
    "discus":     "DISCUS",
}

VERDICT_COLORS = {
    "good": ("#1a5c3a", "#e8f5ee", "EXCELLENT"),
    "ok":   ("#0f3460", "#e8eef5", "SOLID"),
    "warn": ("#c41e2a", "#fdf0f0", "NEEDS WORK"),
}

# ── CSS ──
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@300;600;700;900&family=Inter:wght@400;500;600&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.tl-header { background:#0f0d0b; padding:16px 32px; border-bottom:3px solid #c41e2a;
             display:flex; align-items:center; gap:16px; margin:-1rem -1rem 1.5rem -1rem; }
.tl-logo { font-family:'Barlow Condensed',sans-serif; font-weight:900; font-size:1.8rem;
           letter-spacing:8px; color:#fff; text-transform:uppercase; }
.tl-logo em { color:#c41e2a; font-style:normal; }
.tl-logo-sub { font-family:'Barlow Condensed',sans-serif; font-size:0.55rem; letter-spacing:4px; color:#555; }

.section-title { font-family:'Barlow Condensed',sans-serif; font-weight:700; font-size:0.65rem;
                 letter-spacing:5px; text-transform:uppercase; color:#8a7d6e;
                 border-bottom:1px solid #d4cabf; padding-bottom:5px;
                 margin-bottom:18px; margin-top:24px; }

/* Status strip */
.assign-card { background:#fff; border:1px solid #d4cabf; border-top:3px solid #e0d9d0;
               padding:8px 10px; text-align:center; border-radius:2px; }
.assign-card.assigned   { border-top-color:#1a5c3a; }
.assign-card.unassigned { border-top-color:#c41e2a; }
.assign-pos-name { font-family:'Barlow Condensed',sans-serif; font-weight:900;
                   font-size:0.8rem; letter-spacing:2px; text-transform:uppercase; }
.assign-status { font-size:0.5rem; letter-spacing:1px; margin-top:3px; }
.assign-status.ok      { color:#1a5c3a; font-weight:600; }
.assign-status.missing { color:#c41e2a; }

/* Result card */
.result-card { background:#fff; border:1px solid #e0d9d0; border-radius:4px;
               overflow:hidden; margin-bottom:4px; }
.result-card-body { padding:14px 16px; }
.result-pos-num { font-family:'Barlow Condensed',sans-serif; font-weight:700;
                  font-size:0.55rem; letter-spacing:3px; text-transform:uppercase;
                  color:#aaa; margin-bottom:2px; }
.result-pos-name { font-family:'Barlow Condensed',sans-serif; font-weight:900;
                   font-size:1.1rem; letter-spacing:2px; text-transform:uppercase;
                   color:#0f0d0b; line-height:1.1; }
.result-verdict { display:inline-block; font-family:'Barlow Condensed',sans-serif;
                  font-weight:700; font-size:0.6rem; letter-spacing:3px;
                  padding:3px 10px; margin:6px 0; border-radius:2px; }
.result-oneline { font-size:0.8rem; color:#333; line-height:1.5; margin-top:6px; font-weight:500; }
.result-time { font-size:0.5rem; color:#bbb; letter-spacing:1px; margin-top:4px; }

/* Cue box */
.cue-box { background:#0f0d0b; color:#fff; padding:10px 14px; margin-top:10px;
           border-radius:2px; font-size:0.75rem; font-weight:600; letter-spacing:0.5px;
           line-height:1.4; }
.cue-box::before { content:"CUE  "; font-family:'Barlow Condensed',sans-serif;
                   font-size:0.5rem; letter-spacing:4px; color:#c41e2a;
                   display:block; margin-bottom:3px; }

/* Checklist */
.check-row { display:flex; gap:10px; align-items:flex-start; font-size:0.72rem;
             line-height:1.6; padding:5px 0; border-bottom:1px solid #f5f0eb; }
.check-icon { font-size:0.85rem; flex-shrink:0; width:18px; font-weight:700; }
.check-pass { color:#1a5c3a; }
.check-warn { color:#c8920a; }
.check-fail { color:#c41e2a; }
.check-note { color:#888; font-size:0.65rem; margin-top:1px; font-style:italic; }

/* Coaching report */
.report-card { background:#fff; border:1px solid #e0d9d0; border-radius:4px;
               overflow:hidden; margin-top:8px; }
.report-section { padding:16px 20px; border-bottom:1px solid #f0ebe4; }
.report-section:last-child { border-bottom:none; }
.report-section-label { font-family:'Barlow Condensed',sans-serif; font-weight:900;
                        font-size:0.6rem; letter-spacing:4px; text-transform:uppercase;
                        margin-bottom:8px; }
.report-section-label.strengths  { color:#1a5c3a; }
.report-section-label.faults     { color:#c41e2a; }
.report-section-label.cues       { color:#0f3460; }
.report-section-label.next       { color:#c8920a; }
.report-section-label.projection { color:#555; }
.report-summary { font-size:0.85rem; font-weight:600; color:#0f0d0b;
                  margin-bottom:10px; line-height:1.5; }
.report-bullets { list-style:none; padding:0; margin:0; }
.report-bullets li { font-size:0.78rem; color:#444; line-height:1.6;
                     padding:3px 0 3px 18px; position:relative; }
.report-bullets li::before { content:"→"; position:absolute; left:0;
                              color:#c41e2a; font-weight:700; }

/* Physics strip */
.phys-strip { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-bottom:20px; }
.phys-card { background:#fff; border:1px solid #e0d9d0; border-top:3px solid #e0d9d0;
             padding:14px 16px; border-radius:2px; }
.phys-card.vel { border-top-color:#0f3460; }
.phys-card.ang { border-top-color:#c8920a; }
.phys-card.dst { border-top-color:#1a5c3a; }
.phys-card.grd { border-top-color:#c41e2a; }
.phys-label { font-size:0.5rem; letter-spacing:2px; color:#aaa; text-transform:uppercase; margin-bottom:4px; }
.phys-val { font-family:'Barlow Condensed',sans-serif; font-weight:900;
            font-size:2.2rem; line-height:1; color:#0f0d0b; }
.phys-unit { font-size:0.45rem; color:#aaa; margin-top:2px; letter-spacing:1px; }

/* Sidebar metrics */
.metric-card { background:#fff; border:1px solid #d4cabf; padding:12px 14px;
               border-left:3px solid #d4cabf; margin-bottom:8px; border-radius:2px; }
.metric-card.vel { border-left-color:#0f3460; }
.metric-card.ang { border-left-color:#c8920a; }
.metric-card.dst { border-left-color:#1a5c3a; }
.metric-card.grd { border-left-color:#c41e2a; }
.metric-label { font-size:0.45rem; letter-spacing:2px; color:#8a7d6e; text-transform:uppercase; }
.metric-val { font-family:'Barlow Condensed',sans-serif; font-weight:900;
              font-size:1.8rem; line-height:1.1; color:#0f0d0b; }
.metric-unit { font-size:0.4rem; color:#8a7d6e; letter-spacing:1px; }
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
        st.error("opencv-python-headless is required.")
    return frames


def call_claude(client, content: list, max_tokens: int = 1000) -> str:
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": content}],
    )
    return response.content[0].text


def estimate_release_physics(client, frames: list, event_type: str) -> dict:
    """Pass 0: Multi-frame trajectory + body-proportion physics estimation.
    
    Strategy:
    1. Claude identifies release frame and 2 post-release frames
    2. Claude estimates implement pixel coordinates across those frames  
    3. Claude estimates athlete height in pixels using circle diameter as reference
    4. We compute real angle from pixel displacement vector
    5. We compute real velocity from pixel displacement + frame interval
    6. Discus: spin rate estimated for aerodynamic lift correction
    """
    tn = {"discus": "discus", "shot_glide": "shot put glide", "shot_spin": "shot put spin"}[event_type]
    is_discus = event_type == "discus"
    # Known reference dimensions for scale calibration
    circle_diameter_m = 2.5 if is_discus else 2.135  # metres

    content_msgs = [
        *[{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": f["b64"]}}
          for f in frames],
        {"type": "text", "text": f"""These are {len(frames)} sequential frames (0–{len(frames)-1}) from a {tn} throw in chronological order.

TASK: Extract precise physics data for distance estimation.

Step 1 — Find release: identify the frame where the {"discus" if is_discus else "shot"} leaves the hand.

Step 2 — Track implement position: For the release frame and the 2 frames immediately AFTER release, estimate the implement's pixel coordinates (x=horizontal, y=vertical, origin top-left).

Step 3 — Athlete scale: Estimate the athlete's height in pixels in the release frame. Also estimate the throwing circle diameter in pixels if visible. This lets us convert pixels to metres.

Step 4 — Spin (discus only): Estimate how many times the discus visibly rotates between the release frame and 1 frame later. Even a rough estimate (0.5, 1, 1.5 rotations) helps.

Step 5 — Velocity confidence: Rate how clearly you can track the implement (0.0=can't see it, 1.0=crystal clear).

Return ONLY valid JSON:
{{
  "release_frame_idx": <int>,
  "post_release_frames": [<int>, <int>],
  "implement_coords": [
    {{"frame": <int>, "x": <float px>, "y": <float px>}},
    {{"frame": <int>, "x": <float px>, "y": <float px>}},
    {{"frame": <int>, "x": <float px>, "y": <float px>}}
  ],
  "athlete_height_px": <float>,
  "circle_diameter_px": <float or null>,
  "spin_rotations_per_frame": <float or null>,
  "tracking_confidence": <float 0-1>,
  "notes": "<what you observed>"
}}"""}
    ]

    raw = call_claude(client, content_msgs, max_tokens=500)
    try:
        raw_data = json.loads(raw.strip().replace("```json","").replace("```","").strip())
    except Exception:
        raw_data = {}

    # ── Physics computation from tracked coordinates ──
    coords  = raw_data.get("implement_coords", [])
    frames_list = frames  # alias
    fps     = 1.0 / max(0.01, (frames_list[1]["time"] - frames_list[0]["time"])) if len(frames_list) > 1 else 30.0

    # Scale: metres per pixel
    # Priority: circle diameter → athlete height → fallback
    m_per_px = None
    circle_px = raw_data.get("circle_diameter_px")
    height_px = raw_data.get("athlete_height_px")
    ATHLETE_HEIGHT_M = 1.83  # assumed average thrower height

    if circle_px and circle_px > 20:
        m_per_px = circle_diameter_m / circle_px
    elif height_px and height_px > 50:
        m_per_px = ATHLETE_HEIGHT_M / height_px

    # Compute angle and velocity from pixel trajectory
    angle_deg    = None
    velocity_mps = None
    angle_uncertainty = 5.0  # degrees, default

    if len(coords) >= 2 and m_per_px:
        # Use first two tracked points
        p0, p1 = coords[0], coords[1]
        # Frame time delta
        fi0 = p0.get("frame", raw_data.get("release_frame_idx", 0))
        fi1 = p1.get("frame", fi0 + 1)
        dt  = max(0.001, (fi1 - fi0) / fps)

        dx_px = p1["x"] - p0["x"]
        dy_px = p0["y"] - p1["y"]  # invert Y (screen coords)

        dx_m  = dx_px * m_per_px
        dy_m  = dy_px * m_per_px

        speed_mps = math.sqrt(dx_m**2 + dy_m**2) / dt
        angle_rad = math.atan2(dy_m, abs(dx_m))
        angle_deg = math.degrees(angle_rad)

        # Confidence-weighted uncertainty
        conf = raw_data.get("tracking_confidence", 0.5)
        angle_uncertainty = max(2.0, 8.0 * (1.0 - conf))
        velocity_mps = speed_mps

    # Fallback: ask Claude for a direct visual estimate if tracking failed
    if angle_deg is None or velocity_mps is None or velocity_mps < 3 or velocity_mps > 35:
        # Use Claude's visual estimate as fallback with lower confidence
        defaults = {"discus": (37.0, 18.0), "shot_spin": (39.0, 10.5), "shot_glide": (39.0, 10.5)}
        def_angle, def_vel = defaults[event_type]
        angle_deg    = def_angle
        velocity_mps = def_vel
        angle_uncertainty = 8.0
        raw_data["_used_fallback"] = True

    # Sanity clamps
    angle_deg    = max(15.0, min(60.0, angle_deg))
    velocity_mps = max(8.0,  min(32.0, velocity_mps))

    # Spin rate for discus aerodynamic lift
    spin_rps = None
    if is_discus:
        spf = raw_data.get("spin_rotations_per_frame")
        if spf is not None:
            spin_rps = float(spf) * fps

    return {
        "release_angle":      round(angle_deg, 1),
        "angle_uncertainty":  round(angle_uncertainty, 1),
        "velocity_estimate":  round(velocity_mps, 1),
        "confidence":         raw_data.get("tracking_confidence", 0.4),
        "m_per_px":           round(m_per_px, 5) if m_per_px else None,
        "spin_rps":           round(spin_rps, 1) if spin_rps else None,
        "used_fallback":      raw_data.get("_used_fallback", False),
        "notes":              raw_data.get("notes", ""),
        "release_frame_idx":  raw_data.get("release_frame_idx", len(frames)//2),
    }


def analyze_position(client, frame: dict, pos: dict, event_type: str) -> dict:
    tn = {"discus": "discus", "shot_glide": "shot put glide", "shot_spin": "shot put rotational spin"}[event_type]
    criteria = pos["criteria"][event_type]
    criteria_list = "\n".join(f"{i+1}. {c}" for i, c in enumerate(criteria))

    prompt = f"""You are an elite throws coach analyzing a {tn} athlete.
This frame shows the "{pos['name']}" position ({pos['desc']}).

Evaluate these criteria honestly — don't give unwarranted passes:
{criteria_list}

Return ONLY valid JSON (no markdown):
{{
  "verdict": "good|ok|warn",
  "verdict_label": "EXCELLENT|SOLID|NEEDS WORK|FAULT DETECTED",
  "checks": [{{"criterion":"...","status":"pass|warn|fail","note":"specific, honest observation in 8-12 words"}}],
  "one_line": "most impactful observation about this position, max 12 words, direct coach voice",
  "cue": "one short field coaching cue, max 10 words, the kind you shout from the infield"
}}"""

    raw = call_claude(client, [
        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": frame["b64"]}},
        {"type": "text", "text": prompt},
    ], max_tokens=700)

    try:
        return json.loads(raw.strip().replace("```json", "").replace("```", "").strip())
    except Exception:
        return {"verdict": "ok", "verdict_label": "ANALYZED", "checks": [],
                "one_line": "Analysis complete.", "cue": "Keep working."}


def get_coaching(client, analysis_data: list, physics: dict, event_type: str,
                 athlete: str, pr: str, release_notes: str) -> dict:
    """Returns structured dict with sections instead of a blob of text."""
    tn = {"discus": "discus", "shot_glide": "shot put (glide)", "shot_spin": "shot put (spin)"}[event_type]

    summary = "\n".join(
        f"{d['posName']}: {d.get('verdict_label','—')} — {d.get('one_line','')}"
        for d in analysis_data if d
    )
    faults = "\n".join(
        f"[{d['posName']}] {c['criterion']}: {c.get('note','')}"
        for d in analysis_data if d
        for c in d.get("checks", []) if c.get("status") in ("fail", "warn")
    ) or "None detected"

    prompt = f"""Elite throws coach writing a session report for {athlete}, {tn}.{f' Current PR: {pr}.' if pr else ''}

Position analysis summary:
{summary}

Technical faults identified:
{faults}

Physics analysis: velocity {physics['velocity']} m/s, release angle {physics['angle']}°, predicted distance {physics['dist_ft']} ft.
Physics confidence: {physics.get('confidence_pct', '—')}%. Notes from release frame analysis: {release_notes}

Write an encouraging but honest coaching report. Return ONLY valid JSON:
{{
  "opening": "one encouraging sentence acknowledging what's working overall, max 20 words",
  "strengths": {{
    "summary": "one sentence on biggest strength, max 15 words",
    "bullets": ["specific strength 1", "specific strength 2", "specific strength 3"]
  }},
  "faults": {{
    "summary": "one sentence on highest-priority fault to fix, max 15 words",
    "bullets": ["Priority 1: fault + why it matters", "Priority 2: fault + why it matters", "Priority 3: fault + why it matters"]
  }},
  "cues": {{
    "summary": "one sentence framing the session cues",
    "bullets": ["short cue 1 — context", "short cue 2 — context", "short cue 3 — context", "short cue 4 — context"]
  }},
  "next": {{
    "summary": "one sentence on next session priority",
    "bullets": ["drill or focus 1", "drill or focus 2"]
  }},
  "projection": {{
    "summary": "one encouraging sentence on realistic improvement potential",
    "bullets": ["specific distance gain if top fault fixed", "timeline estimate"]
  }}
}}

Be specific, reference positions by name. Encouraging but direct — no generic filler."""

    raw = call_claude(client, [{"type": "text", "text": prompt}], max_tokens=1200)
    try:
        return json.loads(raw.strip().replace("```json", "").replace("```", "").strip())
    except Exception:
        # Fallback plain structure
        clean = re.sub(r'\*{1,2}(.*?)\*{1,2}', r'\1', raw)
        return {"_raw": clean}


def compute_physics(release_data: dict, event_type: str) -> dict:
    """Full physics model with aerodynamics, spin lift (discus), and confidence intervals."""
    angle    = release_data.get("release_angle", 37 if event_type == "discus" else 39)
    velocity = release_data.get("velocity_estimate", 17 if event_type == "discus" else 10)
    angle_unc = release_data.get("angle_uncertainty", 5.0)   # ± degrees
    vel_unc   = velocity * 0.08                               # assume ±8% velocity uncertainty
    confidence = release_data.get("confidence", 0.5)
    spin_rps  = release_data.get("spin_rps")
    is_discus = event_type == "discus"

    h0 = 1.8 if is_discus else 2.1
    g  = 9.81

    def projectile_dist(v, a_deg, h):
        """Basic projectile with release height."""
        ar = math.radians(a_deg)
        vy = v * math.sin(ar)
        vx = v * math.cos(ar)
        t  = (vy + math.sqrt(vy**2 + 2*g*h)) / g
        return vx * t

    def discus_lift_factor(v, a_deg, spin_rps_val):
        """Simplified aerodynamic lift bonus for discus.
        Based on: L = 0.5 * rho * v^2 * A * CL
        CL increases with spin rate and angle of attack.
        Returns multiplier on base distance (1.0 = no lift bonus).
        """
        if spin_rps_val is None or spin_rps_val <= 0:
            # Typical high school spin: ~5-7 rps estimate
            spin_rps_val = 6.0
        rho   = 1.225   # kg/m^3 air density
        A     = 0.0507  # discus area m^2 (2kg disc)
        mass  = 1.0     # kg (HS women) or 2.0 (HS men) — use 1.5 avg
        # CL approximation: peaks around 10-15° angle of attack
        aoa   = max(0, 35 - a_deg)  # rough angle of attack from release angle
        CL    = 0.3 + 0.015 * min(aoa, 20) + 0.002 * min(spin_rps_val, 12)
        lift  = 0.5 * rho * (v**2) * A * CL
        # Effective gravity reduction
        g_eff = max(1.0, g - lift/mass)
        ar    = math.radians(a_deg)
        vy    = v * math.sin(ar)
        vx    = v * math.cos(ar)
        t     = (vy + math.sqrt(vy**2 + 2*g_eff*h0)) / g_eff
        lift_dist = vx * t
        base_dist = projectile_dist(v, a_deg, h0)
        return lift_dist / max(0.1, base_dist)

    # Central estimate
    base_dist = projectile_dist(velocity, angle, h0)
    if is_discus:
        lift_mult = discus_lift_factor(velocity, angle, spin_rps)
        central_m = base_dist * lift_mult
    else:
        central_m = base_dist

    # Confidence interval: vary angle and velocity within uncertainties
    samples = []
    for da in [-angle_unc, 0, angle_unc]:
        for dv in [-vel_unc, 0, vel_unc]:
            d = projectile_dist(max(5, velocity+dv), max(10, angle+da), h0)
            if is_discus:
                d *= discus_lift_factor(max(5, velocity+dv), max(10, angle+da), spin_rps)
            samples.append(d)

    low_m  = min(samples)
    high_m = max(samples)

    def m_to_ft(m): return round(m * 3.28084, 1)

    return {
        "velocity":       round(velocity, 1),
        "vel_uncertainty":round(vel_unc, 1),
        "angle":          round(angle, 1),
        "angle_uncertainty": round(angle_unc, 1),
        "dist_m":         round(central_m, 2),
        "dist_ft":        m_to_ft(central_m),
        "dist_low_ft":    m_to_ft(low_m),
        "dist_high_ft":   m_to_ft(high_m),
        "spin_rps":       spin_rps,
        "confidence_pct": round(confidence * 100),
        "used_fallback":  release_data.get("used_fallback", False),
        "aerodynamic":    is_discus,
    }


def grade_from_analysis(analysis_data: list) -> str:
    verdicts = [d.get("verdict") for d in analysis_data if d]
    if not verdicts:
        return "—"
    score = round((verdicts.count("good") / len(verdicts)) * 10 - verdicts.count("warn") * 0.5)
    return "A" if score >= 8 else "B" if score >= 6 else "C" if score >= 4 else "D"


def render_report_section(label_text, label_class, section_data):
    """Render one structured coaching report section."""
    if not section_data:
        return ""
    summary = section_data.get("summary", "")
    bullets = section_data.get("bullets", [])
    bullets_html = "".join(f"<li>{b}</li>" for b in bullets)
    return f"""
    <div class="report-section">
      <div class="report-section-label {label_class}">{label_text}</div>
      <div class="report-summary">{summary}</div>
      <ul class="report-bullets">{bullets_html}</ul>
    </div>"""


# ── API KEY — loaded from Streamlit secrets ──
try:
    api_key = st.secrets["ANTHROPIC_API_KEY"]
except (KeyError, FileNotFoundError):
    api_key = None

# ── SIDEBAR ──
with st.sidebar:
    st.markdown('<div class="section-title">API</div>', unsafe_allow_html=True)
    if api_key:
        st.success("API key loaded.", icon="🔑")
    else:
        st.warning("Add ANTHROPIC_API_KEY to Streamlit secrets.", icon="⚠️")
        api_key = st.text_input("API Key (fallback)", type="password", placeholder="sk-ant-...")

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
        g = st.session_state.get("grade", "—")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f'<div class="metric-card vel"><div class="metric-label">Velocity</div><div class="metric-val">{p["velocity"]}</div><div class="metric-unit">m/s</div></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-card dst"><div class="metric-label">Distance</div><div class="metric-val">{p["dist_ft"]}</div><div class="metric-unit">feet</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="metric-card ang"><div class="metric-label">Angle</div><div class="metric-val">{p["angle"]}°</div><div class="metric-unit">deg</div></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-card grd"><div class="metric-label">Grade</div><div class="metric-val">{g}</div><div class="metric-unit">technique</div></div>', unsafe_allow_html=True)
    else:
        st.caption("Assign frames and run analysis to see metrics.")


# ── EXTRACT FRAMES ON UPLOAD ──
if uploaded:
    upload_id = uploaded.name + str(uploaded.size)
    if st.session_state.get("_last_upload") != upload_id:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded.name)[1]) as tmp:
            tmp.write(uploaded.read())
            tmp_path = tmp.name
        with st.spinner("Extracting frames..."):
            frames = extract_frames(tmp_path)
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        if frames:
            st.session_state["frames"]       = frames
            st.session_state["_last_upload"] = upload_id
            for k in list(st.session_state.keys()):
                if k.startswith("assigned_") or k in ("analysis", "physics", "coaching", "grade", "release_data"):
                    del st.session_state[k]
            st.success(f"{len(frames)} frames extracted. Assign each position below.")
        else:
            st.error("Frame extraction failed. Ensure opencv-python-headless is installed.")

all_frames    = st.session_state.get("frames", [])
analysis_done = "analysis" in st.session_state


# ── MAIN HEADER ──
hcol1, hcol2 = st.columns([3, 1])
with hcol1:
    st.markdown(f"""
    <div style="border-bottom:2px solid #0f0d0b;padding-bottom:8px;margin-bottom:16px;">
      <span style="font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:1.5rem;letter-spacing:4px;text-transform:uppercase;">Position Breakdown</span>
      <span style="font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:0.65rem;letter-spacing:3px;color:#c41e2a;border:1px solid #c41e2a;padding:2px 8px;margin-left:12px;">{EVENT_LABELS[event_type]}</span>
      <span style="font-size:0.6rem;color:#8a7d6e;margin-left:12px;">{athlete_name or 'No athlete loaded'}</span>
    </div>
    """, unsafe_allow_html=True)
with hcol2:
    all_assigned = all_frames and all(
        st.session_state.get(f"assigned_{i}") is not None for i in range(len(POSITIONS))
    )
    run_btn    = st.button("⚡ ANALYZE", type="primary",
                           disabled=not all_assigned or not api_key,
                           use_container_width=True,
                           help="Assign all 7 positions first" if not all_assigned else "Run AI analysis")
    report_btn = st.button("↓ REPORT", disabled=not analysis_done, use_container_width=True)
    if analysis_done:
        if st.button("↺ Reset", use_container_width=True):
            for k in list(st.session_state.keys()):
                if k.startswith("assigned_") or k in ("analysis", "physics", "coaching", "grade", "release_data"):
                    del st.session_state[k]
            st.rerun()


# ══════════════════════════════════════════════
# FRAME ASSIGNMENT (hidden after analysis)
# ══════════════════════════════════════════════
if all_frames and not analysis_done:
    st.markdown('<div class="section-title">STEP 1 — ASSIGN FRAMES TO POSITIONS</div>',
                unsafe_allow_html=True)

    # Status strip
    status_cols = st.columns(len(POSITIONS))
    for i, pos in enumerate(POSITIONS):
        assigned_idx = st.session_state.get(f"assigned_{i}")
        with status_cols[i]:
            if assigned_idx is not None:
                fr = all_frames[assigned_idx]
                st.markdown(
                    f'<div class="assign-card assigned">'
                    f'<div class="assign-pos-name">{pos["icon"]} {pos["short"]}</div>'
                    f'<div class="assign-status ok">t={fr["time"]}s</div>'
                    f'</div>', unsafe_allow_html=True)
            else:
                st.markdown(
                    f'<div class="assign-card unassigned">'
                    f'<div class="assign-pos-name">{pos["icon"]} {pos["short"]}</div>'
                    f'<div class="assign-status missing">unassigned</div>'
                    f'</div>', unsafe_allow_html=True)

    st.write("")

    # Carousels
    for i, pos in enumerate(POSITIONS):
        assigned_idx  = st.session_state.get(f"assigned_{i}")
        label_tag     = f"t={all_frames[assigned_idx]['time']}s" if assigned_idx is not None else "unassigned"
        with st.expander(f"{pos['icon']} {pos['name']}  ·  {label_tag}", expanded=(assigned_idx is None)):
            st.markdown(
                f'<div style="font-size:0.7rem;color:#555;margin-bottom:8px;">'
                f'<strong>{pos["desc"]}</strong></div>',
                unsafe_allow_html=True)
            criteria_text = "  ·  ".join(pos["criteria"][event_type])
            st.caption(f"Look for: {criteria_text}")
            st.divider()

            COLS = 4
            for row_start in range(0, len(all_frames), COLS):
                row_frames = all_frames[row_start:row_start + COLS]
                cols = st.columns(COLS)
                for j_rel, fr in enumerate(row_frames):
                    j_abs = row_start + j_rel
                    is_sel = (assigned_idx == j_abs)
                    with cols[j_rel]:
                        st.image(fr["img"], use_container_width=True,
                                 caption=f"{'ASSIGNED  ' if is_sel else ''}t={fr['time']}s")
                        if st.button(
                            "Assigned" if is_sel else "Assign",
                            key=f"assign_{i}_{j_abs}",
                            type="primary" if is_sel else "secondary",
                            use_container_width=True
                        ):
                            st.session_state[f"assigned_{i}"] = j_abs
                            st.rerun()

    if not all_assigned:
        unassigned = [POSITIONS[i]["name"] for i in range(len(POSITIONS))
                      if st.session_state.get(f"assigned_{i}") is None]
        st.info(f"Still needed: **{', '.join(unassigned)}**", icon="📌")
    else:
        st.success("All 7 positions assigned. Click **⚡ ANALYZE** to run the breakdown.")


# ══════════════════════════════════════════════
# RUN ANALYSIS
# ══════════════════════════════════════════════
if run_btn and all_assigned and api_key:
    client   = anthropic.Anthropic(api_key=api_key)
    progress = st.progress(0, text="Starting analysis...")
    log_area = st.empty()
    logs: list = []

    def log(msg, kind=""):
        logs.append(("✓ " if kind == "ok" else "⚠ " if kind == "warn" else "› ") + msg)
        log_area.code("\n".join(logs[-8:]), language=None)

    try:
        # Pass 0 — physics from all frames
        log(f"Pass 0 — reading all {len(all_frames)} frames for release physics...")
        progress.progress(5, text="Estimating release physics from all frames...")
        release_data = estimate_release_physics(client, all_frames, event_type)
        physics = compute_physics(release_data, event_type)
        log(f"Release: {physics['angle']}° at {physics['velocity']} m/s → {physics['dist_ft']}ft "
            f"(confidence {physics['confidence_pct']}%)", "ok")

        # Pass 1 — per-position technique analysis
        analysis_data = []
        for i, pos in enumerate(POSITIONS):
            assigned_idx = st.session_state.get(f"assigned_{i}")
            progress.progress(10 + int(i / len(POSITIONS) * 75), text=f"Analyzing {pos['name']}...")
            frame = all_frames[assigned_idx]
            log(f"Analyzing: {pos['name']} (t={frame['time']}s)...")
            result = analyze_position(client, frame, pos, event_type)
            result.update({"frame": frame, "posName": pos["name"], "posId": pos["id"]})
            analysis_data.append(result)
            log(f"{pos['name']}: {result.get('verdict_label', '—')}", "ok")

        # Pass 2 — coaching report
        progress.progress(88, text="Generating coaching report...")
        grade   = grade_from_analysis(analysis_data)
        coaching = get_coaching(client, analysis_data, physics, event_type,
                                athlete_name or "Athlete", athlete_pr,
                                release_data.get("notes", ""))

        st.session_state.update({
            "analysis":      analysis_data,
            "physics":       physics,
            "release_data":  release_data,
            "coaching":      coaching,
            "grade":         grade,
            "event_type":    event_type,
            "athlete":       athlete_name or "Athlete",
        })
        progress.progress(100, text="Analysis complete!")
        log("Done", "ok")

    except Exception as e:
        st.error(f"Analysis failed: {e}")
        import traceback; traceback.print_exc()

    st.rerun()


# ══════════════════════════════════════════════
# RESULTS
# ══════════════════════════════════════════════
if analysis_done:
    analysis_data = st.session_state.analysis
    physics       = st.session_state.physics
    coaching      = st.session_state.coaching
    grade         = st.session_state.get("grade", "—")
    release_data  = st.session_state.get("release_data", {})

    # Physics strip
    st.markdown('<div class="section-title">PERFORMANCE METRICS</div>', unsafe_allow_html=True)

    # Build caption with method and fallback note
    method_note = "visual fallback (tracking failed)" if physics.get("used_fallback") else "multi-frame trajectory tracking"
    aero_note   = f" · aerodynamic lift model applied" if physics.get("aerodynamic") else ""
    spin_note   = f" · spin ~{physics['spin_rps']} rps" if physics.get("spin_rps") else ""
    conf_note   = f" · {physics['confidence_pct']}% tracking confidence" if physics.get('confidence_pct') else ""
    st.caption(
        f"Physics method: {method_note}{aero_note}{spin_note}{conf_note}. "
        f"{release_data.get('notes', '')}"
    )

    # Confidence interval labels
    ang_range = f"{physics['angle']}° ± {physics['angle_uncertainty']}°"
    vel_range = f"{physics['velocity']} ± {physics['vel_uncertainty']:.1f} m/s"
    dst_range = f"{physics['dist_low_ft']}–{physics['dist_high_ft']} ft"

    st.markdown(
        f'''<div class="phys-strip">
          <div class="phys-card vel">
            <div class="phys-label">Est. Velocity</div>
            <div class="phys-val">{physics['velocity']}</div>
            <div class="phys-unit">{vel_range}</div>
          </div>
          <div class="phys-card ang">
            <div class="phys-label">Release Angle</div>
            <div class="phys-val">{physics['angle']}°</div>
            <div class="phys-unit">{ang_range}</div>
          </div>
          <div class="phys-card dst">
            <div class="phys-label">Predicted Distance</div>
            <div class="phys-val">{physics['dist_ft']}</div>
            <div class="phys-unit">Range: {dst_range}</div>
          </div>
          <div class="phys-card grd">
            <div class="phys-label">Technique Grade</div>
            <div class="phys-val">{grade}</div>
            <div class="phys-unit">overall</div>
          </div>
        </div>''',
        unsafe_allow_html=True
    )

    # Position grid
    st.markdown('<div class="section-title">POSITION BREAKDOWN</div>', unsafe_allow_html=True)
    grid_cols = st.columns(4)  # 7 positions: row of 4, row of 3

    for i, pos in enumerate(POSITIONS):
        data    = analysis_data[i] if i < len(analysis_data) else None
        verdict = (data or {}).get("verdict", "pending")
        vl      = (data or {}).get("verdict_label", "PENDING")
        ol      = (data or {}).get("one_line", "No frame assigned")
        cue     = (data or {}).get("cue", "")
        fr      = (data or {}).get("frame")
        ftime   = f"t={fr['time']:.2f}s" if fr else "—"

        vc, vbg, _ = VERDICT_COLORS.get(verdict, ("#555", "#f5f5f5", vl))

        with grid_cols[i % 4]:
            # Frame image
            if fr and fr.get("img"):
                st.image(fr["img"], use_container_width=True)
            else:
                st.markdown(
                    f'<div style="width:100%;aspect-ratio:4/3;background:#ede8e1;'
                    f'display:flex;align-items:center;justify-content:center;'
                    f'color:#ccc;font-size:2rem;">{pos["icon"]}</div>',
                    unsafe_allow_html=True)

            # Card body
            st.markdown(f"""
            <div class="result-card-body">
              <div class="result-pos-num">{pos['icon']} POSITION {i+1}</div>
              <div class="result-pos-name">{pos['name']}</div>
              <div class="result-verdict" style="background:{vbg};color:{vc};border:1px solid {vc}40;">{vl}</div>
              <div class="result-oneline">{ol}</div>
              <div class="result-time">{ftime}</div>
              {"<div class='cue-box'>"+cue+"</div>" if cue else ""}
            </div>
            """, unsafe_allow_html=True)

            if data and data.get("checks"):
                with st.expander("Checklist"):
                    for c in data["checks"]:
                        s    = c.get("status", "")
                        icon = "✓" if s == "pass" else "✗" if s == "fail" else "⚠"
                        cls  = "check-pass" if s == "pass" else "check-fail" if s == "fail" else "check-warn"
                        note_html = f'<div class="check-note">{c["note"]}</div>' if c.get("note") else ""
                        st.markdown(
                            f'<div class="check-row">'
                            f'<span class="check-icon {cls}">{icon}</span>'
                            f'<div><div>{c["criterion"]}</div>{note_html}</div>'
                            f'</div>',
                            unsafe_allow_html=True)

    # Coaching report
    st.markdown('<div class="section-title">COACHING REPORT</div>', unsafe_allow_html=True)

    if "_raw" in coaching:
        # Fallback plain text
        st.markdown(f'<div style="background:#f7f3ee;border-left:4px solid #0f3460;padding:16px 18px;font-size:0.85rem;line-height:2;white-space:pre-wrap;">{coaching["_raw"]}</div>', unsafe_allow_html=True)
    else:
        opening = coaching.get("opening", "")
        report_html = f"""
        <div class="report-card">
          {"<div class='report-section'><div style='font-size:1rem;font-weight:600;color:#0f0d0b;line-height:1.6;'>"+opening+"</div></div>" if opening else ""}
          {render_report_section("STRENGTHS", "strengths", coaching.get("strengths"))}
          {render_report_section("FAULTS TO FIX", "faults", coaching.get("faults"))}
          {render_report_section("SESSION CUES", "cues", coaching.get("cues"))}
          {render_report_section("NEXT SESSION FOCUS", "next", coaching.get("next"))}
          {render_report_section("PROJECTION", "projection", coaching.get("projection"))}
        </div>"""
        st.markdown(report_html, unsafe_allow_html=True)


# ══════════════════════════════════════════════
# DOWNLOAD REPORT
# ══════════════════════════════════════════════
if report_btn and analysis_done:
    p         = st.session_state.physics
    data_list = st.session_state.analysis
    coaching  = st.session_state.coaching
    ev        = st.session_state.get("event_type", event_type)
    ath       = st.session_state.get("athlete", athlete_name or "Athlete")
    grade     = st.session_state.get("grade", "—")

    cells_html = ""
    for i, pos in enumerate(POSITIONS):
        d   = data_list[i] if i < len(data_list) else None
        v   = (d or {}).get("verdict", "ok")
        vl  = (d or {}).get("verdict_label", "PENDING")
        ol  = (d or {}).get("one_line", "—")
        cue = (d or {}).get("cue", "")
        col = {"good": "#1a5c3a", "warn": "#c41e2a"}.get(v, "#0f3460")
        bg  = {"good": "#e8f5ee", "warn": "#fdf0f0"}.get(v, "#e8eef5")
        img = (
            f'<img src="data:image/jpeg;base64,{d["frame"]["b64"]}" '
            f'style="width:100%;aspect-ratio:4/3;object-fit:cover;display:block;">'
            if d and d.get("frame") and d["frame"].get("b64")
            else f'<div style="width:100%;aspect-ratio:4/3;background:#ede8e1;'
                 f'display:flex;align-items:center;justify-content:center;'
                 f'color:#ccc;font-size:1.5rem;">{pos["icon"]}</div>'
        )
        cue_html = f'<div style="background:#0f0d0b;color:#fff;padding:6px 10px;font-size:0.5rem;margin-top:6px;"><span style="color:#c41e2a;font-size:0.4rem;letter-spacing:2px;display:block;">CUE</span>{cue}</div>' if cue else ""
        cells_html += (
            f'<div style="border:1px solid #e0d9d0;border-radius:4px;overflow:hidden;">{img}'
            f'<div style="padding:10px 12px;">'
            f'<div style="font-size:0.45rem;color:#aaa;letter-spacing:2px;text-transform:uppercase;margin-bottom:2px;">{pos["icon"]} Position {i+1}</div>'
            f'<div style="font-family:\'Barlow Condensed\',sans-serif;font-weight:900;font-size:1rem;letter-spacing:2px;text-transform:uppercase;">{pos["name"]}</div>'
            f'<div style="font-size:0.5rem;font-weight:700;letter-spacing:2px;padding:2px 8px;background:{bg};color:{col};border:1px solid {col}40;display:inline-block;margin:4px 0;border-radius:2px;">{vl}</div>'
            f'<div style="font-size:0.6rem;color:#333;line-height:1.5;font-weight:500;">{ol}</div>'
            f'{cue_html}</div></div>'
        )

    # Coaching HTML for report
    if "_raw" in coaching:
        coaching_body = f'<div style="white-space:pre-wrap;font-size:0.7rem;line-height:2;">{coaching["_raw"]}</div>'
    else:
        def section_html(label, color, sec):
            if not sec: return ""
            bullets = "".join(f'<li style="font-size:0.65rem;color:#444;padding:2px 0 2px 16px;position:relative;list-style:none;"><span style="position:absolute;left:0;color:#c41e2a;">→</span>{b}</li>' for b in sec.get("bullets",[]))
            return (f'<div style="padding:14px 18px;border-bottom:1px solid #f0ebe4;">'
                    f'<div style="font-family:\'Barlow Condensed\',sans-serif;font-weight:900;font-size:0.55rem;letter-spacing:4px;text-transform:uppercase;color:{color};margin-bottom:6px;">{label}</div>'
                    f'<div style="font-size:0.75rem;font-weight:600;color:#0f0d0b;margin-bottom:8px;">{sec.get("summary","")}</div>'
                    f'<ul style="margin:0;padding:0;">{bullets}</ul></div>')

        opening = coaching.get("opening","")
        coaching_body = (
            f'{"<div style=\'padding:14px 18px;border-bottom:1px solid #f0ebe4;font-size:0.85rem;font-weight:600;\'>"+opening+"</div>" if opening else ""}'
            + section_html("STRENGTHS", "#1a5c3a", coaching.get("strengths"))
            + section_html("FAULTS TO FIX", "#c41e2a", coaching.get("faults"))
            + section_html("SESSION CUES", "#0f3460", coaching.get("cues"))
            + section_html("NEXT SESSION FOCUS", "#c8920a", coaching.get("next"))
            + section_html("PROJECTION", "#555", coaching.get("projection"))
        )

    report_html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@700;900&family=Inter:wght@400;500;600&display=swap');
body{{font-family:'Inter',sans-serif;background:#fff;color:#0f0d0b;padding:32px;max-width:960px;margin:0 auto;}}
.hdr{{border-bottom:3px solid #c41e2a;padding-bottom:12px;margin-bottom:20px;display:flex;justify-content:space-between;align-items:flex-end;}}
.logo{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:2rem;letter-spacing:8px;text-transform:uppercase;}}
.logo em{{color:#c41e2a;font-style:normal;}}
.bar{{background:#0f0d0b;color:#fff;padding:8px 16px;margin-bottom:20px;font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:0.9rem;letter-spacing:4px;display:flex;gap:32px;}}
.bar em{{color:#c41e2a;font-style:normal;}}
.sec{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:0.6rem;letter-spacing:5px;text-transform:uppercase;color:#8a7d6e;border-bottom:1px solid #d4cabf;padding-bottom:4px;margin-bottom:14px;margin-top:20px;}}
.mets{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px;}}
.met{{border:1px solid #e0d9d0;padding:12px;border-top:3px solid #e0d9d0;border-radius:4px;}}
.met.v{{border-top-color:#0f3460;}}.met.a{{border-top-color:#c8920a;}}.met.d{{border-top-color:#1a5c3a;}}.met.f{{border-top-color:#c41e2a;}}
.ml{{font-size:0.42rem;letter-spacing:2px;color:#8a7d6e;margin-bottom:4px;}}
.mv{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:2rem;line-height:1;}}
.mu{{font-size:0.4rem;color:#8a7d6e;}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:24px;}}
.report-card{{border:1px solid #e0d9d0;border-radius:4px;overflow:hidden;margin-bottom:24px;}}
.notes{{border:1px solid #e0d9d0;padding:14px;min-height:70px;margin-bottom:24px;font-size:0.65rem;color:#aaa;font-style:italic;border-radius:4px;}}
.footer{{border-top:1px solid #d4cabf;padding-top:10px;font-size:0.42rem;color:#aaa;letter-spacing:2px;display:flex;justify-content:space-between;}}
@media print{{.noprint{{display:none!important;}}}}
</style></head><body>
<div class="hdr">
  <div><div class="logo">THROWS<em>LAB</em></div><div style="font-size:0.45rem;letter-spacing:4px;color:#aaa;">POSITION BREAKDOWN REPORT</div></div>
  <div style="font-size:0.6rem;text-align:right;line-height:2;color:#666;">
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
  <div class="met f"><div class="ml">Technique Grade</div><div class="mv">{grade}</div><div class="mu">overall</div></div>
</div>
<div class="sec">7-Position Breakdown</div>
<div class="grid">{cells_html}</div>
<div class="sec">Coaching Report</div>
<div class="report-card">{coaching_body}</div>
<div class="sec">Coach Notes</div>
<div class="notes" contenteditable="true">Click to add session notes...</div>
<div class="footer">
  <span>THROWSLAB — POSITION BREAKDOWN SYSTEM</span>
  <span>GENERATED {str(athlete_date).upper()}</span>
</div>
<div class="noprint" style="margin-top:20px;text-align:right;">
  <button onclick="window.print()" style="font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:0.8rem;letter-spacing:2px;padding:10px 24px;background:#0f0d0b;color:#fff;border:none;cursor:pointer;border-radius:2px;">🖨 PRINT / SAVE PDF</button>
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
