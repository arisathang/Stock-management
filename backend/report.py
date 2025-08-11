# report.py (Fixed)
# Logic for generating reports and alerts.

def generate_stock_alerts(products, db_connection=None):
    """
    Checks current stock against min/max levels and generates alerts from a given product list.
    This function no longer needs a database connection as all data is passed in.
    """
    alerts = []
    for product in products:
        # The fix is here: Use the 'remaining_stock' key (snake_case)
        # which matches the database column name.
        if product['remaining_stock'] < product['min_stock']:
            alerts.append({
                "type": "low",
                "message": f"{product['name']} is below minimum stock ({product['remaining_stock']}/{product['min_stock']})."
            })
        elif product['remaining_stock'] > product['max_stock']:
            alerts.append({
                "type": "high",
                "message": f"{product['name']} is over maximum stock ({product['remaining_stock']}/{product['max_stock']})."
            })
    return alerts
