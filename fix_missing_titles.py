import configparser
import sys
from datetime import datetime
import pytz
import requests
from requests.auth import HTTPBasicAuth
import urllib3
import json
import time
import re

# --- Configuration ---
config = configparser.ConfigParser()
config.read("segredo.ini")

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Get Pipefy details
pipefy_api_url = config.get("Pipefy", "pipefy_api_url")
pipefy_api_token = config.get("Pipefy", "pipefy_api_token")

# Tables to fix - map table ID to the field that should become the title
TABLES_TO_FIX = {
    "306759853": {"title_source": "product", "name": "Levergy Products"},
    "306759851": {"title_source": "product", "name": "Dalmatian Products"},
    "306759773": {"title_source": "product", "name": "Up and Up Products"},
}

# Globals
tz = pytz.timezone("Africa/Johannesburg")
session = requests.Session()

def log(message):
    """Simple logger with timestamp."""
    timestamp = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def pipefy_post(payload):
    """Generic function to handle Pipefy GraphQL POST requests with retries."""
    max_retries = 3
    delay = 5
    for attempt in range(max_retries):
        try:
            response = session.post(
                pipefy_api_url,
                headers={
                    "Authorization": f"Bearer {pipefy_api_token}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            if "errors" in result:
                log(f"ERROR: Pipefy GraphQL Error (Attempt {attempt+1}). Errors: {result['errors']}")
                if attempt == max_retries - 1:
                    return result
            else:
                return result
        except requests.exceptions.Timeout:
            log(f"Warning: Pipefy API call timed out (Attempt {attempt+1}). Retrying in {delay}s...")
        except requests.exceptions.RequestException as e:
            log(f"ERROR: Pipefy API request failed (Attempt {attempt+1}). Status: {e.response.status_code if e.response else 'N/A'}. Error: {e}")
            if e.response is not None and 400 <= e.response.status_code < 500 and e.response.status_code != 429:
                return {"errors": [{"message": f"Pipefy Client Error: {e}"}]}
        except json.JSONDecodeError:
            log(f"ERROR: Pipefy API returned non-JSON response (Attempt {attempt+1}). Response: {response.text[:200]}")
            return {"errors": [{"message": "Pipefy returned non-JSON response"}]}
        
        if attempt < max_retries - 1:
            time.sleep(delay)
            delay *= 2
        else:
            log(f"ERROR: Pipefy API call failed after {max_retries} attempts.")
            return {"errors": [{"message": "Pipefy API call failed after multiple retries"}]}

def get_pipefy_table_records(table_id):
    """Fetches all records from the specified Pipefy table."""
    log(f"Fetching records from Pipefy table: {table_id}")
    all_records = []
    has_next_page = True
    cursor = None

    query_template = """
    query ($table_id: ID!, $cursor: String) {
      table_records(table_id: $table_id, after: $cursor, first: 50) {
        pageInfo { endCursor hasNextPage }
        edges {
          node {
            id
            title
            record_fields {
              field { id }
              value
            }
          }
        }
      }
    }
    """

    page_count = 0
    while has_next_page:
        page_count += 1
        log(f"Fetching page {page_count} for table {table_id}...")
        variables = {"table_id": table_id}
        if cursor:
            variables["cursor"] = cursor

        payload = {"query": query_template, "variables": variables}
        response = pipefy_post(payload)

        if not response or "errors" in response:
            log(f"ERROR: Failed to fetch page {page_count} from Pipefy table {table_id}. Response: {response}")
            return None

        data = response.get("data", {}).get("table_records", {})
        edges = data.get("edges", [])

        for edge in edges:
            node = edge.get("node", {})
            record_id = node.get("id")
            title = node.get("title")
            fields_list = node.get("record_fields", [])

            record_data = {
                "pipefy_record_id": record_id,
                "title": title
            }
            for field in fields_list:
                slug = field.get("field", {}).get("id")
                value = field.get("value")
                if slug:
                    record_data[slug] = value
            all_records.append(record_data)

        page_info = data.get("pageInfo", {})
        has_next_page = page_info.get("hasNextPage", False)
        cursor = page_info.get("endCursor")
        log(f"Page {page_count} fetched. hasNextPage: {has_next_page}. Records so far: {len(all_records)}")
        if has_next_page:
            time.sleep(1)

    log(f"Total records fetched: {len(all_records)}")
    return all_records

def sanitize_graphql_string(value):
    """Escapes characters that break GraphQL strings and normalizes whitespace."""
    if value is None:
        return ""
    # Normalize whitespace
    normalized = ' '.join(str(value).split())
    # Escape special characters
    return normalized.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')

def build_title_update_mutations(records, title_source_field):
    """Builds mutations to update title fields using updateTableRecord."""
    mutations = []
    
    for i, record in enumerate(records):
        record_id = record.get("pipefy_record_id")
        current_title = record.get("title")
        source_value = record.get(title_source_field)
        
        # Skip if source field is empty
        if not source_value:
            log(f"Warning: Record {record_id} has no value in '{title_source_field}' field. Skipping.")
            continue
        
        # Sanitize the title value
        new_title = sanitize_graphql_string(source_value)
        
        # Log what we're doing
        if not current_title or not current_title.strip():
            log(f"  Setting title for record {record_id}: '' → '{new_title[:50]}'")
        elif current_title != new_title:
            log(f"  Updating title for record {record_id}: '{current_title[:30]}' → '{new_title[:30]}'")
        else:
            # Title already correct, skip
            continue
        
        # Create unique alias
        safe_id = re.sub(r'\W', '_', str(record_id))
        alias = f"update_title_{i}_{safe_id}"
        
        # CORRECTED: Use updateTableRecord mutation instead of setTableRecordFieldValue
        mutation_body = f'updateTableRecord(input: {{id: "{record_id}", title: "{new_title}"}}) {{ table_record {{ id title }} }}'
        mutations.append(f"{alias}: {mutation_body}")
    
    return mutations

def execute_mutations(mutations):
    """Executes mutations in batches."""
    if not mutations:
        log("No mutations to execute.")
        return True
    
    batch_size = 50
    all_successful = True
    
    for i in range(0, len(mutations), batch_size):
        batch = mutations[i:i+batch_size]
        full_mutation_string = f"mutation {{ {' '.join(batch)} }}"
        payload = {"query": full_mutation_string}
        
        log(f"Executing batch {i//batch_size + 1}/{(len(mutations) + batch_size - 1)//batch_size} ({len(batch)} mutations)...")
        
        response = pipefy_post(payload)
        
        if not response or "errors" in response:
            log(f"ERROR: Mutation batch {i//batch_size + 1} failed. Response: {response}")
            all_successful = False
            continue
        else:
            data = response.get("data", {})
            success_count = sum(1 for alias, result in data.items() if result and result.get("table_record"))
            log(f"Batch {i//batch_size + 1} complete. Successfully updated: {success_count}/{len(batch)}")
            
            if success_count < len(batch):
                all_successful = False
                log(f"Warning: Batch {i//batch_size + 1} had partial failures.")
        
        if i + batch_size < len(mutations):
            time.sleep(2)
    
    return all_successful

def fix_table_titles(table_id, title_source, table_name):
    """Fix missing/incorrect titles for a specific table."""
    log(f"\n{'='*60}")
    log(f"Processing: {table_name} (ID: {table_id})")
    log(f"{'='*60}")
    
    # Fetch all records
    records = get_pipefy_table_records(table_id)
    if records is None:
        log(f"ERROR: Could not fetch records for table {table_id}")
        return False
    
    # Count records without proper titles
    records_needing_fix = []
    for r in records:
        title = r.get("title")
        source = r.get(title_source)
        if not title or not title.strip() or (source and title != source.strip()):
            records_needing_fix.append(r)
    
    log(f"Found {len(records_needing_fix)} records needing title fixes out of {len(records)} total records")
    
    if not records_needing_fix:
        log(f"✓ All records already have correct titles. Nothing to fix.")
        return True
    
    # Build update mutations
    mutations = build_title_update_mutations(records_needing_fix, title_source)
    log(f"Built {len(mutations)} title update mutations")
    
    if not mutations:
        log("No valid mutations to execute (all source fields were empty or titles already match)")
        return True
    
    # Execute mutations
    success = execute_mutations(mutations)
    
    if success:
        log(f"✓ Successfully updated titles for {table_name}")
    else:
        log(f"✗ Some title updates failed for {table_name}")
    
    return success

def main():
    log("="*60)
    log("ONE-TIME FIX: Populate/Fix Titles in Product Tables")
    log("="*60)
    
    overall_success = True
    
    for table_id, config in TABLES_TO_FIX.items():
        success = fix_table_titles(
            table_id,
            config["title_source"],
            config["name"]
        )
        if not success:
            overall_success = False
        
        # Small delay between tables
        time.sleep(2)
    
    log("\n" + "="*60)
    if overall_success:
        log("✓ ALL TABLES FIXED SUCCESSFULLY")
        log("Please refresh your Pipefy browser tabs to see the records!")
    else:
        log("✗ SOME TABLES HAD ERRORS - Review logs above")
    log("="*60)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)