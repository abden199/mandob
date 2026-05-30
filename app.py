# ==========================================
# نظام إدارة عهدة مناديب المشتريات
# Streamlit + SQLite + EasyOCR
# ==========================================

import streamlit as st
import sqlite3
import pandas as pd
import easyocr
from PIL import Image
import tempfile
from datetime import datetime

# ==========================================
# إعداد الصفحة
# ==========================================

st.set_page_config(
    page_title="إدارة عهدة المشتريات",
    layout="wide"
)

# ==========================================
# الاتصال بقاعدة البيانات SQLite
# ==========================================

conn = sqlite3.connect(
    "custody.db",
    check_same_thread=False
)

cursor = conn.cursor()

# ==========================================
# إنشاء الجداول
# ==========================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS delegates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE,
    balance REAL DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS invoices (
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
# دوال قاعدة البيانات
# ==========================================

def add_delegate(name, balance):
    cursor.execute(
        """
        INSERT OR IGNORE INTO delegates
        (name,balance)
        VALUES (?,?)
        """,
        (name, balance)
    )
    conn.commit()


def get_delegates():
    return pd.read_sql_query(
        "SELECT * FROM delegates",
        conn
    )


def get_delegate_balance(name):
    result = cursor.execute(
        """
        SELECT balance
        FROM delegates
        WHERE name=?
        """,
        (name,)
    ).fetchone()

    if result:
        return result[0]

    return 0


def add_invoice(
        delegate_name,
        invoice_total,
        tax_type,
        description,
        cost_center,
        invoice_text):

    cursor.execute(
        """
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
            invoice_total,
            tax_type,
            description,
            cost_center,
            invoice_text,
            datetime.now().strftime("%Y-%m-%d %H:%M")
        )
    )

    conn.commit()


def get_invoices():
    return pd.read_sql_query(
        "SELECT * FROM invoices",
        conn
    )


def reset_delegate_balance(name):
    cursor.execute(
        """
        UPDATE delegates
        SET balance=0
        WHERE name=?
        """,
        (name,)
    )
    conn.commit()


# ==========================================
# OCR باستخدام EasyOCR
# ==========================================

@st.cache_resource
def load_reader():
    return easyocr.Reader(['ar', 'en'])


reader = load_reader()


def extract_text_from_image(uploaded_file):
    """
    استخراج النص من صورة الفاتورة

    يتم استخدام EasyOCR المجاني
    لاستخراج النصوص العربية والإنجليزية
    """

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(uploaded_file.read())
        image_path = tmp.name

    result = reader.readtext(
        image_path,
        detail=0
    )

    return " ".join(result)


# ==========================================
# الذكاء الاصطناعي البسيط
# ==========================================

def suggest_cost_center(text):
    """
    دالة تصنيف تعتمد على الكلمات المفتاحية

    يمكن لاحقاً استبدالها بنموذج Transformers
    مجاني مثل:
    distilbert-base-uncased

    حالياً يتم تحليل النص المستخرج من OCR
    أو الوصف المدخل من المستخدم
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

        "الموارد البشرية": [
            "موظف",
            "توظيف",
            "تدريب",
            "دورات"
        ],

        "تقنية المعلومات": [
            "كمبيوتر",
            "لابتوب",
            "طابعة",
            "انترنت",
            "شبكة",
            "software"
        ],

        "المكاتب والإدارة": [
            "قرطاسية",
            "أوراق",
            "حبر",
            "ملفات"
        ],

        "الصيانة": [
            "صيانة",
            "إصلاح",
            "قطع غيار"
        ]
    }

    for center, keywords in rules.items():

        for keyword in keywords:

            if keyword.lower() in text:
                return center

    return "عام"


def suggest_description(text):

    text = text.lower()

    if "وقود" in text or "بنزين" in text:
        return "وقود سيارات"

    if "طابعة" in text:
        return "مستلزمات تقنية"

    if "قرطاسية" in text:
        return "مستلزمات مكتبية"

    if "صيانة" in text:
        return "أعمال صيانة"

    return "مصروف مشتريات"


# ==========================================
# عنوان التطبيق
# ==========================================

st.title("💰 نظام تصفية عهدة بستان العجوة")

# ==========================================
# التبويبات
# ==========================================

tab_delegate, tab_admin = st.tabs(
    [
        "👨‍💼 شاشة المندوب",
        "📊 لوحة الإدارة"
    ]
)

# ==========================================
# شاشة المندوب
# ==========================================

with tab_delegate:

    st.header("إدخال فاتورة جديدة")

    delegates_df = get_delegates()

    existing_names = delegates_df["name"].tolist()

    col1, col2 = st.columns(2)

    with col1:

        delegate_name = st.text_input(
            "اسم المندوب"
        )

    with col2:

        opening_balance = st.number_input(
            "رصيد العهدة",
            min_value=0.0,
            value=0.0
        )

    if delegate_name:

        add_delegate(
            delegate_name,
            opening_balance
        )

    uploaded_file = st.file_uploader(
        "رفع صورة الفاتورة",
        type=["jpg", "jpeg", "png"]
    )

    extracted_text = ""

    if uploaded_file:

        image = Image.open(uploaded_file)

        st.image(
            image,
            caption="الفاتورة"
        )

        extracted_text = extract_text_from_image(
            uploaded_file
        )

        st.success("تم استخراج النص")

        st.text_area(
            "النص المستخرج",
            extracted_text,
            height=150
        )

    suggested_desc = suggest_description(
        extracted_text
    )

    suggested_cc = suggest_cost_center(
        extracted_text
    )

    invoice_total = st.number_input(
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
        "البيان",
        value=suggested_desc
    )

    cost_center = st.text_input(
        "مركز التكلفة",
        value=suggested_cc
    )

    if st.button("حفظ الفاتورة"):

        add_invoice(
            delegate_name,
            invoice_total,
            tax_type,
            description,
            cost_center,
            extracted_text
        )

        st.success(
            "تم حفظ الفاتورة بنجاح"
        )

# ==========================================
# لوحة الإدارة
# ==========================================

with tab_admin:

    st.header("لوحة التحكم")

    delegates = get_delegates()
    invoices = get_invoices()

    if not invoices.empty:

        summary = invoices.groupby(
            "delegate_name"
        )["invoice_total"].sum().reset_index()

        summary.columns = [
            "المندوب",
            "المستهلك"
        ]

        balances = []

        for _, row in summary.iterrows():

            balance = get_delegate_balance(
                row["المندوب"]
            )

            balances.append(balance)

        summary["العهدة"] = balances

        summary["المتبقي"] = (
            summary["العهدة"]
            - summary["المستهلك"]
        )

        st.subheader(
            "ملخص العهد"
        )

        st.dataframe(
            summary,
            use_container_width=True
        )

    st.divider()

    st.subheader(
        "البحث والتصفية"
    )

    filter_delegate = st.selectbox(
        "المندوب",
        ["الكل"] +
        invoices["delegate_name"].unique().tolist()
        if not invoices.empty
        else ["الكل"]
    )

    filter_cc = st.selectbox(
        "مركز التكلفة",
        ["الكل"] +
        invoices["cost_center"].unique().tolist()
        if not invoices.empty
        else ["الكل"]
    )

    filtered_df = invoices.copy()

    if not invoices.empty:

        if filter_delegate != "الكل":
            filtered_df = filtered_df[
                filtered_df["delegate_name"]
                == filter_delegate
            ]

        if filter_cc != "الكل":
            filtered_df = filtered_df[
                filtered_df["cost_center"]
                == filter_cc
            ]

    st.dataframe(
        filtered_df,
        use_container_width=True
    )

    st.divider()

    st.subheader("تصفير العهدة")

    if not delegates.empty:

        selected_delegate = st.selectbox(
            "اختر المندوب",
            delegates["name"].tolist()
        )

        if st.button("تصفير العهدة"):

            reset_delegate_balance(
                selected_delegate
            )

            st.success(
                f"تم تصفير عهدة {selected_delegate}"
            )

# ==========================================
# إغلاق الاتصال
# ==========================================

# conn.close()
# يفضل ترك الاتصال مفتوحاً أثناء تشغيل Streamlit
