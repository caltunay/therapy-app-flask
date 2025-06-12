from flask import Blueprint, render_template, request, session, jsonify, send_file
import os
import random
import requests
from gtts import gTTS
from io import BytesIO
from Levenshtein import distance as levenshtein_distance
from auth_service import login_required

# Create blueprint
reverse_dictionary_bp = Blueprint('reverse_dictionary', __name__, url_prefix='/reverse-dictionary')

# Get environment variables for Supabase
SUPABASE_ANON_PUBLIC_KEY = os.getenv('SUPABASE_ANON_PUBLIC_KEY')
SUPABASE_PROJECT_URL = os.getenv('SUPABASE_PROJECT_URL')
DICTIONARY_TABLE = 'turkish-dictionary'

def get_random_dictionary_entry():
    """Get a random entry from the turkish-dictionary table"""
    headers = {
        "apikey": SUPABASE_ANON_PUBLIC_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_PUBLIC_KEY}"
    }

    response = requests.get(
        f"{SUPABASE_PROJECT_URL}/rest/v1/{DICTIONARY_TABLE}?select=word,description_formatted",
        headers=headers
    )

    if response.status_code != 200:
        return None

    data = response.json()
    if not data:
        return None

    return random.choice(data)

def calculate_guess_score(expected_word, user_guess):
    """Calculate similarity score using Levenshtein distance"""
    if not expected_word or not user_guess:
        return {
            'levenshtein_distance': float('inf'),
            'similarity_percentage': 0
        }
    
    # Normalize strings for comparison
    expected_normalized = expected_word.lower().strip()
    guess_normalized = user_guess.lower().strip()
    
    # Calculate Levenshtein distance
    distance = levenshtein_distance(expected_normalized, guess_normalized)
    
    # Calculate similarity percentage
    max_length = max(len(expected_normalized), len(guess_normalized))
    if max_length == 0:
        similarity_percentage = 100
    else:
        similarity_percentage = ((max_length - distance) / max_length) * 100
    
    return {
        'levenshtein_distance': distance,
        'similarity_percentage': max(0, similarity_percentage)
    }

@reverse_dictionary_bp.route('/')
@login_required
def index():
    """Main reverse dictionary page"""
    # Get mode from query parameters (default to 'kolay')
    mode = request.args.get('mode', 'kolay')
    
    # Get random dictionary entry
    dict_entry = get_random_dictionary_entry()
    if dict_entry:
        description = dict_entry.get('description_formatted', '')
        word = dict_entry.get('word', '')
    else:
        description = 'Tanım bulunamadı'
        word = ''
    
    # Store in session
    session['reverse_dictionary_description'] = description
    session['reverse_dictionary_word'] = word
    session['reverse_dictionary_mode'] = mode
    
    return render_template('reverse_dictionary.html', 
                         description=description,
                         word=word,
                         mode=mode)

@reverse_dictionary_bp.route('/get-new-content', methods=['POST'])
@login_required
def get_new_content():
    """Get new random dictionary entry"""
    data = request.json or {}
    mode = data.get('mode', 'kolay')
    
    # Get new dictionary entry
    dict_entry = get_random_dictionary_entry()
    if dict_entry:
        description = dict_entry.get('description_formatted', '')
        word = dict_entry.get('word', '')
    else:
        description = 'Tanım bulunamadı'
        word = ''
    
    # Store in session
    session['reverse_dictionary_description'] = description
    session['reverse_dictionary_word'] = word
    session['reverse_dictionary_mode'] = mode
    
    return jsonify({
        'description': description,
        'word': word,
        'mode': mode
    })

@reverse_dictionary_bp.route('/pronounce')
@login_required
def pronounce():
    """Pronounce the current description using TTS"""
    description = session.get('reverse_dictionary_description', '')
    if not description:
        return ('', 404)
    
    # Cache-busting parameter is ignored but helps prevent browser caching
    _ = request.args.get('t')  # timestamp parameter for cache-busting
    
    tts = gTTS(text=description, lang='tr', slow=True)
    mp3_fp = BytesIO()
    tts.write_to_fp(mp3_fp)
    mp3_fp.seek(0)
    return send_file(mp3_fp, mimetype='audio/mpeg')

@reverse_dictionary_bp.route('/guess', methods=['POST'])
@login_required
def guess():
    """Check user's guess against the correct word"""
    try:
        data = request.json or {}
        user_guess = data.get('guess', '').strip()
        
        # Get correct word from session
        correct_word = session.get('reverse_dictionary_word', '')
        
        if not correct_word:
            return jsonify({'error': 'Karşılaştırılacak kelime yok'}), 400
        
        if not user_guess:
            return jsonify({'error': 'Lütfen bir tahmin girin'}), 400
        
        # Calculate similarity score
        score_data = calculate_guess_score(correct_word, user_guess)
        score = score_data['similarity_percentage']
        
        # Determine accuracy level and message
        if score >= 90:
            accuracy_level = "Mükemmel"
            message = "🎉 Harika! Doğru cevap!"
        elif score >= 75:
            accuracy_level = "İyi"
            message = "👍 Çok yakın! Güzel tahmin!"
        elif score >= 60:
            accuracy_level = "Güzel"
            message = "👌 Güzel! Doğru yoldasınız!"
        else:
            accuracy_level = "Devam edin"
            message = "💪 Harika bir başlangıç! Tekrar deneyin!"
        
        return jsonify({
            'user_guess': user_guess,
            'correct_answer': correct_word,
            'score': score,
            'accuracy_level': accuracy_level,
            'message': message,
            'levenshtein_distance': score_data['levenshtein_distance']
        })
        
    except Exception as e:
        print(f"Error in guess: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Tahmin kontrol hatası: {str(e)}'}), 500
