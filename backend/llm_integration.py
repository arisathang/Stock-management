import os
import json
import ollama
import psycopg2.extras
from datetime import date, timedelta
from dotenv import load_dotenv
from decimal import Decimal

load_dotenv()

# --- Ollama Configuration ---
OLLAMA_ENABLED = False
try:
    # Use environment variables for host and model, with sensible defaults
    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    ollama_model = os.getenv("OLLAMA_MODEL", "llama3") # llama3 is a good default

    # Initialize the client
    client = ollama.Client(host=ollama_host)
    
    # Check if the model is available locally
    client.show(ollama_model) 
    print(f"✅ Successfully connected to Ollama at {ollama_host} with model '{ollama_model}'")
    OLLAMA_ENABLED = True
except Exception as e:
    print(f"⚠️ Warning: Could not connect to Ollama or find model '{os.getenv('OLLAMA_MODEL', 'llama3')}'. LLM features will be disabled.")
    print(f"   Error: {e}")
# --- End Ollama Configuration ---


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
    Uses a single call to a local Ollama model to calculate the order amount for all necessary items.
    """
    if not OLLAMA_ENABLED:
        print("LLM prediction skipped: Ollama not configured.")
        # Fallback to simple logic if AI is disabled
        return [{"id": item['id'], "order_amount": item['last_year_prediction'] - item['remaining_stock']} for item in current_stock_levels if item['remaining_stock'] < item['min_stock']]

    # 1. First, gather all items that are below the minimum stock threshold.
    items_needing_review = []
    for item_data in current_stock_levels:
        if item_data['remaining_stock'] < item_data['min_stock']:
            history = get_historical_data(item_data['id'], db_connection)
            items_needing_review.append({
                "product_id": item_data['id'],
                "name": item_data['name'],
                "unit": item_data['unit'],
                "current_stock": item_data['remaining_stock'],
                "min_stock": item_data['min_stock'],
                "max_stock": item_data['max_stock'],
                "consumption_history": history if history else "No recent consumption data."
            })

    if not items_needing_review:
        return []

    # 2. Create a single, comprehensive prompt for all items.
    prompt = f"""
    You are an expert inventory manager for a restaurant.
    Analyze the following list of products and determine how much of each we need to order.

    # Products to Analyze:
    {json.dumps(items_needing_review, indent=2)}

    # Task:
    For each product, calculate the ideal quantity to order.
    - The goal is to replenish the stock to a healthy level without exceeding the maximum threshold.
    - Consider the consumption trend. If usage is high, ordering up to the maximum is wise. If usage is low, a smaller order to just get above the minimum is better.
    - If an item doesn't need to be ordered, set its order amount to 0.

    # Response Format:
    Return your answer as a single, valid JSON object.
    - The object should have a single key: "orders".
    - The value of "orders" must be a list of objects.
    - Each object in the list must contain two keys:
        1. `product_id`: The integer ID of the product.
        2. `order_amount`: The recommended integer quantity to order.

    Example of a PERFECT response format:
    {{
      "orders": [
        {{ "product_id": 101, "order_amount": 50 }},
        {{ "product_id": 105, "order_amount": 0 }},
        {{ "product_id": 112, "order_amount": 25 }}
      ]
    }}

    Provide ONLY the JSON response. Do not include any other text, explanations, or markdown formatting.
    """

    # 3. Make a single call to the LLM.
    try:
        response = client.generate(model=ollama_model, prompt=prompt, options={"format": "json"})
        ai_orders = json.loads(response['response']).get('orders', [])
        
        # 4. Map the AI response back to the original data structure.
        items_to_order = []
        original_items_by_id = {item['id']: item for item in current_stock_levels}

        for order in ai_orders:
            order_amount = int(order.get('order_amount', 0))
            product_id = order.get('product_id')

            if order_amount > 0 and product_id in original_items_by_id:
                item_data = original_items_by_id[product_id]
                items_to_order.append({
                    "id": item_data['id'],
                    "name": item_data['name'],
                    "unit": item_data['unit'],
                    "order_amount": order_amount,
                    "prediction": order_amount, # Using AI result as the "prediction"
                    "remaining_stock": item_data['remaining_stock']
                })
        return items_to_order

    except (json.JSONDecodeError, Exception) as e:
        print(f"Error processing batched AI response: {e}")
        print(f"Raw AI Response was: {response.get('response', 'N/A')}")
        return []

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
    
    pricing_data = {}
    for row in cur.fetchall():
        # Convert the database row to a mutable dictionary
        row_dict = dict(row)
        # --- FIX: Convert all Decimal types to float at the source ---
        for key, value in row_dict.items():
            if isinstance(value, Decimal):
                row_dict[key] = float(value)
        
        pid = row_dict['product_id']
        if pid not in pricing_data:
            pricing_data[pid] = []
        pricing_data[pid].append(row_dict)
        
    cur.close()
    return pricing_data


def generate_optimized_invoice_with_ai(items_to_order, db_connection, vendor_filter=[]):
    """
    Uses a local Ollama model to find the most cost-effective purchasing plan.
    """
    if not items_to_order:
        return {}
    
    if not OLLAMA_ENABLED:
        print("LLM optimization skipped: Ollama not configured.")
        return {} # Return empty plan if AI is disabled

    item_ids = [item['id'] for item in items_to_order]
    pricing_data = get_all_vendor_pricing(item_ids, db_connection, vendor_filter)

    # We need to map product IDs to names for the prompt to be more readable for the AI
    product_id_to_name = {item['id']: f"{item['name']} ({item['unit']})" for item in items_to_order}
    items_prompt_list = [f"- {product_id_to_name[item['id']]}: {item['order_amount']}" for item in items_to_order]
    items_prompt = "\n".join(items_prompt_list)
    
    pricing_prompt = json.dumps(pricing_data, indent=2)

    # --- FIX 2: Make the prompt much more specific to prevent errors ---
    prompt = f"""
    You are an expert procurement officer for a restaurant. Your task is to create the most cost-effective purchase plan.

    # Items to Order:
    Here are the items we need to order, with their internal product ID and required quantity:
    {json.dumps(items_to_order, indent=2)}

    # Vendor Pricing Data:
    This is the pricing information from our available vendors. 'bundles' shows discount prices for specific quantities.
    {pricing_prompt}

    # Task:
    Create an optimal purchasing plan that minimizes the TOTAL cost, including shipping.
    - Your calculation MUST factor in shipping costs.
    - Shipping is FREE from a vendor if the subtotal of items from them meets their 'free_shipping_threshold'.
    - It may be cheaper overall to buy from a slightly more expensive vendor to meet their free shipping threshold.

    # Response Format:
    Return your answer as a single, valid JSON object.
    - The keys of the JSON object MUST be the integer `vendor_id` from the pricing data provided.
    - The value for each vendor key MUST be an object containing one key: "items".
    - "items" MUST be a list of objects, where each object has two keys:
        1. `product_id`: The integer ID of the product.
        2. `quantity`: The integer quantity to order.

    Example of a PERFECT response format:
    {{
        "1": {{
            "items": [
                {{"product_id": 101, "quantity": 50}},
                {{"product_id": 107, "quantity": 60}}
            ]
        }},
        "3": {{
            "items": [
                {{"product_id": 103, "quantity": 25}}
            ]
        }}
    }}
    
    Provide ONLY the JSON response. Do not include any other text, explanations, or markdown formatting like ```json.
    """

    try:
        response = client.generate(model=ollama_model, prompt=prompt, options={"format": "json"})
        # The 'format: json' option for Ollama helps ensure the output is valid JSON.
        optimized_plan = json.loads(response['response'])
        return optimized_plan
    except (json.JSONDecodeError, Exception) as e:
        print(f"Error processing AI optimization response: {e}")
        print(f"Raw AI Response was: {response.get('response', 'N/A')}") # Log the raw response for debugging
        return {}