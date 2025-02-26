import os
import json
import boto3
import random
import requests

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.getenv('DYNAMODB_TABLE'))

def lambda_handler(event, context):
    response = table.scan()
    items = response.get('Items', [])
    if not items:
        quote = "No quotes available."
    else:
        quote_item = random.choice(items)
        quote = quote_item['Quote']

    discord_webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
    if not discord_webhook_url:
        return {
            'statusCode': 500,
            'body': json.dumps({"message": "Discord webhook URL not set."})
        }

    payload = {
        "content": quote
    }

    headers = {
        "Content-Type": "application/json"
    }

    response = requests.post(discord_webhook_url, data=json.dumps(payload), headers=headers)

    if response.status_code == 204:
        return {
            'statusCode': 200,
            'body': json.dumps({"message": "Quote sent successfully."})
        }
    else:
        return {
            'statusCode': response.status_code,
            'body': json.dumps({"message": "Failed to send quote."})
        }
