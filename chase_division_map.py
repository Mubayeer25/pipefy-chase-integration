# Chase Division to Field ID Mapping
# This mapping allows retrieval of field_id based on division names

CHASE_DIVISION_MAP = {
    "MTN South Africa division": {
        "Business": "82",
        "Brand": "70",
        "Business Corporate": "90",
        "CDO": "98",
        "CDO – Levergy": "99",
        "Corporate": "71",
        "Corporate Sponsorship": "104",
        "Corporate Sponsorship Levergy": "106",
        "Digital Organic": "95",
        "Digital Paid": "94",
        "Digital Services": "81",
        "EBU Campaign": "173",
        "EBU Digital": "85",
        "EBU Retail": "84",
        "Exp – Levergy": "87",
        "Exp – PR": "75",
        "Expdigital Organic Levergy": "97",
        "Exponline & Social Levergy": "96",
        "Home & Residential": "88",
        "Internal Communications": "91",
        "Internal Communications Levergy": "92",
        "Levergy": "72",
        "MTN Branded Channel": "76",
        "MTN Corporate": "89",
        "MTN Informal Channel": "77",
        "MTN Retail": "133",
        "MTN Retail BRC": "80",
        "MTN Retail Chains": "78",
        "MTN Social/ Organic": "93",
        "Proposition Levergy": "102",
        "Proposition Postpaid": "101",
        "Proposition Prepaid": "100",
        "Razor": "73",
        "Regional": "79",
        "Wholesale": "74",
        "Youth": "107",
        "Youth Levergy": "108"
    },
    
    "Mobile Fintech division": {
        "MTN Fintech Extra Time": "109",
        "MTN Fintech MoMo": "110",
        "MTN Fintech Life Insurance": "111",
        "MTN Fintech Funeral Insurance": "112",
        "MTN Fintech Device Insurance": "113"
    },

    "MTN Group Management Services (Pty) Ltd division": {
        "Ad Hoc / Other": "114",
        "CBU Retail": "116",
        "Digital": "117",
        "EBU Retail": "118",
        "General": "119",
        "Home": "120",
        "MFS": "121",
        "EBU Campaigns": "174",
    }
}

def get_field_id_by_division(division_name):
    """
    Retrieve field_id for a given division name.
    
    Args:
        division_name (str): The name of the division
        
    Returns:
        str: The field_id if found, None otherwise
    """
    for category, divisions in CHASE_DIVISION_MAP.items():
        if division_name in divisions:
            return divisions[division_name]
    return None

def get_field_id_by_category_and_division(category, division_name):
    """
    Retrieve field_id for a given category and division name.
    
    Args:
        category (str): The category name (e.g., "MTN South Africa divisions")
        division_name (str): The name of the division
        
    Returns:
        str: The field_id if found, None otherwise
    """
    if category in CHASE_DIVISION_MAP and division_name in CHASE_DIVISION_MAP[category]:
        return CHASE_DIVISION_MAP[category][division_name]
    return None

def get_all_divisions():
    """
    Get a list of all available division names.
    
    Returns:
        list: List of all division names
    """
    all_divisions = []
    for category, divisions in CHASE_DIVISION_MAP.items():
        all_divisions.extend(divisions.keys())
    return all_divisions

def get_all_field_ids():
    """
    Get a list of all field IDs.
    
    Returns:
        list: List of all field IDs
    """
    all_field_ids = []
    for category, divisions in CHASE_DIVISION_MAP.items():
        all_field_ids.extend(divisions.values())
    return all_field_ids

def get_divisions_by_category(category):
    """
    Get all divisions for a specific category.
    
    Args:
        category (str): The category name
        
    Returns:
        dict: Dictionary of division names to field IDs for the category
    """
    return CHASE_DIVISION_MAP.get(category, {})


# Example usage:
# field_id = get_field_id_by_division("Business")  # Returns "82"
# field_id = get_field_id_by_category_and_division("MTN South Africa divisions", "Business")  # Returns "82"
# divisions = get_all_divisions()  # Returns list of all division names
# mtm_divisions = get_divisions_by_category("MTN South Africa divisions")  # Returns MTN SA divisions dict