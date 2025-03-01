import json
import os
import boto3
import random
from datetime import datetime
import requests

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.getenv('DYNAMODB_TABLE'))

def get_random_unsent_quote():
    response = table.scan(
        FilterExpression="attribute_not_exists(Sent) OR Sent = :val",
        ExpressionAttributeValues={":val": 0}
    )
    
    items = response.get('Items', [])
    if not items:
        reset_response = table.scan()
        all_items = reset_response.get('Items', [])
        
        if not all_items:
            return "No quotes available."
            
        for item in all_items:
            table.update_item(
                Key={'QuoteID': item['QuoteID']},
                UpdateExpression="SET Sent = :val",
                ExpressionAttributeValues={":val": 0}
            )
        
        items = all_items

    quote_item = random.choice(items)
    
    table.update_item(
        Key={'QuoteID': quote_item['QuoteID']},
        UpdateExpression="SET Sent = :val",
        ExpressionAttributeValues={":val": 1}
    )
    
    return quote_item['Quote']

def lambda_handler(event, context):
    quote = get_random_unsent_quote()
    discord_webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
    
    if not discord_webhook_url:
        return {
            'statusCode': 500,
            'body': json.dumps({"message": "Discord webhook URL not set."})
        }

    response = requests.post(
        discord_webhook_url,
        json={"content": quote},
        headers={"Content-Type": "application/json"}
    )

    return {
        'statusCode': 200 if response.status_code == 204 else response.status_code,
        'body': json.dumps({
            "message": "Quote sent successfully." if response.status_code == 204 else "Failed to send quote."
        })
    }
