import csv
from duty_scheduler import schedule, groups

with open('schedule_output.csv', 'w', newline='') as f:
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
