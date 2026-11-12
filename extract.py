import os
import json
from datetime import datetime
import time
import logging
import gzip
import requests
import dotenv

dotenv.load_dotenv()

#Making the timestamp to use later for file name, changing it to a string
timestamp = datetime.now().strftime('%Y-%m-%d %H-%M-%S')

data_dir = 'raw_data'
os.makedirs(data_dir,exist_ok=True)
filename = f'{data_dir}/{timestamp}.zip'

api_key=os.getenv('AMP_API_KEY')
secret_key=os.getenv('AMP_SECRET_KEY')

url='https://analytics.eu.amplitude.com/api/2/export'
params = {
    'start': '20261012T13',
    'end': '20261012T14'
}

response = requests.get(url, params=params, auth=(api_key, secret_key))

if response.status_code == 200:
    data = response.content
    with open(filename, 'wb') as file:
        file.write(data)
    print(f'File {filename} saved successfully :)')

    #with open(filename,'w') as file:
              #  json.dump(data, file)
  ##  print(f'File {filename} saved successfully :)')