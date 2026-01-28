# lbc — Client Python pour Leboncoin

Python >= 3.9 | Dépendance : `curl_cffi==0.11.3` | MIT

## Structure

```
lbc/
├── client.py          # Client (hérite des mixins), _fetch() avec retry sur 403
├── exceptions.py      # DatadomeError, NotFoundError, RequestError, InvalidValue
├── utils.py           # build_search_payload_with_args / with_url
├── mixin/
│   ├── session.py     # Session curl_cffi, proxy, impersonation, UA mobile
│   ├── search.py      # client.search() → POST /finder/search
│   ├── ad.py          # client.get_ad(id) → GET /adfinder/v1/classified/{id}
│   └── user.py        # client.get_user(id) → GET /user-card/v2/{id}/infos
└── model/
    ├── enums.py       # Category, Sort, Region, Department, AdType, OwnerType
    ├── city.py        # City(lat, lng, radius, city)
    ├── proxy.py       # Proxy(host, port, username, password, scheme)
    ├── ad.py          # Ad, Location, Attribute — ad.user est lazy-loaded
    ├── search.py      # Search(ads: List[Ad], total, max_pages, ...)
    └── user.py        # User, Feedback, Pro, Badge, Rating, Review
```

## Usage

```python
import lbc

client = lbc.Client(proxy=lbc.Proxy(host="...", port=8080))

# Recherche
result = client.search(
    text="maison",
    locations=[lbc.City(lat=48.86, lng=2.34, radius=10_000, city="Paris")],
    category=lbc.Category.IMMOBILIER,
    sort=lbc.Sort.NEWEST,
    price=[300_000, 700_000]
)
for ad in result.ads:
    print(ad.url, ad.title, ad.price)

# Ou par URL directe
result = client.search(url="https://www.leboncoin.fr/recherche?category=9&text=maison&...")

# Annonce & utilisateur
ad = client.get_ad(123456789)
print(ad.user.name)  # lazy load

user = client.get_user("uuid-here")
print(user.feedback.score, user.is_pro)
```

## Points clés

- **403 Datadome** : retries automatiques (défaut 5), réinitialisation de session à chaque tentative. Utiliser des proxies résidentiels français.
- **Impersonation** : navigateur aléatoire parmi safari, safari_ios, chrome_android, firefox.
- **kwargs** avancés dans `search()` : `price=[min, max]`, `square=[min, max]`, `real_estate_type=["3","4"]`, etc.
- **Proxy dynamique** : `client.proxy = proxy2` ou `client.proxy = None`.
- **Python réel requis** : le code utilise `match/case` (Python 3.10+), malgré `requires-python = ">=3.9"` dans pyproject.toml.

## Outils dev

- **ruff** : linter + formateur. Config dans `pyproject.toml`. Exécuter : `ruff check lbc/` / `ruff format lbc/`
- **pytest** : tests dans `tests/`. Exécuter : `pytest`
- **git** : initialisé. Associer votre remote GitHub : `git remote add origin <url>`
