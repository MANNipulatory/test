import streamlit as st
import os
import io
import re
import time
from google import genai
from google.genai import types
from google.genai.errors import APIError as GeminiAPIError
from openai import OpenAI
import pypdf
from docx import Document

# ── 1. INITIALIZATION (HYBRID CREW) ──────────────────────────────
if "GEMINI_API_KEY" in st.secrets and st.secrets["GEMINI_API_KEY"]:
    gemini_client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
elif os.environ.get("GEMINI_API_KEY"):
    gemini_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
else:
    gemini_client = None

GEMINI_MODEL = "gemini-2.5-flash"

if "TYPHOON_API_KEY" in st.secrets and st.secrets["TYPHOON_API_KEY"]:
    typhoon_key = st.secrets["TYPHOON_API_KEY"]
elif os.environ.get("TYPHOON_API_KEY"):
    typhoon_key = os.environ.get("TYPHOON_API_KEY")
else:
    typhoon_key = None

if typhoon_key:
    typhoon_client = OpenAI(api_key=typhoon_key, base_url="https://api.opentyphoon.ai/v1")
else:
    typhoon_client = None

TYPHOON_MODEL = "typhoon-v2.5-30b-a3b-instruct"

st.set_page_config(
    page_title="AI Procurement TOR Workspace",
    page_icon="🛡️",
    layout="wide"
)

# 🎨 [ELEVATED MINIMALISM DESIGN]
st.markdown("""
    <style>
        .block-container { max-width: 1000px !important; padding-top: 2.5rem !important; padding-bottom: 5rem !important; }
        h2 { font-size: 1.3rem !important; font-weight: 700 !important; color: #1E3A8A; margin-top: 2.5rem !important; margin-bottom: 1.2rem !important; padding-left: 12px !important; border-left: 4px solid #3B82F6 !important; }
        .stTextArea textarea { background-color: rgba(128, 128, 128, 0.06) !important; border: 1px solid rgba(128, 128, 128, 0.2) !important; border-radius: 8px !important; padding: 12px !important; font-size: 0.95rem !important; }
        .stTextArea textarea:focus { border-color: #3B82F6 !important; background-color: transparent !important; box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15) !important; }
        .stTextInput input { background-color: rgba(128, 128, 128, 0.06) !important; border: 1px solid rgba(128, 128, 128, 0.2) !important; border-radius: 8px !important; }
        .streamlit-expanderHeader { background-color: rgba(128, 128, 128, 0.04) !important; border: 1px solid rgba(128, 128, 128, 0.15) !important; border-radius: 8px !important; font-weight: 600 !important; }
        .stButton button { border-radius: 6px !important; font-size: 0.9rem !important; font-weight: 500 !important; }
        .stButton div button[data-testid="baseButton-primary"] { background: linear-gradient(135deg, #2563EB, #1D4ED8) !important; color: #FFFFFF !important; border: none !important; box-shadow: 0 4px 6px rgba(37, 99, 235, 0.2) !important; }
        
        .export-box {
            background-color: rgba(59, 130, 246, 0.04) !important;
            border: 1px dashed rgba(59, 130, 246, 0.3) !important;
            border-radius: 12px !important;
            padding: 20px !important;
            margin-top: 30px;
        }
        .token-saving-banner {
            background-color: rgba(16, 185, 129, 0.1) !important;
            border: 1px solid rgba(16, 185, 129, 0.3) !important;
            padding: 12px !important;
            border-radius: 8px !important;
            color: #047857 !important;
            font-size: 0.9rem !important;
            margin-bottom: 15px;
            font-weight: 500;
        }
    </style>
""", unsafe_allow_html=True)

TOR_TITLES = {
    1: "ความเป็นมา", 2: "วัตถุประสงค์", 3: "คุณสมบัติผู้ยื่นข้อเสนอ",
    4: "แบบรูปรายการ หรือคุณลักษณะเฉพาะของพัสดุ", 5: "ระยะเวลาดำเนินการ",
    6: "ระยะเวลาส่งมอบงาน หรือส่งมอบพัสดุ", 7: "หลักเกณฑ์ในการพิจารณาคัดเลือกข้อเสนอ",
    8: "อัตราค่าปรับ", 9: "การรับประกันความชำรุดบกพร่อง", 10: "ข้อสงวนสิทธิ์ในการยื่นข้อเสนอและอื่นๆ"
}

SYSTEM_PROMPT = (
    "คุณคือผู้เชี่ยวชาญระดับสูงด้านการจัดซื้อจัดจ้างภาครัฐไทย "
    "หน้าที่ของคุณคือเขียนเนื้อหาขอบเขตของงาน (TOR) ตามมาตรฐานหนังสือเวียน กค (กวจ) 0405.4/ว 159 ของกรมบัญชีกลาง "
    "จงเขียนอธิบายอย่างละเอียด ถี่ถ้วน ครอบคลุมทุกมิติทางกฎหมายพัสดุ ใช้ภาษาราชการไทยที่เป็นทางการอย่างสมบูรณ์ "
    "ห้ามระบุยี่ห้อหรือรุ่นของสินค้าโดยตรงเด็ดขาด ให้ใช้คุณลักษณะเชิงฟังก์ชัน (Functional Specification) เสมอ "
    "ใช้ตัวเลขอารบิกในการรันข้อย่อย ห้ามใช้เลขไทยในทุกกรณี "
    "ห้ามแปลเนื้อหาเป็นภาษาอังกฤษล้วน ให้ตอบเป็นภาษาไทยอย่างเป็นทางการเท่านั้น"
)

# ── 2. STATE MANAGEMENT ──────────────────────────────────────────
if "tor_sections" not in st.session_state: st.session_state.tor_sections = {i: "" for i in range(1, 11)}
if "meta_data" not in st.session_state: st.session_state.meta_data = {}
if "pdf_pre_cleaned_texts" not in st.session_state: st.session_state.pdf_pre_cleaned_texts = {}
if "ai_drafted_spec_v4" not in st.session_state: st.session_state.ai_drafted_spec_v4 = ""

# ── 3. HELPERS & GENERATORS ──────────────────────────────────────
def call_gemini_with_retry(func, *args, **kwargs):
    max_retries = 3
    for attempt in range(max_retries):
        try: return func(*args, **kwargs)
        except GeminiAPIError as e:
            if e.code in [429, 503]: time.sleep(5); continue
            raise e

def call_typhoon_with_retry(func, *args, **kwargs):
    max_retries = 5
    for attempt in range(max_retries):
        try: return func(*args, **kwargs)
        except Exception as e:
            err_msg = str(e).lower()
            if any(k in err_msg for k in ["rate_limit", "429", "503", "overloaded"]):
                time.sleep(15); continue
            raise e

def extract_text_from_pdf(uploaded_file):
    try:
        pdf_reader = pypdf.PdfReader(uploaded_file)
        return "".join([page.extract_text() or "" for page in pdf_reader.pages])
    except Exception as e: return ""

def local_regex_cleaner(text):
    if not text: return ""
    text = re.sub(r'\b\d{2,3}-\d{3}-\d{4}\b|\b\d{2,3}-\d{4}-\d{4}\b|\b\d{9,10}\b', "[PHONE_HIDDEN]", text)
    text = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', "[EMAIL_HIDDEN]", text)
    text = re.sub(r'https?://[^\s<>"]+|www\.[^\s<>"]+', "[URL_HIDDEN]", text)
    text = re.sub(r'(บริษัท\s+[^\s\n]+?\s+จำกัด(?:\s*\(มหาชน\))?)|(ห้างหุ้นส่วนจำกัด\s+[^\s\n]+)', "[COMPANY_HIDDEN]", text)
    en_company = r'\b[A-Za-z0-9\s\.,&\-\(\)]+?\s+(?:Co\s*\.?\s*,?\s*Ltd\s*\.?|Company\s+Limited|Inc\s*\.?|Corp\s*\.?|LLC|Group)\b'
    text = re.sub(en_company, "[COMPANY_HIDDEN]", text, flags=re.IGNORECASE)
    text = re.sub(r'\b(Intel|AMD|NVIDIA|GeForce|Asus|Acer|HP|Dell|Lenovo|Apple|Microsoft|Cisco|Huawei)\b', "[BRAND_HIDDEN]", text, flags=re.IGNORECASE)
    return text

def summarize_single_file_with_gemini(cleaned_text):
    if not gemini_client or not cleaned_text: return cleaned_text
    prompt = f"""
    จงสกัดเฉพาะ 'ข้อมูลข้อกำหนดคุณลักษณะเฉพาะทางเทคนิค' และ 'เงื่อนไขการสนับสนุน/การรับประกัน' จากเอกสารที่ผ่านการคลีนแบรนด์มาแล้วด้านล่างนี้
    สรุปให้กระชับและสั้นที่สุดโดยรักษาข้อมูลตัวเลขทางเทคนิคไว้ครบถ้วน ห้ามเอาเนื้อหาน้ำท่วมทุ่ง เพื่อประหยัดพื้นที่กระดาษ:
    
    [เนื้อหาเอกสาร]:
    {cleaned_text[:12000]}
    """
    try:
        response = call_gemini_with_retry(
            gemini_client.models.generate_content, model=GEMINI_MODEL, contents=prompt,
            config=types.GenerateContentConfig(temperature=0.1)
        )
        # ✅ จุดแก้ไขที่ 1: ดักจับโครงสร้างข้อมูลจาก SDK ตัวใหม่
        if hasattr(response, 'text') and response.text:
            return response.text
        elif hasattr(response, 'candidates') and response.candidates:
            return response.candidates[0].content.parts[0].text
        return "ไม่สามารถสกัดข้อมูลสเปคได้"
    except Exception: 
        return cleaned_text[:2000]

def generate_typhoon_stream(prompt_text, section_num, placeholder):
    if not typhoon_client: return ""
    full_response = ""
    try:
        response_stream = call_typhoon_with_retry(
            typhoon_client.chat.completions.create,
            model=TYPHOON_MODEL,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt_text}],
            temperature=0.4, stream=True
        )
        for chunk in response_stream:
            # ใช้การตรวจสอบ attr ที่ปลอดภัยขึ้น
            delta = chunk.choices[0].delta
            if hasattr(delta, 'content') and delta.content:
                full_response += delta.content
                placeholder.code(full_response + "▌", language="text")
        
        # บันทึกข้อมูลที่เจนเสร็จลงใน state หลักที่ UI อ้างอิง
        st.session_state.tor_sections[section_num] = full_response
        placeholder.empty()
        
        # สั่ง Rerun เพื่อให้ text_area แสดงเนื้อหาใหม่ทันที
        st.rerun()
        return full_response
    except Exception as e: 
        st.error(f"Error: {e}")
        return ""
# 📄 [EXPORT GENERATORS] 
def build_word_document():
    doc = Document()
    title_p = doc.add_paragraph()
    title_run = title_p.add_run(f"ร่างขอบเขตของงาน (TOR)\nโครงการ: {st.session_state.meta_data.get('title', 'ไม่ได้ระบุ')}")
    title_run.bold = True
    title_run.font.size = 203200
    
    doc.add_paragraph(f"หน่วยงานเจ้าของโครงการ: {st.session_state.meta_data.get('agency', '-')}")
    doc.add_paragraph(f"วงเงินงบประมาณ: {st.session_state.meta_data.get('budget', 0):,} บาท")
    doc.add_paragraph("-" * 40)
    
    for idx in range(1, 11):
        heading = doc.add_paragraph()
        h_run = heading.add_run(f"ข้อ {idx} {TOR_TITLES[idx]}")
        h_run.bold = True
        
        content = st.session_state.tor_sections.get(idx, "ไม่มีเนื้อหา")
        doc.add_paragraph(content)
        doc.add_paragraph()
        
    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()

def build_pdf_html_document():
    html_content = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: 'Sarabun', 'Tahama', sans-serif; padding: 40px; color: #333; line-height: 1.6; }}
            h1 {{ text-align: center; font-size: 22px; margin-bottom: 5px; }}
            .meta {{ text-align: center; font-size: 14px; color: #555; margin-bottom: 30px; }}
            .section {{ margin-bottom: 25px; page-break-inside: avoid; }}
            .title {{ font-weight: bold; font-size: 16px; color: #1E3A8A; border-bottom: 1px solid #ddd; padding-bottom: 5px; margin-bottom: 10px; }}
            .content {{ font-size: 14px; white-space: pre-wrap; text-align: justify; }}
        </style>
    </head>
    <body>
        <h1>ร่างขอบเขตของงาน (TOR)</h1>
        <div class="meta">
            <b>โครงการ:</b> {st.session_state.meta_data.get('title', '-')}<br>
            <b>หน่วยงาน:</b> {st.session_state.meta_data.get('agency', '-') or 'ไม่ได้ระบุ'} | 
            <b>งบประมาณ:</b> {st.session_state.meta_data.get('budget', 0):,} บาท
        </div>
    </body>
    </html>
    """
    for idx in range(1, 11):
        text_inside = st.session_state.tor_sections.get(idx, "").replace("\n", "<br>")
        html_content = html_content.replace("</body>", f"""
        <div class="section">
            <div class="title">ข้อ {idx} {TOR_TITLES[idx]}</div>
            <div class="content">{text_inside}</div>
        </div>
        </body>""")
    return html_content

# ── 4. UI WORKFLOW ───────────────────────────────────────────────
st.title("🛡️ AI Procurement TOR Workspace")
st.caption("⚡ Hybrid Core Mode: วิเคราะห์ด้วย Gemini ➔ ร่างข้อกำหนดภาษาราชการเนียนตาด้วย Typhoon")

st.markdown("## 1. ข้อมูลโครงการทั่วไป")
col_form1, col_form2 = st.columns(2)
with col_form1:
    p_name = st.text_input("ชื่อโครงการ / งานจัดซื้อจัดจ้าง *", placeholder="ระบุชื่อโครงการ...")
    p_agency = st.text_input("หน่วยงาน / ส่วนราชการ", placeholder="ระบุหน่วยงานผู้รับผิดชอบ...")
with col_form2:
    p_budget = st.number_input("วงเงินงบประมาณ (บาท) *", min_value=0, step=5000, value=0)
    p_criteria = st.radio("หลักเกณฑ์การคัดเลือกข้อเสนอ", ["เกณฑ์ราคา", "เกณฑ์ราคาประกอบเกณฑ์อื่น"], horizontal=True)

st.markdown("## 2. ขั้นตอนสกัดสเปคอ้างอิงและคัดกรองความโปร่งใส (ประหยัด Token)")
job_description_pdf = st.text_area("วัตถุประสงค์ / ลักษณะงานที่ต้องการใช้งานจริง:", placeholder="อธิบายเป้าหมายการใช้งานจริงเพื่อนำทาง AI...", height=80)

col_file1, col_file2 = st.columns([3, 1])
with col_file1:
    uploaded_files = st.file_uploader("อัปโหลดไฟล์ PDF อ้างอิงจากคู่ค้าหลายๆ ราย", type=["pdf"], accept_multiple_files=True, label_visibility="collapsed")
with col_file2:
    pre_clean_click = st.button("✂️ ใช้ Regex ตัดและคลีนข้อมูลด่วนก่อน", use_container_width=True)

if uploaded_files and pre_clean_click:
    st.session_state.pdf_pre_cleaned_texts = {}
    with st.spinner("⚡ ระบบกำลังใช้ Regex สับกรองคำล็อกสเปคบนเครื่องให้อย่างรวดเร็ว..."):
        for file in uploaded_files:
            raw_text = extract_text_from_pdf(file)
            cleaned_by_regex = local_regex_cleaner(raw_text)
            st.session_state.pdf_pre_cleaned_texts[file.name] = cleaned_by_regex

if st.session_state.pdf_pre_cleaned_texts:
    st.markdown("<div class='token-saving-banner'>💡 ขั้นตอนประหยัด Token: โปรดตรวจสอบและลบชื่อบริษัทหรือข้อมูลล็อกสเปคที่ยังตกค้างในกล่องข้อความด้านล่างนี้แยกตามไฟล์ ก่อนกดส่งไปสรุปด้วย AI</div>", unsafe_allow_html=True)
    
    for file_name, text_content in list(st.session_state.pdf_pre_cleaned_texts.items()):
        with st.expander(f"📁 ดักกรองเนื้อหาไฟล์: {file_name}", expanded=True):
            user_verified_text = st.text_area(
                "พี่สามารถพิมพ์ลบหรือแก้ไขเนื้อหาข้อความตรงนี้เพิ่มเติมได้โดยตรง:",
                value=text_content,
                height=180,
                key=f"user_verify_box_{file_name}"
            )
            st.session_state.pdf_pre_cleaned_texts[file_name] = user_verified_text
            
    st.write("")
    check_confirmation = st.checkbox("ข้าพเจ้ายืนยันว่าได้ทำการตรวจสอบ/ลบรายชื่อแบรนด์ที่ตกค้างเสร็จสิ้นแล้ว และต้องการให้ Gemini เริ่มสกัดสเปค")
    
    if st.button("🚀 ส่งข้อมูลที่ผ่านการกรองแล้วไปสกัดสเปคด้วย Gemini แยกไฟล์", type="primary", use_container_width=True):
        if not job_description_pdf: st.warning("⚠️ โปรดระบุวัตถุประสงค์ลักษณะงานก่อน")
        elif not check_confirmation: st.error("⚠️ โปรดคลิกกล่องยืนยันการตรวจสอบความโปร่งใสด้านบนก่อนครับ")
        else:
            final_summarized_list = []
            progress_bar = st.progress(0)
            
            for idx, (file_name, verified_text) in enumerate(st.session_state.pdf_pre_cleaned_texts.items()):
                st.toast(f"🤖 Gemini กำลังสกัดโครงสร้างข้อมูลไฟล์ที่ {idx+1}...")
                single_summary = summarize_single_file_with_gemini(verified_text)
                final_summarized_list.append(f"\n[ร่างสเปคกลางสกัดจากไฟล์ {idx+1}]:\n{single_summary}\n")
                progress_bar.progress((idx + 1) / len(st.session_state.pdf_pre_cleaned_texts))
                
            with st.spinner("⚙️ กำลังนำสเปคทั้งหมดที่คัดกรองแล้ว ผนวกรวมเข้าสู่ข้อ 4 ของข้อกำหนด TOR..."):
                try:
                    all_merged_specs = "".join(final_summarized_list)
                    prompt_merge = f"สรุปและเรียบเรียงข้อกำหนดคุณลักษณะเฉพาะทางเทคนิคเพื่อใส่ใน TOR ข้อ 4 วัตถุประสงค์คือ {job_description_pdf} ข้อมูลสเปคทั้งหมดคือ: {all_merged_specs} เขียนแบ่งหมวดหมู่ย่อย 4.1, 4.2 อย่างเป็นระเบียบ ห้ามมีชื่อคู่ค้าหรือแบรนด์ใดๆ หลงเหลือ"
                    
                    response = call_gemini_with_retry(gemini_client.models.generate_content, model=GEMINI_MODEL, contents=prompt_merge)
                    
                    # ✅ จุดแก้ไขที่ 2: แก้ไขโครงสร้างการดึงข้อความจุดรวมร่างข้อ 4 (บรรทัด 303 เดิม) เพื่อกันแอปแครช
                    final_text = ""
                    if hasattr(response, 'text') and response.text:
                        final_text = response.text
                    elif hasattr(response, 'candidates') and response.candidates:
                        final_text = response.candidates[0].content.parts[0].text
                        
                    st.session_state.ai_drafted_spec_v4 = final_text
                    st.session_state.tor_sections[4] = final_text
                    st.success("🎉 ซิงค์สเปคที่สกัดแบบประหยัด Token เข้าสู่ร่างข้อ 4 เรียบร้อยแล้ว! พี่สามารถเลื่อนลงไปดูได้ที่ข้อ 4 ด้านล่างครับ")
                    st.rerun()
                except Exception as e: 
                    st.error(f"เกิดข้อผิดพลาดในการรวบรวมเนื้อหา: {e}")

# 📝 ส่วนที่ 3: ใช้ Typhoon ร่างเนื้อหา 10 ข้อหลัก
st.markdown("## 3. จัดการขอบเขตงาน TOR 10 ข้อหลัก")
if p_name: st.caption(f"📍 โครงการปัจจุบัน: **{p_name}** | งบประมาณ: **{p_budget:,} บาท**")

for i in range(1, 11):
    with st.expander(f"📌 ข้อ {i}: {TOR_TITLES[i]}", expanded=(i==4)):
        current_content = st.session_state.tor_sections.get(i, "")
        if i == 4 and st.session_state.ai_drafted_spec_v4:
            st.markdown("<small style='color:#10B981; font-weight:600;'>✓ ซิงค์ข้อมูลโครงสร้างสเปคทางเทคนิคที่ผ่านการตรวจสอบโดยสมบูรณ์แล้ว</small>", unsafe_allow_html=True)
            
        updated_content = st.text_area(f"เนื้อหาข้อ {i}", value=current_content, height=160, key=f"main_edit_sec_{i}", label_visibility="collapsed")
        st.session_state.tor_sections[i] = updated_content
        
        col_space, col_action = st.columns([5, 1.2])
        with col_action:
            if st.button(f"🔄 รีเจนเนื้อหาข้อ {i}", key=f"main_regen_btn_{i}", use_container_width=True):
                if not p_name: st.error("กรุณาระบุชื่อโครงการก่อน")
                else:
                    box_placeholder = st.empty()
                    spec_prompt = f"จงเขียนทบทวนร่างข้อกำหนดขอบเขตงาน TOR โครงการ '{p_name}' เฉพาะในส่วนของ 'ข้อ {i} หัวข้อ: {TOR_TITLES[i]}' ให้ออกมาเป็นข้อๆ ภาษาราชการเต็มรูปแบบ งบประมาณคือ {p_budget} บาท"
                    generate_typhoon_stream(spec_prompt, i, box_placeholder)
                    st.rerun()

st.write("")
if st.button("✨ ให้ Typhoon เริ่มร่างข้อกำหนดส่วนที่เหลือพร้อมกันทั้งหมด", type="primary", use_container_width=True):
    if not p_name: st.error("⚠️ กรุณาระบุชื่อโครงการที่ด้านบนสุดก่อนรันงาน")
    else:
        st.session_state.meta_data = {"title": p_name, "agency": p_agency, "type": "ซื้อ/จ้างทั่วไป", "budget": p_budget, "criteria": p_criteria}
        for i in range(1, 11):
            if i == 4 and st.session_state.tor_sections[4]: continue
            st.toast(f"Typhoon กำลังร่างเรียบเรียงข้อ {i}...")
            box_placeholder = st.empty()
            proj_context = f"โครงการ: {p_name}, หน่วยงาน: {p_agency}, งบประมาณ: {p_budget} บาท, เกณฑ์พิจารณา: {p_criteria}"
            specific_prompt = f"จงเขียนเนื้อหาของขอบเขตของงาน (TOR) ตามมาตรฐานราชการไทย ว.159 เฉพาะ 'ข้อ {i} หัวข้อ: {TOR_TITLES[i]}' ของ{proj_context} อธิบายรายละเอียดเชิงระเบียบพัสดุให้ครบถ้วนและสละสลวยที่สุด"
            generate_typhoon_stream(specific_prompt, i, box_placeholder)
            time.sleep(2.0)
        st.balloons()

# ── 5. EXPORT HUB (ศูนย์ดาวน์โหลด 3 รูปแบบ) ───────────────────────
if st.session_state.tor_sections[1] or st.session_state.tor_sections[4]:
    if not st.session_state.meta_data:
        st.session_state.meta_data = {"title": p_name or "ไม่ได้ระบุชื่อ", "agency": p_agency, "budget": p_budget, "criteria": p_criteria}
        
    st.markdown("<div class='export-box'>", unsafe_allow_html=True)
    st.markdown("### 📥 ศูนย์ส่งออกเอกสาร TOR (Export Hub)")
    st.caption("เลือกดาวน์โหลดไฟล์ขอบเขตงานในรูปแบบที่ต้องการไปใช้งานต่อ")
    
    all_text_export = f"ร่างขอบเขตของงาน (TOR) - {st.session_state.meta_data['title']}\n\n"
    for idx, ct in st.session_state.tor_sections.items():
        all_text_export += f"ข้อ {idx} {TOR_TITLES[idx]}\n{ct}\n\n"
        
    word_bytes = build_word_document()
    html_printable = build_pdf_html_document()
    
    dl_col1, dl_col2, dl_col3 = st.columns(3)
    
    with dl_col1:
        st.download_button(
            label="📝 ดาวน์โหลดไฟล์ Word (.DOCX)",
            data=word_bytes,
            file_name=f"TOR_{p_name or 'Project'}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True
        )
    with dl_col2:
        st.download_button(
            label="📄 ดาวน์โหลดไฟล์ข้อความ (.TXT)",
            data=all_text_export,
            file_name=f"TOR_{p_name or 'Project'}.txt",
            mime="text/plain",
            use_container_width=True
        )
    with dl_col3:
        st.download_button(
            label="🖨️ เปิดพิมพ์ / บันทึกเป็น PDF",
            data=html_printable,
            file_name=f"TOR_Print_Preview_{p_name or 'Project'}.html",
            mime="text/html",
            use_container_width=True,
            help="ดาวน์โหลดไฟล์พรีวิวนี้แล้วเปิดใน Chrome/Edge จากนั้นกด Ctrl+P เพื่อบันทึกเป็น PDF ที่ฟอนต์ไม่พังครับ"
        )
    st.markdown("</div>", unsafe_allow_html=True)
