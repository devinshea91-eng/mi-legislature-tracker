import requests
import csv
import os

# --- CONFIGURATION ---
API_KEY = os.environ.get('LEGISCAN_API_KEY')  
STATE = 'MI'                   
BASE_URL = 'https://api.legiscan.com/'

def get_current_session_id():
    print("Finding current Michigan legislative session ID...")
    params = {'key': API_KEY, 'op': 'getSessionList', 'state': STATE}
    response = requests.get(BASE_URL, params=params)
    
    if response.status_code == 200:
        data = response.json()
        if data.get('status') == 'OK':
            # Finds the most recent session by looking for the highest ID number
            latest_session = max(data['sessions'], key=lambda x: x['session_id'])
            print(f"Found Session ID: {latest_session['session_id']}")
            return latest_session['session_id']
        else:
            print(f"API Error (Session): {data.get('alert', {}).get('message', 'Unknown error')}")
    return None

def get_representatives(session_id):
    print(f"Fetching official list of Representatives for session {session_id}...")
    # Using 'id' instead of 'state' to satisfy LegiScan's strict requirement
    params = {'key': API_KEY, 'op': 'getSessionPeople', 'id': session_id}
    response = requests.get(BASE_URL, params=params)
    
    reps = {}
    if response.status_code == 200:
        data = response.json()
        if data.get('status') == 'OK':
            for person in data['sessionpeople']['people']:
                if person.get('role') == 'Rep':
                    reps[person['people_id']] = {
                        'Name': person['name'],
                        'Party': person.get('party', 'Unknown'),
                        'Bills Introduced': 0,
                        'Bills Passed': 0
                    }
        else:
            print(f"API Error (Reps): {data.get('alert', {}).get('message', 'Unknown error')}")
    return reps

def process_bills(reps, session_id):
    print("Fetching and tallying all current bills...")
    params = {'key': API_KEY, 'op': 'getMasterList', 'id': session_id}
    response = requests.get(BASE_URL, params=params)
    
    if response.status_code == 200:
        data = response.json()
        if data.get('status') == 'OK':
            masterlist = data['masterlist']
            for key, bill in masterlist.items():
                if key == 'session':
                    continue
                
                sponsor_id = bill.get('sponsor_id')
                status = bill.get('status') 
                
                if sponsor_id in reps:
                    reps[sponsor_id]['Bills Introduced'] += 1
                    # In LegiScan, status 4 means Passed/Enacted
                    if status == 4:
                        reps[sponsor_id]['Bills Passed'] += 1
        else:
            print(f"API Error (Bills): {data.get('alert', {}).get('message', 'Unknown error')}")
            
    return list(reps.values())

def save_to_csv(data, filename='mi_reps_data.csv'):
    print(f"Saving real data to {filename}...")
    headers = ['Name', 'Party', 'Bills Introduced', 'Bills Passed']
    
    data = sorted(data, key=lambda x: x['Name'])
    
    with open(filename, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        for row in data:
            writer.writerow(row)
            
    print("Success! Real CSV file generated.")

if __name__ == "__main__":
    if not API_KEY:
        print("Error: API Key not found in GitHub Secrets!")
    else:
        session_id = get_current_session_id()
        if session_id:
            reps_data = get_representatives(session_id)
            if reps_data:
                final_data = process_bills(reps_data, session_id)
                save_to_csv(final_data)
            else:
                print("Failed to pull representatives.")
        else:
            print("Failed to find current session ID.")
