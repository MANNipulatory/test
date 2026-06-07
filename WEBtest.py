import streamlit as st
import os
import io
import re
import time
from datetime import datetime
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
    page_title="AI TOR & Spec Analyzer",
    page_icon="🛡️",
    layout="wide"
)

st.markdown("""
    <style>
        .reportview-container .main .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
        h1 {
            font-size: 2.2rem !important;
            font-weight: 700 !important;
            color: #1E293B;
            margin-bottom: 0.5rem !important;
        }
        h2 {
            font-size: 1.5rem !important;
            font-weight: 600 !important;
            color: #334155;
        }
        h3 {
            font-size: 1.15rem !important;
            font-weight: 600 !important;
            color: #475569;
        }
        .stTextArea textarea {
            border-radius: 8px !important;
        }
        .streamlit-expanderHeader {
            font-weight: 500 !important;
            background-color: #F8FAFC !important;
            border-radius: 6px !important;
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
    "คุณคือผู้เชี่ยวชาญด้านการจัดซื้อจัดจ้างภาครัฐไทย "
    "ที่มีความเชี่ยวชาญในการร่างขอบเขตของงาน (TOR) "
    "ตามมาตรฐานหนังสือเวียน กค (กวจ) 0405.4/ว 159 "
    "ของกรมบัญชีกลาง "
    "ตอบเป็นภาษาราชการไทยที่ถูกต้องและเป็นทางการ "
    "ห้ามระบุยี่ห้อหรือรุ่นของสินค้าโดยตรง ให้ใช้ Functional Specification แทน "
    "เนื้อหาในแต่ละข้อต้องสอดคล้องและสัมพันธ์กัน "
    "ตอบเฉพาะเนื้อหาที่ถามโดยตรง ไม่ต้องมีคำนำหรือคำลงท้ายที่ไม่จำเป็น "
    "ห้ามใช้อักขระภาษาจีน ญี่ปุ่น เกาหลี หรืออักขระพิเศษจากภาษาอื่นโดยเด็ดขาด "
    "ใช้ตัวเลขอารบิก (1, 2, 3, 4, 5) เท่านั้น ห้ามใช้เลขไทย (๑, ๒, ๓, ๔, ๕) ในทุกกรณี "
    "เมื่อเขียนรายการข้อย่อย ให้เริ่มต้นที่ข้อ 1 เสมอ "
    "ห้ามแปลเนื้อหาเป็นภาษาอังกฤษโดยเด็ดขาด ห้ามมี paragraph หรือบรรทัดที่เป็นภาษาอังกฤษล้วน "
    "ตอบเป็นภาษาไทยเท่านั้น คำศัพท์เทคนิคอาจมีภาษาอังกฤษแทรกในวงเล็บได้เท่านั้น"
)

# ── 3. STATE MANAGEMENT ──────────────────────────────────────────
if "tor_sections" not in st.session_state:
    st.session_state.tor_sections = {i: "" for i in range(1, 11)}
if "meta_data" not in st.session_state:
    st.session_state.meta_data = {}
if "pdf_extracted_texts" not in st.session_state:
    st.session_state.pdf_extracted_texts = {}

# ── 4. HELPER FUNCTIONS ──────────────────────────────────────────
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
    """ใช้ Regex กรองข้อมูลติดต่อ และเซนเซอร์ชื่อบริษัท/ห้างหุ้นส่วน/แบรนด์สินค้าอัตโนมัติ"""
    if not text:
        return ""
    
    # 1. กรองเบอร์โทรศัพท์รูปแบบต่างๆ ออก
    text = re.sub(r'\b\d{2,3}-\d{3}-\d{4}\b|\b\d{2,3}-\d{4}-\d{4}\b|\b\d{9,10}\b', "[PHONE_HIDDEN]", text)
    
    # 2. กรองอีเมลออก
    text = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', "[EMAIL_HIDDEN]", text)
    
    # 3. กรองลิงก์/URL ออก
    text = re.sub(r'https?://[^\s<>"]+|www\.[^\s<>"]+', "[URL_HIDDEN]", text)
    
    # 4. 🔥 เพิ่มการเซนเซอร์ชื่อบริษัท/นิติบุคคล (ภาษาไทย)
    # จับกลุ่ม: บริษัท...จำกัด (มหาชน), บริษัท...จำกัด, ห้างหุ้นส่วนจำกัด..., หจก...., บมจ....
    text = re.sub(r'(บริษัท\s+[^\s\n]+?\s+จำกัด(?:\s*\(มหาชน\))?)|(ห้างหุ้นส่วนจำกัด\s+[^\s\n]+)|(หจก\s*\.\s*[^\s\n]+)|(บมจ\s*\.\s*[^\s\n]+)', "[COMPANY_HIDDEN]", text)
    
    # 5. 🔥 เพิ่มการเซนเซอร์ชื่อบริษัท (ภาษาอังกฤษ)
    # จับกลุ่ม: ตัวอักษรตามด้วย Co., Ltd. / Company Limited / Inc. / Corp.
    text = re.sub(r'\b[A-Za-z0-9\s\.,&-]+(?:Co\s*\.\s*,\s*Ltd\s*\.?|Company\s+Limited|Inc\s*\.|Corp\s*\.)', "[COMPANY_HIDDEN]", text, flags=re.IGNORECASE)
    
    # 6. เซนเซอร์แบรนด์ไอทีหลักๆ ที่ชอบติดมาในสเปค (เพื่อป้องกันการล็อกสเปคเบื้องต้น)
    text = re.sub(r'\b(Intel|AMD|NVIDIA|GeForce|Asus|Acer|HP|Dell|Lenovo|Apple|Microsoft|Cisco|Huawei)\b', "[BRAND_HIDDEN]", text, flags=re.IGNORECASE)
    
    return text

def create_docx(title, agency, project_type, budget, criteria, sections):
    try:
        from docx import Document
        from docx.shared import Pt, Cm
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement
    except ImportError:
        return None

    doc = Document()
    sec = doc.sections[0]
    sec.page_width = Cm(21); sec.page_height = Cm(29.7)
    sec.left_margin = Cm(3); sec.right_margin = Cm(2)
    sec.top_margin = Cm(2.5); sec.bottom_margin = Cm(2.5)

    FONT = "TH Sarabun New"

    def set_font(run, size=16, bold=False):
        run.bold = bold; run.font.size = Pt(size)
        rPr = run._element.get_or_add_rPr()
        rFonts = rPr.find(qn('w:rFonts'))
        if rFonts is None:
            rFonts = OxmlElement('w:rFonts')
            rPr.insert(0, rFonts)
        for attr in ('w:ascii', 'w:hAnsi', 'w:cs', 'w:eastAsia'):
            rFonts.set(qn(attr), FONT)

    p = doc.add_paragraph()
    run = p.add_run("ร่างขอบเขตของงาน (Terms of Reference)"); set_font(run, 20, True); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p = doc.add_paragraph()
    run = p.add_run(title); set_font(run, 18, True); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    meta = [
        ("อ้างอิง", "หนังสือเวียน กค (กวจ) 0405.4/ว 159 ลงวันที่ 20 มีนาคม 2566"),
        ("หน่วยงาน", agency), ("ประเภทงาน", project_type),
        ("วงเงินงบประมาณ", f"{budget:,} บาท" if budget else "-"), ("หลักเกณฑ์", criteria)
    ]
    for label, value in meta:
        if value:
            p = doc.add_paragraph()
            r1 = p.add_run(f"{label}: "); set_font(r1, 16, True)
            r2 = p.add_run(str(value)); set_font(r2, 16, False)

    for num, content in sections.items():
        p = doc.add_paragraph()
        r = p.add_run(f"ข้อ {num} {TOR_TITLES[num]}"); set_font(r, 16, True)
        for line in content.strip().split("\n"):
            line = line.strip()
            if not line: continue
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(1)
            r_line = p.add_run(line); set_font(r_line, 16)
            
    buf = io.BytesIO(); doc.save(buf); buf.seek(0)
    return buf

def generate_section_stream(prompt_text, section_num, placeholder):
    if not client:
        st.error("❌ ไม่พบคีย์เชื่อมต่อ Gemini API")
        return ""
    full_response = ""
    try:
        response_stream = client.models.generate_content_stream(
            model=MODEL_NAME,
            contents=prompt_text,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.7,
                top_p=0.6,
                max_output_tokens=1500
            )
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

# ── 5. STREAMLIT NATIVE UI ───────────────────────────────────────
header_col, status_col = st.columns([5, 1])
with header_col:
    st.title("🛡️ AI Procurement Space")
    st.caption("ระบบบริหารจัดการเอกสาร TOR (ว.159) และวิเคราะห์สเปคกลางอัจฉริยะ")
with status_col:
    if client:
        st.markdown("<div style='text-align:right; margin-top:15px;'><span style='background-color:#DCFCE7; color:#15803D; padding:4px 10px; border-radius:12px; font-size:13px; font-weight:500;'>🟢 Connected</span></div>", unsafe_allow_html=True)
    else:
        st.markdown("<div style='text-align:right; margin-top:15px;'><span style='background-color:#FEE2E2; color:#B91C1C; padding:4px 10px; border-radius:12px; font-size:13px; font-weight:500;'>🔴 No Key</span></div>", unsafe_allow_html=True)

st.write("")

tab_gen, tab_pdf_analyze, tab_setup_info = st.tabs([
    "📝 ร่างโครงร่าง TOR (ว.159)", 
    "📊 วิเคราะห์ไฟล์ PDF สเปคกลาง", 
    "📋 ข้อมูลอ้างอิง ว.159"
])

# ── แท็บที่ 1: GENERATOR (ว.159) ───────────────────────────────────
with tab_gen:
    st.write("")
    mode = st.radio("รูปแบบการระบุข้อมูล :", ["⚡ โหมดด่วน (อธิบายแนวคิดโครงการ)", "📋 โหมดฟอร์มละเอียด (ระบุรายหัวข้อ)"], horizontal=True, label_visibility="collapsed")
    
    with st.container():
        if "⚡ โหมดด่วน" in mode:
            quick_name = st.text_input("ชื่อโครงการ / งานจัดซื้อจัดจ้าง *", key="q_name", placeholder="เช่น จัดซื้อคอมพิวเตอร์สำนักงาน 10 เครื่อง")
            col_q1, col_q2 = st.columns([2, 1])
            with col_q1:
                project_desc = st.text_area("อธิบายรายละเอียดโครงการสั้นๆ พอสังเขป", placeholder="ต้องการสเปคสำหรับงานเอกสารทั่วไป ประกันอย่างน้อย 2 ปี...", height=80, key="quick_desc")
            with col_q2:
                quick_budget = st.number_input("วงเงินงบประมาณ (บาท)", min_value=0, step=10000, value=0, key="q_budget")
            
            p_name = quick_name; p_type = "ซื้อ/จ้างทั่วไป"; p_agency = "หน่วยงานภาครัฐ"; p_budget = quick_budget; p_criteria = "เกณฑ์ราคา"
        else:
            p_name = st.text_input("ชื่อโครงการ / งานจัดซื้อจัดจ้าง *", placeholder="เช่น โครงการจ้างพัฒนาระบบสารสนเทศ...", key="detailed_name")
            col_form1, col_form2 = st.columns(2)
            with col_form1:
                p_type = st.selectbox("ประเภทงาน *", ["ซื้อ/จ้างทั่วไป", "จ้างที่ปรึกษา", "จ้างก่อสร้าง", "จ้างสำรวจ/ศึกษา/วิจัย"])
                p_agency = st.text_input("หน่วยงาน / ส่วนราชการ", placeholder="เช่น กรมชลประทาน")
            with col_form2:
                p_budget = st.number_input("วงเงินงบประมาณ (บาท) *", min_value=0, step=1000, value=0)
                p_criteria = st.radio("หลักเกณฑ์คัดเลือกข้อเสนอ", ["เกณฑ์ราคา", "เกณฑ์ราคาประกอบเกณฑ์อื่น"], horizontal=True)
            project_desc = f"โครงการ: {p_name}, ประเภท: {p_type}, หน่วยงาน: {p_agency}, งบประมาณ: {p_budget} บาท, หลักเกณฑ์: {p_criteria}"

    st.write("")
    if st.button("✨ เริ่มร่างขอบเขตงาน TOR ทั้ง 10 ข้อ", type="primary", use_container_width=True):
        if not p_name:
            st.error("⚠️ กรุณาระบุชื่อโครงการก่อนเริ่มกระบวนการ")
        else:
            st.session_state.meta_data = {"title": p_name, "agency": p_agency, "type": p_type, "budget": p_budget, "criteria": p_criteria}
            
            for i in range(1, 11):
                st.markdown(f"📍 **กำลังร่างข้อที่ {i}: {TOR_TITLES[i]}**")
                box_placeholder = st.empty()
                specific_prompt = f"จงเขียนเนื้อหาของขอบเขตของงาน (TOR) สำหรับโครงการ '{p_name}' เฉพาะในส่วนของ 'ข้อ {i} หัวข้อ: {TOR_TITLES[i]}' เท่านั้น โดยอ้างอิงจากข้อมูลบริบทโครงการดังนี้: {project_desc}"
                generate_section_stream(specific_prompt, i, box_placeholder)
            st.balloons()

    if st.session_state.meta_data:
        st.write("")
        st.subheader("📋 ตรวจสอบและดาวน์โหลดเอกสาร")
        
        meta_info = st.session_state.meta_data
        m1, m2, m3 = st.columns(3)
        m1.metric("งบประมาณโครงการ", f"{meta_info['budget']:,} บาท")
        m2.metric("ประเภทสัญญา", meta_info['type'])
        m3.metric("เกณฑ์คัดเลือก", meta_info['criteria'])
        
        dl1, dl2 = st.columns(2)
        all_text = f"ร่างขอบเขตของงาน (TOR) - {meta_info['title']}\n\n"
        for idx, ct in st.session_state.tor_sections.items():
            all_text += f"ข้อ {idx} {TOR_TITLES[idx]}\n{ct}\n\n"
            
        dl1.download_button("⬇️ Export เป็น .TXT", data=all_text, file_name=f"TOR_{meta_info['title']}.txt", mime="text/plain", use_container_width=True)
        
        docx_buf = create_docx(meta_info['title'], meta_info['agency'], meta_info['type'], meta_info['budget'], meta_info['criteria'], st.session_state.tor_sections)
        if docx_buf:
            dl2.download_button("📄 Export เป็น Word (.docx)", data=docx_buf, file_name=f"TOR_{meta_info['title']}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)

        st.write("")
        for i in range(1, 11):
            with st.expander(f"ข้อ {i}: {TOR_TITLES[i]}", expanded=False):
                current_val = st.session_state.tor_sections.get(i, "")
                updated_val = st.text_area("แก้ไขเนื้อหา", value=current_val, key=f"edit_sec_{i}", height=120, label_visibility="collapsed")
                st.session_state.tor_sections[i] = updated_val
                if st.button(f"🔄 รีเจนเฉพาะข้อ {i}", key=f"regen_{i}"):
                    sub_placeholder = st.empty()
                    single_prompt = f"จงเขียนทบทวนปรับปรุงเนื้อหาเฉพาะ 'ข้อ {i} หัวข้อ: {TOR_TITLES[i]}' สำหรับโครงการ '{meta_info['title']}' ให้มีความรายละเอียดชัดเจนตามระบบราชการ"
                    generate_section_stream(single_prompt, i, sub_placeholder)
                    st.rerun()


# ── แท็บที่ 2: PDF ANALYZER ───────────────────────────────────────
with tab_pdf_analyze:
    st.write("")
    
    job_description_pdf = st.text_area(
        "🎯 วัตถุประสงค์การใช้งาน/ลักษณะงานที่ต้องการ :",
        placeholder="เช่น จัดตั้งห้องเรียนคอมพิวเตอร์กราฟิกสามมิติ จำนวน 30 เครื่อง พร้อมระบบเครือข่าย...",
        height=70,
        key="pdf_job_desc"
    )

    st.write("")
    st.markdown("### 📂 อัปโหลดเอกสาร")
    
    uploaded_files = st.file_uploader(
        "เลือกไฟล์ PDF สเปคหรือใบเสนอราคาจากบริษัทต่างๆ (เลือกพร้อมกันคราวละ 2 ไฟล์ขึ้นไป)", 
        type=["pdf"], 
        accept_multiple_files=True,
        key="pdf_uploader"
    )

    if uploaded_files:
        st.write("")
        if st.button("🔓 ดึงข้อมูลและคลีนสิ่งซ้ำซ้อนอัตโนมัติ", type="secondary", use_container_width=True):
            with st.spinner("ระบบกำลังอ่านข้อความและใช้ Regex เคลียร์ข้อมูลติดต่อและชื่อบริษัทออกเบื้องต้น..."):
                st.session_state.pdf_extracted_texts = {}
                for file in uploaded_files:
                    raw_text = extract_text_from_pdf(file)
                    cleaned_text = clean_redundant_info(raw_text)
                    st.session_state.pdf_extracted_texts[file.name] = cleaned_text
            st.success("ดึงและจัดระเบียบข้อมูลสำเร็จ! ตรวจสอบความถูกต้องขั้นสุดท้ายที่กล่องข้อความด้านล่าง")

    if st.session_state.pdf_extracted_texts:
        st.write("")
        st.markdown("### 📝 ตรวจทานและแก้ไขเนื้อหาเอกสารด้วยตัวเอง")
        st.info("💡 ข้อความด้านล่างผ่านการใช้ Regex ซ่อนชื่อบริษัท/เบอร์โทร/อีเมลแล้ว ท่านสามารถพิมพ์แก้ไขสเปคส่วนเกินออกเพิ่มได้ด้วยตัวเองทันทีก่อนส่งให้ AI ประมวลผล")
        
        for file_name, text_content in list(st.session_state.pdf_extracted_texts.items()):
            with st.expander(f"📄 ตรวจสอบเนื้อหา: {file_name}", expanded=True):
                user_updated_text = st.text_area(
                    "แก้ไขเนื้อหาข้อความเพื่อเตรียมส่งให้ AI",
                    value=text_content,
                    height=200,
                    key=f"user_edit_{file_name}",
                    label_visibility="collapsed"
                )
                st.session_state.pdf_extracted_texts[file_name] = user_updated_text

        st.write("")
        st.markdown("### 🚀 ประมวลผลสร้างร่างสเปคกลาง")
        if st.button("📊 สั่ง AI สรุปเปรียบเทียบและทำร่างสเปคกลาง (ไม่ล็อกสเปค)", type="primary", use_container_width=True):
            if not client:
                st.error("🚨 ไม่พบคีย์เชื่อมต่อวิเคราะห์ระบบ")
            elif not job_description_pdf:
                st.warning("⚠️ โปรดใส่ลักษณะงานหรือวัตถุประสงค์ก่อน")
            else:
                with st.spinner("Gemini กำลังวิเคราะห์จุดร่วมทางเทคนิคเพื่อสร้างสเปคกลางที่โปร่งใส..."):
                    try:
                        all_companies_data_prompt = ""
                        for idx, (f_name, final_text) in enumerate(st.session_state.pdf_extracted_texts.items()):
                            all_companies_data_prompt += f"\n--- Spec Document {idx+1} ---\n{final_text[:4000]}\n"
                        
                        prompt = f"""
                        คุณคือผู้เชี่ยวชาญด้านการตรวจรับและจัดทำคุณลักษณะเฉพาะ (TOR Specialist) 
                        งานของคุณคือวิเคราะห์สเปคจากข้อเสนอที่ได้รับ ({len(st.session_state.pdf_extracted_texts)} ชุด) แล้วสรุปเป็น 'ร่างสเปคกลาง' ที่ถูกต้องตามหลักกฎหมายจัดซื้อจัดจ้าง คือ "ห้ามระบุชื่อยี่ห้อหรือรุ่นสินค้าเด็ดขาด" และห้ามระบุชื่อบริษัทใดๆ ทั้งสิ้น แต่ให้ใช้เกณฑ์ทางเทคนิคที่ทุกบริษัทสามารถหาของมาสู้กันได้

                        [ลักษณะงานที่ผู้ใช้ต้องการ]:
                        {job_description_pdf}

                        [ข้อมูลเนื้อหาเอกสารสเปคที่ผู้ใช้ส่งมาและตรวจทานแล้ว]:
                        {all_companies_data_prompt}

                        กรุณาตอบกลับเป็นภาษาไทย โดยใช้รูปแบบ Markdown ที่กระชับ เป็นข้อๆ และเข้าใจง่ายที่สุด ดังนี้:
                        1. ## 📊 ตารางสรุปเปรียบเทียบสเปค (สรุปเฉพาะจุดสำคัญ)
                        2. ## 📋 ร่างสเปคกลาง (ข้อกำหนดขั้นต่ำที่โปร่งใสและแข่งขันได้จริง) *สั่งห้ามระบุคำว่า Intel, AMD, NVIDIA, GeForce โดยเด็ดขาด* ให้เปลี่ยนเป็นคำจำกัดความเชิงเทคนิคเช่น หน่วยประมวลผลกลาง หรือหน่วยประมวลผลกราฟิกชนิดแยก
                        3. ## 💡 ความเห็นกรรมการ (สรุปสั้น 3 บรรทัดจบ)
                        """
                        
                        response = client.models.generate_content(
                            model=MODEL_NAME,
                            contents=prompt,
                            config=types.GenerateContentConfig(
                                system_instruction="คุณคือผู้เชี่ยวชาญด้านกฎหมายพัสดุและขอบเขตสเปค TOR อุปกรณ์เทคโนโลยี",
                                temperature=0.4
                            )
                        )
                        st.write("")
                        st.success("สรุปผลสำเร็จ!")
                        st.markdown(response.text)
                    except Exception as e:
                        st.error(f"เกิดข้อผิดพลาด: {str(e)}")


# ── แท็บที่ 3: INFO ONLY ──────────────────────────────────────────
with tab_setup_info:
    st.write("")
    st.markdown("### 📋 โครงสร้างแนวทาง 10 ข้อหลักตาม ว.159")
    st.caption("อ้างอิงโครงสร้างมาตรฐานหนังสือเวียน กค (กวจ) 0405.4/ว 159 ของกรมบัญชีกลาง")
    
    info_data = [
        {"ข้อที่": f"ข้อ {i}", "หัวข้อโครงร่างมาตรฐาน": TOR_TITLES[i]} for i in range(1, 11)
    ]
    st.table(info_data)
