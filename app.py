# This file is now modularized. All logic has been moved to config.py, services.py, routes.py, __init__.py, and run.py.

from flask import Flask, render_template, request, session, redirect, url_for, send_file, jsonify, Response
import random
import requests
from dotenv import load_dotenv
import os 
import boto3 
from gtts import gTTS
from io import BytesIO
import time
import json

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
        f"{SUPABASE_PROJECT_URL}/rest/v1/{SUPABASE_TABLE}?select=s3_key,eng_word,tr_word&is_confirmed=eq.true",
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

@app.route('/breathing')
def breathing():
    # Default values for the sliders
    breath_duration = request.args.get('breath_duration', 4, type=int)
    hold_duration = request.args.get('hold_duration', 2, type=int)
    
    return render_template('breathing.html', 
                          breath_duration=breath_duration,
                          hold_duration=hold_duration)

@app.route('/breathing/start')
def breathing_start():
    """Start a new breathing session with server-sent events"""
    breath_duration = request.args.get('breath_duration', 4, type=int)
    hold_duration = request.args.get('hold_duration', 2, type=int)
    
    def generate():
        """Generate server-sent events for the breathing animation"""
        # Animation parameters
        min_size = 100  # pixels
        max_size = 250  # pixels
        
        # Initial state
        animation_state = 'inhale'
        frame_position = 0
        
        # Frame rate and total frames
        frame_rate = 10  # frames per second
        total_frames = breath_duration * frame_rate  # total frames for inhale/exhale
        
        # Loop for continuous breathing animation
        try:
            while True:
                # Calculate next animation state
                if animation_state == 'inhale':
                    if frame_position >= total_frames:
                        animation_state = 'hold_inhale'
                        circle_size = max_size
                        frame_position = 0
                        next_update = hold_duration
                    else:
                        # Calculate growing circle size
                        progress = frame_position / total_frames
                        circle_size = min_size + (max_size - min_size) * progress
                        frame_position += 1
                        next_update = 1 / frame_rate
                
                elif animation_state == 'hold_inhale':
                    animation_state = 'exhale'
                    circle_size = max_size
                    frame_position = 0
                    next_update = 1 / frame_rate
                    
                elif animation_state == 'exhale':
                    if frame_position >= total_frames:
                        animation_state = 'hold_exhale'
                        circle_size = min_size
                        frame_position = 0
                        next_update = hold_duration
                    else:
                        # Calculate shrinking circle size
                        progress = frame_position / total_frames
                        circle_size = max_size - (max_size - min_size) * progress
                        frame_position += 1
                        next_update = 1 / frame_rate
                        
                elif animation_state == 'hold_exhale':
                    animation_state = 'inhale'
                    circle_size = min_size
                    frame_position = 0
                    next_update = 1 / frame_rate
                
                # Set label based on state
                if animation_state == 'inhale':
                    label = '🌬️ Nefes Al...'
                    color = '#4CAF50'  # Green
                elif animation_state == 'hold_inhale':
                    label = 'Nefesini Tut...'
                    color = '#4CAF50'  # Green
                elif animation_state == 'exhale':
                    label = '😮‍💨 Nefes Ver...'
                    color = '#2196F3'  # Blue
                elif animation_state == 'hold_exhale':
                    label = 'Nefesini Tut...'
                    color = '#2196F3'  # Blue
                
                # Create event data
                data = {
                    'state': animation_state,
                    'circle_size': int(circle_size),
                    'label': label,
                    'color': color
                }
                
                # Send event
                yield f"data: {json.dumps(data)}\n\n"
                
                # Sleep for next update
                time.sleep(next_update)
                
        except GeneratorExit:
            # Client disconnected
            pass
    
    # Return server-sent events response
    return Response(generate(), mimetype='text/event-stream')

@app.route('/hint', methods=['POST'])
def hint():
    tr_word = session.get('tr_word', '')
    revealed_indices = session.get('revealed_indices', [])
    
    # Find unrevealed indices (ignore spaces)
    unrevealed = [i for i in range(len(tr_word)) if i not in revealed_indices and tr_word[i] != ' ']
    
    if unrevealed:
        idx = random.choice(unrevealed)
        revealed_indices.append(idx)
        session['revealed_indices'] = revealed_indices
    
    # Build censored string with the updated revealed indices
    censored = ''.join([tr_word[i] if (i in revealed_indices or tr_word[i] == ' ') else '_' for i in range(len(tr_word))])
    session['censored'] = censored
    
    return jsonify({'censored': censored, 'revealed': len(revealed_indices)})

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