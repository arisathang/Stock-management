from flask import Flask, jsonify, request
from flask_cors import CORS
import psycopg2, os, json
import psycopg2.extras
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv()

from prediction import calculate_orders
# from optimization import find_best_vendor_for_item
from report import generate_stock_alerts
from llm_integration import calculate_orders_with_ai, generate_optimized_invoice_with_ai

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

@app.route('/daily-spending', methods=['GET'])
def get_daily_spending():
    """Calculates the total spending on approved invoices for today."""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        today = date.today()
        query = """
            SELECT invoice_date, SUM(total_cost) as total_spent
            FROM invoices
            WHERE status = 'Approved' AND invoice_date = %s
            GROUP BY invoice_date;
        """
        cur.execute(query, (today,))
        spending_data = [dict(row) for row in cur.fetchall()]
        
        cur.close()
        conn.close()
        return jsonify(spending_data)
    except Exception as e:
        print(f"Error fetching daily spending: {e}")
        return jsonify({"error": "Failed to fetch daily spending"}), 500

@app.route('/daily-spending-breakdown', methods=['GET'])
def get_daily_spending_breakdown():
    """Fetches all items from approved invoices for a specific date."""
    invoice_date_str = request.args.get('date')
    if not invoice_date_str:
        return jsonify({"error": "A date parameter is required"}), 400
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        query = """
            SELECT 
                i.items, 
                v.name as vendor_name, 
                i.total_cost,
                -- Calculate shipping cost based on free shipping threshold
                CASE 
                    WHEN (i.total_cost - v.shipping_cost) >= v.free_shipping_threshold THEN 0 
                    ELSE v.shipping_cost 
                END as shipping_cost
            FROM invoices i
            JOIN vendors v ON i.vendor_id = v.id
            WHERE i.status = 'Approved' AND i.invoice_date = %s;
        """
        cur.execute(query, (invoice_date_str,))
        
        breakdown = []
        for row in cur.fetchall():
            # Calculate bundle savings for each item
            items_with_savings = []
            for item in row['items']:
                # This is a simplified savings calculation. A more robust solution
                # would store the actual savings per item in the invoice JSON.
                non_discounted_cost = item['quantity'] * item['price']
                savings = non_discounted_cost - item['cost']
                item['savings'] = savings
                items_with_savings.append(item)

            breakdown.append({
                "vendorName": row['vendor_name'],
                "items": items_with_savings,
                "totalCost": float(row['total_cost']),
                "shippingCost": float(row['shipping_cost'])
            })
            
        cur.close()
        conn.close()
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
            SELECT 
                p.id, p.name, p.unit, p.image_url, 
                p.min_stock, p.max_stock, p.last_year_prediction,
                COALESCE((SELECT SUM(m.quantity) FROM stock_movements m WHERE m.product_id = p.id AND m.movement_date::date <= %s), 0) as remaining_stock,
                COALESCE((SELECT SUM(m.quantity) FROM stock_movements m WHERE m.product_id = p.id AND m.movement_type = 'IN' AND m.movement_date::date = %s), 0) as daily_in,
                COALESCE((SELECT SUM(m.quantity) FROM stock_movements m WHERE m.product_id = p.id AND m.movement_type != 'IN' AND m.movement_date::date = %s), 0) as daily_out
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
            "INSERT INTO stock_movements (product_id, quantity, movement_type, description, total_cost) VALUES (%s, %s, %s, %s, %s);",
            (data['productId'], data['quantity'], data['movementType'], data['description'], data.get('totalCost', 0))
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
        query = """
            SELECT 
                m.quantity, 
                m.movement_type, 
                m.description, 
                m.movement_date, 
                m.total_cost,
                p.name as product_name,
                i.modified_by as approved_by
            FROM stock_movements m
            JOIN products p ON m.product_id = p.id
            LEFT JOIN invoices i ON m.description LIKE 'Received from % order #' || i.id
            ORDER BY m.movement_date DESC;
        """
        cur.execute(query)
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

@app.route('/vendor-products/<vendor_id>', methods=['GET'])
def get_vendor_products(vendor_id):
    """Fetches all products sold by a specific vendor."""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        query = """
            SELECT p.id, p.name, p.unit, vp.price, vp.bundles
            FROM products p
            JOIN vendor_products vp ON p.id = vp.product_id
            WHERE vp.vendor_id = %s
            ORDER BY p.name;
        """
        cur.execute(query, (vendor_id,))
        products = [dict(row) for row in cur.fetchall()]
        cur.close()
        conn.close()
        return jsonify(products)
    except Exception as e:
        print(f"Error fetching vendor products: {e}")
        return jsonify({"error": "Failed to fetch vendor products"}), 500

# @app.route('/generate-invoice', methods=['POST'])
# def generate_invoice():
#     try:
#         data = request.json
#         current_stock_levels = data['stockItems']
#         vendor_filter = data.get('vendorFilter', [])
#         conn = get_db_connection()
#         items_to_order = calculate_orders(current_stock_levels, conn)
#         vendor_orders = {}
#         for item in items_to_order:
#             best_option = find_best_vendor_for_item(item, conn, vendor_filter)
#             if best_option and best_option['vendor_id']:
#                 vendor_id = best_option['vendor_id']
#                 if vendor_id not in vendor_orders:
#                     cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
#                     cur.execute('SELECT name, shipping_cost, free_shipping_threshold FROM vendors WHERE id = %s;', (vendor_id,))
#                     vendor_info = dict(cur.fetchone())
#                     cur.close()
#                     vendor_orders[vendor_id] = {"vendorName": vendor_info['name'], "items": [], "subtotal": 0, "bundleSavings": 0, "shippingCost": float(vendor_info['shipping_cost']), "originalShippingCost": float(vendor_info['shipping_cost']), "freeShippingThreshold": float(vendor_info['free_shipping_threshold'])}
#                 cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
#                 cur.execute('SELECT price, bundles FROM vendor_products WHERE vendor_id = %s AND product_id = %s;', (vendor_id, item['id']))
#                 pricing_info = dict(cur.fetchone())
#                 cur.close()
#                 vendor_orders[vendor_id]['items'].append({"id": item['id'], "name": item['name'], "unit": item['unit'], "quantity": item['order_amount'], "cost": float(best_option['cost']), "price": float(pricing_info['price']), "bundles": pricing_info['bundles'], "prediction": item['prediction'], "remaining_stock": item['remaining_stock']})
#                 vendor_orders[vendor_id]['bundleSavings'] += float(best_option['savings'])
#         total_cost = 0; total_bundle_savings = 0; total_shipping_savings = 0
#         for vendor_id, order in vendor_orders.items():
#             order['subtotal'] = sum(item['cost'] for item in order['items'])
#             if order['subtotal'] >= order['freeShippingThreshold']:
#                 order['shippingCost'] = 0
#                 total_shipping_savings += order['originalShippingCost']
#             total_cost += order['subtotal'] + order['shippingCost']
#             total_bundle_savings += order['bundleSavings']
#         invoice = {"vendorOrders": vendor_orders, "totalCost": total_cost, "totalBundleSavings": total_bundle_savings, "totalShippingSavings": total_shipping_savings, "totalSavings": total_bundle_savings + total_shipping_savings}
#         conn.close()
#         return jsonify({"invoice": invoice})
#     except Exception as e:
#         print(f"Error generating invoice: {e}")
#         return jsonify({"error": "Failed to generate invoice"}), 500
    
@app.route('/generate-invoice', methods=['POST'])
def generate_invoice():
    try:
        data = request.json
        current_stock_levels = data['stockItems']
        vendor_filter = data.get('vendorFilter', [])
        conn = get_db_connection()
        
        # 1. Use the ORIGINAL rule-based function for prediction
        items_to_order = calculate_orders(current_stock_levels, conn)
        
        # 2. Use the NEW AI-powered function to generate an optimized purchasing plan
        optimized_plan = generate_optimized_invoice_with_ai(items_to_order, conn, vendor_filter)

        # 3. Structure the AI's plan into the final invoice format
        vendor_orders = {}
        total_cost = 0
        total_bundle_savings = 0 
        total_shipping_savings = 0

        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        for vendor_id, plan in optimized_plan.items():
            cur.execute('SELECT name, shipping_cost, free_shipping_threshold FROM vendors WHERE id = %s;', (vendor_id,))
            vendor_info = dict(cur.fetchone())
            
            vendor_orders[vendor_id] = {
                "vendorName": vendor_info['name'],
                "items": [],
                "subtotal": 0,
                "bundleSavings": 0,
                "shippingCost": float(vendor_info['shipping_cost']),
                "originalShippingCost": float(vendor_info['shipping_cost']),
                "freeShippingThreshold": float(vendor_info['free_shipping_threshold'])
            }

            subtotal = 0
            for item_plan in plan['items']:
                original_item = next((item for item in items_to_order if item['id'] == item_plan['product_id']), None)
                if not original_item: continue

                cur.execute('SELECT price, bundles FROM vendor_products WHERE vendor_id = %s AND product_id = %s;', (vendor_id, item_plan['product_id']))
                pricing_info = dict(cur.fetchone())

                # This simplified cost calculation could be improved to show bundle savings
                item_cost = item_plan['quantity'] * float(pricing_info['price'])
                subtotal += item_cost

                vendor_orders[vendor_id]['items'].append({
                    "id": original_item['id'],
                    "name": original_item['name'],
                    "unit": original_item['unit'],
                    "quantity": item_plan['quantity'],
                    "cost": item_cost,
                    "price": float(pricing_info['price']),
                    "bundles": pricing_info['bundles'],
                    "prediction": original_item['prediction'],
                    "remaining_stock": original_item['remaining_stock']
                })
            
            vendor_orders[vendor_id]['subtotal'] = subtotal
            if subtotal >= vendor_orders[vendor_id]['freeShippingThreshold']:
                vendor_orders[vendor_id]['shippingCost'] = 0
                total_shipping_savings += vendor_orders[vendor_id]['originalShippingCost']
            
            total_cost += subtotal + vendor_orders[vendor_id]['shippingCost']

        cur.close()
        
        invoice = {
            "vendorOrders": vendor_orders, 
            "totalCost": total_cost, 
            "totalBundleSavings": total_bundle_savings, 
            "totalShippingSavings": total_shipping_savings, 
            "totalSavings": total_bundle_savings + total_shipping_savings
        }
        
        conn.close()
        return jsonify({"invoice": invoice})
    except Exception as e:
        print(f"Error generating AI invoice: {e}")
        return jsonify({"error": "Failed to generate AI-powered invoice"}), 500
    
# @app.route('/generate-invoice', methods=['POST'])
# def generate_invoice():
#     try:
#         data = request.json
#         current_stock_levels = data['stockItems']
#         vendor_filter = data.get('vendorFilter', [])
#         conn = get_db_connection()
        
#         # 1. Use AI to predict what needs to be ordered
#         items_to_order = calculate_orders_with_ai(current_stock_levels, conn)
#         print(items_to_order)
#         # 2. Use AI to generate an optimized purchasing plan
#         optimized_plan = generate_optimized_invoice_with_ai(items_to_order, conn, vendor_filter)

#         # 3. Structure the AI's plan into the final invoice format
#         vendor_orders = {}
#         total_cost = 0
#         total_bundle_savings = 0 # Note: Detailed savings calculation would require more logic
#         total_shipping_savings = 0

#         cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

#         for vendor_id, plan in optimized_plan.items():
#             cur.execute('SELECT name, shipping_cost, free_shipping_threshold FROM vendors WHERE id = %s;', (vendor_id,))
#             vendor_info = dict(cur.fetchone())
            
#             vendor_orders[vendor_id] = {
#                 "vendorName": vendor_info['name'],
#                 "items": [],
#                 "subtotal": 0,
#                 "bundleSavings": 0, # Simplified for this example
#                 "shippingCost": float(vendor_info['shipping_cost']),
#                 "originalShippingCost": float(vendor_info['shipping_cost']),
#                 "freeShippingThreshold": float(vendor_info['free_shipping_threshold'])
#             }

#             subtotal = 0
#             for item_plan in plan['items']:
#                 # Fetch full item details
#                 original_item = next((item for item in items_to_order if item['id'] == item_plan['product_id']), None)
#                 if not original_item: continue

#                 # This part is simplified. A full implementation would re-calculate the exact cost
#                 # based on the AI's recommended quantity to also calculate savings.
#                 # For now, we fetch the base price for display.
#                 cur.execute('SELECT price, bundles FROM vendor_products WHERE vendor_id = %s AND product_id = %s;', (vendor_id, item_plan['product_id']))
#                 pricing_info = dict(cur.fetchone())

#                 # A more robust solution would re-run the _calculate_item_cost logic here
#                 # to get the precise cost and savings for the AI-recommended order.
#                 # For brevity, we'll approximate cost.
#                 item_cost = item_plan['quantity'] * float(pricing_info['price'])
#                 subtotal += item_cost

#                 vendor_orders[vendor_id]['items'].append({
#                     "id": original_item['id'],
#                     "name": original_item['name'],
#                     "unit": original_item['unit'],
#                     "quantity": item_plan['quantity'],
#                     "cost": item_cost,
#                     "price": float(pricing_info['price']),
#                     "bundles": pricing_info['bundles'],
#                     "prediction": original_item['prediction'],
#                     "remaining_stock": original_item['remaining_stock']
#                 })
            
#             vendor_orders[vendor_id]['subtotal'] = subtotal
#             if subtotal >= vendor_orders[vendor_id]['freeShippingThreshold']:
#                 vendor_orders[vendor_id]['shippingCost'] = 0
#                 total_shipping_savings += vendor_orders[vendor_id]['originalShippingCost']
            
#             total_cost += subtotal + vendor_orders[vendor_id]['shippingCost']

#         cur.close()
        
#         invoice = {
#             "vendorOrders": vendor_orders, 
#             "totalCost": total_cost, 
#             "totalBundleSavings": total_bundle_savings, 
#             "totalShippingSavings": total_shipping_savings, 
#             "totalSavings": total_bundle_savings + total_shipping_savings
#         }
        
#         conn.close()
#         return jsonify({"invoice": invoice})
#     except Exception as e:
#         print(f"Error generating AI invoice: {e}")
#         return jsonify({"error": "Failed to generate AI-powered invoice"}), 500

@app.route('/save-invoice', methods=['POST'])
def save_invoice():
    try:
        data = request.json
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        cur.execute(
            "INSERT INTO invoices (vendor_id, status, modified_by, items, total_cost) VALUES (%s, %s, %s, %s, %s) RETURNING id;",
            (data['vendorId'], data['status'], data['modifiedBy'], json.dumps(data['items']), data['totalCost'])
        )
        new_invoice_id = cur.fetchone()['id']

        cur.execute(
            "INSERT INTO invoice_status_logs (invoice_id, old_status, new_status, changed_by) VALUES (%s, %s, %s, %s);",
            (new_invoice_id, 'N/A', data['status'], data['modifiedBy'])
        )

        if data['status'] == 'Approved':
            cur.execute("SELECT name FROM vendors WHERE id = %s;", (data['vendorId'],))
            vendor_name = cur.fetchone()['name']
            for item in data['items']:
                description = f"Received from {vendor_name} order #{new_invoice_id}"
                cur.execute(
                    "INSERT INTO stock_movements (product_id, quantity, movement_type, description, total_cost) VALUES (%s, %s, 'IN', %s, %s);", 
                    (item['id'], item['quantity'], description, item['cost'])
                )
        
        conn.commit()
        cur.close()
        conn.close()
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
        result = cur.fetchone()
        if not result: return jsonify({"error": "Invoice not found"}), 404
        old_status = result['status']

        cur.execute(
            "UPDATE invoices SET status = %s, modified_by = %s, items = %s, total_cost = %s WHERE id = %s;",
            (data['status'], data['modifiedBy'], json.dumps(data['items']), data['totalCost'], invoice_id)
        )

        if old_status != data['status']:
            cur.execute(
                "INSERT INTO invoice_status_logs (invoice_id, old_status, new_status, changed_by) VALUES (%s, %s, %s, %s);",
                (invoice_id, old_status, data['status'], data['modifiedBy'])
            )

        if data['status'] == 'Approved' and old_status != 'Approved':
            cur.execute("SELECT name FROM vendors WHERE id = %s;", (data['vendorId'],))
            vendor_name = cur.fetchone()['name']
            for item in data['items']:
                description = f"Received from {vendor_name} order #{invoice_id}"
                cur.execute(
                    "INSERT INTO stock_movements (product_id, quantity, movement_type, description, total_cost) VALUES (%s, %s, 'IN', %s, %s);", 
                    (item['id'], item['quantity'], description, item['cost'])
                )
        
        conn.commit()
        cur.close()
        conn.close()
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
        logs = [dict(row) for row in cur.fetchall()]
        cur.close()
        conn.close()
        return jsonify(logs)
    except Exception as e:
        print(f"Error fetching invoice logs: {e}")
        return jsonify({"error": "Failed to fetch invoice logs"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
