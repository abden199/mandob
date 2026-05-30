import streamlit as st
import sqlite3
import pandas as pd
import easyocr
import cv2
import numpy as np
import datetime
import hashlib

# -----------------------------------------
# 1. إعداد قاعدة البيانات والتشفير (SQLite)
# -----------------------------------------
def make_hashes(password):
    """تشفير كلمة المرور لحمايتها في قاعدة البيانات"""
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_password):
    """التحقق من صحة كلمة المرور المدخلة"""
    if make_hashes(password) == hashed_password:
        return True
    return False

def init_db():
    """إنشاء قاعدة البيانات والجداول وحساب المدير الافتراضي"""
    conn = sqlite3.connect("bustan_alajwa.db", check_same_thread=False)
    cursor = conn.cursor()
    
    # جدول المستخدمين والصلاحيات
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT,
            role TEXT
        )
    ''')
    
    # إنشاء حساب المدير الافتراضي إذا لم يكن موجوداً مسبقاً
    # (admin / admin123)
    cursor.execute("SELECT * FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        hashed_admin_pass = make_hashes("admin123")
        cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", 
                       ("admin", hashed_admin_pass, "مدير"))
    
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
    
    # جدول عهد المناديب
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
    """تحميل نموذج EasyOCR لقراءة الفواتير باللغتين العربية والإنجليزية"""
    return easyocr.Reader(['ar', 'en'])

reader = load_ocr_reader()

def classify_cost_center(text):
    """تحليل الكلمات المفتاحية واقتراح مراكز التكلفة تلقائياً"""
    text = text.lower()
    categories = {
        "الحركة والنقل": ["وقود", "بنزين", "ديزل", "سيارة", "شحن", "توصيل", "صيانة سيارة", "زيت", "car", "fuel", "petrol"],
        "الضيافة والاستقبال": ["قهوة", "شاي", "ضيافة", "مطعم", "غداء", "عشاء", "ماء", "فندق", "coffee", "restaurant"],
        "أدوات مكتبية ومطبوعات": ["قرطاسية", "ورق", "قلم", "طباعة", "دفتر", "حبر", "paper", "print"],
        "صيانة وتشغيل": ["إصلاح", "صيانة", "كهرباء", "سباكة", "قطع غيار", "maintenance", "repair"]
    }
    for center, keywords in categories.items():
        for keyword in keywords:
            if keyword in text:
                return center, f"مشتريات تخص {center}"
    return "عام / أخرى", "مصاريف عامة"

# -----------------------------------------
# 3. إدارة نظام تسجيل الدخول والجلسات
# -----------------------------------------
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['username'] = ""
    st.session_state['role'] = ""

st.set_page_config(page_title="نظام بستان العجوة", layout="wide", page_icon="🌴")

# واجهة تسجيل الدخول في حال لم يكن المستخدم مسجلاً
if not st.session_state['logged_in']:
    st.title("🌴 تسجيل الدخول - نظام بستان العجوة")
    st.markdown("---")
    
    with st.form("login_form"):
        username = st.text_input("اسم المستخدم").strip()
        password = st.text_input("كلمة المرور", type="password")
        login_btn = st.form_submit_button("تسجيل الدخول")
        
        if login_btn:
            cursor = conn.cursor()
            cursor.execute("SELECT password, role FROM users WHERE username = ?", (username,))
            user_record = cursor.fetchone()
            
            if user_record and check_hashes(password, user_record[0]):
                st.session_state['logged_in'] = True
                st.session_state['username'] = username
                st.session_state['role'] = user_record[1]
                st.success(f"مرحباً بك {username} (صلاحية: {user_record[1]})")
                st.rerun()
            else:
                st.error("اسم المستخدم أو كلمة المرور غير صحيحة")

# واجهة النظام الرئيسية بعد تسجيل الدخول بنجاح
else:
    # شريط علوي لمعلومات المستخدم وتسجيل الخروج
    col_user, col_logout = st.columns([8, 2])
    with col_user:
        st.write(f"👤 المستخدم الحالي: **{st.session_state['username']}** | الصلاحية: **{st.session_state['role']}**")
    with col_logout:
        if st.button("🚪 تسجيل الخروج"):
            st.session_state['logged_in'] = False
            st.session_state['username'] = ""
            st.session_state['role'] = ""
            st.rerun()
            
    st.title("🌴 نظام إدارة ومتابعة مناديب بستان العجوة")
    st.markdown("---")

    # تحديد التبويبات المتاحة بناءً على نوع الصلاحية
    user_role = st.session_state['role']
    
    tabs_to_show = []
    if user_role == "مدير":
        tabs_to_show = ["📱 شاشة المندوب", "📊 لوحة تحكم المحاسب", "⚙️ إدارة المستخدمين"]
    elif user_role == "محاسب":
        tabs_to_show = ["📊 لوحة تحكم المحاسب"]
    elif user_role == "مندوب":
        tabs_to_show = ["📱 شاشة المندوب"]
        
    active_tabs = st.tabs(tabs_to_show)

    # =========================================================
    # أ. شاشة المندوب (متاحة للمندوب والمدير)
    # =========================================================
    if "📱 شاشة المندوب" in tabs_to_show:
        idx = tabs_to_show.index("📱 شاشة المندوب")
        with active_tabs[idx]:
            st.header("تسجيل مصاريف وفواتير المندوب")
            
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT cost_center FROM invoices")
            existing_centers = [row[0] for row in cursor.fetchall() if row[0]]
            
            with st.form("delegate_form", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    # إذا كان المسجل مندوب، يتم تثبيت اسمه تلقائياً، وإذا كان مديراً يمكنه الكتابة
                    if user_role == "مندوب":
                        delegate_name = st.text_input("اسم المندوب *", value=st.session_state['username'], disabled=True)
                    else:
                        delegate_name = st.text_input("اسم المندوب *").strip()
                        
                    invoice_total = st.number_input("إجمالي الفاتورة (شامل الضريبة) *", min_value=0.0, step=0.1)
                    is_taxable = st.radio("نوع الفاتورة", ["ضريبية", "غير ضريبية"])
                    
                with col2:
                    uploaded_file = st.file_uploader("رفع صورة الفاتورة (OCR ذكي)", type=["jpg", "jpeg", "png"])
                    ocr_triggered = st.form_submit_button("🔍 قراءة الصورة بالذكاء الاصطناعي")
                    
                    ai_description, ai_cost_center = "", ""
                    if uploaded_file and ocr_triggered:
                        with st.spinner("جاري قراءة الفاتورة وتحليلها ذكياً..."):
                            try:
                                file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
                                image = cv2.imdecode(file_bytes, 1)
                                results = reader.readtext(image, detail=0)
                                full_text = " ".join(results)
                                
                                if full_text.strip():
                                    ai_cost_center, ai_description = classify_cost_center(full_text)
                                    st.success("🤖 تم تحليل الفاتورة بنجاح!")
                                else:
                                    st.warning("لم يتم العثور على نصوص واضحة في الصورة.")
                            except Exception as e:
                                st.error(f"حدث خطأ أثناء معالجة الصورة: {e}")

                st.markdown("### البيانات المستخرجة / الإدخال اليدوي")
                col3, col4 = st.columns(2)
                with col3:
                    description = st.text_input("البيان (الوصف)", value=ai_description)
                with col4:
                    cost_center = st.text_input("مركز التكلفة (اكتب مركز جديد أو اتبع الاقتراح)", value=ai_cost_center)

                submit_invoice = st.form_submit_button("💾 حفظ الفاتورة في النظام")
                
                if submit_invoice:
                    if not delegate_name or invoice_total <= 0:
                        st.error("يرجى التأكد من تعبئة اسم المندوب وقيمة الفاتورة.")
                    else:
                        if not cost_center:
                            cost_center, _ = classify_cost_center(description)
                        
                        current_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                        cursor.execute('''
                            INSERT INTO invoices (delegate_name, invoice_total, is_taxable, description, cost_center, date)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (delegate_name, invoice_total, is_taxable, description, cost_center, current_date))
                        
                        cursor.execute("INSERT OR IGNORE INTO balances (delegate_name, total_allowance) VALUES (?, 0.0)", (delegate_name,))
                        conn.commit()
                        st.success(f"✅ تم حفظ فاتورة المندوب ({delegate_name}) بنجاح بقيمة {invoice_total} ريال.")

    # =========================================================
    # ب. لوحة تحكم المحاسب (متاحة للمحاسب والمدير)
    # =========================================================
    if "📊 لوحة تحكم المحاسب" in tabs_to_show:
        idx = tabs_to_show.index("📊 لوحة تحكم المحاسب")
        with active_tabs[idx]:
            st.header("📊 لوحة تحكم الإدارة والمحاسبة")
            
            # قسم إدارة عهد المناديب
            st.subheader("💳 إدارة شحن وتصفير عهد المناديب")
            with st.expander("إضافة عهدة جديدة أو تصفير عهدة مندوب"):
                col_adm1, col_adm2, col_adm3 = st.columns(3)
                with col_adm1:
                    adm_delegate = st.text_input("اسم المندوب لإدارة عهدته").strip()
                with col_adm2:
                    amount_to_add = st.number_input("المبلغ المراد شحنه (ريال)", min_value=0.0, step=100.0)
                    btn_add = st.button("➕ شحن العهدة")
                with col_adm3:
                    st.write("إجراءات التصفير:")
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
                    cursor.execute("UPDATE balances SET total_allowance = 0 WHERE delegate_name = ?", (adm_delegate,))
                    cursor.execute("DELETE FROM invoices WHERE delegate_name = ?", (adm_delegate,))
                    conn.commit()
                    st.warning(f"⚠️ تم تصفير عهدة وحذف فواتير المندوب {adm_delegate} بالكامل.")

            st.markdown("---")
            
            # جلب وعرض البيانات والتقارير الممالية
            df_invoices = pd.read_sql_query("SELECT * FROM invoices", conn)
            df_balances = pd.read_sql_query("SELECT * FROM balances", conn)
            
            summary_data = []
            for index, row in df_balances.iterrows():
                name = row['delegate_name']
                allowance = row['total_allowance']
                used = df_invoices[df_invoices['delegate_name'] == name]['invoice_total'].sum()
                remaining = allowance - used
                summary_data.append({
                    "المندوب": name, "إجمالي العهدة المصروفة": allowance, "المبالغ المستهلكة": used, "الرصيد Mتبقي": remaining
                })
            df_summary = pd.DataFrame(summary_data)
            
            st.subheader("📈 ملخص مالي عام")
            col_card1, col_card2, col_card3 = st.columns(3)
            if not df_summary.empty:
                col_card1.metric("إجمالي العهد المشحونة", f"{df_summary['إجمالي العهدة المصروفة'].sum():,.2f} ريال")
                col_card2.metric("إجمالي المصاريف المستهلكة", f"{df_summary['المبالغ المستهلكة'].sum():,.2f} ريال")
                col_card3.metric("إجمالي المتبقي في الصناديق", f"{df_summary['الرصيد Mتبقي'].sum():,.2f} ريال")
                st.dataframe(df_summary, use_container_width=True)
            else:
                st.info("لا توجد بيانات عهد مسجلة حالياً.")

            st.markdown("---")
            st.subheader("🔍 استعراض وتصفية الفواتير")
            if not df_invoices.empty:
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    filter_delegate = st.selectbox("تصفية حسب المندوب", ["الكل"] + list(df_invoices['delegate_name'].unique()))
                with col_f2:
                    filter_center = st.selectbox("تصفية حسب مركز التكلفة", ["الكل"] + list(df_invoices['cost_center'].unique()))
                    
                filtered_df = df_invoices.copy()
                if filter_delegate != "الكل":
                    filtered_df = filtered_df[filtered_df['delegate_name'] == filter_delegate]
                if filter_center != "الكل":
                    filtered_df = filtered_df[filtered_df['cost_center'] == filter_center]
                    
                filtered_df_view = filtered_df.rename(columns={
                    "id": "رقم الفاتورة", "delegate_name": "اسم المندوب", "invoice_total": "المبلغ (ريال)",
                    "is_taxable": "النوع", "description": "البيان", "cost_center": "مركز التكلفة", "date": "التاريخ والوقت"
                })
                st.dataframe(filtered_df_view, use_container_width=True)
                
                csv = filtered_df_view.to_csv(index=False).encode('utf-8-sig')
                st.download_button(label="📥 تصدير الفواتير المفلترة إلى CSV", data=csv, file_name="fawateer_report.csv", mime='text/csv')
            else:
                st.info("لا توجد فواتير مرفوعة حالياً.")

    # =========================================================
    # ج. شاشة إدارة المستخدمين (متاحة للمدير فقط)
    # =========================================================
    if "⚙️ إدارة المستخدمين" in tabs_to_show:
        idx = tabs_to_show.index("⚙️ إدارة المستخدمين")
        with active_tabs[idx]:
            st.header("⚙️ لوحة إدارة الحسابات والصلاحيات")
            
            col_u1, col_u2 = st.columns([1, 2])
            
            with col_u1:
                st.subheader("➕ إنشاء حساب جديد")
                with st.form("create_user_form", clear_on_submit=True):
                    new_username = st.text_input("اسم المستخدم الجديد *").strip()
                    new_password = st.text_input("كلمة المرور *", type="password")
                    new_role = st.selectbox("الصلاحية الممنوحة", ["مندوب", "محاسب", "مدير"])
                    submit_user = st.form_submit_button("إنشاء الحساب")
                    
                    if submit_user:
                        if not new_username or not new_password:
                            st.error("يرجى كتابة اسم المستخدم وكلمة المرور")
                        else:
                            cursor = conn.cursor()
                            cursor.execute("SELECT * FROM users WHERE username = ?", (new_username,))
                            if cursor.fetchone():
                                st.error("اسم المستخدم مسجل مسبقاً في النظام!")
                            else:
                                hashed_p = make_hashes(new_password)
                                cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", 
                                               (new_username, hashed_p, new_role))
                                conn.commit()
                                st.success(f"تم إنشاء حساب ({new_username}) بنجاح بصلاحية {new_role}")
                                st.rerun()
            
            with col_u2:
                st.subheader("📋 الحسابات المسجلة حالياً")
                df_users = pd.read_sql_query("SELECT username, role FROM users", conn)
                df_users_view = df_users.rename(columns={"username": "اسم المستخدم", "role": "الصلاحية"})
                st.dataframe(df_users_view, use_container_width=True)
                
                st.subheader("❌ حذف مستخدم")
                user_to_delete = st.selectbox("اختر الحساب المراد حذفه", [""] + list(df_users['username'].unique()))
                if st.button("حذف الحساب المحدد"):
                    if user_to_delete == "admin":
                        st.error("لا يمكن حذف حساب المدير الافتراضي الرئيسي!")
                    elif user_to_delete == st.session_state['username']:
                        st.error("لا يمكنك حذف حسابك الحالي الذي تستخدمه الآن!")
                    elif user_to_delete == "":
                        st.warning("يرجى اختيار مستخدم أولاً")
                    else:
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM users WHERE username = ?", (user_to_delete,))
                        conn.commit()
                        st.success(f"تم حذف الحساب {user_to_delete} بنجاح.")
                        st.rerun()
