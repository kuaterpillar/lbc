# Resources & Setup Guide

Ce fichier a été généré automatiquement par Claude Code.

## 📊 Stack détectée

**Type de projet :** Python Library / API Client (Web Scraping)
**Technologies :** Python 3.9+, curl_cffi, pyproject.toml

## 🤖 Skills Claude Code installés

Les skills suivants ont été installés dans `.claude/skills/` :

| Skill | Description | Étoiles |
|---|---|---|
| **pdf** | Manipulation et génération de PDF | 400⭐ |
| **docx** | Création et édition de documents Word | 400⭐ |

**Pourquoi ces skills ?**

Pour une library Python API, ces skills aident à :
- Générer de la documentation professionnelle (PDF, Word)
- Créer des rapports automatisés
- Documenter les fonctionnalités de l'API

**Installer des skills supplémentaires :**
- Consulte [SkillsMP](https://skillsmp.com/categories/documentation) pour plus de skills documentation
- Cherche "python testing" sur [SkillsMP](https://skillsmp.com/categories/testing) pour des skills de test

## 🔌 APIs recommandées pour ce projet

### Scraping & Automation
- **Bright Data** : Proxies résidentiels premium pour scraping (éviter les blocages Datadome)
- **ScraperAPI** : API de scraping avec rotation de proxies automatique
- **Oxylabs** : Infrastructure proxy pour scraping à grande échelle

### Monitoring & Logging
- **Sentry** : Tracking d'erreurs et monitoring pour Python
- **DataDog** : Monitoring APM et logs
- **LogTail** : Logs centralisés pour Python apps

### Database & Storage
- **Supabase** : PostgreSQL + API REST/GraphQL pour stocker les données scrapées
- **MongoDB Atlas** : NoSQL cloud pour données non-structurées
- **Redis Cloud** : Cache distribué pour optimiser les requêtes

### APIs complémentaires
- **SendGrid** : Notifications email pour alertes de scraping
- **Twilio** : SMS pour alertes critiques (ex: blocage IP)

**Recherche d'APIs supplémentaires :**
- Consulte le [API Mega List](https://github.com/kuaterpillar/Ressources-claude-code/blob/master/API-mega-list-main/API-mega-list-main/README.md) (10 498 APIs)
- Catégories pertinentes : Automation (4 825 APIs), Developer Tools (2 652 APIs)

## 📦 Prochaines étapes

1. **Vérifie les skills installés** : `ls .claude/skills/`
2. **Configure les proxies** : Utilise Bright Data ou ScraperAPI pour contourner Datadome
3. **Ajoute du monitoring** : Intègre Sentry pour tracker les erreurs de scraping
4. **Setup database** : Supabase ou MongoDB pour stocker les annonces scrapées

## 💡 Tips pour ton projet lbc

- **Anti-blocage** : Utilise des proxies résidentiels français (recommandé dans le README)
- **Rate limiting** : Ajoute des delays entre requêtes (déjà mentionné pour éviter 403)
- **Tests** : Installe un skill de testing Python depuis SkillsMP pour automatiser les tests
- **CI/CD** : Configure GitHub Actions pour tester automatiquement les nouvelles versions

---

**Ressources complémentaires :**
- [SkillsMP](https://skillsmp.com) — 96 000+ skills Claude Code
- [API Mega List](https://github.com/kuaterpillar/Ressources-claude-code) — 10 498 APIs ouvertes
- [Skills by Project](https://github.com/kuaterpillar/Ressources-claude-code/blob/master/skills-by-project.md) — Guide skills par type de projet

---

Généré le 2026-01-28 23:40 avec [Claude Code](https://claude.com/claude-code)
