# Quick test script
import configparser
from pipefy_helpers import Pipefy

config = configparser.ConfigParser()
config.read("segredo.ini")

pipefy_api_url = config.get("Pipefy", "pipefy_api_url")
pipefy_api_token = config.get("Pipefy", "pipefy_api_token")

pipefy = Pipefy(pipefy_api_url, pipefy_api_token)

card_id = "1245645512"
card_data, msg, sc = pipefy.get_card_details(card_id)

print("=" * 60)
print("CARD FIELD VALUES:")
print("=" * 60)
print(f"business_unit_record_id: {card_data.get('business_unit_record_id')}")
print(f"product_record_id: {card_data.get('product_record_id')}")
print(f"division_record_id: {card_data.get('division_record_id')}")
print(f"v2_business_unit_id: {card_data.get('v2_business_unit_id')}")
print(f"v2_config_id: {card_data.get('v2_config_id')}")