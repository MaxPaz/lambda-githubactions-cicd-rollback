import json
import boto3
import random
import os

def get_secret(secret_name, region='us-west-1'):
    client = boto3.client('secretsmanager', region_name=region)
    try:
        response = client.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])
    except:
        return None

#sure?
def lambda_handler(event, context):
    secret_name = os.environ.get('SECRET_ENV', '<YOUR_SECRET_NAME>')
    region = os.environ.get('AWS_REGION', 'us-west-1')
    secrets = get_secret(secret_name, region)
    table_name = secrets['DYNAMODB_TABLE_NAME'] if secrets else '<YOUR_TABLE_NAME>'
    
    dynamodb = boto3.resource('dynamodb', region_name=region)
    table = dynamodb.Table(table_name)
    
    random_id = random.randint(1, 3)
    
    try:
        response = table.get_item(Key={'Id': random_id})
        value = response['Item']['value']
        
        return {
            'statusCode': 200,
            'body': json.dumps(f'Random ID {random_id}: {value} (your_environment_name)')
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error: {str(e)}')
        }
