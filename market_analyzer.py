#!/usr/bin/env python3
"""
Module d'analyse de marché pour détecter les bonnes affaires.

Fonctionnalités:
1. Estimation du prix de marché via DuckDuckGo Search
2. Filtrage des "pépites" selon la rentabilité:
   - marge ≥ 60% du prix d'achat **ET**
   - marge ≥ 1000€
"""

import re
import statistics
from dataclasses import dataclass
from typing import Optional

from ddgs import DDGS

# =============================================================================
# CONFIGURATION
# =============================================================================

# Seuil de rentabilité:
# - marge (Prix_Marché - Prix_Annonce) ≥ 60% du prix d'achat
# - ET marge ≥ 1000€
PROFIT_MARGIN_PERCENT = 0.60  # 60% du prix d'achat
PROFIT_MARGIN_FIXED = 1000    # 1000€ minimum de bénéfice

# Seuil anti-faux positifs:
# Si le profit dépasse 200% du prix d'achat, c'est probablement une erreur d'estimation
MAX_PROFIT_PERCENT = 2.0  # 200% max (au-delà = estimation douteuse)

# =============================================================================
# STRUCTURES DE DONNÉES
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
# ESTIMATION DU PRIX DE MARCHÉ
# =============================================================================

def search_market_price(product_name: str, year: Optional[str] = None) -> tuple[Optional[float], list[str]]:
    """
    Recherche le prix de marché d'un produit via DuckDuckGo.

    Args:
        product_name: Nom du produit (ex: "Honda Goldwing 1500")
        year: Année du produit (optionnel)

    Returns:
        Tuple (prix_moyen, liste_sources)
    """
    prices = []
    sources = []

    # Plusieurs requêtes pour maximiser les chances de trouver des prix
    # L'année est TOUJOURS incluse quand disponible pour des résultats plus précis
    if year:
        queries = [
            f"{product_name} {year} prix occasion france",
            f"{product_name} {year} argus cote",
            f"{product_name} {year} a vendre occasion",
        ]
    else:
        queries = [
            f"{product_name} prix occasion france",
            f"{product_name} argus occasion",
            f"{product_name} a vendre",
        ]

    try:
        with DDGS() as ddgs:
            for query in queries[:2]:  # Limiter à 2 requêtes pour la vitesse
                results = list(ddgs.text(query, max_results=10))

                for result in results:
                    title = result.get("title", "")
                    body = result.get("body", "")
                    href = result.get("href", "")
                    text = f"{title} {body}"

                    # Extraire les prix - patterns multiples
                    # Format: 1234€, 1 234 €, 1.234€, 1234 EUR, 1234 euros
                    all_matches = []

                    # Pattern 1: nombre + symbole euro (€ ou \u20ac)
                    all_matches.extend(re.findall(r'(\d[\d\s\.\,\xa0]*\d)\s*[\u20ac€]', text))

                    # Pattern 2: nombre + EUR/euros
                    all_matches.extend(re.findall(r'(\d[\d\s\.\,\xa0]*\d)\s*(?:EUR|euros?)', text, re.IGNORECASE))

                    # Pattern 3: nombre simple (3-6 chiffres) + euro
                    all_matches.extend(re.findall(r'(\d{3,6})\s*[\u20ac€]', text))

                    # Pattern 4: "à partir de X €"
                    all_matches.extend(re.findall(r'(?:partir de|depuis|prix[:\s]+)(\d[\d\s]*)\s*[\u20ac€]', text, re.IGNORECASE))

                    for match in all_matches:
                        # Nettoyer: enlever espaces, points, virgules
                        price_str = re.sub(r'[\s\.\,\xa0]', '', str(match))
                        try:
                            price = int(price_str)
                            # Filtrer les prix aberrants
                            if 500 <= price <= 80000:
                                prices.append(price)
                                if href and href not in sources:
                                    sources.append(href)
                        except ValueError:
                            continue

                # Si on a assez de prix, on arrête
                if len(prices) >= 5:
                    break

    except Exception as e:
        print(f"[MARKET] Erreur recherche: {e}")
        return None, []

    if not prices:
        return None, sources

    # Filtrer les outliers avec IQR (InterQuartile Range)
    if len(prices) >= 4:
        sorted_prices = sorted(prices)
        q1 = sorted_prices[len(sorted_prices) // 4]
        q3 = sorted_prices[3 * len(sorted_prices) // 4]
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        prices = [p for p in prices if lower_bound <= p <= upper_bound]

    if not prices:
        return None, sources

    # Calculer le prix médian (plus robuste que la moyenne)
    median_price = statistics.median(prices)

    return median_price, sources[:3]  # Retourner max 3 sources


def estimate_market_price(
    title: str,
    brand: Optional[str] = None,
    model: Optional[str] = None,
    year: Optional[str] = None,
    category: Optional[str] = None
) -> tuple[Optional[float], list[str]]:
    """
    Estime le prix de marché d'une annonce.

    Args:
        title: Titre de l'annonce
        brand: Marque (ex: "Honda")
        model: Modèle (ex: "Goldwing")
        year: Année
        category: Catégorie (ex: "moto")

    Returns:
        Tuple (prix_estimé, sources)
    """
    # Construire le nom du produit
    product_parts = []

    if brand:
        product_parts.append(brand)

    # Extraire le modèle du titre si non fourni
    if not model:
        # Essayer d'extraire le modèle du titre
        model = title

    product_parts.append(model)

    if category:
        product_parts.append(category)

    product_name = " ".join(product_parts)

    return search_market_price(product_name, year)


# =============================================================================
# ANALYSE DE RENTABILITÉ
# =============================================================================

def analyze_deal(ad_price: float, market_price: Optional[float], sources: list[str]) -> MarketAnalysis:
    """
    Analyse si une annonce est une bonne affaire.

    Règle: Prix_Marché > (Prix_Annonce * 1.6) + 1000€

    Args:
        ad_price: Prix de l'annonce
        market_price: Prix de marché estimé
        sources: Sources utilisées pour l'estimation

    Returns:
        MarketAnalysis avec les résultats
    """
    if market_price is None:
        return MarketAnalysis(
            ad_price=ad_price,
            market_price=None,
            price_sources=sources,
            potential_profit=None,
            is_good_deal=False,
            reason="Impossible d'estimer le prix de marché"
        )

    # Profit brut (en euros)
    potential_profit = market_price - ad_price

    # Seuils de profit demandés
    required_profit_pct = PROFIT_MARGIN_PERCENT * ad_price      # ex: 60% du prix d'achat
    required_profit_abs = PROFIT_MARGIN_FIXED                   # ex: 1000€ minimum
    min_required_profit = max(required_profit_pct, required_profit_abs)

    # Vérifier si le profit est réaliste (anti-faux positifs)
    profit_ratio = potential_profit / ad_price if ad_price > 0 else 0
    is_realistic = profit_ratio <= MAX_PROFIT_PERCENT

    # Bonne affaire seulement si:
    # - profit >= 60% du prix d'achat
    # - ET profit >= 1000€
    # - ET profit <= 200% (sinon estimation douteuse)
    is_good_deal = potential_profit >= min_required_profit and is_realistic

    if is_good_deal:
        reason = (
            f"PEPITE! Profit potentiel: {potential_profit:.0f}€ "
            f"({profit_ratio*100:.0f}%, min requis: {min_required_profit:.0f}€)"
        )
    elif not is_realistic:
        reason = (
            f"Estimation douteuse: profit de {profit_ratio*100:.0f}% (>{MAX_PROFIT_PERCENT*100:.0f}% max). "
            "Le prix de marché estimé semble incorrect."
        )
    else:
        missing_value = max(0.0, min_required_profit - potential_profit)
        reason = (
            "Pas assez rentable. "
            f"Il manque environ {missing_value:.0f}€ de marge pour atteindre le seuil "
            f"({PROFIT_MARGIN_PERCENT*100:.0f}% et au moins {PROFIT_MARGIN_FIXED}€)."
        )

    return MarketAnalysis(
        ad_price=ad_price,
        market_price=market_price,
        price_sources=sources,
        potential_profit=potential_profit,
        is_good_deal=is_good_deal,
        reason=reason
    )


# =============================================================================
# FONCTION PRINCIPALE D'ANALYSE
# =============================================================================

def analyze_ad(
    title: str,
    price: float,
    brand: Optional[str] = None,
    year: Optional[str] = None,
    category: Optional[str] = None,
) -> MarketAnalysis:
    """
    Analyse complète d'une annonce.

    1. Estime le prix de marché via DuckDuckGo
    2. Vérifie si c'est une bonne affaire (>60% + 1000€)

    Args:
        title: Titre de l'annonce
        price: Prix demandé
        brand: Marque
        year: Année
        category: Catégorie

    Returns:
        MarketAnalysis avec résultat
    """
    # 1. Estimer le prix de marché
    market_price, sources = estimate_market_price(
        title=title,
        brand=brand,
        year=year,
        category=category
    )

    # 2. Analyser la rentabilité (prix marché vs prix annonce)
    return analyze_deal(price, market_price, sources)


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    # Test avec une annonce fictive
    print("Test du module market_analyzer")
    print("=" * 50)

    market_price, sources = search_market_price("Honda Goldwing 1500", "1995")
    print(f"Prix marché Honda Goldwing 1500 (1995): {market_price}€")
    print(f"Sources: {sources}")

    # Test analyse complète
    analysis = analyze_ad(
        title="Honda Goldwing 1500 SE",
        price=2000,
        brand="Honda",
        year="1995",
        category="moto"
    )

    print(f"\nAnalyse marché:")
    print(f"  Prix annonce: {analysis.ad_price}€")
    print(f"  Prix marché: {analysis.market_price}€")
    print(f"  Bonne affaire: {analysis.is_good_deal}")
    print(f"  Raison: {analysis.reason}")
