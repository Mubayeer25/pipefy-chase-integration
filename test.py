"""
Script to find the correct Pipefy field IDs for Job Number and Chase Links.
Run this to see all available fields on your card.
"""

import configparser
from pipefy_helpers import Pipefy

# Load config
config = configparser.ConfigParser()
config.read("segredo.ini")

pipefy_api_token = config.get("Pipefy", "pipefy_api_token")
pipefy_api_url = config.get("Pipefy", "pipefy_api_url")

pipefy = Pipefy(pipefy_api_url, pipefy_api_token)

# Get card details
card_id = "1247402269"  # Your test card
card_data, message, status_code = pipefy.get_card_details(card_id)

if status_code != 200:
    print(f"Error getting card: {message}")
    exit(1)

print("\n" + "="*80)
print("SEARCHING FOR JOB NUMBER AND CHASE LINK FIELDS")
print("="*80 + "\n")

# Search for fields that might be job number or links
target_keywords = ["job", "number", "chase", "timesheet", "link"]

print("Fields that might be relevant:\n")

for field_obj in card_data.get("fields", []):
    field_id = field_obj.get("field", {}).get("id", "")
    field_name = field_obj.get("name", "").lower()
    field_value = field_obj.get("value", "")
    
    # Check if this field matches our keywords
    if any(keyword in field_name for keyword in target_keywords):
        print(f"Field ID: '{field_id}'")
        print(f"Field Name: '{field_obj.get('name')}'")
        print(f"Current Value: {field_value[:100] if field_value else '(empty)'}")
        print("-" * 80 + "\n")

print("\n" + "="*80)
print("INSTRUCTIONS:")
print("="*80)
print("Look for these field IDs in the output above:")
print("1. A field called 'Job number' or similar")
print("2. A field called 'Link to Chase' or 'Chase link'")
print("3. A field called 'Link to timesheets' or 'Timesheet link'")
print("\nThen update pipefy_helpers.py in the get_card_details() function")
print("to use the correct field IDs.")
print("="*80 + "\n")