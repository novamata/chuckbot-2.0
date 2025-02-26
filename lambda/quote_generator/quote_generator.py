import os
import json
import boto3
import uuid
import openai
import logging
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Attr

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def get_secret():
    secret_name = "discord_bot_secrets"
    region_name = os.getenv('AWS_REGION')
    
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
    openai.api_key = openai_api_key

    prompt = (
        "Generate a Chuck Norris-style quote. The quote should be witty, humorous, "
        "and reflect the legendary toughness and unique abilities of Chuck Norris. "
        "Example: 'Chuck Norris can divide by zero.'"
    )

    try:
        response = openai.Completion.create(
            model="text-davinci-003", 
            prompt=prompt,
            temperature=0.7,
            max_tokens=60,
            n=1,
            stop=None,
        )
        quote = response.choices[0].text.strip()

        dynamodb = boto3.resource('dynamodb', region_name=os.getenv('AWS_REGION'))
        table = dynamodb.Table(os.getenv('DYNAMODB_TABLE'))
        scan_response = table.scan(FilterExpression=Attr('Quote').eq(quote))
        items = scan_response.get('Items', [])

        if items:
            logger.info("Duplicate quote found. Skipping insertion.")
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'Duplicate quote. No action taken.'})
            }

        quote_id = str(uuid.uuid4())
        table.put_item(
            Item={
                'QuoteID': quote_id,
                'Quote': quote
            }
        )
        logger.info(f"Successfully added quote: {quote}")
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Quote generated and stored successfully.', 'quote': quote})
        }

    except Exception as e:
        logger.error(f"Error generating or storing quote: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': 'Failed to generate or store quote.', 'error': str(e)})
        }
