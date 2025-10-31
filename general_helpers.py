import configparser
import requests
import json

# Papertrail login details
papertrail_log_token = ""

# Ziflow webhook URL
config = configparser.ConfigParser()
config.read("segredo.ini")


def fnLogToPapertrail(oStamp, sMessage):
    """
    Logs a message. 
    If papertrail_log_token in segredo.ini is a valid URL, it sends it there.
    Otherwise, it just prints to the console.
    """
    global papertrail_log_token
    try:
        # Try to read the token if it's not already set
        if not papertrail_log_token:
            try:
                papertrail_log_token = config.get("PaperTrail", "papertrail_log_token")
            except (configparser.NoSectionError, configparser.NoOptionError):
                papertrail_log_token = "" # Set to empty if not found

        #
        # >>> MODIFIED: Check if the token is a valid URL before using it <<<
        #
        if papertrail_log_token and papertrail_log_token.startswith("http"):
            # If it looks like a URL, try to post to it
            oPayload = {
                "cardid": oStamp["cardid"],
                "timestamp": oStamp["time"],
                "message": sMessage,
            }
            requests.post(papertrail_log_token, json=oPayload, timeout=3)
        else:
            # Otherwise, just print to the console
            print(f"LOG: [{oStamp.get('cardid', 'SYSTEM')}] {sMessage}")
        
        return "success", 200
        
    except Exception as e:
        # If anything fails (like a timeout), just print
        print(f"LOG: [{oStamp.get('cardid', 'SYSTEM')}] {sMessage}")
        print(f"Papertrail Error: {e}")
        return str(e), 106


def send_ziflow_obj(card_data, job_number, upload_type, oStamp, agency_name, client_name):
    """
    Sends data to the Ziflow webhook (Workato/Zapier)
    to create a proof and folder structure.
    
    UPDATED: Now matches old payload structure but works with V2 multi-agency system.
    """
    try:
        try:
            ziflow_webhook_url = config.get("Ziflow", "ziflow_webhook_url")
            if not ziflow_webhook_url:
                raise configparser.NoOptionError("ziflow_webhook_url", "Ziflow")
                
        except (configparser.NoSectionError, configparser.NoOptionError):
            message = "Ziflow integration skipped: 'ziflow_webhook_url' not set in segredo.ini"
            fnLogToPapertrail(oStamp, message) # Log the skip
            return message, 106

        # Build the Ziflow object matching the OLD structure
        ziflow_obj = {
            "data": {
                "action": "card.create_ziflow_folder_structure",
                "on_phase": {
                    "id": card_data.get("current_phase_object", {}).get("id"),
                    "name": card_data.get("current_phase_object", {}).get("name"),
                },
                "created_by": {
                    "id": 120,
                    "name": "Pipebot",
                    "username": "pipebot",
                    "email": "pipebot@pipefy.com",
                    "avatar_url": "https://gravatar.com/avatar/18df131953ca09a802848bf3f8dbf83b.png?s=144&d=https://pipestyle.staticpipefy.com/v2-temp/illustrations/avatar.png"
                },
                "card": {
                    "id": oStamp.get("cardid"),
                    "title": card_data.get("card_title"),
                    "pipe_object": {
                        "id": card_data.get("pipe_object", {}).get("id"),
                        "name": card_data.get("pipe_object", {}).get("name"),
                    },
                    # >>> NEW V2 FIELD: Agency Name <<<
                    "agency_name": agency_name,
                    
                    # >>> UPDATED: Client name from database or V1 field <<<
                    "client_name": client_name,
                    
                    # >>> REST OF FIELDS (same as old structure) <<<
                    "campaign_year": card_data.get("campaign_year"),
                    "campaign_quarter": card_data.get("campaign_quarter"),
                    "job_number": job_number,
                    "campaign_name": card_data.get("campaign_name"),
                    
                    # client_division is kept for backwards compatibility
                    "client_division": card_data.get("client_division"),
                    
                    "dev_messages_obj": {
                        "field_id": "dev_message",
                        "field_value": card_data.get("dev_messages_obj")
                    },
                    "review_card": card_data.get("review_card"),
                    "ziflow_folder_id": card_data.get("ziflow_folder_id"),
                    "parent_ziflow_folder_id": card_data.get("parent_ziflow_folder_id"),
                    "work_type": card_data.get("work_type"),
                }
            }
        }
        
        # Remove None values to keep payload clean
        def remove_none_values(d):
            """Recursively remove None values from nested dictionaries"""
            if not isinstance(d, dict):
                return d
            return {k: remove_none_values(v) for k, v in d.items() if v is not None}
        
        ziflow_obj = remove_none_values(ziflow_obj)
        
        # Log what we're sending
        fnLogToPapertrail(
            oStamp, 
            f"Sending to Ziflow: agency='{agency_name}', client='{client_name}', job={job_number}"
        )
        
        response = requests.post(ziflow_webhook_url, json=ziflow_obj, timeout=20)
        
        if response.status_code == 200:
            return response.json(), 200
        else:
            return response.text, response.status_code
            
    except Exception as e:
        return str(e), 106