import os
import json
import boto3
import uuid
import openai
from botocore.exceptions import ClientError

def get_secret():
    secret_name = "discord_bot_secrets"
    region_name = os.getenv('AWS_REGION')

    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        # Handle exceptions
        raise e

    # Decrypts secret using the associated KMS key.
    secret = get_secret_value_response['SecretString']
    return json.loads(secret)

def lambda_handler(event, context):
    secret = get_secret()
    openai_api_key = secret['OPENAI_API_KEY']

    # Initialize OpenAI API
    openai.api_key = openai_api_key

    # Define the prompt
    prompt = (
        "Generate a Chuck Norris-style quote. The quote should be witty, humorous, "
        "and reflect the legendary toughness and unique abilities of Chuck Norris. "
        "Example: 'Chuck Norris can divide by zero.'"
    )

    try:
        # Call OpenAI API to generate a quote
        response = openai.Completion.create(
            engine="text-davinci-003",
            prompt=prompt,
            temperature=0.7,
            max_tokens=60,
            n=1,
            stop=None,
        )

        quote = response.choices[0].text.strip()

        # Initialize DynamoDB resource
        dynamodb = boto3.resource('dynamodb', region_name=os.getenv('AWS_REGION'))
        table = dynamodb.Table(os.getenv('DYNAMODB_TABLE'))

        # Check for duplicate quotes
        scan_response = table.scan(
            FilterExpression=boto3.dynamodb.conditions.Attr('Quote').eq(quote)
        )
        items = scan_response.get('Items', [])

        if items:
            print("Duplicate quote found. Skipping insertion.")
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'Duplicate quote. No action taken.'})
            }

        # Generate a unique QuoteID
        quote_id = str(uuid.uuid4())

        # Store the quote in DynamoDB
        table.put_item(
            Item={
                'QuoteID': quote_id,
                'Quote': quote
            }
        )

        print(f"Successfully added quote: {quote}")

        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Quote generated and stored successfully.', 'quote': quote})
        }

    except Exception as e:
        print(f"Error generating or storing quote: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': 'Failed to generate or store quote.', 'error': str(e)})
        }
