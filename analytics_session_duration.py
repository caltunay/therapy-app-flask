import requests
import json
import os
from dotenv import load_dotenv
import pandas as pd
from datetime import datetime, timedelta

load_dotenv()

POSTHOG_QUERY_API_KEY = os.getenv('POSTHOG_QUERY_API_KEY') 
POSTHOG_PROJECT_ID = os.getenv('POSTHOG_PROJECT_ID') 

def get_user_session_analytics(user_email):
    """Fetch session duration analytics for a specific user"""
    if not user_email or not POSTHOG_QUERY_API_KEY or not POSTHOG_PROJECT_ID:
        return None
    
    url = f"https://eu.posthog.com/api/projects/{POSTHOG_PROJECT_ID}/query/"

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {POSTHOG_QUERY_API_KEY}'
    }

    query_string = f"""
    SELECT 
        distinct_sessions.email,
        formatDateTime(sessions.`$start_timestamp`, '%d-%m-%Y') AS day,
        round(sum(sessions.`$session_duration`)/60) AS total_session_time_minutes
    FROM 
        sessions
    INNER JOIN (
        SELECT DISTINCT 
            properties.`$session_id` AS session_id,
            person.properties.email AS email
        FROM events 
        WHERE person.properties.email = \'{user_email}\'
    ) AS distinct_sessions
    ON sessions.session_id = distinct_sessions.session_id
    GROUP BY 
        distinct_sessions.email, day
    ORDER BY 
        day ASC
    """

    payload = {
        "query": {
            "kind": "HogQLQuery",
            "query": query_string
        }
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        
        data = response.json()
        
        # Extract results and column names
        rows = data.get('results', [])
        columns = data.get('columns', [])
        
        if rows and columns:
            # Create DataFrame
            df = pd.DataFrame(rows, columns=columns)
            analytics_data = df.to_dict('records')
            
            # Fill missing dates with 0 session duration
            if analytics_data:
                # Parse dates and find date range
                dates = [datetime.strptime(record['day'], '%d-%m-%Y') for record in analytics_data]
                min_date = min(dates)
                max_date = max(dates)
                
                # Create complete date range including today
                today = datetime.now()
                if today > max_date:
                    max_date = today
                
                # Generate all dates in range
                current_date = min_date
                all_dates = []
                while current_date <= max_date:
                    all_dates.append(current_date)
                    current_date += timedelta(days=1)
                
                # Convert existing data to a dictionary for quick lookup
                existing_data = {record['day']: record for record in analytics_data}
                
                # Create complete dataset with missing dates filled as 0
                complete_data = []
                for date in all_dates:
                    date_str = date.strftime('%d-%m-%Y')
                    if date_str in existing_data:
                        complete_data.append(existing_data[date_str])
                    else:
                        complete_data.append({
                            'email': user_email,
                            'day': date_str,
                            'total_session_time_minutes': 0
                        })
                
                return complete_data
            else:
                return []
        else:
            return []
            
    except Exception as e:
        print(f"Error fetching analytics: {e}")
        return None

# Keep original code for backward compatibility
EMAIL = "<user_email>"  # This will be replaced by the function parameter

url = f"https://eu.posthog.com/api/projects/{POSTHOG_PROJECT_ID}/query/"

headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {POSTHOG_QUERY_API_KEY}'
}

query_string = f"""
SELECT 
    distinct_sessions.email,
    formatDateTime(sessions.`$start_timestamp`, '%d-%M-%Y') AS day,
    round(sum(sessions.`$session_duration`)/60) AS total_session_time_minutes
FROM 
    sessions
INNER JOIN (
    SELECT DISTINCT 
        properties.`$session_id` AS session_id,
        person.properties.email AS email
    FROM events 
    WHERE person.properties.email = \'{EMAIL}\'
) AS distinct_sessions
ON sessions.session_id = distinct_sessions.session_id
GROUP BY 
    distinct_sessions.email, day
ORDER BY 
    day ASC
"""

payload = {
    "query": {
        "kind": "HogQLQuery",
        "query": query_string
    }
}

response = requests.post(url, headers=headers, data=json.dumps(payload))

data = response.json()

# Extract results and column names
rows = data['results']
columns = data['columns']

# Create DataFrame
df = pd.DataFrame(rows, columns=columns)

print(df)