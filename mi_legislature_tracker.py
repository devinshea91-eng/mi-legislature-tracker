import requests
import csv
import os

# --- CONFIGURATION ---
API_KEY = os.environ.get('LEGISCAN_API_KEY')  
STATE = 'MI'                   
BASE_URL = 'https://api.legiscan.com/'

def get_representatives():
    print("Fetching official list of Michigan Representatives...")
    params = {'key': API_KEY, 'op': 'getSessionPeople', 'state': STATE}
    response = requests.get(BASE_URL, params=params)
    
    reps = {}
    if response.status_code == 200:
        data = response.json()
        if data.get('status') == 'OK':
            # Loop through the roster and pull out the House members
            for person in data['sessionpeople']['people']:
                if person.get('role') == 'Rep':
                    reps[person['people_id']] = {
                        'Name': person['name'],
                        'Party': person.get('party', 'Unknown'),
                        'Bills Introduced': 0,
                        'Bills Passed': 0
                    }
    return reps

def process_bills(reps):
    print("Fetching and tallying all current bills...")
    params = {'key': API_KEY, 'op': 'getMasterList', 'state': STATE}
    response = requests.get(BASE_URL, params=params)
    
    if response.status_code == 200:
        data = response.json()
        if data.get('status') == 'OK':
            masterlist = data['masterlist']
            for key, bill in masterlist.items():
                if key == 'session':
                    continue
                
                # The API returns 'sponsor_id' for the primary sponsor
                sponsor_id = bill.get('sponsor_id')
                status = bill.get('status') 
                
                # If the sponsor is in our list of reps, add to their tally
                if sponsor_id in reps:
                    reps[sponsor_id]['Bills Introduced'] += 1
                    # In LegiScan, status 4 means Passed/Enacted
                    if status == 4:
                        reps[sponsor_id]['Bills Passed'] += 1
                        
    return list(reps.values())

def save_to_csv(data, filename='mi_reps_data.csv'):
    print(f"Saving real data to {filename}...")
    headers = ['Name', 'Party', 'Bills Introduced', 'Bills Passed']
    
    # Sort alphabetically by name to make it look nice in the spreadsheet
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
        reps_data = get_representatives()
        if reps_data:
            final_data = process_bills(reps_data)
            save_to_csv(final_data)
        else:
            print("Failed to pull representatives.")
