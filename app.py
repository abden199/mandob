import streamlit as st
import sqlite3
import pandas as pd
import easyocr
import cv2
import numpy as np
import datetime

# -----------------------------------------
# 1. إعداد قاعدة البيانات وتوصيلها (SQLite)
# -----------------------------------------
def init_db():
    """دالة لإنشاء قاعدة البيانات والجداول المحمية إذا لم تكن موجودة مسبقاً"""
    conn = sqlite3.connect("bustan_alajwa.db", check_same_thread=False)
    cursor = conn.cursor()
    
    # جدول فواتير المناديب
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            delegate_name TEXT,
            invoice_total REAL,
            is_taxable TEXT,
            description TEXT,
            cost_center TEXT,
            date TEXT
        )
    ''')
    
    # جدول عهد المناديب (الرصيد الافتتاحي أو المضاف)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS balances (
            delegate_name TEXT PRIMARY KEY,
            total_allowance REAL
        )
    ''')
    conn.commit()
    return conn

conn = init_db()

# -----------------------------------------
# 2. دالة الذكاء الاصطناعي (OCR والتصنيف الذكي)
# -----------------------------------------
@st.cache_resource
def load_ocr_reader():
    """تحميل نموذج EasyOCR في الذاكرة المؤقتة لسرعة الأداء"""
    # يدعم قراءة النصوص باللغتين العربية والإنجليزية
    return easyocr.Reader(['ar', 'en'])

reader = load_ocr_reader()

def classify_cost_center(text):
    """
    دالة تعتمد على مطابقة الكلمات المفتاحية (Keyword Matching) 
    لتحليل النص المستخرج وتصنيف مركز التكلفة واقتراح البيان تلقائياً.
    """
    text = text.lower()
    
    # خريطة الكلمات المفتاحية لمراكز التكلفة
    categories = {
        "الحركة والنقل": ["وقود", "بنزين", "ديزل", "سيارة", "شحن", "توصيل", "صيانة سيارة", "زيت", "car", "fuel", "petrol"],
        "الضيافة والاستقبال": ["قهوة", "شاي", "ضيافة", "مطعم", "غداء", "عشاء", "ماء", "فندق", "coffee", "restaurant"],
        "أدوات مكتبية ومطبوعات": ["قرطاسية", "ورق", "قلم", "طباعة", "دفتر", "حبر", "paper", "print"],
        "صيانة وتشغيل": ["إصلاح", "صيانة", "كهرباء", "سباكة", "قطع غيار", "maintenance", "repair"]
    }
    
    for center, keywords in categories.items():
        for keyword in keywords:
            if keyword in text:
                return center, f"مشتريات/مصاريف تخص {center}"
                
    # في حال لم يتم التعرف على كلمات مفتاحية مألوفة
    return "عام / أخرى", "مصاريف عامة"

# -----------------------------------------
# 3. واجهة المستخدم الرسومية (Streamlit)
# -----------------------------------------
st.set_page_config(page_title="نظام مناديب بستان العجوة", layout="wide", page_icon="🌴")
st.title("🌴 نظام إدارة ومتابعة مناديب بستان العجوة")
st.markdown("---")

# إنشاء التبويبات لفصل شاشة المندوب عن الإدارة
tab_delegate, tab_admin = st.tabs(["📱 شاشة المندوب", "📊 لوحة تحكم الإدارة والمحاسب"])

# =========================================
# شاشة المندوب (حفظ الفواتير والبيانات)
# =========================================
with tab_delegate:
    st.header("تسجيل مصاريف وفواتير المندوب")
    
    # جلب مراكز التكلفة المتاحة في النظام لتقديمها كخيارات إضافية
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT cost_center FROM invoices")
    existing_centers = [row[0] for row in cursor.fetchall() if row[0]]
    if "الحركة والنقل" not in existing_centers:
        existing_centers.extend(["الحركة والنقل", "الضيافة والاستقبال", "أدوات مكتبية ومطبوعات", "عام / أخرى"])

    with st.form("delegate_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            delegate_name = st.text_input("اسم المندوب *").strip()
            invoice_total = st.number_input("إجمالي الفاتورة (شامل الضريبة إن وجدت) *", min_value=0.0, step=0.1)
            is_taxable = st.radio("نوع الفاتورة", ["ضريبية", "غير ضريبية"])
            
        with col2:
            uploaded_file = st.file_uploader("رفع صورة الفاتورة (OCR ذكي)", type=["jpg", "jpeg", "png"])
            
            # زر تشغيل الذكاء الاصطناعي لقراءة الصورة
            ocr_triggered = st.form_submit_button("🔍 قراءة الصورة بالذكاء الاصطناعي")
            
            ai_description = ""
            ai_cost_center = ""
            
            if uploaded_file and ocr_triggered:
                with st.spinner("جاري قراءة الفاتورة وتحليلها ذكياً..."):
                    try:
                        # تحويل الصورة المرفوعة إلى مصفوفة لقراءتها عبر OpenCV
                        file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
                        image = cv2.imdecode(file_bytes, 1)
                        
                        # استخراج النصوص من الصورة
                        results = reader.readtext(image, detail=0)
                        full_text = " ".join(results)
                        
                        if full_text.strip():
                            # تصنيف النص المقروء تلقائياً
                            ai_cost_center, ai_description = classify_cost_center(full_text)
                            st.success(f"🤖 تم تحليل الفاتورة بنجاح!")
                        else:
                            st.warning("لم يتم العثور على نصوص واضحة في الصورة، يرجى الإدخال يدوياً.")
                    except Exception as e:
                        st.error(f"حدث خطأ أثناء معالجة الصورة: {e}")

        st.markdown("### البيانات المستخرجة / الإدخال اليدوي")
        col3, col4 = st.columns(2)
        with col3:
            # يوضع النص المقترح من الذكاء الاصطناعي أو يكتبه المندوب يدوياً
            description = st.text_input("البيان (الوصف)", value=ai_description)
        with col4:
            # مركز التكلفة: يكتب يدوياً ويقترح الذكاء الاصطناعي بناءً على التحليل
            cost_center = st.text_input("مركز التكلفة (اكتب مركز جديد أو اتبع الاقتراح)", value=ai_cost_center)
            if cost_center:
                st.caption(f"مراكز التكلفة الحالية في النظام: {', '.join(existing_centers)}")

        # زر الحفظ النهائي في قاعدة البيانات
        submit_invoice = st.form_submit_button("💾 حفظ الفاتورة في النظام")
        
        if submit_invoice:
            if not delegate_name or invoice_total <= 0:
                st.error("يرجى إدخال اسم المندوب وقيمة الفاتورة بشكل صحيح.")
            else:
                # إذا لم يكتب المندوب مركز تكلفة، نقوم بعمل تصنيف تلقائي بناء على الوصف اليدوي
                if not cost_center:
                    cost_center, _ = classify_cost_center(description)
                
                current_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                
                # إدراج البيانات في الـ SQLite
                cursor.execute('''
                    INSERT INTO invoices (delegate_name, invoice_total, is_taxable, description, cost_center, date)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (delegate_name, invoice_total, is_taxable, description, cost_center, current_date))
                
                # التأكد من وجود المندوب في جدول العهد، إن لم يوجد ننشئ له رصيد صفر افتراضي
                cursor.execute("INSERT OR IGNORE INTO balances (delegate_name, total_allowance) VALUES (?, 0.0)", (delegate_name,))
                
                conn.commit()
                st.success(f"✅ تم حفظ فاتورة المندوب ({delegate_name}) بنجاح بقيمة {invoice_total} ريال تحت مركز تكلفة ({cost_center}).")

# =========================================
# شاشة المحاسب والإدارة (Dashboard)
# =========================================
with tab_admin:
    st.header("📊 لوحة تحكم الإدارة والمحاسبة")
    
    # --- قسم إدارة عهد المناديب ---
    st.subheader("💳 إدارة شحن وتصفير عهد المناديب")
    with st.expander("إضافة عهدة جديدة أو تصفير عهدة مندوب"):
        col_adm1, col_adm2, col_adm3 = st.columns(3)
        with col_adm1:
            adm_delegate = st.text_input("اسم المندوب لإدارة عهدته").strip()
        with col_adm2:
            amount_to_add = st.number_input("المبلغ المراد شحنه (ريال)", min_value=0.0, step=100.0)
            btn_add = st.button("➕ شحن العهدة")
        with col_adm3:
            st.write("إجراءات تصفير العهدة:")
            btn_reset = st.button("🔄 تصفير عهدة المندوب بالكامل")
            
        cursor = conn.cursor()
        if btn_add and adm_delegate:
            cursor.execute("SELECT total_allowance FROM balances WHERE delegate_name = ?", (adm_delegate,))
            row = cursor.fetchone()
            if row:
                new_balance = row[0] + amount_to_add
                cursor.execute("UPDATE balances SET total_allowance = ? WHERE delegate_name = ?", (new_balance, adm_delegate))
            else:
                cursor.execute("INSERT INTO balances (delegate_name, total_allowance) VALUES (?, ?)", (adm_delegate, amount_to_add))
            conn.commit()
            st.success(f"تمت إضافة {amount_to_add} ريال إلى عهدة المندوب {adm_delegate}")
            
        if btn_reset and adm_delegate:
            # تصفير العهدة يعني جعل الرصيد المتاح مساوياً لصفر وحذف فواتيره السابقة إذا لزم، أو فقط تصفير الرصيد المصروف
            cursor.execute("UPDATE balances SET total_allowance = 0 WHERE delegate_name = ?", (adm_delegate,))
            cursor.execute("DELETE FROM invoices WHERE delegate_name = ?", (adm_delegate,))
            conn.commit()
            st.warning(f"⚠️ تم تصفير عهدة وحذف فواتير المندوب {adm_delegate} بالكامل.")

    st.markdown("---")
    
    # --- جلب البيانات لعرض الداشبورد ---
    df_invoices = pd.read_sql_query("SELECT * FROM invoices", conn)
    df_balances = pd.read_sql_query("SELECT * FROM balances", conn)
    
    # حساب ملخص المناديب المالي
    summary_data = []
    for index, row in df_balances.iterrows():
        name = row['delegate_name']
        allowance = row['total_allowance']
        # حساب المستهلك من جدول الفواتير
        used = df_invoices[df_invoices['delegate_name'] == name]['invoice_total'].sum()
        remaining = allowance - used
        summary_data.append({
            "المندوب": name,
            "إجمالي العهدة المصروفة": allowance,
            "المبالغ المستهلكة": used,
            "الرصيد المتبقي": remaining
        })
    df_summary = pd.DataFrame(summary_data)
    
    # عرض الـ Cards الإجمالية للنظام
    st.subheader("📈 ملخص مالي عام")
    col_card1, col_card2, col_card3 = st.columns(3)
    if not df_summary.empty:
        col_card1.metric("إجمالي العهد المشحونة", f"{df_summary['إجمالي العهدة المصروفة'].sum():,.2f} ريال")
        col_card2.metric("إجمالي المصاريف المستهلكة", f"{df_summary['المبالغ المستهلكة'].sum():,.2f} ريال", delta_color="inverse")
        col_card3.metric("إجمالي المتبقي في الصناديق", f"{df_summary['الرصيد المتبقي'].sum():,.2f} ريال")
    else:
        st.info("لا توجد بيانات عهد مسجلة حالياً.")

    # عرض جدول عهد المناديب
    if not df_summary.empty:
        st.write("#### جدول عهد ومصاريف المناديب التفصيلي:")
        st.dataframe(df_summary, use_container_width=True)

    st.markdown("---")
    
    # --- قسم الفلاتر والبحث في الفواتير ---
    st.subheader("🔍 استعراض وتصفية الفواتير الصادرة")
    
    if not df_invoices.empty:
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            filter_delegate = st.selectbox("تصفية حسب المندوب", ["الكل"] + list(df_invoices['delegate_name'].unique()))
        with col_f2:
            filter_center = st.selectbox("تصفية حسب مركز التكلفة", ["الكل"] + list(df_invoices['cost_center'].unique()))
            
        # تطبيق الفلترة
        filtered_df = df_invoices.copy()
        if filter_delegate != "الكل":
            filtered_df = filtered_df[filtered_df['delegate_name'] == filter_delegate]
        if filter_center != "الكل":
            filtered_df = filtered_df[filtered_df['cost_center'] == filter_center]
            
        # إعادة ترتيب وتسمية الأعمدة للعرض بشكل احترافي بالمظهر العربي
        filtered_df_view = filtered_df.rename(columns={
            "id": "رقم الفاتورة",
            "delegate_name": "اسم المندوب",
            "invoice_total": "المبلغ (ريال)",
            "is_taxable": "النوع",
            "description": "البيان",
            "cost_center": "مركز التكلفة",
            "date": "التاريخ والوقت"
        })
        
        st.dataframe(filtered_df_view, use_container_width=True)
        
        # تصدير البيانات إلى ملف CSV
        csv = filtered_df_view.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 تصدير الفواتير المفلترة إلى Excel / CSV",
            data=csv,
            file_name=f"fawateer_report_{datetime.date.today()}.csv",
            mime='text/csv',
        )
    else:
        st.info("لا توجد فواتير مرفوعة في النظام حتى الآن.")
