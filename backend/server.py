# server.py (with History)
# Handles date-based queries and saves stock updates to a history table.

from flask import Flask, jsonify, request
from flask_cors import CORS
import psycopg2
import os
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

@app.route('/api/stock-status', methods=['GET'])
def get_stock_status():
    """
    API for the Live Page: Fetches stock levels for a given date.
    If no date is provided, fetches the latest stock levels.
    """
    record_date_str = request.args.get('date') # e.g., '2025-08-11'
    
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        if record_date_str:
            # Fetch historical data
            query = """
                SELECT p.id, p.name, p.unit, p.image_url, h.remaining_stock, p.min_stock, p.max_stock, p.last_year_prediction
                FROM products p
                LEFT JOIN stock_history h ON p.id = h.product_id AND h.record_date = %s
                ORDER BY p.name;
            """
            cur.execute(query, (record_date_str,))
        else:
            # Fetch latest data from the main products table
            query = """
                SELECT id, name, unit, image_url, remaining_stock, min_stock, max_stock, last_year_prediction
                FROM products ORDER BY name;
            """
            cur.execute(query)

        products = [dict(row) for row in cur.fetchall()]
        # Handle cases where a product might not have a history entry for a specific date
        for p in products:
            if p['remaining_stock'] is None:
                p['remaining_stock'] = 0

        cur.close()
        alerts = generate_stock_alerts(products)
        conn.close()
        
        return jsonify({"stockItems": products, "alerts": alerts})
    except Exception as e:
        print(f"Error fetching stock status: {e}")
        return jsonify({"error": "Failed to fetch stock status"}), 500


@app.route('/api/update-stock', methods=['POST'])
def update_stock():
    """
    API for the Live Page: Updates the stock for a single item for a specific date.
    It updates both the main products table (for latest value) and the history table.
    """
    try:
        data = request.json
        item_id = data['id']
        remaining_stock = data['remainingStock']
        record_date = data.get('date', date.today().isoformat())

        conn = get_db_connection()
        cur = conn.cursor()

        # Update the history table for the given date
        # "ON CONFLICT" will either INSERT a new row or UPDATE the existing one for that day.
        history_query = """
            INSERT INTO stock_history (product_id, record_date, remaining_stock)
            VALUES (%s, %s, %s)
            ON CONFLICT (product_id, record_date) DO UPDATE
            SET remaining_stock = EXCLUDED.remaining_stock;
        """
        cur.execute(history_query, (item_id, record_date, remaining_stock))

        # If the update is for today, also update the main products table
        if record_date == date.today().isoformat():
            cur.execute(
                'UPDATE products SET remaining_stock = %s WHERE id = %s;',
                (remaining_stock, item_id)
            )
        
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"success": True, "message": f"Stock for {item_id} updated for {record_date}."})
    except Exception as e:
        print(f"Error updating stock: {e}")
        return jsonify({"error": "Failed to update stock"}), 500


# The /api/generate-invoice endpoint remains the same as the previous version.
@app.route('/api/generate-invoice', methods=['POST'])
def generate_invoice():
    try:
        current_stock_levels = request.json['stockItems']
        conn = get_db_connection()
        items_to_order = calculate_orders(current_stock_levels, conn)
        
        vendor_orders = {}
        # ... (rest of the function is unchanged)
        
        total_cost = 0
        total_bundle_savings = 0

        for item in items_to_order:
            best_option = find_best_vendor_for_item(item, conn)
            if best_option and best_option['vendor_id']:
                vendor_id = best_option['vendor_id']
                if vendor_id not in vendor_orders:
                    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
                    cur.execute('SELECT name, shipping_cost, free_shipping_threshold FROM vendors WHERE id = %s;', (vendor_id,))
                    vendor_info = dict(cur.fetchone())
                    cur.close()
                    vendor_orders[vendor_id] = {
                        "vendorName": vendor_info['name'], "items": [], "subtotal": 0, "bundleSavings": 0,
                        "shippingCost": float(vendor_info['shipping_cost']),
                        "originalShippingCost": float(vendor_info['shipping_cost']),
                        "freeShippingThreshold": float(vendor_info['free_shipping_threshold'])
                    }
                
                cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
                cur.execute('SELECT price, bundles FROM vendor_products WHERE vendor_id = %s AND product_id = %s;', (vendor_id, item['id']))
                pricing_info = dict(cur.fetchone())
                cur.close()

                vendor_orders[vendor_id]['items'].append({
                    "id": item['id'], "name": item['name'], "unit": item['unit'],
                    "quantity": item['order_amount'], "cost": float(best_option['cost']),
                    "price": float(pricing_info['price']), "bundles": pricing_info['bundles']
                })
                vendor_orders[vendor_id]['bundleSavings'] += float(best_option['savings'])
        
        total_shipping_savings = 0
        for vendor_id, order in vendor_orders.items():
            order['subtotal'] = sum(item['cost'] for item in order['items'])
            if order['subtotal'] >= order['freeShippingThreshold']:
                order['shippingCost'] = 0
                total_shipping_savings += order['originalShippingCost']
            
            total_cost += order['subtotal'] + order['shippingCost']
            total_bundle_savings += order['bundleSavings']

        invoice = {
            "vendorOrders": vendor_orders, "totalCost": total_cost,
            "totalBundleSavings": total_bundle_savings,
            "totalShippingSavings": total_shipping_savings,
            "totalSavings": total_bundle_savings + total_shipping_savings
        }
        conn.close()
        return jsonify({"invoice": invoice})
    except Exception as e:
        print(f"Error generating invoice: {e}")
        return jsonify({"error": "Failed to generate invoice"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
