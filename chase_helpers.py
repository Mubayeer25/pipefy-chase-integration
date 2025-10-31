import configparser
import json
import re
import sys
from datetime import datetime, timedelta

import pytz
import requests
import urllib3
from requests.adapters import HTTPAdapter
from requests.auth import HTTPBasicAuth
from urllib3.util.retry import Retry

import chase_category_map
import general_helpers

# Suppress only the InsecureRequestWarning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

timeout = 10
max_retry = 3
session = requests.Session()
retries = Retry(
    total=max_retry,
    backoff_factor=1,
)
adapter = HTTPAdapter(max_retries=retries)
session.mount("https://", adapter)
session.mount("http://", adapter)

config = configparser.ConfigParser()
config.read("segredo.ini")

chase_username_live = config.get("Chase", "CHASE_USERNAME_LIVE")
chase_password_live = config.get("Chase", "CHASE_PASSWORD_LIVE")
chase_url_live = config.get("Chase", "CHASE_URL_LIVE")
chase_username_qa = config.get("Chase", "CHASE_USERNAME_QA")
chase_password_qa = config.get("Chase", "CHASE_PASSWORD_QA")
chase_url_qa = config.get("Chase", "CHASE_URL_QA")

test_state = False  # False = Live, True = QA

def get_basic_auth():
    if test_state:
        return HTTPBasicAuth(chase_username_qa, chase_password_qa)
    else:
        return HTTPBasicAuth(chase_username_live, chase_password_live)

def get_chase_url():
    if test_state:
        return chase_url_qa
    else:
        return chase_url_live

def get_current_environment_info():
    if test_state:
        return f"QA Mode: URL={chase_url_qa}, User={chase_username_qa}"
    else:
        return f"Live Mode: URL={chase_url_live}, User={chase_username_live}"


def create_job_bag(config_id, client_id, product_id, category_id, card_data, element=None):
    """
    Creates a new job bag in Chase using URL parameters.
    """
    try:
        base_url = f"{get_chase_url()}/api/Job/AddNew"
        
        # Default element to job name if not provided
        if not element:
            element = card_data.get("job_name", "Job")
        
        # Build URL parameters with MANDATORY fields included
        params = {
            "customerid": client_id,
            "productid": product_id,
            "element": element,
            "categoryid": category_id,
        }
        
        headers = {
            "ConfigID": config_id,
            "Accept": "*/*"
        }

        print(f"\n=== CREATE JOB BAG DEBUG ===")
        print(f"URL: {base_url}")
        print(f"ConfigID: {config_id}")
        print(f"Params: {params}")
        print(f"Chase URL Base: {get_chase_url()}")
        print(f"Auth User: {get_basic_auth().username}")
        print(f"=========================\n")

        response_obj = session.post(
            base_url, 
            auth=get_basic_auth(), 
            headers=headers, 
            params=params,
            json=None,
            verify=False, 
            timeout=timeout
        )

        print(f"Response Status: {response_obj.status_code}")
        print(f"Response Headers: {dict(response_obj.headers)}")
        print(f"Response Body: {response_obj.text}\n")

        if response_obj.status_code == 200:
            job_bag_id = response_obj.text.strip()
                
            if job_bag_id:
                 return job_bag_id, "success", 200
            else:
                 return None, f"Chase returned empty success response. Raw: {response_obj.text}", 500
        
        elif response_obj.status_code == 404:
            error_detail = (
                f"404 Error - Endpoint not found. This could mean:\n"
                f"1. ConfigID '{config_id}' doesn't have access to this endpoint\n"
                f"2. The Chase instance at '{get_chase_url()}' doesn't support this operation\n"
                f"3. The client/product IDs don't exist in this Chase database\n"
                f"Original error: {response_obj.text}"
            )
            return None, error_detail, response_obj.status_code
        
        else:
            return None, response_obj.text, response_obj.status_code

    except Exception as e:
        exc_tb = sys.exc_info()[2]
        line_number = exc_tb.tb_lineno
        message = (
            f"error while creating job bag, client_id: {client_id}, product_id: {product_id}, "
            f"error: {e}, line: {line_number}"
        )
        return None, message, 106
    finally:
        session.close()


def get_client_id(config_id, client_name):
    """
    Gets a client ID by name.
    """
    try:
        url = f"{get_chase_url()}/api/Client/Name/{client_name}"
        headers = {"ConfigID": config_id}
        response_obj = session.get(
            url, auth=get_basic_auth(), headers=headers, verify=False, timeout=timeout
        )
        
        if response_obj.status_code == 200:
            return response_obj.json().get("ClientID"), "success", response_obj.status_code
        else:
            return {}, response_obj.text, response_obj.status_code
            
    except Exception as e:
        exc_tb = sys.exc_info()[2]
        line_number = exc_tb.tb_lineno
        message = f"error while getting client id, client_name: {client_name}, error: {e}, line: {line_number}"
        return None, message, 106
    finally:
        session.close()


def get_product_id(config_id, product_name, client_id):
    """
    Gets a product ID by name, filtered by client ID.
    """
    try:
        url = f"{get_chase_url()}/api/Product/CustomerID/{client_id}"
        headers = {"ConfigID": config_id}
        response_obj = session.get(
            url, auth=get_basic_auth(), headers=headers, verify=False, timeout=timeout
        )

        if response_obj.status_code != 200:
            return None, response_obj.text, response_obj.status_code
        
        products = response_obj.json()
        if not products:
            return None, "No products found for this client.", 404

        for product in products:
            if product.get("ProductName").strip().lower() == product_name.strip().lower():
                return {
                    "product_id": product.get("ProductID"),
                    "product_contact": product.get("ContactName"),
                }, "success", 200
        for product in products:
            if product_name.strip().lower() in product.get("ProductName").strip().lower():
                return {
                    "product_id": product.get("ProductID"),
                    "product_contact": product.get("ContactName"),
                }, "success - partial match", 200
        return None, f"No product found matching '{product_name}'", 404

    except Exception as e:
        exc_tb = sys.exc_info()[2]
        line_number = exc_tb.tb_lineno
        message = (
            f"error while getting product id, product_name: {product_name}, client_id: {client_id}, "
            f"error: {e}, line: {line_number}"
        )
        return None, message, 106
    finally:
        session.close()

def get_client_contact(config_id, client_contact_name):
    """
    Gets a client contact ID by name.
    NOTE: This is a placeholder to fix a missing function error.
    The Chase API endpoint for contacts is not specified.
    This function logs a warning and returns 0.
    """
    try:
        # TODO: Implement the actual Chase API lookup for client contacts
        # Example endpoint might be /api/ClientContact/Name/{client_contact_name}
        # or /api/ClientContact/Customer/{client_id}
        
        # For now, return 0 (no contact) and a warning
        message = f"Placeholder: Contact '{client_contact_name}' lookup not implemented. Returning 0."
        return 0, message, 404

    except Exception as e:
        exc_tb = sys.exc_info()[2]
        line_number = exc_tb.tb_lineno
        message = (
            f"error while getting client contact id, contact_name: {client_contact_name}, "
            f"error: {e}, line: {line_number}"
        )
        return 0, message, 106
    finally:
        session.close()

def get_job_category_id(config_id, brief_type, element, other_element, pipe_name, selected_channel, selected_retail_element):
    """
    Gets a job category ID by matching various card fields against the category map.
    """
    try:
        # Use str(config_id) to ensure matching with string keys in the map
        category_map = chase_category_map.category_map.get(str(config_id), {})
        
        if brief_type is None:
            brief_type = "default"
        
        brief_type_map = category_map.get(brief_type, category_map.get("default", {}))
        
        if other_element is not None and other_element != "":
            category_id = brief_type_map.get(other_element.lower())
            if category_id: return category_id, "success", 200
        if element is not None and element != "":
            category_id = brief_type_map.get(element.lower())
            if category_id: return category_id, "success", 200
        if selected_retail_element is not None and selected_retail_element != "":
            category_id = brief_type_map.get(selected_retail_element.lower())
            if category_id: return category_id, "success", 200
        if selected_channel is not None and selected_channel != "":
            category_id = brief_type_map.get(selected_channel.lower())
            if category_id: return category_id, "success", 200
        category_id = brief_type_map.get(pipe_name.lower())
        if category_id: return category_id, "success", 200

        default_category_id = brief_type_map.get("default")
        if default_category_id: return default_category_id, "success - default match", 200
            
        return None, "No category id found", 404

    except Exception as e:
        exc_tb = sys.exc_info()[2]
        line_number = exc_tb.tb_lineno
        message = (
            f"error while getting job category id, brief_type: {brief_type}, "
            f"error: {e}, line: {line_number}"
        )
        return None, message, 106

def get_business_unit_id(config_id, business_unit):
    """
    Gets a business unit ID by name.
    """
    try:
        url = f"{get_chase_url()}/api/BusinessUnit"
        headers = {"ConfigID": config_id}
        response_obj = session.get(
            url, auth=get_basic_auth(), headers=headers, verify=False, timeout=timeout
        )

        if response_obj.status_code != 200:
            return None, response_obj.text, response_obj.status_code

        business_units = response_obj.json()
        if not business_units:
            return None, "No business units found.", 404
        for bu in business_units:
            if bu.get("BusinessUnit").strip().lower() == business_unit.strip().lower():
                return bu.get("BusinessUnitID"), "success", 200
        return None, f"No business unit found matching '{business_unit}'", 404

    except Exception as e:
        exc_tb = sys.exc_info()[2]
        line_number = exc_tb.tb_lineno
        message = (
            f"error while getting business unit id, business_unit: {business_unit}, "
            f"error: {e}, line: {line_number}"
        )
        return None, message, 106
    finally:
        session.close()

def get_user_id(config_id, user_name, user_role="Traffic"):
    """
    Gets a user ID by name or role using the /api/User/GetUsers endpoint.
    API returns lowercase field names: 'userid' and 'username'.
    
    FIX: Added fuzzy matching to handle small spelling differences.
    """
    try:
        # Safety check: ensure user_name is a string
        if not isinstance(user_name, str):
            return None, f"Invalid user_name type: {type(user_name)}. Expected string.", 400
        
        headers = {"ConfigID": config_id}
        url = f"{get_chase_url()}/api/User/GetUsers"
        
        print(f"\n=== GET USER ID DEBUG ===")
        print(f"URL: {url}")
        print(f"ConfigID: {config_id}")
        print(f"Looking for: '{user_name}' (fallback to role: '{user_role}')")
        
        response_obj = session.get(
            url, auth=get_basic_auth(), headers=headers, verify=False, timeout=timeout
        )
        
        print(f"Response Status: {response_obj.status_code}")
        
        if response_obj.status_code != 200:
            print(f"Failed: {response_obj.text[:200]}")
            return None, response_obj.text, response_obj.status_code
        
        users = response_obj.json()
        
        if not users or not isinstance(users, list):
            return None, f"No users found or unexpected format. Response type: {type(users)}", 404
        
        print(f"Found {len(users)} users")
        
        user_name_lower = user_name.strip().lower()
        
        # Helper function for fuzzy matching (allows 1-2 character differences)
        def fuzzy_match(str1, str2, max_diff=2):
            """Returns True if strings are within max_diff character differences"""
            if str1 == str2:
                return True
            
            # Calculate simple edit distance (Levenshtein-like)
            len1, len2 = len(str1), len(str2)
            if abs(len1 - len2) > max_diff:
                return False
            
            differences = 0
            for i in range(min(len1, len2)):
                if str1[i] != str2[i]:
                    differences += 1
                    if differences > max_diff:
                        return False
            
            differences += abs(len1 - len2)
            return differences <= max_diff
        
        # 1. Try exact match on username (case-insensitive)
        for user in users:
            if not isinstance(user, dict):
                continue
            
            username = user.get("username", "")
            if username and username.strip().lower() == user_name_lower:
                user_id = user.get("userid")
                print(f"✓ Found exact match: '{username}' -> UserID: {user_id}\n")
                return user_id, "success - full name match", 200
        
        # 2. Try fuzzy match on username (handles "Hlalele" vs "Hlaiele" typos)
        for user in users:
            if not isinstance(user, dict):
                continue
            
            username = user.get("username", "")
            if username and fuzzy_match(username.strip().lower(), user_name_lower):
                user_id = user.get("userid")
                print(f"✓ Found fuzzy match: '{username}' -> UserID: {user_id}\n")
                return user_id, "success - fuzzy name match", 200
        
        # 3. Try matching first name only
        for user in users:
            if not isinstance(user, dict):
                continue
            
            username = user.get("username", "")
            if username:
                first_name = username.strip().split(" ")[0]
                if first_name.strip().lower() == user_name_lower or fuzzy_match(first_name.strip().lower(), user_name_lower):
                    user_id = user.get("userid")
                    print(f"✓ Found first name match: '{username}' -> UserID: {user_id}\n")
                    return user_id, "success - first name match", 200
        
        # 4. Only fall back to role matching if user_name was generic (like "Traffic")
        # This prevents wrong matches when a specific name was provided
        if user_name_lower in ["traffic", "account manager", "creative", "studio"]:
            user_role_lower = user_role.strip().lower()
            for user in users:
                if not isinstance(user, dict):
                    continue
                
                designation = user.get("designation", "")
                if designation and user_role_lower in designation.strip().lower():
                    user_id = user.get("userid")
                    username = user.get("username", "")
                    print(f"✓ Found role match: '{username}' (designation: {designation}) -> UserID: {user_id}\n")
                    return user_id, "success - role/designation match", 200
            
            # Fallback: Try matching username that contains the role
            for user in users:
                if not isinstance(user, dict):
                    continue
                
                username = user.get("username", "")
                if username and user_role_lower in username.strip().lower():
                    user_id = user.get("userid")
                    print(f"✓ Found username containing role: '{username}' -> UserID: {user_id}\n")
                    return user_id, "success - username contains role", 200
        
        print(f"✗ No match found for '{user_name}' or role '{user_role}'\n")
        print(f"Available users (first 20):")
        for i, user in enumerate(users[:20]):
            if isinstance(user, dict):
                username = user.get("username", "N/A")
                userid = user.get("userid", "N/A")
                designation = user.get("designation", "N/A")
                print(f"  {i+1}. '{username}' (ID: {userid}, Role: {designation})")
        print()
        
        return None, f"No user found matching '{user_name}' or role '{user_role}'", 404

    except Exception as e:
        exc_tb = sys.exc_info()[2]
        line_number = exc_tb.tb_lineno
        message = f"error while getting user id, user_name: {user_name}, error: {e}, line: {line_number}"
        print(f"ERROR in get_user_id: {message}\n")
        return None, message, 106
    finally:
        session.close()

def populate_mandatory_fields_immediately(config_id, job_bag_id, card_data, client_contact_id, selected_business_unit_id, oStamp, category_id=None):
    """
    Populates ALL mandatory fields immediately after job creation
    using the /api/Job/UpdateSpecificFields endpoint.
    
    NEW: Added category_id parameter to re-set it during update
    """
    try:
        url = f"{get_chase_url()}/api/Job/UpdateSpecificFields"
        headers = {
            "ConfigID": config_id,
            "accept": "application/json",
            "Content-Type": "application/json",
        }
        
        # Build the update payload with ONLY mandatory fields
        update_payload = {
            "JobID": job_bag_id,
        }
        
        # MANDATORY: Job Category (if provided)
        if category_id:
            update_payload["JobCategoryID"] = int(category_id)  # Ensure it's an integer
        
        # MANDATORY: Business Unit ID
        if selected_business_unit_id:
            update_payload["BusinessUnitID"] = int(selected_business_unit_id)
        else:
            general_helpers.fnLogToPapertrail(oStamp, "ERROR: Business Unit ID is missing (mandatory field)")
            return None, "Business Unit ID is required", 400
        
        # MANDATORY: Billing Category ID
        billing_category = card_data.get("billing_category")
        if billing_category:
            if "retainer: in scope" in billing_category.lower():
                update_payload["BillingCategoryID"] = 1
            elif "retainer: out of scope" in billing_category.lower():
                update_payload["BillingCategoryID"] = 2
            elif "project" in billing_category.lower():
                update_payload["BillingCategoryID"] = 3
            else:
                update_payload["BillingCategoryID"] = 2 # Default to 'Out of scope'
                general_helpers.fnLogToPapertrail(oStamp, f"Warning: Unknown billing category, defaulting to 'Retainer: Out of scope' (ID=2)")
        else:
            # Default to 2 (Retainer: Out of scope)
            update_payload["BillingCategoryID"] = 2
            general_helpers.fnLogToPapertrail(oStamp, "Warning: No billing category, defaulting to 'Retainer: Out of scope' (ID=2)")
        
        # MANDATORY: Production Delivery Date (must be in ISO format YYYY-MM-DD)
        delivery_date = card_data.get("job_deadline") or card_data.get("go_live_date")
        if delivery_date:
            # Convert various date formats to ISO format YYYY-MM-DD
            try:
                # Try parsing common formats
                for fmt in ["%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d", "%d/%m/%Y %H:%M", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S"]:
                    try:
                        parsed_date = datetime.strptime(delivery_date, fmt)
                        update_payload["DeliveryDate"] = parsed_date.strftime("%Y-%m-%d")
                        break
                    except (ValueError, TypeError):
                        continue
                else:
                    # If no format matches, log warning and use fallback
                    general_helpers.fnLogToPapertrail(oStamp, f"Warning: Could not parse date '{delivery_date}', using fallback")
                    fallback_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
                    update_payload["DeliveryDate"] = fallback_date
            except Exception as e:
                general_helpers.fnLogToPapertrail(oStamp, f"Error parsing delivery date: {e}")
                fallback_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
                update_payload["DeliveryDate"] = fallback_date
        else:
            # Use today's date + 7 days as fallback
            fallback_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
            update_payload["DeliveryDate"] = fallback_date
            general_helpers.fnLogToPapertrail(oStamp, f"Warning: No delivery date provided, using {fallback_date}")
        
        # MANDATORY: Job Description
        job_description = (
            card_data.get("campaign_objective") or 
            card_data.get("the_brief_in_a_sentence") or 
            card_data.get("background_context") or
            card_data.get("job_name") or
            "Brief created from Pipefy"
        )

        # Add Pipefy Card URL to the description
        card_url = card_data.get("card_url")
        if card_url:
            job_description += f"\n\nPipefy Card URL: {card_url}"

        update_payload["JobDescription"] = job_description[:1000] # Limit to 1000 chars
        
        # MANDATORY: Traffic User ID
        trafficker_name = card_data.get("trafficker")
        traffic_user_id = None
        
        if trafficker_name:
            tf_id, msg, code = get_user_id(config_id, trafficker_name, "Traffic")
            if code == 200:
                traffic_user_id = tf_id
            else:
                general_helpers.fnLogToPapertrail(oStamp, f"Warning: Could not find trafficker '{trafficker_name}'. {msg}")
        
        # If no trafficker found, try to get default Traffic user
        if not traffic_user_id:
            tf_id_default, msg, code = get_user_id(config_id, "Traffic", "Traffic")
            if code == 200:
                traffic_user_id = tf_id_default
            else:
                general_helpers.fnLogToPapertrail(oStamp, "ERROR: No Traffic user found. This is a mandatory field!")
                return None, "Traffic User ID is required but no default found", 400
        
        update_payload["TrafficUserID"] = traffic_user_id
        
        # Optional but recommended: Account Manager
        account_manager_name = card_data.get("account_manager")
        if account_manager_name:
            am_id, msg, code = get_user_id(config_id, account_manager_name, "Account Manager")
            if code == 200:
                update_payload["AccountManagerUserID"] = am_id
        
        # Optional: Client Contact
        if client_contact_id:
            update_payload["ClientContactID"] = client_contact_id
        
        print(f"\n=== UPDATE MANDATORY FIELDS ===")
        print(f"URL: {url}")
        print(f"Payload: {json.dumps(update_payload, indent=2)}")
        print(f"==============================\n")
        
        # Send the update
        data = json.dumps(update_payload)
        response_obj = session.post(
            url, auth=get_basic_auth(), headers=headers, data=data, verify=False, timeout=timeout
        )
        
        print(f"Update Response Status: {response_obj.status_code}")
        print(f"Update Response Body: {response_obj.text[:500]}\n")
        
        if response_obj.status_code == 200:
            try:
                response_data = response_obj.json()
            except json.JSONDecodeError:
                # Handle cases where response is 'true'
                if response_obj.text.lower() == 'true':
                    return {"JobID": job_bag_id}, "success", 200
                return None, f"Update failed: Non-JSON response '{response_obj.text}'", 500

            # Check if the response contains an error message despite 200 status
            if isinstance(response_data, dict):
                if "Message" in response_data and "Error" in response_data.get("Message", ""):
                    error_msg = response_data.get("Message", "Unknown error")
                    exception_msg = response_data.get("ExceptionMessage", "")
                    full_error = f"{error_msg}. {exception_msg}" if exception_msg else error_msg
                    return None, full_error, 500
                
                return response_data, "success", 200
            
            # If response is just 'true', that's also success
            return {"JobID": job_bag_id}, "success", 200
        else:
            return None, response_obj.text, response_obj.status_code
            
    except Exception as e:
        exc_tb = sys.exc_info()[2]
        line_number = exc_tb.tb_lineno
        message = (
            f"error while populating mandatory fields, job_bag_id: {job_bag_id}, "
            f"error: {e}, line: {line_number}"
        )
        return None, message, 106
    finally:
        session.close()
        
def get_job_by_id(config_id, job_id):
    """
    Gets a job by its ID using the correct Chase API endpoint.
    Per Dominic Samra: GET {chase_url}/api/Job/{job_id}
    """
    try:
        url = f"{get_chase_url()}/api/Job/{job_id}"
        headers = {"ConfigID": config_id}
        
        print(f"\n=== GET JOB BY ID ===")
        print(f"URL: {url}")
        print(f"ConfigID: {config_id}")
        print(f"JobID: {job_id}")
        print(f"=====================\n")
        
        response_obj = session.get(
            url, auth=get_basic_auth(), headers=headers, verify=False, timeout=timeout
        )
        
        print(f"Response Status: {response_obj.status_code}")
        print(f"Response Body: {response_obj.text[:500]}\n")
        
        if response_obj.status_code == 200:
            result = response_obj.json()
            
            if isinstance(result, list):
                if len(result) > 0:
                    return result[0], "success", response_obj.status_code
                else:
                    return {}, "Job not found (empty list) - may need mandatory fields populated", 404
            else:
                return result, "success", response_obj.status_code
        elif response_obj.status_code == 404:
            return {}, "Job not found - may need mandatory fields populated", 404
        else:
            return {}, response_obj.text, response_obj.status_code

    except Exception as e:
        exc_tb = sys.exc_info()[2]
        line_number = exc_tb.tb_lineno
        message = (
            f"error while getting job by id, job_id: {job_id}, "
            f"error: {e}, line: {line_number}"
        )
        return None, message, 106
    finally:
        session.close()


def get_job_by_number(config_id, job_bag_number):
    """
    Alias for get_job_by_id, as Job ID is used for retrieval.
    """
    return get_job_by_id(config_id, job_bag_number)


def get_job_required_fields(config_id, job_bag_id):
    """
    Alias for get_job_by_id.
    """
    return get_job_by_id(config_id, job_bag_id)

