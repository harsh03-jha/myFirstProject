import os, sqlite3, datetime
from flask import Flask, g, request, redirect, url_for, flash, render_template_string

app = Flask(__name__)
app.secret_key = "stylestock"
HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "warehouse.db")

def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db

@app.teardown_appcontext
def close(_):
    d = g.pop("db", None)
    if d: d.close()

def q(sql, a=()): return db().execute(sql, a).fetchall()

def run(sql, a=()):
    try:
        with db(): db().execute(sql, a)
        return True
    except sqlite3.Error as e:
        flash("Database error: " + str(e)); return False

def init():
    if not os.path.exists(DB):
        c = sqlite3.connect(DB); c.executescript(open(os.path.join(HERE, "schema.sql")).read()); c.close()

BASE = """<!doctype html><title>StyleStock WMS</title><style>
body{font-family:system-ui,sans-serif;margin:0;background:#f4f5f7;color:#222}
nav{background:#1f2a44;padding:12px 24px}nav a{color:#fff;margin-right:20px;text-decoration:none;font-weight:600}
main{max-width:1000px;margin:24px auto;padding:0 16px}
table{width:100%;border-collapse:collapse;background:#fff;margin-bottom:24px}
th,td{padding:8px 10px;border-bottom:1px solid #e3e5e8;text-align:left;font-size:14px}th{background:#e9ecf3}
.cards{display:flex;gap:16px;margin-bottom:24px}.card{flex:1;background:#fff;padding:16px;border-radius:8px}
.card b{font-size:26px;display:block}form label{display:block;margin:8px 0;font-size:14px}
input,select{padding:6px;width:260px}button,.btn{background:#1f2a44;color:#fff;border:0;padding:7px 14px;border-radius:5px;cursor:pointer;text-decoration:none;font-size:14px}
.red{background:#b3261e}.msg{background:#fde7e5;padding:10px;border-radius:5px;margin-bottom:12px}.low{color:#b3261e;font-weight:700}
</style><nav><a href="/">Dashboard</a><a href="/products">Products</a><a href="/stock">Stock In/Out</a><a href="/reports">Reports</a></nav><main>
{% for m in get_flashed_messages() %}<div class=msg>{{m}}</div>{% endfor %}{{body|safe}}</main>"""

def page(tpl, **ctx):
    return render_template_string(BASE, body=render_template_string(tpl, **ctx))

@app.route("/")
def dashboard():
    s = q("""SELECT (SELECT COUNT(*) FROM product) n, COALESCE(SUM(i.quantity),0) units,
             COALESCE(SUM(i.quantity*p.cost_price),0) val FROM inventory i JOIN product p USING(product_id)""")[0]
    low = q("""SELECT p.sku,p.name,SUM(i.quantity) qty,p.reorder_level FROM product p
               JOIN inventory i USING(product_id) GROUP BY p.product_id HAVING qty < p.reorder_level""")
    recent = q("""SELECT t.*,p.sku,w.name wh FROM stock_txn t JOIN product p USING(product_id)
                  JOIN warehouse w USING(warehouse_id) ORDER BY txn_id DESC LIMIT 5""")
    return page("""<h2>Dashboard</h2><div class=cards><div class=card>Products<b>{{s.n}}</b></div>
    <div class=card>Units in stock<b>{{s.units}}</b></div><div class=card>Stock value (cost)<b>₹{{'{:,.0f}'.format(s.val)}}</b></div>
    <div class=card>Low-stock items<b class=low>{{low|length}}</b></div></div>
    <h3>Low stock alerts</h3><table><tr><th>SKU<th>Product<th>Qty<th>Reorder level</tr>
    {% for r in low %}<tr><td>{{r.sku}}<td>{{r.name}}<td class=low>{{r.qty}}<td>{{r.reorder_level}}</tr>{% endfor %}</table>
    <h3>Recent transactions</h3><table><tr><th>Date<th>Type<th>SKU<th>Warehouse<th>Qty</tr>
    {% for r in recent %}<tr><td>{{r.txn_date}}<td>{{r.txn_type}}<td>{{r.sku}}<td>{{r.wh}}<td>{{r.quantity}}</tr>{% endfor %}</table>""",
    s=s, low=low, recent=recent)

# ---------- Products: search / list / add / update / delete ----------
@app.route("/products")
def products():
    term = request.args.get("q", "")
    like = f"%{term}%"
    rows = q("""SELECT p.*,c.name cat,s.name sup,COALESCE(SUM(i.quantity),0) qty FROM product p
                JOIN category c USING(category_id) JOIN supplier s USING(supplier_id)
                LEFT JOIN inventory i USING(product_id)
                WHERE p.sku LIKE ? OR p.name LIKE ? OR p.color LIKE ? OR c.name LIKE ?
                GROUP BY p.product_id ORDER BY p.product_id""", (like,)*4)
    return page("""<h2>Products</h2><form method=get style="margin-bottom:12px"><input name=q value="{{term}}" placeholder="Search SKU, name, colour, category">
    <button>Search</button> <a class=btn href="/products/new">+ Add product</a></form>
    <table><tr><th>SKU<th>Name<th>Size<th>Colour<th>Category<th>Supplier<th>Price<th>Stock<th></tr>
    {% for r in rows %}<tr><td>{{r.sku}}<td>{{r.name}}<td>{{r.size}}<td>{{r.color}}<td>{{r.cat}}<td>{{r.sup}}<td>₹{{r.sell_price}}<td>{{r.qty}}
    <td><a href="/products/{{r.product_id}}/edit">Edit</a>
    <form method=post action="/products/{{r.product_id}}/delete" style="display:inline" onsubmit="return confirm('Delete?')"><button class=red>Delete</button></form></tr>{% endfor %}</table>""",
    rows=rows, term=term)

FIELDS = [("sku","SKU"),("name","Name"),("size","Size"),("color","Colour"),("cost_price","Cost price"),("sell_price","Selling price"),("reorder_level","Reorder level")]
FORM = """<h2>{{'Edit' if p else 'Add'}} product</h2><form method=post>
{% for f,l in fields %}<label>{{l}}<br><input name={{f}} value="{{p[f] if p else ''}}" required></label>{% endfor %}
<label>Category<br><select name=category_id>{% for c in cats %}<option value={{c.category_id}} {{'selected' if p and p.category_id==c.category_id}}>{{c.name}}</option>{% endfor %}</select></label>
<label>Supplier<br><select name=supplier_id>{% for s in sups %}<option value={{s.supplier_id}} {{'selected' if p and p.supplier_id==s.supplier_id}}>{{s.name}}</option>{% endfor %}</select></label>
<button>Save</button> <a href="/products">Cancel</a></form>"""
COLS = [f for f,_ in FIELDS] + ["category_id", "supplier_id"]

@app.route("/products/new", methods=["GET", "POST"])
def product_new():
    if request.method == "POST":
        if run(f"INSERT INTO product({','.join(COLS)}) VALUES({','.join('?'*len(COLS))})", [request.form[c] for c in COLS]):
            return redirect("/products")
    return page(FORM, p=None, fields=FIELDS, cats=q("SELECT * FROM category"), sups=q("SELECT * FROM supplier"))

@app.route("/products/<int:pid>/edit", methods=["GET", "POST"])
def product_edit(pid):
    if request.method == "POST":
        if run(f"UPDATE product SET {','.join(c+'=?' for c in COLS)} WHERE product_id=?", [request.form[c] for c in COLS] + [pid]):
            return redirect("/products")
    p = q("SELECT * FROM product WHERE product_id=?", (pid,))[0]
    return page(FORM, p=p, fields=FIELDS, cats=q("SELECT * FROM category"), sups=q("SELECT * FROM supplier"))

@app.route("/products/<int:pid>/delete", methods=["POST"])
def product_delete(pid):
    run("DELETE FROM product WHERE product_id=?", (pid,))   # blocked by FK if the product has transactions
    return redirect("/products")

# ---------- Stock in / out ----------
@app.route("/stock", methods=["GET", "POST"])
def stock():
    if request.method == "POST":
        f, t = request.form, request.form["txn_type"]
        if run("INSERT INTO stock_txn(product_id,warehouse_id,txn_type,quantity,txn_date,supplier_id,customer_id) VALUES(?,?,?,?,?,?,?)",
               (f["product_id"], f["warehouse_id"], t, f["quantity"], f["txn_date"],
                f["supplier_id"] if t == "IN" else None, f["customer_id"] if t == "OUT" else None)):
            return redirect("/stock")
    rows = q("""SELECT t.*,p.sku,w.name wh,COALESCE(s.name,c.name) party FROM stock_txn t JOIN product p USING(product_id)
                JOIN warehouse w USING(warehouse_id) LEFT JOIN supplier s USING(supplier_id) LEFT JOIN customer c USING(customer_id)
                ORDER BY txn_id DESC LIMIT 15""")
    return page("""<h2>Stock In / Out</h2><form method=post>
    <label>Type<br><select name=txn_type><option value=IN>IN (from supplier)<option value=OUT>OUT (to customer)</select></label>
    <label>Product<br><select name=product_id>{% for p in prods %}<option value={{p.product_id}}>{{p.sku}} - {{p.name}}</option>{% endfor %}</select></label>
    <label>Warehouse<br><select name=warehouse_id>{% for w in whs %}<option value={{w.warehouse_id}}>{{w.name}}</option>{% endfor %}</select></label>
    <label>Quantity<br><input type=number min=1 name=quantity required></label>
    <label>Date<br><input type=date name=txn_date value="{{today}}" required></label>
    <label>Supplier (for IN)<br><select name=supplier_id>{% for s in sups %}<option value={{s.supplier_id}}>{{s.name}}</option>{% endfor %}</select></label>
    <label>Customer (for OUT)<br><select name=customer_id>{% for c in custs %}<option value={{c.customer_id}}>{{c.name}}</option>{% endfor %}</select></label>
    <button>Record</button></form><h3>Latest transactions</h3>
    <table><tr><th>#<th>Date<th>Type<th>SKU<th>Warehouse<th>Qty<th>Party</tr>
    {% for r in rows %}<tr><td>{{r.txn_id}}<td>{{r.txn_date}}<td>{{r.txn_type}}<td>{{r.sku}}<td>{{r.wh}}<td>{{r.quantity}}<td>{{r.party}}</tr>{% endfor %}</table>""",
    prods=q("SELECT * FROM product"), whs=q("SELECT * FROM warehouse"), sups=q("SELECT * FROM supplier"),
    custs=q("SELECT * FROM customer"), rows=rows, today=datetime.date.today().isoformat())

# ---------- Reports ----------
@app.route("/reports")
def reports():
    cat = q("""SELECT c.name,SUM(i.quantity) units,SUM(i.quantity*p.cost_price) val FROM category c JOIN product p USING(category_id)
               JOIN inventory i USING(product_id) GROUP BY c.category_id ORDER BY val DESC""")
    sup = q("""SELECT s.name,COUNT(*) n,SUM(t.quantity) units,SUM(t.quantity*p.cost_price) val FROM stock_txn t
               JOIN supplier s USING(supplier_id) JOIN product p USING(product_id) WHERE t.txn_type='IN' GROUP BY s.supplier_id ORDER BY val DESC""")
    return page("""<h2>Reports</h2><h3>1. Stock value by category</h3><table><tr><th>Category<th>Units<th>Value (cost)</tr>
    {% for r in cat %}<tr><td>{{r.name}}<td>{{r.units}}<td>₹{{'{:,.0f}'.format(r.val)}}</tr>{% endfor %}</table>
    <h3>2. Supplier-wise purchase summary</h3><table><tr><th>Supplier<th>Deliveries<th>Units<th>Purchase value</tr>
    {% for r in sup %}<tr><td>{{r.name}}<td>{{r.n}}<td>{{r.units}}<td>₹{{'{:,.0f}'.format(r.val)}}</tr>{% endfor %}</table>""", cat=cat, sup=sup)

init()
if __name__ == "__main__":
    app.run(debug=True)
