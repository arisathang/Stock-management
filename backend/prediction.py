import psycopg2.extras

def calculate_orders(current_stock_levels, db_connection):
    """
    Calculates the amount of each item to order and includes the data
    used for the calculation in the output.
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
                "id": item_data['id'],
                "name": item_data['name'],
                "unit": item_data['unit'],
                "order_amount": order_amount,
                "prediction": prediction,
                "remaining_stock": remaining_stock
            })
            
    return items_to_order
