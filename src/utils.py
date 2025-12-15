import json
from openai import OpenAI
import os
from dotenv import load_dotenv
import pg8000

# from dbutils import PooledDB
import boto3
import requests
from datetime import datetime
import traceback
load_dotenv()

db_pool = None

def get_secret(secret_name,key=None):
    region = os.getenv("AWS_REGION", "eu-central-1")
    client = boto3.client("secretsmanager", region_name=region)
    response = client.get_secret_value(SecretId=secret_name)
    secret_dict = json.loads(response["SecretString"])
    if key:
        return secret_dict.get(key)
    return secret_dict


OPENAI_API_KEY = get_secret('openai-api-key','openai-api-key')

client = OpenAI(api_key=OPENAI_API_KEY)


IDEALISTA_KEYS = get_secret('idealista-keys')

API_KEY = IDEALISTA_KEYS['idealista-api-key']
SECRET_KEY = IDEALISTA_KEYS['idealista-secret-key']

def get_db_conn():
    """Initialize (or reuse) a PostgreSQL connection pool."""
    global db_pool
    if db_pool:
        return db_pool
    secret_name ='rds!db-efc52989-89c8-4009-a2c3-e211a33ba1bd'
    credentials = get_secret(secret_name)
    db_conn = pg8000.connect(
        host=IDEALISTA_KEYS['db_endpoint'],
        port=int(IDEALISTA_KEYS['db_port']),
        database=IDEALISTA_KEYS['db_name'],
        user=credentials["username"],
        password=credentials["password"],
        timeout=5,
    )
  
    print("DB connection established.")
    return db_conn

def get_auth_token():
    
    url = "https://api.idealista.com/oauth/token"

    payload = {
        'grant_type': 'client_credentials',
        'scope': 'read'
    }
    response = requests.post(url, data=payload, auth=(API_KEY, SECRET_KEY))
    response.raise_for_status()
    return response.json().get("access_token")


def fetch_data():
    token = get_auth_token()
    headers = {
        'Authorization': f'Bearer {token}'
    }
    url = "https://api.idealista.com/3.5/es/search"
    response = requests.post(
        url, 
        headers=headers, 
        files={
        "center": (None, "41.394915,2.159288"),
        "operation": (None, "rent"),
        "distance": (None, "10000"),
        "propertyType": (None, "homes"),
        "locale": (None, "en"),
        "locationId": (None, "0-EU-ES-08"),
        "maxItems": (None, "50"),
        "numPage": (None, "1"),
        "sinceDate": (None, "T"),
        "order": (None, "publicationDate"),
        "sort": (None, "desc"),
        "hasMultimedia": (None, "True"),
    })

    print(response.status_code)
    print(response.json())
    return response.json()


def process_data(conn,data):
    # Placeholder for data processing logic
    items = data.get("elementList", [])
    print(f"Found {len(items)} items")
    # items = items[:2]
    print(f"Processing {len(items)} items")
    
    valid = 0
    errors = 0
    with conn.cursor() as cursor:
        for item in items:
            try:
                
                print(f"Property ID: {item.get('propertyCode')}, Price: {item.get('price')} {item.get('currency')}")
                property_code= item.get('propertyCode',None)
                description=item.get('description',None)
                price = item.get('price',None)
                url = item.get('url',None)
                size= item.get('size',None)
                rooms= item.get('rooms',None)
                thumbnail= item.get('thumbnail',None)
                priceByArea= item.get('priceByArea',None)
                district= item.get('district',None)
                distance= item.get('distance',None)
                
                if listing_exists(cursor, property_code):
                    print(f"Listing with ID {property_code} already exists. Skipping insertion.")
                    continue
                home_data = {
                    "idealista_id": property_code,
                    "description": description,
                    "price": price,
                    "url": url,
                    "size": size,
                    "rooms": rooms,
                    "thumbnail": thumbnail,
                    "price_by_area": priceByArea,
                    "district": district,
                    "distance": distance
                }
                
                add_home(cursor, home_data)
                analysis,cost = analyze_description(home_data)
                print(f"Analysis Cost: {cost:.6f} USD")
                home_data.update(analysis)
                
                if home_data.get("is_relevant", False) or True:
                    print("Sending notification...")
                    send_notification(home_data)
                    valid += 1
                available_from = analysis.get('available_from', None)
                update_availability(cursor,property_code,available_from)
                conn.commit()
            except Exception as e:
                traceback.print_exc()
                errors += 1
                print(f"Error processing item {item.get('propertyCode')}: {e}")
                
        
    
    print(f"Processed {len(items)} items, {valid} were relevant. [Errors: {errors}]")
    
    total = len(items)
    relevant_pct = (valid / total * 100) if total else 0

    message = (
        f"📊 Processing Summary:\n"
        f"  ✅ Total items     : {total}\n"
        f"  🌟 Relevant items  : {valid} ({relevant_pct:.1f}%)\n"
        f"  ❌ Errors          : {errors}"
    )
    send_telegram_message(message)
        

def analyze_description(home):
    description = home.get("description", "")
    prompt= generate_prompt(description)
    analysis, cost = invoke_openai(prompt, model_id="gpt-4o-mini", object=True)
    return analysis, cost

def update_availability(cursor,home_id, available_from):
    update_query = """
    UPDATE property_listing
    SET available_from = %s
    WHERE idealista_id = %s;
    """
    cursor.execute(update_query, (available_from, home_id))
    
    print(f"Updated availability for home ID {home_id} to {available_from}")
    

def send_notification(home_data):
    
    message=create_home_html(home_data)
    send_telegram_message(message)
    
    
def listing_exists(cursor, idealista_id):
    """Check if a listing with the given idealista_id exists in the database."""
    query = "SELECT 1 FROM property_listing WHERE idealista_id = %s;"
    cursor.execute(query, (idealista_id,))
    return cursor.fetchone() is not None


def add_home(cursor, home_data):
    """Insert a home record into the database using pg8000."""
    insert_query = """
    INSERT INTO property_listing (
        idealista_id,
        description,
        price,
        url,
        size,
        rooms,
        thumbnail,
        price_by_area,
        district,
        distance
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
    )
    """

    values = (
        home_data.get("idealista_id"),
        home_data.get("description"),
        home_data.get("price"),
        home_data.get("url"),
        home_data.get("size"),
        home_data.get("rooms"),
        home_data.get("thumbnail"),
        home_data.get("price_by_area"),
        home_data.get("district"),
        home_data.get("distance"),
    )

    cursor.execute(insert_query, values)
    



 
def invoke_openai(prompt,model_id="gpt-4o-mini",object=True):
    response = client.chat.completions.create(
        model=model_id,
        messages=[{"role": "user", "content": prompt}]
    )

    text = response.choices[0].message.content
    cost = parse_openai_response(response,model_id)
    output_json = parse_output(text,object=object)
    return output_json,cost


def parse_openai_response(response,model_id):
    input_tokens = response.usage.prompt_tokens
    output_tokens = response.usage.completion_tokens
    INPUT_PRICE = OPENAI_PRICING[model_id]['input']
    OUTPUT_PRICE = OPENAI_PRICING[model_id]['output']
    cost = (input_tokens * INPUT_PRICE) + (output_tokens * OUTPUT_PRICE)
    return cost

def parse_output(output,object=False):
    try:
        if object:
            start = output.index("{")
            end = output.rfind("}") + 1
        else:
            # Strip everything except the JSON block
            start = output.index("[")
            end = output.rfind("]") + 1
        json_str = output[start:end]
        # Optional: print cleaned JSON string
        print("Extracted JSON:\n", json_str)
        # Parse the JSON
        parsed = json.loads(json_str)
        return parsed

    except (ValueError, json.JSONDecodeError) as e:
        print("Failed to parse JSON:", e)
        return None



def send_telegram_message(message: str):
    # Example usage:
    BOT_TOKEN = IDEALISTA_KEYS['telegram-bot-token']
    CHAT_ID = IDEALISTA_KEYS['telegram-chat']
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }

    response = requests.post(url, data=payload)

    if response.status_code != 200:
        print("Error sending message:", response.text)
    else:
        print("Message sent successfully")

    return response.json()



  

def generate_prompt(home_description):
    prompt = f"""
    Analyze the following real estate property description for rent  and extract the following information:
    
    - available_from: String representing the date when the property is available for rent
    - is_relevant: True if available_from is from 15 February 2026,False otherwise.

    Property Description: \"\"\"{home_description}\"\"\"
    Today's date is {datetime.now().strftime('%Y-%m-%d')}.
    Return the information in the following JSON format:
    {{
        "available_from": 'YYYY-MM-DD',
        "is_relevant": true|false
    }}
    Do not hallucinate information. If the available_from date is not mentioned, assume the property is available immediately and set is_relevant accordingly.
    """
    return prompt

def create_home_html(home_data):
    """
    Generate a Telegram-friendly HTML message for a property listing
    """
    message = f"""
🏠 <b>Property Listing</b>


<b>Price:</b> {home_data.get('price', 'N/A')} €
<b>Available From:</b> {home_data.get('available_from', 'N/A')}
<b>Price / m²:</b> {home_data.get('price_by_area', 'N/A')} €
<b>Size:</b> {home_data.get('size', 'N/A')} m²
<b>Rooms:</b> {home_data.get('rooms', 'N/A')}
<b>District:</b> {home_data.get('district', 'N/A')}
<b>Distance:</b> {home_data.get('distance', 'N/A')} meters

<b>Relevant:</b> {home_data.get('is_relevant', False)}

<b>URL:</b> <a href="{home_data.get('url', '#')}">View Listing</a>
"""
    return message.strip()



OPENAI_PRICING = {
    # ───────────────
    # GPT-4.1 family
    # ───────────────
    'gpt-4.1-mini': {
        'input': 0.40 / 1_000_000,    # $0.40 / 1M
        'output': 1.60 / 1_000_000    # $1.60 / 1M
    },
    'gpt-4.1': {
        'input': 2.00 / 1_000_000,    # $2.00 / 1M
        'output': 8.00 / 1_000_000    # $8.00 / 1M
    },

    # ───────────────
    # GPT-4o family
    # ───────────────
    'gpt-4o-mini': {
        'input': 0.15 / 1_000_000,    # $0.15 / 1M
        'output': 0.60 / 1_000_000    # $0.60 / 1M
    },
    'gpt-4o': {
        'input': 5.00 / 1_000_000,    # $5.00 / 1M
        'output': 15.00 / 1_000_000   # $15.00 / 1M
    },

    # ───────────────
    # GPT-5 family
    # ───────────────
    'gpt-5-nano': {
        'input': 0.05 / 1_000_000,   # $0.05 / 1M
        'output': 0.40 / 1_000_000   # $0.40 / 1M
    },
    'gpt-5-mini': {
        'input': 0.25 / 1_000_000,    # $0.25 / 1M
        'output': 2.00 / 1_000_000    # $2.00 / 1M
    },
    'gpt-5': {
        'input': 1.25 / 1_000_000,    # $1.25 / 1M
        'output': 10.00 / 1_000_000   # $10.00 / 1M
    }
}
