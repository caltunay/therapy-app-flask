from flask import Blueprint, render_template, request, session, send_file, jsonify
import random
from gtts import gTTS
from io import BytesIO
from Levenshtein import distance as levenshtein_distance
from auth_service import login_required
from data_services import get_random_entry, get_image_url

# Create blueprint
word_guessing_bp = Blueprint('word_guessing', __name__, url_prefix='/word-guessing')

def calculate_word_guess_score(expected_text, guess_text):
    """Calculate word guess similarity using Levenshtein distance"""
    if not expected_text or not guess_text:
        return {'similarity_percentage': 0, 'levenshtein_distance': len(expected_text) if expected_text else 0}
    
    # Normalize text (remove extra spaces, convert to lowercase)
    expected_text = ' '.join(expected_text.lower().split())
    guess_text = ' '.join(guess_text.lower().split())
    
    # Calculate Levenshtein distance
    distance = levenshtein_distance(expected_text, guess_text)
    max_length = max(len(expected_text), len(guess_text))
    
    # Calculate similarity percentage
    if max_length == 0:
        similarity_percentage = 100
    else:
        similarity_percentage = (1 - distance / max_length) * 100
    
    return {
        'similarity_percentage': similarity_percentage,
        'levenshtein_distance': distance
    }

@word_guessing_bp.route('/')
@login_required
def index():
    item = get_random_entry()
    if not item:
        return "No data found"
    s3_key = item.get('s3_key', '')
    image_url = get_image_url(s3_key)
    tr_word = item.get('tr_word', '')

    # If session already has tr_word and image_url, use them
    if session.get('tr_word') == tr_word and session.get('image_url') == image_url:
        revealed_indices = session.get('revealed_indices', [])
    else:
        session['tr_word'] = tr_word
        session['image_url'] = image_url
        revealed_indices = []  # Reset explicitly
        session['revealed_indices'] = revealed_indices

    # Always rebuild censored string explicitly
    censored = ''
    for i in range(len(tr_word)):
        if i in session['revealed_indices'] or tr_word[i] == ' ':
            censored += tr_word[i]
        else:
            censored += '_'

    session['censored'] = censored
    
    print(f"tr_word: '{tr_word}', length: {len(tr_word)}")
    print(f"censored: '{censored}', length: {len(censored)}")
    print("Revealed indices at start of new word:", session.get('revealed_indices'))

    return render_template('word_guessing.html', image_url=image_url, censored=censored, revealed=len(session['revealed_indices']), tr_word=tr_word)

@word_guessing_bp.route('/hint', methods=['POST'])
@login_required
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

@word_guessing_bp.route('/pronounce')
@login_required
def pronounce():
    tr_word = session.get('tr_word', '')
    if not tr_word:
        return ('', 404)
    
    # Cache-busting parameter is ignored but helps prevent browser caching
    _ = request.args.get('t')  # timestamp parameter for cache-busting
    
    tts = gTTS(text=tr_word, lang='tr', slow=True)
    mp3_fp = BytesIO()
    tts.write_to_fp(mp3_fp)
    mp3_fp.seek(0)
    return send_file(mp3_fp, mimetype='audio/mpeg')

@word_guessing_bp.route('/word-guess', methods=['POST'])
@login_required
def word_guess():
    """Check user's word guess using Levenshtein distance"""
    data = request.get_json()
    user_guess = data.get('guess', '').strip()
    tr_word = session.get('tr_word', '')
    
    if not user_guess:
        return jsonify({'error': 'Lütfen bir kelime girin!'}), 400
    
    if not tr_word:
        return jsonify({'error': 'Karşılaştırılacak kelime yok'}), 400
    
    # Calculate similarity score
    score_data = calculate_word_guess_score(tr_word, user_guess)
    score = score_data['similarity_percentage']
    
    # Determine message based on score (same as pronunciation game)
    if score >= 90:
        message = "🎉 Harika! Çok güzel bir tahmin!"
        is_correct = True
    elif score >= 75:
        message = "👍 Çok iyi! Güzel ilerliyorsunuz!"
        is_correct = True
    elif score >= 60:
        message = "👌 Güzel! Her seferinde daha da iyileşiyorsunuz!"
        is_correct = False
    else:
        message = "💪 Harika bir başlangıç! Her deneme sizi ileriye taşıyor!"
        is_correct = False
    
    # If score is high enough, reveal the word
    if is_correct:
        session['revealed_indices'] = list(range(len(tr_word)))
        session['censored'] = tr_word
    
    return jsonify({
        'guess': user_guess,
        'expected': tr_word,
        'score': round(score),
        'message': message,
        'is_correct': is_correct,
        'censored': session.get('censored', tr_word) if is_correct else session.get('censored', ''),
        'levenshtein_distance': score_data['levenshtein_distance']
    })

@word_guessing_bp.route('/guess', methods=['POST'])
@login_required
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
