# prediction.py (Final Fix)
# Logic to determine order quantities.

def calculate_orders(current_stock_levels, db_connection):
    """
    Calculates the amount of each item to order based on stock levels and predictions.
    
    Args:
        current_stock_levels (list): A list of dicts from the frontend, e.g., 
                                     [{'id': 'item1', 'remaining_stock': 50}, ...]
        db_connection: An active database connection.

    Returns:
        list: A list of dicts for items that need to be ordered.
    """
    items_to_order = []
    cur = db_connection.cursor()

    for item_data in current_stock_levels:
        # Fetch the full product details from the database
        cur.execute(
            'SELECT name, unit, min_stock, max_stock, last_year_prediction FROM products WHERE id = %s;',
            (item_data['id'],)
        )
        product_info = cur.fetchone()
        if not product_info:
            continue

        name, unit, min_stock, max_stock, prediction = product_info
        
        # The fix is here: Use the 'remaining_stock' key (snake_case)
        # to match the data structure used throughout the application.
        remaining_stock = int(item_data['remaining_stock'])

        # Calculate the initial order amount
        order_amount = prediction - remaining_stock
        
        # Adjust the order amount to stay within min/max stock levels
        potential_total = remaining_stock + order_amount
        if potential_total < min_stock:
            order_amount = min_stock - remaining_stock
        elif potential_total > max_stock:
            order_amount = max_stock - remaining_stock
            
        # Ensure we don't place negative orders
        order_amount = max(0, order_amount)

        if order_amount > 0:
            items_to_order.append({
                "id": item_data['id'],
                "name": name,
                "unit": unit,
                "order_amount": order_amount
            })
            
    cur.close()
    return items_to_order
