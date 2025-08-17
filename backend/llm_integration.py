import os
import json
import google.generativeai as genai
import psycopg2.extras
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv()

# Configure the Gemini API client
gemini_api_key = os.getenv("GEMINI_API_KEY")
if not gemini_api_key:
    raise ValueError("GEMINI_API_KEY environment variable not set.")
genai.configure(api_key=gemini_api_key)
model = genai.GenerativeModel('gemini-2.5-pro')

def get_historical_data(product_id, db_connection):
    """Fetches the last 90 days of stock movements for a product."""
    cur = db_connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    ninety_days_ago = date.today() - timedelta(days=90)
    
    query = """
        SELECT movement_date::date, SUM(quantity) as daily_total
        FROM stock_movements
        WHERE product_id = %s AND movement_type != 'IN' AND movement_date::date >= %s
        GROUP BY movement_date::date
        ORDER BY movement_date::date DESC;
    """
    cur.execute(query, (product_id, ninety_days_ago))
    history = [f"  - {row['movement_date']}: Used {abs(row['daily_total'])} units" for row in cur.fetchall()]
    cur.close()
    return "\n".join(history)

def calculate_orders_with_ai(current_stock_levels, db_connection):
    """
    Uses the Gemini model to calculate the amount of each item to order
    based on historical consumption.
    """
    items_to_order = []
    
    for item_data in current_stock_levels:
        # We only generate orders for items below their minimum stock level
        if item_data['remaining_stock'] >= item_data['min_stock']:
            continue
            
        history = get_historical_data(item_data['id'], db_connection)
        
        prompt = f"""
        You are an expert inventory manager for a restaurant.
        Analyze the following data for a product and determine how much of it we need to order.

        Product Details:
        - Name: {item_data['name']} ({item_data['unit']})
        - Current Stock: {item_data['remaining_stock']}
        - Minimum Stock Threshold: {item_data['min_stock']}
        - Maximum Stock Threshold: {item_data['max_stock']}

        Recent Consumption History (last 90 days):
        {history if history else "  - No recent consumption data."}

        Task:
        Based on the data, calculate the ideal quantity to order. The goal is to replenish the stock to a healthy level without exceeding the maximum threshold.
        
        Consider the consumption trend. If usage is high, ordering up to the maximum is wise. If usage is low, a smaller order to just get above the minimum is better.
        
        Return ONLY a single integer number representing the recommended order amount. Do not add any other text or explanation.
        """
        
        try:
            response = model.generate_content(prompt)
            # Basic validation to ensure the response is a number
            order_amount = int(response.text.strip())
        except (ValueError, Exception) as e:
            print(f"Error processing AI response for {item_data['name']}: {e}. Defaulting to zero.")
            order_amount = 0 # Default to 0 if AI fails

        if order_amount > 0:
            items_to_order.append({
                "id": item_data['id'],
                "name": item_data['name'],
                "unit": item_data['unit'],
                "order_amount": order_amount,
                "prediction": order_amount, # Use AI result as the prediction
                "remaining_stock": item_data['remaining_stock']
            })
            
    return items_to_order

def get_all_vendor_pricing(item_ids, db_connection, vendor_filter=[]):
    """Fetches all pricing, bundle, and shipping info for the required items."""
    cur = db_connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    query = """
        SELECT 
            vp.product_id, vp.vendor_id, v.name as vendor_name, 
            vp.price, vp.bundles, v.shipping_cost, v.free_shipping_threshold
        FROM vendor_products vp
        JOIN vendors v ON vp.vendor_id = v.id
        WHERE vp.product_id = ANY(%s)
    """
    params = [item_ids]
    
    if vendor_filter:
        query += " AND vp.vendor_id = ANY(%s)"
        params.append(vendor_filter)
        
    cur.execute(query, tuple(params))
    
    # Structure the data for the AI prompt
    pricing_data = {}
    for row in cur.fetchall():
        pid = row['product_id']
        if pid not in pricing_data:
            pricing_data[pid] = []
        pricing_data[pid].append(dict(row))
        
    cur.close()
    return pricing_data


def generate_optimized_invoice_with_ai(items_to_order, db_connection, vendor_filter=[]):
    """
    Uses the Gemini model to find the most cost-effective purchasing plan for a list of items.
    """
    if not items_to_order:
        return {} # Return empty if there's nothing to order

    item_ids = [item['id'] for item in items_to_order]
    pricing_data = get_all_vendor_pricing(item_ids, db_connection, vendor_filter)

    # Create a detailed context for the AI
    items_prompt = "\n".join([f"- {item['name']}: {item['order_amount']} {item['unit']}" for item in items_to_order])
    pricing_prompt = json.dumps(pricing_data, indent=2)

    prompt = f"""
    You are an expert procurement officer for a restaurant. Your task is to create the most cost-effective purchase plan.

    Here are the items we need to order:
    {items_prompt}

    Here is the pricing information from our available vendors. 'bundles' shows discount price for a certain quantity.
    {pricing_prompt}

    Task:
    Determine the best vendor to purchase each item from to minimize the TOTAL cost. Your calculation must include shipping costs.
    Remember that shipping is free if the subtotal for a single vendor meets their 'free_shipping_threshold'.
    Sometimes, it's cheaper to buy from a slightly more expensive vendor if it helps you reach the free shipping threshold and avoid a shipping fee.

    Return your answer as a JSON object with the vendor ID as the key. Each value should be an object containing a list of `items` to order from that vendor.
    
    Example Response Format:
    {{
        "vendor1": {{
            "items": [
                {{"product_id": "item1", "quantity": 50}},
                {{"product_id": "item7", "quantity": 60}}
            ]
        }},
        "vendor3": {{
            "items": [
                {{"product_id": "item3", "quantity": 25}}
            ]
        }}
    }}
    
    Provide ONLY the JSON response. Do not include any other text, explanations, or formatting like ```json.
    """

    try:
        response = model.generate_content(prompt)
        # Clean up the response to ensure it's valid JSON
        cleaned_response = response.text.strip().replace("```json\n", "").replace("\n```", "")
        optimized_plan = json.loads(cleaned_response)
        return optimized_plan
    except (json.JSONDecodeError, Exception) as e:
        print(f"Error processing AI optimization response: {e}")
        return {} # Return empty plan on failure
    
