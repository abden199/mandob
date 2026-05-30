import streamlit as st
import sqlite3
import pandas as pd
import easyocr
from PIL import Image
from datetime import datetime
import io

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

conn = sqlite3.connect("delegates.db", check_same_thread=False)
cursor = conn.cursor()

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

# =====================================================
# دوال قاعدة البيانات
# =====================================================

def add_delegate(name):
    try:
        cursor.execute(
            "INSERT INTO delegates(name,balance) VALUES(?,?)",
            (name, 0)
        )
        conn.commit()
    except:
        pass


def get_delegates():
    return pd.read_sql_query(
        "SELECT * FROM delegates",
        conn
    )


def add_invoice(
        delegate_name,
        invoice_total,
        tax_type,
        description,
        cost_center,
        invoice_text
):
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
        VALUES(?,?,?,?,?,?,?)
    """,
    (
        delegate_name,
        invoice_total,
        tax_type,
        description,
        cost_center,
        invoice_text,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()


def get_invoices():
    return pd.read_sql_query(
        "SELECT * FROM invoices ORDER BY id DESC",
        conn
    )


def update_balance(delegate_name, amount):
    cursor.execute("""
        UPDATE delegates
        SET balance = balance + ?
        WHERE name = ?
    """,
    (amount, delegate_name))

    conn.commit()


def reset_balance(delegate_name):
    cursor.execute("""
        UPDATE delegates
        SET balance = 0
        WHERE name = ?
    """,
    (delegate_name,))
    conn.commit()

# =====================================================
# OCR باستخدام EasyOCR
# =====================================================

@st.cache_resource
def load_reader():
    return easyocr.Reader(['ar', 'en'])

reader = load_reader()

def extract_text_from_image(image):
    """
    استخراج النص من صورة الفاتورة
    """
    try:
        result = reader.readtext(image)
        text = " ".join([item[1] for item in result])
        return text
    except Exception as e:
        return ""

# =====================================================
# ذكاء اصطناعي بسيط لتحديد مركز التكلفة
# =====================================================

def suggest_cost_center(text):

    """
    تصنيف مركز التكلفة
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
            "كفر",
            "زيت"
        ],

        "الضيافة": [
            "مطعم",
            "قهوة",
            "شاي",
            "وجبة",
            "بوفيه"
        ],

        "الصيانة": [
            "صيانة",
            "إصلاح",
            "قطع غيار",
            "كهرباء",
            "سباكة"
        ],

        "المشتريات": [
            "أدوات",
            "معدات",
            "مستلزمات",
            "قرطاسية"
        ]
    }

    for center, keywords in mapping.items():
        for keyword in keywords:
            if keyword.lower() in text:
                return center

    return "عام"

# =====================================================
# العنوان
# =====================================================

st.title("🌴 نظام متابعة مناديب بستان العجوة")

tab_delegate, tab_admin = st.tabs([
    "المندوب",
    "الإدارة والمحاسبة"
])

# =====================================================
# شاشة المندوب
# =====================================================

with tab_delegate:

    st.subheader("إضافة فاتورة")

    delegate_name = st.text_input(
        "اسم المندوب"
    )

    if delegate_name:
        add_delegate(delegate_name)

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
            width=400
        )

        with st.spinner("جاري قراءة الفاتورة..."):
            extracted_text = extract_text_from_image(image)

        st.text_area(
            "النص المستخرج",
            extracted_text,
            height=120
        )

    invoice_total = st.number_input(
        "إجمالي الفاتورة",
        min_value=0.0,
        step=1.0
    )

    tax_type = st.radio(
        "نوع الفاتورة",
        ["ضريبية", "غير ضريبية"]
    )

    description = st.text_area(
        "البيان"
    )

    suggested_center = suggest_cost_center(
        description + " " + extracted_text
    )

    cost_center = st.text_input(
        "مركز التكلفة",
        value=suggested_center
    )

    if st.button("حفظ الفاتورة"):

        if delegate_name == "":
            st.error("أدخل اسم المندوب")
        else:

            add_invoice(
                delegate_name,
                invoice_total,
                tax_type,
                description,
                cost_center,
                extracted_text
            )

            update_balance(
                delegate_name,
                invoice_total
            )

            st.success("تم حفظ الفاتورة بنجاح")

# =====================================================
# لوحة الإدارة
# =====================================================

with tab_admin:

    st.subheader("لوحة التحكم")

    delegates_df = get_delegates()
    invoices_df = get_invoices()

    total_consumed = 0

    if not invoices_df.empty:
        total_consumed = invoices_df[
            "invoice_total"
        ].sum()

    col1, col2 = st.columns(2)

    with col1:
        st.metric(
            "عدد المناديب",
            len(delegates_df)
        )

    with col2:
        st.metric(
            "إجمالي المصروف",
            round(total_consumed, 2)
        )

    st.divider()

    st.subheader("العهد الحالية")

    if not delegates_df.empty:

        report_rows = []

        for _, row in delegates_df.iterrows():

            consumed = invoices_df[
                invoices_df["delegate_name"] == row["name"]
            ]["invoice_total"].sum()

            report_rows.append({
                "المندوب": row["name"],
                "إجمالي المستهلك": consumed,
                "الرصيد الحالي": row["balance"]
            })

        report_df = pd.DataFrame(report_rows)

        st.dataframe(
            report_df,
            use_container_width=True
        )

    st.divider()

    st.subheader("الفواتير")

    filter_delegate = st.selectbox(
        "تصفية حسب المندوب",
        ["الكل"] +
        invoices_df["delegate_name"].unique().tolist()
        if not invoices_df.empty
        else ["الكل"]
    )

    filter_center = st.selectbox(
        "تصفية حسب مركز التكلفة",
        ["الكل"] +
        invoices_df["cost_center"].unique().tolist()
        if not invoices_df.empty
        else ["الكل"]
    )

    filtered_df = invoices_df.copy()

    if not filtered_df.empty:

        if filter_delegate != "الكل":
            filtered_df = filtered_df[
                filtered_df["delegate_name"]
                == filter_delegate
            ]

        if filter_center != "الكل":
            filtered_df = filtered_df[
                filtered_df["cost_center"]
                == filter_center
            ]

    st.dataframe(
        filtered_df,
        use_container_width=True
    )

    # =================================================
    # تصدير CSV
    # =================================================

    if not filtered_df.empty:

        csv = filtered_df.to_csv(
            index=False
        ).encode("utf-8-sig")

        st.download_button(
            label="📥 تصدير CSV",
            data=csv,
            file_name="invoices.csv",
            mime="text/csv"
        )

    st.divider()

    st.subheader("تصفير عهدة مندوب")

    if not delegates_df.empty:

        delegate_to_reset = st.selectbox(
            "اختر المندوب",
            delegates_df["name"].tolist()
        )

        if st.button("تصفير العهدة"):

            reset_balance(
                delegate_to_reset
            )

            st.success(
                f"تم تصفير عهدة {delegate_to_reset}"
            )

            st.rerun()
