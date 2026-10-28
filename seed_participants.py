"""
Crée 20 participants de test via l'API REST.
Usage : python scripts/seed_participants.py
"""
import sys
import requests

BASE_URL = "http://127.0.0.1:8000/api"
PASSWORD = "Password123"

def create_participant(index: int, last_name: str, phone: str) -> None:
    payload = {
        "first_name": f"Participant{index}",
        "last_name": last_name,
        "email": f"participant{index}@gmail.com",
        "phone": phone,
        "password": PASSWORD,
        "password_confirm": PASSWORD,
        "role": "participant",
    }
    r = requests.post(f"{BASE_URL}/auth/register/", json=payload, timeout=15)
    if r.status_code == 201:
        print(f"✅ Participant{index} ({last_name}) créé")
    elif r.status_code == 400 and "email" in r.text.lower():
        print(f"⏭  Participant{index} existe déjà")
    else:
        print(f"❌ Participant{index} : {r.status_code} {r.text[:200]}")

# Les noms varient pour rendre la liste réaliste
LAST_NAMES = [
    "Balde", "Sonko", "Diop", "Ndiaye", "Fall", "Sarr", "Gueye", "Ba",
    "Diallo", "Sow", "Faye", "Camara", "Cissé", "Mbaye", "Ndour",
    "Thiam", "Sy", "Kane", "Sagna", "Diatta",
]

def main() -> None:
    for i, last_name in enumerate(LAST_NAMES, start=3):
        phone = f"7870{i:05d}"   # 787000003, 787000004, ...
        create_participant(i, last_name, phone)

if __name__ == "__main__":
    main()