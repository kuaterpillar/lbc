#!/usr/bin/env python3
"""
Test: Recherche de motos 1500cc (2016-2025) en Île-de-France
et analyse des bonnes affaires via DuckDuckGo.
"""

import sys
import time
import io

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import lbc
from market_analyzer import analyze_ad

def main():
    print("=" * 60)
    print("RECHERCHE MOTOS 1500cc (2016-2025) - ILE-DE-FRANCE")
    print("=" * 60)

    # Initialiser le client LBC
    client = lbc.Client()
    print("[OK] Client LBC initialisé")

    # Recherche: motos en IDF, cylindrée ~1500cc (1400-1600), années 2016-2025
    print("\n[...] Recherche en cours sur LeBonCoin...")
    print("    Filtres: IDF, 1400-1600cc, 2016-2025")

    try:
        results = client.search(
            category=lbc.Category.VEHICULES_MOTOS,
            locations=lbc.Region.ILE_DE_FRANCE,
            sort=lbc.Sort.NEWEST,
            limit=20,
            regdate=[2016, 2025],           # Année de 2016 à 2025
            cubic_capacity=[1400, 1600],    # Cylindrée 1400-1600cc (~1500cc)
        )
        print(f"[OK] {len(results.ads)} annonces trouvées")
    except Exception as e:
        print(f"[ERREUR] Échec de la recherche: {e}")
        sys.exit(1)

    if not results.ads:
        print("[INFO] Aucune annonce trouvée avec ces critères.")
        sys.exit(0)

    # Analyser chaque annonce
    print("\n" + "=" * 60)
    print("ANALYSE DES ANNONCES")
    print("=" * 60)

    pepites = []

    for i, ad in enumerate(results.ads, 1):
        print(f"\n--- Annonce {i}/{len(results.ads)} ---")
        print(f"Titre: {ad.subject}")
        print(f"Prix: {ad.price}€")
        print(f"URL: {ad.url}")

        # Extraire l'année depuis les attributs si disponible
        year = None
        brand = None

        if hasattr(ad, 'attributes') and ad.attributes:
            for attr in ad.attributes:
                if attr.key == 'regdate':
                    year = str(attr.value) if attr.value else None
                elif attr.key == 'brand':
                    brand = attr.value_label or attr.value

        if not ad.price or ad.price <= 0:
            print("[SKIP] Prix non disponible")
            continue

        if ad.price < 500:
            print(f"[SKIP] Prix trop bas ({ad.price}€ < 500€)")
            continue

        # Analyse de marché via DuckDuckGo
        print(f"[...] Analyse du prix de marché (année: {year or 'N/A'})...")

        try:
            analysis = analyze_ad(
                title=ad.subject,
                price=ad.price,
                brand=brand,
                year=year,
                category="moto"
            )

            print(f"  Prix marché estimé: {analysis.market_price}€" if analysis.market_price else "  Prix marché: Non trouvé")
            print(f"  Profit potentiel: {analysis.potential_profit:.0f}€" if analysis.potential_profit else "  Profit: N/A")
            print(f"  Verdict: {analysis.reason}")

            if analysis.is_good_deal:
                pepites.append({
                    'ad': ad,
                    'analysis': analysis
                })
                print("  >>> PEPITE DETECTEE! <<<")

        except Exception as e:
            print(f"  [ERREUR] Analyse échouée: {e}")

        # Pause pour éviter le rate-limiting de DuckDuckGo
        time.sleep(1)

    # Résumé final
    print("\n" + "=" * 60)
    print("RESUME - PEPITES DETECTEES")
    print("=" * 60)

    if pepites:
        for p in pepites:
            ad = p['ad']
            a = p['analysis']
            print(f"\n{ad.subject}")
            print(f"  Prix: {ad.price}€ | Marché: {a.market_price}€ | Profit: {a.potential_profit:.0f}€")
            print(f"  URL: {ad.url}")
    else:
        print("\nAucune pépite détectée parmi les annonces analysées.")

    print(f"\nTotal: {len(pepites)} pépite(s) sur {len(results.ads)} annonces")


if __name__ == "__main__":
    main()
