from flask import Flask, render_template, request, session, redirect, url_for
import random
import requests
from dotenv import load_dotenv
import os 

# load env variables
load_dotenv()

# get key from env
SUPABASE_ANON_PUBLIC_KEY = os.getenv('SUPABASE_ANON_PUBLIC_KEY')
SUPABASE_PROJECT_URL = os.getenv('SUPABASE_PROJECT_URL')
SUPABASE_TABLE = "speech-therapy-data" 

# start app
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev')  # Needed for session

@app.route('/', methods=['GET'])
def index():
    headers = {
        "apikey": SUPABASE_ANON_PUBLIC_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_PUBLIC_KEY}"
    }
    url = f"{SUPABASE_PROJECT_URL}/rest/v1/{SUPABASE_TABLE}?select=image_url,tr_word"
    resp = requests.get(url, headers=headers)
    data = resp.json()
    if not data:
        return "No data found"
    item = random.choice(data)
    image_url = item.get('image_url', '')
    tr_word = item.get('tr_word', '')
    # If session already has tr_word and image_url, use them
    if session.get('tr_word') == tr_word and session.get('image_url') == image_url:
        censored = session.get('censored', '_' * len(tr_word))
        revealed_indices = session.get('revealed_indices', [])
    else:
        session['tr_word'] = tr_word
        session['image_url'] = image_url
        session['revealed_indices'] = []
        censored = '_' * len(tr_word)
        revealed_indices = []
    return render_template('index.html', image_url=image_url, censored=censored, revealed=len(revealed_indices), tr_word=tr_word)

@app.route('/hint', methods=['POST'])
def hint():
    tr_word = session.get('tr_word', '')
    image_url = session.get('image_url', '')
    revealed_indices = session.get('revealed_indices', [])
    # Find unrevealed indices
    unrevealed = [i for i in range(len(tr_word)) if i not in revealed_indices]
    if unrevealed:
        idx = random.choice(unrevealed)
        revealed_indices.append(idx)
        session['revealed_indices'] = revealed_indices
    # Build censored string
    censored = ''.join([tr_word[i] if i in revealed_indices else '_' for i in range(len(tr_word))])
    session.modified = True
    session['censored'] = censored
    return {'censored': censored, 'revealed': len(revealed_indices)}

if __name__ == "__main__":
    app.run(debug=True)