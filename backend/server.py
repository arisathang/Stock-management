from flask import Flask, jsonify, request
from flask_cors import CORS
import psycopg2, os, json
import psycopg2.extras
from datetime import date

from prediction import calculate_orders
from optimization import find_best_vendor_for_item
from report import generate_stock_alerts

app = Flask(__name__)
CORS(app)

DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = "5432"

def get_db_connection():
    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST, port=DB_PORT)
    return conn

@app.route('/stock-status', methods=['GET'])
def get_stock_status():
    """
    Fetches stock levels and daily movements for a given date.
    """
    record_date_str = request.args.get('date', date.today().isoformat())
    
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # This single, powerful query does everything:
        # 1. Calculates the total remaining stock up to the selected date.
        # 2. Calculates the total stock IN for the selected date.
        # 3. Calculates the total stock OUT for the selected date.
        query = """
            SELECT 
                p.id, p.name, p.unit, p.image_url, 
                p.min_stock, p.max_stock, p.last_year_prediction,
                COALESCE(
                    (SELECT SUM(m.quantity) 
                     FROM stock_movements m 
                     WHERE m.product_id = p.id AND m.movement_date::date <= %s),
                    0
                ) as remaining_stock,
                COALESCE(
                    (SELECT SUM(m.quantity) 
                     FROM stock_movements m 
                     WHERE m.product_id = p.id AND m.movement_type = 'IN' AND m.movement_date::date = %s),
                    0
                ) as daily_in,
                COALESCE(
                    (SELECT SUM(m.quantity) 
                     FROM stock_movements m 
                     WHERE m.product_id = p.id AND m.movement_type != 'IN' AND m.movement_date::date = %s),
                    0
                ) as daily_out
            FROM products p
            ORDER BY p.name;
        """
        cur.execute(query, (record_date_str, record_date_str, record_date_str))

        products = [dict(row) for row in cur.fetchall()]
        cur.close()
        alerts = generate_stock_alerts(products)
        conn.close()
        
        return jsonify({"stockItems": products, "alerts": alerts})
    except Exception as e:
        print(f"Error fetching stock status: {e}")
        return jsonify({"error": "Failed to fetch stock status"}), 500

@app.route('/record-movement', methods=['POST'])
def record_movement():
    try:
        data = request.json
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO stock_movements (product_id, quantity, movement_type, description) VALUES (%s, %s, %s, %s);",
            (data['productId'], data['quantity'], data['movementType'], data['description'])
        )
        cur.execute(
            "UPDATE products SET remaining_stock = remaining_stock + %s WHERE id = %s;",
            (data['quantity'], data['productId'])
        )
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        print(f"Error recording stock movement: {e}")
        return jsonify({"error": "Failed to record movement"}), 500

@app.route('/movement-log', methods=['GET'])
def get_movement_log():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("""
            SELECT m.quantity, m.movement_type, m.description, m.movement_date, p.name as product_name
            FROM stock_movements m JOIN products p ON m.product_id = p.id
            ORDER BY m.movement_date DESC;
        """)
        logs = [dict(row) for row in cur.fetchall()]
        cur.close()
        conn.close()
        return jsonify(logs)
    except Exception as e:
        print(f"Error fetching movement log: {e}")
        return jsonify({"error": "Failed to fetch movement log"}), 500

@app.route('/vendors', methods=['GET'])
def get_vendors():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute('SELECT id, name FROM vendors ORDER BY name;')
        vendors = [dict(row) for row in cur.fetchall()]
        cur.close()
        conn.close()
        return jsonify(vendors)
    except Exception as e:
        print(f"Error fetching vendors: {e}")
        return jsonify({"error": "Failed to fetch vendors"}), 500

@app.route('/generate-invoice', methods=['POST'])
def generate_invoice():
    try:
        data = request.json
        current_stock_levels = data['stockItems']
        vendor_filter = data.get('vendorFilter', [])
        conn = get_db_connection()
        items_to_order = calculate_orders(current_stock_levels, conn)
        vendor_orders = {}
        for item in items_to_order:
            best_option = find_best_vendor_for_item(item, conn, vendor_filter)
            if best_option and best_option['vendor_id']:
                vendor_id = best_option['vendor_id']
                if vendor_id not in vendor_orders:
                    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
                    cur.execute('SELECT name, shipping_cost, free_shipping_threshold FROM vendors WHERE id = %s;', (vendor_id,))
                    vendor_info = dict(cur.fetchone())
                    cur.close()
                    vendor_orders[vendor_id] = {"vendorName": vendor_info['name'], "items": [], "subtotal": 0, "bundleSavings": 0, "shippingCost": float(vendor_info['shipping_cost']), "originalShippingCost": float(vendor_info['shipping_cost']), "freeShippingThreshold": float(vendor_info['free_shipping_threshold'])}
                cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
                cur.execute('SELECT price, bundles FROM vendor_products WHERE vendor_id = %s AND product_id = %s;', (vendor_id, item['id']))
                pricing_info = dict(cur.fetchone())
                cur.close()
                vendor_orders[vendor_id]['items'].append({"id": item['id'], "name": item['name'], "unit": item['unit'], "quantity": item['order_amount'], "cost": float(best_option['cost']), "price": float(pricing_info['price']), "bundles": pricing_info['bundles'], "prediction": item['prediction'], "remaining_stock": item['remaining_stock']})
                vendor_orders[vendor_id]['bundleSavings'] += float(best_option['savings'])
        total_cost = 0; total_bundle_savings = 0; total_shipping_savings = 0
        for vendor_id, order in vendor_orders.items():
            order['subtotal'] = sum(item['cost'] for item in order['items'])
            if order['subtotal'] >= order['freeShippingThreshold']:
                order['shippingCost'] = 0
                total_shipping_savings += order['originalShippingCost']
            total_cost += order['subtotal'] + order['shippingCost']
            total_bundle_savings += order['bundleSavings']
        invoice = {"vendorOrders": vendor_orders, "totalCost": total_cost, "totalBundleSavings": total_bundle_savings, "totalShippingSavings": total_shipping_savings, "totalSavings": total_bundle_savings + total_shipping_savings}
        conn.close()
        return jsonify({"invoice": invoice})
    except Exception as e:
        print(f"Error generating invoice: {e}")
        return jsonify({"error": "Failed to generate invoice"}), 500

@app.route('/save-invoice', methods=['POST'])
def save_invoice():
    try:
        data = request.json
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO invoices (vendor_id, status, modified_by, items, total_cost) VALUES (%s, %s, %s, %s, %s) RETURNING id;",
            (data['vendorId'], data['status'], data['modifiedBy'], json.dumps(data['items']), data['totalCost'])
        )
        new_invoice_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"success": True, "invoiceId": new_invoice_id})
    except Exception as e:
        print(f"Error saving invoice: {e}")
        return jsonify({"error": "Failed to save invoice"}), 500

@app.route('/update-invoice-status', methods=['POST'])
def update_invoice_status():
    try:
        data = request.json
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("UPDATE invoices SET status = %s, modified_by = %s WHERE id = %s;", (data['newStatus'], data['changedBy'], data['invoiceId']))
        cur.execute("INSERT INTO invoice_status_logs (invoice_id, old_status, new_status, changed_by) VALUES (%s, %s, %s, %s);", (data['invoiceId'], data['oldStatus'], data['newStatus'], data['changedBy']))
        if data['newStatus'] == 'Approved':
            cur.execute("SELECT items, vendor_id FROM invoices WHERE id = %s;", (data['invoiceId'],))
            invoice_data = cur.fetchone()
            items = invoice_data['items']
            vendor_id = invoice_data['vendor_id']
            cur.execute("SELECT name FROM vendors WHERE id = %s;", (vendor_id,))
            vendor_name = cur.fetchone()['name']
            for item in items:
                description = f"Received from {vendor_name} order #{data['invoiceId']}"
                cur.execute("INSERT INTO stock_movements (product_id, quantity, movement_type, description) VALUES (%s, %s, 'IN', %s);", (item['id'], item['quantity'], description))
                cur.execute("UPDATE products SET remaining_stock = remaining_stock + %s WHERE id = %s;", (item['quantity'], item['id']))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        print(f"Error updating invoice status: {e}")
        return jsonify({"error": "Failed to update status"}), 500

@app.route('/invoice-logs/<int:invoice_id>', methods=['GET'])
def get_invoice_logs(invoice_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SELECT new_status, changed_by, change_date FROM invoice_status_logs WHERE invoice_id = %s ORDER BY change_date DESC;", (invoice_id,))
        logs = [dict(row) for row in cur.fetchall()]
        cur.close()
        conn.close()
        return jsonify(logs)
    except Exception as e:
        print(f"Error fetching invoice logs: {e}")
        return jsonify({"error": "Failed to fetch invoice logs"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
