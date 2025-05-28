from supabase import create_client, Client
from dotenv import load_dotenv
import os
from flask import session
from functools import wraps

load_dotenv()

class AuthService:
    def __init__(self):
        self.url = os.getenv('SUPABASE_PROJECT_URL')
        self.key = os.getenv('SUPABASE_ANON_PUBLIC_KEY')
        self.supabase: Client = create_client(self.url, self.key)
    
    def sign_up(self, email: str, password: str) -> dict:
        """Sign up a new user"""
        try:
            response = self.supabase.auth.sign_up({
                "email": email,
                "password": password
            })
            return {"success": True, "data": response}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def sign_in(self, email: str, password: str) -> dict:
        """Sign in an existing user"""
        try:
            response = self.supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            return {"success": True, "data": response}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def sign_out(self) -> dict:
        """Sign out the current user"""
        try:
            response = self.supabase.auth.sign_out()
            return {"success": True, "data": response}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_user(self, access_token: str = None) -> dict:
        """Get current user info"""
        try:
            if access_token:
                self.supabase.auth.set_session(access_token, "")
            user = self.supabase.auth.get_user()
            return {"success": True, "user": user.user}
        except Exception as e:
            return {"success": False, "error": str(e)}

# Initialize auth service
auth_service = AuthService()

def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or 'access_token' not in session:
            from flask import redirect, url_for, request
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function
