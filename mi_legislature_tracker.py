import requests
import csv
import os
import base64
import zipfile
import io
import json

# --- CONFIGURATION ---
API_KEY = os.environ.get('LEGISCAN_API_KEY')  
STATE = 'MI'                   
BASE_URL = 'https://api.legiscan.com/'

def get_current_session():
    print("Finding current Michigan legislative session...")
    params = {'key': API_KEY, 'op': 'getSessionList', 'state': STATE}
    r = requests.get(BASE_URL, params=params).json()
    if r.get('status') == 'OK':
        latest = max(r['sessions'], key=lambda x: x['session_id'])
        return latest['session_id']
    return None

def get_dataset_access_key(session_id):
    print("Locating free Bulk Dataset access key...")
    params = {'key': API_KEY, 'op': 'getDatasetList', 'state': STATE}
    r = requests.get(BASE_URL, params=params).json()
    if r.get('status') == 'OK':
        for ds in r.get('datasetlist', []):
            if ds['session_id'] == session_id:
                return ds['access_key']
    return None

def get_representatives(session_id):
    print("Fetching official House roster...")
    params = {'key': API_KEY, 'op': 'getSessionPeople', 'id': session_id}
    r = requests.get(BASE_URL, params=params).json()
    
    reps = {}
    if r.get('status') == 'OK':
        for person in r['sessionpeople']['people']:
            if person.get('role') == 'Rep':
                reps[person['people_id']] = {
                    'Name': person['name'],
                    'Party': person.get('party', 'Unknown'),
                    'Contested Votes Cast': 0,
                    'Votes Against Party': 0
                }
    return reps

def process_bulk_dataset(session_id, access_key, reps):
    print("Downloading Bulk Dataset archive (this may take 10-20 seconds)...")
    params = {'key': API_KEY, 'op': 'getDataset', 'id': session_id, 'access_key': access_key}
    r = requests.get(BASE_URL, params=params).json()
    
    if r.get('status') != 'OK':
        print("Failed to download dataset.")
        return list(reps.values())
        
    print("Unzipping archive and analyzing thousands of votes...")
    zip_bytes = base64.b64decode(r['dataset']['zip'])
    
    analyzed_roll_calls = 0
    
    # Unzip the file directly in the cloud's memory
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        for filename in z.namelist():
            # Find the roll call files hidden inside the ZIP folders
            if 'roll_call' in filename.lower() and filename.endswith('.json'):
                with z.open(filename) as f:
                    try:
                        data = json.load(f)
                        rc = data.get('roll_call', {})
                        votes = rc.get('votes', [])
                        
                        # 1. Check if the vote is contested (At least 10% opposition)
                        yeas = rc.get('yea', 0)
                        nays = rc.get('nay', 0)
                        total = yeas + nays
                        
                        if total ==
