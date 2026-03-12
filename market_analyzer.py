#!/usr/bin/env python3
"""
Module d'analyse de marché pour détecter les bonnes affaires.

Utilise une base de données locale de prix (data/moto_prices.json)
pour estimer le prix de marché sans appels API externes.

Critères pépite:
- marge >= 60% du prix d'achat ET marge >= 1200€
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# =============================================================================
# CONFIGURATION
# =============================================================================

PROFIT_MARGIN_PERCENT = 0.60  # 60% du prix d'achat
PROFIT_MARGIN_FIXED = 1200    # 1200€ minimum
MIN_AD_PRICE = 500            # Ignorer annonces < 500€

PRICES_FILE = Path(__file__).parent / "data" / "moto_prices.json"

# =============================================================================
# CHARGEMENT BASE DE DONNÉES
# =============================================================================

_PRICES_DB: dict = {}

def _load_prices_db() -> dict:
    """Charge la base de données de prix."""
    global _PRICES_DB
    if _PRICES_DB:
        return _PRICES_DB

    if not PRICES_FILE.exists():
        print(f"[WARN] Fichier prix introuvable: {PRICES_FILE}")
        return {}

    try:
        with open(PRICES_FILE, encoding="utf-8") as f:
            _PRICES_DB = json.load(f)
        print(f"[MARKET] {len(_PRICES_DB)} modèles chargés")
        return _PRICES_DB
    except Exception as e:
        print(f"[WARN] Erreur chargement prix: {e}")
        return {}

# =============================================================================
# STRUCTURES
# =============================================================================

@dataclass
class MarketAnalysis:
    """Résultat de l'analyse de marché."""
    ad_price: float
    market_price: Optional[float]
    price_sources: list[str]
    potential_profit: Optional[float]
    is_good_deal: bool
    reason: str

# =============================================================================
# MATCHING TITRE -> MODÈLE
# =============================================================================

def _normalize(text: str) -> str:
    """Normalise un texte pour le matching."""
    text = text.upper()
    text = re.sub(r'[^A-Z0-9\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def _title_to_key(title: str) -> Optional[str]:
    """
    Convertit un titre d'annonce en clé de la base de données.

    Ex: "Honda Africa Twin 1100 Adventure" -> "HONDA_AFRICA_TWIN_1100"

    Utilise un matching strict par séquence :
    - Les mots de la clé doivent apparaître dans l'ordre dans le titre
    - TOUS les mots de la clé doivent être présents
    - En cas d'égalité, la clé la plus longue (plus spécifique) est privilégiée
    """
    db = _load_prices_db()
    if not db:
        return None

    title_norm = _normalize(title)
    title_words = title_norm.split()

    # Chercher tous les modèles qui matchent complètement
    valid_matches = []

    for key in db.keys():
        # Convertir clé en mots: HONDA_AFRICA_TWIN_1100 -> ["HONDA", "AFRICA", "TWIN", "1100"]
        key_words = key.split('_')

        # Vérifier que TOUS les mots de la clé apparaissent dans l'ordre dans le titre
        title_idx = 0
        matched_count = 0

        for key_word in key_words:
            # Chercher ce mot à partir de la position courante dans le titre
            found = False
            for i in range(title_idx, len(title_words)):
                if key_word == title_words[i]:
                    title_idx = i + 1  # Continuer après ce mot
                    matched_count += 1
                    found = True
                    break

            if not found:
                # Ce mot de la clé n'est pas dans le titre (ou pas dans l'ordre)
                break

        # Si TOUS les mots de la clé sont présents dans l'ordre, c'est un match valide
        if matched_count == len(key_words):
            valid_matches.append(key)

    # Si aucun match valide, retourner None
    if not valid_matches:
        return None

    # Tiebreaker : prendre la clé la plus longue (plus spécifique)
    # Ex: HONDA_AFRICA_TWIN_1100_ADVENTURE est plus spécifique que HONDA_AFRICA_TWIN_1100
    return max(valid_matches, key=lambda k: len(k.split('_')))

# =============================================================================
# RECHERCHE PRIX
# =============================================================================

def search_market_price(title: str, year: Optional[str] = None) -> tuple[Optional[float], list[str]]:
    """
    Recherche le prix de marché dans la base locale.

    Args:
        title: Titre de l'annonce
        year: Année du véhicule

    Returns:
        (prix_marché, ["Base locale"])
    """
    db = _load_prices_db()
    if not db:
        return None, []

    # Trouver le modèle correspondant
    key = _title_to_key(title)
    if not key or key not in db:
        return None, []

    prices = db[key]

    # Si année fournie, chercher le prix exact
    if year:
        year_str = str(year)
        if year_str in prices:
            price = prices[year_str]
            if price > 0:
                return float(price), [f"Base locale: {key}"]

    # Sinon, prendre le prix le plus récent disponible
    for y in sorted(prices.keys(), reverse=True):
        if prices[y] > 0:
            return float(prices[y]), [f"Base locale: {key} ({y})"]

    return None, []

# =============================================================================
# ANALYSE
# =============================================================================

def analyze_deal(ad_price: float, market_price: Optional[float], sources: list[str]) -> MarketAnalysis:
    """Analyse si une annonce est une bonne affaire."""

    if ad_price < MIN_AD_PRICE:
        return MarketAnalysis(
            ad_price=ad_price,
            market_price=market_price,
            price_sources=sources,
            potential_profit=None,
            is_good_deal=False,
            reason=f"Prix < {MIN_AD_PRICE}€"
        )

    if market_price is None:
        return MarketAnalysis(
            ad_price=ad_price,
            market_price=None,
            price_sources=sources,
            potential_profit=None,
            is_good_deal=False,
            reason="Modèle non reconnu"
        )

    potential_profit = market_price - ad_price
    required_profit = max(PROFIT_MARGIN_PERCENT * ad_price, PROFIT_MARGIN_FIXED)
    profit_ratio = potential_profit / ad_price if ad_price > 0 else 0

    is_good_deal = potential_profit >= required_profit

    if is_good_deal:
        reason = f"PEPITE! +{potential_profit:.0f}€ ({profit_ratio*100:.0f}%)"
    else:
        reason = f"Marge insuffisante: {potential_profit:.0f}€"

    return MarketAnalysis(
        ad_price=ad_price,
        market_price=market_price,
        price_sources=sources,
        potential_profit=potential_profit,
        is_good_deal=is_good_deal,
        reason=reason
    )

def analyze_ad(
    title: str,
    price: float,
    brand: Optional[str] = None,
    year: Optional[str] = None,
    category: Optional[str] = None,
) -> MarketAnalysis:
    """
    Analyse complète d'une annonce.

    Args:
        title: Titre de l'annonce
        price: Prix demandé
        brand: Marque (utilisé pour améliorer le matching)
        year: Année
        category: Ignoré (pour compatibilité)

    Returns:
        MarketAnalysis
    """
    # Construire titre enrichi si marque fournie
    search_title = title
    if brand and brand.upper() not in title.upper():
        search_title = f"{brand} {title}"

    market_price, sources = search_market_price(search_title, year)
    return analyze_deal(price, market_price, sources)

# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("TEST 1: Validation du matching strict par séquence (_title_to_key)")
    print("=" * 80)

    # Tests de matching strict
    matching_tests = [
        # (titre, clé_attendue, description)
        ("Honda Africa Twin 1100 Adventure", "HONDA_AFRICA_TWIN_1100", "Match complet"),
        ("Honda CB500X 2022", "HONDA_CB500X", "Match CB500X"),
        ("Honda CB500X 2022", None, "NE DOIT PAS matcher AFRICA_TWIN (faux positif)"),
        ("BMW R 1250 GS", "BMW_R_1250_GS", "Match BMW R 1250 GS"),
        ("BMW R 1250 GS Adventure", "BMW_R_1250_GS_ADVENTURE", "Tiebreaker: cle plus longue (plus specifique)"),
        ("Yamaha MT-07", "YAMAHA_MT_07", "Match modele simple"),
        ("Honda Goldwing 1800 Touring", "HONDA_GOLDWING_1800_TOURING", "Match Goldwing"),
        ("Kawasaki Ninja 650", "KAWASAKI_NINJA_650", "Match Ninja"),
    ]

    print(f"\n{'TITRE':<40} | {'CLÉ TROUVÉE':<30} | {'STATUT'}")
    print("-" * 80)

    for title, expected_key, description in matching_tests:
        found_key = _title_to_key(title)

        # Vérifier les cas spéciaux (faux positifs à éviter)
        if "NE DOIT PAS" in description:
            # Pour Honda CB500X, vérifier qu'il ne matche PAS AFRICA_TWIN
            if found_key and "AFRICA_TWIN" in found_key:
                status = "FAIL (faux positif)"
            elif found_key == "HONDA_CB500X":
                status = "OK (match correct)"
            else:
                status = "OK (pas de match)"
        else:
            # Cas normaux
            if found_key == expected_key:
                status = "OK"
            else:
                status = f"FAIL (attendu: {expected_key})"

        display_key = found_key if found_key else "Aucun match"
        print(f"{title:<40} | {display_key:<30} | {status}")

    print("\n" + "=" * 80)
    print("TEST 2: Analyse de marché complète")
    print("=" * 80)

    tests = [
        ("Honda Africa Twin 1100", 8000, "2022"),
        ("BMW R 1250 GS Adventure", 14000, "2021"),
        ("Yamaha MT-07", 4500, "2020"),
        ("Kawasaki Z900", 5000, "2019"),
        ("Triumph Street Triple 765 RS", 7000, "2022"),
    ]

    print(f"\n{'STATUT':<8} | {'TITRE':<35} | {'PRIX':<15} | {'RAISON'}")
    print("-" * 80)

    for title, price, year in tests:
        result = analyze_ad(title, price, year=year)
        status = "PEPITE" if result.is_good_deal else "Normal"
        market = f"{result.market_price:.0f}€" if result.market_price else "?"
        price_str = f"{price}€ vs {market}"
        print(f"{status:8} | {title[:35]:35} | {price_str:15} | {result.reason}")
