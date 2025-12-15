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


IDEALISTA_KEYS = get_secret('idealista-keys')

API_KEY = IDEALISTA_KEYS['idealista-api-key']
SECRET_KEY = IDEALISTA_KEYS['idealista-secret-key']

def get_db_conn():
    """Initialize (or reuse) a PostgreSQL connection pool."""

    secret_name ='rds!db-efc52989-89c8-4009-a2c3-e211a33ba1bd'
    credentials = get_secret(secret_name)
    
    print(credentials)
    db_conn = pg8000.connect(
        host='cardy-dev.cb60yy2s4a4i.eu-central-1.rds.amazonaws.com',
        port=5432,
        database='idealista',
        user='postgres',
        password='?gfP_lIHfO63x_RAOo00i]_vIEoK',
        timeout=5
    )
  
    print("DB connection established.")
    return db_conn


conn = get_db_conn()