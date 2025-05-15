from flask import Blueprint, render_template, request, Response
import json
import time

# Create a Blueprint with URL prefix
breathing_bp = Blueprint('breathing_bp', __name__, url_prefix='/breathing')

# Now the route doesn't need /breathing prefix since the blueprint has it
@breathing_bp.route('/')
def index():
    # Default values for the sliders
    breath_duration = request.args.get('breath_duration', 4, type=int)
    hold_duration = request.args.get('hold_duration', 2, type=int)
    
    return render_template('breathing.html', 
                          breath_duration=breath_duration,
                          hold_duration=hold_duration)

# Now the route is /breathing/start instead of /breathing/breathing/start
@breathing_bp.route('/start')
def start():
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