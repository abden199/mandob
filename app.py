
import streamlit as st
import sqlite3
import pandas as pd
import hashlib
from datetime import datetime

try:
    import easyocr
    from PIL import Image
    OCR_AVAILABLE = True
except Exception:
    OCR_AVAILABLE = False

st.set_page_config(page_title="بستان العجوة", layout="wide")

# ---------------- Database ----------------
conn = sqlite3.connect("delegates.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users(
id INTEGER PRIMARY KEY AUTOINCREMENT,
username TEXT UNIQUE,
password TEXT,
role TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS delegates(
id INTEGER PRIMARY KEY AUTOINCREMENT,
name TEXT UNIQUE,
balance REAL DEFAULT 0
)
""")

cur.execute("""
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

def hash_password(p):
    return hashlib.sha256(p.encode()).hexdigest()

cur.execute("INSERT OR IGNORE INTO users(username,password,role) VALUES(?,?,?)",
            ("admin", hash_password("admin123"), "accountant"))
cur.execute("INSERT OR IGNORE INTO users(username,password,role) VALUES(?,?,?)",
            ("user1", hash_password("user123"), "delegate"))
conn.commit()

def auth(u,p):
    cur.execute("SELECT username,role FROM users WHERE username=? AND password=?",
                (u, hash_password(p)))
    return cur.fetchone()

def add_delegate(name):
    cur.execute("INSERT OR IGNORE INTO delegates(name,balance) VALUES(?,0)", (name,))
    conn.commit()

def add_invoice(d,total,tax,desc,cc,text):
    cur.execute("""
    INSERT INTO invoices(delegate_name,invoice_total,tax_type,description,cost_center,invoice_text,created_at)
    VALUES(?,?,?,?,?,?,?)
    """,(d,total,tax,desc,cc,text,datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()

def invoices_df():
    return pd.read_sql_query("SELECT * FROM invoices ORDER BY id DESC", conn)

def delegates_df():
    return pd.read_sql_query("SELECT * FROM delegates", conn)

def suggest_cost_center(text):
    text = text.lower()
    rules = {
        "الحركة والنقل":["وقود","بنزين","ديزل","سيارة"],
        "الضيافة":["مطعم","قهوة","شاي","وجبة"],
        "الصيانة":["صيانة","إصلاح","قطع غيار"],
        "المشتريات":["معدات","أدوات","قرطاسية"]
    }
    for center, words in rules.items():
        for w in words:
            if w.lower() in text:
                return center
    return "عام"

@st.cache_resource
def get_reader():
    if OCR_AVAILABLE:
        return easyocr.Reader(['ar','en'])
    return None

def extract_text(image):
    if not OCR_AVAILABLE:
        return ""
    reader = get_reader()
    result = reader.readtext(image)
    return " ".join([r[1] for r in result])

# ---------------- Session ----------------
for k,v in {
    "logged_in":False,
    "username":"",
    "role":""
}.items():
    if k not in st.session_state:
        st.session_state[k]=v

# ---------------- Login ----------------
if not st.session_state.logged_in:
    st.title("🔐 تسجيل الدخول")
    u = st.text_input("اسم المستخدم")
    p = st.text_input("كلمة المرور", type="password")
    if st.button("دخول"):
        user = auth(u,p)
        if user:
            st.session_state.logged_in=True
            st.session_state.username=user[0]
            st.session_state.role=user[1]
            st.rerun()
        else:
            st.error("بيانات غير صحيحة")
    st.stop()

c1,c2 = st.columns([8,2])
with c1:
    st.write(f"المستخدم: {st.session_state.username} | الدور: {st.session_state.role}")
with c2:
    if st.button("تسجيل الخروج"):
        st.session_state.logged_in=False
        st.session_state.username=""
        st.session_state.role=""
        st.rerun()

st.title("🌴 نظام متابعة مناديب بستان العجوة")

# ---------------- Delegate Screen ----------------
def delegate_screen():
    st.subheader("إضافة فاتورة")

    if st.session_state.role == "delegate":
        delegate_name = st.session_state.username
        st.info(f"المندوب: {delegate_name}")
    else:
        delegate_name = st.text_input("اسم المندوب")

    uploaded = st.file_uploader("صورة الفاتورة", type=["jpg","jpeg","png"])
    extracted = ""

    if uploaded and OCR_AVAILABLE:
        image = Image.open(uploaded)
        st.image(image, width=300)
        extracted = extract_text(image)
        st.text_area("النص المستخرج", extracted, height=120)

    total = st.number_input("إجمالي الفاتورة", min_value=0.0)
    tax = st.radio("نوع الفاتورة", ["ضريبية","غير ضريبية"])
    desc = st.text_area("البيان")

    cc = st.text_input(
        "مركز التكلفة",
        value=suggest_cost_center(desc + " " + extracted)
    )

    if st.button("حفظ الفاتورة"):
        if not delegate_name:
            st.error("أدخل اسم المندوب")
        else:
            add_delegate(delegate_name)
            add_invoice(delegate_name,total,tax,desc,cc,extracted)
            st.success("تم حفظ الفاتورة")

# ---------------- Admin Dashboard ----------------
def admin_screen():
    st.subheader("لوحة الإدارة")

    inv = invoices_df()
    dels = delegates_df()

    st.metric("إجمالي المصروف", 0 if inv.empty else round(inv["invoice_total"].sum(),2))

    fd = st.selectbox("تصفية حسب المندوب",
                      ["الكل"] + ([] if inv.empty else inv["delegate_name"].dropna().unique().tolist()))
    fc = st.selectbox("تصفية حسب مركز التكلفة",
                      ["الكل"] + ([] if inv.empty else inv["cost_center"].dropna().unique().tolist()))

    data = inv.copy()
    if not data.empty:
        if fd != "الكل":
            data = data[data["delegate_name"] == fd]
        if fc != "الكل":
            data = data[data["cost_center"] == fc]

    st.dataframe(data, use_container_width=True)

    if not data.empty:
        csv = data.to_csv(index=False).encode("utf-8-sig")
        st.download_button("تصدير CSV", csv, "invoices.csv", "text/csv")

    st.subheader("المناديب")
    st.dataframe(dels, use_container_width=True)

# ---------------- Role Routing ----------------
if st.session_state.role == "accountant":
    t1,t2 = st.tabs(["شاشة المندوب","لوحة الإدارة"])
    with t1:
        delegate_screen()
    with t2:
        admin_screen()
else:
    delegate_screen()
