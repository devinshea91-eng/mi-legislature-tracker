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

def get_previous_session():
    print("Finding the 2023-2024 Michigan legislative session...")
    params = {'key': API_KEY, 'op': 'getSessionList', 'state': STATE}
    r = requests.get(BASE_URL, params=params).json()
    if r.get('status') == 'OK':
        # Filter out empty Special Sessions, only grab Regular Sessions
        regular_sessions = [s for s in r['sessions'] if s.get('special') == 0]
        
        # Sort them from newest to oldest
        regular_sessions.sort(key=lambda x: x['session_id'], reverse=True)
        
        # Index 0 is the current session (2025-2026)
        # Index 1 is the previous session (2023-2024)
        if len(regular_sessions) > 1:
            target_session = regular_sessions[1]
            print(f"Targeting: {target_session.get('session_title')} (ID: {target_session['session_id']})")
            return target_session['session_id']
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
    print("Fetching official House roster for the selected session...")
    params = {'key': API_KEY, 'op': 'getSessionPeople', 'id': session_id}
    r = requests.get(BASE_URL, params=params).json()
    
    reps = {}
    if r.get('status') == 'OK':
        for person in r['sessionpeople']['people']:
            if person.get('role') == 'Rep':
                reps[person['people_id']] = {
                    'Name': person['name'],
                    'Party': person.get('party', 'Unknown'),
                    'Total Votes Cast': 0,
                    'Votes Against Party': 0
                }
    return reps

def process_bulk_dataset(session_id, access_key, reps):
    print("Downloading Bulk Dataset archive...")
    params = {'key': API_KEY, 'op': 'getDataset', 'id': session_id, 'access_key': access_key}
    r = requests.get(BASE_URL, params=params).json()
    
    if r.get('status') != 'OK':
        print("Failed to download dataset.")
        return list(reps.values())
        
    print("Unzipping archive and analyzing ALL votes...")
    zip_bytes = base64.b64decode(r['dataset']['zip'])
    
    total_roll_calls_found = 0
    analyzed_roll_calls = 0
    errors_encountered = 0
    
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        for filename in z.namelist():
            if '/vote/' in filename.lower() and filename.endswith('.json'):
                total_roll_calls_found += 1
                with z.open(filename) as f:
                    try:
                        data = json.load(f)
                        rc = data.get('roll_call') or data.get('vote') or {}
                        votes = rc.get('votes', [])
                        
                        yeas = int(rc.get('yea', 0))
                        nays = int(rc.get('nay', 0))
                        total = yeas + nays
                        
                        if total == 0:
                            continue
                            
                        analyzed_roll_calls += 1
                        
                        # 1. Determine Party Lines
                        party_tallies = {'D': {1: 0, 2: 0}, 'R': {1: 0, 2: 0}}
                        for vote in votes:
                            pid = vote['people_id']
                            v_id = int(vote['vote_id'])
                            if pid in reps and v_id in [1, 2]: # 1 = Yea, 2 = Nay
                                party = reps[pid]['Party']
                                if party in party_tallies:
                                    party_tallies[party][v_id] += 1
                                    
                        dem_line = 1 if party_tallies['D'][1] > party_tallies['D'][2] else 2
                        gop_line = 1 if party_tallies['R'][1] > party_tallies['R'][2] else 2
                        
                        # 2. Grade the Representatives based on the party line
                        for vote in votes:
                            pid = vote['people_id']
                            v_id = int(vote['vote_id'])
                            
                            if pid in reps and v_id in [1, 2]:
                                reps[pid]['Total Votes Cast'] += 1
                                party = reps[pid]['Party']
                                
                                if party == 'D' and v_id != dem_line:
                                    reps[pid]['Votes Against Party'] += 1
                                elif party == 'R' and v_id != gop_line:
                                    reps[pid]['Votes Against Party'] += 1
                                    
                    except Exception as e:
                        errors_encountered += 1
                        continue 
                        
    print(f"Total 'vote' files found in ZIP: {total_roll_calls_found}")
    print(f"Total files that crashed during read: {errors_encountered}")
    print(f"Total votes successfully evaluated: {analyzed_roll_calls}")
    return list(reps.values())

def save_to_csv(data, filename='mi_reps_data_2023_2024.csv'):
    print(f"Saving Final Rebel Data to {filename}...")
    
    for row in data:
        if row['Total Votes Cast'] > 0:
            row['Rebellion Rate (%)'] = round((row['Votes Against Party'] / row['Total Votes Cast']) * 100, 1)
        else:
            row['Rebellion Rate (%)'] = 0.0

    data = sorted(data, key=lambda x: x['Rebellion Rate (%)'], reverse=True) 
    headers = ['Name', 'Party', 'Total Votes Cast', 'Votes Against Party', 'Rebellion Rate (%)']
    
    with open(filename, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(data)
            
    print("Success! Professional-grade CSV generated.")

if __name__ == "__main__":
    sid = get_previous_session()
    if sid:
        akey = get_dataset_access_key(sid)
        if akey:
            reps = get_representatives(sid)
            final_data = process_bulk_dataset(sid, akey, reps)
            save_to_csv(final_data)
        else:
            print("Error: Could not find Bulk Dataset access key.")
    else:
        print("Error: Could not find session ID.")
