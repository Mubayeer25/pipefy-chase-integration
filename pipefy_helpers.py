import json
import requests
import sys
from datetime import datetime
import re

class Pipefy:
    def __init__(self, host, token):
        self.host = host
        self.token = token
        self.headers = {"Content-Type": "application/json", "Authorization": "Bearer %s" % self.token}

    def post(self, payload):
        try:
            response = requests.post(self.host, data=json.dumps(payload), headers=self.headers)
            if response.status_code != 200:
                print(f"Pipefy API Error! Status: {response.status_code}, Response: {response.text}")
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Pipefy request failed: {e}")
            return {"error": "RequestException", "details": str(e)}
        except json.JSONDecodeError as e:
            print(f"Failed to decode Pipefy JSON response: {e}")
            return {"error": "JSONDecodeError", "details": str(e), "response_text": response.text if 'response' in locals() else 'No response'}

    def get_table_record_by_id(self, record_id):
        """
        Fetches a single table record by its ID.
        This is used to get the Chase IDs from the selected DB record.
        """
        # Ensure record_id is a string and properly quoted for GraphQL
        quoted_record_id = json.dumps(str(record_id))
        
        values = {
            "query": """{
                table_record(id: %s) {
                    id
                    title
                    record_fields {
                        name
                        value
                        field { id }
                    }
                }
            }"""
            % quoted_record_id
        }
        
        response = self.post(values)
        if "data" in response and response["data"].get("table_record"):
            return response["data"]["table_record"], None, 200
        else:
            error_message = response.get("errors", "Failed to get table record")
            print(f"Error in get_table_record_by_id: {error_message}")
            return {}, error_message, 106

    def get_card_details(self, card_id):
        values = {
            "query": """{
                card(id: %s) {
                    id
                    title
                    url
                    assignees { id, name }
                    fields { name, value, field { id } }
                    labels { id, name }
                    phases_history { phase { id, name }, firstTimeIn, lastTimeOut }
                    parent_relations { cards { id, title, pipe { id } } }
                    pipe { id, name }
                    current_phase { id, name }
                }
            }"""
            % card_id
        }

        response = self.post(values)
        if "data" not in response or response["data"].get("card") is None:
            return {}, response.get("errors", "Card not found or error"), 106

        card_obj = response["data"]["card"]
        
        # >>> DEBUG BLOCK (you can remove this after testing) <<<
        print("\n=== DEBUG: ALL CARD FIELDS ===")
        for field_obj in card_obj.get("fields", []):
            field_id = field_obj.get("field", {}).get("id")
            field_name = field_obj.get("name")
            field_value = field_obj.get("value")
            print(f"Field ID: '{field_id}' | Name: '{field_name}' | Value: '{field_value}'")
        print("=== END DEBUG ===\n")
        # >>> END DEBUG BLOCK <<<
        
        return_obj = {}

        # Parse basic card info
        return_obj["assignees"] = card_obj.get("assignees", [])
        return_obj["labels"] = [label["name"] for label in card_obj.get("labels", [])]
        return_obj["phases_history"] = card_obj.get("phases_history", [])
        return_obj["pipe_object"] = card_obj.get("pipe", {})
        return_obj["current_phase_object"] = card_obj.get("current_phase", {})
        return_obj["card_url"] = card_obj.get("url")
        return_obj["card_title"] = card_obj.get("title")
        
        # Get Parent Card ID (for brief updates)
        parent_relations = card_obj.get("parent_relations", [])
        if parent_relations:
            parent_cards = parent_relations[0].get("cards", [])
            if parent_cards:
                return_obj["parent_card_id"] = parent_cards[0].get("id")

        # Start parsing card fields
        return_obj["child_cards"] = []
        for field_obj in card_obj.get("fields", []):
            field_id = field_obj.get("field", {}).get("id")
            field_value = field_obj.get("value")
            
            # --- V1 Fields (Kept for backwards compatibility) ---
            if field_id == "job_name":
                return_obj["job_name"] = field_value
            elif field_id == "campaign_name":
                return_obj["campaign_name"] = field_value
            elif field_id == "job_deadline":
                try:
                    return_obj["job_deadline"] = datetime.strptime(
                        field_value, "%Y-%m-%dT%H:%M:%S%z"
                    ).strftime("%Y-%m-%d")
                except:
                    return_obj["job_deadline"] = field_value
            elif field_id == "brief_type":
                return_obj["brief_type"] = self.returnSelectValue(field_value)
            elif field_id == "element":
                return_obj["element"] = self.returnSelectValue(field_value)
            elif field_id == "other_element":
                return_obj["other_element"] = field_value
            elif field_id == "client_division":
                return_obj["client_division"] = self.returnSelectValue(field_value)
            elif field_id == "product":
                return_obj["product"] = self.returnSelectValue(field_value)
            elif field_id == "billing_category":
                return_obj["billing_category"] = self.returnSelectValue(field_value)
            elif field_id == "account_manager":
                return_obj["account_manager"] = self.returnSelectValue(field_value)
            elif field_id == "trafficker":
                # FIX: Parse trafficker through returnSelectValue to handle JSON arrays
                return_obj["trafficker"] = self.returnSelectValue(field_value)
            elif field_id == "job_number":
                return_obj["job_number"] = field_value
            elif field_id == "link_to_chase":
                return_obj["link_to_chase"] = field_value
            elif field_id == "link_to_timesheets":
                return_obj["link_to_timesheets"] = field_value
            elif field_id == "job_name_with_job_number":
                return_obj["job_name_with_job_number"] = field_value
            elif field_id == "client_contact":
                return_obj["client_contact"] = field_value
            elif field_id == "client_name":
                return_obj["client_name"] = self.returnSelectValue(field_value)
            elif field_id == "campaign_year":
                return_obj["campaign_year"] = self.returnSelectValue(field_value)
            elif field_id == "quarter":
                return_obj["campaign_quarter"] = self.returnSelectValue(field_value)
            elif field_id == "campaign_quarter":
                return_obj["campaign_quarter"] = self.returnSelectValue(field_value)
            elif field_id == "dev_message":
                return_obj["dev_messages_obj"] = self.returnSelectValue(field_value)
            elif field_id == "review_card":
                return_obj["review_card"] = self.returnSelectValue(field_value)
            elif field_id == "ziflow_folder_id":
                return_obj["ziflow_folder_id"] = field_value
            elif field_id == "parent_ziflow_folder_id":
                return_obj["parent_ziflow_folder_id"] = field_value
            elif field_id == "work_type":
                return_obj["work_type"] = self.returnSelectValue(field_value)
            elif field_id == "new_job_required":
                return_obj["new_job_required"] = self.returnSelectValue(field_value)
            elif field_id == "selected_channel":
                return_obj["selected_channel"] = self.returnSelectValue(field_value)
            elif field_id == "selected_retail_element":
                return_obj["selected_retail_element"] = self.returnSelectValue(field_value)
            elif field_id == "report_name":
                return_obj["report_name"] = field_value
            elif field_id == "retainer_or_out_of_scope":
                return_obj["billing_category"] = self.returnSelectValue(field_value)
            elif field_id == "account_manager_1":
                return_obj["account_manager"] = self.returnSelectValue(field_value)
            
            elif field_id == "go_live_date":
                # Parse go_live_date for delivery date fallback
                return_obj["go_live_date"] = field_value
            
            # --- ADD THIS NEW BLOCK START ---
            
            # --- V2 Element Fields (from GraphQL.txt) ---
            elif field_id == "atl_element":
                return_obj["atl_element"] = self.returnSelectValue(field_value)
            elif field_id == "btl_element":
                return_obj["btl_element"] = self.returnSelectValue(field_value)
            elif field_id == "design_element":
                return_obj["design_element"] = self.returnSelectValue(field_value)
            elif field_id == "digital_element":
                return_obj["digital_element"] = self.returnSelectValue(field_value)
            elif field_id == "social_element":
                return_obj["social_element"] = self.returnSelectValue(field_value)
            elif field_id == "internal_marketing_element":
                return_obj["internal_marketing_element"] = self.returnSelectValue(field_value)

            # --- V2 Division Fields (from GraphQL.txt & Log) ---
            elif field_id == "division": # From your log
                 return_obj["division"] = self.returnSelectValue(field_value)
            elif field_id == "mtn_south_africa_division":
                return_obj["mtn_south_africa_division"] = self.returnSelectValue(field_value)
            elif field_id == "mobile_fintech_division": 
                return_obj["mobile_fintech_division"] = self.returnSelectValue(field_value)
            elif field_id == "mtn_group_management_services_pty_ltd_division":
                return_obj["mtn_group_management_services_pty_ltd_division"] = self.returnSelectValue(field_value)
            
            # --- ADD THIS NEW BLOCK END ---
            
            elif field_id == "the_brief_in_a_sentence":
            
                # Parse go_live_date for delivery date fallback
                return_obj["go_live_date"] = field_value
            elif field_id == "the_brief_in_a_sentence":
                return_obj["the_brief_in_a_sentence"] = field_value
            elif field_id == "background_context":
                return_obj["background_context"] = field_value
            elif field_id == "campaign_objective":
                return_obj["campaign_objective"] = field_value
            elif field_id == "business_unit_id":
                return_obj["business_unit_id"] = field_value
            elif field_id == "client_db_name":
                return_obj["client_db_name"] = field_value

            # --- V2 Element Fields (from GraphQL.txt) ---
            elif field_id == "atl_element":
                return_obj["atl_element"] = self.returnSelectValue(field_value)
            elif field_id == "btl_element":
                return_obj["btl_element"] = self.returnSelectValue(field_value)
            elif field_id == "design_element":
                return_obj["design_element"] = self.returnSelectValue(field_value)
            elif field_id == "digital_element":
                return_obj["digital_element"] = self.returnSelectValue(field_value)
            elif field_id == "social_element":
                return_obj["social_element"] = self.returnSelectValue(field_value)
            elif field_id == "internal_marketing_element":
                return_obj["internal_marketing_element"] = self.returnSelectValue(field_value)

            # --- V2 Division Fields (from GraphQL.txt) ---
            elif field_id == "mtn_south_africa_division":
                return_obj["mtn_south_africa_division"] = self.returnSelectValue(field_value)
            elif field_id == "mobile_fintech_division": # Note: 'division' singular
                return_obj["mobile_fintech_division"] = self.returnSelectValue(field_value)
            elif field_id == "mtn_group_management_services_pty_ltd_division":
                return_obj["mtn_group_management_services_pty_ltd_division"] = self.returnSelectValue(field_value)

        # --- V2 Logic: Extract Chase Master Data Record ID ---
        AGENCY_FIELD_ID = "select_agency"
        PRODUCT_RECORD_ID_FIELD = "product_record_id"
        CONFIG_ID_FIELD = "config_id"
        BUSINESS_UNIT_ID_FIELD = "business_unit_id"
        CLIENT_ID_FIELD = "client_id"    # <-- ADD
        PRODUCT_ID_FIELD = "product_id"  # <-- ADD
        
        agency_name = None
        chase_master_data_record_id = None
        config_id_from_card = None
        business_unit_id_from_card = None
        client_id_from_card = None     # <-- ADD
        product_id_from_card = None    # <-- ADD

        for field_obj in card_obj.get("fields", []):
            field_id = field_obj.get("field", {}).get("id")
            field_value = field_obj.get("value")

            if field_id == AGENCY_FIELD_ID:
                agency_name = self.returnSelectValue(field_value)
            
            elif field_id == PRODUCT_RECORD_ID_FIELD:
                if field_value and field_value.strip():
                    chase_master_data_record_id = field_value.strip()
            
            elif field_id == CONFIG_ID_FIELD:
                if field_value and field_value.strip():
                    config_id_from_card = field_value.strip()
            
            elif field_id == BUSINESS_UNIT_ID_FIELD:
                if field_value and field_value.strip():
                    business_unit_id_from_card = field_value.strip()

            elif field_id == CLIENT_ID_FIELD:    # <-- ADD
                if field_value and field_value.strip():
                    client_id_from_card = field_value.strip()

            elif field_id == PRODUCT_ID_FIELD:   # <-- ADD
                if field_value and field_value.strip():
                    product_id_from_card = field_value.strip()

        # Add the V2 data to the return object
        return_obj["agency_name"] = agency_name
        return_obj["chase_master_data_record_id"] = chase_master_data_record_id
        return_obj["config_id_from_card"] = config_id_from_card
        return_obj["business_unit_id_from_card"] = business_unit_id_from_card
        return_obj["client_id_from_card"] = client_id_from_card     # <-- ADD
        return_obj["product_id_from_card"] = product_id_from_card    # <-- ADD
        
        return (return_obj, None, 200)

    def returnValueFromID(self, fields_array, field_id):
        for field_obj in fields_array:
            if field_obj.get("field", {}).get("id") == field_id:
                return field_obj.get("value")
        return None

    def returnSelectValue(self, str_value):
        """
        Extracts the first value from a select field.
        Handles:
        - None values
        - Already-parsed lists
        - JSON string arrays like '["Jason Blignaut"]'
        - Plain strings
        """
        if str_value is None:
            return None
        
        # If it's already a list, return first item
        if isinstance(str_value, list):
            return str_value[0] if len(str_value) > 0 else None
        
        # If it's a string that looks like a JSON array, try to parse it
        if isinstance(str_value, str):
            str_value_stripped = str_value.strip()
            
            # Check if it looks like a JSON array
            if str_value_stripped.startswith('[') and str_value_stripped.endswith(']'):
                try:
                    parsed = json.loads(str_value_stripped)
                    if isinstance(parsed, list) and len(parsed) > 0:
                        return parsed[0]
                    return parsed
                except (json.JSONDecodeError, ValueError):
                    # If parsing fails, return as-is
                    pass
            
            # Return the string as-is
            return str_value
        
        # For any other type, return as-is
        return str_value

    def update_card_field(self, card_id, field_id, field_value):
        """
        Update a single card field.
        DIAGNOSTIC VERSION: Shows the GraphQL mutation being sent.
        """
        if isinstance(field_value, str):
            field_value_json = json.dumps(field_value)
        else:
            field_value_json = str(field_value)
        
        mutation = (
            "mutation{updateCardField(input: {card_id: %s, field_id: \"%s\", new_value: %s}) "
            "{card {id title}}}"
        ) % (card_id, field_id, field_value_json)
        
        print(f"\n--- GraphQL Mutation ---")
        print(f"Field ID: {field_id}")
        print(f"Value: {field_value}")
        print(f"Mutation: {mutation[:200]}...")
        print(f"------------------------\n")
        
        values = {"query": mutation}
        result = self.post(values)
        
        # Check for errors in response
        if "errors" in result:
            print(f"❌ ERROR updating field '{field_id}': {result['errors']}")
        elif "data" in result:
            print(f"✅ SUCCESS updating field '{field_id}'")
        
        return result
        
    def update_pipefy_fields(self, card_id, job_number, job_bag_id, goto_url, card_data):
        """
        Update Pipefy fields with Chase job information.
        DIAGNOSTIC VERSION: Logs all update attempts.
        """
        # 1. Create the Timesheet URL
        timesheet_url = f"https://chase_mc.mcsaatchiabel.co.za/Chase/Time/TimeSheet.aspx?Job={job_number}"
        
        # 2. Create the Markdown-formatted strings
        job_bag_link_markdown = f"[Click here to access Chase job bag]({goto_url})"
        timesheet_link_markdown = f"[Click here to access Chase timesheets]({timesheet_url})"

        print(f"\n=== PIPEFY UPDATE DEBUG ===")
        print(f"Card ID: {card_id}")
        print(f"Job Number: {job_number} (type: {type(job_number)})")
        print(f"Job Bag ID: {job_bag_id}")
        print(f"Chase Link: {job_bag_link_markdown}")
        print(f"Timesheet Link: {timesheet_link_markdown}")
        print(f"===========================\n")

        # 3. Update job_number field
        try:
            job_number_as_int = int(job_number)
            print(f"Updating 'job_number' field with integer: {job_number_as_int}")
            result = self.update_card_field(card_id, "job_number", job_number_as_int)
            print(f"job_number update result: {result}")
        except (ValueError, TypeError) as e:
            print(f"Could not convert to int: {e}. Using string instead.")
            result = self.update_card_field(card_id, "job_number", job_number)
            print(f"job_number update result: {result}")

        # 4. Update link_to_chase field
        print(f"Updating 'link_to_chase' field...")
        result = self.update_card_field(card_id, "link_to_chase", job_bag_link_markdown)
        print(f"link_to_chase update result: {result}")

        # 5. Update link_to_timesheets field
        print(f"Updating 'link_to_timesheets' field...")
        result = self.update_card_field(card_id, "link_to_timesheets", timesheet_link_markdown)
        print(f"link_to_timesheets update result: {result}")

        # 6. Update job_name_with_job_number field (Dynamic)
        print(f"Updating 'job_name_with_job_number' field...")

        job_name = card_data.get("job_name", "")
        campaign_name = card_data.get("campaign_name", "")

        # Get the various "element" fields
        element = (
            card_data.get("atl_element") or
            card_data.get("btl_element") or
            card_data.get("digital_element") or
            card_data.get("social_element") or
            card_data.get("design_element") or
            card_data.get("internal_marketing_element") or
            card_data.get("element") or
            card_data.get("other_element")
        )
        report_name = card_data.get("report_name")
        # NOTE: You may need to add 'post_name' to your get_card_details parser if it's a field
        post_name = card_data.get("post_name") 
        select_channel = card_data.get("selected_channel")

        # Build the base string
        base_parts = [job_number, job_name, campaign_name]

        # Check for special overrides first (as per your colleague's chat)
        if post_name and select_channel:
            job_name_parts = [select_channel, post_name, job_number, job_name, campaign_name]
        elif report_name:
            job_name_parts = base_parts + [report_name]
        elif element:
            job_name_parts = base_parts + [element]
        else:
            job_name_parts = base_parts

        # Filter out None or empty strings and join
        final_job_name_string = " | ".join([str(part) for part in job_name_parts if part])

        print(f"Updating 'job_name_with_job_number' field with: '{final_job_name_string}'")
        result = self.update_card_field(card_id, "job_name_with_job_number", final_job_name_string)
        print(f"job_name_with_job_number update result: {result}")
        
        print(f"=== PIPEFY UPDATE COMPLETE ===\n")


    def move_card_to_phase(self, card_id, phase_id):
        values = {
            "query": "mutation{moveCardToPhase(input: {card_id: %s, destination_phase_id: %s}) {card {id title}}}"
            % (card_id, phase_id)
        }
        return self.post(values)

    def get_phases(self, pipe_id):
        values = {
            "query": """{
                pipe(id: %s) {
                    phases {
                        id
                        name
                    }
                }
            }"""
            % pipe_id
        }
        response = self.post(values)
        try:
            for phase in response["data"]["pipe"]["phases"]:
                if phase["name"].lower() == "in progress":
                    return phase["id"]
            return response["data"]["pipe"]["phases"][0]["id"]
        except:
            return None

    def showTable(self, table_id):
        values = {
            "query": """{
                table_records(table_id: "306454179") {
                    nodes {
                        id
                        title
                        record_fields {
                            name
                            value
                        }
                    }
                }
            }"""
        }
        return self.post(values)