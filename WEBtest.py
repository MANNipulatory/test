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
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+Thai:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root {
    --tor-surface:      var(--secondary-background-color);
    --tor-bg:           var(--background-color);
    --tor-text:         var(--text-color);
    --tor-border:       rgba(128,128,128,0.18);
    --tor-border-hover: rgba(59,130,246,0.4);
    --tor-accent:       #3B82F6;
    --tor-accent-dim:   rgba(59,130,246,0.14);
    --tor-muted:        rgba(128,128,128,0.75);
}
*, *::before, *::after { box-sizing: border-box; }
html, body, [class*="css"] { font-family: 'Noto Sans Thai', sans-serif !important; }
.stApp { background: var(--tor-bg); color: var(--tor-text); }
#MainMenu, footer, header { visibility: hidden; }
.block-container { max-width: 1100px !important; padding: 2rem 2rem 6rem !important; }
.app-header { background: var(--tor-surface); border: 1px solid var(--tor-border); border-radius: 16px; padding: 28px 36px; margin-bottom: 32px; position: relative; overflow: hidden; }
.app-header::before { content: ''; position: absolute; top: 0; right: 0; width: 300px; height: 100%; background: radial-gradient(ellipse at right center, var(--tor-accent-dim) 0%, transparent 70%); pointer-events: none; }
.app-header-title { font-size: 1.6rem; font-weight: 700; color: var(--tor-text); margin: 0 0 6px; }
.app-header-sub { font-size: 0.85rem; color: var(--tor-muted); margin: 0; display: flex; align-items: center; gap: 16px; }
.badge { background: var(--tor-accent-dim); color: var(--tor-accent); border: 1px solid rgba(59,130,246,0.3); border-radius: 20px; padding: 2px 10px; font-size: 0.75rem; font-weight: 600; font-family: 'IBM Plex Mono', monospace; }
.sec-header { display: flex; align-items: center; gap: 12px; margin: 36px 0 20px; }
.sec-number { width: 32px; height: 32px; background: linear-gradient(135deg, #2563EB, #1D4ED8); color: white; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 0.85rem; font-weight: 700; flex-shrink: 0; box-shadow: 0 4px 12px rgba(37,99,235,0.35); }
.sec-title { font-size: 1.05rem; font-weight: 600; color: var(--tor-text); margin: 0; }
.card { background: var(--tor-surface); border: 1px solid var(--tor-border); border-radius: 12px; padding: 24px; margin-bottom: 16px; }
.stTextInput > label, .stTextArea > label, .stNumberInput > label, .stRadio > label, .stFileUploader > label { color: var(--tor-muted) !important; font-size: 0.82rem !important; font-weight: 500 !important; letter-spacing: 0.3px !important; text-transform: uppercase !important; margin-bottom: 6px !important; }
.stTextInput input, .stNumberInput input { background: var(--tor-bg) !important; border: 1px solid var(--tor-border) !important; border-radius: 8px !important; color: var(--tor-text) !important; font-family: 'Noto Sans Thai', sans-serif !important; font-size: 0.95rem !important; padding: 10px 14px !important; transition: border-color 0.2s, box-shadow 0.2s !important; }
.stTextInput input:focus, .stNumberInput input:focus { border-color: var(--tor-accent) !important; box-shadow: 0 0 0 3px var(--tor-accent-dim) !important; }
.stTextArea textarea { background: var(--tor-bg) !important; border: 1px solid var(--tor-border) !important; border-radius: 8px !important; color: var(--tor-text) !important; font-family: 'Noto Sans Thai', sans-serif !important; font-size: 0.93rem !important; line-height: 1.7 !important; transition: border-color 0.2s, box-shadow 0.2s !important; resize: vertical !important; }
.stTextArea textarea:focus { border-color: var(--tor-accent) !important; box-shadow: 0 0 0 3px var(--tor-accent-dim) !important; }
.stRadio > div { gap: 12px !important; }
.stRadio [data-testid="stMarkdownContainer"] p { color: var(--tor-text) !important; font-size: 0.9rem !important; }
.stButton > button { border-radius: 8px !important; font-family: 'Noto Sans Thai', sans-serif !important; font-size: 0.88rem !important; font-weight: 600 !important; transition: all 0.18s !important; }
.stButton > button[kind="primary"] { background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%) !important; color: white !important; box-shadow: 0 4px 14px rgba(37,99,235,0.35) !important; border: none !important; }
.stButton > button[kind="primary"]:hover { transform: translateY(-1px) !important; box-shadow: 0 6px 20px rgba(37,99,235,0.45) !important; }
.stButton > button[kind="secondary"] { background: var(--tor-surface) !important; color: var(--tor-muted) !important; border: 1px solid var(--tor-border) !important; }
.stButton > button[kind="secondary"]:hover { border-color: var(--tor-border-hover) !important; color: var(--tor-text) !important; }
.stButton > button:disabled { opacity: 0.4 !important; cursor: not-allowed !important; transform: none !important; }
.tor-card { background: var(--tor-surface); border: 1px solid var(--tor-border); border-radius: 12px; margin-bottom: 12px; overflow: hidden; transition: border-color 0.2s; }
.tor-card:hover { border-color: var(--tor-border-hover); }
.tor-card.generating { border-color: var(--tor-accent); box-shadow: 0 0 0 1px var(--tor-accent-dim), 0 4px 24px var(--tor-accent-dim); }
.tor-card.done { border-color: rgba(16,185,129,0.35); }
.tor-card-header { padding: 14px 20px; display: flex; align-items: center; gap: 12px; cursor: pointer; user-select: none; }
.tor-num { width: 26px; height: 26px; background: var(--tor-accent-dim); color: var(--tor-accent); border-radius: 6px; font-size: 0.78rem; font-weight: 700; font-family: 'IBM Plex Mono', monospace; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.tor-num.done-num { background: rgba(16,185,129,0.18); color: #10B981; }
.tor-title-text { font-size: 0.9rem; font-weight: 600; color: var(--tor-text); flex: 1; }
.status-gen { background: rgba(245,158,11,0.15); color: #D97706; border: 1px solid rgba(245,158,11,0.3); border-radius: 6px; padding: 2px 9px; font-size: 0.72rem; font-weight: 600; font-family: 'IBM Plex Mono', monospace; animation: pulse-badge 1.2s ease-in-out infinite; }
.status-done { background: rgba(16,185,129,0.12); color: #059669; border: 1px solid rgba(16,185,129,0.3); border-radius: 6px; padding: 2px 9px; font-size: 0.72rem; font-weight: 600; }
@keyframes pulse-badge { 0%, 100% { opacity: 1; } 50% { opacity: 0.55; } }
.info-box { background: var(--tor-accent-dim); border: 1px solid rgba(59,130,246,0.28); border-radius: 8px; padding: 12px 16px; color: var(--tor-accent); font-size: 0.88rem; margin: 12px 0; }
.warn-box { background: rgba(245,158,11,0.1); border: 1px solid rgba(245,158,11,0.28); border-radius: 8px; padding: 12px 16px; color: #B45309; font-size: 0.88rem; margin: 12px 0; }
.success-box { background: rgba(16,185,129,0.1); border: 1px solid rgba(16,185,129,0.28); border-radius: 8px; padding: 12px 16px; color: #047857; font-size: 0.88rem; margin: 12px 0; }
.error-box { background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.28); border-radius: 8px; padding: 12px 16px; color: #B91C1C; font-size: 0.88rem; margin: 12px 0; }
.stProgress > div > div > div { background: linear-gradient(90deg, #2563EB, #60A5FA) !important; border-radius: 99px !important; }
.stProgress > div > div { background: var(--tor-border) !important; border-radius: 99px !important; }
[data-testid="stFileUploader"] { background: var(--tor-surface) !important; border: 1.5px dashed var(--tor-border) !important; border-radius: 10px !important; padding: 8px !important; transition: border-color 0.2s !important; }
[data-testid="stFileUploader"]:hover { border-color: var(--tor-border-hover) !important; }
.streamlit-expanderHeader { background: var(--tor-surface) !important; border: 1px solid var(--tor-border) !important; border-radius: 8px !important; color: var(--tor-text) !important; font-weight: 600 !important; font-size: 0.88rem !important; }
.stCheckbox label { color: var(--tor-muted) !important; font-size: 0.88rem !important; }
.stDownloadButton > button { background: var(--tor-surface) !important; border: 1px solid var(--tor-border) !important; color: var(--tor-text) !important; border-radius: 10px !important; font-family: 'Noto Sans Thai', sans-serif !important; font-size: 0.88rem !important; font-weight: 600 !important; padding: 12px 16px !important; width: 100% !important; transition: all 0.18s !important; }
.stDownloadButton > button:hover { background: var(--tor-accent-dim) !important; border-color: var(--tor-border-hover) !important; color: var(--tor-accent) !important; transform: translateY(-1px) !important; }
.export-section { background: var(--tor-surface); border: 1px solid var(--tor-border); border-radius: 16px; padding: 28px; margin-top: 36px; }
.export-title { font-size: 1rem; font-weight: 700; color: var(--tor-text); }
.export-sub { font-size: 0.8rem; color: var(--tor-muted); }
hr { border-color: var(--tor-border) !important; margin: 28px 0 !important; }
.stSpinner > div { border-top-color: var(--tor-accent) !important; }
[data-testid="stToast"] { background: var(--tor-surface) !important; border: 1px solid var(--tor-border) !important; color: var(--tor-text) !important; border-radius: 10px !important; }
.stream-container { background: var(--tor-bg); border: 1px solid rgba(59,130,246,0.3); border-radius: 8px; padding: 16px; min-height: 80px; font-size: 0.92rem; line-height: 1.8; color: var(--tor-text); }
</style>
"""

# inject CSS — ใช้ components.html เพื่อป้องกัน Streamlit sanitize <style> tag
components.html(_CSS, height=0)


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
    "tor_sections":         {i: "" for i in range(1, 11)},
    "meta_data":            {},
    "pdf_pre_cleaned_texts":{},
    "ai_drafted_spec_v4":   "",
    "generating_section":   None,
    "generate_all_queue":   [],
    "gen_error":            None,
    "proj_name":            "",
    "proj_agency":          "",
    "proj_budget":          0,
    "proj_criteria":        "เกณฑ์ราคา",
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
            temperature=0.4,
            stream=True
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
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+Thai:wght@400;600;700&display=swap" rel="stylesheet">
<style>
body{{font-family:'Noto Sans Thai',sans-serif;padding:48px 60px;color:#1e293b;line-height:1.8;max-width:860px;margin:0 auto}}
h1{{text-align:center;font-size:22px;color:#1E3A8A;margin-bottom:4px}}
.meta{{text-align:center;font-size:13px;color:#64748b;margin-bottom:36px}}
.section{{margin-bottom:28px;page-break-inside:avoid}}
.sec-title{{font-weight:700;font-size:15px;color:#1E3A8A;border-left:3px solid #3B82F6;
   padding:4px 0 4px 12px;margin-bottom:10px;background:#F0F6FF;border-radius:0 4px 4px 0}}
.sec-content{{font-size:14px;text-align:justify;padding-left:4px}}
</style></head><body>
<h1>ร่างขอบเขตของงาน (TOR)</h1>
<div class="meta">
  <strong>โครงการ:</strong> {meta.get('title','-')} &nbsp;|&nbsp;
  <strong>หน่วยงาน:</strong> {meta.get('agency','-') or 'ไม่ได้ระบุ'} &nbsp;|&nbsp;
  <strong>งบประมาณ:</strong> {meta.get('budget',0):,} บาท
</div>
{sections_html}</body></html>"""

# ══════════════════════════════════════════════════════════════════
# 7. UI — HEADER
# ══════════════════════════════════════════════════════════════════
st.markdown("""
<div class="app-header">
  <div class="app-header-title">🛡️ AI Procurement TOR Workspace</div>
  <div class="app-header-sub">
    <span class="badge">Gemini 2.5 Flash</span>
    <span class="badge">Typhoon v2.5</span>
    <span>ระบบช่วยร่างขอบเขตของงาน (TOR) ตามมาตรฐาน ว.159 กรมบัญชีกลาง</span>
  </div>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
# 8. STEP 1 — PROJECT INFO
# ══════════════════════════════════════════════════════════════════
st.markdown("""
<div class="sec-header">
  <div class="sec-number">1</div>
  <p class="sec-title">ข้อมูลโครงการ</p>
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
            placeholder="เช่น กองพัสดุ กรมXXX",
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
<div class="sec-header">
  <div class="sec-number">2</div>
  <p class="sec-title">สกัดสเปคอ้างอิง &amp; คัดกรองความโปร่งใส</p>
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
    do_clean = st.button("✂️ Regex คลีนข้อมูล", use_container_width=True, type="secondary")

if do_clean:
    if not uploaded_files:
        st.markdown('<div class="warn-box">⚠️ กรุณาอัปโหลดไฟล์ PDF ก่อน</div>', unsafe_allow_html=True)
    else:
        st.session_state.pdf_pre_cleaned_texts = {}
        with st.spinner("⚡ กำลัง Regex สกัดข้อมูล..."):
            for f in uploaded_files:
                raw = extract_text_from_pdf(f)
                st.session_state.pdf_pre_cleaned_texts[f.name] = local_regex_cleaner(raw)
        st.markdown(
            f'<div class="success-box">✓ คลีนเสร็จ {len(uploaded_files)} ไฟล์ — ตรวจสอบและแก้ไขด้านล่าง</div>',
            unsafe_allow_html=True
        )

st.markdown('</div>', unsafe_allow_html=True)

if st.session_state.pdf_pre_cleaned_texts:
    st.markdown(
        '<div class="info-box">💡 ตรวจสอบและลบชื่อบริษัท/แบรนด์ที่อาจตกค้าง ก่อนส่ง Gemini</div>',
        unsafe_allow_html=True
    )
    for fname, txt in list(st.session_state.pdf_pre_cleaned_texts.items()):
        with st.expander(f"📁 {fname}", expanded=True):
            edited = st.text_area(
                "แก้ไขได้โดยตรง:", value=txt, height=160, key=f"verify_{fname}"
            )
            st.session_state.pdf_pre_cleaned_texts[fname] = edited

    confirmed = st.checkbox("✅ ยืนยันว่าตรวจสอบ / ลบแบรนด์เสร็จสิ้นแล้ว")

    if st.button("🚀 ส่ง Gemini สกัดสเปค → ซิงค์เข้าข้อ 4", type="primary", use_container_width=True):
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

            with st.spinner("⚙️ รวมสเปคทั้งหมดเข้าข้อ 4..."):
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
                    st.markdown('<div class="success-box">🎉 ซิงค์สเปคเข้าข้อ 4 เรียบร้อย! เลื่อนลงดูข้อ 4 ด้านล่าง</div>', unsafe_allow_html=True)
                    st.rerun()
                except Exception as e:
                    st.markdown(f'<div class="error-box">❌ {e}</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
# 10. STEP 3 — TOR 10 SECTIONS
# ══════════════════════════════════════════════════════════════════
st.markdown("""
<div class="sec-header">
  <div class="sec-number">3</div>
  <p class="sec-title">ร่างขอบเขตงาน TOR 10 ข้อหลัก</p>
</div>""", unsafe_allow_html=True)

is_busy = st.session_state.generating_section is not None

if p_name:
    st.markdown(
        f'<div class="info-box" style="margin-bottom:16px;">📍 <strong>{p_name}</strong> &nbsp;|&nbsp; '
        f'งบประมาณ <strong>{p_budget:,} บาท</strong> &nbsp;|&nbsp; {p_criteria}</div>',
        unsafe_allow_html=True
    )

if is_busy:
    gen_sec = st.session_state.generating_section
    queue_remaining = len(st.session_state.generate_all_queue)
    col_info, col_cancel = st.columns([4, 1])
    with col_info:
        st.markdown(
            f'<div class="warn-box" style="margin:0;">⚡ กำลังร่างข้อ <strong>{gen_sec}</strong>: {TOR_TITLES[gen_sec]}'
            + (f' &nbsp;|&nbsp; เหลือในคิว: {queue_remaining} ข้อ' if queue_remaining else '') +
            '</div>', unsafe_allow_html=True
        )
    with col_cancel:
        if st.button("⛔ ยกเลิก", key="btn_cancel", use_container_width=True):
            st.session_state.generating_section = None
            st.session_state.generate_all_queue = []
            st.session_state.gen_error = None
            st.rerun()

st.write("")

if st.session_state.gen_error:
    st.markdown(
        f'<div class="error-box">⚠️ การร่างข้อก่อนหน้าล้มเหลว: {st.session_state.gen_error} — คิวถูกหยุดแล้ว</div>',
        unsafe_allow_html=True
    )

# ── render 10 ข้อ ─────────────────────────────────────────────────
for i in range(1, 11):
    is_gen_this = (st.session_state.generating_section == i)
    has_content = bool(st.session_state.tor_sections[i].strip())

    card_cls = "tor-card generating" if is_gen_this else ("tor-card done" if has_content else "tor-card")
    num_cls  = "tor-num done-num" if has_content else "tor-num"
    status_html = ""
    if is_gen_this:
        status_html = '<span class="status-gen">⚡ กำลังร่าง</span>'
    elif has_content:
        status_html = '<span class="status-done">✓ มีเนื้อหา</span>'

    st.markdown(f"""
    <div class="{card_cls}">
      <div class="tor-card-header">
        <div class="{num_cls}">{i:02d}</div>
        <div class="tor-title-text">ข้อ {i} &nbsp;{TOR_TITLES[i]}</div>
        {status_html}
      </div>
    </div>""", unsafe_allow_html=True)

    with st.expander("", expanded=is_gen_this or (i == 4 and has_content)):

        if is_gen_this:
            stream_box = st.empty()
            stream_box.markdown('<div class="stream-container">_⚡ กำลังร่างเนื้อหา..._</div>', unsafe_allow_html=True)

            proj_ctx = (
                f"โครงการ: {p_name}, หน่วยงาน: {p_agency}, "
                f"งบประมาณ: {p_budget:,} บาท, เกณฑ์: {p_criteria}"
            )
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
                st.markdown(
                    '<small style="color:#059669;font-weight:600;">✓ ซิงค์สเปค Gemini แล้ว</small>',
                    unsafe_allow_html=True
                )

            col_btn, _ = st.columns([1, 3])
            with col_btn:
                if st.button(
                    f"🔄 รีเจนข้อ {i}", key=f"btn_regen_{i}",
                    disabled=is_busy, type="secondary"
                ):
                    if not p_name:
                        st.markdown('<div class="error-box">กรุณาระบุชื่อโครงการก่อน</div>', unsafe_allow_html=True)
                    else:
                        st.session_state.gen_error = None
                        st.session_state.generating_section = i
                        st.rerun()

st.write("")

# ── ปุ่มรันทั้งหมด ────────────────────────────────────────────────
col_run, col_clear = st.columns([3, 1])
with col_run:
    if st.button(
        "✨ ให้ Typhoon ร่างทุกข้อที่ยังว่างพร้อมกัน",
        type="primary", use_container_width=True, disabled=is_busy
    ):
        if not p_name:
            st.markdown('<div class="error-box">⚠️ กรุณาระบุชื่อโครงการก่อน</div>', unsafe_allow_html=True)
        else:
            st.session_state.meta_data = {
                "title": p_name, "agency": p_agency,
                "budget": p_budget, "criteria": p_criteria
            }
            queue = [i for i in range(1, 11) if not st.session_state.tor_sections[i].strip()]
            if not queue:
                st.markdown(
                    '<div class="info-box">ทุกข้อมีเนื้อหาแล้ว หากต้องการ re-gen ให้กด "ล้างทั้งหมด" ก่อน</div>',
                    unsafe_allow_html=True
                )
            else:
                st.session_state.gen_error = None
                first = queue.pop(0)
                st.session_state.generate_all_queue = queue
                st.session_state.generating_section = first
                st.rerun()

with col_clear:
    if st.button("🗑️ ล้างทั้งหมด", use_container_width=True, disabled=is_busy, type="secondary"):
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
        st.session_state.meta_data = {
            "title": p_name or "ไม่ได้ระบุ", "agency": p_agency,
            "budget": p_budget, "criteria": p_criteria
        }

    st.markdown('<div class="export-section">', unsafe_allow_html=True)
    st.markdown("""
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:18px;">
      <span style="font-size:1.4rem;">📥</span>
      <div>
        <div class="export-title">ส่งออกเอกสาร TOR</div>
        <div class="export-sub">เลือกรูปแบบที่ต้องการดาวน์โหลด</div>
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
            "📝 Word Document (.DOCX)",
            data=word_bytes,
            file_name=f"{fname_base}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
            help="ฟอนต์ไทยครบถ้วน พร้อมใช้งานทันที"
        )
    with dc2:
        st.download_button(
            "📄 ข้อความธรรมดา (.TXT)",
            data=all_txt,
            file_name=f"{fname_base}.txt",
            mime="text/plain",
            use_container_width=True,
            help="เปิดได้ทุก Text Editor"
        )
    with dc3:
        st.download_button(
            "🖨️ พิมพ์เป็น PDF (.HTML)",
            data=html_bytes,
            file_name=f"{fname_base}_Print.html",
            mime="text/html",
            use_container_width=True,
            help="เปิดในเบราว์เซอร์แล้วกด Ctrl+P → Save as PDF"
        )
    st.markdown('</div>', unsafe_allow_html=True)
