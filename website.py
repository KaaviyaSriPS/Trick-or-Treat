from flask import Flask, render_template, request, redirect, url_for, flash, session
import mysql.connector as sql
from datetime import date, timedelta

app = Flask(__name__)
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_TYPE'] = 'filesystem'
app.secret_key = 'temp'

# ---------------------------------------------
# DATABASE CONNECTION
# ---------------------------------------------
def get_db_connection(user=None, pwd=None):
    return sql.connect(
        host="localhost",
        user=user or "root",
        password=pwd or "bunny",
        database="21_29"
    )

# ---------------------------------------------
# HOME PAGE
# ---------------------------------------------
@app.route('/')
def index():
    return render_template('index.html')

# ---------------------------------------------
# CATEGORY PAGES
# ---------------------------------------------
@app.route('/classic')
def classic():
    con = get_db_connection()
    cur = con.cursor()
    cur.execute("SELECT * FROM i_classic")
    rows = cur.fetchall()
    return render_template('menu.html', title='Classic Flavours', table_name='i_classic', rows=rows)

@app.route('/fruit')
def fruit():
    con = get_db_connection()
    cur = con.cursor()
    cur.execute("SELECT * FROM i_fruit")
    rows = cur.fetchall()
    return render_template('menu.html', title='Fruit Flavours', table_name='i_fruit', rows=rows)

@app.route('/uncon')
def uncon():
    con = get_db_connection()
    cur = con.cursor()
    cur.execute("SELECT * FROM i_uncon")
    rows = cur.fetchall()
    return render_template('menu.html', title='Unconventional Flavours', table_name='i_uncon', rows=rows)

@app.route('/sundaes')
def sundaes():
    con = get_db_connection()
    cur = con.cursor()
    cur.execute("SELECT * FROM sundaes")
    rows = cur.fetchall()
    return render_template('menu.html', title='Sundaes', table_name='sundaes', rows=rows)

@app.route('/shakes')
def shakes():
    con = get_db_connection()
    cur = con.cursor()
    cur.execute("SELECT * FROM shakes")
    rows = cur.fetchall()
    return render_template('menu.html', title='Milkshakes', table_name='shakes', rows=rows)

# ---------------------------------------------
# ADD TO CART
# ---------------------------------------------
@app.route('/add_to_cart/<code>')
def add_to_cart(code):
    con = get_db_connection()
    cur = con.cursor(dictionary=True)
    tables = ['i_classic', 'i_fruit', 'i_uncon', 'sundaes', 'shakes']
    item = None

    for table in tables:
        cur.execute(f"SELECT * FROM {table} WHERE Code = %s", (code,))
        result = cur.fetchone()
        if result:
            item = result
            break

    if item:
        cart = session.get('cart', [])
        for c in cart:
            if c['Code'] == item['Code']:
                c['Quantity'] = c.get('Quantity', 1) + 1
                break
        else:
            item['Quantity'] = 1
            cart.append(item)

        session['cart'] = cart
        session.modified = True

    return redirect(request.referrer or url_for('index'))

# ---------------------------------------------
# VIEW CART
# ---------------------------------------------
@app.route('/cart')
def menu_cart():
    cart = session.get('cart', [])
    total = sum(item['Price'] * item.get('Quantity', 1) for item in cart)
    return render_template('cart.html', cart=cart, total=total)

# ---------------------------------------------
# CHECKOUT PAGE
# ---------------------------------------------
@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    cart = session.get('cart', [])

    if request.method == 'POST':
        customer_name = request.form.get('customer')
        if not customer_name:
            return "Missing customer name", 400

        total = sum(item['Price'] * item['Quantity'] for item in cart)

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT COALESCE(MAX(Order_No), 0) + 1 FROM order_log")
        order_no = cur.fetchone()[0]
        today = date.today()

        for item in cart:
            code = item['Code']
            qty = item['Quantity']
            paid = item['Price'] * qty
            cur.execute("""
                INSERT INTO order_log (Order_No, Code, Customer, Quantity, Paid, Date)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (order_no, code, customer_name, qty, paid, today))

        conn.commit()
        conn.close()

        session['cart'] = []
        return render_template('order_confirm.html', customer=customer_name, order_no=order_no, total=total)

    return render_template('checkout.html', cart=cart)

# ---------------------------------------------
# ORDER CONFIRMATION
# ---------------------------------------------
@app.route('/order_confirm')
def order_confirm():
    name = request.args.get('name', 'Customer')
    return render_template('order_confirm.html', name=name)

# ---------------------------------------------
# ADMIN LOGIN
# ---------------------------------------------
@app.route('/admin/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form['user']
        pwd = request.form['pwd']
        conn = get_db_connection(user, pwd)
        if conn:
            session['user'] = user
            session['pwd'] = pwd
            flash("Login successful!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Login failed. Check credentials.", "error")
    return render_template('login.html')

# ---------------------------------------------
# DASHBOARD (Reports)
# ---------------------------------------------
@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection(session['user'], session['pwd'])
    cur = conn.cursor(dictionary=True)

    cur.execute("SELECT DISTINCT Date FROM order_log ORDER BY Date ASC")
    all_dates = [row['Date'] for row in cur.fetchall()]
    if not all_dates:
        return render_template('dashboard.html', no_data=True)

    selected_date_str = request.args.get('date')
    if not selected_date_str:
        selected_date_str = all_dates[-1].strftime("%Y-%m-%d")

    selected_index = next((i for i, d in enumerate(all_dates) if d.strftime("%Y-%m-%d") == selected_date_str), len(all_dates) - 1)
    prev_date = all_dates[selected_index - 1].strftime("%Y-%m-%d") if selected_index > 0 else None
    next_date = all_dates[selected_index + 1].strftime("%Y-%m-%d") if selected_index < len(all_dates) - 1 else None

    selected_date = date.fromisoformat(selected_date_str)
    start_of_week = selected_date - timedelta(days=selected_date.weekday())
    first_day_of_month = selected_date.replace(day=1)

    # --- Summary counts ---
    cur.execute("""
        SELECT COUNT(DISTINCT Order_No) AS orders, SUM(Quantity) AS items, SUM(Paid) AS revenue 
        FROM order_log WHERE DATE(Date) = %s
    """, (selected_date_str,))
    summary = cur.fetchone() or {}

    orders_yesterday = summary.get("orders", 0) or 0
    items_yesterday = summary.get("items", 0) or 0
    revenue_yesterday = summary.get("revenue", 0) or 0

    # --- Most popular item overall ---
    cur.execute("""
        SELECT ol.Code, MAX(t.Item) AS Item, COUNT(*) AS times_ordered
        FROM order_log ol
        JOIN (
            SELECT Code, Item FROM i_classic
            UNION ALL SELECT Code, Item FROM i_fruit
            UNION ALL SELECT Code, Item FROM i_uncon
            UNION ALL SELECT Code, Item FROM sundaes
            UNION ALL SELECT Code, Item FROM shakes
        ) t ON ol.Code = t.Code
        GROUP BY ol.Code
        ORDER BY times_ordered DESC
        LIMIT 1
    """)
    popular = cur.fetchone()

    # --- Weekly summary ---
    cur.execute("""
        SELECT COUNT(DISTINCT Order_No) AS orders, SUM(Quantity) AS items, SUM(Paid) AS revenue
        FROM order_log WHERE DATE(Date) >= %s
    """, (start_of_week,))
    weekly = cur.fetchone() or {"orders": 0, "items": 0, "revenue": 0}

    # --- Monthly summary ---
    cur.execute("""
        SELECT COUNT(DISTINCT Order_No) AS orders, SUM(Quantity) AS items, SUM(Paid) AS revenue
        FROM order_log WHERE DATE(Date) >= %s
    """, (first_day_of_month,))
    monthly = cur.fetchone() or {"orders": 0, "items": 0, "revenue": 0}

    # --- Most popular item by category ---
    categories = ['i_classic', 'i_fruit', 'i_uncon', 'sundaes', 'shakes']
    popular_by_category = []
    for cat in categories:
        cur.execute(f"""
            SELECT MAX(t.Item) AS Item, COUNT(*) AS orders
            FROM order_log ol
            JOIN {cat} t ON ol.Code = t.Code
            WHERE DATE(ol.Date) = %s
            GROUP BY ol.Code
            ORDER BY orders DESC
            LIMIT 1
        """, (selected_date_str,))
        result = cur.fetchone()
        if result:
            popular_by_category.append({
                "category": cat,
                "item": result['Item'],
                "orders": result['orders']
            })

    # --- Recent orders ---
    cur.execute("SELECT * FROM order_log WHERE DATE(Date) = %s ORDER BY Order_No DESC LIMIT 20", (selected_date_str,))
    recent_orders = cur.fetchall()

    # --- Weekly sales by category ---
    cur.execute("""
        SELECT 
            CASE
                WHEN Code LIKE 'IC%%' THEN 'Classic'
                WHEN Code LIKE 'IF%%' THEN 'Fruit'
                WHEN Code LIKE 'IU%%' THEN 'Unconventional'
                WHEN Code LIKE 'SD%%' THEN 'Sundaes'
                WHEN Code LIKE 'MS%%' THEN 'Shakes'
            END AS category,
            SUM(Paid) AS total_sales
        FROM order_log
        WHERE DATE(Date) >= %s
        GROUP BY category
    """, (start_of_week,))
    weekly_sales = cur.fetchall()

    # --- Monthly sales by category ---
    cur.execute("""
        SELECT 
            CASE
                WHEN Code LIKE 'IC%%' THEN 'Classic'
                WHEN Code LIKE 'IF%%' THEN 'Fruit'
                WHEN Code LIKE 'IU%%' THEN 'Unconventional'
                WHEN Code LIKE 'SD%%' THEN 'Sundaes'
                WHEN Code LIKE 'MS%%' THEN 'Shakes'
            END AS category,
            SUM(Paid) AS total_sales
        FROM order_log
        WHERE DATE(Date) >= %s
        GROUP BY category
    """, (first_day_of_month,))
    monthly_sales = cur.fetchall()

    weekly_categories = [row['category'] for row in weekly_sales]
    weekly_totals = [float(row['total_sales'] or 0) for row in weekly_sales]
    monthly_categories = [row['category'] for row in monthly_sales]
    monthly_totals = [float(row['total_sales'] or 0) for row in monthly_sales]

    conn.close()

    return render_template(
        'dashboard.html',
        selected_date=selected_date_str,
        prev_date=prev_date,
        next_date=next_date,
        orders_yesterday=orders_yesterday,
        items_yesterday=items_yesterday,
        revenue_yesterday=revenue_yesterday,
        popular=popular,
        weekly=weekly,
        monthly=monthly,
        weekly_categories=weekly_categories,
        weekly_totals=weekly_totals,
        monthly_categories=monthly_categories,
        monthly_totals=monthly_totals,
        popular_by_category=popular_by_category,
        recent_orders=recent_orders
    )

# ---------------------------------------------
# LOGOUT
# ---------------------------------------------
@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully!", "info")
    return redirect(url_for('index'))

# ---------------------------------------------
# MAIN RUN
# ---------------------------------------------
if __name__ == '__main__':
    app.run(debug=True)