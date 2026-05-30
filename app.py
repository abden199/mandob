# -*- coding: utf-8 -*-

import streamlit as st
import sqlite3
import pandas as pd
import easyocr
from PIL import Image
import tempfile
from datetime import datetime
from io import BytesIO

# ==========================================
# إعداد الصفحة
# ==========================================

st.set_page_config(
    page_title="إدارة عهدة المشتريات",
    page_icon="💰",
    layout="wide"
)

# ==========================================
# قاعدة البيانات SQLite
# ==========================================

conn = sqlite3.connect("custody.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS delegates(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE,
    balance REAL DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS invoices(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    delegate_name TEXT,
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
# بيانات ابتدائية
# ==========================================

for name in ["ابو غزل", "ابو محمود"]:
    cursor.execute(
        "INSERT OR IGNORE INTO delegates(name,balance) VALUES (?,?)",
        (name, 10000)
    )

conn.commit()

# ==========================================
# OCR
# ==========================================

@st.cache_resource
def load_ocr():
    """
    تحميل نموذج EasyOCR مرة واحدة فقط
    """
    return easyocr.Reader(['ar', 'en'], gpu=False)

reader = load_ocr()

def extract_text_from_image(image):
    """
    استخراج النص من الفاتورة باستخدام OCR
    """
    results = reader.readtext(image)

    text = " ".join([item[1] for item in results])

    return text


# ==========================================
# ذكاء اصطناعي بسيط
# ==========================================

def suggest_cost_center(text):
    """
    دالة تصنيف تعتمد على الكلمات المفتاحية

    يمكن استبدالها مستقبلاً بنموذج
    Transformers مجاني مفتوح المصدر.

    تقوم بقراءة النص المستخرج من الفاتورة
    أو الوصف المدخل ثم تقترح مركز تكلفة.
    """

    text = text.lower()

    rules = {

        "الحركة والنقل": [
            "وقود",
            "بنزين",
            "ديزل",
            "سيارة",
            "نقل",
            "مركبة"
        ],

        "الصيانة": [
            "صيانة",
            "اصلاح",
            "قطع غيار",
            "ورشة"
        ],

        "المشتريات المكتبية": [
            "قرطاسية",
            "ورق",
            "طابعة",
            "حبر",
            "مكتبية"
        ],

        "الضيافة": [
            "قهوة",
            "شاي",
            "مطعم",
            "وجبات",
            "ضيافة"
        ]
    }

    for center, words in rules.items():

        for word in words:

            if word in text:
                return center

    return "أخرى"


# ==========================================
# دوال قاعدة البيانات
# ==========================================

def get_delegates():

    return pd.read_sql(
        "SELECT * FROM delegates",
        conn
    )


def add_delegate(name):

    try:
        cursor.execute(
            "INSERT INTO delegates(name,balance) VALUES (?,?)",
            (name, 10000)
        )

        conn.commit()

    except:
        pass


def add_invoice(
        delegate_name,
        total,
        tax_type,
        description,
        cost_center,
        invoice_text):

    cursor.execute("""
    INSERT INTO invoices(
    delegate_name,
    invoice_total,
    tax_type,
    description,
    cost_center,
    invoice_text,
    created_at
    )
    VALUES (?,?,?,?,?,?,?)
    """,

    (
        delegate_name,
        total,
        tax_type,
        description,
        cost_center,
        invoice_text,
        datetime.now().strftime("%Y-%m-%d %H:%M")
    )
    )

    cursor.execute("""
    UPDATE delegates
    SET balance = balance - ?
    WHERE name = ?
    """,

    (
        total,
        delegate_name
    )
    )

    conn.commit()


def reset_balance(delegate_name):

    cursor.execute("""
    UPDATE delegates
    SET balance = 10000
    WHERE name = ?
    """,

    (delegate_name,)
    )

    conn.commit()


# ==========================================
# Tabs
# ==========================================

tab1, tab2 = st.tabs(
    [
        "👨‍💼 شاشة المندوب",
        "📊 لوحة الإدارة"
    ]
)

# ===================================================
# شاشة المندوب
# ===================================================

with tab1:

    st.header("إدخال فاتورة جديدة")

    delegates_df = get_delegates()

    delegate_names = delegates_df["name"].tolist()

    selected_delegate = st.selectbox(
        "اسم المندوب",
        delegate_names
    )

    st.subheader("إضافة مندوب جديد")

    new_delegate = st.text_input(
        "اسم المندوب الجديد"
    )

    if st.button("إضافة المندوب"):

        if new_delegate:

            add_delegate(new_delegate)

            st.success("تمت الإضافة")

            st.rerun()

    uploaded_file = st.file_uploader(
        "رفع صورة الفاتورة",
        type=["jpg", "jpeg", "png"]
    )

    extracted_text = ""

    if uploaded_file:

        image = Image.open(uploaded_file)

        st.image(image, width=300)

        with tempfile.NamedTemporaryFile(delete=False) as tmp:

            image.save(tmp.name)

            extracted_text = extract_text_from_image(
                tmp.name
            )

        st.text_area(
            "النص المستخرج",
            extracted_text,
            height=150
        )

    st.markdown("---")

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

    ai_text = description + " " + extracted_text

    suggested_center = suggest_cost_center(
        ai_text
    )

    cost_center = st.selectbox(
        "مركز التكلفة",
        [
            suggested_center,
            "الحركة والنقل",
            "الصيانة",
            "المشتريات المكتبية",
            "الضيافة",
            "أخرى"
        ]
    )

    st.info(
        f"اقتراح الذكاء الاصطناعي: {suggested_center}"
    )

    if st.button("حفظ الفاتورة"):

        add_invoice(
            selected_delegate,
            invoice_total,
            tax_type,
            description,
            cost_center,
            extracted_text
        )

        st.success(
            "تم حفظ الفاتورة بنجاح"
        )

# ===================================================
# لوحة الإدارة
# ===================================================

with tab2:

    st.header("لوحة التحكم")

    delegates = pd.read_sql(
        "SELECT * FROM delegates",
        conn
    )

    invoices = pd.read_sql(
        "SELECT * FROM invoices",
        conn
    )

    st.subheader("ملخص العهد")

    if not delegates.empty:

        total_balance = delegates["balance"].sum()

        total_spent = invoices["invoice_total"].sum() \
            if not invoices.empty else 0

        c1, c2 = st.columns(2)

        c1.metric(
            "إجمالي المصروف",
            f"{total_spent:,.2f}"
        )

        c2.metric(
            "إجمالي المتبقي",
            f"{total_balance:,.2f}"
        )

    st.markdown("---")

    st.subheader("تفاصيل المندوبين")

    summary = pd.read_sql("""

    SELECT
        d.name,
        10000 AS original_custody,
        IFNULL(
        SUM(i.invoice_total),0
        ) AS spent,
        d.balance

    FROM delegates d

    LEFT JOIN invoices i
    ON d.name=i.delegate_name

    GROUP BY d.name

    """, conn)

    st.dataframe(
        summary,
        use_container_width=True
    )

    st.markdown("---")

    st.subheader("تصفية الفواتير")

    delegate_filter = st.selectbox(
        "المندوب",
        ["الكل"] + delegates["name"].tolist()
    )

    cost_filter = st.selectbox(
        "مركز التكلفة",
        ["الكل"] +
        invoices["cost_center"].dropna()
        .unique()
        .tolist()
        if not invoices.empty
        else ["الكل"]
    )

    filtered = invoices.copy()

    if delegate_filter != "الكل":

        filtered = filtered[
            filtered["delegate_name"]
            == delegate_filter
        ]

    if cost_filter != "الكل":

        filtered = filtered[
            filtered["cost_center"]
            == cost_filter
        ]

    st.dataframe(
        filtered,
        use_container_width=True
    )

    # ======================================
    # تصدير Excel
    # ======================================

    output = BytesIO()

    with pd.ExcelWriter(
        output,
        engine="openpyxl"
    ) as writer:

        filtered.to_excel(
            writer,
            index=False,
            sheet_name="Invoices"
        )

    st.download_button(
        "📥 تصدير Excel",
        data=output.getvalue(),
        file_name="Invoices.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # ======================================
    # تصفير العهدة
    # ======================================

    st.markdown("---")

    st.subheader("تصفير عهدة مندوب")

    reset_delegate = st.selectbox(
        "اختر المندوب",
        delegates["name"].tolist()
    )

    if st.button("تصفير العهدة"):

        reset_balance(reset_delegate)

        st.success(
            "تم تصفير العهدة بنجاح"
        )

        st.rerun()
