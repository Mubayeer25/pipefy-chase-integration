import configparser
import json
import sys
import re
import time
from datetime import datetime

import pytz
import uvicorn
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware

import chase_helpers
import general_helpers
from pipefy_helpers import Pipefy

# Load configuration from the file
config = configparser.ConfigParser()
config.read("segredo.ini")

# --- Config loading ---
chase_username_live = config.get("Chase", "CHASE_USERNAME_LIVE")
chase_password_live = config.get("Chase", "CHASE_PASSWORD_LIVE")
chase_url_live = config.get("Chase", "CHASE_URL_LIVE")
chase_username_qa = config.get("Chase", "CHASE_USERNAME_QA")
chase_password_qa = config.get("Chase", "CHASE_PASSWORD_QA")
chase_url_qa = config.get("Chase", "CHASE_URL_QA")
pipefy_api_token = config.get("Pipefy", "pipefy_api_token")
pipefy_api_url = config.get("Pipefy", "pipefy_api_url")
general_helpers.papertrail_log_token = config.get("PaperTrail", "papertrail_log_token")

# Create a Pipefy object
pipefy = Pipefy(pipefy_api_url, pipefy_api_token)
tz = pytz.timezone("Africa/Johannesburg")
app = FastAPI()

# --- Middleware (unchanged) ---
class LogRequestsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = datetime.now()
        body = await request.body()
        log_message = f"Request: {request.method} {request.url} - Body: {body.decode()}"
        oStamp = {"cardid": "Middleware", "time": datetime.now(tz).strftime("%Y:%m:%d %H:%M:%S")}
        general_helpers.fnLogToPapertrail(oStamp, log_message)
        response = await call_next(request)
        log_message = f"Response: {response.status_code} - Time: {datetime.now() - start_time}"
        general_helpers.fnLogToPapertrail(oStamp, log_message)
        return response

app.add_middleware(LogRequestsMiddleware)

# --- Helper to set QA/Live state ---
def set_test_state(card_data):
    """Sets the global test_state in chase_helpers based on card labels."""
    if "QA" in card_data.get("labels", []):
        chase_helpers.test_state = True
        return True
    else:
        chase_helpers.test_state = False
        return False

#
# --- Main Endpoint: V1/V2 Router ---
#
@app.post("/started_processing")
async def started_processing(request: Request):
    """
    Main webhook entry point.
    Fetches card details and routes to V1 or V2 creation logic.
    """
    try:
        data = await request.json()
        card_id = data["data"]["card"]["id"]
        oStamp = {"cardid": card_id, "time": datetime.now(tz).strftime("%Y:%m:%d %H:%M:%S")}
        
        resp_obj, status_code = general_helpers.fnLogToPapertrail(oStamp, "Started Processing...")
        
        card_data, message, status_code = pipefy.get_card_details(card_id)
        if status_code != 200:
            raise KeyError(f"Failed to get card details: {message}")
            
        set_test_state(card_data)
        env_info = chase_helpers.get_current_environment_info()
        general_helpers.fnLogToPapertrail(oStamp, f"Environment set: {env_info}")

        # --- V1/V2 ROUTER LOGIC ---
        master_record_id = card_data.get("chase_master_data_record_id")
        config_id_field = card_data.get("config_id_from_card")

        if master_record_id or config_id_field:
            message = (
                f"V2 card detected (Record ID: {master_record_id}, "
                f"Config ID Field: {config_id_field}). Running new Chase creation."
            )
            general_helpers.fnLogToPapertrail(oStamp, message)
            await chase_creation_v2(card_data, card_id, oStamp)
        else:
            message = f"V1 card detected (No DB Record ID or V2 fields). Running legacy Chase creation."
            general_helpers.fnLogToPapertrail(oStamp, message)
            await chase_creation_v1(card_data, card_id, oStamp)

        return "success", 200
        
    except Exception as e:
        exc_tb = sys.exc_info()[2]
        line_number = exc_tb.tb_lineno
        message = f"error in started_processing, error: {e}, line: {line_number}"
        try:
            oStamp = {"cardid": data["data"]["card"]["id"], "time": datetime.now(tz).strftime("%Y:%m:%d %H:%M:%S")}
            general_helpers.fnLogToPapertrail(oStamp, message)
        except:
            print(message)
        return message, 106

#
# --- V1: Legacy Chase Creation (Refactored to use V2 logic) ---
#
async def chase_creation_v1(card_data, card_id, oStamp):
    """
    Handles the original (V1) Chase job creation logic.
    REFFACTORED to use V2 functions (populate_mandatory_fields_immediately)
    to avoid broken /api/Job/Save endpoint.
    """
    try:
        # --- Pre-flight checks ---
        if card_data.get("new_job_required") == "no":
            message = "New job not required. Skipping Chase creation."
            general_helpers.fnLogToPapertrail(oStamp, message)
            return message, 200
        if card_data.get("job_number"):
            message = f"Job number {card_data.get('job_number')} already exists. Skipping Chase creation."
            general_helpers.fnLogToPapertrail(oStamp, message)
            return message, 200

        general_helpers.fnLogToPapertrail(oStamp, "V1: Creating job bag...")
        
        # --- V1 LOGIC: Hardcode ConfigID="1" and BU_ID=11 ---
        CONFIG_ID_V1 = "1"
        BU_ID_V1 = 11

        # --- VALIDATION: Check required V1 fields ---
        client_name = card_data.get("client_name")
        if not client_name:
            error_msg = "VALIDATION ERROR: 'client_name' field is missing."
            general_helpers.fnLogToPapertrail(oStamp, error_msg)
            pipefy.update_card_field(card_id, "dev_message", error_msg)
            return error_msg, 400

        product_name = card_data.get("product")
        if not product_name:
            error_msg = "VALIDATION ERROR: 'product' field is missing."
            general_helpers.fnLogToPapertrail(oStamp, error_msg)
            pipefy.update_card_field(card_id, "dev_message", error_msg)
            return error_msg, 400
        
        # --- Get V1 Chase IDs ---
        client_id, error_message, status_code = chase_helpers.get_client_id(CONFIG_ID_V1, client_name)
        if status_code != 200: 
            raise KeyError(f"Error getting client id: {error_message}")

        product, error_message, status_code = chase_helpers.get_product_id(CONFIG_ID_V1, product_name, client_id)
        if status_code != 200: 
            raise KeyError(f"Error getting product id: {error_message}")
        product_id = product.get("product_id")
        
        category_id, error_message, status_code = chase_helpers.get_job_category_id(
            CONFIG_ID_V1, card_data.get("brief_type"), card_data.get("element"),
            card_data.get("other_element"), card_data["pipe_object"].get("name"),
            card_data.get("selected_channel"), card_data.get("selected_retail_element"),
        )
        if status_code != 200: 
            raise KeyError(f"Error getting job category id: {error_message}")

        element = card_data.get("element") or card_data.get("other_element")

                # --- Dynamically build the Chase Element field ---
        campaign_year = card_data.get("campaign_year", "")
        job_name = card_data.get("job_name", "")
        campaign_name = card_data.get("campaign_name", "")

        # Filter out None or empty strings and join with '-'
        chase_element_parts = [part for part in [campaign_year, job_name, campaign_name] if part]
        chase_element_string = "-".join(chase_element_parts)

        if not chase_element_string:
            chase_element_string = "Job from Pipefy" # Fallback

        general_helpers.fnLogToPapertrail(oStamp, f"Constructed Chase Element: '{chase_element_string}'")

        # --- Create Job Bag ---
        job_bag_id, error_message, status_code = chase_helpers.create_job_bag(
            CONFIG_ID_V1, client_id, product_id, category_id, card_data, chase_element_string
        )
        
        if status_code != 200: 
            raise KeyError(f"Error creating job bag: {error_message}")
        general_helpers.fnLogToPapertrail(oStamp, f"✓ Job bag {job_bag_id} created. Populating mandatory fields...")

        # --- Get Client Contact (V1) ---
        client_contact_name = card_data.get("client_contact")
        client_contact_id = 0
        if client_contact_name:
            client_contact_id, _, error_message = chase_helpers.get_client_contact(CONFIG_ID_V1, client_contact_name)
            if client_contact_id == 0: 
                general_helpers.fnLogToPapertrail(oStamp, f"Warning: Could not find client contact '{client_contact_name}'. Error: {error_message}")

        # --- USE THE V2 FUNCTION TO POPULATE FIELDS ---
        populate_result, error_message, status_code = chase_helpers.populate_mandatory_fields_immediately(
            CONFIG_ID_V1, job_bag_id, card_data, client_contact_id, BU_ID_V1, oStamp,
            category_id=category_id    
        )
        
        if status_code != 200:
            raise KeyError(f"Error populating mandatory fields: {error_message}")
        
        general_helpers.fnLogToPapertrail(oStamp, f"✓ Mandatory fields populated. Retrieving job...")

        # --- USE V2 RETRIEVAL LOGIC ---
        time.sleep(2)
        job_bag_obj, error_message, status_code = chase_helpers.get_job_by_id(
            CONFIG_ID_V1, job_bag_id
        )
        
        job_number = None
        if status_code == 404 or (status_code == 200 and not job_bag_obj):
            general_helpers.fnLogToPapertrail(oStamp, f"Warning: Job {job_bag_id} not immediately retrievable. Using JobID as JobNo.")
            job_number = job_bag_id
        else:
            if isinstance(job_bag_obj, list): job_bag_obj = job_bag_obj[0] if len(job_bag_obj) > 0 else {}
            if not job_bag_obj:
                job_number = job_bag_id
            else:
                job_number = job_bag_obj.get("JobNo") or job_bag_id
        
        card_data["job_number"] = job_number
        general_helpers.fnLogToPapertrail(oStamp, f"✓ Job bag retrieved. Job Number: {job_number}")

        # --- Update Pipefy IMMEDIATELY (FIX #1) ---
        goto_url = f"{chase_helpers.get_chase_url()}/Goto.ashx?c={CONFIG_ID_V1}&f=2&i={job_bag_id}"
        pipefy.update_pipefy_fields(card_id, job_number, job_bag_id, goto_url, card_data)
        general_helpers.fnLogToPapertrail(oStamp, f"✓ Pipefy fields updated with job number {job_number}")

        # --- V1 Ziflow Call ---
        selected_client_name = card_data.get("client_name")
        selected_division = card_data.get("client_division")
        card_data["client_division"] = selected_division if selected_division else "N/A"

        general_helpers.fnLogToPapertrail(
            oStamp, 
            f"Sending to Ziflow: agency='N/A (V1)', client='{selected_client_name}', division='{card_data['client_division']}', job={job_number}"
        )

        ziflow_obj, status_code = general_helpers.send_ziflow_obj(
            card_data, job_number, "card", oStamp,
            agency_name=None,
            client_name=selected_client_name
        )
        if status_code == 200:
            general_helpers.fnLogToPapertrail(oStamp, f"Ziflow folder structure created. {ziflow_obj}")
            #ziflow_folder_id = ziflow_obj.get("ziflow_folder_id", "")
            #pipefy.update_card_field(card_id, "ziflow_folder_id", ziflow_folder_id)
        else:
            general_helpers.fnLogToPapertrail(oStamp, f"Ziflow error: {ziflow_obj}")

        # --- Move Card to Phase ---
        phase_id = pipefy.get_phases(card_data["pipe_object"].get("id"))
        if phase_id: 
            pipefy.move_card_to_phase(card_id, phase_id)
        
        general_helpers.fnLogToPapertrail(oStamp, f"Job {job_number} created successfully.")
        return "success", 200

    except Exception as e:
        exc_tb = sys.exc_info()[2]
        line_number = exc_tb.tb_lineno
        message = f"error in chase_creation_v1, error: {e}, line: {line_number}"
        general_helpers.fnLogToPapertrail(oStamp, message)
        pipefy.update_card_field(card_id, "dev_message", message)
        return message, 106

#
# --- V2: New Chase Creation ---
#
async def chase_creation_v2(card_data, card_id, oStamp):
    """Handles the new (V2) Chase job creation logic."""
    try:
        # --- Pre-flight checks ---
        if card_data.get("new_job_required") == "no":
            message = "New job not required. Skipping Chase creation."
            general_helpers.fnLogToPapertrail(oStamp, message)
            return message, 200
        if card_data.get("job_number"):
            message = f"Job number {card_data.get('job_number')} already exists. Skipping Chase creation."
            general_helpers.fnLogToPapertrail(oStamp, message)
            return message, 200

        general_helpers.fnLogToPapertrail(oStamp, "V2: Creating job bag...")

        # 1. Get Record ID from card
        record_id = card_data.get("chase_master_data_record_id")
        general_helpers.fnLogToPapertrail(oStamp, f"V2 card identified via DB record {record_id}.")

        # 2. Get all IDs from helper fields
        selected_config_id = card_data.get("config_id_from_card")
        selected_client_id = card_data.get("client_id_from_card")
        selected_product_id = card_data.get("product_id_from_card")
        selected_bu_id = card_data.get("business_unit_id_from_card")
        
        if not selected_bu_id:
            selected_bu_id = card_data.get("business_unit_id")
            
        # 3. Get names for Ziflow
        selected_agency_name = card_data.get("agency_name")
        
        # 4. Validation
        missing_fields = []
        if not selected_config_id:
            missing_fields.append("config_id (helper field on card)")
        if not selected_client_id:
            missing_fields.append("client_id (helper field on card)")
        if not selected_product_id:
            missing_fields.append("product_id (helper field on card)")
        if not selected_bu_id:
            missing_fields.append("business_unit_id (helper field on card)")
        
        if missing_fields:
            error_msg = (
                f"Card {card_id} is missing required V2 helper fields: {', '.join(missing_fields)}. "
                f"Please ensure the Pipefy automation is correctly populating these fields "
                f"after the 'product_record_id' is selected."
            )
            raise KeyError(error_msg)

        general_helpers.fnLogToPapertrail(
            oStamp, 
            f"Data from card fields: ConfigID={selected_config_id}, BU={selected_bu_id}, "
            f"Client={selected_client_id}, Product={selected_product_id}"
        )

        # 5. Find the correct V2 element based on brief_type
        brief_type = card_data.get("brief_type")
        selected_element = None
        if brief_type == "ATL":
            selected_element = card_data.get("atl_element")
        elif brief_type == "BTL":
            selected_element = card_data.get("btl_element")
        elif brief_type == "Digital":
            selected_element = card_data.get("digital_element")
        elif brief_type == "Social":
            selected_element = card_data.get("social_element")
        elif brief_type == "Design":
            selected_element = card_data.get("design_element")
        elif brief_type == "Internal":
            selected_element = card_data.get("internal_marketing_element")
        
        if not selected_element:
            selected_element = card_data.get("element") or card_data.get("other_element")
        
        general_helpers.fnLogToPapertrail(oStamp, f"Brief Type: '{brief_type}'. Selected Element: '{selected_element}'")

        # 6. Get Job Category ID
        category_id, error_message, status_code = chase_helpers.get_job_category_id(
            selected_config_id, 
            brief_type, 
            selected_element,
            card_data.get("other_element"), 
            card_data["pipe_object"].get("name"),
            card_data.get("selected_channel"), 
            card_data.get("selected_retail_element"),
        )
        if status_code != 200: 
            raise KeyError(f"Error getting job category id: {error_message}")
        
        general_helpers.fnLogToPapertrail(oStamp, f"Found Category ID: '{category_id}'")

        # --- Dynamically build the Chase Element field ---
        campaign_year = card_data.get("campaign_year", "")
        job_name = card_data.get("job_name", "")
        campaign_name = card_data.get("campaign_name", "")

        # Filter out None or empty strings and join with '-'
        chase_element_parts = [part for part in [campaign_year, job_name, campaign_name] if part]
        chase_element_string = "-".join(chase_element_parts)

        if not chase_element_string:
            chase_element_string = "Job from Pipefy" # Fallback

        general_helpers.fnLogToPapertrail(oStamp, f"Constructed Chase Element: '{chase_element_string}'")

        # 7. Create Job Bag
        job_bag_id, error_message, status_code = chase_helpers.create_job_bag(
            selected_config_id, selected_client_id, selected_product_id, category_id, card_data, chase_element_string
        )

        if status_code != 200: 
            raise KeyError(f"Error creating job bag: {error_message}")
        
        general_helpers.fnLogToPapertrail(
            oStamp, 
            f"✓ Job bag {job_bag_id} created. Populating mandatory fields immediately..."
        )

        # 8. Get Client Contact BEFORE populating fields
        client_contact_name = card_data.get("client_contact")
        client_contact_id = 0
        if client_contact_name:
            client_contact_id, _, error_message = chase_helpers.get_client_contact(
                selected_config_id, client_contact_name
            )
            if client_contact_id == 0: 
                general_helpers.fnLogToPapertrail(
                    oStamp, 
                    f"Warning: Could not find client contact '{client_contact_name}'. Error: {error_message}"
                )

        # 9. POPULATE MANDATORY FIELDS IMMEDIATELY
        populate_result, error_message, status_code = chase_helpers.populate_mandatory_fields_immediately(
            selected_config_id, job_bag_id, card_data, client_contact_id, selected_bu_id, oStamp,
            category_id=category_id
        )
        
        if status_code != 200:
            raise KeyError(f"Error populating mandatory fields: {error_message}")
        
        general_helpers.fnLogToPapertrail(
            oStamp, 
            f"✓ Mandatory fields populated. Now retrieving job to get JobNo..."
        )

        # 10. Retrieve job with retry logic
        max_retries = 3
        job_bag_obj = None
        job_number = None

        for attempt in range(max_retries):
            wait_time = 3 * (attempt + 1)
            general_helpers.fnLogToPapertrail(oStamp, f"Waiting {wait_time}s before retrieval attempt {attempt + 1}...")
            time.sleep(wait_time)
            
            job_bag_obj, error_message, status_code = chase_helpers.get_job_by_id(
                selected_config_id, job_bag_id
            )
            
            if status_code == 200 and job_bag_obj:
                if isinstance(job_bag_obj, list):
                    job_bag_obj = job_bag_obj[0] if len(job_bag_obj) > 0 else None
                
                if job_bag_obj and job_bag_obj.get("JobNo"):
                    job_number = job_bag_obj.get("JobNo")
                    general_helpers.fnLogToPapertrail(
                        oStamp,
                        f"✓ Job retrieved successfully. Job Number: {job_number}"
                    )
                    break
            
            if attempt < max_retries - 1:
                general_helpers.fnLogToPapertrail(
                    oStamp,
                    f"Job not yet retrievable (attempt {attempt + 1}/{max_retries}). Retrying..."
                )

        # Fallback if retrieval fails
        if not job_number:
            general_helpers.fnLogToPapertrail(
                oStamp,
                f"Warning: Job {job_bag_id} not retrievable after {max_retries} attempts. Using JobID as JobNo."
            )
            job_number = job_bag_id

        card_data["job_number"] = job_number

        # 11. --- FIX #1: Update Pipefy IMMEDIATELY after getting job number ---
        goto_url = f"{chase_helpers.get_chase_url()}/Goto.ashx?c={selected_config_id}&f=2&i={job_bag_id}"
        pipefy.update_pipefy_fields(card_id, job_number, job_bag_id, goto_url, card_data)
        general_helpers.fnLogToPapertrail(oStamp, f"✓ Pipefy fields updated with job number {job_number}")

        # 12. Prepare data for Ziflow
        selected_client_name = card_data.get("client_db_name") or card_data.get("client_name") or "Unknown"
        selected_division = card_data.get("division_db_name") or card_data.get("division") or card_data.get("client_division")
        card_data["client_division"] = selected_division if selected_division else "N/A"

        general_helpers.fnLogToPapertrail(
            oStamp, 
            f"Sending to Ziflow: agency='{selected_agency_name}', client='{selected_client_name}', division='{card_data['client_division']}', job={job_number}"
        )

        # --- Ziflow Call ---
        ziflow_obj, status_code = general_helpers.send_ziflow_obj(
            card_data, job_number, "card", oStamp,
            agency_name=selected_agency_name,
            client_name=selected_client_name
        )

        if status_code == 200:
            general_helpers.fnLogToPapertrail(oStamp, f"Ziflow folder structure created. {ziflow_obj}")
            #ziflow_folder_id = ziflow_obj.get("ziflow_folder_id", "")
            #pipefy.update_card_field(card_id, "ziflow_folder_id", ziflow_folder_id)
        else:
            general_helpers.fnLogToPapertrail(oStamp, f"Ziflow error: {ziflow_obj}")

        # 13. Move card to phase
        phase_id = pipefy.get_phases(card_data["pipe_object"].get("id"))
        if phase_id: 
            pipefy.move_card_to_phase(card_id, phase_id)
        
        general_helpers.fnLogToPapertrail(
            oStamp, 
            f"Job {job_number} created successfully."
        )
        return "success", 200

    except Exception as e:
        exc_tb = sys.exc_info()[2]
        line_number = exc_tb.tb_lineno
        message = f"error in chase_creation_v2, error: {e}, line: {line_number}"
        general_helpers.fnLogToPapertrail(oStamp, message)
        pipefy.update_card_field(card_id, "dev_message", message)
        return message, 106


@app.post("/card_field_updated")
async def card_field_updated(request: Request):
    """Placeholder endpoint for field update webhooks."""
    try:
        data = await request.json()
        card_id = data["data"]["card"]["id"]
        field_id = data["data"]["field"]["id"]
        new_value = data["data"]["new_value"]
        oStamp = {"cardid": card_id, "time": datetime.now(tz).strftime("%Y:%m:%d %H:%M:%S")}
        general_helpers.fnLogToPapertrail(
            oStamp, f"Card field {field_id} updated to {new_value}"
        )
        return "success", 200
    except Exception as e:
        exc_tb = sys.exc_info()[2]
        line_number = exc_tb.tb_lineno
        message = f"error in card_field_updated, error: {e}, line: {line_number}"
        try:
            oStamp = {"cardid": data["data"]["card"]["id"], "time": datetime.now(tz).strftime("%Y:%m:%d %H:%M:%S")}
            general_helpers.fnLogToPapertrail(oStamp, message)
        except:
            print(message)
        return message, 106

#
# --- Brief Update Endpoint ---
#
@app.post("/brief_update")
async def brief_update(request: Request):
    """Webhook entry point for the 'Brief Update' pipe."""
    try:
        data = await request.json()
        card_id = data["data"]["card"]["id"]
        
        job_number_match = re.search(r"(\d{5,})", data["data"]["card"]["title"])
        if not job_number_match:
            raise KeyError(f"Could not parse job number from update card title: {data['data']['card']['title']}")
        job_number = job_number_match.group(1)
        
        oStamp = {"cardid": card_id, "time": datetime.now(tz).strftime("%Y:%m:%d %H:%M:%S")}
        general_helpers.fnLogToPapertrail(
            oStamp, f"Brief update received for card {card_id}, job {job_number}"
        )
        message, status_code = await update_chase_job_bag(card_id, job_number, oStamp)
        return message, status_code
    except Exception as e:
        exc_tb = sys.exc_info()[2]
        line_number = exc_tb.tb_lineno
        message = f"error in brief_update, error: {e}, line: {line_number}"
        try:
            oStamp = {"cardid": data["data"]["card"]["id"], "time": datetime.now(tz).strftime("%Y:%m:%d %H:%M:%S")}
            general_helpers.fnLogToPapertrail(oStamp, message)
        except:
            print(message)
        return message, 106

#
# --- Brief Update Logic ---
#
async def update_chase_job_bag(card_id, job_number, oStamp):
    """Updates an existing Chase job bag with info from the update card."""
    try:
        card_data, message, status_code = pipefy.get_card_details(card_id)
        if status_code != 200: 
            raise KeyError(f"Failed to get update card details {card_id}: {message}")
            
        parent_card_id = card_data.get("parent_card_id")
        if not parent_card_id: 
            raise KeyError(f"Update card {card_id} is not linked to a parent card.")
            
        general_helpers.fnLogToPapertrail(oStamp, f"Fetching parent card {parent_card_id} for context...")
        parent_card_data, message, status_code = pipefy.get_card_details(parent_card_id)
        if status_code != 200: 
            raise KeyError(f"Failed to get parent card details {parent_card_id}: {message}")

        set_test_state(parent_card_data)
        env_info = chase_helpers.get_current_environment_info()
        general_helpers.fnLogToPapertrail(oStamp, f"Environment set: {env_info}")

        selected_config_id = "1"
        selected_bu_id = 11
        
        master_record_id = parent_card_data.get("chase_master_data_record_id")
        config_id_field = parent_card_data.get("config_id_from_card")
        
        if master_record_id or config_id_field:
            general_helpers.fnLogToPapertrail(oStamp, f"V2 Parent Card {parent_card_id}. Reading helper fields...")
            selected_config_id = parent_card_data.get("config_id_from_card")
            selected_bu_id = parent_card_data.get("business_unit_id_from_card")
            if not selected_bu_id:
                selected_bu_id = parent_card_data.get("business_unit_id")
            if not selected_config_id or not selected_bu_id:
                raise KeyError(f"Parent card {parent_card_id} is missing Config ID or Business Unit ID helper fields.")
            general_helpers.fnLogToPapertrail(oStamp, f"V2 context loaded from card: ConfigID={selected_config_id}, BU={selected_bu_id}")
        else:
            general_helpers.fnLogToPapertrail(oStamp, "V1 Parent Card. Using default ConfigID=1, BU=11")

        job_bag_obj, error_message, status_code = chase_helpers.get_job_by_number(
            selected_config_id, job_number
        )
        if status_code != 200: 
            raise KeyError(f"Error getting job bag by number {job_number}: {error_message}")
        
        job_bag_id = job_bag_obj.get("JobID")
        if not job_bag_id:
            raise KeyError(f"Could not find JobID for Job Number {job_number}")

        client_contact_name = card_data.get("client_contact")
        client_contact_id = 0
        if client_contact_name:
            client_contact_id, _, error_message = chase_helpers.get_client_contact(
                selected_config_id, client_contact_name
            )
            if client_contact_id == 0: 
                general_helpers.fnLogToPapertrail(oStamp, f"Warning: Could not find client contact '{client_contact_name}'. Error: {error_message}")

        populate_result, error_message, status_code = chase_helpers.populate_mandatory_fields_immediately(
            selected_config_id, job_bag_id, card_data, client_contact_id, selected_bu_id, oStamp,
            category_id=None
        )

        if status_code != 200: 
            raise KeyError(f"Error updating required job bag fields: {error_message}")
            
        general_helpers.fnLogToPapertrail(oStamp, f"Job bag {job_number} updated successfully.")
        return "success", 200

    except Exception as e:
        exc_tb = sys.exc_info()[2]
        line_number = exc_tb.tb_lineno
        message = f"error in update_chase_job_bag, error: {e}, line: {line_number}"
        general_helpers.fnLogToPapertrail(oStamp, message)
        pipefy.update_card_field(card_id, "dev_message", message)
        return message, 106


if __name__ == "__main__":
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8080
    host = sys.argv[1] if len(sys.argv) > 1 else "0.0.0.0"
    uvicorn.run(app, host=host, port=port)