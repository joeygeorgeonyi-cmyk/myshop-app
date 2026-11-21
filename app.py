# ============================================================
# MY SHOP APP - V5 FINAL - ONE CLEAN FILE
# Features: Multi-Shop, Admin/Sales Roles, Stock, Buy/Sell,
# Profit in Words, Debtors/Creditors/Bad Debt, Losses,
# Discount/Bonanza/Jara, Stock Levels, Subscription Control,
# Forgot Password, Profit At A Glance, Performance Report,
# Edit/Delete Correction, Case-Insensitive, Export CSV, Print
# ============================================================
from flask import Flask, request, redirect, render_template_string, session, Response
import sqlite3, csv, io
from datetime import date, timedelta

app = Flask(__name__)
app.secret_key = "change-this-secret-very-long-2026-please"

# --- SUPER ADMIN (YOU - App Owner) - CHANGE BEFORE DEPLOYMENT ---
SUPER_USER = "superadmin"
SUPER_PASS = "super123"

def get_db():
    conn = sqlite3.connect("shop.db")
    conn.row_factory = sqlite3.Row
    return conn

# --- NUMBER TO WORDS ---
ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten",
        "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]
def under_1000(n):
    if n == 0: return ""
    if n < 20: return ONES[n]
    if n < 100: return TENS[n//10] + (" " + ONES[n%10] if n%10 else "")
    return ONES[n//100] + " Hundred" + (" " + under_1000(n%100) if n%100 else "")
def num_words(n):
    if n == 0: return "Zero Naira Only"
    if n < 0: return "Minus " + num_words(-n)
    parts=[]; b=n//1000000000; m=(n%1000000000)//1000000; t=(n%1000000)//1000; r=n%1000
    if b: parts.append(under_1000(b)+" Billion")
    if m: parts.append(under_1000(m)+" Million")
    if t: parts.append(under_1000(t)+" Thousand")
    if r: parts.append(under_1000(r))
    return " ".join(parts)+" Naira Only"

def norm(name): return name.strip().lower()
def display(name): return name.strip().title()
def is_admin(): return session.get("role") in ("admin", "superadmin")
def check_subscription(shop):
    if not shop: return False
    if shop["active"] == 0: return False
    if shop["expiry"] and shop["expiry"] < date.today().isoformat(): return False
    return True
def current_shop():
    if "shop_id" not in session: return None
    conn=get_db(); s=conn.execute("SELECT * FROM shops WHERE id=?", (session["shop_id"],)).fetchone(); conn.close(); return s

# --- CREATE TABLES ---
conn = get_db()
conn.execute("""CREATE TABLE IF NOT EXISTS shops (
    id INTEGER PRIMARY KEY AUTOINCREMENT, shop_name TEXT, caption TEXT, address TEXT,
    phone TEXT, logo TEXT, owner_name TEXT, expiry TEXT DEFAULT '2027-12-31', active INTEGER DEFAULT 1)""")
conn.execute("""CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT, shop_id INTEGER, username TEXT UNIQUE, password TEXT, role TEXT)""")
conn.execute("""CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT, shop_id INTEGER, name TEXT, name_key TEXT,
    buy_price INTEGER DEFAULT 0, sell_price INTEGER DEFAULT 0, stock INTEGER DEFAULT 0,
    min_stock INTEGER DEFAULT 5, max_stock INTEGER DEFAULT 100, reorder_level INTEGER DEFAULT 10)""")
conn.execute("""CREATE TABLE IF NOT EXISTS purchases (id INTEGER PRIMARY KEY AUTOINCREMENT, shop_id INTEGER, item TEXT, qty INTEGER, buy_price INTEGER, total_cost INTEGER, date TEXT)""")
conn.execute("""CREATE TABLE IF NOT EXISTS sales (id INTEGER PRIMARY KEY AUTOINCREMENT, shop_id INTEGER, item TEXT, qty INTEGER, bonus_qty INTEGER DEFAULT 0, discount INTEGER DEFAULT 0, discount_reason TEXT, sell_price INTEGER, buy_price INTEGER, amount INTEGER, profit INTEGER, date TEXT)""")
conn.execute("""CREATE TABLE IF NOT EXISTS debtors (id INTEGER PRIMARY KEY AUTOINCREMENT, shop_id INTEGER, customer TEXT, phone TEXT, item TEXT, amount INTEGER, paid INTEGER DEFAULT 0, balance INTEGER, date TEXT, status TEXT DEFAULT 'Owing')""")
conn.execute("""CREATE TABLE IF NOT EXISTS creditors (id INTEGER PRIMARY KEY AUTOINCREMENT, shop_id INTEGER, supplier TEXT, phone TEXT, reason TEXT, amount INTEGER, paid INTEGER DEFAULT 0, balance INTEGER, date TEXT, status TEXT DEFAULT 'Owing')""")
conn.execute("""CREATE TABLE IF NOT EXISTS losses (id INTEGER PRIMARY KEY AUTOINCREMENT, shop_id INTEGER, item TEXT, qty INTEGER, reason TEXT, loss_amount INTEGER, date TEXT)""")
conn.commit(); conn.close()

# ============================================================
# HTML - MAIN SHOP PAGE
# ============================================================
HTML = """
<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{font-family:Arial;padding:12px;background:#f2f2f2} .card{background:white;padding:12px;border-radius:10px;margin-bottom:12px}
input,select{width:100%;padding:10px;margin:5px 0;font-size:16px}
button{width:100%;padding:12px;font-weight:bold;background:#0a7a42;color:white;border:none;border-radius:8px;margin-top:6px}
button.blue{background:#1a5fc1} button.orange{background:#e67300} button.red{background:#c1121f} button.grey{background:#555}
.total-box{display:flex;gap:8px;flex-wrap:wrap} .total{flex:1;min-width:140px;padding:12px;border-radius:10px;text-align:center;border:3px solid black}
.total b{font-size:20px;display:block} .total i{font-size:11px;display:block}
.stock-box{background:#fff8c5;border-color:#e6b800} .sales-box{background:#d6f5d6;border-color:#0a7a42} .profit-box{background:#ffe0b3;border-color:#e67300}
.cost-box{background:#ffd6d6;border-color:#c1121f} .debtor-box{background:#e0f0ff;border-color:#1a5fc1} .creditor-box{background:#f0d6ff;border-color:#7b1fa2}
.loss-box{background:#e8e8e8;border-color:#333} .bad-box{background:#ffcccc;border-color:#c1121f}
table{width:100%;border-collapse:collapse;background:white;font-size:13px} th,td{border:1px solid #ccc;padding:7px;text-align:left} th{background:#222;color:white}
.red-row{background:#ffcccc} .yellow-row{background:#fff8c5} .green-row{background:#d6f5d6}
.small-btn{width:auto;padding:5px 10px;font-size:12px;display:inline-block} .footer{text-align:center;font-size:11px;color:#666;margin-top:20px}
@media print{ .no-print{display:none} }
</style></head><body>
<div style="text-align:center">
{% if shop['logo'] %}<img src="{{ shop['logo'] }}" style="max-height:80px"><br>{% endif %}
<h1>{{ shop['shop_name'] }}</h1><p><i>{{ shop['caption'] }}</i><br>{{ shop['address'] }} | {{ shop['phone'] }} | Owner: {{ shop['owner_name'] }}</p>
<p>Logged in: {{ session['username'] }} ({{ session['role'] }}) | Expiry: {{ shop['expiry'] }} | <a href="/logout">Logout</a>
{% if is_admin %} | <a href="/super">Super Admin</a> | <a href="/export">📥 Export Excel/CSV</a> {% endif %}
| <button onclick="window.print()" class="small-btn grey no-print">🖨️ Print Report</button></p>
</div>

<div class="card no-print"><form method="get">Period: <select name="period">
<option value="today" {% if period=='today' %}selected{% endif %}>Today</option>
<option value="week" {% if period=='week' %}selected{% endif %}>This Week</option>
<option value="month" {% if period=='month' %}selected{% endif %}>This Month</option>
<option value="quarter" {% if period=='quarter' %}selected{% endif %}>This Quarter</option>
<option value="year" {% if period=='year' %}selected{% endif %}>This Year</option>
<option value="all" {% if period=='all' %}selected{% endif %}>All Time</option>
<option value="custom" {% if period=='custom' %}selected{% endif %}>Custom</option></select>
From <input type="date" name="from_date" value="{{ from_date }}"> To <input type="date" name="to_date" value="{{ to_date }}">
<button class="blue" type="submit">SHOW TOTALS</button></form><b>Showing:</b> {{ label }}</div>

<h2>📊 TOTALS - {{ label }}</h2><div class="total-box">
<div class="total stock-box">STOCK VALUE<b>₦{{ stock_value }}</b><i>{{ stock_value_w }}</i></div>
{% if is_admin %}<div class="total sales-box">SALES<b>₦{{ total_sales }}</b><i>{{ total_sales_w }}</i><small>{{ total_qty }} sold</small></div>
<div class="total profit-box">GROSS PROFIT<b>₦{{ total_profit }}</b><i>{{ total_profit_w }}</i></div>
<div class="total cost-box">PURCHASES<b>₦{{ total_purchases }}</b><i>{{ total_purchases_w }}</i></div>{% endif %}
<div class="total debtor-box">DEBTORS OWE YOU<b>₦{{ total_debtors }}</b><i>{{ total_debtors_w }}</i></div>
<div class="total creditor-box">YOU OWE<b>₦{{ total_creditors }}</b><i>{{ total_creditors_w }}</i></div>
<div class="total bad-box">BAD DEBT<b>₦{{ total_bad }}</b><i>{{ total_bad_w }}</i></div>
<div class="total loss-box">LOSSES<b>₦{{ total_loss }}</b><i>{{ total_loss_w }}</i></div>
</div>

{% if is_admin %}
<h2>💰 PROFIT AT A GLANCE - Admin Only</h2>
<div class="total-box">
<div class="total profit-box">PROFIT TODAY<b>₦{{ p_today }}</b><i>{{ p_today_w }}</i></div>
<div class="total profit-box">PROFIT THIS WEEK<b>₦{{ p_week }}</b><i>{{ p_week_w }}</i></div>
<div class="total profit-box">PROFIT THIS MONTH<b>₦{{ p_month }}</b><i>{{ p_month_w }}</i></div>
<div class="total profit-box">PROFIT THIS QUARTER<b>₦{{ p_quarter }}</b><i>{{ p_quarter_w }}</i></div>
<div class="total profit-box">PROFIT THIS YEAR<b>₦{{ p_year }}</b><i>{{ p_year_w }}</i></div>
</div>

<div class="card" style="border:3px solid #0a7a42">
<h2>🏆 SELLING PERFORMANCE REPORT - Admin Only</h2>
<p><i>Most Selling = Highest Qty | Most Profitable = Highest Profit</i></p>
<table><tr><th>Period</th><th>Most Selling Product</th><th>Qty</th><th>Most Profitable Product</th><th>Profit</th></tr>
<tr><td><b>Today</b> {{ today_str }}</td><td>{{ perf['today']['best_qty_item'] }}</td><td>{{ perf['today']['best_qty'] }}</td><td>{{ perf['today']['best_profit_item'] }}</td><td>₦{{ perf['today']['best_profit'] }}</td></tr>
<tr><td><b>This Week</b></td><td>{{ perf['week']['best_qty_item'] }}</td><td>{{ perf['week']['best_qty'] }}</td><td>{{ perf['week']['best_profit_item'] }}</td><td>₦{{ perf['week']['best_profit'] }}</td></tr>
<tr><td><b>This Month</b></td><td>{{ perf['month']['best_qty_item'] }}</td><td>{{ perf['month']['best_qty'] }}</td><td>{{ perf['month']['best_profit_item'] }}</td><td>₦{{ perf['month']['best_profit'] }}</td></tr>
<tr><td><b>This Quarter</b></td><td>{{ perf['quarter']['best_qty_item'] }}</td><td>{{ perf['quarter']['best_qty'] }}</td><td>{{ perf['quarter']['best_profit_item'] }}</td><td>₦{{ perf['quarter']['best_profit'] }}</td></tr>
<tr><td><b>This Year</b></td><td>{{ perf['year']['best_qty_item'] }}</td><td>{{ perf['year']['best_qty'] }}</td><td>{{ perf['year']['best_profit_item'] }}</td><td>₦{{ perf['year']['best_profit'] }}</td></tr>
<tr><td><b>Selected Period</b><br>{{ label }}</td><td>{{ perf['selected']['best_qty_item'] }}</td><td>{{ perf['selected']['best_qty'] }}</td><td>{{ perf['selected']['best_profit_item'] }}</td><td>₦{{ perf['selected']['best_profit'] }}</td></tr>
</table><p><b>Insight:</b> {{ insight }}</p></div>

<div class="card no-print" style="border:2px dashed #c1121f"><h3>🔑 Admin: Reset Salesperson Password</h3>
<form method="post" action="/reset_sales_password">New Sales Password: <input name="new_password" required>
<button class="red" type="submit">RESET SALES PASSWORD</button></form></div>
{% endif %}

<div class="card"><h2>➕ Add / Restock (Not Case Sensitive)</h2><form method="post" action="/add">
Item: <input name="name" placeholder="Rice, rice, RICE = same" required>
Buy: <input name="buy_price" type="number" required> Sell: <input name="sell_price" type="number" required> Qty: <input name="qty" type="number" required>
Min Stock: <input name="min_stock" type="number" value="5"> Max Stock: <input name="max_stock" type="number" value="100"> Reorder Level: <input name="reorder_level" type="number" value="10">
<button type="submit">ADD STOCK</button></form></div>

<div class="card"><h2>💰 Sell + Bonanza / Discount / Jara</h2><form method="post" action="/sell">
Item: <input name="name" required> Qty: <input name="qty" type="number" required>
Discount ₦: <input name="discount" type="number" value="0"> Bonus / Jara Qty (Free): <input name="bonus_qty" type="number" value="0">
Reason: <select name="discount_reason"><option value="">No Discount</option><option>Bonanza</option><option>Christmas Promo</option><option>Customer Loyalty</option><option>Jara / Freebie</option><option>Damaged - Discount</option></select>
<button type="submit">SELL</button></form></div>

<div class="card"><h2>📦 Current Stock - Colours = Level</h2><p>🔴 Red = Below Min / Urgent | 🟡 Yellow = At Reorder | 🟢 Green = OK</p>
<table><tr><th>Item</th><th>Buy</th><th>Sell</th><th>Profit/Unit</th><th>Stock</th><th>Min / Reorder / Max</th><th>Status</th><th>Action</th></tr>
{% for it in items %}<tr class="{{ it['row_class'] }}"><td><b>{{ it['name'] }}</b></td><td>₦{{ it['buy_price'] }}</td><td>₦{{ it['sell_price'] }}</td>
<td>₦{{ it['sell_price']-it['buy_price'] }}</td><td>{{ it['stock'] }}</td><td>{{ it['min_stock'] }} / {{ it['reorder_level'] }} / {{ it['max_stock'] }}</td><td><b>{{ it['status'] }}</b></td>
<td><a href="/edit_item/{{ it['id'] }}">Edit</a> {% if is_admin %} | <a href="/delete_item/{{ it['id'] }}" onclick="return confirm('Delete?')">Delete</a>{% endif %}</td></tr>{% endfor %}</table></div>

<div class="card"><h2>🧾 Sales History</h2><table><tr><th>Date</th><th>Item</th><th>Qty</th><th>Bonus</th><th>Discount</th><th>Amount</th><th>Words</th>{% if is_admin %}<th>Profit</th><th>Action</th>{% endif %}</tr>
{% for s in sales_list %}<tr><td>{{ s['date'] }}</td><td>{{ s['item'] }}</td><td>{{ s['qty'] }}</td><td>{{ s['bonus_qty'] }}</td><td>₦{{ s['discount'] }} {{ s['discount_reason'] }}</td><td>₦{{ s['amount'] }}</td><td><i>{{ s['words'] }}</i></td>
{% if is_admin %}<td>₦{{ s['profit'] }}</td><td><a href="/delete_sale/{{ s['id'] }}">Delete / Correct</a></td>{% endif %}</tr>{% endfor %}</table></div>

<div class="card" style="border:3px solid #1a5fc1"><h2>👥 DEBTORS - Owing You</h2><form method="post" action="/add_debtor">
Customer: <input name="customer" required> Phone: <input name="phone"> For: <input name="item" required> Amount: <input name="amount" type="number" required>
<button class="blue" type="submit">ADD DEBTOR</button></form>
<table><tr><th>Customer</th><th>Reason</th><th>Amount</th><th>Paid</th><th>Balance</th><th>Words</th><th>Status</th><th>Action</th></tr>
{% for d in debtors %}<tr><td>{{ d['customer'] }}</td><td>{{ d['item'] }}</td><td>₦{{ d['amount'] }}</td><td>₦{{ d['paid'] }}</td><td>₦{{ d['balance'] }}</td><td><i>{{ d['words'] }}</i></td><td>{{ d['status'] }}</td>
<td>{% if d['status']=='Owing' %}<form method="post" action="/pay_debtor/{{ d['id'] }}"><input name="pay" type="number" required><button class="blue small-btn" type="submit">PAY</button></form>
<form method="post" action="/bad_debt/{{ d['id'] }}"><button class="red small-btn" type="submit">MARK BAD DEBT</button></form>{% endif %}
{% if is_admin %}<a href="/delete_debtor/{{ d['id'] }}">Delete / Correct</a>{% endif %}</td></tr>{% endfor %}</table></div>

<div class="card" style="border:3px solid #7b1fa2"><h2>🏦 CREDITORS - You Owe</h2><form method="post" action="/add_creditor">
Supplier: <input name="supplier" required> Phone: <input name="phone"> Reason: <input name="reason" required> Amount: <input name="amount" type="number" required>
<button class="orange" type="submit">ADD CREDITOR</button></form>
<table><tr><th>Supplier</th><th>Reason</th><th>Amount</th><th>Paid</th><th>Balance</th><th>Words</th><th>Action</th></tr>
{% for c in creditors %}<tr><td>{{ c['supplier'] }}</td><td>{{ c['reason'] }}</td><td>₦{{ c['amount'] }}</td><td>₦{{ c['paid'] }}</td><td>₦{{ c['balance'] }}</td><td><i>{{ c['words'] }}</i></td>
<td>{% if c['balance']>0 %}<form method="post" action="/pay_creditor/{{ c['id'] }}"><input name="pay" type="number" required><button class="orange small-btn" type="submit">PAY</button></form>{% endif %}</td></tr>{% endfor %}</table></div>

<div class="card" style="border:3px solid #333"><h2>⚠️ LOSSES - Expired / Spoilt / Broken</h2><form method="post" action="/add_loss">
Item: <input name="item" required> Qty Lost: <input name="qty" type="number" required>
Reason: <select name="reason"><option>Expired Product</option><option>Spoilt Product</option><option>Broken Bottle</option><option>Broken Seal</option><option>Theft / Missing</option><option>Other Damage</option></select>
<button class="grey" type="submit">RECORD LOSS</button></form>
<table><tr><th>Date</th><th>Item</th><th>Qty</th><th>Reason</th><th>Loss ₦</th><th>Action</th></tr>
{% for l in losses %}<tr><td>{{ l['date'] }}</td><td>{{ l['item'] }}</td><td>{{ l['qty'] }}</td><td>{{ l['reason'] }}</td><td>₦{{ l['loss_amount'] }}</td><td>{% if is_admin %}<a href="/delete_loss/{{ l['id'] }}">Delete / Correct</a>{% endif %}</td></tr>{% endfor %}</table></div>

<div class="card"><h2>🛒 Purchases</h2><table><tr><th>Date</th><th>Item</th><th>Qty</th><th>Cost</th><th>Words</th>{% if is_admin %}<th>Action</th>{% endif %}</tr>
{% for p in purchases_list %}<tr><td>{{ p['date'] }}</td><td>{{ p['item'] }}</td><td>{{ p['qty'] }}</td><td>₦{{ p['total_cost'] }}</td><td><i>{{ p['words'] }}</i></td>{% if is_admin %}<td><a href="/delete_purchase/{{ p['id'] }}">Delete</a></td>{% endif %}</tr>{% endfor %}</table></div>

<div class="footer">© 2026 {{ shop['shop_name'] }} - All Rights Reserved. Powered by Your Shop App. Do not copy without permission.</div>
</body></html>
"""

LOGIN_HTML = """<h2 style="text-align:center">🏪 Shop App - Login</h2>
<form method="post" style="max-width:400px;margin:auto">Username: <input name="username" required><br>Password: <input name="password" type="password" required><br>
<button style="padding:12px;width:100%;background:#0a7a42;color:white" type="submit">LOGIN</button></form>
<p style="text-align:center"><a href="/forgot">Forgot Password? Click here to Reset</a></p>
<p style="text-align:center">Super Admin? <a href="/super_login">Super Admin Login</a></p><p style="text-align:center;color:red">{{ msg }}</p>"""

FORGOT_HTML = """<h2 style="text-align:center">🔑 Forgot Password?</h2>
<form method="post" style="max-width:400px;margin:auto">Username: <input name="username" required><br>
Shop Phone (for verification): <input name="phone" placeholder="Phone you registered with shop" required><br>
New Password: <input name="new_password" type="password" required><br>
<button style="padding:12px;width:100%;background:#1a5fc1;color:white" type="submit">RESET PASSWORD</button></form>
<p style="text-align:center;color:red">{{ msg }}</p><p style="text-align:center"><a href="/login">Back to Login</a></p>"""

SUPER_HTML = """<h2>🛡️ Super Admin - Manage Shops (You)</h2><p><a href="/logout">Logout</a></p>
<h3>Create New Shop / Client</h3><form method="post" action="/create_shop">
Shop Name: <input name="shop_name" required> Caption: <input name="caption" placeholder="e.g Best Prices in Abuja">
Address: <input name="address"> Phone: <input name="phone"> Logo URL: <input name="logo" placeholder="https://... or leave blank">
Owner Name: <input name="owner_name"> Expiry Date: <input name="expiry" type="date" value="2027-12-31" required>
Admin Username: <input name="admin_user" required> Admin Password: <input name="admin_pass" required>
Sales Username: <input name="sales_user" required> Sales Password: <input name="sales_pass" required>
<button type="submit">CREATE SHOP</button></form>
<h3>All Shops - Subscription Control</h3>
{% for s in shops %}<div style="border:1px solid #ccc;padding:10px;margin:10px 0">
<b>{{ s['shop_name'] }}</b> | {{ s['phone'] }} | Expiry: {{ s['expiry'] }} | Active: {{ 'YES' if s['active'] else 'CUT OFF' }} | Users: {{ s['users'] }}
<form method="post" action="/toggle_shop/{{ s['id'] }}"><button type="submit">TOGGLE ACTIVE / CUT OFF</button></form>
<form method="post" action="/extend_shop/{{ s['id'] }}">New Expiry: <input type="date" name="expiry" required><button type="submit">EXTEND</button></form>
<form method="post" action="/super_reset/{{ s['id'] }}">New Admin Pass: <input name="new_pass" required><button type="submit">RESET SHOP ADMIN PASS</button></form>
</div>{% endfor %}"""

# ============================================================
# AUTH + SUPER ADMIN
# ============================================================
@app.route("/super_login", methods=["GET","POST"])
def super_login():
    if request.method=="POST" and request.form['username']==SUPER_USER and request.form['password']==SUPER_PASS:
        session['username']=SUPER_USER; session['role']="superadmin"; session['shop_id']=0; return redirect("/super")
    return render_template_string(LOGIN_HTML, msg="Super Admin Login" if request.method=="GET" else "Wrong")

@app.route("/super")
def super_page():
    if session.get("role")!="superadmin": return redirect("/super_login")
    conn=get_db(); shops=conn.execute("SELECT * FROM shops").fetchall(); out=[]
    for s in shops:
        users=conn.execute("SELECT username||'('||role||')' as u FROM users WHERE shop_id=?", (s['id'],)).fetchall()
        out.append(dict(s, users=", ".join([u['u'] for u in users])))
    conn.close(); return render_template_string(SUPER_HTML, shops=out)

@app.route("/create_shop", methods=["POST"])
def create_shop():
    if session.get("role")!="superadmin": return redirect("/super_login")
    conn=get_db()
    cur=conn.execute("INSERT INTO shops (shop_name, caption, address, phone, logo, owner_name, expiry, active) VALUES (?,?,?,?,?,?,?,1)",
        (request.form['shop_name'], request.form['caption'], request.form['address'], request.form['phone'], request.form['logo'], request.form['owner_name'], request.form['expiry']))
    sid=cur.lastrowid
    conn.execute("INSERT INTO users (shop_id, username, password, role) VALUES (?,?,?,?)", (sid, request.form['admin_user'], request.form['admin_pass'], "admin"))
    conn.execute("INSERT INTO users (shop_id, username, password, role) VALUES (?,?,?,?)", (sid, request.form['sales_user'], request.form['sales_pass'], "sales"))
    conn.commit(); conn.close(); return redirect("/super")

@app.route("/toggle_shop/<int:id>", methods=["POST"])
def toggle_shop(id):
    if session.get("role")!="superadmin": return redirect("/super_login")
    conn=get_db(); r=conn.execute("SELECT active FROM shops WHERE id=?", (id,)).fetchone()
    conn.execute("UPDATE shops SET active=? WHERE id=?", (0 if r['active'] else 1, id)); conn.commit(); conn.close(); return redirect("/super")

@app.route("/extend_shop/<int:id>", methods=["POST"])
def extend_shop(id):
    if session.get("role")!="superadmin": return redirect("/super_login")
    conn=get_db(); conn.execute("UPDATE shops SET expiry=?, active=1 WHERE id=?", (request.form['expiry'], id)); conn.commit(); conn.close(); return redirect("/super")

@app.route("/super_reset/<int:id>", methods=["POST"])
def super_reset(id):
    if session.get("role")!="superadmin": return redirect("/super_login")
    conn=get_db(); conn.execute("UPDATE users SET password=? WHERE shop_id=? AND role='admin'", (request.form['new_pass'], id)); conn.commit(); conn.close(); return redirect("/super")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        conn=get_db(); u=conn.execute("SELECT * FROM users WHERE username=? AND password=?", (request.form['username'], request.form['password'])).fetchone(); conn.close()
        if u:
            shop_conn=get_db(); shop=shop_conn.execute("SELECT * FROM shops WHERE id=?", (u['shop_id'],)).fetchone(); shop_conn.close()
            if not check_subscription(shop):
                return render_template_string(LOGIN_HTML, msg="SUBSCRIPTION EXPIRED OR CUT OFF. Contact App Owner to renew.")
            session['username']=u['username']; session['role']=u['role']; session['shop_id']=u['shop_id']; return redirect("/")
        return render_template_string(LOGIN_HTML, msg="Wrong username or password")
    return render_template_string(LOGIN_HTML, msg="")

@app.route("/forgot", methods=["GET","POST"])
def forgot():
    if request.method=="POST":
        conn=get_db(); u=conn.execute("SELECT * FROM users WHERE username=?", (request.form['username'],)).fetchone()
        if not u: conn.close(); return render_template_string(FORGOT_HTML, msg="Username not found")
        shop=conn.execute("SELECT * FROM shops WHERE id=? AND phone=?", (u['shop_id'], request.form['phone'])).fetchone()
        if not shop: conn.close(); return render_template_string(FORGOT_HTML, msg="Phone does not match this shop. Contact Super Admin.")
        conn.execute("UPDATE users SET password=? WHERE id=?", (request.form['new_password'], u['id'])); conn.commit(); conn.close()
        return render_template_string(FORGOT_HTML, msg="✅ Password reset! Now login with new password.")
    return render_template_string(FORGOT_HTML, msg="")

@app.route("/reset_sales_password", methods=["POST"])
def reset_sales_password():
    if not is_admin(): return "Admin only"
    conn=get_db(); conn.execute("UPDATE users SET password=? WHERE shop_id=? AND role='sales'", (request.form['new_password'], session["shop_id"])); conn.commit(); conn.close(); return redirect("/")

@app.route("/logout")
def logout(): session.clear(); return redirect("/login")

# ============================================================
# MAIN PAGE
# ============================================================
@app.route("/")
def home():
    if "shop_id" not in session or session.get("role")=="superadmin": return redirect("/login")
    shop=current_shop()
    if not check_subscription(shop): session.clear(); return "Subscription Expired. Contact App Owner."
    period=request.args.get("period","today"); from_date=request.args.get("from_date",""); to_date=request.args.get("to_date","")
    today=date.today()
    if period=="today": start=end=today.isoformat(); label=f"Today {today}"
    elif period=="week": start=(today-timedelta(days=today.weekday())).isoformat(); end=today.isoformat(); label=f"Week {start} to {end}"
    elif period=="month": start=today.replace(day=1).isoformat(); end=today.isoformat(); label=f"Month {start} to {end}"
    elif period=="quarter": qm=((today.month-1)//3)*3+1; start=today.replace(month=qm, day=1).isoformat(); end=today.isoformat(); label=f"Quarter {start} to {end}"
    elif period=="year": start=today.replace(month=1, day=1).isoformat(); end=today.isoformat(); label=f"Year {start} to {end}"
    elif period=="custom" and from_date and to_date: start,end=from_date,to_date; label=f"{start} to {end}"
    else: start,end="2000-01-01","2100-01-01"; label="All Time"; period="all"

    sid=session["shop_id"]; conn=get_db()
    items_raw=conn.execute("SELECT * FROM items WHERE shop_id=? ORDER BY name", (sid,)).fetchall()
    items=[]
    for it in items_raw:
        if it['stock']<=it['min_stock']: rc="red-row"; st="🔴 URGENT - Below Min"
        elif it['stock']<=it['reorder_level']: rc="yellow-row"; st="🟡 Reorder Now"
        else: rc="green-row"; st="🟢 OK"
        items.append(dict(it, row_class=rc, status=st))
    stock_value=sum(i['stock']*i['buy_price'] for i in items_raw)
    sales_raw=conn.execute("SELECT * FROM sales WHERE shop_id=? AND date BETWEEN ? AND ? ORDER BY id DESC", (sid, start, end)).fetchall()
    purch_raw=conn.execute("SELECT * FROM purchases WHERE shop_id=? AND date BETWEEN ? AND ? ORDER BY id DESC", (sid, start, end)).fetchall()
    debtors_raw=conn.execute("SELECT * FROM debtors WHERE shop_id=? ORDER BY id DESC", (sid,)).fetchall()
    creditors_raw=conn.execute("SELECT * FROM creditors WHERE shop_id=? ORDER BY id DESC", (sid,)).fetchall()
    losses_raw=conn.execute("SELECT * FROM losses WHERE shop_id=? AND date BETWEEN ? AND ? ORDER BY id DESC", (sid, start, end)).fetchall()

    def profit_between(s,e):
        r=conn.execute("SELECT SUM(profit) as p FROM sales WHERE shop_id=? AND date BETWEEN ? AND ?", (sid,s,e)).fetchone(); return r['p'] or 0
    p_today=profit_between(today.isoformat(), today.isoformat())
    p_week=profit_between((today-timedelta(days=today.weekday())).isoformat(), today.isoformat())
    p_month=profit_between(today.replace(day=1).isoformat(), today.isoformat())
    qm=((today.month-1)//3)*3+1; p_quarter=profit_between(today.replace(month=qm, day=1).isoformat(), today.isoformat())
    p_year=profit_between(today.replace(month=1, day=1).isoformat(), today.isoformat())

    def perf_for(s,e):
        q=conn.execute("SELECT item, SUM(qty) as q FROM sales WHERE shop_id=? AND date BETWEEN ? AND ? GROUP BY item ORDER BY q DESC LIMIT 1", (sid,s,e)).fetchone()
        p=conn.execute("SELECT item, SUM(profit) as pr FROM sales WHERE shop_id=? AND date BETWEEN ? AND ? GROUP BY item ORDER BY pr DESC LIMIT 1", (sid,s,e)).fetchone()
        return {"best_qty_item": q['item'] if q else "No Sales", "best_qty": q['q'] if q else 0,
                "best_profit_item": p['item'] if p else "No Sales", "best_profit": p['pr'] if p else 0}
    perf={"today": perf_for(today.isoformat(), today.isoformat()), "week": perf_for((today-timedelta(days=today.weekday())).isoformat(), today.isoformat()),
          "month": perf_for(today.replace(day=1).isoformat(), today.isoformat()), "quarter": perf_for(today.replace(month=qm, day=1).isoformat(), today.isoformat()),
          "year": perf_for(today.replace(month=1, day=1).isoformat(), today.isoformat()), "selected": perf_for(start, end)}
    if perf['selected']['best_qty_item'] != perf['selected']['best_profit_item']:
        insight=f"{perf['selected']['best_qty_item']} sells most in quantity, but {perf['selected']['best_profit_item']} brings more profit. Push {perf['selected']['best_profit_item']} more."
    else:
        insight=f"{perf['selected']['best_qty_item']} is your star - it sells most AND makes most profit. Keep it in stock always."
    conn.close()

    sales_list=[dict(s, words=num_words(s['amount'])) for s in sales_raw]
    purchases_list=[dict(p, words=num_words(p['total_cost'])) for p in purch_raw]
    debtors=[dict(d, words=num_words(d['balance'])) for d in debtors_raw if d['status']=='Owing']
    creditors=[dict(c, words=num_words(c['balance'])) for c in creditors_raw]
    total_sales=sum(s['amount'] for s in sales_raw); total_profit=sum(s['profit'] for s in sales_raw); total_qty=sum(s['qty'] for s in sales_raw)
    total_purch=sum(p['total_cost'] for p in purch_raw); total_debtors=sum(d['balance'] for d in debtors_raw if d['status']=='Owing')
    total_bad=sum(d['balance'] for d in debtors_raw if d['status']=='Bad Debt'); total_creditors=sum(c['balance'] for c in creditors_raw)
    total_loss=sum(l['loss_amount'] for l in losses_raw)

    return render_template_string(HTML, shop=shop, session=session, is_admin=is_admin(), period=period, from_date=from_date, to_date=to_date, label=label,
        items=items, sales_list=sales_list, purchases_list=purchases_list, debtors=debtors, creditors=creditors, losses=losses_raw,
        stock_value=stock_value, total_sales=total_sales, total_profit=total_profit, total_qty=total_qty, total_purchases=total_purch,
        total_debtors=total_debtors, total_creditors=total_creditors, total_bad=total_bad, total_loss=total_loss,
        stock_value_w=num_words(stock_value), total_sales_w=num_words(total_sales), total_profit_w=num_words(total_profit),
        total_purchases_w=num_words(total_purch), total_debtors_w=num_words(total_debtors), total_creditors_w=num_words(total_creditors),
        total_bad_w=num_words(total_bad), total_loss_w=num_words(total_loss),
        p_today=p_today, p_week=p_week, p_month=p_month, p_quarter=p_quarter, p_year=p_year,
        p_today_w=num_words(p_today), p_week_w=num_words(p_week), p_month_w=num_words(p_month), p_quarter_w=num_words(p_quarter), p_year_w=num_words(p_year),
        perf=perf, insight=insight, today_str=today.isoformat())

# ============================================================
# ACTIONS
# ============================================================
@app.route("/add", methods=["POST"])
def add():
    if "shop_id" not in session: return redirect("/login")
    sid=session["shop_id"]; name=display(request.form['name']); key=norm(name)
    buy=int(request.form['buy_price']); sell=int(request.form['sell_price']); qty=int(request.form['qty'])
    min_s=int(request.form.get("min_stock",5)); max_s=int(request.form.get("max_stock",100)); reorder=int(request.form.get("reorder_level",10))
    conn=get_db(); row=conn.execute("SELECT * FROM items WHERE shop_id=? AND name_key=?", (sid, key)).fetchone()
    if row: conn.execute("UPDATE items SET buy_price=?, sell_price=?, stock=?, min_stock=?, max_stock=?, reorder_level=? WHERE id=?", (buy,sell,row['stock']+qty,min_s,max_s,reorder,row['id']))
    else: conn.execute("INSERT INTO items (shop_id, name, name_key, buy_price, sell_price, stock, min_stock, max_stock, reorder_level) VALUES (?,?,?,?,?,?,?,?,?)", (sid,name,key,buy,sell,qty,min_s,max_s,reorder))
    conn.execute("INSERT INTO purchases (shop_id, item, qty, buy_price, total_cost, date) VALUES (?,?,?,?,?,?)", (sid,name,qty,buy,buy*qty,date.today().isoformat()))
    conn.commit(); conn.close(); return redirect("/")

@app.route("/sell", methods=["POST"])
def sell():
    if "shop_id" not in session: return redirect("/login")
    sid=session["shop_id"]; key=norm(request.form['name']); qty=int(request.form['qty']); disc=int(request.form.get("discount",0) or 0); bonus=int(request.form.get("bonus_qty",0) or 0); reason=request.form.get("discount_reason","")
    conn=get_db(); row=conn.execute("SELECT * FROM items WHERE shop_id=? AND name_key=?", (sid, key)).fetchone()
    if not row or qty+bonus > row['stock']: conn.close(); return "Not enough stock (including Jara). <a href='/'>Go Back</a>"
    amount=row['sell_price']*qty - disc; profit=(row['sell_price']-row['buy_price'])*qty - disc
    conn.execute("UPDATE items SET stock=? WHERE id=?", (row['stock']-qty-bonus, row['id']))
    conn.execute("INSERT INTO sales (shop_id, item, qty, bonus_qty, discount, discount_reason, sell_price, buy_price, amount, profit, date) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (sid,row['name'],qty,bonus,disc,reason,row['sell_price'],row['buy_price'],max(0,amount),profit,date.today().isoformat()))
    conn.commit(); conn.close(); return redirect("/")

@app.route("/add_debtor", methods=["POST"])
def add_debtor():
    if "shop_id" not in session: return redirect("/login")
    sid=session["shop_id"]; amt=int(request.form['amount']); conn=get_db()
    conn.execute("INSERT INTO debtors (shop_id, customer, phone, item, amount, paid, balance, date) VALUES (?,?,?,?,?,?,?,?)", (sid,request.form['customer'],request.form['phone'],request.form['item'],amt,0,amt,date.today().isoformat()))
    conn.commit(); conn.close(); return redirect("/")
@app.route("/pay_debtor/<int:id>", methods=["POST"])
def pay_debtor(id):
    if "shop_id" not in session: return redirect("/login")
    pay=int(request.form['pay']); conn=get_db(); r=conn.execute("SELECT * FROM debtors WHERE id=? AND shop_id=?", (id,session["shop_id"])).fetchone()
    if r: conn.execute("UPDATE debtors SET paid=?, balance=?, status=? WHERE id=?", (r['paid']+pay, max(0,r['amount']-(r['paid']+pay)), "Paid" if r['amount']-(r['paid']+pay)<=0 else "Owing", id))
    conn.commit(); conn.close(); return redirect("/")
@app.route("/bad_debt/<int:id>", methods=["POST"])
def bad_debt(id):
    if "shop_id" not in session: return redirect("/login")
    conn=get_db(); conn.execute("UPDATE debtors SET status='Bad Debt' WHERE id=? AND shop_id=?", (id,session["shop_id"])); conn.commit(); conn.close(); return redirect("/")
@app.route("/add_creditor", methods=["POST"])
def add_creditor():
    if "shop_id" not in session: return redirect("/login")
    sid=session["shop_id"]; amt=int(request.form['amount']); conn=get_db()
    conn.execute("INSERT INTO creditors (shop_id, supplier, phone, reason, amount, paid, balance, date) VALUES (?,?,?,?,?,?,?,?)", (sid,request.form['supplier'],request.form['phone'],request.form['reason'],amt,0,amt,date.today().isoformat()))
    conn.commit(); conn.close(); return redirect("/")
@app.route("/pay_creditor/<int:id>", methods=["POST"])
def pay_creditor(id):
    if "shop_id" not in session: return redirect("/login")
    pay=int(request.form['pay']); conn=get_db(); r=conn.execute("SELECT * FROM creditors WHERE id=? AND shop_id=?", (id,session["shop_id"])).fetchone()
    if r: conn.execute("UPDATE creditors SET paid=?, balance=? WHERE id=?", (r['paid']+pay, max(0,r['amount']-(r['paid']+pay)), id))
    conn.commit(); conn.close(); return redirect("/")
@app.route("/add_loss", methods=["POST"])
def add_loss():
    if "shop_id" not in session: return redirect("/login")
    sid=session["shop_id"]; key=norm(request.form['item']); qty=int(request.form['qty']); reason=request.form['reason']
    conn=get_db(); row=conn.execute("SELECT * FROM items WHERE shop_id=? AND name_key=?", (sid,key)).fetchone()
    if not row or qty>row['stock']: conn.close(); return "Not enough stock for loss. <a href='/'>Go Back</a>"
    loss_amt=row['buy_price']*qty
    conn.execute("UPDATE items SET stock=? WHERE id=?", (row['stock']-qty, row['id']))
    conn.execute("INSERT INTO losses (shop_id, item, qty, reason, loss_amount, date) VALUES (?,?,?,?,?,?)", (sid,row['name'],qty,reason,loss_amt,date.today().isoformat()))
    conn.commit(); conn.close(); return redirect("/")

# --- CORRECTION ---
@app.route("/edit_item/<int:id>")
def edit_item(id):
    if not is_admin(): return "Admin only"
    conn=get_db(); it=conn.execute("SELECT * FROM items WHERE id=? AND shop_id=?", (id,session["shop_id"])).fetchone(); conn.close()
    return f"""<h2>Edit {it['name']}</h2><form method="post" action="/update_item/{id}">
    Name: <input name="name" value="{it['name']}"><br>Buy: <input name="buy_price" type="number" value="{it['buy_price']}"><br>
    Sell: <input name="sell_price" type="number" value="{it['sell_price']}"><br>Stock: <input name="stock" type="number" value="{it['stock']}"><br>
    Min: <input name="min_stock" type="number" value="{it['min_stock']}"> Max: <input name="max_stock" type="number" value="{it['max_stock']}"> Reorder: <input name="reorder_level" type="number" value="{it['reorder_level']}"><br>
    <button type="submit">SAVE CORRECTION</button></form><a href="/">Back</a>"""
@app.route("/update_item/<int:id>", methods=["POST"])
def update_item(id):
    if not is_admin(): return "Admin only"
    conn=get_db(); conn.execute("UPDATE items SET name=?, name_key=?, buy_price=?, sell_price=?, stock=?, min_stock=?, max_stock=?, reorder_level=? WHERE id=? AND shop_id=?",
        (display(request.form['name']), norm(request.form['name']), int(request.form['buy_price']), int(request.form['sell_price']), int(request.form['stock']), int(request.form['min_stock']), int(request.form['max_stock']), int(request.form['reorder_level']), id, session["shop_id"]))
    conn.commit(); conn.close(); return redirect("/")
@app.route("/delete_item/<int:id>")
def delete_item(id):
    if not is_admin(): return "Admin only"
    conn=get_db(); conn.execute("DELETE FROM items WHERE id=? AND shop_id=?", (id,session["shop_id"])); conn.commit(); conn.close(); return redirect("/")
@app.route("/delete_sale/<int:id>")
def delete_sale(id):
    if not is_admin(): return "Admin only"
    conn=get_db(); r=conn.execute("SELECT * FROM sales WHERE id=? AND shop_id=?", (id,session["shop_id"])).fetchone()
    if r:
        item=conn.execute("SELECT * FROM items WHERE shop_id=? AND name_key=?", (session["shop_id"], norm(r['item']))).fetchone()
        if item: conn.execute("UPDATE items SET stock=? WHERE id=?", (item['stock']+r['qty']+r['bonus_qty'], item['id']))
        conn.execute("DELETE FROM sales WHERE id=?", (id,))
    conn.commit(); conn.close(); return redirect("/")
@app.route("/delete_purchase/<int:id>")
def delete_purchase(id):
    if not is_admin(): return "Admin only"
    conn=get_db(); conn.execute("DELETE FROM purchases WHERE id=? AND shop_id=?", (id,session["shop_id"])); conn.commit(); conn.close(); return redirect("/")
@app.route("/delete_debtor/<int:id>")
def delete_debtor(id):
    if not is_admin(): return "Admin only"
    conn=get_db(); conn.execute("DELETE FROM debtors WHERE id=? AND shop_id=?", (id,session["shop_id"])); conn.commit(); conn.close(); return redirect("/")
@app.route("/delete_loss/<int:id>")
def delete_loss(id):
    if not is_admin(): return "Admin only"
    conn=get_db(); r=conn.execute("SELECT * FROM losses WHERE id=? AND shop_id=?", (id,session["shop_id"])).fetchone()
    if r:
        item=conn.execute("SELECT * FROM items WHERE shop_id=? AND name_key=?", (session["shop_id"], norm(r['item']))).fetchone()
        if item: conn.execute("UPDATE items SET stock=? WHERE id=?", (item['stock']+r['qty'], item['id']))
        conn.execute("DELETE FROM losses WHERE id=?", (id,))
    conn.commit(); conn.close(); return redirect("/")

@app.route("/export")
def export():
    if not is_admin(): return "Admin only - Salesperson cannot export"
    sid=session["shop_id"]; conn=get_db(); rows=conn.execute("SELECT date, item, qty, bonus_qty, discount, amount, profit FROM sales WHERE shop_id=?", (sid,)).fetchall(); conn.close()
    output=io.StringIO(); w=csv.writer(output); w.writerow(["Date","Item","Qty","Bonus","Discount","Amount","Profit"])
    for r in rows: w.writerow([r['date'],r['item'],r['qty'],r['bonus_qty'],r['discount'],r['amount'],r['profit']])
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition":"attachment;filename=sales_report.csv"})

if __name__=="__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
