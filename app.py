from flask import Flask, render_template, request, redirect, session, send_file, url_for
import sqlite3, datetime, os
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors

app = Flask(__name__)
app.secret_key = "vyapar_pro_secret_99"

def db_conn():
    return sqlite3.connect("database.db")

# Table Setup
def init_db():
    conn = db_conn()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS products(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, barcode TEXT, purchase REAL, sell REAL, 
        stock INTEGER, purchase_date TEXT)""")
    
    c.execute("""CREATE TABLE IF NOT EXISTS customers(
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, mobile TEXT UNIQUE)""")
    
    c.execute("""CREATE TABLE IF NOT EXISTS sales(
        id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER, 
        product TEXT, qty INTEGER, total REAL, date TEXT)""")
    conn.commit()
    conn.close()

init_db()

@app.route("/")
def index():
    conn = db_conn()
    products = conn.execute("SELECT * FROM products").fetchall()
    conn.close()
    return render_template("index.html", products=products)

@app.route("/add_product", methods=["GET", "POST"])
def add_product():
    if request.method == "POST":
        conn = db_conn()
        conn.execute("""INSERT INTO products(name, barcode, purchase, sell, stock, purchase_date) 
                        VALUES (?,?,?,?,?,?)""", 
                     (request.form['name'], request.form['barcode'], request.form['purchase'], 
                      request.form['sell'], request.form['stock'], request.form['purchase_date']))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    return render_template("add_product.html")

@app.route("/delete_product/<int:id>")
def delete_product(id):
    conn = db_conn()
    conn.execute("DELETE FROM products WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route("/update_stock", methods=["POST"])
def update_stock():
    pid = request.form['pid']
    qty = int(request.form['qty'])
    action = request.form['action']
    conn = db_conn()
    if action == "add":
        conn.execute("UPDATE products SET stock = stock + ? WHERE id=?", (qty, pid))
    else:
        conn.execute("UPDATE products SET stock = MAX(stock - ?, 0) WHERE id=?", (qty, pid))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route("/sell", methods=["GET", "POST"])
def sell():
    conn = db_conn()
    products = conn.execute("SELECT * FROM products").fetchall()
    if request.method == "POST":
        p_id = request.form['product_id']
        qty = int(request.form['qty'])
        disc_p = float(request.form['discount'])
        gst_p = float(request.form['gst'])
        
        prod = conn.execute("SELECT name, sell, stock FROM products WHERE id=?", (p_id,)).fetchone()
        if not prod or qty > prod[2]: return "Low Stock!"

        subtotal = qty * prod[1]
        disc_amt = subtotal * (disc_p/100)
        taxable = subtotal - disc_amt
        gst_amt = taxable * (gst_p/100)
        grand_total = taxable + gst_amt

        # Customer Save
        conn.execute("INSERT OR IGNORE INTO customers(name, mobile) VALUES (?,?)", 
                     (request.form['c_name'], request.form['c_mobile']))
        cid = conn.execute("SELECT id FROM customers WHERE mobile=?", (request.form['c_mobile'],)).fetchone()[0]
        
        conn.execute("INSERT INTO sales(customer_id, product, qty, total, date) VALUES (?,?,?,?,?)",
                     (cid, prod[0], qty, grand_total, str(datetime.date.today())))
        conn.execute("UPDATE products SET stock = stock - ? WHERE id=?", (qty, p_id))
        conn.commit()
        
        session['bill_data'] = {
            "c_name": request.form['c_name'], "mobile": request.form['c_mobile'],
            "item": prod[0], "qty": qty, "rate": prod[1], "subtotal": subtotal,
            "disc": disc_amt, "gst": gst_amt, "total": grand_total, "date": str(datetime.date.today())
        }
        return render_template("bill_preview.html", b=session['bill_data'])
    return render_template("sell.html", products=products)

from reportlab.lib import colors
from reportlab.lib.units import inch

@app.route("/download_pdf")
def download_pdf():
    b = session.get('bill_data')
    if not b: return "No Data"
    
    path = "static/last_bill.pdf"
    c = canvas.Canvas(path, pagesize=A4)
    width, height = A4

    # --- Header: Business Info ---
    if os.path.exists("static/logo.png"):
        c.drawImage("static/logo.png", 50, height - 80, 50, 50)
    
    c.setFont("Helvetica-Bold", 16)
    c.drawString(110, height - 50, "APNA VYAPAR PVT LTD")
    c.setFont("Helvetica", 10)
    c.drawString(110, height - 65, "Main Road, Patna, Bihar - 800001")
    c.drawString(110, height - 78, "GSTIN: 10AAAAA0000A1Z5 | Contact: +91 6202794300")
    
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(width/2, height - 110, "TAX INVOICE")
    c.line(50, height - 115, 545, height - 115)

    # --- Customer & Invoice Details ---
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, height - 135, f"Billed To:")
    c.setFont("Helvetica", 10)
    c.drawString(50, height - 150, f"Name: {b['c_name']}")
    c.drawString(50, height - 165, f"Mobile: {b['mobile']}")
    
    c.setFont("Helvetica-Bold", 10)
    c.drawString(400, height - 135, f"Invoice No: #INV-{datetime.datetime.now().strftime('%M%S')}")
    c.setFont("Helvetica", 10)
    c.drawString(400, height - 150, f"Date: {b['date']}")

    # --- Table Header ---
    y = height - 200
    c.setFillColor(colors.lightgrey)
    c.rect(50, y, 495, 20, fill=1)
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(60, y + 6, "Description")
    c.drawString(250, y + 6, "Rate")
    c.drawString(350, y + 6, "Qty")
    c.drawString(450, y + 6, "Total Amount")

    # --- Table Body ---
    y -= 25
    c.setFont("Helvetica", 10)
    c.drawString(60, y, f"{b['item']}")
    c.drawString(250, y, f"Rs. {b['rate']}")
    c.drawString(350, y, f"{b['qty']}")
    c.drawString(450, y, f"Rs. {b['subtotal']}")
    
    c.line(50, y - 10, 545, y - 10)

    # --- Calculation Summary ---
    y -= 40
    c.setFont("Helvetica", 10)
    c.drawString(350, y, "Sub-Total:")
    c.drawRightString(540, y, f"Rs. {b['subtotal']}")
    
    y -= 15
    c.setFillColor(colors.red)
    c.drawString(350, y, "Discount:")
    c.drawRightString(540, y, f"- Rs. {b['disc']}")
    
    y -= 15
    c.setFillColor(colors.black)
    c.drawString(350, y, "GST Amount:")
    c.drawRightString(540, y, f"+ Rs. {b['gst']}")
    
    y -= 25
    c.setFont("Helvetica-Bold", 12)
    c.rect(345, y-5, 200, 25, fill=0)
    c.drawString(350, y, "GRAND TOTAL:")
    c.drawRightString(540, y, f"Rs. {b['total']}")

    # --- Footer ---
    y -= 80
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(50, y, "Terms: Goods once sold will not be taken back.")
    c.drawRightString(545, y, "For APNA VYAPAR")
    y -= 40
    c.drawRightString(545, y, "Authorized Signatory")
    
    c.setFont("Helvetica", 8)
    c.drawCentredString(width/2, 30, "This is a computer-generated invoice and does not require a physical signature.")

    c.save()
    return send_file(path, as_attachment=True)

@app.route("/customers")
def customers():
    conn = db_conn()
    data = conn.execute("""SELECT customers.name, customers.mobile, sales.product, sales.qty, sales.total, sales.date 
                           FROM sales JOIN customers ON sales.customer_id = customers.id ORDER BY sales.id DESC""").fetchall()
    conn.close()
    return render_template("customers.html", sales=data)

if __name__ == "__main__":
    app.run(debug=True)