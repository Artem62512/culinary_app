import re

SAMPLE = "белки 3 г, жиры 2.5 г, углеводы 4.7 г; 53.3 ккал Поставщики:ООО \"КОСМОЛ\""

def parse_kbju(text: str) -> dict:
    result = {"proteins": None, "fats": None, "carbs": None, "calories": None}
    # Белки, жиры, углеводы
    m = re.search(r"белки\s+([\d.,]+)\s*г", text, re.IGNORECASE)
    if m: result["proteins"] = float(m.group(1).replace(",", "."))
    m = re.search(r"жиры\s+([\d.,]+)\s*г", text, re.IGNORECASE)
    if m: result["fats"] = float(m.group(1).replace(",", "."))
    m = re.search(r"углеводы\s+([\d.,]+)\s*г", text, re.IGNORECASE)
    if m: result["carbs"] = float(m.group(1).replace(",", "."))
    # Калории
    m = re.search(r"([\d.,]+)\s*ккал", text, re.IGNORECASE)
    if m: result["calories"] = float(m.group(1).replace(",", "."))
    return result

def kbju_status(kbju: dict) -> str:
    vals = [kbju["calories"], kbju["proteins"], kbju["fats"], kbju["carbs"]]
    if all(v is not None for v in vals):
        return "full"
    if any(v is not None for v in vals):
        return "partial"
    return "missing"

if __name__ == "__main__":
    parsed = parse_kbju(SAMPLE)
    print("Parsed:", parsed)
    print("Status:", kbju_status(parsed))
