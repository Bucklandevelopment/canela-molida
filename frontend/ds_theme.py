"""UTOP.IA design-system theming for canela-molida (Streamlit).

Vendored from /projects/design-system/streamlit_theme.py (keep in sync).
Call inject_design_css(st) once, right after st.set_page_config().
"""

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@300;400;500&display=swap');

:root {
  --bg-primary: #0a0e17;
  --bg-secondary: #0d1321;
  --bg-card: rgba(13, 19, 33, 0.85);
  --text-primary: #e8edf5;
  --text-secondary: #8892a4;
  --text-muted: #4a5568;
  --border: rgba(0, 240, 255, 0.1);
  --border-strong: rgba(0, 240, 255, 0.2);
  --accent-cyan: #00f0ff;
  --accent-green: #00ff88;
  --accent-purple: #a855f7;
  --glow-cyan: 0 0 20px rgba(0, 240, 255, 0.3);
  --font-display: 'Orbitron', monospace;
  --font-body: 'Inter', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
  --radius: 8px;
  --radius-lg: 16px;
}

.stApp { background: var(--bg-primary); color: var(--text-primary); font-family: var(--font-body); }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stSidebar"] { background: var(--bg-secondary); border-right: 1px solid var(--border); }
.main .block-container { font-family: var(--font-body); }

h1, h2, h3, h4, h5, h6 { font-family: var(--font-display) !important; letter-spacing: 1px; color: var(--text-primary); }
h1 { background: linear-gradient(135deg, var(--accent-cyan), var(--accent-purple));
     -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; }

.stButton > button, .stDownloadButton > button {
  font-family: var(--font-mono); text-transform: uppercase; letter-spacing: 1px;
  background: linear-gradient(135deg, var(--accent-cyan), #4d7cff);
  color: var(--bg-primary); border: none; border-radius: var(--radius); font-weight: 600;
  transition: all 0.3s ease;
}
.stButton > button:hover, .stDownloadButton > button:hover { box-shadow: var(--glow-cyan); filter: brightness(1.08); }

.stTextInput input, .stTextArea textarea, .stNumberInput input,
.stSelectbox div[data-baseweb="select"] > div {
  background: var(--bg-secondary) !important; color: var(--text-primary) !important;
  border: 1px solid var(--border) !important; border-radius: var(--radius) !important;
  font-family: var(--font-mono);
}

[data-testid="stMetric"] {
  background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-lg);
  padding: 1rem; backdrop-filter: blur(20px);
}
[data-testid="stMetricValue"] { font-family: var(--font-display); color: var(--accent-cyan); }
[data-testid="stMetricLabel"] { font-family: var(--font-mono); color: var(--text-muted);
  text-transform: uppercase; letter-spacing: 2px; }

[data-testid="stVerticalBlockBorderWrapper"] {
  background: var(--bg-card); border: 1px solid var(--border) !important;
  border-radius: var(--radius-lg) !important; backdrop-filter: blur(20px);
}

.stTabs [data-baseweb="tab-list"] { border-bottom: 1px solid var(--border); }
.stTabs [data-baseweb="tab"] { font-family: var(--font-mono); text-transform: uppercase;
  letter-spacing: 1px; color: var(--text-secondary); }
.stTabs [aria-selected="true"] { color: var(--accent-cyan) !important; }

code, pre, .stCodeBlock { font-family: var(--font-mono) !important; }
[data-testid="stChatMessage"] { background: var(--bg-card); border: 1px solid var(--border);
  border-radius: var(--radius-lg); }

.stProgress > div > div > div { background: var(--accent-cyan); }
</style>
"""


def inject_design_css(st) -> None:
    """Inject the canonical UTOP.IA dark theme CSS into a Streamlit app."""
    st.markdown(_CSS, unsafe_allow_html=True)
