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
    print("Pulling the 20 most recently active bills to analyze voting records...")
    
    # 1. Get the Master List of bills
    params = {'key': API_KEY, 'op': 'getMasterList', 'id': session_id}
    response = requests.
