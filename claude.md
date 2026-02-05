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
| `monitor.py` | Surveillance d'annonces + notifications Discord + détection accidentés |
| `market_analyzer.py` | Estimation prix marché via base locale + détection pépites (≥1200€) |
| `data/moto_prices.json` | Base de données locale : 156 modèles motos, prix par année (2013-2025) |
| `data/searches.json` | Recherches actives configurées via le bot Discord |
| `discord_bot.py` | Bot Discord pour gérer les recherches (ajout/suppression/activation) |

## Market Analyzer (Analyse de Marché)

Module d'analyse pour détecter les bonnes affaires en comparant le prix annonce vs prix marché.

**Fonctionnement :**
1. Recherche du prix marché dans la base locale (`data/moto_prices.json`)
2. Matching du titre d'annonce vers une clé modèle (ex: `HONDA_AFRICA_TWIN_1100`)
3. Calcul de la marge potentielle (prix marché - prix annonce)
4. Filtrage des "pépites" : marge ≥ 60% du prix d'achat ET marge ≥ 1200€

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

**Dépendances :** Aucune (base locale uniquement)

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

## GitHub Actions Workflow

Le projet inclut un workflow GitHub Actions qui surveille LeBonCoin automatiquement.

**Fichier:** `.github/workflows/monitor.yml`

**Fonctionnement:**
1. Exécution automatique toutes les 15 minutes (cron)
2. Recherche les nouvelles annonces via `monitor.py`
3. Analyse de marché via base locale pour chaque annonce
4. Détection des pépites (marge ≥60% ET ≥1200€)
5. Détection des annonces accidentées (embed rouge Discord)
6. Envoi notifications Discord (webhook)
7. Sauvegarde des annonces vues dans `data/seen_{id}.json`

**Secrets GitHub requis:**
- `DISCORD_WEBHOOK_URL` : URL du webhook Discord

**Secrets optionnels (proxy):**
- `LBC_PROXY_HOST`, `LBC_PROXY_PORT`
- `LBC_PROXY_USER`, `LBC_PROXY_PASS`

**Exécution manuelle:**
```bash
# Via GitHub CLI
gh workflow run monitor.yml --field simulate=true

# Localement
python monitor.py --simulate
```

## Configuration des Recherches

Les recherches sont configurées via le bot Discord (`discord_bot.py`) et stockées dans `data/searches.json`. Le moniteur charge automatiquement les recherches actives.

```json
// data/searches.json (géré par le bot Discord)
{
    "searches": {
        "4": {
            "text": "honda moto",
            "category_id": 3,
            "region_id": 1,
            "price_min": 500,
            "price_max": 15000,
            "active": true
        }
    },
    "next_id": 5
}
```

## Détection des Accidentés

Le moniteur détecte automatiquement les annonces de véhicules accidentés ou à réparer via une liste de mots-clés (~30 termes). Ces annonces reçoivent un embed Discord **rouge** avec le préfixe "ACCIDENTÉ:".

**Couleurs Discord :**
- Vert (`0x00AA00`) : annonce normale
- Or (`0xFFD700`) : pépite (bonne affaire détectée)
- Rouge (`0xFF0000`) : véhicule accidenté / à réparer

## Important Notes

- **Python 3.10+ requis** : le code utilise `match/case` malgré `requires-python = ">=3.9"` dans pyproject.toml
- **Proxy résidentiel français recommandé** : pour éviter les blocages Datadome
- **Impersonation** : navigateur aléatoire (safari, chrome_android, firefox, safari_ios) si non spécifié
- **Prix minimum** : les annonces < 500€ sont ignorées par l'analyse de marché

