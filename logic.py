from translation import t


ORDER_STATUSES = [
    "cat_order_inbox",
    "cat_order_confirmed",
    "cat_order_processed",
    "cat_order_complete",
    "cat_order_released",
    "cat_order_annulated",
]

PIPELINE_STATUS_FLOW = [
    "cat_order_inbox",
    "cat_order_confirmed",
    "cat_order_processed",
    "cat_order_complete",
]

STATUS_COLORS = {
    "cat_order_inbox": "#E2B05E",
    "cat_order_confirmed": "#A88E75",
    "cat_order_processed": "#89A6B3",
    "cat_order_complete": "#CFA071",
    "cat_order_released": "#9EB384",
    "cat_order_annulated": "#D67B72",
}

METHOD_WEIGHTS = {"ph_cacl": 1, "humus": 1, "texture": 40}


def calculate_workload_index(active_df, weekly_capacity=40):
    total_points = 0

    for s_list in active_df["samples"]:
        for s in s_list:
            if s.get("methods"):
                methods = [m.strip() for m in s["methods"].split(",") if m.strip()]
                for m in methods:
                    total_points += METHOD_WEIGHTS.get(m, 1.0)

    index = (total_points / weekly_capacity) * 100 if weekly_capacity > 0 else 0
    return total_points, index


PREPARATION_CATALOG = {
    "cat_prep_methods": [
        "drying_40",
        "drying_60",
        "drying_105",
        "cheek_crusher",
        "sieving_2mm",
        "fine_grinding",
    ],
}

METHOD_CATALOG = {
    "cat_base_methods": [
        "ph_cacl",
        "ph_h2o",
        "toc_400",
        "humus",
        "ca_co3",
    ],
    "cat_additional_methods": [
        "cec_eff_wsl",
        "cec_pot_agr",
        "tc_tn",
    ],
    "cat_physical_methods": [
        "dry_substance",
        "text_kom",
        "text_kof",
    ],
}

PROJECT_TYPE = [
    "proj_hafl_agr",
    "proj_hafl_wwi",
    "proj_hafl_kobo",
    "proj_hafl_stud",
    "proj_external",
    "proj_others",
]

PREPARATION_PACKAGES = {
    "prep_standard_package": [
        "drying_60",
        "cheek_crusher",
        "sieving_2mm",
        "fine_grinding",
    ],
    "prep_basic_package": [
        "drying_105",
        "cheek_crusher",
        "sieving_2mm",
    ],
    "prep_care_package": [
        "drying_40",
        "cheek_crusher",
        "sieving_2mm",
        "fine_grinding",
    ],
}

ANALYSES_PACKAGES = {
    "cartosol_package": [
        "ph_cacl",
        "toc_400",
        "humus",
        "text_kom",
    ],
    "cartosol_plus_package": [
        "ph_cacl",
        "toc_400",
        "humus",
        "text_kom",
        "ca_co3",
    ],
    "agro_qual_package": [
        "ph_h2o",
        "toc_400",
        "humus",
        "tc_tn",
        "text_kof",
        "cec_pot_agr",
    ],
}


M_PH = 20  # pH benötigt meist mehr Material
M_ORG = 5  # Humus/Glühverlust
M_ICP = 2  # Elementaranalytik (sehr wenig nötig)
M_NUT = 10  # Nährstoff-Extraktionen
M_PHY = 10  # Standard Physik
M_GRAIN = 50  # Korngrößenverteilung benötigt viel Material


METHOD_DETAILS = {
    "ph_cacl": {
        "key_desc": "Bodenazidität in CaCl2",
        "ref": "DIN ISO 10390",
        "samplemass": M_PH,
    },
    "humus": {
        "key_desc": "Organische Substanz",
        "ref": "DIN ISO 10694",
        "samplemass": M_ORG,
    },
    "TC": {
        "key_desc": "Total Carbon (Elementaranalyse)",
        "ref": "DIN ISO 10694",
        "samplemass": M_ICP,
    },
    "TN": {
        "key_desc": "Total Nitrogen (Elementaranalyse)",
        "ref": "DIN ISO 13878",
        "samplemass": M_ICP,
    },
    "Trockensubstanz": {
        "key_desc": "Gravimetrisch",
        "ref": "Standard",
        "samplemass": M_PHY,
    },
    "texture": {
        "key_desc": "Pipettenmethode",
        "ref": "Standard",
        "samplemass": M_GRAIN,
    },
}


def notify_user_status_change(order_no, email, status):
    """MOCK: Mail-Versand."""
    print(f"[MAIL] {email}: {order_no} -> {status}")
