from flask import Blueprint, render_template, session, request, jsonify, redirect, url_for
import random
from data_services import get_random_entry, get_image_url
from auth_service import login_required

image_memory_bp = Blueprint('image_memory_bp', __name__, url_prefix='/image_memory')

DIFFICULTY_SETTINGS = {
    'Kolay': {'num_images': 2, 'num_choices_multiplier': 2},
    'Orta': {'num_images': 3, 'num_choices_multiplier': 2},
    'Zor': {'num_images': 4, 'num_choices_multiplier': 2},
    'Cok Zor': {'num_images': 5, 'num_choices_multiplier': 2}
}
DEFAULT_DIFFICULTY = 'Kolay'

@image_memory_bp.route('/')
@login_required
def index():
    # Reset game state
    session['image_game_state'] = 'setup'
    
    difficulty = request.args.get('difficulty', session.get('image_difficulty', DEFAULT_DIFFICULTY))
    if difficulty not in DIFFICULTY_SETTINGS:
        difficulty = DEFAULT_DIFFICULTY
    session['image_difficulty'] = difficulty

    settings = DIFFICULTY_SETTINGS[difficulty]
    num_images = settings['num_images']
    
    # Get random entries for images
    original_images = []
    for _ in range(num_images):
        item = get_random_entry()
        if item:
            image_data = {
                's3_key': item.get('s3_key', ''),
                'tr_word': item.get('tr_word', ''),
                'image_url': get_image_url(item.get('s3_key', ''))
            }
            original_images.append(image_data)
    
    # Store original images in session
    session['original_images'] = original_images
    
    return render_template('image_memory.html', 
                          images=original_images, 
                          game_state='setup',
                          countdown=5,
                          current_difficulty=difficulty,
                          difficulties=list(DIFFICULTY_SETTINGS.keys()))

@image_memory_bp.route('/play')
@login_required
def play():
    # Move to the play phase
    if 'original_images' not in session or 'image_difficulty' not in session:
        return redirect(url_for('image_memory_bp.index'))
    
    original_images = session['original_images']
    difficulty = session['image_difficulty']
    settings = DIFFICULTY_SETTINGS[difficulty]
    session['image_game_state'] = 'play'
    
    # Generate choice images (original + decoys)
    all_images = original_images.copy()
    
    num_choices = settings['num_images'] * settings['num_choices_multiplier']

    # Add decoy images
    while len(all_images) < num_choices:
        item = get_random_entry()
        if item:
            decoy_image = {
                's3_key': item.get('s3_key', ''),
                'tr_word': item.get('tr_word', ''),
                'image_url': get_image_url(item.get('s3_key', ''))
            }
            # Check if this image is not already in the list (avoid duplicates)
            if not any(img['s3_key'] == decoy_image['s3_key'] for img in all_images):
                all_images.append(decoy_image)
    
    # Shuffle the images
    random.shuffle(all_images)
    
    # Reset found images for this session
    session['found_images'] = []
    
    return render_template('image_memory.html',
                          images=original_images, # These are the ones to be guessed, shown as '?'
                          choice_images=all_images,
                          game_state='play',
                          current_difficulty=difficulty,
                          difficulties=list(DIFFICULTY_SETTINGS.keys()))

@image_memory_bp.route('/check', methods=['POST'])
@login_required
def check():
    if 'original_images' not in session:
        return jsonify({'valid': False, 'message': 'No active game'})
    
    selected_s3_key = request.form.get('s3_key')
    original_images = session['original_images']
    
    # Check if selected image is in original images
    is_correct = any(img['s3_key'] == selected_s3_key for img in original_images)
    
    # Initialize found_images if not present
    if 'found_images' not in session:
        session['found_images'] = []
    
    # Make a copy to avoid modification issues with session objects
    found_images = session['found_images'].copy()
    
    if is_correct and selected_s3_key not in found_images:
        found_images.append(selected_s3_key)
        session['found_images'] = found_images
        # Force the session to update
        session.modified = True
    
    # Check if all images have been found
    original_s3_keys = [img['s3_key'] for img in original_images]
    all_found = set(session['found_images']) == set(original_s3_keys)
    
    return jsonify({
        'valid': True,
        'correct': is_correct,
        'allFound': all_found,
        'selected_image': next((img for img in original_images if img['s3_key'] == selected_s3_key), None) if is_correct else None,
        'debugInfo': {
            'found': session['found_images'],
            'original_keys': original_s3_keys,
            'allFound': all_found
        }
    })
