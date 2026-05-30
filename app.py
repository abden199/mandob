import streamlit as st
import sqlite3
import pandas as pd
import easyocr
import tempfile
from PIL import Image
from datetime import datetime

# =====================================================
# إعدادات الصفحة
# =====================================================

st.set_page_config(
    page_title="إدارة عهدة مناديب المشتريات",
    page_icon="💰",
    layout="wide"
)

# =====================================================
# قاعدة البيانات SQLite
# =====================================================

DB_NAME = "custody_management.db"


def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)


conn = get_connection()
cursor = conn.cursor()

# =====================================================
# إنشاء الجداول
# =====================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS delegates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE,
    custody_amount REAL DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    delegate_name TEXT,
    invoice_total REAL,
    tax_amount REAL,
    non_tax_amount REAL,
    description TEXT,
    cost_center TEXT,
    extracted_text TEXT,
    created_at TEXT
)
""")

conn.commit()

# =====================================================
# OCR باستخدام EasyOCR
# =====================================================

@st.cache_resource
def load_ocr():
    """
    تحميل نموذج OCR مرة واحدة فقط لتحسين الأداء
    """
    return easyocr.Reader(['ar', 'en'])

reader = load_ocr()


def extract_text_from_image(uploaded_file):
    """
    استخراج النصوص من صورة الفاتورة
    باستخدام EasyOCR المجاني مفتوح المصدر
    """

    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        tmp.write(uploaded_file.read())
        image_path = tmp.name

    results = reader.readtext(image_path)

    text = " ".join([item[1] for item in results])

    return text


# =====================================================
# الذكاء الاصطناعي البسيط (Keyword Matching)
# =====================================================

def suggest_cost_center(text):
    """
    دالة ذكاء اصطناعي بسيطة تعتمد على الكلمات المفتاحية.

    تقوم بتحليل النص المستخرج من الفاتورة أو البيان
    ثم تقترح مركز تكلفة مناسب.
    """

    text = text.lower()

    mapping = {

        "الحركة والنقل": [
            "وقود",
            "بنزين",
            "ديزل",
            "سيارة",
            "نقل",
            "fuel",
            "gasoline"
        ],

        "الصيانة": [
            "صيانة",
            "اصلاح",
            "قطع غيار",
            "maintenance",
            "repair"
        ],

        "المشتريات المكتبية": [
            "قرطاسية",
            "مكتب",
            "طابعة",
            "ورق",
            "حبر",
            "stationery",
            "printer"
        ],

        "الضيافة": [
            "قهوة",
            "شاي",
            "مياه",
            "ضيافة",
            "coffee",
            "tea"
        ],

        "تقنية المعلومات": [
            "لابتوب",
            "كمبيوتر",
            "شاشة",
            "software",
            "hardware",
            "network"
        ]
    }

    for center, keywords in mapping.items():
        for keyword in keywords:
            if keyword.lower() in text:
                return center

    return "أخرى"


# =====================================================
# دوال قاعدة البيانات
# =====================================================

def add_delegate(name, custody_amount):
    cursor.execute("""
        INSERT OR REPLACE INTO delegates(name,custody_amount)
        VALUES(?,?)
    """, (name, custody_amount))

    conn.commit()


def save_invoice(
        delegate_name,
        invoice_total,
        tax_amount,
        non_tax_amount,
        description,
        cost_center,
        extracted_text):

    cursor.execute("""
        INSERT INTO invoices(
            delegate_name,
            invoice_total,
            tax_amount,
            non_tax_amount,
            description,
            cost_center,
            extracted_text,
            created_at
        )
        VALUES(?,?,?,?,?,?,?,?)
    """, (
        delegate_name,
        invoice_total,
        tax_amount,
        non_tax_amount,
        description,
        cost_center,
        extracted_text,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()


def get_delegates():
    return pd.read_sql(
        "SELECT * FROM delegates",
        conn
    )


def get_invoices():
    return pd.read_sql(
        "SELECT * FROM invoices",
        conn
    )


# =====================================================
# عنوان التطبيق
# =====================================================

st.title("💰 نظام إدارة عهدة مناديب المشتريات")

tab1, tab2 = st.tabs([
    "👨‍💼 شاشة المندوب",
    "📊 لوحة تحكم الإدارة"
])

# =====================================================
# شاشة المندوب
# =====================================================

with tab1:

    st.header("إدخال فاتورة جديدة")

    with st.expander("إضافة أو تحديث مندوب"):

        delegate_name_setup = st.text_input(
            "اسم المندوب"
        )

        custody_amount = st.number_input(
            "قيمة العهدة",
            min_value=0.0,
            value=0.0
        )

        if st.button("حفظ بيانات المندوب"):

            if delegate_name_setup:
                add_delegate(
                    delegate_name_setup,
                    custody_amount
                )
                st.success("تم حفظ بيانات المندوب")

    st.divider()

    delegates_df = get_delegates()

    delegate_names = []

    if not delegates_df.empty:
        delegate_names = delegates_df["name"].tolist()

    delegate_name = st.selectbox(
        "اختر المندوب",
        options=delegate_names
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
            caption="صورة الفاتورة",
            use_container_width=True
        )

        with st.spinner("جاري قراءة الفاتورة..."):

            extracted_text = extract_text_from_image(
                uploaded_file
            )

        st.subheader("النص المستخرج")

        st.text_area(
            "",
            extracted_text,
            height=150
        )

    description = st.text_input(
        "البيان"
    )

    combined_text = (
        extracted_text + " " + description
    )

    suggested_center = suggest_cost_center(
        combined_text
    )

    invoice_total = st.number_input(
        "إجمالي الفاتورة",
        min_value=0.0
    )

    tax_amount = st.number_input(
        "المبلغ الضريبي",
        min_value=0.0
    )

    non_tax_amount = st.number_input(
        "المبلغ غير الضريبي",
        min_value=0.0
    )

    cost_center = st.text_input(
        "مركز التكلفة المقترح",
        value=suggested_center
    )

    if st.button("حفظ الفاتورة"):

        if delegate_name:

            save_invoice(
                delegate_name,
                invoice_total,
                tax_amount,
                non_tax_amount,
                description,
                cost_center,
                extracted_text
            )

            st.success("تم حفظ الفاتورة بنجاح")

        else:
            st.error("يرجى اختيار المندوب")

# =====================================================
# لوحة تحكم الإدارة
# =====================================================

with tab2:

    st.header("لوحة تحكم الإدارة")

    delegates = get_delegates()
    invoices = get_invoices()

    if not delegates.empty:

        summary = []

        for _, row in delegates.iterrows():

            name = row["name"]

            custody = row["custody_amount"]

            spent = invoices[
                invoices["delegate_name"] == name
            ]["invoice_total"].sum()

            remaining = custody - spent

            summary.append({
                "المندوب": name,
                "العهدة": custody,
                "المصروف": spent,
                "المتبقي": remaining
            })

        summary_df = pd.DataFrame(summary)

        st.subheader("ملخص العهد")

        st.dataframe(
            summary_df,
            use_container_width=True
        )

    st.divider()

    st.subheader("الفواتير")

    filter_delegate = st.selectbox(
        "تصفية حسب المندوب",
        ["الكل"] + (
            invoices["delegate_name"].unique().tolist()
            if not invoices.empty else []
        )
    )

    filter_cost_center = st.selectbox(
        "تصفية حسب مركز التكلفة",
        ["الكل"] + (
            invoices["cost_center"].unique().tolist()
            if not invoices.empty else []
        )
    )

    filtered = invoices.copy()

    if filter_delegate != "الكل":
        filtered = filtered[
            filtered["delegate_name"] ==
            filter_delegate
        ]

    if filter_cost_center != "الكل":
        filtered = filtered[
            filtered["cost_center"] ==
            filter_cost_center
        ]

    st.dataframe(
        filtered,
        use_container_width=True
    )

    if not invoices.empty:

        total_spent = invoices[
            "invoice_total"
        ].sum()

        st.metric(
            "إجمالي المصروف",
            f"{total_spent:,.2f}"
        )

# =====================================================
# إغلاق الاتصال عند انتهاء التطبيق
# =====================================================

# SQLite سيغلق الاتصال تلقائياً عند إغلاق التطبيق
