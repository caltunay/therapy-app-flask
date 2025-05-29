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
    
    def reset_password_for_email(self, email: str) -> dict:
        """Send password reset email"""
        try:
            # Get base URL from environment or default to 127.0.0.1
            base_url = os.getenv('BASE_URL', 'http://127.0.0.1:5000')
            response = self.supabase.auth.reset_password_for_email(
                email,
                {
                    "redirect_to": f"{base_url}/reset-password"
                }
            )
            return {"success": True, "data": response}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def update_password(self, access_token: str, refresh_token: str, new_password: str) -> dict:
        """Update user password"""
        try:
            print(f"DEBUG - Attempting to update password with access token: {access_token[:50]}...")
            print(f"DEBUG - Refresh token: {refresh_token}")
            
            # For password reset, we need to use both access token and refresh token
            self.supabase.auth.set_session(access_token, refresh_token)
            
            # Update the user's password
            response = self.supabase.auth.update_user({
                "password": new_password
            })
            
            print(f"DEBUG - Password update response: {response}")
            return {"success": True, "data": response}
        except Exception as e:
            print(f"DEBUG - Password update error: {str(e)}")
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
