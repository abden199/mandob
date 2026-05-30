# -*- coding: utf-8 -*-

import streamlit as st
import sqlite3
import pandas as pd
import easyocr
from PIL import Image
from datetime import datetime
import tempfile
import os

# =====================================================
# إعداد الصفحة
# =====================================================

st.set_page_config(
    page_title="نظام متابعة مناديب بستان العجوة",
    layout="wide"
)

# =====================================================
# قاعدة البيانات SQLite
# =====================================================

DB_NAME = "delegates.db"


def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)


conn = get_connection()
cursor = conn.cursor()


def create_tables():
    """
    إنشاء الجداول عند التشغيل لأول مرة
    """

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS delegates(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        custody REAL DEFAULT 0
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS invoices(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        delegate_name TEXT,
        amount REAL,
        tax_type TEXT,
        description TEXT,
        cost_center TEXT,
        invoice_text TEXT,
        created_at TEXT
    )
    """)

    conn.commit()


create_tables()

# =====================================================
# OCR - قراءة الفواتير
# =====================================================

@st.cache_resource
def load_reader():
    """
    تحميل EasyOCR مرة واحدة فقط
    """
    return easyocr.Reader(['ar', 'en'])


reader = load_reader()


def extract_text_from_invoice(image):
    """
    استخراج النص من صورة الفاتورة
    """

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            image.save(tmp.name)

            results = reader.readtext(tmp.name)

            text = " ".join([item[1] for item in results])

        os.remove(tmp.name)

        return text

    except Exception as e:
        return f"OCR Error: {str(e)}"


# =====================================================
# الذكاء الاصطناعي المبسط
# =====================================================

def suggest_cost_center(text):
    """
    تصنيف مركز التكلفة بناء على الكلمات المفتاحية

    يمكن لاحقاً استبدالها بنموذج Transformers
    """

    text = text.lower()

    rules = {
        "الحركة والنقل": [
            "وقود",
            "بنزين",
            "ديزل",
            "سيارة",
            "نقل",
            "محطة"
        ],

        "الضيافة": [
            "مطعم",
            "قهوة",
            "شاي",
            "ضيافة",
            "بوفيه"
        ],

        "المشتريات": [
            "مستلزمات",
            "أدوات",
            "معدات",
            "شراء"
        ],

        "الصيانة": [
            "صيانة",
            "اصلاح",
            "ورشة",
            "قطع غيار"
        ],

        "الاتصالات": [
            "جوال",
            "هاتف",
            "انترنت",
            "اتصالات"
        ]
    }

    for center, words in rules.items():

        for word in words:

            if word.lower() in text:
                return center

    return "عام"


# =====================================================
# دوال المندوبين
# =====================================================

def add_delegate(name, custody):

    try:
        cursor.execute("""
        INSERT INTO delegates(name,custody)
        VALUES (?,?)
        """, (name, custody))

        conn.commit()

    except:
        pass


def get_delegates():

    return pd.read_sql_query(
        "SELECT * FROM delegates",
        conn
    )


def reset_custody(delegate_name):

    cursor.execute("""
    UPDATE delegates
    SET custody=0
    WHERE name=?
    """, (delegate_name,))

    conn.commit()


# =====================================================
# دوال الفواتير
# =====================================================

def add_invoice(
        delegate_name,
        amount,
        tax_type,
        description,
        cost_center,
        invoice_text):

    cursor.execute("""
    INSERT INTO invoices(
        delegate_name,
        amount,
        tax_type,
        description,
        cost_center,
        invoice_text,
        created_at
    )
    VALUES (?,?,?,?,?,?,?)
    """, (
        delegate_name,
        amount,
        tax_type,
        description,
        cost_center,
        invoice_text,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()


def get_invoices():

    return pd.read_sql_query(
        "SELECT * FROM invoices",
        conn
    )


# =====================================================
# واجهة التطبيق
# =====================================================

st.title("🌴 نظام متابعة مناديب بستان العجوة")

tab1, tab2 = st.tabs([
    "👨‍💼 شاشة المندوب",
    "📊 لوحة الإدارة"
])

# =====================================================
# شاشة المندوب
# =====================================================

with tab1:

    st.header("إدخال فاتورة")

    st.subheader("إضافة مندوب")

    col1, col2 = st.columns(2)

    with col1:
        new_delegate = st.text_input("اسم المندوب")

    with col2:
        custody_amount = st.number_input(
            "العهدة المبدئية",
            min_value=0.0,
            value=0.0
        )

    if st.button("إضافة المندوب"):

        if new_delegate:
            add_delegate(
                new_delegate,
                custody_amount
            )
            st.success("تم إضافة المندوب")

    delegates_df = get_delegates()

    delegate_list = delegates_df["name"].tolist()

    if len(delegate_list) > 0:

        delegate = st.selectbox(
            "اختر المندوب",
            delegate_list
        )

        uploaded_file = st.file_uploader(
            "رفع صورة الفاتورة",
            type=["png", "jpg", "jpeg"]
        )

        extracted_text = ""

        if uploaded_file:

            image = Image.open(uploaded_file)

            st.image(
                image,
                caption="الفاتورة"
            )

            with st.spinner("استخراج النص..."):

                extracted_text = extract_text_from_invoice(
                    image
                )

            st.text_area(
                "النص المستخرج",
                extracted_text,
                height=150
            )

        amount = st.number_input(
            "إجمالي الفاتورة",
            min_value=0.0
        )

        tax_type = st.radio(
            "نوع الفاتورة",
            [
                "ضريبية",
                "غير ضريبية"
            ]
        )

        description = st.text_input(
            "البيان"
        )

        ai_text = (
            extracted_text + " " +
            description
        )

        suggested_center = suggest_cost_center(
            ai_text
        )

        st.info(
            f"اقتراح الذكاء الاصطناعي: {suggested_center}"
        )

        cost_center = st.text_input(
            "مركز التكلفة",
            value=suggested_center
        )

        if st.button("حفظ الفاتورة"):

            add_invoice(
                delegate,
                amount,
                tax_type,
                description,
                cost_center,
                extracted_text
            )

            st.success(
                "تم حفظ الفاتورة بنجاح"
            )

# =====================================================
# لوحة الإدارة
# =====================================================

with tab2:

    st.header("لوحة المحاسب والإدارة")

    delegates_df = get_delegates()
    invoices_df = get_invoices()

    if not delegates_df.empty:

        st.subheader("ملخص العهد")

        summary = []

        for _, row in delegates_df.iterrows():

            delegate_name = row["name"]

            consumed = 0

            if not invoices_df.empty:

                consumed = invoices_df[
                    invoices_df["delegate_name"]
                    == delegate_name
                ]["amount"].sum()

            remaining = (
                row["custody"]
                - consumed
            )

            summary.append({
                "المندوب": delegate_name,
                "العهدة": row["custody"],
                "المستهلك": consumed,
                "المتبقي": remaining
            })

        summary_df = pd.DataFrame(summary)

        st.dataframe(
            summary_df,
            use_container_width=True
        )

        st.subheader("تصفير العهدة")

        delegate_reset = st.selectbox(
            "اختر المندوب",
            delegates_df["name"]
        )

        if st.button("تصفير العهدة"):

            reset_custody(
                delegate_reset
            )

            st.success(
                "تم تصفير العهدة"
            )

    st.divider()

    st.subheader("الفواتير")

    if not invoices_df.empty:

        col1, col2 = st.columns(2)

        with col1:

            selected_delegate = st.selectbox(
                "تصفية حسب المندوب",
                ["الكل"] +
                invoices_df["delegate_name"]
                .unique()
                .tolist()
            )

        with col2:

            selected_center = st.selectbox(
                "تصفية حسب مركز التكلفة",
                ["الكل"] +
                invoices_df["cost_center"]
                .unique()
                .tolist()
            )

        filtered = invoices_df.copy()

        if selected_delegate != "الكل":

            filtered = filtered[
                filtered["delegate_name"]
                == selected_delegate
            ]

        if selected_center != "الكل":

            filtered = filtered[
                filtered["cost_center"]
                == selected_center
            ]

        st.dataframe(
            filtered,
            use_container_width=True
        )

        csv = filtered.to_csv(
            index=False
        ).encode("utf-8-sig")

        st.download_button(
            "📥 تصدير CSV",
            csv,
            file_name="invoices.csv",
            mime="text/csv"
        )

    else:

        st.warning(
            "لا توجد فواتير مسجلة"
        )

# =====================================================
# إغلاق الاتصال
# =====================================================

conn.commit()
