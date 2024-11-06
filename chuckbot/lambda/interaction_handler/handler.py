import json
import os
import boto3
import random

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.getenv('DYNAMODB_TABLE'))

def lambda_handler(event, context):
    # Parse the incoming Discord interaction
    body = json.loads(event['body'])
    token = body['token']
    application_id = body['application_id']
    guild_id = body.get('guild_id')
    channel_id = body.get('channel_id')
    data = body['data']
    command_name = data['name']

    if command_name == "quote":
        # Fetch a random quote from DynamoDB
        response = table.scan()
        items = response.get('Items', [])
        if not items:
            quote = "No quotes available."
        else:
            quote_item = random.choice(items)
            quote = quote_item['Quote']

        # Respond to Discord
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                "type": 4,  # Channel message with source
                "data": {
                    "content": quote
                }
            })
        }

    # Handle other commands if any
    return {
        'statusCode': 200,
        'body': json.dumps({"type": 4, "data": {"content": "Unknown command."}})
    }
