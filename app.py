import streamlit as st
import sqlite3, hashlib
import pandas as pd
from datetime import datetime

try:
    import easyocr
    from PIL import Image
    OCR=True
except:
    OCR=False

st.set_page_config(page_title="بستان العجوة", layout="wide")

conn=sqlite3.connect("delegates.db",check_same_thread=False)
cur=conn.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS users(
id INTEGER PRIMARY KEY AUTOINCREMENT,
username TEXT UNIQUE,
password TEXT,
role TEXT)""")

cur.execute("""CREATE TABLE IF NOT EXISTS invoices(
id INTEGER PRIMARY KEY AUTOINCREMENT,
delegate_name TEXT,
invoice_total REAL,
tax_type TEXT,
description TEXT,
cost_center TEXT,
invoice_text TEXT,
created_at TEXT)""")
conn.commit()

def hp(p): return hashlib.sha256(p.encode()).hexdigest()

def init_admin():
    cur.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0]==0:
        cur.execute("INSERT INTO users(username,password,role) VALUES(?,?,?)",
                    ("admin",hp("admin123"),"accountant"))
        conn.commit()
init_admin()

def auth(u,p):
    cur.execute("SELECT username,role FROM users WHERE username=? AND password=?",(u,hp(p)))
    return cur.fetchone()

for k,v in {"logged_in":False,"username":"","role":""}.items():
    if k not in st.session_state: st.session_state[k]=v

if not st.session_state.logged_in:
    st.title("🔐 تسجيل الدخول")
    u=st.text_input("اسم المستخدم")
    p=st.text_input("كلمة المرور",type="password")
    if st.button("دخول"):
        x=auth(u,p)
        if x:
            st.session_state.logged_in=True
            st.session_state.username=x[0]
            st.session_state.role=x[1]
            st.rerun()
        st.error("بيانات غير صحيحة")
    st.stop()

st.sidebar.write(f"👤 {st.session_state.username}")
if st.sidebar.button("تسجيل الخروج"):
    st.session_state.clear()
    st.rerun()

def suggest(text):
    m={"الحركة والنقل":["وقود","بنزين","سيارة"],
       "الضيافة":["قهوة","مطعم","شاي"],
       "الصيانة":["صيانة","اصلاح"],
       "المشتريات":["معدات","أدوات"]}
    for c,ws in m.items():
        if any(w in text for w in ws): return c
    return "عام"

def extract(img):
    if not OCR: return ""
    reader=easyocr.Reader(['ar','en'])
    return " ".join([r[1] for r in reader.readtext(img)])

def delegate_page():
    st.header("شاشة المندوب")
    name=st.session_state.username if st.session_state.role=="delegate" else st.text_input("اسم المندوب")
    up=st.file_uploader("صورة فاتورة",type=["png","jpg","jpeg"])
    txt=""
    if up and OCR:
        img=Image.open(up)
        txt=extract(img)
        st.text_area("النص المستخرج",txt)
    total=st.number_input("إجمالي الفاتورة",0.0)
    tax=st.selectbox("نوع الفاتورة",["ضريبية","غير ضريبية"])
    desc=st.text_area("البيان")
    cc=st.text_input("مركز التكلفة",value=suggest(desc+" "+txt))
    if st.button("حفظ الفاتورة"):
        cur.execute("""INSERT INTO invoices(delegate_name,invoice_total,tax_type,description,cost_center,invoice_text,created_at)
                    VALUES(?,?,?,?,?,?,?)""",
                    (name,total,tax,desc,cc,txt,datetime.now().strftime("%Y-%m-%d %H:%M")))
        conn.commit()
        st.success("تم الحفظ")

def admin_page():
    st.header("لوحة الإدارة")
    inv=pd.read_sql_query("SELECT * FROM invoices ORDER BY id DESC",conn)
    st.metric("إجمالي المصروف",0 if inv.empty else inv.invoice_total.sum())
    st.dataframe(inv,use_container_width=True)

    if not inv.empty:
        st.download_button("تصدير CSV",inv.to_csv(index=False).encode("utf-8-sig"),"invoices.csv")

    st.subheader("إدارة المستخدمين")

    with st.expander("إضافة مستخدم"):
        u=st.text_input("اسم مستخدم جديد")
        p=st.text_input("كلمة مرور",type="password")
        r=st.selectbox("الصلاحية",["delegate","accountant"])
        if st.button("إضافة"):
            try:
                cur.execute("INSERT INTO users(username,password,role) VALUES(?,?,?)",(u,hp(p),r))
                conn.commit()
                st.success("تمت الإضافة")
            except Exception as e:
                st.error("المستخدم موجود")

    users=pd.read_sql_query("SELECT id,username,role FROM users",conn)
    st.dataframe(users,use_container_width=True)

    sel=st.selectbox("حذف مستخدم",users["username"])
    if st.button("حذف المستخدم"):
        if sel!="admin":
            cur.execute("DELETE FROM users WHERE username=?",(sel,))
            conn.commit()
            st.rerun()

    sel2=st.selectbox("إعادة تعيين كلمة المرور",users["username"],key="r")
    np=st.text_input("كلمة المرور الجديدة",type="password")
    if st.button("حفظ كلمة المرور"):
        cur.execute("UPDATE users SET password=? WHERE username=?",(hp(np),sel2))
        conn.commit()
        st.success("تم التحديث")

st.title("🌴 نظام متابعة مناديب بستان العجوة")

if st.session_state.role=="accountant":
    t1,t2=st.tabs(["المندوب","الإدارة"])
    with t1: delegate_page()
    with t2: admin_page()
else:
    delegate_page()
