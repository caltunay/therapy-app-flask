from flask import Flask, render_template, request, session, redirect, url_for, send_file, jsonify, Response, flash
import random
from dotenv import load_dotenv
import os 
from gtts import gTTS
from io import BytesIO

# Import the blueprints and services
from breathing import breathing_bp
from bosluk import bosluk_bp
from memory import memory_bp
from image_memory import image_memory_bp
from data_services import get_random_entry, get_image_url
from auth_service import auth_service, login_required

# load env variables
load_dotenv()

# start app
app = Flask(__name__)
app.secret_key = os.getenv('SESSION_SECRET_KEY')

# Register the breathing blueprint
app.register_blueprint(breathing_bp)
app.register_blueprint(bosluk_bp)
app.register_blueprint(memory_bp)
app.register_blueprint(image_memory_bp)

# Context processor to make environment variables available to all templates
@app.context_processor
def inject_config():
    return {
        'POSTHOG_PROJECT_KEY': os.getenv('POSTHOG_PROJECT_KEY')
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
        
        result = auth_service.update_password(access_token, refresh_token, new_password)
        
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
    return redirect(url_for('breathing_bp.start', **request.args))

@app.route('/', methods=['GET'])
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

    return render_template('index.html', image_url=image_url, censored=censored, revealed=len(session['revealed_indices']), tr_word=tr_word)

@app.route('/hint', methods=['POST'])
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

@app.route('/pronounce')
@login_required
def pronounce():
    tr_word = session.get('tr_word', '')
    if not tr_word:
        return ('', 404)
    tts = gTTS(text=tr_word, lang='tr', slow=True)
    mp3_fp = BytesIO()
    tts.write_to_fp(mp3_fp)
    mp3_fp.seek(0)
    return send_file(mp3_fp, mimetype='audio/mpeg')

@app.route('/guess', methods=['POST'])
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

if __name__ == "__main__":
    app.run(debug=True)