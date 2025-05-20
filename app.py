from flask import Flask, render_template, request, session, redirect, url_for, send_file, jsonify, Response
import random
from dotenv import load_dotenv
import os 
from gtts import gTTS
from io import BytesIO

# Import the blueprints and services
from breathing import breathing_bp
from bosluk import bosluk_bp
from memory import memory_bp
from data_services import get_random_entry, get_image_url

# load env variables
load_dotenv()

# start app
app = Flask(__name__)
app.secret_key = os.getenv('SESSION_SECRET_KEY')

# Register the breathing blueprint
app.register_blueprint(breathing_bp)
app.register_blueprint(bosluk_bp)
app.register_blueprint(memory_bp)

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
        censored = ''
        for i in range(len(tr_word)):
            if i in revealed_indices or tr_word[i] == ' ':
                censored += tr_word[i]
            else:
                censored += '_'
        
        session['censored'] = censored
    return render_template('index.html', image_url=image_url, censored=censored, revealed=len(revealed_indices), tr_word=tr_word)

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
    censored = ''
    for i in range(len(tr_word)):
        if i in revealed_indices or tr_word[i] == ' ':
            censored += tr_word[i]
        else:
            censored += '_'
    
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
            
            # Build censored string with the updated revealed indices
            censored = ''
            for i in range(len(tr_word)):
                if i in revealed_indices or tr_word[i] == ' ':
                    censored += tr_word[i]
                else:
                    censored += '_'
            
            session['censored'] = censored
            session.modified = True
        return jsonify({'success': True, 'censored': session['censored']})
    else:
        return jsonify({'success': False})

@app.route('/breathing')
def breathing_redirect():
    return redirect(url_for('breathing_bp.index'))

@app.route('/breathing/start')
def breathing_start_redirect():
    # Forward any query parameters
    return redirect(url_for('breathing_bp.start', **request.args))

if __name__ == "__main__":
    app.run(debug=True)