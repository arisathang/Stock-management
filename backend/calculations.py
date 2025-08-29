# calculations.py
# This file combines the logic for predicting order amounts and optimizing purchase costs.

import json
import psycopg2.extras

def calculate_orders(current_stock_levels, db_connection):
    """
    Calculates the amount of each item to order based on stock levels and predictions.
    This is the fast, non-AI logic.
    """
    items_to_order = []
    for item_data in current_stock_levels:
        prediction = int(item_data['last_year_prediction'])
        remaining_stock = int(item_data['remaining_stock'])
        min_stock = int(item_data['min_stock'])
        max_stock = int(item_data['max_stock'])
        order_amount = prediction - remaining_stock
        potential_total = remaining_stock + order_amount
        if potential_total < min_stock:
            order_amount = min_stock - remaining_stock
        elif potential_total > max_stock:
            order_amount = max_stock - remaining_stock
        order_amount = max(0, int(order_amount))
        if order_amount > 0:
            items_to_order.append({
                "id": item_data['id'], "name": item_data['name'], "unit": item_data['unit'],
                "order_amount": order_amount, "prediction": prediction, "remaining_stock": remaining_stock
            })
    return items_to_order

def _calculate_item_cost(quantity, price, bundles_json):
    """
    Calculates the cost for a given quantity of an item from a specific vendor,
    considering their bundle deals.
    """
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

def optimize_purchases(items_to_order, db_connection, vendor_filter=[]):
    """
    Finds the cheapest vendor for a batch of items in a single database query.
    """
    if not items_to_order:
        return {}

    item_ids = [item['id'] for item in items_to_order]
    
    cur = db_connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    # Fetch all possible vendor prices for all required items in one query
    query = """
        SELECT product_id, vendor_id, price, bundles 
        FROM vendor_products 
        WHERE product_id = ANY(%s)
    """
    params = [item_ids]
    if vendor_filter:
        query += " AND vendor_id = ANY(%s)"
        params.append(vendor_filter)
        
    cur.execute(query, tuple(params))
    
    # Organize pricing data for easy lookup
    pricing_data = {}
    for row in cur.fetchall():
        pid = row['product_id']
        if pid not in pricing_data:
            pricing_data[pid] = []
        pricing_data[pid].append(dict(row))
    
    # Process the data in memory to find the best option for each item
    best_options = {}
    for item in items_to_order:
        item_id = item['id']
        best_option = {"vendor_id": None, "cost": float('inf'), "savings": 0, "price": 0, "bundles": None}
        
        if item_id in pricing_data:
            for price_info in pricing_data[item_id]:
                cost_details = _calculate_item_cost(item['order_amount'], float(price_info['price']), price_info['bundles'])
                if cost_details['cost'] < best_option['cost']:
                    best_option['vendor_id'] = price_info['vendor_id']
                    best_option['cost'] = cost_details['cost']
                    best_option['savings'] = cost_details['savings']
                    best_option['price'] = float(price_info['price'])
                    best_option['bundles'] = price_info['bundles']
        
        if best_option['vendor_id']:
            best_options[item_id] = best_option
            
    cur.close()
    return best_options
