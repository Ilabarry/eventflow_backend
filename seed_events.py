"""
Crée 5 événements pour organisateur2@gmail.com.
Usage : python scripts/seed_events.py
"""
import requests
from datetime import datetime, timezone

BASE_URL = "http://127.0.0.1:8000/api"
ORGANIZER_EMAIL = "organisateur2@gmail.com"
PASSWORD = "Password123"

def login(email: str, password: str) -> str:
    r = requests.post(
        f"{BASE_URL}/auth/login/",
        json={"email": email, "password": password},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["data"]["tokens"]["access"]

def get_categories(token: str) -> list:
    r = requests.get(
        f"{BASE_URL}/categories/",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["data"]

def create_event(token: str, title: str, category_id: str, format_type: str) -> str:
    """
    Crée un événement le 27/10/2026 à 15h00 (Africa/Dakar = UTC+0).
    format_type : 'ONLINE' ou 'IN_PERSON'
    """
    start = "2026-10-27T15:00:00+00:00"
    end = "2026-10-27T18:00:00+00:00"

    payload = {
        "title": title,
        "short_description": f"Événement de test — {title}",
        "description": f"<p>Description complète de {title}.</p>",
        "format": format_type,
        "participation_type": "FREE",       # ← FREE pour simplifier (pas de paiement)
        "capacity_type": "LIMITED",
        "capacity_limit": 100,
        "start_at": start,
        "end_at": end,
        "city": "Dakar",
        "category": category_id,
    }
    if format_type == "IN_PERSON":
        payload["venue_name"] = "Centre de Conférence"
        payload["address"] = "Avenue Léopold Sédar Senghor"
    else:
        payload["online_platform"] = "Zoom"
        payload["access_url"] = "https://zoom.us/j/test-event"

    r = requests.post(
        f"{BASE_URL}/events/",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
        timeout=15,
    )
    if r.status_code == 201:
        event_id = r.json()["data"]["id"]
        print(f"✅ Événement créé : {title} ({event_id})")
        return event_id
    else:
        print(f"❌ Échec création {title} : {r.status_code} {r.text[:200]}")
        raise SystemExit(1)

def publish_event(token: str, event_id: str, title: str) -> None:
    r = requests.post(
        f"{BASE_URL}/events/{event_id}/publish/",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    if r.status_code == 200:
        print(f"✅ Événement publié : {title}")
    else:
        print(f"❌ Échec publication {title} : {r.status_code} {r.text[:200]}")

def main() -> None:
    print("🔐 Connexion organisateur…")
    token = login(ORGANIZER_EMAIL, PASSWORD)

    print("📂 Récupération des catégories…")
    categories = get_categories(token)
    if not categories:
        print("❌ Aucune catégorie disponible. Créez-en une d'abord.")
        return
    category_id = categories[0]["id"]

    titles = [
        "Atelier Bureautique",
        "Conférence Tech 2026",
        "Meetup Design",
        "Formation Marketing Digital",
        "Séminaire Leadership",
    ]
    formats = ["IN_PERSON", "ONLINE", "IN_PERSON", "ONLINE", "IN_PERSON"]

    event_ids = []
    for title, fmt in zip(titles, formats):
        event_id = create_event(token, title, category_id, fmt)
        publish_event(token, event_id, title)
        event_ids.append(event_id)

    print(f"\n✅ {len(event_ids)} événements créés et publiés")
    print("IDs :", event_ids)

if __name__ == "__main__":
    main()