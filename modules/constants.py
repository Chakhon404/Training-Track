# modules/constants.py
# Shared constants used across forms, analytics, and daily_reminder.
# Keep this file free of any streamlit or database imports.

# json_key → (display_name, session_key, db_column)
SUPPLEMENT_MAP = {
    "creatine":       ("Creatine",       "nut_crea",         "creatine"),
    "protein_powder": ("Protein Powder", "nut_prot",         "protein_powder"),
    "multi_vitamin":  ("Multi-Vitamin",  "nut_vit",          "multivitamin"),
    "omega_3":        ("Omega-3",        "nut_omg",          "omega3"),
    "fish_oil":       ("Fish Oil",       "nut_fish_oil",     "fish_oil"),
    "astaxanthin":    ("Astaxanthin",    "nut_astaxanthin",  "astaxanthin"),
    "magnesium":      ("Magnesium",      "nut_magnesium",    "magnesium"),
    "zinc":           ("Zinc",           "nut_zinc",         "zinc"),
    "vitamin_d3":     ("Vitamin D3",     "nut_vitamin_d3",   "vitamin_d3"),
    "vitamin_c":      ("Vitamin C",      "nut_vitamin_c",    "vitamin_c"),
    "bcaa_eaa":       ("BCAA/EAA",       "nut_bcaa_eaa",     "bcaa_eaa"),
    "pre_workout":    ("Pre-Workout",    "nut_pre_workout",  "pre_workout"),
    "caffeine":       ("Caffeine",       "nut_caffeine",     "caffeine"),
    "probiotics":     ("Probiotics",     "nut_probiotics",   "probiotics"),
    "b_complex":      ("B-Complex",      "nut_b_complex",    "b_complex"),
}
