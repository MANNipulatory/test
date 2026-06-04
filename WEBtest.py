import streamlit as st
from google import genai
import pypdf
import re

# 1. ตั้งค่าหน้าเว็บสตรีมลิต (แถบไตเติ้ลและเลย์เอาต์)
st.set_page_config(page_title="AI วิเคราะห์ TOR - Cloud Version", layout="wide")

# 2. ตรวจสอบและเชื่อมต่อ API Key ผ่านระบบ Secrets ของ Streamlit หลังบ้าน (เพื่อความปลอดภัย)
if "GEMINI_API_KEY" in st.secrets and st.secrets["GEMINI_API_KEY"]:
    # หากอยู่บน Cloud ระบบจะดึงคีย์จาก Secrets อัตโนมัติ
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
else:
    # เผื่อกรณีที่คุณเอาไปรันเทสในเครื่องคอมตัวเองก่อน สามารถใส่คีย์ตรงนี้ชั่วคราวได้
    # แต่ตอนอัปโหลดขึ้น GitHub แนะนำให้ปล่อยเป็นค่าว่างไว้ครับ
    LOCAL_KEY = "" 
    if LOCAL_KEY:
        client = genai.Client(api_key=LOCAL_KEY)
    else:
        st.sidebar.warning("🔒 ตรวจไม่พบ API Key ในระบบหลังบ้าน")
        st.sidebar.info("หากรันในเครื่องตัวเอง กรุณาใส่คีย์ในโค้ด (LOCAL_KEY) หรือหากขึ้น Cloud ให้ตั้งค่าในระบบ Secrets ของ Streamlit ครับ")
        client = None

# ส่วนหัวของหน้าเว็บ
st.title("🛡️ ระบบ AI วิเคราะห์ TOR และสร้างสเปคกลาง")
st.write("เวอร์ชันรองรับหลายบริษัทและปกป้องข้อมูลความลับ (ระบบจะแอบตัดข้อมูลส่วนตัวออกอัตโนมัติก่อนส่งให้ AI)")

# ฟังก์ชันสำหรับอ่านข้อความจากไฟล์ PDF
def extract_text_from_pdf(uploaded_file):
    pdf_reader = pypdf.PdfReader(uploaded_file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text() or ""
    return text

# ฟังก์ชันเซนเซอร์ข้อมูลอัตโนมัติ (Data Anonymization)
def auto_censor_text(text):
    if not text:
        return ""
    # 1. เซนเซอร์เบอร์โทรศัพท์อัตโนมัติด้วย Regex
    text = re.sub(r'\b\d{2,3}-\d{3}-\d{4}\b|\b\d{2,3}-\d{4}-\d{4}\b|\b\d{9,10}\b', "[PHONE_NUMBER_HIDDEN]", text)
    # 2. เซนเซอร์อีเมลอัตโนมัติ
    text = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', "[EMAIL_HIDDEN]", text)
    # 3. เซนเซอร์ลิงก์เว็บไซต์บริษัท
    text = re.sub(r'https?://[^\s<>"]+|www\.[^\s<>"]+', "[WEBSITE_HIDDEN]", text)
    return text

# 3. ส่วนรับข้อมูลลักษณะงานจากผู้ใช้
job_description = st.text_area(
    "ระบุลักษณะงานหรือวัตถุประสงค์ที่ต้องการนำไปใช้:",
    placeholder="เช่น ต้องการระบบคอมพิวเตอร์สำหรับการเรียนการสอนห้องปฏิบัติการคอมพิวเตอร์ จำนวน 40 เครื่อง..."
)

st.markdown("---")

# 4. ช่องอัปโหลดไฟล์แบบหลายไฟล์พร้อมกัน (Multiple Files Upload)
st.subheader("📂 อัปโหลดเอกสารสเปค/ใบเสนอราคาจากบริษัทต่างๆ")
uploaded_files = st.file_uploader(
    "เลือกไฟล์ PDF สเปคจากบริษัทต่างๆ (สามารถเลือกพร้อมกันหลายๆ ไฟล์ได้เลย)", 
    type=["pdf"], 
    accept_multiple_files=True
)

# แสดงรายชื่อไฟล์ที่อัปโหลดเข้ามาให้ผู้ใช้ตรวจทาน
if uploaded_files:
    st.info(f"📁 อัปโหลดเอกสารเข้ามาทั้งหมด {len(uploaded_files)} บริษัท")
    for idx, file in enumerate(uploaded_files):
        st.write(f"• บริษัทที่ {idx+1}: {file.name}")

st.markdown("---")

# 5. ปุ่มเริ่มทำงานและประมวลผล
if st.button("🚀 เริ่มวิเคราะห์และสรุปสเปคกลาง", type="primary"):
    if client is None:
        st.error("🚨 ไม่สามารถเริ่มทำงานได้ เนื่องจากระบบยังไม่ได้เชื่อมต่อกับ Gemini API Key กรุณาตั้งค่าคีย์หลังบ้านก่อนครับ")
    elif not job_description:
        st.warning("⚠️ กรุณากรอกรายละเอียดลักษณะงานที่ต้องการนำไปใช้ก่อนครับ")
    elif len(uploaded_files) < 2:
        st.warning("⚠️ กรุณาอัปโหลดเอกสารเปรียบเทียบอย่างน้อย 2 บริษัทขึ้นไป เพื่อให้ระบบหาจุดร่วมของสเปคกลางได้ครับ")
    else:
        with st.spinner(f"กำลังสแกนและเซนเซอร์ข้อมูลความลับจากทั้ง {len(uploaded_files)} บริษัท เพื่อส่งให้ AI วิเคราะห์..."):
            try:
                # ตัวแปรสำหรับรวมข้อความของทุกบริษัทเข้าด้วยกัน
                all_companies_data_prompt = ""
                
                # ลูปอ่านไฟล์และเซนเซอร์ข้อมูลทีละไฟล์อัตโนมัติ
                for idx, file in enumerate(uploaded_files):
                    company_label = f"[COMPANY_{idx+1}]"
                    
                    # อ่านข้อความดิบจาก PDF
                    raw_text = extract_text_from_pdf(file)
                    
                    # เซนเซอร์ข้อมูลติดต่ออัตโนมัติในเครื่องเซิร์ฟเวอร์ก่อนส่งขึ้นคลาวด์ AI
                    clean_text = auto_censor_text(raw_text)
                    
                    # นำมารวมกันในฟอร์แมตโครงสร้างเพื่อเตรียมส่งให้ AI
                    all_companies_data_prompt += f"\n--- ข้อมูลสเปคของ {company_label} ---\n"
                    # จำกัดความยาวต่อหนึ่งบริษัทเพื่อไม่ให้ยาวเกินโควตารุ่นฟรี (ตัดเอา 5,000 ตัวอักษรแรก)
                    all_companies_data_prompt += clean_text[:5000] + "\n"
                
                # ออกแบบ Prompt สั่งการ AI อย่างละเอียด
                # 📜 ปรับ Prompt ใหม่: เน้นกระชับ ตัดยี่ห้อ ห้ามล็อกสเปค
                prompt = f"""
                คุณคือผู้เชี่ยวชาญด้านการตรวจรับและจัดทำคุณลักษณะเฉพาะ (TOR Specialist) 
                งานของคุณคือวิเคราะห์สเปคจากข้อเสนอที่ได้รับ ({len(uploaded_files)} บริษัท) แล้วสรุปเป็น 'ร่างสเปคกลาง' ที่ถูกต้องตามหลักกฎหมายจัดซื้อจัดจ้าง คือ **"ห้ามระบุชื่อยี่ห้อหรือรุ่นสินค้าเด็ดขาด"** แต่ให้ใช้เกณฑ์ทางเทคนิคที่ทุกบริษัทสามารถหาของมาสู้กันได้

                [ลักษณะงานที่ผู้ใช้ต้องการ]:
                {job_description}

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
                # เรียกใช้งานโมเดลราคาประหยัดประสิทธิภาพสูงของค่าย Google
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt,
                )
                
                # แสดงผลลัพธ์บนหน้าจอเว็บ
                st.success("✨ AI วิเคราะห์และจัดทำร่างสเปคกลางสำเร็จเรียบร้อย!")
                st.markdown(response.text)
                
            except Exception as e:
                st.error(f"เกิดข้อผิดพลาดในการประมวลผล: {str(e)}")
