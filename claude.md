# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Client Python non-officiel pour l'API LeBonCoin. Permet de rechercher des annonces, récupérer les détails d'une annonce et les informations d'un utilisateur.

## Commands

```bash
# Lint
ruff check lbc/
ruff check lbc/ --fix    # Auto-fix

# Format
ruff format lbc/

# Tests
pytest
pytest tests/test_specific.py -v    # Single test file

# Run monitor (Discord notifications)
python monitor.py              # Mode API (nécessite proxy)
python monitor.py --simulate   # Mode simulation
```

## Architecture

**Client avec Mixins** : `Client` hérite de 4 mixins qui séparent les responsabilités :
- `SessionMixin` : gestion session curl_cffi, proxy, impersonation navigateur
- `SearchMixin` : `client.search()` → POST /finder/search
- `AdMixin` : `client.get_ad(id)` → GET /adfinder/v1/classified/{id}
- `UserMixin` : `client.get_user(id)` → GET /user-card/v2/{id}/infos

**Retry automatique sur 403** : `Client._fetch()` réinitialise la session et retry jusqu'à `max_retries` fois en cas de blocage Datadome.

**Lazy loading** : `Ad.user` charge l'utilisateur à la demande via `client.get_user()`.

**Modèles** : dataclasses dans `lbc/model/` avec méthode statique `_build(raw, client)` pour construire depuis le JSON API.

## Key Files

| Fichier | Rôle |
|---------|------|
| `lbc/client.py` | Client principal, `_fetch()` avec retry |
| `lbc/utils.py` | `build_search_payload_with_args()` / `build_search_payload_with_url()` |
| `lbc/model/enums.py` | `Category`, `Sort`, `Region`, `Department` |
| `monitor.py` | Surveillance d'annonces + notifications Discord |
| `market_analyzer.py` | Estimation prix marché via DuckDuckGo + détection pépites |

## Market Analyzer (Analyse de Marché)

Module d'analyse pour détecter les bonnes affaires en comparant le prix annonce vs prix marché.

**Fonctionnement :**
1. Recherche du prix marché via DuckDuckGo (`ddgs`)
2. L'année de production est **toujours incluse** dans les requêtes pour des résultats précis
3. Calcul de la marge potentielle (prix marché - prix annonce)
4. Filtrage des "pépites" : marge ≥ 60% du prix d'achat ET marge ≥ 1000€

**Requêtes DuckDuckGo (avec année) :**
```
"{marque} {modèle} {année} prix occasion france"
"{marque} {modèle} {année} argus cote"
"{marque} {modèle} {année} a vendre occasion"
```

**Usage :**
```python
from market_analyzer import analyze_ad, search_market_price

# Recherche prix marché
price, sources = search_market_price("Honda Goldwing 1500", year="1995")

# Analyse complète
result = analyze_ad(
    title="Honda Goldwing 1500 SE",
    price=2000,
    brand="Honda",
    year="1995",
    category="moto"
)
print(f"Pépite: {result.is_good_deal}, Profit: {result.potential_profit}€")
```

**Dépendances :** `pip install ddgs`

## Usage Examples

```python
import lbc

client = lbc.Client(proxy=lbc.Proxy(host="...", port=8080))

# Recherche par arguments
result = client.search(
    text="honda",
    category=lbc.Category.VEHICULES_MOTOS,
    sort=lbc.Sort.NEWEST,
    price=[1000, 10000]
)

# Recherche par URL LeBonCoin
result = client.search(url="https://www.leboncoin.fr/recherche?...")

# Accès annonce et utilisateur
ad = client.get_ad(123456789)
print(ad.user.name)  # lazy load
```

## Important Notes

- **Python 3.10+ requis** : le code utilise `match/case` malgré `requires-python = ">=3.9"` dans pyproject.toml
- **Proxy résidentiel français recommandé** : pour éviter les blocages Datadome
- **Impersonation** : navigateur aléatoire (safari, chrome_android, firefox, safari_ios) si non spécifié

