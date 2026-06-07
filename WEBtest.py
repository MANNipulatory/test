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
# ตรวจสอบและเชื่อมต่อ API Key ผ่านระบบ Secrets ของ Streamlit หลังบ้าน หรือ Environment Variable
if "GEMINI_API_KEY" in st.secrets and st.secrets["GEMINI_API_KEY"]:
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
elif os.environ.get("GEMINI_API_KEY"):
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
else:
    # เผื่อกรณีกรอกในหน้าแอปชั่วคราว
    client = None

# ใช้โมเดลยอดนิยม ประสิทธิภาพสูงและเร็วสตรีมข้อมูลได้ดี
MODEL_NAME = "gemini-2.5-flash"

st.set_page_config(
    page_title="TOR (ว.159) & AI วิเคราะห์สเปคกลาง (Gemini)",
    page_icon="🛡️",
    layout="wide"
)

# ระบบหัวข้อมาตรฐาน 10 ข้อ ตาม ว.159
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

# ── 2. SYSTEM PROMPT FOR TOR GENERATOR (ว.159) ─────────────────────
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

# ── 4. HELPER FUNCTIONS ──────────────────────────────────────────

def extract_text_from_pdf(uploaded_file):
    """ฟังก์ชันสำหรับอ่านข้อความจากไฟล์ PDF"""
    try:
        pdf_reader = pypdf.PdfReader(uploaded_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() or ""
        return text
    except Exception as e:
        st.error(f"ไม่สามารถอ่านไฟล์ {uploaded_file.name} ได้: {e}")
        return ""

def auto_censor_text(text, custom_company=None, custom_phone=None):
    """ฟังก์ชันเซนเซอร์ข้อมูลติดต่อและชื่อบริษัทอัตโนมัติ (Data Anonymization)"""
    if not text:
        return ""
    text = re.sub(r'\b\d{2,3}-\d{3}-\d{4}\b|\b\d{2,3}-\d{4}-\d{4}\b|\b\d{9,10}\b', "[PHONE_NUMBER_HIDDEN]", text)
    text = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', "[EMAIL_HIDDEN]", text)
    text = re.sub(r'https?://[^\s<>"]+|www\.[^\s<>"]+', "[WEBSITE_HIDDEN]", text)
    
    if custom_company and custom_company.strip():
        text = re.sub(re.escape(custom_company.strip()), "[COMPANY_NAME_HIDDEN]", text, flags=re.IGNORECASE)
    if custom_phone and custom_phone.strip():
        text = text.replace(custom_phone.strip(), "[PHONE_NUMBER_HIDDEN]")
        
    return text

def generate_section_stream(prompt_text, section_num, placeholder):
    """ฟังก์ชันยิง Gemini API แบบ Stream เพื่อร่าง TOR 10 ข้อ"""
    if not client:
        st.error("❌ ไม่พบคีย์เชื่อมต่อ Gemini API กรุณาตั้งค่าคีย์ในแท็บตั้งค่าระบบ")
        return ""
    
    full_response = ""
    try:
        # ใช้ลูกเล่น Generate แบบ Stream ของ SDK ใหม่กลุ่ม genai.Client
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
        st.error(f"เกิดข้อผิดพลาดในการดึงข้อมูลข้อ {section_num}: {e}")
        return ""

def create_docx(title, agency, project_type, budget, criteria, sections):
    """ฟังก์ชันสร้างไฟล์ Word (.docx) มาตรฐานราชการไทย"""
    try:
        from docx import Document
        from docx.shared import Pt, Cm
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement
    except ImportError:
        st.error("กรุณาเพิ่ม python-docx ลงในไฟล์ requirements.txt")
        return None

    doc = Document()
    sec = doc.sections[0]
    sec.page_width = Cm(21)
    sec.page_height = Cm(29.7)
    sec.left_margin = Cm(3)
    sec.right_margin = Cm(2)
    sec.top_margin = Cm(2.5)
    sec.bottom_margin = Cm(2.5)

    FONT = "TH Sarabun New"

    def set_font(run, size=16, bold=False):
        run.bold = bold
        run.font.size = Pt(size)
        rPr = run._element.get_or_add_rPr()
        rFonts = rPr.find(qn('w:rFonts'))
        if rFonts is None:
            rFonts = OxmlElement('w:rFonts')
            rPr.insert(0, rFonts)
        for attr in ('w:ascii', 'w:hAnsi', 'w:cs', 'w:eastAsia'):
            rFonts.set(qn(attr), FONT)

    def add_text(para, text, bold=False, size=16, align=None):
        run = para.add_run(text)
        set_font(run, size=size, bold=bold)
        if align:
            para.alignment = align
        return run

    p = doc.add_paragraph()
    add_text(p, "ร่างขอบเขตของงาน (Terms of Reference)", bold=True, size=20, align=WD_ALIGN_PARAGRAPH.CENTER)
    p = doc.add_paragraph()
    add_text(p, title, bold=True, size=18, align=WD_ALIGN_PARAGRAPH.CENTER)
    doc.add_paragraph()

    meta = [
        ("อ้างอิง", "หนังสือเวียน กค (กวจ) 0405.4/ว 159 ลงวันที่ 20 มีนาคม 2566"),
        ("หน่วยงาน", agency),
        ("ประเภทงาน", project_type),
        ("วงเงินงบประมาณ", f"{budget:,} บาท" if budget else "-"),
        ("หลักเกณฑ์", criteria),
        ("วันที่สร้าง", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    ]
    for label, value in meta:
        if value:
            p = doc.add_paragraph()
            add_text(p, f"{label}: ", bold=True, size=16)
            add_text(p, str(value), bold=False, size=16)
    doc.add_paragraph()

    for num, content in sections.items():
        p = doc.add_paragraph()
        add_text(p, f"ข้อ {num} {TOR_TITLES[num]}", bold=True, size=16)
        
        for line in content.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            
            line_no_num = re.sub(r'^(ข้อ\s*)?\d+[\.\s]*', '', line).strip()
            title_words = set(re.sub(r'[/\-]', ' ', TOR_TITLES[num]).split())
            line_words = set(re.sub(r'[/\-]', ' ', line_no_num).split())
            if title_words and line_words:
                overlap = len(title_words & line_words) / len(line_words)
                if overlap >= 0.6 and len(line_no_num) < 60:
                    continue
            
            line = re.sub(r'[ \t]+', ' ', line).strip()
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.left_indent = Cm(1)
            p.paragraph_format.space_after = Pt(4)
            add_text(p, line, size=16)
        doc.add_paragraph()

    p = doc.add_paragraph()
    add_text(p, "หมายเหตุ: ", bold=True, size=14)
    add_text(p, "โครงร่างนี้เป็นแนวทางเบื้องต้น เจ้าหน้าที่ผู้รับผิดชอบต้องตรวจสอบและแก้ไขก่อนนำไปใช้งาน", size=14)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf

# ── 5. STREAMLIT NATIVE UI ───────────────────────────────────────
st.title("🛡️ ระบบ AI บริหารจัดการเอกสาร TOR และวิเคราะห์สเปคกลาง (Gemini Version)")
st.caption("ระบบรวมฟังก์ชันการจัดทำ TOR 10 ข้อหลัก (ว.159), ตรวจจับใบเสนอราคาคัดลอกแบรนด์ออก และเซนเซอร์ข้อมูลความลับ")

# ส่วนแสดงสถานะ API Key ด้านขวาบน
status_col1, status_col2 = st.columns([4, 1])
with status_col2:
    if client:
        st.success("🟢 Connected (Gemini)")
    else:
        st.error("🔴 Disconnected (No Key)")

# แท็บการทำงานแยกหมวดหมู่ชัดเจน
tab_gen, tab_pdf_analyze, tab_censor_tool, tab_setup_info = st.tabs([
    "📝 1. เจนโครงร่าง 10 หัวข้อ (ว.159)", 
    "📊 2. วิเคราะห์เปรียบเทียบ PDF สเปคกลาง", 
    "✂️ 3. เครื่องมือแอบตัด/เซนเซอร์ข้อมูลความลับ", 
    "⚙️ ตั้งค่าระบบ & ข้อมูล ว.159"
])

# ── แท็บที่ 1: GENERATOR (ว.159 ดั้งเดิมของคุณ ปรับเป็น Gemini) ───────────
with tab_gen:
    if not client:
        st.warning("⚠️ ยังไม่ได้เชื่อมต่อระบบ — กรุณาตั้งค่า API Key ในแท็บขวาสุดเพื่อเปิดใช้งานระบบ AI")
        
    st.subheader("📄 เครื่องมือสร้างโครงร่าง TOR ตามหนังสือ ว.159")
    mode = st.radio("เลือกโหมดการทำงาน", ["⚡ โหมดด่วน — บอก AI เลย", "📋 โหมดละเอียด — กรอกฟอร์ม"], horizontal=True)
    
    if "⚡ โหมดด่วน" in mode:
        st.markdown("**✨ อธิบายโครงการแล้วให้ AI สร้าง TOR ทั้ง 10 ข้อให้เลย**")
        project_desc = st.text_area(
            "รายละเอียดโครงการ",
            placeholder="เช่น: ต้องการจัดซื้อคอมพิวเตอร์สำหรับทำงานเอกสารทั่วไป จำนวน 10 เครื่อง งบประมาณ 500,000 บาท...",
            height=120,
            key="quick_desc"
        )
        quick_name = st.text_input("ชื่อโครงการ (ย่อ) *", key="q_name")
        quick_budget = st.number_input("วงเงินงบประมาณ (บาท)", min_value=0, step=10000, value=0, key="q_budget")
        
        p_name = quick_name
        p_type = "ซื้อ/จ้างทั่วไป"
        p_agency = "หน่วยงานภาครัฐ"
        p_budget = quick_budget
        p_criteria = "เกณฑ์ราคา"
    else:
        st.markdown("**📋 กรอกรายละเอียดฟอร์มแบบละเอียด**")
        p_name = st.text_input("ชื่อโครงการ / งานจัดซื้อจัดจ้าง *", placeholder="เช่น จัดซื้อคอมพิวเตอร์ หรือ จ้างสำรวจพื้นที่", key="detailed_name")
        
        col_form1, col_form2 = st.columns(2)
        with col_form1:
            p_type = st.selectbox("ประเภทงาน *", ["ซื้อ/จ้างทั่วไป", "จ้างที่ปรึกษา", "จ้างออกแบบหรือควบคุมงานก่อสร้าง", "จ้างก่อสร้าง", "จ้างสำรวจ/ศึกษา/วิจัย"], key="d_type")
            p_agency = st.text_input("หน่วยงาน / ส่วนราชการ", placeholder="เช่น กรมชลประทาน", key="d_agency")
        with col_form2:
            p_budget = st.number_input("วงเงินงบประมาณ (บาท) *", min_value=0, step=1000, value=0, key="d_budget")
            p_duration = st.number_input("ระยะเวลาดำเนินการ (วัน)", min_value=1, value=90, key="d_dur")
            
        p_criteria = st.radio("หลักเกณฑ์คัดเลือกข้อเสนอ", ["เกณฑ์ราคา", "เกณฑ์ราคาประกอบเกณฑ์อื่น"], horizontal=True, key="d_crit")
        project_desc = f"โครงการ: {p_name}, ประเภท: {p_type}, หน่วยงาน: {p_agency}, งบประมาณ: {p_budget} บาท, หลักเกณฑ์: {p_criteria}"

    if st.button("⚡ สร้างโครงร่าง TOR ทั้ง 10 ข้อ", type="primary", use_container_width=True):
        if not p_name:
            st.error("⚠️ กรุณาระบุชื่อโครงการก่อนเริ่มต้นทำงาน")
        else:
            st.session_state.meta_data = {
                "title": p_name, "agency": p_agency, "type": p_type, "budget": p_budget, "criteria": p_criteria
            }
            st.success(f"กำลังเริ่มประมวลผลโครงร่างโครงการด้วย Gemini: {p_name}")
            
            for i in range(1, 11):
                st.markdown(f"### ⚙️ กำลังร่าง ข้อ {i}: {TOR_TITLES[i]}")
                box_placeholder = st.empty()
                
                specific_prompt = (
                    f"จงเขียนเนื้อหาของขอบเขตของงาน (TOR) สำหรับโครงการ '{p_name}' "
                    f"เฉพาะในส่วนของ 'ข้อ {i} หัวข้อ: {TOR_TITLES[i]}' เท่านั้น "
                    f"โดยอ้างอิงจากข้อมูลบริบทโครงการดังนี้: {project_desc}"
                )
                generate_section_stream(specific_prompt, i, box_placeholder)
            st.balloons()

    # แสดงผลลัพธ์โครงร่าง
    if st.session_state.meta_data:
        st.divider()
        st.subheader("📊 สรุปผลลัพธ์โครงร่างเอกสาร TOR (ว.159)")
        
        meta_info = st.session_state.meta_data
        c1, c2, c3 = st.columns(3)
        c1.metric("💰 วงเงินงบประมาณ", f"{meta_info['budget']:,} บาท")
        c2.metric("📁 ประเภทงาน", meta_info['type'])
        c3.metric("⚖️ หลักเกณฑ์คัดเลือก", meta_info['criteria'])
        
        st.markdown("#### ⬇️ ส่งออกเอกสาร")
        dl_col1, dl_col2 = st.columns(2)
        
        all_text = f"ร่างขอบเขตของงาน (TOR) - {meta_info['title']}\n\n"
        for idx, ct in st.session_state.tor_sections.items():
            all_text += f"ข้อ {idx} {TOR_TITLES[idx]}\n{ct}\n\n"
            
        dl_col1.download_button(
            label="⬇️ ดาวน์โหลดเป็นไฟล์ .txt",
            data=all_text,
            file_name=f"TOR_{meta_info['title']}.txt",
            mime="text/plain",
            use_container_width=True
        )
        
        docx_buf = create_docx(
            meta_info['title'], meta_info['agency'], meta_info['type'], 
            meta_info['budget'], meta_info['criteria'], st.session_state.tor_sections
        )
        if docx_buf:
            dl_col2.download_button(
                label="📄 ดาวน์โหลดเป็นไฟล์ Word (.docx)",
                data=docx_buf,
                file_name=f"TOR_{meta_info['title']}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True
            )

        st.markdown("#### 📝 ตรวจสอบและแก้ไขเนื้อหารายข้อ")
        for i in range(1, 11):
            with st.expander(f"ข้อ {i}: {TOR_TITLES[i]}", expanded=True):
                current_val = st.session_state.tor_sections.get(i, "")
                updated_val = st.text_area(f"แก้ไขเนื้อหา ข้อ {i}", value=current_val, key=f"edit_sec_{i}", height=150, label_visibility="collapsed")
                st.session_state.tor_sections[i] = updated_val
                
                if st.button(f"✨ ให้ AI เขียนข้อ {i} ใหม่เฉพาะข้อ", key=f"regen_{i}"):
                    sub_placeholder = st.empty()
                    single_prompt = f"จงเขียนทบทวนปรับปรุงเนื้อหาเฉพาะ 'ข้อ {i} หัวข้อ: {TOR_TITLES[i]}' สำหรับโครงการ '{meta_info['title']}' ให้มีความละเอียดและสอดคล้องกับระเบียบราชการยิ่งขึ้น"
                    generate_section_stream(single_prompt, i, sub_placeholder)
                    st.rerun()


# ── แท็บที่ 2: PDF ANALYZER (วิเคราะห์ใบเสนอราคา/สเปคกลางห้ามล็อกสเปค) ──────
with tab_pdf_analyze:
    st.subheader("📂 อัปโหลดเอกสารสเปค/ใบเสนอราคา เพื่อวิเคราะห์ 'ร่างสเปคกลาง'")
    st.write("ระบบจะอ่านไฟล์ PDF ของแต่ละบริษัท คัดชื่อข้อมูลติดต่อออกอัตโนมัติ แล้วใช้ Gemini สรุปเกณฑ์เทคนิคห้ามใส่แบรนด์ตามหลักจัดซื้อจัดจ้าง")

    job_description_pdf = st.text_area(
        "ระบุลักษณะงานหรือวัตถุประสงค์ที่ต้องการนำไปใช้เพื่อตรวจเทียบ:",
        placeholder="เช่น ต้องการระบบคอมพิวเตอร์สำหรับการเรียนการสอนห้องปฏิบัติการคอมพิวเตอร์ จำนวน 40 เครื่อง...",
        key="pdf_job_desc"
    )

    uploaded_files = st.file_uploader(
        "เลือกไฟล์ PDF สเปคจากบริษัทต่างๆ (เลือกพร้อมกันตั้งแต่ 2 ไฟล์ขึ้นไป):", 
        type=["pdf"], 
        accept_multiple_files=True,
        key="pdf_uploader"
    )

    if uploaded_files:
        st.info(f"📁 อัปโหลดเอกสารเข้ามาทั้งหมด {len(uploaded_files)} บริษัท")
        for idx, file in enumerate(uploaded_files):
            st.write(f"• บริษัทที่ {idx+1}: {file.name}")

    if st.button("🚀 เริ่มวิเคราะห์และสรุปสเปคกลาง", type="primary", key="btn_pdf_analyze"):
        if not client:
            st.error("🚨 ไม่สามารถเริ่มทำงานได้ เนื่องจากระบบยังไม่ได้เชื่อมต่อกับ Gemini API Key กรุณาตั้งค่าคีย์ก่อนครับ")
        elif not job_description_pdf:
            st.warning("⚠️ กรุณากรอกรายละเอียดลักษณะงานที่ต้องการนำไปใช้ก่อนครับ")
        elif len(uploaded_files) < 2:
            st.warning("⚠️ กรุณาอัปโหลดเอกสารเปรียบเทียบอย่างน้อย 2 บริษัทขึ้นไป เพื่อหาจุดร่วมสเปคกลางครับ")
        else:
            with st.spinner(f"กำลังสแกนและลบข้อมูลความลับยื่นประมวลผลบนคลาวด์ Gemini..."):
                try:
                    all_companies_data_prompt = ""
                    for idx, file in enumerate(uploaded_files):
                        company_label = f"[COMPANY_{idx+1}]"
                        raw_text = extract_text_from_pdf(file)
                        clean_text = auto_censor_text(raw_text)
                        all_companies_data_prompt += f"\n--- ข้อมูลสเปคของ {company_label} ---\n"
                        all_companies_data_prompt += clean_text[:5000] + "\n"
                    
                    prompt = f"""
                    คุณคือผู้เชี่ยวชาญด้านการตรวจรับและจัดทำคุณลักษณะเฉพาะ (TOR Specialist) 
                    งานของคุณคือวิเคราะห์สเปคจากข้อเสนอที่ได้รับ ({len(uploaded_files)} บริษัท) แล้วสรุปเป็น 'ร่างสเปคกลาง' ที่ถูกต้องตามหลักกฎหมายจัดซื้อจัดจ้าง คือ **"ห้ามระบุชื่อยี่ห้อหรือรุ่นสินค้าเด็ดขาด"** แต่ให้ใช้เกณฑ์ทางเทคนิคที่ทุกบริษัทสามารถหาของมาสู้กันได้

                    [ลักษณะงานที่ผู้ใช้ต้องการ]:
                    {job_description_pdf}

                    [ข้อมูลเอกสารสเปคของทุกบริษัท]:
                    {all_companies_data_prompt}

                    กรุณาตอบกลับเป็นภาษาไทย โดยใช้รูปแบบ Markdown ที่กระชับ เป็นข้อๆ และเข้าใจง่ายที่สุด ดังนี้:

                    1. ## 📊 ตารางสรุปเปรียบเทียบสเปค (ทำเป็นตารางสั้นๆ สรุปเฉพาะจุดสำคัญ)
                    
                    2. ## 📋 ร่างสเปคกลาง (ข้อกำหนดขั้นต่ำที่โปร่งใสและแข่งขันได้จริง)
                    *สั่งห้ามระบุคำว่า Intel, AMD, NVIDIA, GeForce โดยเด็ดขาด* ให้เปลี่ยนคำสั่งดังนี้:
                    - CPU: ให้ใช้คำว่า "หน่วยประมวลผลกลาง ไม่น้อยกว่า X คอร์ X เธรด และมีความเร็วสัญญาณนาฬิกาขั้นต่ำ..."
                    - GPU: ให้ใช้คำว่า "หน่วยประมวลผลกราฟิกชนิดแยก (Dedicated GPU) มีหน่วยความจำไม่น้อยกว่า X GB"
                    - ส่วนอื่นๆ ให้ระบุเป็นค่าขั้นต่ำที่อย่างน้อย 3 รายผ่านเกณฑ์

                    3. ## 💡 ความเห็นกรรมการ (สรุปสั้น 3 บรรทัด)
                    - สเปคกลางนี้พอมั้ยกับงาน?
                    - จุดที่ควรระวังหรือควร upgrade เพิ่มเพื่อความคุ้มค่า (สรุปเป็นข้อสั้นๆ ห้ามยาว)
                    """
                    
                    # เรียกใช้งานผ่านโมเดล Gemini 2.5 Flash ตัวหลัก
                    response = client.models.generate_content(
                        model=MODEL_NAME,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            system_instruction="คุณคือผู้เชี่ยวชาญด้านกฎหมายพัสดุและขอบเขตสเปค TOR เครื่องคอมพิวเตอร์และอุปกรณ์เทคโนโลยีสารสนเทศ",
                            temperature=0.4
                        )
                    )
                    
                    st.success("✨ Gemini วิเคราะห์และจัดทำร่างสเปคกลางสำเร็จเรียบร้อย!")
                    st.markdown(response.text)
                    
                except Exception as e:
                    st.error(f"เกิดข้อผิดพลาดในการประมวลผลสเปคกลาง: {str(e)}")


# ── แท็บที่ 3: CENSOR TOOL (แอบตัดชื่อบริษัท/เบอร์โทรจำเพาะ) ────────────────
with tab_censor_tool:
    st.subheader("✂️ ระบบกรอกข้อมูลและตัดคำเพื่อปกป้องความลับเอกสาร")
    st.write("ฟังก์ชันเสริม: วางข้อความที่คัดลอกมาเพื่อตรวจสอบและแอบตัดชื่อบริษัท/เบอร์โทรศัพท์จำเพาะออก ก่อนเอาไปใช้งานต่อ")

    col_input1, col_input2 = st.columns(2)
    with col_input1:
        censor_company = st.text_input("ระบุชื่อบริษัทที่ต้องการแอบตัด (ถ้ามี)", placeholder="เช่น บริษัท เอบีซี จำกัด", key="c_comp")
    with col_input2:
        censor_phone = st.text_input("ระบุเบอร์โทรศัพท์จำเพาะที่ต้องการแอบตัด (ถ้ามี)", placeholder="เช่น 02-123-4567", key="c_phone")

    raw_text_input = st.text_area(
        "วางข้อความสเปคหรือเนื้อหา TOR ที่ต้องการให้ระบบกรองคำที่นี่:",
        placeholder="วางเนื้อหาที่นี่... ระบบจะตัดคำกรองอัตโนมัติด้วย Regex ร่วมกับเงื่อนไขด้านบนของคุณ",
        height=200,
        key="raw_censor_area"
    )

    if st.button("🧼 เริ่มตัดและเซนเซอร์ข้อมูล", type="primary", key="btn_censor_run"):
        if not raw_text_input:
            st.warning("⚠️ กรุณาวางข้อความก่อนกดยืนยันการตัดคำ")
        else:
            with st.spinner("กำลังดำเนินการกรองคำอันตรายออก..."):
                processed_output = auto_censor_text(
                    raw_text_input, 
                    custom_company=censor_company, 
                    custom_phone=censor_phone
                )
                st.success("🔒 ระบบแอบตัดข้อมูลส่วนบุคคลและข้อมูลติดต่ออกเรียบร้อย!")
                st.text_area("คัดลอกผลลัพธ์ไปใช้งานต่อได้ทันที:", value=processed_output, height=250, key="clean_output_area")


# ── แท็บที่ 4: SETUP & INFO (ตั้งค่า API และตารางอ้างอิง) ─────────────────
with tab_setup_info:
    col_setup, col_info = st.columns([1, 1])
    
    with col_setup:
        st.subheader("⚙️ การตั้งค่าการเชื่อมต่อ API ของ Gemini")
        st.markdown(
            """
            * **กรณีติดตั้งขึ้น Streamlit Cloud (แนะนำ):** นำ API Key ไปฝากไว้ที่เมนู **Advanced Settings > Secrets** บน Dashboard โดยใส่ชื่อตัวแปรดังนี้:
            ```toml
            GEMINI_API_KEY = "AIzaSyxxxxxxxxxxxx"
            ```
            * **กรณีทดสอบชั่วคราว:** กรอกคีย์ของคุณลงในช่องด้านล่างเพื่อใช้ในเซสชันนี้ได้เลย:
            """
        )
        user_key = st.text_input("ระบุ Gemini API Key (AIzaSy...) ", type="password", value=os.environ.get("GEMINI_API_KEY") if os.environ.get("GEMINI_API_KEY") else "", key="setup_key_input")
        if st.button("💾 บันทึก API Key เฉพาะเซสชันนี้", key="btn_save_key"):
            os.environ["GEMINI_API_KEY"] = user_key
            st.success("บันทึกคีย์เรียบร้อย! กำลังรีเฟรชหน้าเว็บเพื่อเปลี่ยนระบบเชื่อมต่อ")
            time.sleep(1)
            st.rerun()

    with col_info:
        st.subheader("📋 ตารางข้อมูล ว.159")
        st.caption("อ้างอิงโครงสร้าง ว.159 ทั้ง 10 ข้อหลัก")
        info_data = [
            {"หัวข้อ ว.159": "ข้อ 1", "ชื่อโครงร่างมาตรฐาน": TOR_TITLES[1], "คำอธิบายเบื้องต้น": "ความเป็นมาของโครงการ"},
            {"หัวข้อ ว.159": "ข้อ 2", "ชื่อโครงร่างมาตรฐาน": TOR_TITLES[2], "คำอธิบายเบื้องต้น": "วัตถุประสงค์ในการจัดซื้อจัดจ้าง"},
            {"หัวข้อ ว.159": "ข้อ 3", "ชื่อโครงร่างมาตรฐาน": TOR_TITLES[3], "คำอธิบายเบื้องต้น": "คุณสมบัติที่จำเป็นของผู้ยื่นข้อเสนอ"},
            {"หัวข้อ ว.159": "ข้อ 4", "ชื่อโครงร่างมาตรฐาน": TOR_TITLES[4], "คำอธิบายเบื้องต้น": "รายละเอียดคุณลักษณะเฉพาะพัสดุ"},
            {"หัวข้อ ว.159": "ข้อ 5", "ชื่อโครงร่างมาตรฐาน": TOR_TITLES[5], "คำอธิบายเบื้องต้น": "กำหนดระยะเวลาในการดำเนินโครงการ"},
            {"หัวข้อ ว.159": "ข้อ 6", "ชื่อโครงร่างมาตรฐาน": TOR_TITLES[6], "คำอธิบายเบื้องต้น": "เงื่อนไขการส่งมอบงานและการตรวจรับ"},
            {"หัวข้อ ว.159": "ข้อ 7", "ชื่อโครงร่างมาตรฐาน": TOR_TITLES[7], "คำอธิบายเบื้องต้น": "หลักเกณฑ์ในการพิจารณาคัดเลือก"},
            {"หัวข้อ ว.159": "ข้อ 8", "ชื่อโครงร่างมาตรฐาน": TOR_TITLES[8], "คำอธิบายเบื้องต้น": "เงื่อนไขอัตราค่าปรับกรณีล่าช้า"},
            {"หัวข้อ ว.159": "ข้อ 9", "ชื่อโครงร่างมาตรฐาน": TOR_TITLES[9], "คำอธิบายเบื้องต้น": "เงื่อนไขการรับประกันความชำรุดบกพร่อง"},
            {"หัวข้อ ว.159": "ข้อ 10", "ชื่อโครงร่างมาตรฐาน": TOR_TITLES[10], "คำอธิบายเบื้องต้น": "ข้อสงวนสิทธิ์ในการยื่นข้อเสนอและอื่นๆ"}
        ]
        st.table(info_data)
