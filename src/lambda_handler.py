from dotenv import load_dotenv
import json
from utils import *

import traceback
load_dotenv()


conn = get_db_conn()


def main(event,context):
    
    
    # response = fetch_data()

    response = load_data()
    items = response['elementList']
    
    process_data(conn,response)
    
    # print("Main function executed.")

def load_data():
    file_path = r'C:\Users\Alessio\Projects\idealista-analyzer\src\data.json'
    with open(file_path,'r',encoding='utf-8') as f:
        data = json.load(f)
    return data


def testing():
    file_path = r'C:\Users\Alessio\Projects\idealista-analyzer\data\raw\idealista_data.json'
    with open(file_path,'r',encoding='utf-8') as f:
        data = json.load(f)
    process_data(conn,data)
    

main({},{})
    