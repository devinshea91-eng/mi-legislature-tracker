import requests
import csv
import os
import time

# --- CONFIGURATION ---
API_KEY = os.environ.get('LEGISCAN_API_KEY')  
STATE = 'MI'                   
BASE_URL = 'https://api.legiscan.com/'

def get_current_session_id():
    print("Finding current Michigan legislative session ID...")
    params = {'key': API_KEY, 'op': 'getSessionList', 'state': STATE}
    response = requests.get(BASE_URL, params=params)
    if response.status_code == 200 and response.json().get('status') == 'OK':
        latest_session = max(response.json()['sessions'], key=lambda x: x['session_id'])
        return latest_session['session_id']
    return None

def get_representatives(session_id):
    print("Fetching House roster and party affiliations...")
    params = {'key': API_KEY, 'op': 'getSessionPeople', 'id': session_id}
    response = requests.get(BASE_URL, params=params)
    
    reps = {}
    if response.status_code == 200 and response.json().get('status') == 'OK':
        for person in response.json()['sessionpeople']['people']:
            if person.get('role') == 'Rep':
                reps[person['people_id']] = {
                    'Name': person['name'],
                    'Party': person.get('party', 'Unknown'),
                    'Total Votes': 0,
                    'Votes Against Party': 0
                }
    return reps

def analyze_party_rebels(reps, session_id):
    print("Pulling a sample of recent bills to analyze voting records...")
    
    # 1. Get the Master List of bills
    params = {'key': API_KEY, 'op': 'getMasterList', 'id': session_id}
    response = requests.get(BASE_URL, params=params)
    if response.status_code != 200 or response.json().get('status') != 'OK':
        return reps

    masterlist = response.json()['masterlist']
    bill_ids_to_check = []
    
    # Grab a small sample of 5 recent bills to prevent server timeouts
    for key, bill in masterlist.items():
        if key != 'session' and len(bill_ids_to_check) < 5:
            bill_ids_to_check.append(bill['bill_id'])

    # 2. Extract Roll Call IDs from those bills
    roll_call_ids = []
    for bill_id in bill_ids_to_check:
        params = {'key': API_KEY, 'op': 'getBill', 'id': bill_id}
        resp = requests.get(BASE_URL, params=params)
        time.sleep(0.5) # Speed limit pause
        if resp.status_code == 200 and resp.json().get('status') == 'OK':
            for rc in resp.json()['bill'].get('votes', []):
                roll_call_ids.append(rc['roll_call_id'])

    print(f"Analyzing {len(roll_call_ids)} recent roll call votes...")

    # 3. Analyze who voted against their party
    for rc_id in roll_call_ids:
        params = {'key': API_KEY, 'op': 'getRollCall', 'id': rc_id}
        resp = requests.get(BASE_URL, params=params)
        time.sleep(0.5) # Speed limit pause
        
        if resp.status_code == 200 and resp.json().get('status') == 'OK':
            votes = resp.json()['roll_call']['votes']
            
            # Tally what the majority of each party voted (1 = Yea, 2 = Nay)
            party_tallies = {'D': {1: 0, 2: 0}, 'R': {1: 0, 2: 0}}
            
            for vote in votes:
                pid = vote['people_id']
                v_id = vote['vote_id']
                if pid in reps and v_id in [1, 2]: # Only count Yeas and Nays
                    party = reps[pid]['Party']
                    if party in party_tallies:
                        party_tallies[party][v_id] += 1
            
            # Determine the "Party Line" (which way did the majority vote?)
            dem_line = 1 if party_tallies['D'][1] > party_tallies['D'][2] else 2
            gop_line = 1 if party_tallies['R'][1] > party_tallies['R'][2] else 2
            
            # Check each rep against their party line
            for vote in votes:
                pid = vote['people_id']
                v_id = vote['vote_id']
                
                if pid in reps and v_id in [1, 2]:
                    reps[pid]['Total Votes'] += 1
                    party = reps[pid]['Party']
                    
                    if party == 'D' and v_id != dem_line:
                        reps[pid]['Votes Against Party'] += 1
                    elif party == 'R' and v_id != gop_line:
                        reps[pid]['Votes Against Party'] += 1

    return list(reps.values())

def save_to_csv(data, filename='mi_reps_data.csv'):
    print(f"Saving Rebel Data to {filename}...")
    
    # Calculate the exact rebellion percentage before saving
    for row in data:
        if row['Total Votes'] > 0:
            row['Rebellion Rate (%)'] = round((row['Votes Against Party'] / row['Total Votes']) * 100, 1)
        else:
            row['Rebellion Rate (%)'] = 0.0

    headers = ['Name', 'Party', 'Total Votes', 'Votes Against Party', 'Rebellion Rate (%)']
    data = sorted(data, key=lambda x: x['Rebellion Rate (%)'], reverse=True) # Sort highest rebels to the top
    
    with open(filename, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        for row in data:
            # We don't need these columns in the final CSV if we are just looking at the rate, but keeping them helps verify the math
            writer.writerow({
                'Name': row['Name'],
                'Party': row['Party'],
                'Total Votes': row['Total Votes'],
                'Votes Against Party': row['Votes Against Party'],
                'Rebellion Rate (%)': row['Rebellion Rate (%)']
            })
            
    print("Success! Rebel CSV generated.")

if __name__ == "__main__":
    session_id = get_current_session_id()
    if session_id:
        reps_data = get_representatives(session_id)
        if reps_data:
            final_data = analyze_party_rebels(reps_data, session_id)
            save_to_csv(final_data)
