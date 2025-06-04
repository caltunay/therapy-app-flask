from flask import Blueprint, render_template, request, jsonify, session
import os
import random
from Levenshtein import distance as levenshtein_distance
from google.cloud import speech
from auth_service import login_required

# Create blueprint
word_pronunciation_bp = Blueprint('word_pronunciation', __name__, url_prefix='/word-pronunciation')

# Test sentences
TEST_SENTENCES = [
    'Psikolojik dayanıklılık zorluklarla başa çıkmayı sağlar.',
    'Çevre kirliliği birçok türün neslini tehdit ediyor.'
]

# Set up Google Cloud credentials
credentials_path = 'google_stt.json'
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path

# Initialize Google Speech client (cached)
_speech_client = None

def get_speech_client():
    global _speech_client
    if _speech_client is None:
        _speech_client = speech.SpeechClient()
    return _speech_client

def transcribe_audio(audio_data):
    """Transcribe audio using Google Speech-to-Text API"""
    client = get_speech_client()
    
    # Configure request for recorded audio
    audio = speech.RecognitionAudio(content=audio_data)
    
    # First try with WEBM_OPUS (common for browser recordings)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
        language_code='tr-TR',  # Turkish
        enable_automatic_punctuation=True,
        audio_channel_count=1,
        enable_word_time_offsets=False
    )
    
    try:
        # Make request
        response = client.recognize(config=config, audio=audio)
        
        # Extract result
        if response.results:
            return response.results[0].alternatives[0].transcript
        else:
            # Try fallback configurations
            return try_fallback_configs(client, audio)
    except Exception as e:
        print(f"WEBM_OPUS failed: {e}")
        # Try fallback configurations
        return try_fallback_configs(client, audio)

def try_fallback_configs(client, audio):
    """Try different audio configurations if the first attempt fails"""
    # Try common configurations for browser audio
    common_configs = [
        # Browser MediaRecorder often uses these formats
        (speech.RecognitionConfig.AudioEncoding.WEBM_OPUS, None),
        (speech.RecognitionConfig.AudioEncoding.OGG_OPUS, None),
        (speech.RecognitionConfig.AudioEncoding.LINEAR16, 48000),
        (speech.RecognitionConfig.AudioEncoding.LINEAR16, 44100),
        (speech.RecognitionConfig.AudioEncoding.LINEAR16, 16000),
        (speech.RecognitionConfig.AudioEncoding.LINEAR16, 8000),
        # Let Google auto-detect
        (speech.RecognitionConfig.AudioEncoding.ENCODING_UNSPECIFIED, None),
    ]
    
    for encoding, sample_rate in common_configs:
        try:
            config_kwargs = {
                'encoding': encoding,
                'language_code': 'tr-TR',
                'enable_automatic_punctuation': True,
                'audio_channel_count': 1,
            }
            
            # Only set sample_rate_hertz if we have a value
            if sample_rate:
                config_kwargs['sample_rate_hertz'] = sample_rate
                
            config = speech.RecognitionConfig(**config_kwargs)
            response = client.recognize(config=config, audio=audio)
            
            if response.results:
                print(f"Success with encoding: {encoding.name}, sample rate: {sample_rate}")
                return response.results[0].alternatives[0].transcript
                
        except Exception as e:
            print(f"Failed with {encoding.name}, sample rate {sample_rate}: {e}")
            continue
    
    # If all attempts fail, return error message
    return "Konuşma algılanamadı - lütfen sessiz bir ortamda tekrar kayıt yapmayı deneyin"

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

@word_pronunciation_bp.route('/')
@login_required
def index():
    """Main word pronunciation page"""
    # Get a random sentence
    random_sentence = random.choice(TEST_SENTENCES)
    session['current_sentence'] = random_sentence
    
    return render_template('word_pronunciation.html', sentence=random_sentence)

@word_pronunciation_bp.route('/get-random-sentence', methods=['POST'])
@login_required
def get_random_sentence():
    """Get a new random sentence"""
    random_sentence = random.choice(TEST_SENTENCES)
    session['current_sentence'] = random_sentence
    
    return jsonify({'sentence': random_sentence})

@word_pronunciation_bp.route('/assess-pronunciation', methods=['POST'])
@login_required
def assess_pronunciation():
    """Assess user's pronunciation"""
    try:
        # Get the audio file from the request
        if 'audio' not in request.files:
            return jsonify({'error': 'Ses dosyası sağlanmadı'}), 400
        
        audio_file = request.files['audio']
        if audio_file.filename == '':
            return jsonify({'error': 'Ses dosyası seçilmedi'}), 400
        
        # Get the current sentence
        expected_sentence = session.get('current_sentence')
        if not expected_sentence:
            return jsonify({'error': 'Karşılaştırılacak cümle yok'}), 400
        
        # Read audio data
        audio_data = audio_file.read()
        print(f"Received audio file: {audio_file.filename}")
        print(f"Audio data size: {len(audio_data)} bytes")
        print(f"Audio content type: {audio_file.content_type}")
        
        # Transcribe the audio
        transcript = transcribe_audio(audio_data)
        print(f"Transcript result: '{transcript}'")
        
        # Calculate similarity score
        score_data = calculate_pronunciation_score(expected_sentence, transcript)
        
        # Determine accuracy level
        score = score_data['similarity_percentage']
        if score >= 90:
            accuracy_level = "Mükemmel"
            message = "🎉 Mükemmel! Harika telaffuz!"
        elif score >= 75:
            accuracy_level = "İyi"
            message = "👍 İyi iş! Böyle devam edin!"
        elif score >= 60:
            accuracy_level = "Orta"
            message = "👌 Fena değil. Daha net konuşmaya çalışın."
        else:
            accuracy_level = "Pratik gerekli"
            message = "💪 Pratik yapmaya devam edin! Daha iyi olacaksınız!"
        
        return jsonify({
            'transcript': transcript,
            'expected': expected_sentence,
            'score': score,
            'accuracy_level': accuracy_level,
            'message': message,
            'levenshtein_distance': score_data['levenshtein_distance']
        })
        
    except Exception as e:
        print(f"Error in assess_pronunciation: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Ses işleme hatası: {str(e)}'}), 500
