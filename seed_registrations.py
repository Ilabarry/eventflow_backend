"""
Inscrit 20 participants à 5 événements.
Usage : python scripts/seed_registrations.py
"""
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "http://127.0.0.1:8000/api"
PASSWORD = "Password123"
ORGANIZER_EMAIL = "organisateur2@gmail.com"

PARTICIPANT_EMAILS = [f"participant{i}@gmail.com" for i in range(3, 23)]

def login(email: str, password: str) -> str:
    r = requests.post(
        f"{BASE_URL}/auth/login/",
        json={"email": email, "password": password},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["data"]["tokens"]["access"]

def list_my_events(token: str) -> list:
    r = requests.get(
        f"{BASE_URL}/events/my/",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["data"]["results"]

def register(token: str, event_id: str) -> str:
    """Inscrit un participant. Retourne 'ok', 'already' ou 'error:<msg>'."""
    r = requests.post(
        f"{BASE_URL}/registrations/",
        headers={"Authorization": f"Bearer {token}"},
        json={"event_id": event_id},
        timeout=15,
    )
    if r.status_code == 201:
        return "ok"
    if r.status_code == 400 and "déjà" in r.text.lower():
        return "already"
    return f"error:{r.status_code}:{r.text[:150]}"

def process_participant(email: str, event_ids: list) -> tuple[str, dict]:
    try:
        token = login(email, PASSWORD)
    except Exception as e:
        return email, {"login_error": str(e)}

    stats = {"ok": 0, "already": 0, "errors": []}
    for eid in event_ids:
        res = register(token, eid)
        if res == "ok":
            stats["ok"] += 1
        elif res == "already":
            stats["already"] += 1
        else:
            stats["errors"].append(res)
    return email, stats

def main() -> None:
    print("🔐 Connexion organisateur…")
    org_token = login(ORGANIZER_EMAIL, PASSWORD)

    print("📋 Récupération des événements de l'organisateur…")
    events = list_my_events(org_token)
    if len(events) < 5:
        print(f"⚠️  Seulement {len(events)} événements trouvés. Lancez d'abord seed_events.py.")
        return

    event_ids = [e["id"] for e in events]
    print(f"→ {len(event_ids)} événements cibles\n")

    total_ok = 0
    total_already = 0
    total_errors = 0

    # Parallélisation contrôlée : 5 participants à la fois
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {
            pool.submit(process_participant, email, event_ids): email
            for email in PARTICIPANT_EMAILS
        }
        for future in as_completed(futures):
            email, stats = future.result()
            if "login_error" in stats:
                print(f"❌ {email} — connexion échouée : {stats['login_error']}")
                total_errors += 1
                continue
            total_ok += stats["ok"]
            total_already += stats["already"]
            total_errors += len(stats["errors"])
            label = "✅" if not stats["errors"] else "⚠️ "
            print(f"{label} {email} — {stats['ok']} ok, {stats['already']} déjà, {len(stats['errors'])} err")
            for err in stats["errors"][:2]:
                print(f"    {err}")

    print(f"\n📊 Bilan : {total_ok} inscriptions créées, {total_already} déjà existantes, {total_errors} erreurs")
    print(f"   Attendu : 20 participants × 5 événements = 100 inscriptions")

if __name__ == "__main__":
    main()