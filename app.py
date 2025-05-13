from flask import Flask, render_template, request, session, redirect, url_for, send_file, jsonify
import random
import requests
from dotenv import load_dotenv
import os 
import boto3 
from gtts import gTTS
from io import BytesIO

# load env variables
load_dotenv()

# get key from env
SUPABASE_ANON_PUBLIC_KEY = os.getenv('SUPABASE_ANON_PUBLIC_KEY')
SUPABASE_PROJECT_URL = os.getenv('SUPABASE_PROJECT_URL')
SUPABASE_TABLE = 'speech-therapy-s3-keys'

AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_REGION = os.getenv('AWS_REGION')
AWS_BUCKET = 'therapy-app-s3'

# Debug: print bucket name
print(f"AWS_BUCKET value: '{AWS_BUCKET}'")

# start app
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev')  

def get_random_entry():
    headers = {
        "apikey": SUPABASE_ANON_PUBLIC_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_PUBLIC_KEY}"
    }

    response = requests.get(
        f"{SUPABASE_PROJECT_URL}/rest/v1/{SUPABASE_TABLE}?select=s3_key,eng_word,tr_word",
        headers=headers
    )

    if response.status_code != 200:
        return None

    data = response.json()
    if not data:
        return None

    return random.choice(data)

def get_image_url(s3_key):
    s3 = boto3.client('s3',
                    region_name=AWS_REGION,
                    aws_access_key_id=AWS_ACCESS_KEY,
                    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
    )
     
    url = s3.generate_presigned_url('get_object',
                                    Params={'Bucket': AWS_BUCKET, 'Key':s3_key},
                                    ExpiresIn=3600
    )

    return url

@app.route('/', methods=['GET'])
def index():
    item = get_random_entry()
    if not item:
        return "No data found"
    s3_key = item.get('s3_key', '')
    image_url = get_image_url(s3_key)
    tr_word = item.get('tr_word', '')

    # If session already has tr_word and image_url, use them
    if session.get('tr_word') == tr_word and session.get('image_url') == image_url:
        censored = session.get('censored', '_' * len(tr_word))
        revealed_indices = session.get('revealed_indices', [])
    else:
        session['tr_word'] = tr_word
        session['image_url'] = image_url
        revealed_indices = []  # Initialize before use
        session['revealed_indices'] = revealed_indices
        
        # Build censored string, keeping spaces as spaces
        censored = ''.join([tr_word[i] if (i in revealed_indices or tr_word[i] == ' ') else '_' for i in range(len(tr_word))])
        session['censored'] = censored
    return render_template('index.html', image_url=image_url, censored=censored, revealed=len(revealed_indices), tr_word=tr_word)

@app.route('/hint', methods=['POST'])
def hint():
    tr_word = session.get('tr_word', '')
    image_url = session.get('image_url', '')
    revealed_indices = session.get('revealed_indices', [])
    # Find unrevealed indices (ignore spaces)
    unrevealed = [i for i in range(len(tr_word)) if i not in revealed_indices and tr_word[i] != ' ']
    if unrevealed:
        idx = random.choice(unrevealed)
        revealed_indices.append(idx)
        session['revealed_indices'] = revealed_indices
    # Build censored string, keeping spaces as spaces
    censored = ''.join([tr_word[i] if (i in revealed_indices or tr_word[i] == ' ') else '_' for i in range(len(tr_word))])
    session.modified = True
    session['censored'] = censored
    return {'censored': censored, 'revealed': len(revealed_indices)}

@app.route('/pronounce')
def pronounce():
    tr_word = session.get('tr_word', '')
    if not tr_word:
        return ('', 404)
    tts = gTTS(text=tr_word, lang='tr', slow=True)
    mp3_fp = BytesIO()
    tts.write_to_fp(mp3_fp)
    mp3_fp.seek(0)
    return send_file(mp3_fp, mimetype='audio/mpeg')

@app.route('/guess', methods=['POST'])
def guess():
    data = request.get_json()
    idx = int(data.get('index'))
    letter = data.get('letter', '').strip()
    tr_word = session.get('tr_word', '')
    revealed_indices = session.get('revealed_indices', [])
    if idx < 0 or idx >= len(tr_word):
        return jsonify({'success': False})
    if tr_word[idx].lower() == letter.lower():
        if idx not in revealed_indices:
            revealed_indices.append(idx)
            session['revealed_indices'] = revealed_indices
            censored = ''.join([tr_word[i] if (i in revealed_indices or tr_word[i] == ' ') else '_' for i in range(len(tr_word))])
            session['censored'] = censored
            session.modified = True
        return jsonify({'success': True, 'censored': session['censored']})
    else:
        return jsonify({'success': False})

if __name__ == "__main__":
    app.run(debug=True)