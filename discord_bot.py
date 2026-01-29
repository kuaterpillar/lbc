#!/usr/bin/env python3
"""
Bot Discord interactif pour surveiller les annonces LeBonCoin.
Supporte plusieurs recherches simultanées.

Commandes:
    !aide              - Affiche l'aide
    !new               - Créer une nouvelle recherche
    !list              - Liste toutes les recherches
    !delete <id>       - Supprimer une recherche
    !start <id>        - Démarrer une recherche
    !stop <id>         - Arrêter une recherche
    !startall          - Démarrer toutes les recherches
    !stopall           - Arrêter toutes les recherches
    !check <id>        - Vérification immédiate
    !category          - Liste les catégories
    !region            - Liste les régions
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

import discord
from discord.ext import commands, tasks

import lbc
from market_analyzer import analyze_ad, MarketAnalysis

# =============================================================================
# CONFIGURATION
# =============================================================================

# Activer/désactiver l'analyse de marché
MARKET_ANALYSIS_ENABLED = True

TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")

# Configuration Proxy (pour éviter les blocages Datadome)
# Recommandé: proxies résidentiels français (Bright Data, Oxylabs, etc.)
PROXY_HOST = os.environ.get("LBC_PROXY_HOST", "")
PROXY_PORT = os.environ.get("LBC_PROXY_PORT", "")
PROXY_USER = os.environ.get("LBC_PROXY_USER", "")
PROXY_PASS = os.environ.get("LBC_PROXY_PASS", "")


def get_proxy() -> lbc.Proxy | None:
    """Retourne un proxy configuré ou None."""
    if not PROXY_HOST or not PROXY_PORT:
        return None
    return lbc.Proxy(
        host=PROXY_HOST,
        port=int(PROXY_PORT),
        username=PROXY_USER if PROXY_USER else None,
        password=PROXY_PASS if PROXY_PASS else None
    )
DATA_DIR = Path(__file__).parent / "data"
SEARCHES_FILE = DATA_DIR / "searches.json"

# Intervalle de vérification en minutes
CHECK_INTERVAL = 15

# Catégories principales
CATEGORIES = {
    1: ("Toutes catégories", lbc.Category.TOUTES_CATEGORIES),
    2: ("Voitures", lbc.Category.VEHICULES_VOITURES),
    3: ("Motos", lbc.Category.VEHICULES_MOTOS),
    4: ("Immobilier - Ventes", lbc.Category.IMMOBILIER_VENTES_IMMOBILIERES),
    5: ("Immobilier - Locations", lbc.Category.IMMOBILIER_LOCATIONS),
    6: ("Informatique", lbc.Category.ELECTRONIQUE),
    7: ("Téléphones", lbc.Category.ELECTRONIQUE_TELEPHONES_ET_OBJETS_CONNECTES),
    8: ("Meubles", lbc.Category.MAISON_ET_JARDIN_AMEUBLEMENT),
    9: ("Vélos", lbc.Category.VEHICULES_VELOS),
    10: ("Jeux vidéo", lbc.Category.ELECTRONIQUE_JEUX_VIDEO),
    11: ("Consoles", lbc.Category.ELECTRONIQUE_CONSOLES),
    12: ("Photo/Audio/Vidéo", lbc.Category.ELECTRONIQUE_PHOTO_AUDIO_ET_VIDEO),
}

REGIONS = {
    1: ("Île-de-France", lbc.Region.ILE_DE_FRANCE),
    2: ("Auvergne-Rhône-Alpes", lbc.Region.AUVERGNE_RHONE_ALPES),
    3: ("Nouvelle-Aquitaine", lbc.Region.NOUVELLE_AQUITAINE),
    4: ("Occitanie", lbc.Region.OCCITANIE),
    5: ("Hauts-de-France", lbc.Region.HAUTS_DE_FRANCE),
    6: ("Provence-Alpes-Côte d'Azur", lbc.Region.PROVENCE_ALPES_COTE_DAZUR),
    7: ("Grand Est", lbc.Region.GRAND_EST),
    8: ("Pays de la Loire", lbc.Region.PAYS_DE_LA_LOIRE),
    9: ("Bretagne", lbc.Region.BRETAGNE),
    10: ("Normandie", lbc.Region.NORMANDIE),
}


# =============================================================================
# GESTION DES RECHERCHES
# =============================================================================

def load_searches() -> dict:
    """Charge toutes les recherches depuis le fichier JSON."""
    if not SEARCHES_FILE.exists():
        return {"searches": {}, "next_id": 1}
    try:
        with open(SEARCHES_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"searches": {}, "next_id": 1}


def save_searches(data: dict) -> None:
    """Sauvegarde les recherches."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(SEARCHES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_seen_file(search_id: str) -> Path:
    """Retourne le chemin du fichier des annonces vues pour une recherche."""
    return DATA_DIR / f"seen_{search_id}.json"


def load_seen_ads(search_id: str) -> set[str]:
    """Charge les IDs des annonces déjà vues pour une recherche."""
    seen_file = get_seen_file(search_id)
    if not seen_file.exists():
        return set()
    try:
        with open(seen_file, encoding="utf-8") as f:
            data = json.load(f)
            return set(data.get("seen_ids", []))
    except (json.JSONDecodeError, OSError):
        return set()


def save_seen_ads(search_id: str, seen_ids: set[str]) -> None:
    """Sauvegarde les IDs des annonces vues pour une recherche."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "seen_ids": list(seen_ids),
        "last_update": datetime.now().isoformat(),
        "count": len(seen_ids),
    }
    with open(get_seen_file(search_id), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# =============================================================================
# BOT DISCORD
# =============================================================================

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# État pour le wizard de création
user_wizards = {}


@bot.event
async def on_ready():
    print(f"[BOT] Connecté en tant que {bot.user}")
    print(f"[BOT] Serveurs: {[g.name for g in bot.guilds]}")
    monitor_loop.start()


# =============================================================================
# COMMANDES
# =============================================================================

@bot.command(name="aide")
async def aide(ctx):
    """Affiche l'aide."""
    embed = discord.Embed(
        title="🔍 LeBonCoin Monitor - Aide",
        description="Surveillez plusieurs recherches en même temps !",
        color=0x00AA00,
    )
    embed.add_field(
        name="📋 Gestion des recherches",
        value=(
            "`!new` - Créer une nouvelle recherche\n"
            "`!list` - Voir toutes les recherches\n"
            "`!delete <id>` - Supprimer une recherche\n"
            "`!info <id>` - Détails d'une recherche"
        ),
        inline=False,
    )
    embed.add_field(
        name="▶️ Contrôle",
        value=(
            "`!start <id>` - Démarrer une recherche\n"
            "`!stop <id>` - Arrêter une recherche\n"
            "`!startall` - Tout démarrer\n"
            "`!stopall` - Tout arrêter\n"
            "`!check <id>` - Vérif immédiate"
        ),
        inline=False,
    )
    embed.add_field(
        name="📚 Références",
        value=(
            "`!category` - Liste des catégories\n"
            "`!region` - Liste des régions"
        ),
        inline=False,
    )
    embed.add_field(
        name="🔒 Proxy",
        value=(
            "`!proxy` - Statut du proxy\n"
            "`!testproxy` - Tester la connexion"
        ),
        inline=False,
    )
    embed.set_footer(text=f"Vérification automatique toutes les {CHECK_INTERVAL} minutes")
    await ctx.send(embed=embed)


@bot.command(name="category")
async def category(ctx):
    """Liste les catégories disponibles."""
    lines = [f"`{k}` - {v[0]}" for k, v in CATEGORIES.items()]
    embed = discord.Embed(
        title="📁 Catégories disponibles",
        description="\n".join(lines),
        color=0x00AA00,
    )
    await ctx.send(embed=embed)


@bot.command(name="region")
async def region(ctx):
    """Liste les régions disponibles."""
    lines = [f"`{k}` - {v[0]}" for k, v in REGIONS.items()]
    embed = discord.Embed(
        title="📍 Régions disponibles",
        description="\n".join(lines) + "\n`0` - Toute la France",
        color=0x00AA00,
    )
    await ctx.send(embed=embed)


@bot.command(name="proxy")
async def proxy_status(ctx):
    """Affiche le statut du proxy."""
    proxy = get_proxy()

    if proxy:
        embed = discord.Embed(
            title="🔒 Proxy configuré",
            color=0x00AA00,
        )
        embed.add_field(name="Host", value=f"`{PROXY_HOST}`", inline=True)
        embed.add_field(name="Port", value=f"`{PROXY_PORT}`", inline=True)
        embed.add_field(name="Auth", value="✅ Oui" if PROXY_USER else "❌ Non", inline=True)
        embed.set_footer(text="Le proxy sera utilisé pour toutes les recherches")
    else:
        embed = discord.Embed(
            title="⚠️ Aucun proxy configuré",
            description="Sans proxy, tu risques d'être bloqué par Datadome.\n\n**Variables à configurer:**\n`LBC_PROXY_HOST`\n`LBC_PROXY_PORT`\n`LBC_PROXY_USER` (optionnel)\n`LBC_PROXY_PASS` (optionnel)",
            color=0xFF0000,
        )
        embed.add_field(
            name="🛒 Proxies recommandés",
            value="• [Bright Data](https://brightdata.com) - Résidentiels FR\n• [Oxylabs](https://oxylabs.io) - Résidentiels FR\n• [IPRoyal](https://iproyal.com) - Budget friendly",
            inline=False
        )

    await ctx.send(embed=embed)


@bot.command(name="testproxy")
async def test_proxy(ctx):
    """Teste la connexion avec le proxy."""
    proxy = get_proxy()

    if not proxy:
        await ctx.send("❌ Aucun proxy configuré. Utilise `!proxy` pour voir comment configurer.")
        return

    await ctx.send("🔄 Test de connexion en cours...")

    try:
        client = lbc.Client(proxy=proxy)
        result = client.search(text="test", limit=1)
        await ctx.send(f"✅ Proxy fonctionnel ! Connexion OK ({len(result.ads)} résultat)")
    except lbc.DatadomeError:
        await ctx.send("❌ Proxy bloqué par Datadome. Change de proxy ou attends.")
    except Exception as e:
        await ctx.send(f"❌ Erreur connexion: {e}")


@bot.command(name="new")
async def new_search(ctx):
    """Démarre le wizard de création d'une recherche."""
    user_id = ctx.author.id
    user_wizards[user_id] = {
        "step": 1,
        "channel_id": ctx.channel.id,
        "data": {}
    }

    embed = discord.Embed(
        title="🆕 Nouvelle recherche (1/7)",
        description="**Quel texte veux-tu rechercher ?**\n\nExemple: `honda goldwing`, `iphone 14`, `appartement`",
        color=0x3498DB,
    )
    embed.set_footer(text="Tape ta réponse ou 'annuler' pour quitter")
    await ctx.send(embed=embed)


@bot.event
async def on_message(message):
    # Ignorer les messages du bot
    if message.author == bot.user:
        return

    # Traiter les commandes d'abord
    ctx = await bot.get_context(message)
    if ctx.valid:
        await bot.process_commands(message)
        return

    # Vérifier si l'utilisateur est dans un wizard
    user_id = message.author.id
    if user_id in user_wizards:
        await handle_wizard(message)
        return

    await bot.process_commands(message)


async def handle_wizard(message):
    """Gère les étapes du wizard de création."""
    user_id = message.author.id
    wizard = user_wizards[user_id]
    content = message.content.strip()

    if content.lower() == "annuler":
        del user_wizards[user_id]
        await message.channel.send("❌ Création annulée.")
        return

    step = wizard["step"]

    if step == 1:  # Texte de recherche
        wizard["data"]["text"] = content
        wizard["step"] = 2

        lines = [f"`{k}` - {v[0]}" for k, v in CATEGORIES.items()]
        embed = discord.Embed(
            title="🆕 Nouvelle recherche (2/7)",
            description=f"**Choisis une catégorie (numéro) :**\n\n" + "\n".join(lines),
            color=0x3498DB,
        )
        await message.channel.send(embed=embed)

    elif step == 2:  # Catégorie
        try:
            cat_id = int(content)
            if cat_id not in CATEGORIES:
                await message.channel.send("❌ Numéro invalide. Réessaie.")
                return
            wizard["data"]["category_id"] = cat_id
            wizard["step"] = 3

            lines = [f"`{k}` - {v[0]}" for k, v in REGIONS.items()]
            embed = discord.Embed(
                title="🆕 Nouvelle recherche (3/7)",
                description=f"**Choisis une région (numéro) ou `0` pour toute la France :**\n\n" + "\n".join(lines) + "\n`0` - Toute la France",
                color=0x3498DB,
            )
            await message.channel.send(embed=embed)
        except ValueError:
            await message.channel.send("❌ Entre un numéro valide.")

    elif step == 3:  # Région
        try:
            reg_id = int(content)
            if reg_id != 0 and reg_id not in REGIONS:
                await message.channel.send("❌ Numéro invalide. Réessaie.")
                return
            wizard["data"]["region_id"] = reg_id if reg_id != 0 else None
            wizard["step"] = 4

            embed = discord.Embed(
                title="🆕 Nouvelle recherche (4/7)",
                description="**Prix minimum ? (en €)**\n\nExemple: `1000` ou `0` pour pas de minimum",
                color=0x3498DB,
            )
            await message.channel.send(embed=embed)
        except ValueError:
            await message.channel.send("❌ Entre un numéro valide.")

    elif step == 4:  # Prix min
        try:
            price_min = int(content)
            wizard["data"]["price_min"] = price_min if price_min > 0 else None
            wizard["step"] = 5

            embed = discord.Embed(
                title="🆕 Nouvelle recherche (5/7)",
                description="**Prix maximum ? (en €)**\n\nExemple: `5000` ou `0` pour pas de maximum",
                color=0x3498DB,
            )
            await message.channel.send(embed=embed)
        except ValueError:
            await message.channel.send("❌ Entre un numéro valide.")

    elif step == 5:  # Prix max
        try:
            price_max = int(content)
            wizard["data"]["price_max"] = price_max if price_max > 0 else None
            wizard["step"] = 6

            embed = discord.Embed(
                title="🆕 Nouvelle recherche (6/7)",
                description="**Année minimum ?** (pour véhicules/immobilier)\n\nExemple: `1990` ou `0` pour ignorer",
                color=0x3498DB,
            )
            await message.channel.send(embed=embed)
        except ValueError:
            await message.channel.send("❌ Entre un numéro valide.")

    elif step == 6:  # Année min
        try:
            year_min = int(content)
            wizard["data"]["year_min"] = year_min if year_min > 0 else None
            wizard["step"] = 7

            embed = discord.Embed(
                title="🆕 Nouvelle recherche (7/7)",
                description="**Année maximum ?**\n\nExemple: `2015` ou `0` pour ignorer",
                color=0x3498DB,
            )
            await message.channel.send(embed=embed)
        except ValueError:
            await message.channel.send("❌ Entre un numéro valide.")

    elif step == 7:  # Année max + Sauvegarde
        try:
            year_max = int(content)
            wizard["data"]["year_max"] = year_max if year_max > 0 else None

            # Sauvegarder la recherche
            data = load_searches()
            search_id = str(data["next_id"])
            data["next_id"] += 1

            data["searches"][search_id] = {
                "text": wizard["data"]["text"],
                "category_id": wizard["data"]["category_id"],
                "region_id": wizard["data"]["region_id"],
                "price_min": wizard["data"]["price_min"],
                "price_max": wizard["data"]["price_max"],
                "year_min": wizard["data"].get("year_min"),
                "year_max": wizard["data"].get("year_max"),
                "active": False,
                "channel_id": wizard["channel_id"],
                "created_at": datetime.now().isoformat(),
            }
            save_searches(data)

            del user_wizards[user_id]

            # Résumé
            cat_name = CATEGORIES[wizard["data"]["category_id"]][0]
            reg_name = REGIONS.get(wizard["data"]["region_id"], ("Toute la France",))[0] if wizard["data"]["region_id"] else "Toute la France"
            price_str = f"{wizard['data']['price_min'] or 0}€ - {wizard['data']['price_max'] or '∞'}€"
            year_str = "Non défini"
            if wizard["data"].get("year_min") or wizard["data"].get("year_max"):
                year_str = f"{wizard['data'].get('year_min') or '?'} - {wizard['data'].get('year_max') or '?'}"

            embed = discord.Embed(
                title=f"✅ Recherche #{search_id} créée !",
                color=0x00AA00,
            )
            embed.add_field(name="🔍 Texte", value=wizard["data"]["text"], inline=True)
            embed.add_field(name="📁 Catégorie", value=cat_name, inline=True)
            embed.add_field(name="📍 Région", value=reg_name, inline=True)
            embed.add_field(name="💰 Prix", value=price_str, inline=True)
            embed.add_field(name="📅 Année", value=year_str, inline=True)
            embed.set_footer(text=f"Utilise !start {search_id} pour démarrer le monitoring")
            await message.channel.send(embed=embed)

        except ValueError:
            await message.channel.send("❌ Entre un numéro valide.")


@bot.command(name="list")
async def list_searches(ctx):
    """Liste toutes les recherches."""
    data = load_searches()

    if not data["searches"]:
        await ctx.send("📭 Aucune recherche configurée. Utilise `!new` pour en créer une.")
        return

    embed = discord.Embed(
        title="📋 Mes recherches",
        color=0x00AA00,
    )

    for search_id, search in data["searches"].items():
        status = "🟢 Active" if search["active"] else "🔴 Inactive"
        cat_name = CATEGORIES.get(search["category_id"], ("?",))[0]
        price_str = ""
        if search["price_min"] or search["price_max"]:
            price_str = f" | {search['price_min'] or 0}-{search['price_max'] or '∞'}€"

        embed.add_field(
            name=f"#{search_id} - {search['text']}",
            value=f"{status} | {cat_name}{price_str}",
            inline=False,
        )

    embed.set_footer(text="!start <id> pour démarrer | !info <id> pour détails")
    await ctx.send(embed=embed)


@bot.command(name="info")
async def info_search(ctx, search_id: str = None):
    """Affiche les détails d'une recherche."""
    if not search_id:
        await ctx.send("❌ Usage: `!info <id>`")
        return

    data = load_searches()
    if search_id not in data["searches"]:
        await ctx.send(f"❌ Recherche #{search_id} introuvable.")
        return

    search = data["searches"][search_id]
    seen_count = len(load_seen_ads(search_id))

    status = "🟢 Active" if search["active"] else "🔴 Inactive"
    cat_name = CATEGORIES.get(search["category_id"], ("?",))[0]
    reg_name = REGIONS.get(search["region_id"], ("Toute la France",))[0] if search["region_id"] else "Toute la France"
    price_str = f"{search['price_min'] or 0}€ - {search['price_max'] or '∞'}€"
    year_str = "Non défini"
    if search.get("year_min") or search.get("year_max"):
        year_str = f"{search.get('year_min') or '?'} - {search.get('year_max') or '?'}"

    embed = discord.Embed(
        title=f"🔍 Recherche #{search_id}",
        color=0x00AA00 if search["active"] else 0xFF0000,
    )
    embed.add_field(name="📝 Texte", value=search["text"], inline=True)
    embed.add_field(name="📁 Catégorie", value=cat_name, inline=True)
    embed.add_field(name="📍 Région", value=reg_name, inline=True)
    embed.add_field(name="💰 Prix", value=price_str, inline=True)
    embed.add_field(name="📅 Année", value=year_str, inline=True)
    embed.add_field(name="📡 Status", value=status, inline=True)
    embed.add_field(name="👁️ Vues", value=str(seen_count), inline=True)
    await ctx.send(embed=embed)


@bot.command(name="delete")
async def delete_search(ctx, search_id: str = None):
    """Supprime une recherche."""
    if not search_id:
        await ctx.send("❌ Usage: `!delete <id>`")
        return

    data = load_searches()
    if search_id not in data["searches"]:
        await ctx.send(f"❌ Recherche #{search_id} introuvable.")
        return

    del data["searches"][search_id]
    save_searches(data)

    # Supprimer le fichier des annonces vues
    seen_file = get_seen_file(search_id)
    if seen_file.exists():
        seen_file.unlink()

    await ctx.send(f"✅ Recherche #{search_id} supprimée.")


@bot.command(name="start")
async def start_search(ctx, search_id: str = None):
    """Démarre une recherche."""
    if not search_id:
        await ctx.send("❌ Usage: `!start <id>`")
        return

    data = load_searches()
    if search_id not in data["searches"]:
        await ctx.send(f"❌ Recherche #{search_id} introuvable.")
        return

    data["searches"][search_id]["active"] = True
    data["searches"][search_id]["channel_id"] = ctx.channel.id
    save_searches(data)

    await ctx.send(f"✅ Recherche #{search_id} démarrée ! Vérification toutes les {CHECK_INTERVAL} min.")


@bot.command(name="stop")
async def stop_search(ctx, search_id: str = None):
    """Arrête une recherche."""
    if not search_id:
        await ctx.send("❌ Usage: `!stop <id>`")
        return

    data = load_searches()
    if search_id not in data["searches"]:
        await ctx.send(f"❌ Recherche #{search_id} introuvable.")
        return

    data["searches"][search_id]["active"] = False
    save_searches(data)

    await ctx.send(f"🛑 Recherche #{search_id} arrêtée.")


@bot.command(name="startall")
async def start_all(ctx):
    """Démarre toutes les recherches."""
    data = load_searches()
    count = 0
    for search_id in data["searches"]:
        data["searches"][search_id]["active"] = True
        data["searches"][search_id]["channel_id"] = ctx.channel.id
        count += 1
    save_searches(data)
    await ctx.send(f"✅ {count} recherche(s) démarrée(s) !")


@bot.command(name="stopall")
async def stop_all(ctx):
    """Arrête toutes les recherches."""
    data = load_searches()
    count = 0
    for search_id in data["searches"]:
        data["searches"][search_id]["active"] = False
        count += 1
    save_searches(data)
    await ctx.send(f"🛑 {count} recherche(s) arrêtée(s).")


@bot.command(name="check")
async def check_search(ctx, search_id: str = None):
    """Lance une vérification immédiate."""
    if not search_id:
        await ctx.send("❌ Usage: `!check <id>`")
        return

    data = load_searches()
    if search_id not in data["searches"]:
        await ctx.send(f"❌ Recherche #{search_id} introuvable.")
        return

    await ctx.send(f"🔍 Vérification de la recherche #{search_id}...")
    await do_check(search_id, data["searches"][search_id], ctx.channel)


# =============================================================================
# MONITORING
# =============================================================================

async def do_check(search_id: str, search: dict, channel):
    """Effectue une vérification pour une recherche."""
    try:
        # Construire les paramètres
        search_params = {
            "text": search["text"],
            "category": CATEGORIES[search["category_id"]][1],
            "sort": lbc.Sort.NEWEST,
        }

        if search["price_min"] or search["price_max"]:
            search_params["price"] = [search["price_min"] or 0, search["price_max"] or 999999999]

        if search["region_id"]:
            search_params["locations"] = [REGIONS[search["region_id"]][1]]

        # Filtre année (regdate)
        if search.get("year_min") or search.get("year_max"):
            search_params["regdate"] = [search.get("year_min") or 1900, search.get("year_max") or 2100]

        # Récupérer les annonces (avec proxy si configuré)
        proxy = get_proxy()
        client = lbc.Client(proxy=proxy)

        if proxy:
            print(f"[PROXY] Utilisation de {PROXY_HOST}:{PROXY_PORT}")

        result = client.search(**search_params)
        ads = result.ads

        # Filtrer les nouvelles
        seen_ids = load_seen_ads(search_id)
        new_ads = [ad for ad in ads if str(ad.id) not in seen_ids]

        if new_ads:
            # Analyser chaque annonce pour trouver les pépites
            pepites = []
            normal_ads = []

            for ad in new_ads:
                if MARKET_ANALYSIS_ENABLED and ad.price:
                    # Extraire les attributs
                    year = None
                    mileage = None
                    for attr in ad.attributes:
                        if attr.key == "regdate":
                            year = attr.value_label or attr.value
                        elif attr.key == "mileage":
                            mileage = attr.value_label or attr.value

                    # Analyser le marché
                    try:
                        market_analysis = analyze_ad(
                            title=ad.title,
                            price=ad.price,
                            brand=ad.brand,
                            year=year,
                            category="moto" if search["category_id"] == 3 else None,
                        )

                        if market_analysis.is_good_deal:
                            pepites.append((ad, market_analysis))
                        else:
                            normal_ads.append((ad, market_analysis))
                    except Exception as e:
                        print(f"[MARKET] Erreur analyse: {e}")
                        normal_ads.append((ad, None))
                else:
                    normal_ads.append((ad, None))

            # Afficher les PÉPITES en premier (en or!)
            if pepites:
                await channel.send(f"🏆 **{len(pepites)} PÉPITE(S) DÉTECTÉE(S)** pour *{search['text']}* :")

                for ad, market in pepites[:5]:
                    embed = discord.Embed(
                        title=f"💎 {ad.title}",
                        url=ad.url,
                        color=0xFFD700,  # Or
                    )
                    embed.add_field(name="💰 Prix annonce", value=f"{int(ad.price)} €", inline=True)
                    if market and market.market_price:
                        embed.add_field(name="📊 Prix marché", value=f"{int(market.market_price)} €", inline=True)
                        embed.add_field(name="📈 Profit potentiel", value=f"+{int(market.potential_profit)} €", inline=True)

                    if ad.location and ad.location.city_label:
                        embed.add_field(name="📍 Lieu", value=ad.location.city_label, inline=True)

                    for attr in ad.attributes:
                        if attr.key == "regdate":
                            embed.add_field(name="📅 Année", value=attr.value_label or attr.value, inline=True)
                        elif attr.key == "mileage":
                            embed.add_field(name="🛣️ Km", value=attr.value_label or attr.value, inline=True)

                    if ad.images and ad.images[0]:
                        embed.set_thumbnail(url=ad.images[0])

                    embed.set_footer(text=f"Recherche #{search_id} | {market.reason if market else ''}")
                    await channel.send(embed=embed)
                    seen_ids.add(str(ad.id))
                    await asyncio.sleep(1)

            # Afficher les annonces normales (résumé seulement)
            if normal_ads:
                skipped = len([a for a, m in normal_ads if m and not m.is_good_deal])
                shown = 0

                await channel.send(f"📋 **{len(normal_ads)} autre(s) annonce(s)** ({skipped} ignorée(s) car pas assez rentables)")

                for ad, market in normal_ads[:5]:
                    if market and not market.is_good_deal:
                        # Ignorer les annonces pas rentables (juste compter)
                        seen_ids.add(str(ad.id))
                        continue

                    shown += 1
                    embed = discord.Embed(
                        title=ad.title,
                        url=ad.url,
                        color=0x00AA00,
                    )
                    if ad.price:
                        embed.add_field(name="💰 Prix", value=f"{int(ad.price)} €", inline=True)
                    if ad.location and ad.location.city_label:
                        embed.add_field(name="📍 Lieu", value=ad.location.city_label, inline=True)

                    for attr in ad.attributes:
                        if attr.key == "regdate":
                            embed.add_field(name="📅 Année", value=attr.value_label or attr.value, inline=True)
                        elif attr.key == "mileage":
                            embed.add_field(name="🛣️ Km", value=attr.value_label or attr.value, inline=True)

                    if ad.images and ad.images[0]:
                        embed.set_thumbnail(url=ad.images[0])

                    embed.set_footer(text=f"Recherche #{search_id}")
                    await channel.send(embed=embed)
                    seen_ids.add(str(ad.id))
                    await asyncio.sleep(1)

                # Marquer toutes les autres comme vues
                for ad, _ in normal_ads[5:]:
                    seen_ids.add(str(ad.id))

            save_seen_ads(search_id, seen_ids)

            if len(new_ads) > 10:
                await channel.send(f"*...et {len(new_ads) - 10} autres annonces*")
        else:
            await channel.send(f"✅ Aucune nouvelle annonce pour *{search['text']}*.")

    except lbc.DatadomeError:
        await channel.send(f"⚠️ Recherche #{search_id}: Bloqué par Datadome. Réessayez plus tard.")
    except Exception as e:
        await channel.send(f"❌ Recherche #{search_id}: Erreur - {e}")


@tasks.loop(minutes=CHECK_INTERVAL)
async def monitor_loop():
    """Boucle de monitoring automatique."""
    data = load_searches()

    for search_id, search in data["searches"].items():
        if not search["active"] or not search.get("channel_id"):
            continue

        channel = bot.get_channel(search["channel_id"])
        if channel:
            await do_check(search_id, search, channel)
            await asyncio.sleep(5)  # Pause entre les recherches


@monitor_loop.before_loop
async def before_monitor():
    await bot.wait_until_ready()


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    if not TOKEN:
        print("Erreur: DISCORD_BOT_TOKEN non défini")
        print("Utilisez: DISCORD_BOT_TOKEN=token python discord_bot.py")
        exit(1)

    bot.run(TOKEN)
