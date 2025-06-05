from flask import Blueprint, render_template, request, session, send_file, jsonify
from gtts import gTTS
from io import BytesIO
import random
from auth_service import login_required
from data_services import get_random_entry, get_random_sentence

# Create blueprint
pronunciation_game_bp = Blueprint('pronunciation_game', __name__, url_prefix='/pronunciation-game')

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
    """Check if the user's guess matches the current content"""
    data = request.get_json()
    user_guess = data.get('guess', '').strip()
    
    # Get the correct answer from session
    correct_answer = session.get('pronunciation_game_content', '')
    
    if not correct_answer:
        return jsonify({'success': False, 'error': 'No content found'})
    
    if not user_guess:
        return jsonify({'success': False, 'error': 'No guess provided'})
    
    # Compare the guess with the actual content (case insensitive)
    if user_guess.lower() == correct_answer.lower():
        return jsonify({
            'success': True, 
            'correct_answer': correct_answer
        })
    else:
        return jsonify({
            'success': False,
            'correct_answer': correct_answer
        })
