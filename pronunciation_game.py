from flask import Blueprint, render_template, request, session, send_file, jsonify
from gtts import gTTS
from io import BytesIO
import random
from Levenshtein import distance as levenshtein_distance
from auth_service import login_required
from data_services import get_random_entry, get_random_sentence

# Create blueprint
pronunciation_game_bp = Blueprint('pronunciation_game', __name__, url_prefix='/pronunciation-game')

def calculate_pronunciation_score(expected_text, transcribed_text):
    """Calculate pronunciation similarity using Levenshtein distance"""
    # Normalize texts (lowercase, strip whitespace)
    expected = expected_text.lower().strip()
    transcribed = transcribed_text.lower().strip()
    
    # Calculate Levenshtein distance
    distance = levenshtein_distance(expected, transcribed)
    
    # Calculate similarity as percentage
    max_length = max(len(expected), len(transcribed))
    if max_length == 0:
        return 100.0
    
    similarity_percentage = (1 - distance / max_length) * 100
    
    return {
        'similarity_percentage': round(similarity_percentage, 1),
        'levenshtein_distance': distance,
        'expected_length': len(expected),
        'transcribed_length': len(transcribed)
    }

@pronunciation_game_bp.route('/')
@login_required
def index():
    """Main pronunciation game page"""
    # Get mode from query parameters (default to 'kelime')
    mode = request.args.get('mode', 'kelime')
    
    # Get content based on mode
    if mode == 'cumle':
        # Get random sentence
        sentence_data = get_random_sentence()
        content = sentence_data.get('sentence', '') if sentence_data else 'Cümle bulunamadı'
        content_type = 'sentence'
    else:
        # Get random word (default mode)
        word_data = get_random_entry()
        content = word_data.get('tr_word', '') if word_data else 'Kelime bulunamadı'
        content_type = 'word'
    
    # Store in session
    session['pronunciation_game_content'] = content
    session['pronunciation_game_mode'] = mode
    session['pronunciation_game_content_type'] = content_type
    
    return render_template('pronunciation_game.html', 
                         content=content, 
                         mode=mode, 
                         content_type=content_type)

@pronunciation_game_bp.route('/get-new-content', methods=['POST'])
@login_required
def get_new_content():
    """Get new random content based on current mode"""
    data = request.get_json()
    mode = data.get('mode', 'kelime')
    
    # Get content based on mode
    if mode == 'cumle':
        # Get random sentence
        sentence_data = get_random_sentence()
        content = sentence_data.get('sentence', '') if sentence_data else 'Cümle bulunamadı'
        content_type = 'sentence'
    else:
        # Get random word
        word_data = get_random_entry()
        content = word_data.get('tr_word', '') if word_data else 'Kelime bulunamadı'
        content_type = 'word'
    
    # Store in session
    session['pronunciation_game_content'] = content
    session['pronunciation_game_mode'] = mode
    session['pronunciation_game_content_type'] = content_type
    
    return jsonify({
        'content': content, 
        'mode': mode, 
        'content_type': content_type
    })

@pronunciation_game_bp.route('/pronounce')
@login_required
def pronounce():
    """Pronounce the current content using TTS - same method as main app"""
    content = session.get('pronunciation_game_content', '')
    if not content:
        return ('', 404)
    
    # Cache-busting parameter is ignored but helps prevent browser caching
    _ = request.args.get('t')  # timestamp parameter for cache-busting
    
    tts = gTTS(text=content, lang='tr', slow=True)
    mp3_fp = BytesIO()
    tts.write_to_fp(mp3_fp)
    mp3_fp.seek(0)
    return send_file(mp3_fp, mimetype='audio/mpeg')

@pronunciation_game_bp.route('/guess', methods=['POST'])
@login_required
def guess():
    """Check if the user's guess matches the current content using similarity scoring"""
    data = request.get_json()
    user_guess = data.get('guess', '').strip()
    
    # Get the correct answer from session
    correct_answer = session.get('pronunciation_game_content', '')
    
    if not correct_answer:
        return jsonify({'success': False, 'error': 'No content found'})
    
    if not user_guess:
        return jsonify({'success': False, 'error': 'No guess provided'})
    
    # Calculate similarity score using Levenshtein distance
    score_data = calculate_pronunciation_score(correct_answer, user_guess)
    score = score_data['similarity_percentage']
    
    # Determine accuracy level and message based on score
    if score >= 90:
        accuracy_level = "Mükemmel"
        message = "🎉 Harika! Çok güzel bir performans!"
        success = True
    elif score >= 75:
        accuracy_level = "İyi"
        message = "👍 Çok iyi! Güzel ilerliyorsunuz!"
        success = True
    elif score >= 60:
        accuracy_level = "Güzel"
        message = "👌 Güzel! Her seferinde daha da iyileşiyorsunuz!"
        success = True
    else:
        accuracy_level = "Devam edin"
        message = "💪 Harika bir başlangıç! Her deneme sizi ileriye taşıyor!"
        success = True
    
    return jsonify({
        'success': success,
        'score': score,
        'accuracy_level': accuracy_level,
        'message': message,
        'user_guess': user_guess,
        'correct_answer': correct_answer,
        'levenshtein_distance': score_data['levenshtein_distance']
    })
