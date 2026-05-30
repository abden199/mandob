
إضافة مبلغ العهدة المستلمة:

1- أنشئ جدول جديد:

CREATE TABLE IF NOT EXISTS advances(
id INTEGER PRIMARY KEY AUTOINCREMENT,
username TEXT,
amount REAL,
created_at TEXT
)

2- داخل شاشة المندوب أضف:

advance_amount = st.number_input(
    "مبلغ العهدة المستلمة",
    min_value=0.0,
    step=100.0
)

3- عند حفظ الفاتورة:

cur.execute(
    '''INSERT INTO advances(username,amount,created_at)
       VALUES(?,?,?)''',
    (
        name,
        advance_amount,
        datetime.now().strftime("%Y-%m-%d %H:%M")
    )
)

4- في لوحة الإدارة أضف تقرير:

adv = pd.read_sql_query(
    "SELECT username, SUM(amount) total_advance FROM advances GROUP BY username",
    conn
)

ثم احسب:

إجمالي العهدة
إجمالي المصروف
المتبقي = العهدة - المصروف

واعرضها في DataFrame.
