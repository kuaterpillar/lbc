#!/usr/bin/env python3
"""
Module d'analyse de marché pour détecter les bonnes affaires.

Utilise une base de données locale de prix (data/moto_prices.json)
pour estimer le prix de marché sans appels API externes.

Critères pépite:
- marge >= 60% du prix d'achat ET marge >= 1000€
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
    """
    db = _load_prices_db()
    if not db:
        return None

    title_norm = _normalize(title)

    # Score de matching pour chaque modèle
    best_match = None
    best_score = 0

    for key in db.keys():
        # Convertir clé en mots: HONDA_AFRICA_TWIN_1100 -> ["HONDA", "AFRICA", "TWIN", "1100"]
        key_words = key.split('_')

        # Compter combien de mots de la clé sont dans le titre
        score = 0
        for word in key_words:
            if word in title_norm:
                score += 1

        # Bonus si tous les mots sont présents
        if score == len(key_words):
            score += 10

        # Prendre le meilleur match
        if score > best_score and score >= 2:  # Au moins 2 mots en commun
            best_score = score
            best_match = key

    return best_match

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
    print("Test market_analyzer (base locale)")
    print("=" * 50)

    tests = [
        ("Honda Africa Twin 1100", 8000, "2022"),
        ("BMW R 1250 GS Adventure", 14000, "2021"),
        ("Yamaha MT-07", 4500, "2020"),
        ("Kawasaki Z900", 5000, "2019"),
        ("Triumph Street Triple 765 RS", 7000, "2022"),
    ]

    for title, price, year in tests:
        result = analyze_ad(title, price, year=year)
        status = "PEPITE" if result.is_good_deal else "Normal"
        market = f"{result.market_price:.0f}€" if result.market_price else "?"
        print(f"{status:7} | {title[:35]:35} | {price}€ vs {market} | {result.reason}")
