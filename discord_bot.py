#!/usr/bin/env python3
"""
Bot Discord pour piloter le workflow GitHub Actions LeBonCoin.

Ce bot ne fait PAS de monitoring lui-même. Il sert d'interface pour:
- Créer/modifier/supprimer des recherches (stockées dans data/searches.json)
- Déclencher le workflow GitHub Actions
- Activer/désactiver des recherches

Commandes:
    !aide              - Affiche l'aide
    !new               - Créer une nouvelle recherche
    !list              - Liste toutes les recherches
    !delete <id>       - Supprimer une recherche
    !start <id>        - Activer une recherche
    !stop <id>         - Désactiver une recherche
    !startall          - Activer toutes les recherches
    !stopall           - Désactiver toutes les recherches
    !run               - Déclencher le workflow manuellement
    !status            - Statut du dernier workflow
    !category          - Liste les catégories
    !region            - Liste les régions

Variables d'environnement:
    DISCORD_BOT_TOKEN  - Token du bot Discord
    GITHUB_TOKEN       - Token GitHub (repo scope) pour déclencher les workflows
    GITHUB_REPO        - Repo au format "owner/repo" (ex: "monuser/lbc-main")
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

import discord
import requests
from discord.ext import commands

import lbc

# =============================================================================
# CONFIGURATION
# =============================================================================

TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "")  # format: "owner/repo"

DATA_DIR = Path(__file__).parent / "data"
SEARCHES_FILE = DATA_DIR / "searches.json"


# =============================================================================
# GITHUB API
# =============================================================================

def github_headers() -> dict:
    """Headers pour l'API GitHub."""
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }


def trigger_workflow() -> tuple[bool, str]:
    """
    Déclenche le workflow GitHub Actions.

    Returns:
        (success, message)
    """
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return False, "GITHUB_TOKEN ou GITHUB_REPO non configuré"

    url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/monitor.yml/dispatches"

    try:
        resp = requests.post(
            url,
            headers=github_headers(),
            json={"ref": "main"},
            timeout=10,
        )
        if resp.status_code == 204:
            return True, "Workflow déclenché avec succès"
        return False, f"Erreur {resp.status_code}: {resp.text}"
    except Exception as e:
        return False, f"Erreur: {e}"


def get_workflow_status() -> dict | None:
    """
    Récupère le statut du dernier workflow.

    Returns:
        Dict avec les infos du workflow ou None.
    """
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return None

    url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/monitor.yml/runs"

    try:
        resp = requests.get(
            url,
            headers=github_headers(),
            params={"per_page": 1},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("workflow_runs"):
                return data["workflow_runs"][0]
        return None
    except Exception:
        return None


def commit_searches_to_github(searches_data: dict) -> tuple[bool, str]:
    """
    Commit le fichier searches.json sur GitHub.

    Args:
        searches_data: Données des recherches à sauvegarder.

    Returns:
        (success, message)
    """
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return False, "GITHUB_TOKEN ou GITHUB_REPO non configuré"

    import base64

    file_path = "data/searches.json"
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{file_path}"

    try:
        # Récupérer le SHA actuel du fichier (s'il existe)
        resp = requests.get(url, headers=github_headers(), timeout=10)
        sha = resp.json().get("sha") if resp.status_code == 200 else None

        # Préparer le contenu
        content = json.dumps(searches_data, indent=2, ensure_ascii=False)
        content_b64 = base64.b64encode(content.encode()).decode()

        # Créer ou mettre à jour
        payload = {
            "message": "Update searches.json via Discord bot",
            "content": content_b64,
            "branch": "main",
        }
        if sha:
            payload["sha"] = sha

        resp = requests.put(url, headers=github_headers(), json=payload, timeout=10)

        if resp.status_code in (200, 201):
            return True, "Configuration synchronisée avec GitHub"
        return False, f"Erreur {resp.status_code}: {resp.text}"
    except Exception as e:
        return False, f"Erreur: {e}"

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


def save_searches(data: dict, sync_github: bool = True) -> tuple[bool, str] | None:
    """
    Sauvegarde les recherches localement et sur GitHub.

    Args:
        data: Données des recherches.
        sync_github: Si True, synchronise aussi avec GitHub.

    Returns:
        (success, message) si sync_github, sinon None.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(SEARCHES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    if sync_github and GITHUB_TOKEN and GITHUB_REPO:
        return commit_searches_to_github(data)
    return None


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
    print(f"[BOT] GitHub Repo: {GITHUB_REPO or 'Non configuré'}")


# =============================================================================
# COMMANDES
# =============================================================================

@bot.command(name="aide")
async def aide(ctx):
    """Affiche l'aide."""
    embed = discord.Embed(
        title="🔍 LeBonCoin Monitor - Aide",
        description="Pilotez vos recherches LeBonCoin via GitHub Actions !",
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
            "`!start <id>` - Activer une recherche\n"
            "`!stop <id>` - Désactiver une recherche\n"
            "`!startall` - Tout activer\n"
            "`!stopall` - Tout désactiver"
        ),
        inline=False,
    )
    embed.add_field(
        name="🚀 GitHub Actions",
        value=(
            "`!run` - Déclencher le workflow maintenant\n"
            "`!status` - Statut du dernier workflow\n"
            "`!sync` - Synchroniser config avec GitHub"
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
    embed.set_footer(text="Le monitoring tourne sur GitHub Actions toutes les 15 min")
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


@bot.command(name="run")
async def run_workflow(ctx):
    """Déclenche le workflow GitHub Actions manuellement."""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        await ctx.send("❌ `GITHUB_TOKEN` ou `GITHUB_REPO` non configuré.")
        return

    await ctx.send("🚀 Déclenchement du workflow...")

    success, message = trigger_workflow()
    if success:
        await ctx.send(f"✅ {message}\n📍 Le monitoring va s'exécuter dans quelques secondes.")
    else:
        await ctx.send(f"❌ {message}")


@bot.command(name="status")
async def workflow_status(ctx):
    """Affiche le statut du dernier workflow."""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        await ctx.send("❌ `GITHUB_TOKEN` ou `GITHUB_REPO` non configuré.")
        return

    run = get_workflow_status()
    if not run:
        await ctx.send("❌ Impossible de récupérer le statut.")
        return

    status_emoji = {
        "completed": "✅",
        "in_progress": "🔄",
        "queued": "⏳",
        "failure": "❌",
        "cancelled": "🚫",
    }.get(run.get("status"), "❓")

    conclusion_emoji = {
        "success": "✅",
        "failure": "❌",
        "cancelled": "🚫",
    }.get(run.get("conclusion"), "")

    embed = discord.Embed(
        title="📊 Dernier workflow",
        url=run.get("html_url"),
        color=0x00AA00 if run.get("conclusion") == "success" else 0xFF0000,
    )
    embed.add_field(name="Status", value=f"{status_emoji} {run.get('status')}", inline=True)
    if run.get("conclusion"):
        embed.add_field(name="Résultat", value=f"{conclusion_emoji} {run.get('conclusion')}", inline=True)
    embed.add_field(name="Démarré", value=run.get("created_at", "?")[:19].replace("T", " "), inline=True)
    embed.set_footer(text=f"Run #{run.get('run_number')}")

    await ctx.send(embed=embed)


@bot.command(name="sync")
async def sync_github(ctx):
    """Synchronise la configuration avec GitHub."""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        await ctx.send("❌ `GITHUB_TOKEN` ou `GITHUB_REPO` non configuré.")
        return

    await ctx.send("🔄 Synchronisation avec GitHub...")

    data = load_searches()
    success, message = commit_searches_to_github(data)

    if success:
        await ctx.send(f"✅ {message}")
    else:
        await ctx.send(f"❌ {message}")


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
            result = save_searches(data)

            del user_wizards[user_id]

            # Résumé
            cat_name = CATEGORIES[wizard["data"]["category_id"]][0]
            reg_name = REGIONS.get(wizard["data"]["region_id"], ("Toute la France",))[0] if wizard["data"]["region_id"] else "Toute la France"
            price_str = f"{wizard['data']['price_min'] or 0}€ - {wizard['data']['price_max'] or '∞'}€"
            year_str = "Non défini"
            if wizard["data"].get("year_min") or wizard["data"].get("year_max"):
                year_str = f"{wizard['data'].get('year_min') or '?'} - {wizard['data'].get('year_max') or '?'}"

            sync_status = "✅ Synchronisé avec GitHub" if (result and result[0]) else "⚠️ Non synchronisé"

            embed = discord.Embed(
                title=f"✅ Recherche #{search_id} créée !",
                color=0x00AA00,
            )
            embed.add_field(name="🔍 Texte", value=wizard["data"]["text"], inline=True)
            embed.add_field(name="📁 Catégorie", value=cat_name, inline=True)
            embed.add_field(name="📍 Région", value=reg_name, inline=True)
            embed.add_field(name="💰 Prix", value=price_str, inline=True)
            embed.add_field(name="📅 Année", value=year_str, inline=True)
            embed.add_field(name="🔄 GitHub", value=sync_status, inline=True)
            embed.set_footer(text=f"!start {search_id} pour activer | !run pour lancer maintenant")
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
    result = save_searches(data)

    # Supprimer le fichier des annonces vues
    seen_file = get_seen_file(search_id)
    if seen_file.exists():
        seen_file.unlink()

    if result and result[0]:
        await ctx.send(f"✅ Recherche #{search_id} supprimée et synchronisée avec GitHub.")
    else:
        await ctx.send(f"✅ Recherche #{search_id} supprimée.")


@bot.command(name="start")
async def start_search(ctx, search_id: str = None):
    """Active une recherche."""
    if not search_id:
        await ctx.send("❌ Usage: `!start <id>`")
        return

    data = load_searches()
    if search_id not in data["searches"]:
        await ctx.send(f"❌ Recherche #{search_id} introuvable.")
        return

    data["searches"][search_id]["active"] = True
    data["searches"][search_id]["channel_id"] = ctx.channel.id
    result = save_searches(data)

    if result and result[0]:
        await ctx.send(f"✅ Recherche #{search_id} activée et synchronisée avec GitHub !")
    else:
        await ctx.send(f"✅ Recherche #{search_id} activée (sync GitHub: {result[1] if result else 'non configuré'})")


@bot.command(name="stop")
async def stop_search(ctx, search_id: str = None):
    """Désactive une recherche."""
    if not search_id:
        await ctx.send("❌ Usage: `!stop <id>`")
        return

    data = load_searches()
    if search_id not in data["searches"]:
        await ctx.send(f"❌ Recherche #{search_id} introuvable.")
        return

    data["searches"][search_id]["active"] = False
    result = save_searches(data)

    if result and result[0]:
        await ctx.send(f"🛑 Recherche #{search_id} désactivée et synchronisée avec GitHub.")
    else:
        await ctx.send(f"🛑 Recherche #{search_id} désactivée.")


@bot.command(name="startall")
async def start_all(ctx):
    """Active toutes les recherches."""
    data = load_searches()
    count = 0
    for search_id in data["searches"]:
        data["searches"][search_id]["active"] = True
        data["searches"][search_id]["channel_id"] = ctx.channel.id
        count += 1
    result = save_searches(data)

    if result and result[0]:
        await ctx.send(f"✅ {count} recherche(s) activée(s) et synchronisée(s) avec GitHub !")
    else:
        await ctx.send(f"✅ {count} recherche(s) activée(s).")


@bot.command(name="stopall")
async def stop_all(ctx):
    """Désactive toutes les recherches."""
    data = load_searches()
    count = 0
    for search_id in data["searches"]:
        data["searches"][search_id]["active"] = False
        count += 1
    result = save_searches(data)

    if result and result[0]:
        await ctx.send(f"🛑 {count} recherche(s) désactivée(s) et synchronisée(s) avec GitHub.")
    else:
        await ctx.send(f"🛑 {count} recherche(s) désactivée(s).")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    if not TOKEN:
        print("Erreur: DISCORD_BOT_TOKEN non défini")
        print("Définir: DISCORD_BOT_TOKEN, GITHUB_TOKEN, GITHUB_REPO")
        exit(1)

    if not GITHUB_TOKEN or not GITHUB_REPO:
        print("⚠️  GITHUB_TOKEN ou GITHUB_REPO non défini")
        print("   Le bot fonctionnera mais ne pourra pas synchroniser avec GitHub Actions")

    bot.run(TOKEN)
