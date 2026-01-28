import lbc

def search_honda_motos():
    print("=== Recherche Motos Honda (>800cc, <50000km, <1500€) ===")
    
    client = lbc.Client()

    # Construction de l'URL avec les filtres demandés
    # category=3 -> Motos
    # text=Honda -> Marque
    # cubiccacity=800-max -> Cylindrée > 800cc
    # mileage=min-50000 -> Kilométrage < 50000km
    # price=min-1500 -> Prix < 1500€
    # sort=time -> Tri par les plus récentes
    
    category_id = lbc.Category.VEHICULES_MOTOS.value
    search_url = (
        f"https://www.leboncoin.fr/recherche"
        f"?category={category_id}"
        f"&text=Honda"
        f"&cubiccacity=800-max"
        f"&mileage=0-50000"
        f"&price=0-1500"
        f"&sort=time"
    )

    try:
        # Utilisation de la recherche par URL pour appliquer les filtres complexes
        print(f"URL utilisée: {search_url}")
        results = client.search(url=search_url, limit=50)
        
        print(f"\n{len(results.ads)} annonces trouvées :")
        for ad in results.ads:
            print(f"- {ad.subject} | {ad.price}€ | {ad.url}")
            
    except Exception as e:
        print(f"[ERREUR] La recherche a échoué : {e}")

if __name__ == "__main__":
    search_honda_motos()