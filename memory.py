from flask import Blueprint, render_template, session, request, jsonify, redirect, url_for
import random

memory_bp = Blueprint('memory_bp', __name__, url_prefix='/memory')

DIFFICULTY_SETTINGS = {
    'Kolay': {'num_boxes': 2, 'num_choices_multiplier': 2},
    'Orta': {'num_boxes': 3, 'num_choices_multiplier': 2},
    'Zor': {'num_boxes': 4, 'num_choices_multiplier': 2},
    'Cok Zor': {'num_boxes': 5, 'num_choices_multiplier': 2}
}
DEFAULT_DIFFICULTY = 'Kolay'

@memory_bp.route('/')
def index():
    # Reset game state
    session['game_state'] = 'setup'
    
    difficulty = request.args.get('difficulty', session.get('difficulty', DEFAULT_DIFFICULTY))
    if difficulty not in DIFFICULTY_SETTINGS:
        difficulty = DEFAULT_DIFFICULTY
    session['difficulty'] = difficulty

    settings = DIFFICULTY_SETTINGS[difficulty]
    num_boxes = settings['num_boxes']
    
    # Generate random numbers for each box (0-100)
    original_numbers = [random.randint(0, 100) for _ in range(num_boxes)]
    
    # Store original numbers in session
    session['original_numbers'] = original_numbers
    
    return render_template('memory.html', 
                          box_numbers=original_numbers, 
                          game_state='setup',
                          countdown=5,
                          current_difficulty=difficulty,
                          difficulties=list(DIFFICULTY_SETTINGS.keys()))

@memory_bp.route('/play')
def play():
    # Move to the play phase
    if 'original_numbers' not in session or 'difficulty' not in session:
        return redirect(url_for('memory_bp.index'))
    
    original_numbers = session['original_numbers']
    difficulty = session['difficulty']
    settings = DIFFICULTY_SETTINGS[difficulty]
    session['game_state'] = 'play'
    
    # Generate choice numbers (original + decoys)
    all_numbers = original_numbers.copy()
    
    num_choices = settings['num_boxes'] * settings['num_choices_multiplier']

    # Add decoy numbers
    while len(all_numbers) < num_choices: # Use num_choices based on difficulty
        num = random.randint(0, 100)
        if num not in all_numbers:
            all_numbers.append(num)
    
    # Shuffle the numbers
    random.shuffle(all_numbers)
    
    return render_template('memory.html',
                          box_numbers=original_numbers, # These are the ones to be guessed, shown as '?'
                          choice_numbers=all_numbers,
                          game_state='play',
                          current_difficulty=difficulty,
                          difficulties=list(DIFFICULTY_SETTINGS.keys()))

@memory_bp.route('/check', methods=['POST'])
def check():
    if 'original_numbers' not in session:
        return jsonify({'valid': False, 'message': 'No active game'})
    
    selected_number = int(request.form.get('number'))
    original_numbers = session['original_numbers']
    
    is_correct = selected_number in original_numbers
    
    # Initialize found_numbers if not present
    if 'found_numbers' not in session:
        session['found_numbers'] = []
    
    # Make a copy to avoid modification issues with session objects
    found_numbers = session['found_numbers'].copy()
    
    if is_correct and selected_number not in found_numbers:
        found_numbers.append(selected_number)
        session['found_numbers'] = found_numbers
        # Force the session to update
        session.modified = True
    
    # Debug output for troubleshooting
    # print(f"Debug - Selected: {selected_number}, Is Correct: {is_correct}")
    # print(f"Debug - Found Numbers: {session['found_numbers']}")
    # print(f"Debug - Original Numbers: {original_numbers}")
    
    # Check if all numbers have been found
    all_found = set(session['found_numbers']) == set(original_numbers)
    print(f"Debug - All Found: {all_found}")
    
    return jsonify({
        'valid': True,
        'correct': is_correct,
        'allFound': all_found,
        'debugInfo': {
            'found': session['found_numbers'],
            'original': original_numbers,
            'allFound': all_found
        }
    })