import os
import json
import boto3
import uuid
import logging
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Attr
from openai import OpenAI  

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def get_secret():
    secret_name = "discord_bot_secrets"
    region_name = os.getenv('REGION')
    
    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager', region_name=region_name)
    
    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    except ClientError as e:
        logger.error(f"Error retrieving secret: {str(e)}")
        raise e

    secret = get_secret_value_response['SecretString']
    return json.loads(secret)

def lambda_handler(event, context):
    secret = get_secret()
    openai_api_key = secret.get('OPENAI_API_KEY')
    if not openai_api_key:
        logger.error("OPENAI_API_KEY not found in secret.")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': 'Server error: OPENAI_API_KEY missing.'})
        }
    
    client = OpenAI(api_key=openai_api_key)

    prompt = (
        "Generate a Chuck Norris-style quote. The quote should be witty, humorous, "
        "and reflect the legendary toughness and unique abilities of Chuck Norris. "
        "Example: 'Chuck Norris can divide by zero.'"
    )
    
    dynamodb = boto3.resource('dynamodb', region_name=os.getenv('REGION'))
    table = dynamodb.Table(os.getenv('DYNAMODB_TABLE'))

    num_quotes_to_generate = 30
    added_count = 0
    attempts = 0
    max_attempts = 50  

    while added_count < num_quotes_to_generate and attempts < max_attempts:
        attempts += 1

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a witty Chuck Norris quote generator."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=60,
                n=1
            )
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {str(e)}")
            break

        quote = response.choices[0].message.content.strip()
        logger.info(f"Generated quote: '{quote}'")
        
        scan_response = table.scan(FilterExpression=Attr('Quote').eq(quote))
        items = scan_response.get('Items', [])
        if items:
            logger.info("Duplicate quote found, skipping insertion.")
            continue
        
        quote_id = str(uuid.uuid4())
        try:
            table.put_item(
                Item={
                    'QuoteID': quote_id,
                    'Quote': quote
                }
            )
            logger.info(f"Added quote: {quote}")
            added_count += 1
        except Exception as e:
            logger.error(f"Error inserting quote into DynamoDB: {str(e)}")

    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': f'Quote generation complete. {added_count} new quotes added after {attempts} attempts.'
        })
    }
