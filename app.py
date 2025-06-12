from flask import Flask, render_template, request, session, redirect, url_for, send_file, jsonify, Response, flash
import random
from dotenv import load_dotenv
import os 
from gtts import gTTS
from io import BytesIO
from Levenshtein import distance as levenshtein_distance

# Import the blueprints and services
from breathing import breathing_bp
from bosluk import bosluk_bp
from memory import memory_bp
from image_memory import image_memory_bp
from word_pronunciation import word_pronunciation_bp
from pronunciation_game import pronunciation_game_bp
from word_guessing import word_guessing_bp
from reverse_dictionary import reverse_dictionary_bp
from data_services import get_random_entry, get_image_url
from auth_service import auth_service, login_required
from analytics_session_duration import get_user_session_analytics

# load env variables
load_dotenv()

# start app
app = Flask(__name__)
app.secret_key = os.getenv('SESSION_SECRET_KEY')

# Register the blueprints
app.register_blueprint(breathing_bp)
app.register_blueprint(bosluk_bp)
app.register_blueprint(memory_bp)
app.register_blueprint(image_memory_bp)
app.register_blueprint(word_pronunciation_bp)
app.register_blueprint(pronunciation_game_bp)
app.register_blueprint(word_guessing_bp)
app.register_blueprint(reverse_dictionary_bp)

# Context processor to make environment variables available to all templates
@app.context_processor
def inject_config():
    user_email = session.get('user_email')
    should_identify_new_login = session.pop('posthog_identify', False)
    should_reset = session.pop('posthog_reset', False)
    
    # Always identify if user is logged in (either new login or existing session)
    should_identify = should_identify_new_login or bool(user_email)
    
    return {
        'POSTHOG_PROJECT_KEY': os.getenv('POSTHOG_PROJECT_KEY'),
        'user_email': user_email,
        'should_identify': should_identify,
        'should_reset': should_reset
    }

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not email or not password:
            flash('E-posta ve şifre gereklidir.', 'error')
            return render_template('login.html', error='E-posta ve şifre gereklidir.')
        
        result = auth_service.sign_in(email, password)
        
        if result['success']:
            # Store user info in session
            user_data = result['data']
            session['user_id'] = user_data.user.id
            session['access_token'] = user_data.session.access_token
            session['user_email'] = user_data.user.email
            session['posthog_identify'] = True  # Flag to trigger PostHog identify
            
            # Redirect to original page or home
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            error_msg = result['error']
            if 'Invalid login credentials' in error_msg:
                error_msg = 'Geçersiz e-posta veya şifre.'
            return render_template('login.html', error=error_msg)
    
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not email or not password or not confirm_password:
            return render_template('signup.html', error='Tüm alanlar gereklidir.')
        
        if password != confirm_password:
            return render_template('signup.html', error='Şifreler eşleşmiyor.')
        
        if len(password) < 6:
            return render_template('signup.html', error='Şifre en az 6 karakter olmalıdır.')
        
        result = auth_service.sign_up(email, password)
        
        if result['success']:
            return render_template('signup.html', 
                                success='Kayıt başarılı! E-postanızı kontrol ederek hesabınızı onaylayın, sonra giriş yapabilirsiniz.')
        else:
            error_msg = result['error']
            if 'User already registered' in error_msg:
                error_msg = 'Bu e-posta adresi zaten kayıtlı.'
            elif 'Password should be at least 6 characters' in error_msg:
                error_msg = 'Şifre en az 6 karakter olmalıdır.'
            return render_template('signup.html', error=error_msg)
    
    return render_template('signup.html')

@app.route('/logout')
@login_required
def logout():
    auth_service.sign_out()
    session['posthog_reset'] = True  # Flag to trigger PostHog reset
    session.clear()
    flash('Başarıyla çıkış yaptınız.', 'success')
    return redirect(url_for('login'))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        
        if not email:
            return render_template('forgot_password.html', error='E-posta adresi gereklidir.')
        
        result = auth_service.reset_password_for_email(email)
        
        if result['success']:
            return render_template('forgot_password.html', 
                                success='Şifre sıfırlama e-postası gönderildi! E-postanızı kontrol edin.')
        else:
            return render_template('forgot_password.html', 
                                error='E-posta gönderilirken bir hata oluştu.')
    
    return render_template('forgot_password.html')

@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        access_token = request.form.get('access_token')
        refresh_token = request.form.get('refresh_token')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # Debug: Print what we received
        print(f"DEBUG - access_token: {access_token}")
        print(f"DEBUG - refresh_token: {refresh_token}")
        print(f"DEBUG - new_password present: {bool(new_password)}")
        print(f"DEBUG - confirm_password present: {bool(confirm_password)}")
        
        if not access_token or not new_password or not confirm_password:
            error_msg = 'Tüm alanlar gereklidir.'
            if not access_token:
                error_msg = 'Geçersiz erişim bağlantısı. Lütfen e-postanızdaki bağlantıyı tekrar kullanın.'
            return render_template('reset_password.html', error=error_msg, access_token=access_token, refresh_token=refresh_token)
        
        if new_password != confirm_password:
            return render_template('reset_password.html', error='Şifreler eşleşmiyor.', access_token=access_token, refresh_token=refresh_token)
        
        if len(new_password) < 6:
            return render_template('reset_password.html', error='Şifre en az 6 karakter olmalıdır.', access_token=access_token, refresh_token=refresh_token)
        
        result = auth_service.update_password(access_token, refresh_token or '', new_password)
        
        if result['success']:
            return render_template('reset_password.html', 
                                success='Şifreniz başarıyla güncellendi! Giriş yapabilirsiniz.')
        else:
            return render_template('reset_password.html', 
                                error='Şifre güncellenirken bir hata oluştu.', access_token=access_token, refresh_token=refresh_token)
    
    # Get tokens from URL query parameters 
    access_token = request.args.get('access_token', '')
    refresh_token = request.args.get('refresh_token', '')
    
    return render_template('reset_password.html', 
                         access_token=access_token, 
                         refresh_token=refresh_token)

@app.route('/breathing')
@login_required
def breathing_redirect():
    return redirect(url_for('breathing_bp.index'))

@app.route('/breathing/start')
@login_required
def breathing_start_redirect():
    # Forward any query parameters
    return redirect(url_for('breathing_bp.start') + '?' + request.query_string.decode())

@app.route('/', methods=['GET'])
@login_required
def index():
    """Homepage with game menu"""
    user_email = session.get('user_email')
    analytics_data = None
    
    if user_email:
        analytics_data = get_user_session_analytics(user_email)
    
    return render_template('index.html', analytics_data=analytics_data)

if __name__ == "__main__":
    app.run(debug=True, port=5001)