from flask import Flask, jsonify, request
from flask_cors import CORS
import psycopg2, os, json
import psycopg2.extras
from datetime import date, timedelta
from dotenv import load_dotenv
from decimal import Decimal
import traceback

load_dotenv()
# non-AI calculations
from calculations import calculate_orders, optimize_purchases

# AI optimizing
from llm_integration import OLLAMA_ENABLED, calculate_orders_with_ai, generate_optimized_invoice_with_ai
from report import generate_stock_alerts

app = Flask(__name__)
CORS(app)

# Custom JSON encoder to handle Decimal types from the database
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(CustomJSONEncoder, self).default(obj)
app.json_encoder = CustomJSONEncoder

DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = "5432"

def get_db_connection():
    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST, port=DB_PORT)
    return conn

@app.route('/daily-spending', methods=['GET'])
def get_daily_spending():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        today = date.today()
        cur.execute("SELECT invoice_date, SUM(total_cost) as total_spent FROM invoices WHERE status = 'Approved' AND invoice_date = %s GROUP BY invoice_date;", (today,))
        return jsonify([dict(row) for row in cur.fetchall()])
    except Exception as e:
        print(f"Error fetching daily spending: {e}")
        return jsonify({"error": "Failed to fetch daily spending"}), 500

@app.route('/daily-spending-breakdown', methods=['GET'])
def get_daily_spending_breakdown():
    invoice_date_str = request.args.get('date')
    if not invoice_date_str:
        return jsonify({"error": "A date parameter is required"}), 400
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        query = """
            SELECT i.items, v.name as vendor_name, i.total_cost,
                   CASE WHEN (i.total_cost - v.shipping_cost) >= v.free_shipping_threshold THEN 0 ELSE v.shipping_cost END as shipping_cost
            FROM invoices i JOIN vendors v ON i.vendor_id = v.id
            WHERE i.status = 'Approved' AND i.invoice_date = %s;
        """
        cur.execute(query, (invoice_date_str,))
        breakdown = []
        for row in cur.fetchall():
            items_with_savings = [{'savings': item['quantity'] * item['price'] - item['cost'], **item} for item in row['items']]
            breakdown.append({"vendorName": row['vendor_name'], "items": items_with_savings, "totalCost": row['total_cost'], "shippingCost": row['shipping_cost']})
        return jsonify(breakdown)
    except Exception as e:
        print(f"Error fetching daily spending breakdown: {e}")
        return jsonify({"error": "Failed to fetch spending breakdown"}), 500

@app.route('/stock-status', methods=['GET'])
def get_stock_status():
    record_date_str = request.args.get('date', date.today().isoformat())
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        query = """
            SELECT p.id, p.name, p.unit, p.image_url, p.min_stock, p.max_stock, p.last_year_prediction,
                   COALESCE((SELECT SUM(m.quantity) FROM stock_movements m WHERE m.product_id = p.id AND m.movement_date::date <= %s), 0) as remaining_stock,
                   COALESCE((SELECT SUM(m.quantity) FROM stock_movements m WHERE m.product_id = p.id AND m.movement_type = 'IN' AND m.movement_date::date = %s), 0) as daily_in,
                   COALESCE((SELECT SUM(m.quantity) FROM stock_movements m WHERE m.product_id = p.id AND m.movement_type != 'IN' AND m.movement_date::date = %s), 0) as daily_out
            FROM products p ORDER BY p.name;
        """
        cur.execute(query, (record_date_str, record_date_str, record_date_str))
        products = [dict(row) for row in cur.fetchall()]
        alerts = generate_stock_alerts(products)
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
        cur.execute("INSERT INTO stock_movements (product_id, quantity, movement_type, description, total_cost) VALUES (%s, %s, %s, %s, %s);",
                    (data['productId'], data['quantity'], data['movementType'], data['description'], data.get('totalCost', 0)))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        print(f"Error recording stock movement: {e}")
        return jsonify({"error": "Failed to record movement"}), 500

@app.route('/movement-log', methods=['GET'])
def get_movement_log():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        query = """
            SELECT m.quantity, m.movement_type, m.description, m.movement_date, m.total_cost, p.name as product_name, i.modified_by as approved_by
            FROM stock_movements m JOIN products p ON m.product_id = p.id
            LEFT JOIN invoices i ON m.description LIKE 'Received from % order #' || i.id
            ORDER BY m.movement_date DESC;
        """
        cur.execute(query)
        return jsonify([dict(row) for row in cur.fetchall()])
    except Exception as e:
        print(f"Error fetching movement log: {e}")
        return jsonify({"error": "Failed to fetch movement log"}), 500

@app.route('/vendors', methods=['GET'])
def get_vendors():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute('SELECT id, name FROM vendors ORDER BY name;')
        return jsonify([dict(row) for row in cur.fetchall()])
    except Exception as e:
        print(f"Error fetching vendors: {e}")
        return jsonify({"error": "Failed to fetch vendors"}), 500

@app.route('/vendor-products/<vendor_id>', methods=['GET'])
def get_vendor_products(vendor_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SELECT p.id, p.name, p.unit, vp.price, vp.bundles FROM products p JOIN vendor_products vp ON p.id = vp.product_id WHERE vp.vendor_id = %s ORDER BY p.name;", (vendor_id,))
        return jsonify([dict(row) for row in cur.fetchall()])
    except Exception as e:
        print(f"Error fetching vendor products: {e}")
        return jsonify({"error": "Failed to fetch vendor products"}), 500

def _calculate_item_cost_with_bundles(quantity, price, bundles_json):
    cost = 0
    remaining_qty = quantity
    non_discounted_cost = quantity * float(price)
    if bundles_json:
        bundles = sorted(bundles_json, key=lambda b: b['quantity'], reverse=True)
        for bundle in bundles:
            num_bundles = remaining_qty // bundle['quantity']
            if num_bundles > 0:
                cost += num_bundles * bundle['price']
                remaining_qty -= num_bundles * bundle['quantity']
    cost += remaining_qty * float(price)
    savings = non_discounted_cost - cost
    return {"cost": cost, "savings": savings}

@app.route('/generate-invoice', methods=['POST'])
def generate_invoice():
    try:
        data = request.json
        conn = get_db_connection()
        
        print("🤖 Using AI to determine order quantities...")
        items_to_order = calculate_orders_with_ai(data['stockItems'], conn)
        
        if not items_to_order:
             return jsonify({"invoice": {"vendorOrders": {}, "totalCost": 0, "totalBundleSavings": 0, "totalShippingSavings": 0, "totalSavings": 0}})

        if not OLLAMA_ENABLED:
            print("🔴 AI features disabled. Cannot generate invoice.")
            return jsonify({"error": "AI features are disabled, cannot generate an optimized invoice."}), 503

        print("🤖 Using AI for cost optimization...")
        optimized_plan = generate_optimized_invoice_with_ai(items_to_order, conn, data.get('vendorFilter', []))
        
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute('SELECT id, name, shipping_cost, free_shipping_threshold FROM vendors;')
        all_vendors = [dict(row) for row in cur.fetchall()]
        vendors_by_id = {v['id']: v for v in all_vendors}
        vendors_by_name = {v['name']: v for v in all_vendors}
        
        vendor_orders = {}
        for key, plan in optimized_plan.items():
            vendor_key_as_int = None
            try:
                vendor_key_as_int = int(key)
            except (ValueError, TypeError):
                pass

            vendor_info = vendors_by_id.get(vendor_key_as_int) or vendors_by_name.get(key)
            
            if not vendor_info:
                print(f"⚠️ Warning: AI returned an unknown vendor key: '{key}'. Skipping.")
                continue
            
            vendor_id = vendor_info['id']

            vendor_orders[vendor_id] = {
                "vendorName": vendor_info['name'], "items": [], "subtotal": 0, "bundleSavings": 0,
                "shippingCost": float(vendor_info['shipping_cost']),
                "originalShippingCost": float(vendor_info['shipping_cost']),
                "freeShippingThreshold": float(vendor_info['free_shipping_threshold'])
            }

            for item_plan in plan.get('items', []):
                product_id = item_plan.get('product_id')
                raw_quantity = item_plan.get('quantity')
                quantity = None
                if raw_quantity is not None:
                    try:
                        quantity = int(raw_quantity)
                    except (ValueError, TypeError):
                        print(f"⚠️ Warning: AI returned a non-numeric quantity: '{raw_quantity}'. Skipping item.")
                        continue
                
                if not product_id or not quantity:
                    print(f"⚠️ Warning: AI returned an incomplete item plan: '{item_plan}'. Skipping.")
                    continue

                original_item = next((item for item in items_to_order if item['id'] == product_id), None)
                if not original_item: continue

                cur.execute('SELECT price, bundles FROM vendor_products WHERE vendor_id = %s AND product_id = %s;', (vendor_id, product_id))
                pricing_info = cur.fetchone()
                if not pricing_info:
                    print(f"⚠️ Warning: Could not find pricing for product '{product_id}' from vendor '{vendor_id}'. Skipping.")
                    continue
                
                cost_details = _calculate_item_cost_with_bundles(quantity, pricing_info['price'], pricing_info['bundles'])
                vendor_orders[vendor_id]['bundleSavings'] += cost_details['savings']
                vendor_orders[vendor_id]['items'].append({
                    "id": original_item['id'], "name": original_item['name'], "unit": original_item['unit'],
                    "quantity": quantity, "cost": cost_details['cost'], "price": pricing_info['price'],
                    "bundles": pricing_info['bundles'], "prediction": original_item['prediction'],
                    "remaining_stock": original_item['remaining_stock']
                })
        cur.close()

        total_cost = 0; total_bundle_savings = 0; total_shipping_savings = 0
        for vendor_id, order in vendor_orders.items():
            order['subtotal'] = sum(i['cost'] for i in order['items'])
            if order['subtotal'] >= order['freeShippingThreshold']:
                order['shippingCost'] = 0
                total_shipping_savings += order['originalShippingCost']
            total_cost += order['subtotal'] + order['shippingCost']
            total_bundle_savings += order['bundleSavings']
        
        invoice = {"vendorOrders": vendor_orders, "totalCost": total_cost, "totalBundleSavings": total_bundle_savings, "totalShippingSavings": total_shipping_savings, "totalSavings": total_bundle_savings + total_shipping_savings}
        conn.close()
        return jsonify({"invoice": invoice})
    except Exception as e:
        print("!!! DETAILED ERROR IN /generate-invoice !!!")
        traceback.print_exc()
        return jsonify({"error": "Failed to generate invoice"}), 500
    
############################

# For non-AI logic

############################

# @app.route('/generate-invoice', methods=['POST'])
# def generate_invoice():
#     try:
#         data = request.json
#         conn = get_db_connection()
        
#         items_to_order = calculate_orders(data['stockItems'], conn)
        
#         if not items_to_order:
#              return jsonify({"invoice": {"vendorOrders": {}, "totalCost": 0, "totalBundleSavings": 0, "totalShippingSavings": 0, "totalSavings": 0}})

#         vendor_orders = {}
#         for item in items_to_order:
#             best_option = find_best_vendor_for_item(item, conn, data.get('vendorFilter', []))
#             if best_option['vendor_id']:
#                 vendor_id = best_option['vendor_id']
#                 if vendor_id not in vendor_orders:
#                     cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
#                     cur.execute('SELECT name, shipping_cost, free_shipping_threshold FROM vendors WHERE id = %s;', (vendor_id,))
#                     vendor_info = dict(cur.fetchone())
#                     vendor_orders[vendor_id] = {
#                         "vendorName": vendor_info['name'], "items": [], "subtotal": 0, "bundleSavings": 0,
#                         "shippingCost": float(vendor_info['shipping_cost']),
#                         "originalShippingCost": float(vendor_info['shipping_cost']),
#                         "freeShippingThreshold": float(vendor_info['free_shipping_threshold'])
#                     }
                
#                 vendor_orders[vendor_id]['items'].append({
#                     "id": item['id'], "name": item['name'], "unit": item['unit'],
#                     "quantity": item['order_amount'], "cost": best_option['cost'], "price": best_option['price'],
#                     "bundles": best_option['bundles'], "prediction": item['prediction'],
#                     "remaining_stock": item['remaining_stock']
#                 })

#         total_cost = 0; total_bundle_savings = 0; total_shipping_savings = 0
#         for vendor_id, order in vendor_orders.items():
#             order['subtotal'] = sum(i['cost'] for i in order['items'])
#             order['bundleSavings'] = sum(i['savings'] for i in order['items'] if 'savings' in i) # Recalculate savings
            
#             if order['subtotal'] >= order['freeShippingThreshold']:
#                 order['shippingCost'] = 0
#                 total_shipping_savings += order['originalShippingCost']
            
#             total_cost += order['subtotal'] + order['shippingCost']
#             total_bundle_savings += order['bundleSavings']
        
#         invoice = {"vendorOrders": vendor_orders, "totalCost": total_cost, "totalBundleSavings": total_bundle_savings, "totalShippingSavings": total_shipping_savings, "totalSavings": total_bundle_savings + total_shipping_savings}
#         conn.close()
#         return jsonify({"invoice": invoice})
#     except Exception as e:
#         print("!!! DETAILED ERROR IN /generate-invoice !!!")
#         traceback.print_exc()
#         return jsonify({"error": "Failed to generate invoice"}), 500
    
#############################################

@app.route('/save-invoice', methods=['POST'])
def save_invoice():
    try:
        data = request.json
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        cur.execute("INSERT INTO invoices (vendor_id, status, modified_by, items, total_cost) VALUES (%s, %s, %s, %s, %s) RETURNING id;",
                    (data['vendorId'], data['status'], data['modifiedBy'], json.dumps(data['items']), data['totalCost']))
        new_invoice_id = cur.fetchone()['id']

        cur.execute("INSERT INTO invoice_status_logs (invoice_id, old_status, new_status, changed_by) VALUES (%s, %s, %s, %s);",
                    (new_invoice_id, 'N/A', data['status'], data['modifiedBy']))

        if data['status'] == 'Approved':
            cur.execute("SELECT name FROM vendors WHERE id = %s;", (data['vendorId'],))
            vendor_name = cur.fetchone()['name']
            for item in data['items']:
                description = f"Received from {vendor_name} order #{new_invoice_id}"
                cur.execute("INSERT INTO stock_movements (product_id, quantity, movement_type, description, total_cost) VALUES (%s, %s, 'IN', %s, %s);", 
                            (item['id'], item['quantity'], description, item['cost']))
        
        conn.commit()
        return jsonify({"success": True, "invoiceId": new_invoice_id})
    except Exception as e:
        print(f"Error saving invoice: {e}")
        return jsonify({"error": "Failed to save invoice"}), 500

@app.route('/update-invoice/<int:invoice_id>', methods=['POST'])
def update_invoice(invoice_id):
    try:
        data = request.json
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        cur.execute("SELECT status FROM invoices WHERE id = %s;", (invoice_id,))
        old_status = cur.fetchone()['status']

        cur.execute("UPDATE invoices SET status = %s, modified_by = %s, items = %s, total_cost = %s WHERE id = %s;",
                    (data['status'], data['modifiedBy'], json.dumps(data['items']), data['totalCost'], invoice_id))

        if old_status != data['status']:
            cur.execute("INSERT INTO invoice_status_logs (invoice_id, old_status, new_status, changed_by) VALUES (%s, %s, %s, %s);",
                        (invoice_id, old_status, data['status'], data['modifiedBy']))

        if data['status'] == 'Approved' and old_status != 'Approved':
            cur.execute("SELECT name FROM vendors WHERE id = %s;", (data['vendorId'],))
            vendor_name = cur.fetchone()['name']
            for item in data['items']:
                description = f"Received from {vendor_name} order #{invoice_id}"
                cur.execute("INSERT INTO stock_movements (product_id, quantity, movement_type, description, total_cost) VALUES (%s, %s, 'IN', %s, %s);", 
                            (item['id'], item['quantity'], description, item['cost']))
        
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        print(f"Error updating invoice: {e}")
        return jsonify({"error": "Failed to update invoice"}), 500

@app.route('/invoice-logs/<int:invoice_id>', methods=['GET'])
def get_invoice_logs(invoice_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SELECT new_status, changed_by, change_date FROM invoice_status_logs WHERE invoice_id = %s ORDER BY change_date DESC;", (invoice_id,))
        return jsonify([dict(row) for row in cur.fetchall()])
    except Exception as e:
        print(f"Error fetching invoice logs: {e}")
        return jsonify({"error": "Failed to fetch invoice logs"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
