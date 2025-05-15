from flask import Blueprint, render_template, request, session, jsonify, send_file
import random
from data_services import get_random_sentence
from gtts import gTTS
from io import BytesIO

bosluk_bp = Blueprint('bosluk_bp', __name__, url_prefix='/bosluk')

@bosluk_bp.route('/')
def index():
    difficulty = request.args.get('difficulty', 'kolay')
    items = [get_random_sentence(difficulty) for _ in range(5)]
    sentences = [item.get('sentence', '') if item else '' for item in items]
    words = []
    hide_indices = []
    for s in sentences:
        ws = [w for w in s.split() if w.isalpha()]
        if ws:
            idx = random.randint(0, len(ws)-1)
            words.append(ws[idx].lower())
            hide_indices.append(idx)
        else:
            words.append('')
            hide_indices.append(0)
    main_sentence = sentences[0]
    main_words = main_sentence.split()
    main_idx = hide_indices[0]
    hidden_word = words[0] if words else ''
    original_sentence = main_sentence  # Save the original, uncensored sentence

    if difficulty == 'zor':
        # Zor: hide the whole word in the sentence and show whole words in boxes
        if main_idx < len(main_words):
            main_words[main_idx] = '_' * len(main_words[main_idx])
        censored_sentence = ' '.join(main_words)
        # Shuffle the word boxes so the correct answer is not always first
        word_boxes = words.copy()
        random.shuffle(word_boxes)
        return render_template('bosluk.html', sentence=censored_sentence, difficulty=difficulty, word_boxes=word_boxes, hidden_word=hidden_word, original_word=hidden_word, original_sentence=original_sentence)
    else:
        # Kolay: hide only the first half of the word in the sentence and show first half in boxes
        if main_idx < len(main_words):
            word = main_words[main_idx]
            half = len(word) // 2
            censored = '_' * half + word[half:]
            main_words[main_idx] = censored
        censored_sentence = ' '.join(main_words)
        # Prepare first halves for word boxes
        word_first_halves = []
        for w in words:
            if w:
                half = len(w) // 2
                word_first_halves.append(w[:half])
            else:
                word_first_halves.append('')
        # Shuffle the word boxes so the correct answer is not always first
        word_boxes = word_first_halves.copy()
        random.shuffle(word_boxes)
        return render_template('bosluk.html', sentence=censored_sentence, difficulty=difficulty, word_boxes=word_boxes, hidden_word='_' * (len(hidden_word)//2) + hidden_word[len(hidden_word)//2:], original_word=hidden_word, original_sentence=original_sentence)

@bosluk_bp.route('/guess', methods=['POST'])
def guess():
    data = request.get_json()
    idx = int(data.get('index'))
    letter = data.get('letter', '').strip()
    hide_word = session.get('bosluk_hide_word', '')
    revealed_indices = session.get('bosluk_revealed_indices', [])
    if idx < 0 or idx >= len(hide_word):
        return jsonify({'success': False})
    if hide_word[idx].lower() == letter.lower():
        if idx not in revealed_indices:
            revealed_indices.append(idx)
            session['bosluk_revealed_indices'] = revealed_indices
            # Build censored word
            censored_word = ''.join(
                hide_word[i] if i in revealed_indices else '_' for i in range(len(hide_word))
            )
            # Replace in sentence
            char_idx = session.get('bosluk_hide_word_start', 0)
            sentence = session.get('bosluk_sentence', '')
            censored_sentence = sentence[:char_idx] + censored_word + sentence[char_idx+len(hide_word):]
            session['bosluk_censored'] = censored_sentence
            session.modified = True
        return jsonify({'success': True, 'censored': session['bosluk_censored']})
    else:
        return jsonify({'success': False})

@bosluk_bp.route('/multi')
def multi():
    difficulty = request.args.get('difficulty', 'kolay')
    # Get the main sentence and 4 more
    items = [get_random_sentence(difficulty) for _ in range(5)]
    sentences = [item.get('sentence', '') if item else '' for item in items]
    words = []
    hide_indices = []
    for s in sentences:
        ws = [w for w in s.split() if w.isalpha()]
        if ws:
            idx = random.randint(0, len(ws)-1)
            words.append(ws[idx].lower())
            hide_indices.append(idx)
        else:
            words.append('')
            hide_indices.append(0)
    # For the first sentence, hide the word
    main_sentence = sentences[0]
    main_words = main_sentence.split()
    main_idx = hide_indices[0]
    if main_idx < len(main_words):
        main_words[main_idx] = '_' * len(main_words[main_idx])
    censored_sentence = ' '.join(main_words)
    # Pass all words to template
    return render_template('bosluk.html', sentence=censored_sentence, difficulty=difficulty, word_boxes=words)

@bosluk_bp.route('/pronounce_sentence')
def pronounce_sentence():
    # Get the current sentence from the query or session (here, from the request args for simplicity)
    sentence = request.args.get('sentence')
    if not sentence:
        # Try to get from referrer or fallback to a default
        sentence = request.args.get('sentence') or ''
    # If not provided, try to get from the rendered template context (not available here), so fallback to empty
    if not sentence:
        return ('', 404)
    tts = gTTS(text=sentence, lang='tr', slow=True)
    mp3_fp = BytesIO()
    tts.write_to_fp(mp3_fp)
    mp3_fp.seek(0)
    return send_file(mp3_fp, mimetype='audio/mpeg')