import os
import json
import boto3
import uuid
import logging
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Attr
from openai import OpenAI  
from difflib import SequenceMatcher

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def get_secret():
    secret_name = "discord_bot_secrets"
    region_name = os.getenv('REGION')
    
    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager', region_name=region_name)
    
    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        return json.loads(get_secret_value_response['SecretString'])
    except ClientError as e:
        logger.error(f"Error retrieving secret: {str(e)}")
        raise e

def similar(a, b, threshold=0.6):
    a = a.lower()
    b = b.lower()
    return SequenceMatcher(None, a, b).ratio() > threshold

def check_similarity_with_existing(table, new_quote):
    response = table.scan()
    existing_quotes = [item['Quote'] for item in response['Items']]
    
    for existing_quote in existing_quotes:
        if similar(new_quote, existing_quote):
            logger.info(f"Similar quote found:\nNew: {new_quote}\nExisting: {existing_quote}")
            return True
    return False

def lambda_handler(event, context):
    try:
        secret = get_secret()
        openai_api_key = secret.get('OPENAI_API_KEY')
        
        client = OpenAI(api_key=openai_api_key)
        dynamodb = boto3.resource('dynamodb', region_name=os.getenv('REGION'))
        table = dynamodb.Table(os.getenv('DYNAMODB_TABLE'))
        
        max_attempts = 3
        quotes_needed = 2
        stored_quotes = []

        for _ in range(quotes_needed):
            for attempt in range(max_attempts):
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a witty Chuck Norris quote generator. Create original, unique quotes that haven't been used before. Focus on unexpected and creative scenarios. Avoid variations of existing concepts."},
                        {"role": "user", "content": "Generate a completely unique Chuck Norris quote that uses a totally new concept. Avoid any variations of common themes like push-ups, counting, time, or physical feats. Instead, create something entirely original with a modern or unexpected twist."}
                    ],
                    temperature=0.9,
                    max_tokens=60,
                    n=1
                )
                
                quote = response.choices[0].message.content.strip()
                logger.info(f"Generated quote {len(stored_quotes) + 1} (attempt {attempt + 1}): {quote}")
                
                if not check_similarity_with_existing(table, quote):
                    quote_id = str(uuid.uuid4())
                    table.put_item(
                        Item={
                            'QuoteID': quote_id,
                            'Quote': quote,
                            'Sent': 0
                        }
                    )
                    logger.info(f"Stored unique quote with ID: {quote_id}")
                    stored_quotes.append({
                        'quote': quote,
                        'quoteId': quote_id
                    })
                    break
                else:
                    logger.info(f"Similar or duplicate quote found, trying again...")
            
            if attempt == max_attempts - 1:
                logger.warning(f"Failed to generate unique quote {len(stored_quotes) + 1} after {max_attempts} attempts")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Generated {len(stored_quotes)} unique quotes out of {quotes_needed} requested',
                'quotes': stored_quotes
            })
        }
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
