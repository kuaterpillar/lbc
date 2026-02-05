#!/usr/bin/env python3
"""
Moniteur d'annonces LeBonCoin avec notifications Discord.

Ce script utilise la librairie lbc du projet pour surveiller les nouvelles
annonces et envoyer des notifications Discord.

Usage:
    python monitor.py              # Mode normal (appel API via lbc)
    python monitor.py --simulate   # Mode simulation (données fictives)

Variables d'environnement:
    DISCORD_WEBHOOK_URL : URL du webhook Discord pour les notifications
    LBC_PROXY_HOST      : (optionnel) Hôte du proxy
    LBC_PROXY_PORT      : (optionnel) Port du proxy
    LBC_PROXY_USER      : (optionnel) Utilisateur du proxy
    LBC_PROXY_PASS      : (optionnel) Mot de passe du proxy
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import requests

# Import de la librairie lbc du projet
import lbc
from market_analyzer import analyze_ad, MarketAnalysis, MIN_AD_PRICE

# =============================================================================
# CONFIGURATION
# =============================================================================

# Répertoire de stockage des annonces déjà vues (un fichier par recherche)
DATA_DIR = Path(__file__).parent / "data"

# URL du webhook Discord (à configurer via variable d'environnement)
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

# Activer l'analyse de marché pour détecter les pépites
MARKET_ANALYSIS_ENABLED = True


# =============================================================================
# CONFIGURATION DES RECHERCHES (depuis Discord Bot)
# =============================================================================

SEARCHES_FILE = Path(__file__).parent / "data" / "searches.json"

# Catégories (même mapping que discord_bot.py)
CATEGORIES = {
    1: lbc.Category.TOUTES_CATEGORIES,
    2: lbc.Category.VEHICULES_VOITURES,
    3: lbc.Category.VEHICULES_MOTOS,
    4: lbc.Category.IMMOBILIER_VENTES_IMMOBILIERES,
    5: lbc.Category.IMMOBILIER_LOCATIONS,
    6: lbc.Category.ELECTRONIQUE,
    7: lbc.Category.ELECTRONIQUE_TELEPHONES_ET_OBJETS_CONNECTES,
    8: lbc.Category.MAISON_ET_JARDIN_AMEUBLEMENT,
    9: lbc.Category.VEHICULES_VELOS,
    10: lbc.Category.ELECTRONIQUE_JEUX_VIDEO,
    11: lbc.Category.ELECTRONIQUE_CONSOLES,
    12: lbc.Category.ELECTRONIQUE_PHOTO_AUDIO_ET_VIDEO,
}

REGIONS = {
    1: lbc.Region.ILE_DE_FRANCE,
    2: lbc.Region.AUVERGNE_RHONE_ALPES,
    3: lbc.Region.NOUVELLE_AQUITAINE,
    4: lbc.Region.OCCITANIE,
    5: lbc.Region.HAUTS_DE_FRANCE,
    6: lbc.Region.PROVENCE_ALPES_COTE_DAZUR,
    7: lbc.Region.GRAND_EST,
    8: lbc.Region.PAYS_DE_LA_LOIRE,
    9: lbc.Region.BRETAGNE,
    10: lbc.Region.NORMANDIE,
}


def load_searches() -> dict:
    """Charge les recherches depuis le fichier JSON créé par le bot Discord."""
    if not SEARCHES_FILE.exists():
        print("[WARN] Aucun fichier searches.json trouvé")
        return {"searches": {}, "next_id": 1}
    try:
        with open(SEARCHES_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[WARN] Erreur lecture searches.json: {e}")
        return {"searches": {}, "next_id": 1}


def build_search_params(search: dict) -> dict:
    """Convertit une recherche du bot Discord en paramètres pour lbc.Client.search()."""
    params = {
        "text": search["text"],
        "category": CATEGORIES.get(search["category_id"], lbc.Category.TOUTES_CATEGORIES),
        "sort": lbc.Sort.NEWEST,
    }

    if search.get("price_min") or search.get("price_max"):
        params["price"] = [search.get("price_min") or 0, search.get("price_max") or 999999999]

    if search.get("region_id"):
        region = REGIONS.get(search["region_id"])
        if region:
            params["locations"] = [region]

    if search.get("year_min") or search.get("year_max"):
        params["regdate"] = [search.get("year_min") or 1900, search.get("year_max") or 2100]

    return params


# =============================================================================
# SIMULATION - Données fictives pour les tests
# =============================================================================


def get_simulated_data() -> list[lbc.Ad]:
    """
    Retourne des données simulées sous forme d'objets Ad.

    Utilisé pour tester le pipeline sans appel API réel.

    Returns:
        Liste d'objets Ad simulés.
    """
    # Création d'annonces simulées avec la structure réelle
    simulated_raw = [
        {
            "list_id": 2847593847,
            "subject": "Honda CB 500 F - Excellent etat",
            "price_cents": 450000,
            "url": "https://www.leboncoin.fr/motos/2847593847.htm",
            "first_publication_date": "2025-01-28T10:30:00",
            "index_date": "2025-01-28T10:30:00",
            "expiration_date": "2025-03-28T10:30:00",
            "status": "active",
            "category_id": "3",
            "category_name": "Motos",
            "body": "Belle Honda CB 500 F en excellent etat",
            "brand": "Honda",
            "ad_type": "offer",
            "has_phone": False,
            "images": {"urls_large": ["https://example.com/image1.jpg"]},
            "location": {
                "city_label": "Paris 75011",
                "city": "Paris",
                "zipcode": "75011",
                "department_name": "Paris",
                "region_name": "Ile-de-France",
                "lat": 48.86,
                "lng": 2.38,
            },
            "attributes": [
                {"key": "mileage", "value": "15000", "value_label": "15 000 km"},
                {"key": "regdate", "value": "2020", "value_label": "2020"},
            ],
            "owner": {"user_id": "user1"},
        },
        {
            "list_id": 2847593848,
            "subject": "Honda CBR 650 R - Premiere main",
            "price_cents": 780000,
            "url": "https://www.leboncoin.fr/motos/2847593848.htm",
            "first_publication_date": "2025-01-28T09:15:00",
            "index_date": "2025-01-28T09:15:00",
            "expiration_date": "2025-03-28T09:15:00",
            "status": "active",
            "category_id": "3",
            "category_name": "Motos",
            "body": "CBR 650 R premiere main, jamais chutee",
            "brand": "Honda",
            "ad_type": "offer",
            "has_phone": True,
            "images": {"urls_large": ["https://example.com/image2.jpg"]},
            "location": {
                "city_label": "Lyon 69003",
                "city": "Lyon",
                "zipcode": "69003",
                "department_name": "Rhone",
                "region_name": "Rhone-Alpes",
                "lat": 45.76,
                "lng": 4.85,
            },
            "attributes": [
                {"key": "mileage", "value": "8000", "value_label": "8 000 km"},
                {"key": "regdate", "value": "2022", "value_label": "2022"},
            ],
            "owner": {"user_id": "user2"},
        },
        {
            "list_id": 2847593849,
            "subject": "Honda Africa Twin CRF 1100",
            "price_cents": 1250000,
            "url": "https://www.leboncoin.fr/motos/2847593849.htm",
            "first_publication_date": "2025-01-28T08:00:00",
            "index_date": "2025-01-28T08:00:00",
            "expiration_date": "2025-03-28T08:00:00",
            "status": "active",
            "category_id": "3",
            "category_name": "Motos",
            "body": "Africa Twin en tres bon etat general",
            "brand": "Honda",
            "ad_type": "offer",
            "has_phone": False,
            "images": {"urls_large": ["https://example.com/image3.jpg"]},
            "location": {
                "city_label": "Marseille 13008",
                "city": "Marseille",
                "zipcode": "13008",
                "department_name": "Bouches-du-Rhone",
                "region_name": "Provence-Alpes-Cote d'Azur",
                "lat": 43.30,
                "lng": 5.37,
            },
            "attributes": [
                {"key": "mileage", "value": "22000", "value_label": "22 000 km"},
                {"key": "regdate", "value": "2021", "value_label": "2021"},
            ],
            "owner": {"user_id": "user3"},
        },
    ]

    # Construire les objets Ad à partir des données brutes
    return [lbc.Ad._build(raw=data, client=None) for data in simulated_raw]


# =============================================================================
# RÉCUPÉRATION DES ANNONCES VIA LA LIBRAIRIE LBC
# =============================================================================


def get_proxy() -> lbc.Proxy | None:
    """
    Construit un objet Proxy à partir des variables d'environnement.

    Returns:
        Objet Proxy configuré ou None si pas de proxy.
    """
    host = os.environ.get("LBC_PROXY_HOST")
    port = os.environ.get("LBC_PROXY_PORT")

    if not host or not port:
        return None

    return lbc.Proxy(
        host=host, port=int(port), username=os.environ.get("LBC_PROXY_USER"), password=os.environ.get("LBC_PROXY_PASS")
    )


def fetch_data(search_params: dict) -> list[lbc.Ad]:
    """
    Récupère les annonces depuis LeBonCoin via la librairie lbc.

    Args:
        search_params: Paramètres de recherche (text, category, price, etc.)

    La librairie gère automatiquement :
        - L'impersonation de navigateur (Safari, Chrome, Firefox)
        - Les retries sur erreur 403 Datadome
        - La réinitialisation de session

    Pour de meilleurs résultats, configurez un proxy résidentiel français
    via les variables d'environnement LBC_PROXY_*.

    Returns:
        Liste d'objets Ad représentant les annonces trouvées.

    Raises:
        lbc.DatadomeError: Si bloqué par Datadome après plusieurs tentatives.
        lbc.RequestError: En cas d'erreur réseau.
    """
    # Créer le client avec proxy optionnel
    proxy = get_proxy()
    client = lbc.Client(proxy=proxy)

    # Effectuer la recherche avec les paramètres fournis
    result: lbc.Search = client.search(**search_params)

    return result.ads


# =============================================================================
# GESTION DES ANNONCES VUES
# =============================================================================


def get_seen_file(search_id: str) -> Path:
    """Retourne le chemin du fichier des annonces vues pour une recherche."""
    return DATA_DIR / f"seen_{search_id}.json"


def load_seen_ads(search_id: str) -> set[str]:
    """
    Charge les IDs des annonces déjà vues pour une recherche.

    Args:
        search_id: ID de la recherche.

    Returns:
        Ensemble des IDs d'annonces déjà notifiées.
    """
    seen_file = get_seen_file(search_id)
    if not seen_file.exists():
        return set()

    try:
        with open(seen_file, encoding="utf-8") as f:
            data = json.load(f)
            return set(data.get("seen_ids", []))
    except (OSError, json.JSONDecodeError) as e:
        print(f"[WARN] Erreur lecture {seen_file}: {e}")
        return set()


def save_seen_ads(search_id: str, seen_ids: set[str]) -> None:
    """
    Sauvegarde les IDs des annonces vues pour une recherche.

    Args:
        search_id: ID de la recherche.
        seen_ids: Ensemble des IDs à sauvegarder.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    data = {"seen_ids": list(seen_ids), "last_update": datetime.now().isoformat(), "count": len(seen_ids)}

    with open(get_seen_file(search_id), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# =============================================================================
# FILTRAGE DES NOUVELLES ANNONCES
# =============================================================================


def filter_new_ads(ads: list[lbc.Ad], seen_ids: set[str]) -> list[lbc.Ad]:
    """
    Filtre les annonces pour ne garder que les nouvelles.

    Args:
        ads: Liste complète des annonces récupérées.
        seen_ids: Ensemble des IDs déjà vus.

    Returns:
        Liste des annonces jamais vues auparavant.
    """
    return [ad for ad in ads if str(ad.id) not in seen_ids]


# =============================================================================
# NOTIFICATIONS DISCORD
# =============================================================================


# Mots-clés indiquant une moto accidentée / à réparer (potentielle bonne affaire)
DAMAGED_KEYWORDS = [
    "accident", "accidente", "accidenté", "accidentée",
    "pour piece", "pour pièce", "pour pieces", "pour pièces",
    "a reparer", "à réparer", "a remettre en etat", "à remettre en état",
    "en panne", "ne demarre pas", "ne démarre pas",
    "moteur hs", "boite hs", "boîte hs",
    "epave", "épave", "sinistre", "sinistré", "sinistrée",
    "non roulant", "non roulante",
    "carte grise barree", "carte grise barrée",
    "casse", "cassé", "cassée",
    "chute", "chuté", "chutée", "chutee",
    "tomber", "tombée", "tombee",
    "sans ct", "sans controle technique",
    "pieces a changer", "pièces à changer",
    "beaucoup de travaux", "gros travaux",
]


def is_damaged_ad(ad: lbc.Ad) -> bool:
    """Détecte si une annonce concerne un véhicule accidenté ou à réparer."""
    text = f"{ad.title} {ad.body or ''}".lower()
    return any(kw in text for kw in DAMAGED_KEYWORDS)


def get_attribute_value(ad: lbc.Ad, key: str) -> str | None:
    """
    Récupère la valeur d'un attribut d'annonce par sa clé.

    Args:
        ad: Objet Ad.
        key: Clé de l'attribut (ex: "mileage", "regdate").

    Returns:
        Valeur de l'attribut ou None si non trouvé.
    """
    for attr in ad.attributes:
        if attr.key == key:
            return attr.value_label or attr.value
    return None


def format_discord_message(ad: lbc.Ad, market: MarketAnalysis | None = None) -> dict:
    """
    Formate une annonce en message Discord (embed).

    Args:
        ad: Objet Ad contenant les données de l'annonce.
        market: Résultat de l'analyse de marché (optionnel).

    Returns:
        Payload JSON pour l'API Discord webhooks.
    """
    is_pepite = market and market.is_good_deal
    damaged = is_damaged_ad(ad)

    # Construction de la description
    description_parts = []

    if ad.price:
        description_parts.append(f"**Prix:** {int(ad.price)} EUR")

    # Ajouter infos marché si disponible
    if market and market.market_price:
        description_parts.append(f"**Prix marché:** {int(market.market_price)} EUR")
        if market.potential_profit:
            profit_str = f"+{int(market.potential_profit)}" if market.potential_profit > 0 else str(int(market.potential_profit))
            description_parts.append(f"**Profit potentiel:** {profit_str} EUR")

    if ad.location and ad.location.city_label:
        description_parts.append(f"**Lieu:** {ad.location.city_label}")

    year = get_attribute_value(ad, "regdate")
    if year:
        description_parts.append(f"**Annee:** {year}")

    mileage = get_attribute_value(ad, "mileage")
    if mileage:
        description_parts.append(f"**Kilometrage:** {mileage}")

    if damaged:
        description_parts.append("\n**⚠️ ATTENTION: Accidenté / À réparer**")

    description = "\n".join(description_parts)

    # Embed Discord - couleur selon le type
    if damaged:
        title = f"🔴 ACCIDENTÉ: {ad.title}"
        color = 0xFF0000  # Rouge
    elif is_pepite:
        title = f"💎 PÉPITE: {ad.title}"
        color = 0xFFD700  # Or
    else:
        title = ad.title
        color = 0x00AA00  # Vert

    embed = {
        "title": title,
        "url": ad.url,
        "description": description,
        "color": color,
        "footer": {"text": f"LeBonCoin Monitor | {market.reason if market else ''}"},
        "timestamp": datetime.now().isoformat(),
    }

    # Ajouter l'image si disponible
    if ad.images and ad.images[0]:
        embed["thumbnail"] = {"url": ad.images[0]}

    return {"embeds": [embed]}


def analyze_ad_market(ad: lbc.Ad) -> MarketAnalysis | None:
    """
    Analyse le prix de marché d'une annonce.

    Args:
        ad: Objet Ad.

    Returns:
        MarketAnalysis ou None si analyse impossible.
    """
    if not MARKET_ANALYSIS_ENABLED:
        return None

    if not ad.price or ad.price < MIN_AD_PRICE:
        return None

    year = get_attribute_value(ad, "regdate")
    brand = ad.brand if hasattr(ad, "brand") else None

    try:
        return analyze_ad(
            title=ad.title,
            price=ad.price,
            brand=brand,
            year=year,
            category="moto" if "moto" in ad.title.lower() else None,
        )
    except Exception as e:
        print(f"[MARKET] Erreur analyse {ad.id}: {e}")
        return None


def send_discord_notification(ad: lbc.Ad, market: MarketAnalysis | None = None) -> bool:
    """
    Envoie une notification Discord pour une annonce.

    Args:
        ad: Objet Ad contenant les données de l'annonce.
        market: Résultat de l'analyse de marché (optionnel).

    Returns:
        True si l'envoi a réussi, False sinon.
    """
    is_pepite = market and market.is_good_deal

    if not DISCORD_WEBHOOK_URL:
        print("[WARN] DISCORD_WEBHOOK_URL non configure. Notification ignoree.")
        pepite_tag = " [PEPITE]" if is_pepite else ""
        print(f"  -> {ad.title}{pepite_tag} - {int(ad.price) if ad.price else 'N/A'} EUR")
        return False

    payload = format_discord_message(ad, market)

    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except requests.RequestException as e:
        print(f"[ERROR] Erreur envoi Discord: {e}")
        return False


# =============================================================================
# PROGRAMME PRINCIPAL
# =============================================================================


def process_search(search_id: str, search: dict, simulate: bool = False) -> tuple[int, int, int]:
    """
    Traite une recherche individuelle.

    Args:
        search_id: ID de la recherche.
        search: Configuration de la recherche.
        simulate: Si True, utilise des données simulées.

    Returns:
        Tuple (nouvelles_annonces, notifications_envoyees, pepites_detectees)
    """
    import time
    import random

    # Délai aléatoire pour éviter détection
    if not simulate:
        delay = random.uniform(3, 10)
        print(f"\n[SEARCH #{search_id}] {search['text']} (attente {delay:.1f}s)")
        time.sleep(delay)
    else:
        print(f"\n[SEARCH #{search_id}] {search['text']}")

    # 1. Récupérer les annonces
    try:
        if simulate:
            ads = get_simulated_data()
        else:
            search_params = build_search_params(search)
            ads = fetch_data(search_params)
        print(f"  [INFO] {len(ads)} annonce(s) recuperee(s)")
    except lbc.DatadomeError:
        print(f"  [SKIP] Bloque par Datadome")
        return 0, 0, 0
    except Exception as e:
        print(f"  [SKIP] Erreur: {e}")
        return 0, 0, 0

    # 2. Charger les annonces déjà vues pour cette recherche
    seen_ids = load_seen_ads(search_id)
    print(f"  [INFO] {len(seen_ids)} annonce(s) deja vue(s)")

    # 3. Filtrer les nouvelles annonces
    new_ads = filter_new_ads(ads, seen_ids)
    print(f"  [INFO] {len(new_ads)} nouvelle(s) annonce(s)")

    if not new_ads:
        return 0, 0, 0

    # 4. Analyser et envoyer les notifications
    success_count = 0
    pepite_count = 0

    for ad in new_ads:
        market = None
        if MARKET_ANALYSIS_ENABLED and ad.price and ad.price >= MIN_AD_PRICE:
            market = analyze_ad_market(ad)
            if market and market.is_good_deal:
                pepite_count += 1
                print(f"  [PEPITE] {ad.title} - Profit: {int(market.potential_profit)}€")

        if send_discord_notification(ad, market):
            success_count += 1

        seen_ids.add(str(ad.id))

    # 5. Sauvegarder les annonces vues
    save_seen_ads(search_id, seen_ids)

    return len(new_ads), success_count, pepite_count


def main(simulate: bool = False) -> int:
    """
    Point d'entrée principal du moniteur.

    Args:
        simulate: Si True, utilise des données simulées au lieu de l'API.

    Returns:
        Code de sortie (0 = succès, 1 = erreur).
    """
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Demarrage du moniteur...")

    # Charger les recherches depuis le fichier créé par le bot Discord
    searches_data = load_searches()
    searches = searches_data.get("searches", {})

    # Filtrer uniquement les recherches actives
    active_searches = {sid: s for sid, s in searches.items() if s.get("active", False)}

    if not active_searches:
        print("[INFO] Aucune recherche active trouvee")
        print("[HINT] Utilisez le bot Discord pour creer et activer des recherches")
        return 0

    print(f"[INFO] {len(active_searches)} recherche(s) active(s) sur {len(searches)} totale(s)")

    # Traiter chaque recherche active
    total_new = 0
    total_sent = 0
    total_pepites = 0

    for search_id, search in active_searches.items():
        new_ads, sent, pepites = process_search(search_id, search, simulate)
        total_new += new_ads
        total_sent += sent
        total_pepites += pepites

    # Résumé
    print(f"\n[RESUME]")
    print(f"  - Recherches traitees: {len(active_searches)}")
    print(f"  - Nouvelles annonces: {total_new}")
    print(f"  - Notifications envoyees: {total_sent}")
    if MARKET_ANALYSIS_ENABLED:
        print(f"  - Pepites detectees: {total_pepites}")

    print("[OK] Termine")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Moniteur d'annonces LeBonCoin avec notifications Discord")
    parser.add_argument("--simulate", "-s", action="store_true", help="Utiliser des donnees simulees au lieu de l'API")
    args = parser.parse_args()

    sys.exit(main(simulate=args.simulate))
