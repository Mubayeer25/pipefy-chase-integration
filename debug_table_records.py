import configparser
import requests
import json

config = configparser.ConfigParser()
config.read("segredo.ini")

pipefy_api_url = config.get("Pipefy", "pipefy_api_url")
pipefy_api_token = config.get("Pipefy", "pipefy_api_token")

# First, get the table structure to see ALL fields
structure_query = """
query {
  table(id: "306759853") {
    name
    table_fields {
      id
      label
      type
      required
    }
  }
}
"""

print("=" * 60)
print("TABLE STRUCTURE:")
print("=" * 60)
response = requests.post(
    pipefy_api_url,
    headers={"Authorization": f"Bearer {pipefy_api_token}", "Content-Type": "application/json"},
    json={"query": structure_query}
)
structure = response.json()
print(json.dumps(structure, indent=2))

# Now check a few sample records
records_query = """
query {
  table_records(table_id: "306759853", first: 3) {
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

print("\n" + "=" * 60)
print("SAMPLE RECORDS:")
print("=" * 60)
response = requests.post(
    pipefy_api_url,
    headers={"Authorization": f"Bearer {pipefy_api_token}", "Content-Type": "application/json"},
    json={"query": records_query}
)
records = response.json()
print(json.dumps(records, indent=2))

# Check if any required fields are missing
print("\n" + "=" * 60)
print("ANALYSIS:")
print("=" * 60)

table_fields = structure.get("data", {}).get("table", {}).get("table_fields", [])
required_fields = [f for f in table_fields if f.get("required")]

if required_fields:
    print(f"Table has {len(required_fields)} REQUIRED fields:")
    for field in required_fields:
        print(f"  - {field['id']} ({field['label']}) - Type: {field['type']}")
else:
    print("Table has NO required fields")

# Check first record
edges = records.get("data", {}).get("table_records", {}).get("edges", [])
if edges:
    first_record = edges[0]["node"]
    record_field_ids = [f["field"]["id"] for f in first_record["record_fields"]]
    all_field_ids = [f["id"] for f in table_fields]
    
    missing_fields = set(all_field_ids) - set(record_field_ids)
    if missing_fields:
        print(f"\nFirst record is MISSING these fields:")
        for field_id in missing_fields:
            field = next((f for f in table_fields if f["id"] == field_id), None)
            if field:
                print(f"  - {field_id} ({field.get('label')}) - Required: {field.get('required')}")