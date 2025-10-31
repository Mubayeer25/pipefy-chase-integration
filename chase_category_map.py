category_map = {
    "1": {  # Config ID for MC Saatchi Abel
        "ATL": { "tv": 1, "radio": 2, "print": 3, "ooh": 4, "default": 1 },
        "BTL": { "activations": 5, "in-store": 6, "print": 7, "default": 5 },
        "Digital": {
            "digital_ooh": 8, "social_media_monthly_retainer": 9, "social_media_campaign": 10,
            "social_media_content_creation": 11, "website_design_and_dev": 12, "website_maintenance": 13,
            "seo": 14, "paid_media": 15, "app_design_and_dev": 16, "influencer_campaign": 17,
            "ar_filter": 18, "digital_display_banners": 19, "email_marketing": 20,
            "content_creation_and_production": 21, "default": 8,
        },
        "Internal": { "internal_comms": 22, "internal_marketing": 23, "default": 22 },
        "Brand": { "ci_development": 24, "ci_rollout": 25, "brand_strategy": 26, "brand_guides": 27, "default": 24 },
        "Production": {
            "tv_production": 28, "radio_production": 29, "print_production": 30, "ooh_production": 31,
            "digital_ooh_production": 32, "in-store_production": 33, "activations_production": 34, "default": 28,
        },
        "Media": {"media": 35, "default": 35},
        "Retail": {
            "in-store": 36, "promotions": 37, "print": 38, "digital_display": 39,
            "social_media": 40, "ooh": 41, "activations": 42, "default": 36,
        },
        "PR": {
            "media_relations": 43, "media_monitoring": 44, "influencer_management": 45,
            "event_management": 46, "crisis_management": 47, "default": 43,
        },
        "Other": {"other": 48, "default": 48},
        "default": { "default": 48 },
    },

    # --- CORRECTED Config ID 6 (Up and Up Group) ---
    "6": {
        "ATL": {
            "tv": 130,           # TV
            "radio": 218,        # Radio
            "print": 219,        # Print
            "outdoor": 227,      # Outdoor
            "press": 226,        # Press
            "atl_media": 12,     # ATL Media
            "default": 579       # ATL (main category)
        },
        "BTL": {
            "activation": 881,   # Activation
            "events": 129,       # Events
            "pos": 127,          # POS
            "promotional_items": 131,  # Promotional Items
            "default": 578       # BTL (main category)
        },
        "Digital": {
            "digital": 220,          # Digital
            "digital_media": 222,    # Digital Media
            "social_media": 581,     # Social Media
            "default": 220           # Digital (main category)
        },
        "Social": {
            "social_media": 581,     # Social Media
            "default": 581
        },
        "Design": {
            "design": 884,           # Design
            "packaging": 580,        # Packaging
            "ci_development": 882,   # CI Development
            "default": 884           # Design (main category)
        },
        "Internal": {
            "general": 948,          # General
            "default": 948
        },
        "Production": {
            "production": 892,       # Production
            "printing": 224,         # Printing
            "default": 892           # Production (main category)
        },
        "Media": {
            "media": 11,             # Media
            "atl_media": 12,         # ATL Media
            "digital_media": 222,    # Digital Media
            "default": 11            # Media (main category)
        },
        "PR": {
            "pr_press": 221,         # PR/Press
            "default": 221
        },
        "Strategy": {
            "strategy": 265,         # Strategy
            "strategy_developmental": 448,  # Strategy & Developmental
            "default": 265
        },
        "Other": {
            "concept": 883,          # Concept
            "pitch": 887,            # Pitch
            "fees": 228,             # Fees
            "retainer": 124,         # Retainer
            "general": 948,          # General
            "default": 948           # General (fallback)
        },
        "default": { "default": 948 }  # General as overall fallback
    },

    # --- Config ID 7 (Copy structure from 6, adjust as needed) ---
    "7": {
        "ATL": { "default": 579 },
        "BTL": { "default": 578 },
        "Digital": { "default": 220 },
        "Social": { "default": 581 },
        "Design": { "default": 884 },
        "Production": { "default": 892 },
        "Media": { "default": 11 },
        "PR": { "default": 221 },
        "Strategy": { "default": 265 },
        "default": { "default": 948 }
    },

    # --- Config ID 8 (Copy structure from 6, adjust as needed) ---
    "8": {
        "ATL": { "default": 579 },
        "BTL": { "default": 578 },
        "Digital": { "default": 220 },
        "Social": { "default": 581 },
        "Design": { "default": 884 },
        "Production": { "default": 892 },
        "Media": { "default": 11 },
        "PR": { "default": 221 },
        "Strategy": { "default": 265 },
        "default": { "default": 948 }
    },

    # --- Config ID 9 (Copy structure from 6, adjust as needed) ---
    "9": {
        "ATL": { "default": 579 },
        "BTL": { "default": 578 },
        "Digital": { "default": 220 },
        "Social": { "default": 581 },
        "Design": { "default": 884 },
        "Production": { "default": 892 },
        "Media": { "default": 11 },
        "PR": { "default": 221 },
        "Strategy": { "default": 265 },
        "default": { "default": 948 }
    },
}