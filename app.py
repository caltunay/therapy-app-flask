from flask import Flask
import random
import requests
from dotenv import load_dotenv
import os 

# load env variables
load_dotenv()

# get key from env
UNSPLASH_ACCESS_KEY = os.getenv('UNSPLASH_ACCESS_KEY') 

# start app
app = Flask(__name__)

# get words
def load_words(filepath='word_list.txt'):
    """load words from list, one word per line"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            words = f.read().splitlines()
        # filter out if word is blank
        words = [word for word in words if word]
        if not words:
            print(f"error: {filepath} is empty or is whitespace-only")
            return []
        return words
    except FileNotFoundError:
        print(f"error: {filepath} not found. please get file first.")
        return []
    
# fetch image from unsplash given the random word selected
def get_unsplash_image(word):
    # fetch image for given word from unsplash
    if not UNSPLASH_ACCESS_KEY:
        return "UNSPLASH API KEY MISSING"
    
    url = f"https://api.unsplash.com/search/photos?query={word}&client_id={UNSPLASH_ACCESS_KEY}"
    
    try:
        response = requests.get(url)
        response.raise_for_status() # check http errs
        data = response.json()

        if data.get('results'):
            image_url = data['results'][0]['urls']['small']
            return image_url
        else:
            return "no image found in unsplash"
    except:
        print('unsplash couldnt try requests')

# load words once app starts
WORD_LIST = load_words()

# homepage shit
@app.route('/')
def home():
    welcome_message = 'aphasia therapy app in turkish'
    if not WORD_LIST:
        random_word_message = "couldn't load words list"

    chosen_word = random.choice(WORD_LIST)
    image_url_or_message = get_unsplash_image(chosen_word)

    output_text = f"chosen word: {chosen_word}\n image URL: {image_url_or_message}"
    html_output = f"<img src='{image_url_or_message}' alt='Image for {chosen_word}' width='300'>"

    return html_output # f"<pre>{output_text}</pre>"

# run app
if __name__ == '__main__':
    app.run(debug=True)
