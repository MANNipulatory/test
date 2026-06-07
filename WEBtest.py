import streamlit as st
import os
import io
import re
import time
from google import genai
from google.genai import types
import pypdf

# ── 1. CONFIGURATION & INITIALIZATION ────────────────────────────
if "GEMINI_API_KEY" in st.secrets and st.secrets["GEMINI_API_KEY"]:
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
elif os.environ.get("GEMINI_API_KEY"):
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
else:
    client = None

MODEL_NAME = "gemini-2.5-flash"

st.set_page_config(
    page_title="🛡️ AI Procurement TOR Space",
    page_icon="🛡️",
    layout="wide"
)

# 🔥 [DESIGN UPDATE] ปรับแต่ง CSS ใหม่หมดจด: สวยเฉียบ กะทัดรัด รองรับ Dark/Light Theme สมบูรณ์แบบ
st.markdown("""
    <style>
        /* จำกัดความกว้างเนื้อหาหลักไม่ให้แผ่กระจายเต็มจอเกินไปจนเทอะทะ */
        .block-container {
            max-width: 1100px !important;
            padding-top: 1.5rem !important;
            padding-bottom: 3rem !important;
        }
        
        /* ปรับสไตล์หัวข้อ */
        h1 {
            font-size: 1.8rem !important;
            font-weight: 700 !important;
            margin-bottom: 0.1rem !important;
        }
        h2 {
            font-size: 1.25rem !important;
            font-weight: 600 !important;
            margin-top: 1.5rem !important;
            margin-bottom: 0.8rem !important;
            padding-bottom: 4px;
            border-bottom: 1px solid rgba(128, 128, 128, 0.2);
        }
        
        /* ปรับดีไซน์การจัดกลุ่ม Layout (รองรับ Dark Theme อัตโนมัติด้วยการใช้สีโปร่งแสง) */
        .step-card {
            background-color: rgba(128, 128, 128, 0.04);
            border: 1px solid rgba(128, 128, 128, 0.15);
            padding: 1.1rem;
            border-radius: 8px;
            margin-bottom: 1.2rem;
        }
        
        /* ปรับแต่งความกะทัดรัดของกล่องข้อความ Textarea */
        .stTextArea textarea {
            border-radius: 6px !important;
            border: 1px solid rgba(128, 128, 128, 0.25) !important;
            padding: 8px 12px !important;
            font-size: 0.95rem !important;
        }
        
        /* ปรับปรุงหน้าตาปุ่มกดให้ดูโมเดิร์น ไม่หนา */
        .stButton button {
            border-radius: 6px !important;
            padding: 0.35rem 1rem !important;
            font-weight: 500 !important;
            font-size: 0.9rem !important;
        }
        
        /* ลูกเล่นกรอบ Expander (ข้อ 1-10) ให้ดูเป็น Card มินิมอล */
        .streamlit-expanderHeader {
            border: 1px solid rgba(128, 128, 128, 0.12) !important;
            border-radius: 6px !important;
            padding: 8px 12px !important;
            font-size: 0.95rem !important;
        }
        .streamlit-expanderContent {
            border-left: 1px solid rgba(128, 128, 128, 0.12) !important;
            border-right: 1px solid rgba(128, 128, 128, 0.12) !important;
            border-bottom: 1px solid rgba(128, 128, 128, 0.12) !important;
            border-bottom-left-radius: 6px;
            border-bottom-right-radius: 6px;
            padding: 10px !important;
        }
    </style>
""", unsafe_allow_html=True)

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
    "ใช้ตัวเลขอารบิกในการรันข้อย่อย (เช่น 1., 2., 3.) ห้ามใช้เลขไทยในทุกกรณี "
    "ห้ามแปลเนื้อหาเป็นภาษาอังกฤษล้วน ให้ตอบเป็นภาษาไทยอย่างเป็นทางการเท่านั้น"
)

# ── 2. STATE MANAGEMENT ──────────────────────────────────────────
if "tor_sections" not in st.session_state:
    st.session_state.tor_sections = {i: "" for i in range(1, 11)}
if "meta_data" not in st.session_state:
    st.session_state.meta_data = {}
if "pdf_extracted_texts" not in st.session_state:
    st.session_state.pdf_extracted_texts = {}
if "ai_drafted_spec_v4" not in st.session_state:
    st.session_state.ai_drafted_spec_v4 = ""

# ── 3. HELPER FUNCTIONS ──────────────────────────────────────────
def extract_text_from_pdf(uploaded_file):
    try:
        pdf_reader = pypdf.PdfReader(uploaded_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() or ""
        return text
    except Exception as e:
        st.error(f"ไม่สามารถอ่านไฟล์ {uploaded_file.name} ได้: {e}")
        return ""

def clean_redundant_info(text):
    if not text:
        return ""
    text = re.sub(r'\b\d{2,3}-\d{3}-\d{4}\b|\b\d{2,3}-\d{4}-\d{4}\b|\b\d{9,10}\b', "[PHONE_HIDDEN]", text)
    text = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', "[EMAIL_HIDDEN]", text)
    text = re.sub(r'https?://[^\s<>"]+|www\.[^\s<>"]+', "[URL_HIDDEN]", text)
    text = re.sub(r'(บริษัท\s+[^\s\n]+ coars\s+จำกัด(?:\s*\(มหาชน\))?)|(ห้างหุ้นส่วนจำกัด\s+[^\s\n]+)|(\bหจก\s*\.\s*[^\s\n]+)|(\bบมจ\s*\.\s*[^\s\n]+)|(\bบจก\s*\.\s*[^\s\n]+)', "[COMPANY_HIDDEN]", text)
    text = re.sub(r'บริษัท\s+([A-Za-z0-9เ-แ🏡ก-ฮ\s\.\-\(\)]+?)(?=\s*(?:เสนอ|ราคา|จำกัด|ติดต่อ|\n|$))', "[COMPANY_HIDDEN]", text)
    en_company_pattern = r'\b[A-Za-z0-9\s\.,&\-\(\)]+?\s+(?:Co\s*\.?\s*,?\s*Ltd\s*\.?|Company\s+Limited|Inc\s*\.?|Corp\s*\.?|Corporation|LLC|Pty\s+Ltd|Group)\b'
    text = re.sub(en_company_pattern, "[COMPANY_HIDDEN]", text, flags=re.IGNORECASE)
    text = re.sub(r'\b(Intel|AMD|NVIDIA|GeForce|Asus|Acer|HP|Dell|Lenovo|Apple|Microsoft|Cisco|Huawei)\b', "[BRAND_HIDDEN]", text, flags=re.IGNORECASE)
    text = re.sub(r'(ผู้ยื่นข้อเสนอ:|เสนอโดย:|โดยบริษัท)\s*\[COMPANY_HIDDEN\]', "[COMPANY_HIDDEN]", text)
    return text

def summarize_single_pdf_spec(raw_text):
    if not client or not raw_text:
        return raw_text
    prompt = f"""
    คุณคือผู้ช่วยสกัดข้อมูลทางเทคนิค อ่านข้อความด้านล่างนี้แล้วสรุปเนื้อหาสำคัญเกี่ยวกับ 'รายละเอียดคุณลักษณะเฉพาะทางเทคนิคทั้งหมด' 
    และ 'เงื่อนไขการรับประกันและการสนับสนุน' โดยรักษาข้อมูลตัวเลขสเปคทางเทคนิคไว้ให้ครบถ้วนที่สุด แต่ตัดพวกเศษขยะหรือชื่อคู่ค้าออก
    [ข้อมูลเอกสาร]:
    {raw_text[:8000]}
    """
    try:
        response = client.models.generate_content(model=MODEL_NAME, contents=prompt, config=types.GenerateContentConfig(temperature=0.2))
        return response.text
    except Exception as e:
        return raw_text[:3000]

def generate_section_stream(prompt_text, section_num, placeholder):
    if not client: return ""
    full_response = ""
    try:
        response_stream = client.models.generate_content_stream(
            model=MODEL_NAME, contents=prompt_text,
            config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT, temperature=0.5, max_output_tokens=3000)
        )
        for chunk in response_stream:
            if chunk.text:
                full_response += chunk.text
                placeholder.code(full_response + "▌", language="text")
        placeholder.code(full_response, language="text")
        st.session_state.tor_sections[section_num] = full_response
        return full_response
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดข้อ {section_num}: {e}")
        return ""

def create_docx(title, agency, project_type, budget, criteria, sections):
    try:
        from docx import Document; from docx.shared import Pt, Cm; from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml.ns import qn; from docx.oxml import OxmlElement
    except ImportError: return None
    doc = Document(); sec = doc.sections[0]
    sec.page_width = Cm(21); sec.page_height = Cm(29.7)
    sec.left_margin = Cm(3); sec.right_margin = Cm(2); sec.top_margin = Cm(2.5); sec.bottom_margin = Cm(2.5)
    FONT = "TH Sarabun New"
    def set_font(run, size=16, bold=False):
        run.bold = bold; run.font.size = Pt(size)
        rPr = run._element.get_or_add_rPr()
        rFonts = rPr.find(qn('w:rFonts'))
        if rFonts is None: rFonts = OxmlElement('w:rFonts'); rPr.insert(0, rFonts)
        for attr in ('w:ascii', 'w:hAnsi', 'w:cs', 'w:eastAsia'): rFonts.set(qn(attr), FONT)
    
    p = doc.add_paragraph()
    run = p.add_run("ร่างขอบเขตของงาน (Terms of Reference)"); set_font(run, 20, True); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p = doc.add_paragraph()
    run = p.add_run(title); set_font(run, 18, True); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    meta = [("หน่วยงาน", agency), ("ประเภทงาน", project_type), ("งบประมาณ", f"{budget:,} บาท" if budget else "-"), ("หลักเกณฑ์", criteria)]
    for label, value in meta:
        if value:
            p = doc.add_paragraph()
            r1 = p.add_run(f"{label}: "); set_font(r1, 16, True)
            r2 = p.add_run(str(value)); set_font(r2, 16, False)

    for num, content in sections.items():
        p = doc.add_paragraph()
        r = p.add_run(f"ข้อ {num} {TOR_TITLES[num]}"); set_font(r, 16, True)
        for line in content.strip().split("\n"):
            if not line.strip(): continue
            p = doc.add_paragraph(); p.paragraph_format.left_indent = Cm(1)
            r_line = p.add_run(line.strip()); set_font(r_line, 16)
    buf = io.BytesIO(); doc.save(buf); buf.seek(0)
    return buf

# ── 4. UI RENDER (SINGLE PAGE WORKFLOW) ──────────────────────────
st.title("🛡️ AI Procurement TOR Workspace")
st.caption("ระบบรวบรวม วิเคราะห์สเปคกลาง และร่างเอกสาร TOR (ว.159) ดีไซน์กะทัดรัดระดับมืออาชีพ")

# 📊 ส่วนที่ 1: ตั้งค่าข้อมูลโครงการหลัก
st.markdown("## 1. ข้อมูลโครงการทั่วไป")
st.markdown("<div class='step-card'>", unsafe_allow_html=True)
col_form1, col_form2 = st.columns(2)
with col_form1:
    p_name = st.text_input("ชื่อโครงการ / งานจัดซื้อจัดจ้าง *", placeholder="เช่น จัดซื้อชุดคอมพิวเตอร์ประมวลผลสูง 30 เครื่อง")
    p_agency = st.text_input("หน่วยงาน / ส่วนราชการ", placeholder="เช่น กองการพัสดุ")
with col_form2:
    p_budget = st.number_input("วงเงินงบประมาณ (บาท) *", min_value=0, step=5000, value=0)
    p_criteria = st.radio("หลักเกณฑ์การคัดเลือก", ["เกณฑ์ราคา", "เกณฑ์ราคาประกอบเกณฑ์อื่น"], horizontal=True)
st.markdown("</div>", unsafe_allow_html=True)

# 🔍 ส่วนที่ 2: ผนึกกำลังวิเคราะห์และคลีนไฟล์สเปค (สำหรับลงข้อ 4 อัตโนมัติ)
st.markdown("## 2. ระบบวิเคราะห์เอกสารสเปคกลางเพื่อสร้าง TOR ข้อ 4")
st.markdown("<div class='step-card'>", unsafe_allow_html=True)
job_description_pdf = st.text_area("วัตถุประสงค์ / ลักษณะงานที่ต้องการใช้จริง (ช่วยนำทาง AI):", placeholder="เช่น ต้องการสร้างห้องปฏิบัติการคอมพิวเตอร์ที่เน้นการประมวลผลโมเดล 3D และงานกราฟิกสเปคสูง...", height=65)

col_file1, col_file2 = st.columns([2, 1])
with col_file1:
    uploaded_files = st.file_uploader("เลือกไฟล์ PDF สเปคหรือใบเสนอราคาอ้างอิง", type=["pdf"], accept_multiple_files=True, label_visibility="collapsed")
with col_file2:
    process_pdf_click = st.button("🔓 สกัดสเปค & ซ่อนความลับ", use_container_width=True)

if uploaded_files and process_pdf_click:
    with st.spinner("กำลังคลีนข้อมูลนิติบุคคล..."):
        st.session_state.pdf_extracted_texts = {}
        for file in uploaded_files:
            raw_text = extract_text_from_pdf(file)
            cleaned_text = clean_redundant_info(raw_text)
            st.session_state.pdf_extracted_texts[file.name] = summarize_single_pdf_spec(cleaned_text)
    st.success("สกัดสเปคและแปลงข้อมูลลับเรียบร้อยแล้ว!")

if st.session_state.pdf_extracted_texts:
    st.markdown("<br><b>📝 กล่องตรวจสอบการเซนเซอร์ชื่อบริษัท:</b>", unsafe_allow_html=True)
    for file_name, text_content in list(st.session_state.pdf_extracted_texts.items()):
        with st.expander(f"🔎 ตรวจสอบไฟล์ย่อย: {file_name}", expanded=False): # ปรับเป็นยุบไว้เพื่อประหยัดพื้นที่หน้าจอ ไม่ดูเทอะทะ
            user_updated_text = st.text_area("แก้ไขสเปคย่อยท่อนนี้", value=text_content, height=120, key=f"edit_pdf_{file_name}", label_visibility="collapsed")
            st.session_state.pdf_extracted_texts[file_name] = user_updated_text
    
    check_company = st.checkbox("✅ ตรวจสอบเรียบร้อย: ข้าพเจ้ายืนยันว่าลบรายชื่อบริษัทและตราสินค้า (ล็อกสเปค) เกลี้ยงแล้ว")
    
    if st.button("📊 บันทึกคุณลักษณะเฉพาะ (สเปคกลาง) เข้าสู่ข้อ 4 TOR", type="primary"):
        if not job_description_pdf:
            st.warning("⚠️ โปรดระบุวัตถุประสงค์ลักษณะงานก่อน")
        elif not check_company:
            st.error("⚠️ โปรดกดยืนยันการตรวจสอบรายชื่อบริษัทด้านบนก่อนดำเนินงาน")
        else:
            with st.spinner("AI กำลังสร้างข้อกำหนดสเปคกลางราชการ (ข้อ 4)..."):
                try:
                    all_data = ""
                    for idx, (f_name, f_text) in enumerate(st.session_state.pdf_extracted_texts.items()):
                        all_data += f"\n[เอกสารอ้างอิง {idx+1}]\n{f_text}\n"
                    
                    prompt = f"""
                    วิเคราะห์ข้อมูลและร่างสเปคกลางเพื่อนำไปใส่ในเอกสาร TOR ข้อ 4 (แบบรูปรายการ หรือคุณลักษณะเฉพาะของพัสดุ)
                    วัตถุประสงค์โครงการ: {job_description_pdf}
                    ข้อมูลอ้างอิงจากผู้เสนอราคา: {all_data}
                    
                    เขียนสเปคและข้อย่อยละเอียดและครบครันที่สุด แตกหัวข้อย่อยชัดเจน ขึ้นต้นด้วย 4.1, 4.2 ตามระเบียบราชการไทย ห้ามมีชื่อยี่ห้อและชื่อบริษัทเด็ดขาด
                    """
                    response = client.models.generate_content(
                        model=MODEL_NAME, contents=prompt,
                        config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT, temperature=0.3, max_output_tokens=3500)
                    )
                    st.session_state.ai_drafted_spec_v4 = response.text
                    st.session_state.tor_sections[4] = response.text  # ซิงค์เข้า State ข้อ 4 ทันที
                    st.success("สร้างร่างสเปคกลางเรียบร้อย! ข้อมูลถูกส่งเข้าสู่แบบฟอร์มร่างข้อ 4 ด้านล่างแล้วครับ")
                except Exception as e:
                    st.error(f"เกิดข้อผิดพลาด: {e}")
st.markdown("</div>", unsafe_allow_html=True)

# 📝 ส่วนที่ 3: แบบฟอร์มตรวจทานและร่างเอกสาร TOR 10 ข้อ
st.markdown("## 3. ตรวจทานและจัดการร่างขอบเขตงาน TOR ทั้ง 10 ข้อ")
if p_name:
    st.caption(f"📌 กำลังทำงานในโครงการ: **{p_name}** | งบประมาณ: **{p_budget:,} บาท**")

# วนลูปแสดงกล่องข้อความ 10 ข้อหลักในรูปแบบ Card ยุบขยายได้ มินิมอล ไม่กินพื้นที่หน้าจอ
for i in range(1, 11):
    with st.expander(f"🔹 ข้อ {i}: {TOR_TITLES[i]}", expanded=(i==4)):
        current_content = st.session_state.tor_sections.get(i, "")
        
        if i == 4 and st.session_state.ai_drafted_spec_v4:
            st.markdown("<span style='color:#10B981; font-size:12px; font-weight:500;'>🟢 ข้อมูลชุดนี้ได้รับการซิงค์มาจากระบบวิเคราะห์สเปคกลางด้านบนแล้ว</span>", unsafe_allow_html=True)
            
        updated_content = st.text_area(f"เนื้อหาข้อ {i}", value=current_content, height=140, key=f"main_edit_sec_{i}", label_visibility="collapsed")
        st.session_state.tor_sections[i] = updated_content
        
        col_btn1, col_btn2 = st.columns([4, 1])
        with col_btn2:
            if st.button(f"🔄 รีเจนเฉพาะข้อ {i}", key=f"main_regen_btn_{i}", use_container_width=True):
                if not p_name:
                    st.error("กรุณาระบุชื่อโครงการก่อน")
                else:
                    box_placeholder = st.empty()
                    spec_prompt = f"จงเขียนทบทวนร่างข้อกำหนดขอบเขตงาน TOR โครงการ '{p_name}' เฉพาะในส่วนของ 'ข้อ {i} หัวข้อ: {TOR_TITLES[i]}' ให้ออกมาเป็นข้อๆ ภาษาราชการอย่างละเอียด ถี่ถ้วน เต็มรูปแบบ วงเงินงบประมาณคือ {p_budget} บาท"
                    generate_section_stream(spec_prompt, i, box_placeholder)
                    st.rerun()

st.write("")
# ปุ่มสั่งการยิงเจนยาวพร้อมกัน 10 ข้อหลัก
if st.button("✨ สั่ง AI ร่างเอกสารทุกข้อที่เหลือพร้อมกันแบบละเอียดยิบ", type="primary", use_container_width=True):
    if not p_name:
        st.error("⚠️ กรุณาระบุชื่อโครงการที่ด้านบนสุดก่อนเริ่มกระบวนการ")
    else:
        st.session_state.meta_data = {"title": p_name, "agency": p_agency, "type": "ซื้อ/จ้างทั่วไป", "budget": p_budget, "criteria": p_criteria}
        for i in range(1, 11):
            if i == 4 and st.session_state.tor_sections[4]:
                continue
                
            st.toast(f"กำลังร่างข้อ {i} แบบละเอียด...")
            box_placeholder = st.empty()
            proj_context = f"โครงการ: {p_name}, หน่วยงาน: {p_agency}, งบประมาณ: {p_budget} บาท, เกณฑ์พิจารณา: {p_criteria}"
            specific_prompt = f"""
            จงเขียนเนื้อหาของขอบเขตของงาน (TOR) ตามมาตรฐานราชการไทย ว.159 เฉพาะ 'ข้อ {i} หัวข้อ: {TOR_TITLES[i]}' ของ{proj_context} 
            ข้อกำหนดกติกา: อธิบายรายละเอียดความรับผิดชอบ เงื่อนไข เงื่อนไขเวลา กฎหมายพัสดุ และระเบียบปฏิบัติที่เกี่ยวข้องให้ถี่ถ้วนและยาวที่สุดเท่าที่จะทำได้ ห้ามสรุปสั้นย่อเด็ดขาด
            """
            generate_section_stream(specific_prompt, i, box_placeholder)
        st.balloons()

# ⬇️ ส่วนการ Export ออกเป็นไฟล์ใช้งาน (ปรับปรุงปุ่มให้สวยกะทัดรัดเข้าคู่กัน)
if st.session_state.meta_data:
    st.markdown("### 💾 ดาวน์โหลดเอกสารผลลัพธ์")
    all_text_export = f"ร่างขอบเขตของงาน (TOR) - {p_name}\n\n"
    for idx, ct in st.session_state.tor_sections.items():
        all_text_export += f"ข้อ {idx} {TOR_TITLES[idx]}\n{ct}\n\n"
        
    down_col1, down_col2 = st.columns(2)
    down_col1.download_button("⬇️ ดาวน์โหลดเป็นไฟล์ .TXT", data=all_text_export, file_name=f"TOR_{p_name}.txt", mime="text/plain", use_container_width=True)
    
    docx_buf = create_docx(p_name, p_agency, "ซื้อ/จ้างทั่วไป", p_budget, p_criteria, st.session_state.tor_sections)
    if docx_buf:
        down_col2.download_button("📄 ส่งออกเป็นไฟล์ Word (.docx)", data=docx_buf, file_name=f"TOR_{p_name}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
