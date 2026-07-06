import datetime
import csv
import urllib.request
import io

# === НАЛАШТУВАННЯ ===
MEALS = [
    {"name": "Сніданок", "weight": 1.0, "workers_needed": 1},
    {"name": "Обід",     "weight": 1.0, "workers_needed": 1},
    {"name": "Вечеря",   "weight": 1.0, "workers_needed": 1}
]

# З якого прийому їжі починається перший день (наприклад, в перший день немає сніданку)
CAMP_START_MEAL = "Обід" 
# Яким прийомом їжі закінчується останній день (наприклад, в останній день тільки сніданок)
CAMP_END_MEAL = "Сніданок" 

MIN_REST_DAYS = 1

CAMP_END_DEFAULT = datetime.date(2026, 8, 2)

# Вага дитини відносно дорослого при розрахунку порцій (і відповідно норми чергувань)
KID_MEAL_WEIGHT = 0.5

# Фіксовані (ручні) чергування. Формат: {"ДД.ММ": {"Прийом їжі": "Назва групи"}}
FIXED_DUTIES = {
    
}

def parse_date(date_str):
    date_str = date_str.strip()
    if not date_str:
        raise ValueError("порожнє значення дати")
        
    try:
        day, month = map(int, date_str.split('.'))
        return datetime.date(2026, month, day)
    except Exception as e:
        raise ValueError(f"невірний формат дати '{date_str}', очікується DD.MM")

def fetch_and_parse_data():
    print("Читання даних з локального файлу data.csv...")
    groups = []
    with open('data.csv', 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        try:
            next(reader) # Skip header
        except StopIteration:
            pass
        
        for row_idx, row in enumerate(reader, start=2):
            if len(row) < 3 or not row[0].strip():
                continue
            
            name = row[0].strip()
            size_str = row[1].strip()
            
            try:
                if '+' in size_str:
                    parts = size_str.split('+')
                    adults = int(parts[0].strip())
                    kids = int(parts[1].strip())
                else:
                    adults = int(size_str)
                    kids = 0
            except ValueError:
                raise ValueError(f"Рядок {row_idx}: Невірна кількість людей для '{name}': '{row[1]}'")
                
            dates = row[2].split('-')
            if len(dates) != 2:
                raise ValueError(f"Рядок {row_idx}: Невірний формат періоду для '{name}': '{row[2]}'. Очікується 'DD.MM-DD.MM'")
                
            try:
                start_date = parse_date(dates[0])
                end_date = parse_date(dates[1])
            except ValueError as e:
                raise ValueError(f"Рядок {row_idx} ({name}): {e}")
            
            groups.append({
                "name": name,
                "adults": adults,
                "kids": kids,
                "eating_size": adults + KID_MEAL_WEIGHT * kids,
                "work_size": adults,
                "start": start_date,
                "end": end_date,
                "target": 0.0,
                "earned": 0.0,
                "last_cooked_date": datetime.date(2026, 7, 1),
                "cook_count": 0,
                "meal_counts": {"Сніданок": 0, "Обід": 0, "Вечеря": 0}
            })
    return groups

groups = fetch_and_parse_data()
camp_start = min(g["start"] for g in groups)
camp_end = max(g["end"] for g in groups)

schedule = []
meal_index = 0
current_date = camp_start
meal_order = [m["name"] for m in MEALS]

# Карта зафіксованих дат для кожної групи
fixed_dates = {}
for d_str, meals in FIXED_DUTIES.items():
    d = parse_date(d_str)
    for m_name, g_name in meals.items():
        if g_name not in fixed_dates:
            fixed_dates[g_name] = []
        fixed_dates[g_name].append(d)

while current_date <= camp_end:
    for meal in MEALS:
        # Пропускаємо прийоми їжі до початку табору в перший день
        if current_date == camp_start:
            if meal_order.index(meal["name"]) < meal_order.index(CAMP_START_MEAL):
                continue
                
        # Пропускаємо прийоми їжі після завершення табору в останній день
        if current_date == camp_end:
            if meal_order.index(meal["name"]) > meal_order.index(CAMP_END_MEAL):
                continue
                
        meal_index += 1
        
        present_groups = [g for g in groups if g["start"] <= current_date <= g["end"]]
        if not present_groups:
            continue
            
        total_eating_size = sum(g["eating_size"] for g in present_groups)
        
        for g in present_groups:
            share = (g["eating_size"] / total_eating_size) * meal["weight"] if total_eating_size > 0 else 0
            g["target"] += share
            
        # Перевірка на зафіксовані чергування
        date_str = current_date.strftime('%d.%m')
        fixed_group_name = FIXED_DUTIES.get(date_str, {}).get(meal["name"])
        
        assigned = []
        if fixed_group_name:
            for g in present_groups:
                if g["name"] == fixed_group_name:
                    assigned.append(g)
                    g["last_cooked_date"] = current_date
                    g["cook_count"] += 1
                    break
            if not assigned:
                print(f"ПОПЕРЕДЖЕННЯ: Зафіксована група '{fixed_group_name}' відсутня в таборі на {date_str} ({meal['name']})")
        
        if not assigned:
            available_groups = []
            for rest in range(MIN_REST_DAYS, -1, -1):
                available_groups = []
                for g in present_groups:
                    if (current_date - g["last_cooked_date"]).days <= rest:
                        continue
                    too_close = False
                    for f_date in fixed_dates.get(g["name"], []):
                        if abs((f_date - current_date).days) <= rest:
                            too_close = True
                            break
                    if too_close:
                        continue
                    available_groups.append(g)
                if available_groups:
                    break
            
            DIVERSITY_PENALTY = 1.0
            
            def calculate_score(g):
                deficit = g["target"] - g["earned"]
                same_meal_count = g["meal_counts"][meal["name"]]
                return deficit - (same_meal_count * DIVERSITY_PENALTY)
                
            available_groups.sort(key=calculate_score, reverse=True)
            
            for g in available_groups:
                if len(assigned) == 1 and g["work_size"] > 1:
                    continue
                assigned.append(g)
                g["last_cooked_date"] = current_date
                g["cook_count"] += 1
                if len(assigned) >= 2: break
                if len(assigned) == 1 and g["work_size"] > 1: break
                
        if assigned:
            total_assigned_work_size = sum(g["work_size"] for g in assigned)
            for g in assigned:
                g["earned"] += meal["weight"] * (g["work_size"] / total_assigned_work_size)
                g["meal_counts"][meal["name"]] += 1
                
        schedule.append({
            "date": current_date,
            "meal": meal["name"],
            "groups": [g["name"] for g in assigned]
        })
    current_date += datetime.timedelta(days=1)

print("\nГенерація файлу schedule_output.csv...")
with open('schedule_output.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(["Дата", "Прийом їжі", "Чергові"])
    for entry in schedule:
        names = " + ".join(entry["groups"]) if entry["groups"] else "НЕМАЄ КОМУ"
        writer.writerow([entry["date"].strftime('%d.%m.%Y'), entry["meal"], names])
        
    writer.writerow([])
    writer.writerow(["СТАТИСТИКА", "", ""])
    writer.writerow(["Група", "Мета (Борг)", "Відпрацьовано", "Різниця", "К-ть чергувань"])
    groups.sort(key=lambda x: x["target"], reverse=True)
    for g in groups:
        diff = g["earned"] - g["target"]
        writer.writerow([g['name'], round(g['target'], 1), round(g['earned'], 1), round(diff, 1), g['cook_count']])
        
    writer.writerow([])
    writer.writerow(["МАТРИЦЯ ЧЕРГУВАНЬ", "(С - Сніданок, О - Обід, В - Вечеря, '-' - відсутні)"])
    
    matrix_header = ["Група"]
    curr_d = camp_start
    dates_list = []
    while curr_d <= camp_end:
        dates_list.append(curr_d)
        matrix_header.append(curr_d.strftime('%d.%m'))
        curr_d += datetime.timedelta(days=1)
        
    writer.writerow(matrix_header)
    
    meal_letters = {"Сніданок": "С", "Обід": "О", "Вечеря": "В"}
    
    # Сортуємо групи для матриці в алфавітному порядку або за датою приїзду
    groups_for_matrix = sorted(groups, key=lambda x: (x["start"], x["name"]))
    
    for g in groups_for_matrix:
        row = [g["name"]]
        for d in dates_list:
            if g["start"] <= d <= g["end"]:
                cooked = ""
                for entry in schedule:
                    if entry["date"] == d and g["name"] in entry["groups"]:
                        cooked = meal_letters.get(entry["meal"], "+")
                        break
                row.append(cooked)
            else:
                row.append("-")
        writer.writerow(row)
        
    # Додаємо рядок з кількістю людей
    people_count_row = ["Всього людей"]
    for d in dates_list:
        adults_sum = sum(g["adults"] for g in groups if g["start"] <= d <= g["end"])
        kids_sum = sum(g["kids"] for g in groups if g["start"] <= d <= g["end"])
        people_count_row.append(f"{adults_sum}+{kids_sum}")
    writer.writerow(people_count_row)
        
print("Готово!")
