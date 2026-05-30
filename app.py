# ==========================================
# تطبيق متابعة مناديب بستان العجوة
# Streamlit + SQLite + EasyOCR
# ==========================================

import streamlit as st
import sqlite3
import pandas as pd
import easyocr
from PIL import Image
import tempfile
import os
from datetime import datetime

# ==========================================
# إعداد الصفحة
# ==========================================

st.set_page_config(
    page_title="نظام متابعة المناديب",
    page_icon="📋",
    layout="wide"
)

# ==========================================
# قاعدة البيانات SQLite
# ==========================================

DB_NAME = "mandobeen.db"


def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)


conn = get_connection()
cursor = conn.cursor()

# ==========================================
# إنشاء الجداول
# ==========================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS representatives(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE,
    balance REAL DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS invoices(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rep_name TEXT,
    invoice_total REAL,
    tax_type TEXT,
    description TEXT,
    cost_center TEXT,
    invoice_text TEXT,
    created_at TEXT
)
""")

conn.commit()

# ==========================================
# OCR باستخدام EasyOCR
# ==========================================

reader = easyocr.Reader(['ar', 'en'], gpu=False)


def extract_text_from_image(uploaded_file):
    """
    استخراج النص من صورة الفاتورة
    باستخدام EasyOCR المجاني
    """

    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        tmp.write(uploaded_file.getvalue())
        temp_path = tmp.name

    results = reader.readtext(temp_path)

    extracted_text = " ".join([item[1] for item in results])

    os.remove(temp_path)

    return extracted_text


# ==========================================
# الذكاء الاصطناعي البسيط
# Keyword Matching
# ==========================================

def suggest_cost_center(text):
    """
    تصنيف البيان واقتراح مركز التكلفة
    اعتماداً على الكلمات المفتاحية
    """

    text = text.lower()

    mapping = {
        "الحركة والنقل": [
            "وقود",
            "بنزين",
            "ديزل",
            "سيارة",
            "نقل",
            "زيت"
        ],

        "المشتريات": [
            "شراء",
            "مستلزمات",
            "مواد",
            "أدوات",
            "معدات"
        ],

        "الصيانة": [
            "صيانة",
            "اصلاح",
            "كهرباء",
            "سباكة",
            "قطع غيار"
        ],

        "الاتصالات": [
            "اتصالات",
            "انترنت",
            "جوال",
            "شريحة"
        ],

        "الضيافة": [
            "قهوة",
            "شاي",
            "مياه",
            "ضيافة",
            "مطعم"
        ]
    }

    for center, keywords in mapping.items():
        for word in keywords:
            if word in text:
                return center

    return "عام"


# ==========================================
# دوال قاعدة البيانات
# ==========================================

def add_representative(name, balance):

    cursor.execute("""
    INSERT OR IGNORE INTO representatives(name,balance)
    VALUES(?,?)
    """, (name, balance))

    conn.commit()


def add_invoice(
        rep_name,
        total,
        tax_type,
        description,
        cost_center,
        invoice_text
):

    cursor.execute("""
    INSERT INTO invoices(
    rep_name,
    invoice_total,
    tax_type,
    description,
    cost_center,
    invoice_text,
    created_at
    )
    VALUES(?,?,?,?,?,?,?)
    """,
                   (
                       rep_name,
                       total,
                       tax_type,
                       description,
                       cost_center,
                       invoice_text,
                       datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                   ))

    conn.commit()


def get_representatives():

    return pd.read_sql(
        "SELECT * FROM representatives",
        conn
    )


def get_invoices():

    return pd.read_sql(
        "SELECT * FROM invoices",
        conn
    )


def reset_balance(rep_name):

    cursor.execute("""
    UPDATE representatives
    SET balance=0
    WHERE name=?
    """, (rep_name,))

    conn.commit()


# ==========================================
# التبويبات
# ==========================================

tab1, tab2 = st.tabs(
    ["👨‍💼 شاشة المندوب", "📊 لوحة تحكم الإدارة"]
)

# ==========================================
# شاشة المندوب
# ==========================================

with tab1:

    st.header("إضافة فاتورة")

    rep_name = st.text_input("اسم المندوب")

    opening_balance = st.number_input(
        "العهدة الحالية",
        min_value=0.0,
        value=0.0
    )

    if st.button("حفظ المندوب"):

        add_representative(
            rep_name,
            opening_balance
        )

        st.success("تم حفظ المندوب")

    st.divider()

    uploaded_file = st.file_uploader(
        "رفع صورة الفاتورة",
        type=["jpg", "jpeg", "png"]
    )

    extracted_text = ""

    if uploaded_file:

        image = Image.open(uploaded_file)

        st.image(
            image,
            caption="صورة الفاتورة",
            use_container_width=True
        )

        with st.spinner("جاري قراءة الفاتورة..."):

            extracted_text = extract_text_from_image(
                uploaded_file
            )

        st.text_area(
            "النص المستخرج",
            extracted_text,
            height=150
        )

    invoice_total = st.number_input(
        "إجمالي الفاتورة",
        min_value=0.0
    )

    tax_type = st.radio(
        "نوع الفاتورة",
        ["ضريبية", "غير ضريبية"]
    )

    description = st.text_area(
        "البيان"
    )

    auto_center = suggest_cost_center(
        extracted_text + " " + description
    )

    cost_center = st.selectbox(
        "مركز التكلفة",
        [
            auto_center,
            "الحركة والنقل",
            "المشتريات",
            "الصيانة",
            "الاتصالات",
            "الضيافة",
            "عام"
        ]
    )

    st.info(
        f"اقتراح الذكاء الاصطناعي: {auto_center}"
    )

    if st.button("حفظ الفاتورة"):

        add_invoice(
            rep_name,
            invoice_total,
            tax_type,
            description,
            cost_center,
            extracted_text
        )

        st.success("تم حفظ الفاتورة")

# ==========================================
# لوحة الإدارة
# ==========================================

with tab2:

    st.header("لوحة التحكم")

    reps_df = get_representatives()
    invoices_df = get_invoices()

    # ======================
    # حساب المؤشرات
    # ======================

    if not reps_df.empty:

        summary = []

        for _, row in reps_df.iterrows():

            rep = row["name"]

            balance = row["balance"]

            consumed = invoices_df[
                invoices_df["rep_name"] == rep
            ]["invoice_total"].sum()

            remaining = balance - consumed

            summary.append({
                "المندوب": rep,
                "العهدة": balance,
                "المستهلك": consumed,
                "المتبقي": remaining
            })

        summary_df = pd.DataFrame(summary)

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "إجمالي العهد",
            round(summary_df["العهدة"].sum(), 2)
        )

        col2.metric(
            "إجمالي المصروف",
            round(summary_df["المستهلك"].sum(), 2)
        )

        col3.metric(
            "إجمالي المتبقي",
            round(summary_df["المتبقي"].sum(), 2)
        )

        st.subheader("ملخص المناديب")

        st.dataframe(
            summary_df,
            use_container_width=True
        )

        st.subheader("تصفير العهدة")

        selected_rep = st.selectbox(
            "اختر المندوب",
            reps_df["name"]
        )

        if st.button("تصفير العهدة"):

            reset_balance(selected_rep)

            st.success(
                f"تم تصفير عهدة {selected_rep}"
            )

    # ======================
    # الفلاتر
    # ======================

    st.subheader("الفواتير")

    if not invoices_df.empty:

        rep_filter = st.selectbox(
            "فلترة حسب المندوب",
            ["الكل"] +
            list(invoices_df["rep_name"].unique())
        )

        center_filter = st.selectbox(
            "فلترة حسب مركز التكلفة",
            ["الكل"] +
            list(invoices_df["cost_center"].unique())
        )

        filtered = invoices_df.copy()

        if rep_filter != "الكل":
            filtered = filtered[
                filtered["rep_name"] == rep_filter
            ]

        if center_filter != "الكل":
            filtered = filtered[
                filtered["cost_center"] == center_filter
            ]

        st.dataframe(
            filtered,
            use_container_width=True
        )

        # ======================
        # تصدير CSV
        # ======================

        csv = filtered.to_csv(
            index=False
        ).encode("utf-8-sig")

        st.download_button(
            label="📥 تصدير CSV",
            data=csv,
            file_name="invoices.csv",
            mime="text/csv"
        )

    else:

        st.warning("لا توجد فواتير حالياً")
