from dotenv import load_dotenv
import json
from utils import *

load_dotenv()


conn = get_db_conn()


def main():
    
    
    # response = fetch_data()
    # process_data(conn,response)
    
    print("Main function executed.")

def testing():
    file_path = r'C:\Users\Alessio\Projects\idealista-analyzer\data\raw\idealista_data.json'
    with open(file_path,'r',encoding='utf-8') as f:
        data = json.load(f)
    process_data(conn,data)
    

testing()
    