COLOR_GREEN_BG = "#9DFE9D"
COLOR_YELLOW_BG = "#FEFE9D"
COLOR_RED_BG = "#FE9D9D"
COLOR_TEXT_DARK = "#000000"

def calculate_bmr(gender, weight, height, age):
    return (10 * weight) + (6.25 * height) - (5 * age) + (5 if gender.lower() == "male" else -161)

DIET_LIMITS = {
    "WHO Guidelines": {'fat_percent_max': 30, 'carbs_percent_max': 55, 'protein_percent_max': 15, 'fiber_grams_max': 25, 'salt_max': 5},
    "LCHF": {'fat_percent_max': 75, 'carbs_percent_max': 5, 'protein_percent_max': 20, 'fiber_grams_max': 30, 'salt_max': 15},
    "Ketogenic Diet": {'fat_percent_max': 80, 'carbs_percent_max': 5, 'protein_percent_max': 20, 'fiber_grams_max': 30, 'salt_max': 15},
    "High Protein Diet": {'fat_percent_max': 30, 'carbs_percent_max': 45, 'protein_percent_max': 25, 'fiber_grams_max': 25, 'salt_max': 5},
    "Vegan Diet": {'fat_percent_max': 40, 'carbs_percent_max': 60, 'protein_percent_max': 20, 'fiber_grams_max': 30, 'salt_max': 6},
    "Raw Food Diet": {'fat_percent_max': 10, 'carbs_percent_max': 80, 'protein_percent_max': 10, 'fiber_grams_max': 30, 'salt_max': 6},
    "Ray Kurzweil Diet": {'fat_percent_max': 10, 'carbs_percent_max': 60, 'protein_percent_max': 30, 'fiber_grams_max': 40, 'salt_max': 2},
    "Paleo Diet": {'fat_percent_max': 39, 'carbs_percent_max': 23, 'protein_percent_max': 38, 'fiber_grams_max': 45, 'salt_max': 2},
    "Mediterranean Diet": {'fat_percent_max': 37, 'carbs_percent_max': 46, 'protein_percent_max': 17, 'fiber_grams_max': 33, 'salt_max': 6},
    "DASH Diet": {'fat_percent_max': 40, 'carbs_percent_max': 60, 'protein_percent_max': 20, 'fiber_grams_max': 30, 'salt_max': 6},
    "Zone Diet": {'fat_percent_max': 30, 'carbs_percent_max': 40, 'protein_percent_max': 30, 'fiber_grams_max': 25, 'salt_max': 6},
    "Carnivore Diet": {'fat_percent_max': 75, 'carbs_percent_max': 0, 'protein_percent_max': 25, 'fiber_grams_max': 0, 'salt_max': 12},
    "Atkins Diet": {'fat_percent_max': 70, 'carbs_percent_max': 5, 'protein_percent_max': 25, 'fiber_grams_max': 35, 'salt_max': 5},
    "Pescatarian Diet": {'fat_percent_max': 30, 'carbs_percent_max': 55, 'protein_percent_max': 15, 'fiber_grams_max': 35, 'salt_max': 6},
    "Fruitarian Diet": {'fat_percent_max': 5, 'carbs_percent_max': 90, 'protein_percent_max': 5, 'fiber_grams_max': 30, 'salt_max': 6},
    "Military Diet": {'fat_percent_max': 35, 'carbs_percent_max': 55, 'protein_percent_max': 20, 'fiber_grams_max': 38, 'salt_max': 6},
    "Scandinavian Diet": {'fat_percent_max': 25, 'carbs_percent_max': 58, 'protein_percent_max': 17, 'fiber_grams_max': 35, 'salt_max': 6}
}

def get_diet_limits(diet):
    return DIET_LIMITS.get(diet) if diet else None

def calculate_remaining(all_values, diet, bmr=None):
    if not diet:
        return {}
        
    limits = DIET_LIMITS.get(diet)
    if not limits:
        return {}
        
    remaining = {}
    total_kcal = all_values.get('kcal', 1) or 1
    
    if bmr and 'kcal' in all_values:
        remaining['kcal'] = {
            'current': all_values['kcal'],
            'max': bmr,
            'remaining': max(0, bmr - all_values['kcal']),
            'percent': (all_values['kcal'] / bmr) * 100 if bmr else 0
        }
    
    for nutrient, kcal_per_gram in [('fat', 9), ('carbs', 4), ('protein', 4)]:
        if nutrient in all_values:
            grams = all_values[nutrient]
            max_percent = limits.get(f'{nutrient}_percent_max', 100)
            percent = (grams * kcal_per_gram) / total_kcal * 100 if total_kcal else 0
            
            remaining[nutrient] = {
                'grams': grams,
                'percent': percent,
                'max_percent': max_percent,
                'remaining_percent': max(0, max_percent - percent),
                'remaining_grams': max(0, (max_percent/100 * total_kcal / kcal_per_gram) - grams) if total_kcal and kcal_per_gram else 0
            }
    
    for nutrient, key in [('fiber', 'fiber_grams_max'), ('salt', 'salt_max')]:
        if nutrient in all_values:
            remaining[nutrient] = {
                'grams': all_values[nutrient],
                'max': limits[key],
                'remaining': max(0, limits[key] - all_values[nutrient])
            }
    
    return remaining

def get_diet_colors(diet, col_index, value, total_kcal, bmr=None):
    if col_index == 2 and bmr is not None and bmr > 0:
        percent = (value / bmr) * 100 if bmr else 0
        return {
            'foreground': COLOR_TEXT_DARK,
            'background': (COLOR_GREEN_BG if percent <= 100 else
                          COLOR_YELLOW_BG if percent <= 110 else
                          COLOR_RED_BG)
        }
    
    if not diet:
        return None
    
    color_map = {
        5: ('fat_percent_max', 9),
        3: ('carbs_percent_max', 4),
        6: ('protein_percent_max', 4),
        7: ('fiber_grams_max', 1),
        8: ('salt_max', 1)
    }
    
    if col_index not in color_map:
        return None
    
    limit_key, kcal_per_gram = color_map[col_index]
    max_val = DIET_LIMITS[diet].get(limit_key, 1) or 1
    
    if col_index in (7, 8):  # Fiber or Salt
        ratio = value / max_val if max_val > 0 else 0
    else:  # Fat, Carbs, Protein
        ratio = (value * kcal_per_gram) / total_kcal * 100 / max_val if (total_kcal and max_val > 0) else 0
    
    return {
        'foreground': COLOR_TEXT_DARK,
        'background': (COLOR_GREEN_BG if ratio <= 1 else
                      COLOR_YELLOW_BG if ratio <= 1.1 else
                      COLOR_RED_BG)
    }
