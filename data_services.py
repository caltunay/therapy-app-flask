import os
import random
import requests
import boto3

# Get environment variables
SUPABASE_ANON_PUBLIC_KEY = os.getenv('SUPABASE_ANON_PUBLIC_KEY')
SUPABASE_PROJECT_URL = os.getenv('SUPABASE_PROJECT_URL')
SUPABASE_TABLE = 'speech-therapy-s3-keys'
SENTENCE_TABLE = 'sentence-list'

AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_REGION = os.getenv('AWS_REGION')
AWS_BUCKET = 'therapy-app-s3'

def get_random_entry():
    """Get a random entry from the Supabase database"""
    headers = {
        "apikey": SUPABASE_ANON_PUBLIC_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_PUBLIC_KEY}"
    }

    response = requests.get(
        f"{SUPABASE_PROJECT_URL}/rest/v1/{SUPABASE_TABLE}?select=s3_key,eng_word,tr_word&is_confirmed=eq.true",
        headers=headers
    )

    if response.status_code != 200:
        return None

    data = response.json()
    if not data:
        return None

    return random.choice(data)

def get_random_sentence(difficulty=None, apply_filter=True):
    """Get a random sentence from the sentence-list table without filtering by difficulty
    
    Args:
        difficulty (str, optional): The difficulty level. Defaults to None.
        apply_filter (bool, optional): Whether to apply the difficulty filter. Defaults to True.
    """
    headers = {
        "apikey": SUPABASE_ANON_PUBLIC_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_PUBLIC_KEY}"
    }
    
    url = f"{SUPABASE_PROJECT_URL}/rest/v1/{SENTENCE_TABLE}?select=sentence,ease_degree"
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return None
    data = response.json()
    if not data:
        return None
    return random.choice(data)

def get_image_url(s3_key):
    """Generate a presigned URL for the S3 object"""
    s3 = boto3.client('s3',
                    region_name=AWS_REGION,
                    aws_access_key_id=AWS_ACCESS_KEY,
                    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
    )
     
    url = s3.generate_presigned_url('get_object',
                                    Params={'Bucket': AWS_BUCKET, 'Key':s3_key},
                                    ExpiresIn=3600
    )

    return url