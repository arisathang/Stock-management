# optimization.py (with Filter & Savings)
# Logic to find the most cost-effective purchasing options, calculate savings,
# and filter by selected vendors.

import json

def _calculate_item_cost(quantity, product_pricing):
    """
    Calculates the cost for a given quantity of an item from a specific vendor,
    considering their bundle deals. It also calculates the non-discounted cost.
    
    Returns:
        dict: A dictionary containing {'cost', 'nonDiscountedCost', 'savings'}.
    """
    price, bundles_json = product_pricing
    cost = 0
    remaining_qty = quantity
    non_discounted_cost = quantity * float(price)
    savings = 0

    if bundles_json:
        # Sort bundles by quantity (desc) to use largest bundles first
        bundles = sorted(bundles_json, key=lambda b: b['quantity'], reverse=True)
        
        for bundle in bundles:
            num_bundles = remaining_qty // bundle['quantity']
            if num_bundles > 0:
                cost += num_bundles * bundle['price']
                remaining_qty -= num_bundles * bundle['quantity']
    
    # Cost for the remaining items not in a bundle
    cost += remaining_qty * float(price)
    savings = non_discounted_cost - cost
    
    return {"cost": cost, "nonDiscountedCost": non_discounted_cost, "savings": savings}


def find_best_vendor_for_item(item, db_connection, vendor_filter=[]):
    """
    Finds the cheapest vendor for a single item, optionally filtered by a list of vendor IDs.
    """
    best_option = {"vendor_id": None, "cost": float('inf'), "savings": 0}
    cur = db_connection.cursor()

    query = 'SELECT vendor_id, price, bundles FROM vendor_products WHERE product_id = %s'
    params = [item['id']]

    # If a filter is provided, add it to the query
    if vendor_filter:
        query += ' AND vendor_id = ANY(%s)'
        params.append(vendor_filter)

    cur.execute(query, tuple(params))
    all_vendor_prices = cur.fetchall()

    for vendor_price_info in all_vendor_prices:
        vendor_id, price, bundles = vendor_price_info
        
        cost_details = _calculate_item_cost(
            item['order_amount'], 
            (float(price), bundles)
        )
        
        if cost_details['cost'] < best_option['cost']:
            best_option['vendor_id'] = vendor_id
            best_option['cost'] = cost_details['cost']
            best_option['savings'] = cost_details['savings']
            
    cur.close()
    return best_option
