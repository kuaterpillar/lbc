import lbc
import time

def test_lbc_features():
    print("=== Démarrage du test complet de la librairie LBC ===")
    
    # 1. Initialisation du client
    # Note: Si vous avez des erreurs 403, envisagez d'utiliser un proxy résidentiel ici
    client = lbc.Client()
    print("[OK] Client initialisé")

    # 2. Test de Recherche (Search)
    print("\n--- Test de Recherche (Immobilier / Paris) ---")
    location = lbc.City(
        lat=48.8566,
        lng=2.3522,
        radius=5000,
        city="Paris"
    )

    try:
        results = client.search(
            text="appartement",
            locations=[location],
            category=lbc.Category.IMMOBILIER_LOCATIONS,
            sort=lbc.Sort.NEWEST,
            limit=5
        )
        print(f"[OK] Recherche effectuée. {len(results.ads)} annonces trouvées.")
        
        if not results.ads:
            print("[WARN] Aucune annonce trouvée, impossible de continuer les tests détaillés.")
            return

        first_ad = results.ads[0]
        print(f"    Exemple: {first_ad.subject} - {first_ad.price}€ (ID: {first_ad.id})")

    except Exception as e:
        print(f"[ERREUR] Échec de la recherche: {e}")
        return

    # Pause pour éviter le rate-limiting
    time.sleep(2)

    # 3. Test de récupération d'une annonce (Get Ad)
    print(f"\n--- Test de récupération de l'annonce ID {first_ad.id} ---")
    try:
        full_ad = client.get_ad(first_ad.id)
        print(f"[OK] Détails récupérés pour: {full_ad.subject}")
        print(f"    Description (extrait): {full_ad.body[:100]}...")
        print(f"    Vendeur: {full_ad.user.name} (Pro: {full_ad.user.pro is not None})")
    except Exception as e:
        print(f"[ERREUR] Échec de récupération de l'annonce: {e}")

    # 4. Test de récupération d'utilisateur (Get User)
    if full_ad.user and full_ad.user.id:
        print(f"\n--- Test de récupération de l'utilisateur ID {full_ad.user.id} ---")
        try:
            user = client.get_user(full_ad.user.id)
            print(f"[OK] Utilisateur récupéré: {user.name}")
            print(f"    Nombre d'annonces actives: {user.total_ads}")
        except Exception as e:
            print(f"[ERREUR] Échec de récupération de l'utilisateur: {e}")

if __name__ == "__main__":
    test_lbc_features()