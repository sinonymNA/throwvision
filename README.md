# ThrowsLab — Streamlit Edition

AI-powered throws coaching analysis. Upload a shot put or discus video, get a 6-position breakdown with coaching cues, fault detection, and a printable report — all powered by Claude Vision.

## Run Locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Enter your Anthropic API key in the sidebar when the app opens.

## Deploy Free on Streamlit Community Cloud

1. Push this folder to a GitHub repo (public or private)
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub
3. Click **New app** → select your repo → set main file to `app.py`
4. Go to **Advanced settings → Secrets** and add:

```toml
ANTHROPIC_API_KEY = "sk-ant-your-key-here"
```

5. Click **Deploy** — done. Free hosting, no credit card.

> If you add the secret, the app will use it automatically and the API key field in the sidebar becomes optional. To enable this, uncomment the two lines in `app.py` marked `# STREAMLIT CLOUD`.

## How It Works

1. Upload a `.mp4`, `.mov`, or `.webm` throw video
2. The app extracts 6–12 evenly-spaced frames using OpenCV
3. **Pass 1**: All frames sent to Claude Vision — it identifies which frame best represents each of the 6 technical positions
4. **Pass 2**: Each identified frame analyzed in depth against position-specific criteria
5. Physics engine estimates release velocity, angle, and projected distance
6. Claude writes a structured coaching report (Strengths, Faults, Cues, Projection)
7. Download the HTML report and print to PDF from your browser

## Events Supported

- Shot Put — Spin (rotational)
- Shot Put — Glide
- Discus

## File Structure

```
throwslab/
├── app.py           # Main Streamlit app
├── requirements.txt # Dependencies
└── README.md        # This file
```
