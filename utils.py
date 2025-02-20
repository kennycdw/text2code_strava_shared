import uuid
import pandas as pd

def custom_hash(id: str) -> str:
    """
    Generate a unique 10-character hash using UUID and custom base conversion
    """
    # Characters for base conversion (62 characters)
    CHARS = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    
    # Create a UUID using telegram_id as namespace
    namespace = uuid.NAMESPACE_URL
    unique_id = uuid.uuid5(namespace, str(id))
    
    # Convert UUID to integer
    uuid_int = int(unique_id.hex, 16)
    
    # Convert to base-62 string
    result = ""
    while uuid_int:
        uuid_int, remainder = divmod(uuid_int, 62)
        result = CHARS[remainder] + result
    
    # Pad with leading zeros if necessary
    result = result.zfill(10)
    
    return result[:10]

def format_week_year_to_readable_dates(row):
    """
    Format the start and end dates of a week given a year and week number
    """
    # Create a date from year and week number
    year = int(row['IsoYear'])
    week = int(row['Week'])
    start_date = pd.to_datetime(f"{year}-W{week:02d}-1", format='%G-W%V-%u')
    end_date = start_date + pd.Timedelta(days=6)
    
    # Format the dates
    return f"{start_date.strftime('%d %b')} - {end_date.strftime('%d %b %y')}"


def get_nested_value(data_dict, path):
   """
   Get a nested dictionary value using a path string like 'summary-total_activities'
   Returns None if path doesn't exist
   """
   try:
       # Split the path into parts
       keys = path.split('-')
       result = data_dict
       
       # Navigate through the nested dictionary
       for key in keys:
           result = result[key]
       
       return result
   except (KeyError, TypeError):
       return None