import streamlit as st
import os
import io
import re
import streamlit.components.v1 as components
from google import genai
from google.genai import types
from google.genai.errors import APIError as GeminiAPIError
from openai import OpenAI
import pypdf
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

# ══════════════════════════════════════════════════════════════════
# 1. CLIENTS
# ══════════════════════════════════════════════════════════════════
def _get_secret(key):
    if key in st.secrets and st.secrets[key]: return st.secrets[key]
    return os.environ.get(key)

gemini_key  = _get_secret("GEMINI_API_KEY")
typhoon_key = _get_secret("TYPHOON_API_KEY")
gemini_client  = genai.Client(api_key=gemini_key)   if gemini_key  else None
typhoon_client = OpenAI(api_key=typhoon_key, base_url="https://api.opentyphoon.ai/v1") if typhoon_key else None

GEMINI_MODEL  = "gemini-2.5-flash"
TYPHOON_MODEL = "typhoon-v2.5-30b-a3b-instruct"

# ══════════════════════════════════════════════════════════════════
# 2. PAGE CONFIG & DESIGN SYSTEM
# ══════════════════════════════════════════════════════════════════
st.set_page_config(page_title="TOR Workspace", page_icon="🛡️", layout="wide")

_CSS = """
<style>
/* ════════════════════════════════════════════════
   DESIGN TOKENS
════════════════════════════════════════════════ */
:root {
    --bg:          var(--background-color);
    --surface:     var(--secondary-background-color);
    --text:        var(--text-color);
    --muted:       rgba(128,128,128,0.65);
    --border:      rgba(128,128,128,0.10);
    --border-md:   rgba(128,128,128,0.20);

    --navy:        #060E24;
    --blue:        #1C4ED8;
    --blue-lt:     #3B82F6;
    --blue-dim:    rgba(59,130,246,0.10);
    --blue-glow:   rgba(59,130,246,0.22);
    --gold:        #D4A017;
    --gold-dim:    rgba(212,160,23,0.12);
    --green:       #059669;
    --green-dim:   rgba(5,150,105,0.12);
    --amber:       #D97706;
    --amber-dim:   rgba(217,119,6,0.12);
    --red:         #DC2626;
    --red-dim:     rgba(220,38,38,0.10);

    --radius-sm: 6px;
    --radius:    10px;
    --radius-lg: 14px;
    --radius-xl: 20px;

    --shadow-sm:   0 1px 4px rgba(0,0,0,0.06);
    --shadow:      0 4px 16px rgba(0,0,0,0.08);
    --shadow-lg:   0 12px 40px rgba(0,0,0,0.14);
    --shadow-blue: 0 4px 20px rgba(28,78,216,0.35);
}

/* ════ RESET ════ */
*, *::before, *::after { box-sizing: border-box; }
html, body, [class*="css"] {
    font-family: 'Sarabun', sans-serif !important;
}

/* ════ STREAMLIT SHELL ════ */
.stApp { background: var(--bg); color: var(--text); }
#MainMenu, footer, header { visibility: hidden; }
.block-container {
    max-width: 1080px !important;
    padding: 1.5rem 2rem 8rem !important;
}

/* ════ HERO ════ */
.hero {
    background: linear-gradient(140deg, #060E24 0%, #0D1B3E 45%, #132045 70%, #1a2f6b 100%);
    border-radius: var(--radius-xl);
    padding: 38px 46px 34px;
    margin-bottom: 36px;
    position: relative;
    overflow: hidden;
    border: 1px solid rgba(59,130,246,0.18);
    box-shadow: var(--shadow-lg), 0 0 0 1px rgba(255,255,255,0.03) inset;
}
.hero-grid {
    position: absolute; inset: 0;
    background-image:
        linear-gradient(rgba(59,130,246,0.04) 1px, transparent 1px),
        linear-gradient(90deg, rgba(59,130,246,0.04) 1px, transparent 1px);
    background-size: 40px 40px;
    pointer-events: none;
}
.hero-orb-1 {
    position: absolute;
    width: 420px; height: 420px;
    right: -100px; top: -140px;
    background: radial-gradient(circle, rgba(59,130,246,0.18) 0%, transparent 65%);
    pointer-events: none;
}
.hero-orb-2 {
    position: absolute;
    width: 220px; height: 220px;
    left: 30%; bottom: -70px;
    background: radial-gradient(circle, rgba(212,160,23,0.12) 0%, transparent 65%);
    pointer-events: none;
}
.hero-top-line {
    position: absolute;
    top: 0; left: 0; right: 0; height: 1px;
    background: linear-gradient(90deg, transparent 5%, rgba(212,160,23,0.7) 30%, rgba(59,130,246,0.5) 70%, transparent 95%);
}
.hero-eyebrow {
    display: flex; align-items: center; gap: 10px;
    margin-bottom: 16px; position: relative;
}
.hero-line {
    width: 24px; height: 1.5px;
    background: var(--gold); border-radius: 2px; opacity: 0.7;
}
.hero-label {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.68rem; font-weight: 600;
    letter-spacing: 2.5px; text-transform: uppercase;
    color: var(--gold);
}
.hero-title {
    font-family: 'Chakra Petch', sans-serif;
    font-size: 2rem; font-weight: 700;
    color: #F4F9FF;
    margin: 0 0 8px;
    letter-spacing: -0.5px; line-height: 1.15;
    position: relative;
}
.hero-title-accent {
    background: linear-gradient(135deg, #7DB8FA, #BFDBFE);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.hero-sub {
    font-size: 0.875rem;
    color: rgba(180,210,255,0.55);
    margin: 0 0 24px;
    line-height: 1.7; position: relative;
    max-width: 520px;
}
.hero-badges {
    display: flex; gap: 8px; flex-wrap: wrap;
    position: relative;
}
.hbadge {
    display: inline-flex; align-items: center; gap: 6px;
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 99px;
    padding: 5px 14px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.68rem; font-weight: 500;
    color: rgba(180,215,255,0.75);
    backdrop-filter: blur(8px);
    transition: border-color 0.2s, background 0.2s;
}
.hbadge:hover {
    border-color: rgba(59,130,246,0.4);
    background: rgba(59,130,246,0.08);
}
.hbadge-dot {
    width: 5px; height: 5px; border-radius: 50%;
    background: #34D399;
    box-shadow: 0 0 6px #34D399;
    animation: blink 2s ease-in-out infinite;
}
@keyframes blink { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:0.5;transform:scale(0.85)} }

/* ════ STEP HEADERS ════ */
.step-header {
    display: flex; align-items: center; gap: 14px;
    margin: 40px 0 18px; position: relative;
}
.step-header::after {
    content: ''; flex: 1; height: 1px;
    background: linear-gradient(90deg, rgba(59,130,246,0.2), transparent);
    margin-left: 4px;
}
.step-pill {
    display: flex; align-items: center; gap: 10px;
    background: linear-gradient(135deg, rgba(28,78,216,0.12), rgba(59,130,246,0.06));
    border: 1px solid rgba(59,130,246,0.25);
    border-radius: 99px;
    padding: 6px 18px 6px 7px;
}
.step-num {
    width: 30px; height: 30px;
    background: linear-gradient(135deg, #1C4ED8, #2563EB);
    color: white; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.72rem; font-weight: 600;
    box-shadow: 0 3px 10px rgba(28,78,216,0.4);
    flex-shrink: 0;
}
.step-title {
    font-size: 0.92rem; font-weight: 700;
    color: var(--blue-lt); letter-spacing: 0.2px;
}

/* ════ CARDS ════ */
.card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 24px 28px;
    margin-bottom: 16px;
    box-shadow: var(--shadow-sm), 0 0 0 1px rgba(255,255,255,0.02) inset;
    transition: border-color 0.2s;
}
.card:hover { border-color: var(--border-md); }

/* ════ FORM LABELS ════ */
.stTextInput > label,
.stTextArea > label,
.stNumberInput > label,
.stRadio > label,
.stFileUploader > label {
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.65rem !important;
    font-weight: 600 !important;
    letter-spacing: 1.5px !important;
    text-transform: uppercase !important;
    color: var(--muted) !important;
    margin-bottom: 6px !important;
}

/* ════ INPUTS ════ */
.stTextInput input,
.stNumberInput input {
    background: var(--bg) !important;
    border: 1.5px solid var(--border-md) !important;
    border-radius: var(--radius) !important;
    color: var(--text) !important;
    font-family: 'Sarabun', sans-serif !important;
    font-size: 0.95rem !important;
    padding: 10px 14px !important;
    transition: border-color 0.2s, box-shadow 0.2s, background 0.2s !important;
    box-shadow: var(--shadow-sm) !important;
}
.stTextInput input:focus,
.stNumberInput input:focus {
    border-color: var(--blue-lt) !important;
    box-shadow: 0 0 0 3px var(--blue-dim) !important;
    outline: none !important;
}
.stTextArea textarea {
    background: var(--bg) !important;
    border: 1.5px solid var(--border-md) !important;
    border-radius: var(--radius) !important;
    color: var(--text) !important;
    font-family: 'Sarabun', sans-serif !important;
    font-size: 0.93rem !important;
    line-height: 1.75 !important;
    transition: border-color 0.2s, box-shadow 0.2s !important;
    resize: vertical !important;
}
.stTextArea textarea:focus {
    border-color: var(--blue-lt) !important;
    box-shadow: 0 0 0 3px var(--blue-dim) !important;
}

/* ════ RADIO ════ */
.stRadio > div { gap: 12px !important; }
.stRadio [data-testid="stMarkdownContainer"] p {
    color: var(--text) !important; font-size: 0.9rem !important;
}

/* ════ BUTTONS ════ */
.stButton > button {
    border-radius: var(--radius) !important;
    font-family: 'Sarabun', sans-serif !important;
    font-size: 0.9rem !important; font-weight: 700 !important;
    transition: all 0.2s !important; letter-spacing: 0.2px !important;
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #1C4ED8 0%, #1e40af 100%) !important;
    color: white !important;
    box-shadow: var(--shadow-blue) !important;
    border: none !important;
    padding: 10px 24px !important;
}
.stButton > button[kind="primary"]:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 28px rgba(28,78,216,0.5) !important;
    background: linear-gradient(135deg, #2563EB 0%, #1C4ED8 100%) !important;
}
.stButton > button[kind="secondary"] {
    background: var(--surface) !important;
    color: var(--muted) !important;
    border: 1.5px solid var(--border-md) !important;
}
.stButton > button[kind="secondary"]:hover {
    border-color: var(--blue-lt) !important;
    color: var(--blue-lt) !important;
    background: var(--blue-dim) !important;
}
.stButton > button:disabled {
    opacity: 0.35 !important; cursor: not-allowed !important;
    transform: none !important;
}

/* ════ TOR SECTION CARDS ════ */
.tor-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    margin-bottom: 8px; overflow: hidden;
    transition: border-color 0.25s, box-shadow 0.25s, transform 0.15s;
    position: relative;
    box-shadow: var(--shadow-sm);
}
.tor-card::before {
    content: ''; position: absolute;
    left: 0; top: 0; bottom: 0; width: 3px;
    background: var(--border-md);
    border-radius: 3px 0 0 3px;
    transition: background 0.25s;
}
.tor-card:hover {
    border-color: rgba(59,130,246,0.28);
    box-shadow: 0 4px 16px rgba(59,130,246,0.08);
    transform: translateX(2px);
}
.tor-card:hover::before { background: var(--blue-lt); }
.tor-card.generating {
    border-color: rgba(59,130,246,0.5);
    box-shadow: 0 0 0 1px rgba(59,130,246,0.15), 0 6px 28px rgba(59,130,246,0.15);
}
.tor-card.generating::before {
    background: linear-gradient(180deg, var(--blue-lt), #60A5FA);
    animation: stripe-slide 1.5s linear infinite;
}
@keyframes stripe-slide { 0%,100%{opacity:1} 50%{opacity:0.4} }
.tor-card.done::before { background: var(--green); }
.tor-card.done { border-color: rgba(5,150,105,0.22); }

.tor-card-header {
    padding: 14px 20px 14px 24px;
    display: flex; align-items: center; gap: 14px;
    cursor: pointer; user-select: none;
}
.tor-index {
    font-family: 'Chakra Petch', sans-serif;
    font-size: 1.05rem; font-weight: 700;
    color: var(--border-md); min-width: 32px;
    transition: color 0.2s; letter-spacing: -0.5px;
}
.tor-card:hover .tor-index { color: var(--blue-lt); }
.tor-card.done .tor-index  { color: var(--green); }
.tor-card.generating .tor-index { color: var(--blue-lt); }
.tor-title-text {
    font-size: 0.92rem; font-weight: 600;
    color: var(--text); flex: 1; line-height: 1.4;
}

/* ════ STATUS CHIPS ════ */
.chip {
    display: inline-flex; align-items: center; gap: 5px;
    border-radius: 99px; padding: 3px 10px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.65rem; font-weight: 600; letter-spacing: 0.3px;
}
.chip-gen {
    background: var(--amber-dim); color: var(--amber);
    border: 1px solid rgba(217,119,6,0.3);
    animation: chip-pulse 1.4s ease-in-out infinite;
}
.chip-done {
    background: var(--green-dim); color: var(--green);
    border: 1px solid rgba(5,150,105,0.3);
}
@keyframes chip-pulse { 0%,100%{opacity:1} 50%{opacity:0.5} }

/* ════ ALERT BOXES ════ */
.alert {
    display: flex; align-items: flex-start; gap: 10px;
    border-radius: 0 var(--radius) var(--radius) 0;
    padding: 12px 16px; font-size: 0.88rem;
    line-height: 1.6; margin: 10px 0; border-left: 3px solid;
}
.alert-info  { background: var(--blue-dim);  border-color: var(--blue-lt); color: var(--blue-lt); }
.alert-warn  { background: var(--amber-dim); border-color: var(--amber);   color: var(--amber); }
.alert-ok    { background: var(--green-dim); border-color: var(--green);   color: var(--green); }
.alert-error { background: var(--red-dim);   border-color: var(--red);     color: var(--red); }

.info-box    { background: var(--blue-dim);  border-left: 3px solid var(--blue-lt); border-radius: 0 var(--radius) var(--radius) 0; padding: 12px 16px; color: var(--blue-lt); font-size: 0.88rem; margin: 10px 0; }
.warn-box    { background: var(--amber-dim); border-left: 3px solid var(--amber);   border-radius: 0 var(--radius) var(--radius) 0; padding: 12px 16px; color: var(--amber);   font-size: 0.88rem; margin: 10px 0; }
.success-box { background: var(--green-dim); border-left: 3px solid var(--green);   border-radius: 0 var(--radius) var(--radius) 0; padding: 12px 16px; color: var(--green);   font-size: 0.88rem; margin: 10px 0; }
.error-box   { background: var(--red-dim);   border-left: 3px solid var(--red);     border-radius: 0 var(--radius) var(--radius) 0; padding: 12px 16px; color: var(--red);     font-size: 0.88rem; margin: 10px 0; }

/* ════ PROJECT INFO PILL ════ */
.proj-pill {
    display: inline-flex; align-items: center;
    background: var(--surface);
    border: 1px solid var(--border-md);
    border-radius: var(--radius-lg);
    padding: 10px 20px; margin-bottom: 16px;
    font-size: 0.88rem; color: var(--text);
    box-shadow: var(--shadow-sm);
    flex-wrap: wrap; row-gap: 4px;
}
.proj-pill strong { color: var(--blue-lt); }
.pill-sep { color: var(--border-md); margin: 0 12px; font-size: 1rem; }

/* ════ STREAM CONTAINER ════ */
.stream-container {
    background: var(--bg);
    border: 1px solid rgba(59,130,246,0.25);
    border-radius: var(--radius);
    padding: 18px 20px; min-height: 90px;
    font-size: 0.92rem; line-height: 1.85;
    color: var(--text); position: relative;
}
.stream-container::before {
    content: 'GENERATING';
    position: absolute; top: 10px; right: 12px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.6rem; font-weight: 600;
    letter-spacing: 2px; color: var(--blue-lt); opacity: 0.5;
}

/* ════ PROGRESS BAR ════ */
.stProgress > div > div > div {
    background: linear-gradient(90deg, #1C4ED8, #3B82F6, #60A5FA) !important;
    border-radius: 99px !important;
}
.stProgress > div > div {
    background: var(--border) !important;
    border-radius: 99px !important; height: 6px !important;
}

/* ════ FILE UPLOADER ════ */
[data-testid="stFileUploader"] {
    background: var(--surface) !important;
    border: 1.5px dashed var(--border-md) !important;
    border-radius: var(--radius-lg) !important;
    padding: 10px !important;
    transition: border-color 0.2s, background 0.2s !important;
}
[data-testid="stFileUploader"]:hover {
    border-color: var(--blue-lt) !important;
    background: var(--blue-dim) !important;
}

/* ════ EXPANDER ════ */
.streamlit-expanderHeader {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    color: var(--text) !important; font-weight: 600 !important;
    font-size: 0.9rem !important;
    transition: border-color 0.2s !important;
}
.streamlit-expanderHeader:hover { border-color: var(--border-md) !important; }

/* ════ CHECKBOX ════ */
.stCheckbox label { font-size: 0.9rem !important; color: var(--text) !important; }

/* ════ EXPORT ZONE ════ */
.export-zone {
    background: var(--surface);
    border: 1px solid var(--border-md);
    border-radius: var(--radius-xl);
    padding: 32px 36px; margin-top: 44px;
    position: relative; overflow: hidden;
    box-shadow: var(--shadow);
}
.export-zone::before {
    content: ''; position: absolute;
    top: 0; left: 0; right: 0; height: 3px;
    background: linear-gradient(90deg, #1C4ED8, #3B82F6, #60A5FA, rgba(96,165,250,0));
}
.export-heading {
    font-family: 'Chakra Petch', sans-serif;
    font-size: 1.1rem; font-weight: 700;
    color: var(--text); margin: 0 0 4px; letter-spacing: -0.3px;
}
.export-sub { font-size: 0.8rem; color: var(--muted); margin: 0 0 24px; }

/* ════ DOWNLOAD BUTTONS ════ */
.stDownloadButton > button {
    background: var(--bg) !important;
    border: 1.5px solid var(--border-md) !important;
    color: var(--text) !important;
    border-radius: var(--radius-lg) !important;
    font-family: 'Sarabun', sans-serif !important;
    font-size: 0.9rem !important; font-weight: 700 !important;
    padding: 14px 18px !important; width: 100% !important;
    transition: all 0.2s !important;
    box-shadow: var(--shadow-sm) !important;
    text-align: left !important;
}
.stDownloadButton > button:hover {
    background: var(--blue-dim) !important;
    border-color: var(--blue-lt) !important;
    color: var(--blue-lt) !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 20px rgba(59,130,246,0.15) !important;
}

/* ════ MISC ════ */
hr { border-color: var(--border) !important; margin: 32px 0 !important; }
.stSpinner > div { border-top-color: var(--blue-lt) !important; }
[data-testid="stToast"] {
    background: var(--surface) !important;
    border: 1px solid var(--border-md) !important;
    color: var(--text) !important;
    border-radius: var(--radius-lg) !important;
    box-shadow: var(--shadow-lg) !important;
}

/* ════ GENERATION BANNER ════ */
.gen-banner {
    display: flex; align-items: center; gap: 12px;
    background: linear-gradient(90deg, var(--blue-dim), transparent);
    border: 1px solid var(--blue-glow);
    border-radius: var(--radius);
    padding: 12px 18px; margin-bottom: 8px; font-size: 0.88rem;
}
.gen-spinner {
    width: 14px; height: 14px;
    border: 2px solid var(--blue-dim);
    border-top-color: var(--blue-lt);
    border-radius: 50%;
    animation: spin 0.8s linear infinite; flex-shrink: 0;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
"""

st.markdown("""<link href="https://fonts.googleapis.com/css2?family=Sarabun:ital,wght@0,300;0,400;0,500;0,600;0,700;0,800;1,400&family=IBM+Plex+Mono:wght@400;500;600&family=Chakra+Petch:wght@500;600;700&display=swap" rel="stylesheet">""", unsafe_allow_html=True)
st.markdown(_CSS, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
# 3. CONSTANTS
# ══════════════════════════════════════════════════════════════════
TOR_TITLES = {
    1: "ความเป็นมา",
    2: "วัตถุประสงค์",
    3: "คุณสมบัติผู้ยื่นข้อเสนอ",
    4: "แบบรูปรายการ หรือคุณลักษณะเฉพาะของพัสดุ",
    5: "ระยะเวลาดำเนินการ",
    6: "ระยะเวลาส่งมอบงาน หรือส่งมอบพัสดุ",
    7: "หลักเกณฑ์ในการพิจารณาคัดเลือกข้อเสนอ",
    8: "อัตราค่าปรับ",
    9: "การรับประกันความชำรุดบกพร่อง",
    10: "ข้อสงวนสิทธิ์ในการยื่นข้อเสนอและอื่นๆ"
}

SYSTEM_PROMPT = (
    "คุณคือผู้เชี่ยวชาญระดับสูงด้านการจัดซื้อจัดจ้างภาครัฐไทย "
    "หน้าที่ของคุณคือเขียนเนื้อหาขอบเขตของงาน (TOR) ตามมาตรฐานหนังสือเวียน กค (กวจ) 0405.4/ว 159 ของกรมบัญชีกลาง "
    "จงเขียนอธิบายอย่างละเอียด ถี่ถ้วน ครอบคลุมทุกมิติทางกฎหมายพัสดุ ใช้ภาษาราชการไทยที่เป็นทางการอย่างสมบูรณ์ "
    "ห้ามระบุยี่ห้อหรือรุ่นของสินค้าโดยตรงเด็ดขาด ให้ใช้คุณลักษณะเชิงฟังก์ชัน (Functional Specification) เสมอ "
    "ใช้ตัวเลขอารบิกในการรันข้อย่อย ห้ามใช้เลขไทยในทุกกรณี "
    "ห้ามแปลเนื้อหาเป็นภาษาอังกฤษล้วน ให้ตอบเป็นภาษาไทยอย่างเป็นทางการเท่านั้น"
)

IT_BRANDS = (
    r"Intel|AMD|NVIDIA|GeForce|Asus|Acer|HP|Dell|Lenovo|Apple|Microsoft|Cisco|Huawei|"
    r"Samsung|LG|Epson|Canon|Panasonic|Sony|Fujitsu|Brother|Xerox|Toshiba|Sharp|Ricoh|"
    r"Kyocera|Hitachi|NEC|D-Link|TP-Link|Netgear|Synology|QNAP|Seagate|WD|Western Digital|"
    r"Kingston|Corsair|Logitech|Belkin|APC|Schneider|IBM|Oracle|VMware|Fortinet"
)

# ══════════════════════════════════════════════════════════════════
# 4. STATE MANAGEMENT
# ══════════════════════════════════════════════════════════════════
_DEFAULTS = {
    "tor_sections":          {i: "" for i in range(1, 11)},
    "meta_data":             {},
    "pdf_pre_cleaned_texts": {},
    "ai_drafted_spec_v4":    "",
    "generating_section":    None,
    "generate_all_queue":    [],
    "gen_error":             None,
    "proj_name":             "",
    "proj_agency":           "",
    "proj_budget":           0,
    "proj_criteria":         "เกณฑ์ราคา",
}
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ══════════════════════════════════════════════════════════════════
# 5. HELPERS
# ══════════════════════════════════════════════════════════════════
def call_gemini_with_retry(func, *args, **kwargs):
    last_exc = None
    for attempt in range(3):
        try:
            return func(*args, **kwargs)
        except GeminiAPIError as e:
            last_exc = e
            if e.code in [429, 503]:
                import time; time.sleep(5 * (attempt + 1))
                continue
            raise e
    raise last_exc

def extract_text_from_pdf(uploaded_file):
    try:
        reader = pypdf.PdfReader(uploaded_file)
        return "".join([p.extract_text() or "" for p in reader.pages])
    except:
        return ""

def local_regex_cleaner(text):
    if not text: return ""
    text = re.sub(r'\b\d{2,3}-\d{3}-\d{4}\b|\b\d{2,3}-\d{4}-\d{4}\b|\b\d{9,10}\b', "[PHONE_HIDDEN]", text)
    text = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', "[EMAIL_HIDDEN]", text)
    text = re.sub(r'https?://[^\s<>"]+|www\.[^\s<>"]+', "[URL_HIDDEN]", text)
    text = re.sub(r'(บริษัท\s+[^\s\n]+?\s+จำกัด(?:\s*\(มหาชน\))?)|(ห้างหุ้นส่วนจำกัด\s+[^\s\n]+)', "[COMPANY_HIDDEN]", text)
    en_co = r'\b[A-Za-z0-9\s\.,&\-\(\)]+?\s+(?:Co\s*\.?\s*,?\s*Ltd\s*\.?|Company\s+Limited|Inc\s*\.?|Corp\s*\.?|LLC|Group)\b'
    text = re.sub(en_co, "[COMPANY_HIDDEN]", text, flags=re.IGNORECASE)
    text = re.sub(IT_BRANDS, "[BRAND_HIDDEN]", text, flags=re.IGNORECASE)
    return text

def _extract_gemini_text(response):
    if hasattr(response, 'text') and response.text:
        return response.text
    if hasattr(response, 'candidates') and response.candidates:
        return response.candidates[0].content.parts[0].text
    return ""

def summarize_single_file_with_gemini(cleaned_text):
    if not gemini_client or not cleaned_text: return cleaned_text
    prompt = (
        "จงสกัดเฉพาะ 'ข้อมูลข้อกำหนดคุณลักษณะเฉพาะทางเทคนิค' และ "
        "'เงื่อนไขการสนับสนุน/การรับประกัน' จากเอกสารด้านล่าง\n"
        "สรุปกระชับ รักษาตัวเลขทางเทคนิคไว้ครบถ้วน:\n\n"
        f"[เนื้อหาเอกสาร]:\n{cleaned_text[:12000]}"
    )
    try:
        resp = call_gemini_with_retry(
            gemini_client.models.generate_content, model=GEMINI_MODEL,
            contents=prompt, config=types.GenerateContentConfig(temperature=0.1)
        )
        return _extract_gemini_text(resp) or cleaned_text[:2000]
    except Exception as e:
        return f"[สกัดสเปคไม่สำเร็จ: {e}]\n\n{cleaned_text[:2000]}"

def generate_typhoon_section(section_num, prompt_text, stream_placeholder):
    if not typhoon_client:
        stream_placeholder.markdown('<div class="error-box">❌ ไม่พบ Typhoon API Key</div>', unsafe_allow_html=True)
        return ""
    full_response = ""
    try:
        stream = typhoon_client.chat.completions.create(
            model=TYPHOON_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt_text}
            ],
            temperature=0.4, stream=True
        )
        for chunk in stream:
            delta = chunk.choices[0].delta
            if hasattr(delta, 'content') and delta.content:
                full_response += delta.content
                stream_placeholder.markdown(
                    f'<div class="stream-container">{full_response}▌</div>',
                    unsafe_allow_html=True
                )
        stream_placeholder.markdown(
            f'<div class="stream-container">{full_response}</div>',
            unsafe_allow_html=True
        )
        st.session_state.tor_sections[section_num] = full_response
        st.session_state.gen_error = None
        return full_response
    except Exception as e:
        err_msg = str(e)
        stream_placeholder.markdown(
            f'<div class="error-box">❌ เกิดข้อผิดพลาดในข้อ {section_num}: {err_msg}</div>',
            unsafe_allow_html=True
        )
        st.session_state.gen_error = err_msg
        return ""

def _make_on_change(idx):
    def _cb():
        st.session_state.tor_sections[idx] = st.session_state[f"ta_{idx}"]
    return _cb

_ON_CHANGE = {i: _make_on_change(i) for i in range(1, 11)}

# ══════════════════════════════════════════════════════════════════
# 6. EXPORT BUILDERS
# ══════════════════════════════════════════════════════════════════
def build_word_document():
    doc = Document()
    style = doc.styles['Normal']
    style.font.name = 'TH Sarabun New'
    style.font.size = Pt(14)
    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = title_p.add_run("ร่างขอบเขตของงาน (TOR)")
    r.bold = True; r.font.size = Pt(18)
    r.font.name = 'TH Sarabun New'
    r.font.color.rgb = RGBColor(0x1E, 0x3A, 0x8A)
    meta = st.session_state.meta_data
    sub_p = doc.add_paragraph()
    sub_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub_r = sub_p.add_run(f"โครงการ: {meta.get('title','ไม่ได้ระบุ')}")
    sub_r.font.size = Pt(15); sub_r.font.name = 'TH Sarabun New'
    doc.add_paragraph(f"หน่วยงาน: {meta.get('agency','-')}").runs[0].font.name = 'TH Sarabun New'
    doc.add_paragraph(f"วงเงินงบประมาณ: {meta.get('budget',0):,} บาท").runs[0].font.name = 'TH Sarabun New'
    doc.add_paragraph("─" * 50)
    for idx in range(1, 11):
        hp = doc.add_paragraph()
        hr = hp.add_run(f"ข้อ {idx}  {TOR_TITLES[idx]}")
        hr.bold = True; hr.font.size = Pt(15); hr.font.name = 'TH Sarabun New'
        hr.font.color.rgb = RGBColor(0x1E, 0x3A, 0x8A)
        cp = doc.add_paragraph(st.session_state.tor_sections.get(idx, "ไม่มีเนื้อหา"))
        cp.runs[0].font.name = 'TH Sarabun New'
        doc.add_paragraph()
    bio = io.BytesIO(); doc.save(bio); return bio.getvalue()

def build_html_document():
    meta = st.session_state.meta_data
    sections_html = ""
    for idx in range(1, 11):
        txt = st.session_state.tor_sections.get(idx, "").replace("\n", "<br>")
        sections_html += (
            f'<div class="section">'
            f'<div class="sec-title">ข้อ {idx} &nbsp;{TOR_TITLES[idx]}</div>'
            f'<div class="sec-content">{txt}</div></div>'
        )
    return f"""<!DOCTYPE html><html lang="th"><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Sarabun:wght@400;600;700&display=swap" rel="stylesheet">
<style>
body{{font-family:'Sarabun',sans-serif;padding:48px 60px;color:#1e293b;line-height:1.85;max-width:860px;margin:0 auto}}
h1{{text-align:center;font-size:22px;color:#0D1B3E;margin-bottom:4px;letter-spacing:-0.3px}}
.meta{{text-align:center;font-size:13px;color:#64748b;margin-bottom:36px}}
.section{{margin-bottom:32px;page-break-inside:avoid}}
.sec-title{{font-weight:700;font-size:15px;color:#1C4ED8;border-left:3px solid #3B82F6;
   padding:5px 0 5px 14px;margin-bottom:12px;background:#EFF6FF;border-radius:0 6px 6px 0}}
.sec-content{{font-size:14.5px;text-align:justify;padding-left:2px;color:#1e293b}}
</style></head><body>
<h1>ร่างขอบเขตของงาน (TOR)</h1>
<div class="meta">
  <strong>โครงการ:</strong> {meta.get('title','-')} &nbsp;|&nbsp;
  <strong>หน่วยงาน:</strong> {meta.get('agency','-') or 'ไม่ได้ระบุ'} &nbsp;|&nbsp;
  <strong>งบประมาณ:</strong> {meta.get('budget',0):,} บาท
</div>
{sections_html}</body></html>"""

# ══════════════════════════════════════════════════════════════════
# 7. UI — HERO HEADER
# ══════════════════════════════════════════════════════════════════
st.markdown("""
<div class="hero">
  <div class="hero-grid"></div>
  <div class="hero-orb-1"></div>
  <div class="hero-orb-2"></div>
  <div class="hero-top-line"></div>
  <div class="hero-eyebrow">
    <div class="hero-line"></div>
    <span class="hero-label">AI Procurement System · ว.159</span>
    <div class="hero-line"></div>
  </div>
  <div class="hero-title">🛡️ TOR <span class="hero-title-accent">Workspace</span></div>
  <div class="hero-sub">ระบบช่วยร่างขอบเขตของงาน ตามมาตรฐานกรมบัญชีกลาง — คัดกรองความโปร่งใส · สกัดสเปค · ร่าง 10 ข้อ</div>
  <div class="hero-badges">
    <span class="hbadge"><span class="hbadge-dot"></span>Gemini 2.5 Flash</span>
    <span class="hbadge"><span class="hbadge-dot"></span>Typhoon v2.5</span>
    <span class="hbadge">กค (กวจ) 0405.4/ว 159</span>
  </div>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
# 8. STEP 1 — PROJECT INFO
# ══════════════════════════════════════════════════════════════════
st.markdown("""
<div class="step-header">
  <div class="step-pill">
    <div class="step-num">1</div>
    <span class="step-title">ข้อมูลโครงการ</span>
  </div>
</div>""", unsafe_allow_html=True)

with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        p_name = st.text_input(
            "ชื่อโครงการ / งานจัดซื้อจัดจ้าง *",
            value=st.session_state.proj_name,
            placeholder="เช่น จัดซื้อครุภัณฑ์คอมพิวเตอร์ ประจำปี 2568",
            key="inp_name"
        )
        st.session_state.proj_name = p_name

        p_agency = st.text_input(
            "หน่วยงาน / ส่วนราชการ",
            value=st.session_state.proj_agency,
            placeholder="เช่น กองพัสดุ กรม XXX",
            key="inp_agency"
        )
        st.session_state.proj_agency = p_agency

    with c2:
        p_budget = st.number_input(
            "วงเงินงบประมาณ (บาท) *",
            min_value=0, step=5000,
            value=st.session_state.proj_budget,
            key="inp_budget"
        )
        st.session_state.proj_budget = p_budget

        p_criteria = st.radio(
            "หลักเกณฑ์การคัดเลือกข้อเสนอ",
            ["เกณฑ์ราคา", "เกณฑ์ราคาประกอบเกณฑ์อื่น"],
            index=["เกณฑ์ราคา","เกณฑ์ราคาประกอบเกณฑ์อื่น"].index(st.session_state.proj_criteria),
            horizontal=True,
            key="inp_criteria"
        )
        st.session_state.proj_criteria = p_criteria
    st.markdown('</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
# 9. STEP 2 — SPEC EXTRACTION
# ══════════════════════════════════════════════════════════════════
st.markdown("""
<div class="step-header">
  <div class="step-pill">
    <div class="step-num">2</div>
    <span class="step-title">สกัดสเปคอ้างอิง &amp; คัดกรองความโปร่งใส</span>
  </div>
</div>""", unsafe_allow_html=True)

st.markdown('<div class="card">', unsafe_allow_html=True)
job_desc = st.text_area(
    "วัตถุประสงค์ / ลักษณะงานที่ต้องการ",
    placeholder="อธิบายเป้าหมายการใช้งานจริง เช่น จัดซื้อคอมพิวเตอร์ตั้งโต๊ะสำหรับงานธุรการ จำนวน 10 เครื่อง...",
    height=90, key="inp_jobdesc"
)

cf1, cf2 = st.columns([3, 1])
with cf1:
    uploaded_files = st.file_uploader(
        "อัปโหลดไฟล์ PDF สเปคจากผู้ค้า (เลือกได้หลายไฟล์)",
        type=["pdf"], accept_multiple_files=True, label_visibility="visible"
    )
with cf2:
    st.write("")
    st.write("")
    do_clean = st.button("✂️  Regex คลีนข้อมูล", use_container_width=True, type="secondary")

if do_clean:
    if not uploaded_files:
        st.markdown('<div class="warn-box">⚠️ กรุณาอัปโหลดไฟล์ PDF ก่อน</div>', unsafe_allow_html=True)
    else:
        st.session_state.pdf_pre_cleaned_texts = {}
        with st.spinner("กำลัง Regex สกัดข้อมูล..."):
            for f in uploaded_files:
                raw = extract_text_from_pdf(f)
                st.session_state.pdf_pre_cleaned_texts[f.name] = local_regex_cleaner(raw)
        st.markdown(
            f'<div class="success-box">✓ คลีนเสร็จ {len(uploaded_files)} ไฟล์ — ตรวจสอบและแก้ไขด้านล่าง</div>',
            unsafe_allow_html=True
        )

st.markdown('</div>', unsafe_allow_html=True)

if st.session_state.pdf_pre_cleaned_texts:
    st.markdown('<div class="info-box">💡 ตรวจสอบและลบชื่อบริษัท/แบรนด์ที่อาจตกค้าง ก่อนส่ง Gemini</div>', unsafe_allow_html=True)
    for fname, txt in list(st.session_state.pdf_pre_cleaned_texts.items()):
        with st.expander(f"📁  {fname}", expanded=True):
            edited = st.text_area(
                "แก้ไขได้โดยตรง:", value=txt, height=160, key=f"verify_{fname}"
            )
            st.session_state.pdf_pre_cleaned_texts[fname] = edited

    confirmed = st.checkbox("✅  ยืนยันว่าตรวจสอบ / ลบแบรนด์เสร็จสิ้นแล้ว")

    if st.button("🚀  ส่ง Gemini สกัดสเปค → ซิงค์เข้าข้อ 4", type="primary", use_container_width=True):
        if not job_desc.strip():
            st.markdown('<div class="warn-box">⚠️ โปรดระบุวัตถุประสงค์ก่อน</div>', unsafe_allow_html=True)
        elif not confirmed:
            st.markdown('<div class="error-box">⚠️ กรุณายืนยันการตรวจสอบความโปร่งใสก่อน</div>', unsafe_allow_html=True)
        elif not gemini_client:
            st.markdown('<div class="error-box">❌ ไม่พบ Gemini API Key</div>', unsafe_allow_html=True)
        else:
            summaries = []
            prog = st.progress(0)
            items = list(st.session_state.pdf_pre_cleaned_texts.items())
            for idx, (fname, vtxt) in enumerate(items):
                st.toast(f"🤖 Gemini สกัดไฟล์ {idx+1}/{len(items)}: {fname}")
                s = summarize_single_file_with_gemini(vtxt)
                summaries.append(f"\n[สเปคจากไฟล์ {idx+1} ({fname})]:\n{s}\n")
                prog.progress((idx+1) / len(items))
            with st.spinner("รวมสเปคทั้งหมดเข้าข้อ 4..."):
                try:
                    merged = "".join(summaries)
                    prompt_merge = (
                        f"สรุปและเรียบเรียงข้อกำหนดคุณลักษณะเฉพาะทางเทคนิคเพื่อใส่ใน TOR ข้อ 4 "
                        f"วัตถุประสงค์: {job_desc} "
                        f"ข้อมูลสเปค: {merged} "
                        "แบ่งหมวดย่อย 4.1, 4.2 ห้ามมีชื่อคู่ค้าหรือแบรนด์ใดๆ"
                    )
                    resp = call_gemini_with_retry(
                        gemini_client.models.generate_content,
                        model=GEMINI_MODEL, contents=prompt_merge
                    )
                    final_text = _extract_gemini_text(resp)
                    st.session_state.ai_drafted_spec_v4 = final_text
                    st.session_state.tor_sections[4] = final_text
                    if "ta_4" in st.session_state:
                        del st.session_state["ta_4"]
                    st.markdown('<div class="success-box">🎉 ซิงค์สเปคเข้าข้อ 4 เรียบร้อย!</div>', unsafe_allow_html=True)
                    st.markdown("""
                    <div style="margin-top:16px;">
                      <div style="font-family:'IBM Plex Mono',monospace;font-size:0.65rem;font-weight:600;letter-spacing:1.5px;text-transform:uppercase;color:var(--muted);margin-bottom:8px;">
                        📋 สเปคที่ Gemini สกัดได้ (ข้อ 4)
                      </div>
                    </div>""", unsafe_allow_html=True)
                    st.text_area(
                        label="สเปค Gemini",
                        value=final_text,
                        height=300,
                        key="gemini_spec_preview",
                        label_visibility="collapsed",
                        disabled=True
                    )
                    st.rerun()
                except Exception as e:
                    st.markdown(f'<div class="error-box">❌ {e}</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
# 10. STEP 3 — TOR 10 SECTIONS
# ══════════════════════════════════════════════════════════════════
st.markdown("""
<div class="step-header">
  <div class="step-pill">
    <div class="step-num">3</div>
    <span class="step-title">ร่างขอบเขตงาน TOR 10 ข้อหลัก</span>
  </div>
</div>""", unsafe_allow_html=True)

is_busy = st.session_state.generating_section is not None

# ── แสดงสเปค Gemini (ถ้ามี) ─────────────────────────────────────
if st.session_state.ai_drafted_spec_v4.strip():
    with st.expander("📋 สเปคที่ Gemini สกัดได้ (ข้อ 4) — คลิกเพื่อดู/ซ่อน", expanded=False):
        st.markdown(
            '<small style="color:var(--muted);">สเปคนี้จะถูกส่งให้ Typhoon เป็น reference ตอนร่างข้อ 4 โดยอัตโนมัติ</small>',
            unsafe_allow_html=True
        )
        st.text_area(
            label="gemini_spec_ro",
            value=st.session_state.ai_drafted_spec_v4,
            height=280,
            key="gemini_spec_readonly",
            label_visibility="collapsed",
            disabled=True
        )
    st.write("")

if p_name:
    st.markdown(
        f'<div class="proj-pill">'
        f'📍 <strong>{p_name}</strong>'
        f'<span class="pill-sep">|</span>'
        f'งบประมาณ <strong>{p_budget:,} บาท</strong>'
        f'<span class="pill-sep">|</span>'
        f'{p_criteria}'
        f'</div>',
        unsafe_allow_html=True
    )

if is_busy:
    gen_sec = st.session_state.generating_section
    queue_remaining = len(st.session_state.generate_all_queue)
    col_info, col_cancel = st.columns([4, 1])
    with col_info:
        queue_txt = f" &nbsp;·&nbsp; เหลือในคิว {queue_remaining} ข้อ" if queue_remaining else ""
        st.markdown(
            f'<div class="gen-banner">'
            f'<div class="gen-spinner"></div>'
            f'<span>กำลังร่าง <strong>ข้อ {gen_sec}</strong> — {TOR_TITLES[gen_sec]}{queue_txt}</span>'
            f'</div>',
            unsafe_allow_html=True
        )
    with col_cancel:
        if st.button("⛔  ยกเลิก", key="btn_cancel", use_container_width=True):
            st.session_state.generating_section = None
            st.session_state.generate_all_queue = []
            st.session_state.gen_error = None
            if f"ta_{i}" in st.session_state:
                del st.session_state[f"ta_{i}"]
            st.rerun()

st.write("")

if st.session_state.gen_error:
    st.markdown(
        f'<div class="error-box">⚠️ ร่างข้อก่อนหน้าล้มเหลว: {st.session_state.gen_error} — คิวถูกหยุดแล้ว</div>',
        unsafe_allow_html=True
    )

# ── render 10 ข้อ ──────────────────────────────────────────────────
for i in range(1, 11):
    is_gen_this = (st.session_state.generating_section == i)
    has_content = bool(st.session_state.tor_sections[i].strip())

    card_cls = "tor-card generating" if is_gen_this else ("tor-card done" if has_content else "tor-card")
    status_html = ""
    if is_gen_this:
        status_html = '<span class="chip chip-gen">⚡ กำลังร่าง</span>'
    elif has_content:
        status_html = '<span class="chip chip-done">✓ เสร็จแล้ว</span>'

    st.markdown(f"""
    <div class="{card_cls}">
      <div class="tor-card-header">
        <span class="tor-index">{i:02d}</span>
        <span class="tor-title-text">{TOR_TITLES[i]}</span>
        {status_html}
      </div>
    </div>""", unsafe_allow_html=True)

    with st.expander("", expanded=is_gen_this or (i == 4 and has_content)):
        if is_gen_this:
            stream_box = st.empty()
            stream_box.markdown('<div class="stream-container">กำลังร่างเนื้อหา...</div>', unsafe_allow_html=True)
            proj_ctx = (
                f"โครงการ: {p_name}, หน่วยงาน: {p_agency}, "
                f"งบประมาณ: {p_budget:,} บาท, เกณฑ์: {p_criteria}"
            )
            gemini_spec = st.session_state.ai_drafted_spec_v4
            if i == 4 and gemini_spec.strip():
                prompt = (
                    f"จงเขียนเนื้อหาของขอบเขตของงาน (TOR) ตามมาตรฐานราชการไทย ว.159 "
                    f"เฉพาะ 'ข้อ {i} หัวข้อ: {TOR_TITLES[i]}' ของ{proj_ctx}\n\n"
                    f"⚠️ สำคัญมาก: ให้ใช้ข้อมูลสเปคด้านล่างนี้เป็นฐานในการเขียนทุกคุณลักษณะเฉพาะ "
                    f"ห้ามเปลี่ยนแปลง เพิ่ม หรือตัดทอนตัวเลขและข้อกำหนดทางเทคนิคโดยเด็ดขาด "
                    f"ให้จัดเรียงเป็นรูปแบบ TOR ราชการเท่านั้น:\n\n"
                    f"[สเปคที่ได้จากการสกัดเอกสาร]:\n{gemini_spec}"
                )
            else:
                prompt = (
                    f"จงเขียนเนื้อหาของขอบเขตของงาน (TOR) ตามมาตรฐานราชการไทย ว.159 "
                    f"เฉพาะ 'ข้อ {i} หัวข้อ: {TOR_TITLES[i]}' ของ{proj_ctx} "
                    "อธิบายรายละเอียดเชิงระเบียบพัสดุให้ครบถ้วนและสละสลวย"
                )
            generate_typhoon_section(i, prompt, stream_box)
            if st.session_state.gen_error:
                st.session_state.generating_section = None
                st.session_state.generate_all_queue = []
            else:
                st.session_state.generating_section = None
                if st.session_state.generate_all_queue:
                    next_sec = st.session_state.generate_all_queue.pop(0)
                    st.session_state.generating_section = next_sec
            st.rerun()

        else:
            st.text_area(
                label="เนื้อหา",
                value=st.session_state.tor_sections[i],
                height=200,
                key=f"ta_{i}",
                on_change=_ON_CHANGE[i],
                label_visibility="collapsed"
            )
            if i == 4 and st.session_state.ai_drafted_spec_v4:
                st.markdown('<small style="color:var(--green);font-weight:600;">✓ ซิงค์สเปค Gemini แล้ว</small>', unsafe_allow_html=True)

            col_btn, _ = st.columns([1, 3])
            with col_btn:
                if st.button(f"🔄  รีเจนข้อ {i}", key=f"btn_regen_{i}", disabled=is_busy, type="secondary"):
                    if not p_name:
                        st.markdown('<div class="error-box">กรุณาระบุชื่อโครงการก่อน</div>', unsafe_allow_html=True)
                    else:
                        st.session_state.gen_error = None
                        st.session_state.generating_section = i
                        st.rerun()

st.write("")

# ── ปุ่มรันทั้งหมด ──────────────────────────────────────────────────
col_run, col_clear = st.columns([3, 1])
with col_run:
    if st.button(
        "✨  ให้ Typhoon ร่างทุกข้อที่ยังว่าง",
        type="primary", use_container_width=True, disabled=is_busy
    ):
        if not p_name:
            st.markdown('<div class="error-box">⚠️ กรุณาระบุชื่อโครงการก่อน</div>', unsafe_allow_html=True)
        else:
            st.session_state.meta_data = {"title": p_name, "agency": p_agency, "budget": p_budget, "criteria": p_criteria}
            queue = [i for i in range(1, 11) if not st.session_state.tor_sections[i].strip()]
            if not queue:
                st.markdown('<div class="info-box">ทุกข้อมีเนื้อหาแล้ว หากต้องการ re-gen ให้กด "ล้างทั้งหมด" ก่อน</div>', unsafe_allow_html=True)
            else:
                st.session_state.gen_error = None
                first = queue.pop(0)
                st.session_state.generate_all_queue = queue
                st.session_state.generating_section = first
                st.rerun()

with col_clear:
    if st.button("🗑️  ล้างทั้งหมด", use_container_width=True, disabled=is_busy, type="secondary"):
        st.session_state.tor_sections = {i: "" for i in range(1, 11)}
        st.session_state.ai_drafted_spec_v4 = ""
        st.session_state.gen_error = None
        st.rerun()

# ══════════════════════════════════════════════════════════════════
# 11. EXPORT HUB
# ══════════════════════════════════════════════════════════════════
has_any = any(st.session_state.tor_sections[i].strip() for i in range(1, 11))
if has_any:
    if not st.session_state.meta_data:
        st.session_state.meta_data = {"title": p_name or "ไม่ได้ระบุ", "agency": p_agency, "budget": p_budget, "criteria": p_criteria}

    st.markdown('<div class="export-zone">', unsafe_allow_html=True)
    st.markdown("""
    <div style="display:flex;align-items:center;gap:14px;margin-bottom:22px;">
      <div style="width:46px;height:46px;background:var(--blue-dim);border:1px solid var(--blue-glow);border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:1.3rem;flex-shrink:0;">📥</div>
      <div>
        <div class="export-heading">ส่งออกเอกสาร TOR</div>
        <div class="export-sub">เลือกรูปแบบไฟล์ที่ต้องการดาวน์โหลด</div>
      </div>
    </div>""", unsafe_allow_html=True)

    all_txt = f"ร่างขอบเขตของงาน (TOR) — {st.session_state.meta_data.get('title','')}\n\n"
    for idx in range(1, 11):
        all_txt += f"ข้อ {idx} {TOR_TITLES[idx]}\n{st.session_state.tor_sections.get(idx,'')}\n\n"

    word_bytes = build_word_document()
    html_bytes = build_html_document()
    fname_base = p_name.replace(" ", "_") if p_name else "TOR_Project"

    dc1, dc2, dc3 = st.columns(3)
    with dc1:
        st.download_button(
            "📝  Word Document (.DOCX)",
            data=word_bytes,
            file_name=f"{fname_base}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
            help="ฟอนต์ TH Sarabun New พร้อมใช้งาน"
        )
    with dc2:
        st.download_button(
            "📄  ข้อความธรรมดา (.TXT)",
            data=all_txt,
            file_name=f"{fname_base}.txt",
            mime="text/plain",
            use_container_width=True,
            help="เปิดได้ทุก Text Editor"
        )
    with dc3:
        st.download_button(
            "🖨️  พิมพ์เป็น PDF (.HTML)",
            data=html_bytes,
            file_name=f"{fname_base}_Print.html",
            mime="text/html",
            use_container_width=True,
            help="เปิดในเบราว์เซอร์ → Ctrl+P → Save as PDF"
        )
    st.markdown('</div>', unsafe_allow_html=True)
