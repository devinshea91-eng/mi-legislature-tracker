import requests
import csv
import os
import time

# --- CONFIGURATION ---
API_KEY = os.environ.get('LEGISCAN_API_KEY')  
STATE = 'MI'                   
BASE_URL = 'https://api.legiscan.com/'

def get_recent_sessions():
    print("Finding the current and previous Michigan sessions...")
    params = {'key': API_KEY, 'op': 'getSessionList', 'state': STATE}
    response = requests.get(BASE_URL, params=params)
    
    session_ids = []
    if response.status_code == 200:
        data = response.json()
        if data.get('status') == 'OK':
            # Sort all sessions from newest to oldest
            sessions = data.get('sessions', [])
            sessions.sort(key=lambda x: x.get('session_id', 0), reverse=True)
            
            # Grab the 2 most recent session IDs (Current and Previous)
            session_ids = [s['session_id'] for s in sessions[:2]]
            print(f"Found Session IDs: {session_ids}")
        else:
            print("API Error: Could not load sessions.")
    return session_ids

def get_representatives(session_ids):
    reps = {}
    for sid in session_ids:
        print(f"Fetching official House roster for session {sid}...")
        params = {'key': API_KEY, 'op': 'getSessionPeople', 'id': sid}
        response = requests.get(BASE_URL, params=params)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'OK':
                for person in data['sessionpeople']['people']:
                    # Only grab House Representatives
                    if person.get('role') == 'Rep':
                        pid = person['people_id']
                        if pid not in reps:
                            reps[pid] = {
                                'Name': person['name'],
                                'Party': person.get('party', 'Unknown'),
                                'Bills Introduced': 0,
                                'Bills Passed': 0
                            }
        time.sleep(0.5) # Pause to respect API rate limits
    return reps

def process_sponsored_bills(reps, session_ids):
    print(f"Counting bills for {len(reps)} representatives... (This will take about 1-2 minutes)")
    
    for pid, rep_data in reps.items():
        params = {'key': API_KEY, 'op': 'getSponsoredList', 'id': pid}
        response = requests.get(BASE_URL, params=params)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'OK':
                # LegiScan usually stores this under 'sponsoredbills' or 'bills'
                bills = data.get('sponsoredbills') or data.get('bills') or []
                
                for bill in bills:
                    # Only count bills if they belong to the 2 sessions we selected
                    if bill.get('session_id') in session_ids:
                        rep_data['Bills Introduced'] += 1
                        
                        # Status 4 = Passed/Enacted
                        if bill.get('status') == 4:
                            rep_data['Bills Passed'] += 1
                            
        time.sleep(0.5) # Pause so LegiScan doesn't block us
            
    return list(reps.values())

def save_to_csv(data, filename='mi_reps_data.csv'):
    print(f"Saving finalized data to {filename}...")
    headers = ['Name', 'Party', 'Bills Introduced', 'Bills Passed']
    
    # Sort alphabetically by name
    data = sorted(data, key=lambda x: x['Name'])
    
    with open(filename, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        for row in data:
            writer.writerow(row)
            
    print("Success! Your comprehensive spreadsheet is ready.")

if __name__ == "__main__":
    if not API_KEY:
        print("Error: API Key not found in GitHub Secrets!")
    else:
        sessions = get_recent_sessions()
        if sessions:
            reps_data = get_representatives(sessions)
            if reps_data:
                final_data = process_sponsored_bills(reps_data, sessions)
                save_to_csv(final_data)
            else:
                print("Failed to pull representatives.")
