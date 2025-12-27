# 🐋 Docker Cost Analyzer

Outil CLI pour analyser vos containers Docker et détecter :
- 💰 **Gaspillage de ressources** (CPU/RAM sur-provisionnés)
- 🔒 **Vulnérabilités de sécurité** (root, ports exposés, capabilities)
- 📊 **Calcul des coûts** en €/mois avec économies potentielles

## ✨ Fonctionnalités

### Analyse des Ressources
- Détection containers sur-provisionnés (CPU/RAM)
- Calcul des coûts de gaspillage
- Recommandations de dimensionnement optimales
- Estimation d'économies annuelles

### Analyse de Sécurité
- ⚠️ **CRITICAL** : Container root, mode privileged
- ⚠️ **HIGH** : Ports exposés internet, capabilities dangereuses
- ⚠️ **MEDIUM** : Secrets en env vars, security options désactivées
- ⚠️ **LOW** : Filesystem writable, images outdated

## 🚀 Installation
```bash
# Cloner le repo
git clone https://github.com/Pegasus04-Nathanael/docker-cost-analyzer.git
cd docker-cost-analyzer

# Installer dépendances
pip install -r requirements.txt
```

## 📖 Usage

### Scan rapide (overview)
```bash
python src/cli.py scan
```

### Scan détaillé (ressources + sécurité)
```bash
python src/cli.py scan --detailed
```

## 📊 Exemple de sortie
```
🔬 Analyse détaillée en cours...

💰 GASPILLAGE DE RESSOURCES
╭──────────────┬───────────┬──────────┬──────────┬────────────┬───────────╮
│ Container    │ Ressource │   Alloué │  Utilisé │ Gaspillage │ Coût/mois │
├──────────────┼───────────┼──────────┼──────────┼────────────┼───────────┤
│ api-backend  │ CPU       │ 2.00 vCPU│ 0.15 vCPU│        93% │   €54.12  │
│ api-backend  │ MEMORY    │  4.00 GB │  0.50 GB │        88% │   €25.33  │
╰──────────────┴───────────┴──────────┴──────────┴────────────┴───────────╯

🔒 PROBLÈMES DE SÉCURITÉ
Container: api-backend
  🔴 [CRITICAL] Container running as root
     Fix : Ajouter 'USER 1000' dans le Dockerfile

💰 Économie potentielle : €953/an
```

## 💰 Méthodologie des Coûts

Prix basés sur moyennes cloud providers (AWS, GCP, Azure) :
- **CPU** : €0.04/vCPU/heure
- **RAM** : €0.005/GB/heure

📖 Détails complets : [docs/PRICING.md](docs/PRICING.md)

**Précision** : ±30-50% selon votre configuration exacte

## 🛠️ Technologies

- **Python 3.10+**
- **Docker SDK** - Interaction avec Docker API
- **Click** - Framework CLI
- **Rich** - Affichage terminal élégant

## 📁 Structure du projet
```
docker-cost-analyzer/
├── src/
│   ├── cli.py                 # Point d'entrée CLI
│   ├── analyzers/
│   │   ├── resources.py       # Analyse CPU/RAM
│   │   └── security.py        # Analyse sécurité
│   └── reporting/             # (à venir)
├── docs/
│   └── PRICING.md            # Méthodologie coûts
├── requirements.txt
└── README.md
```

## 🧪 Tests
```bash
# Créer containers de test
docker run -d --name test-nginx --memory=4096m --cpus=2 nginx:alpine
docker run -d --name test-redis --privileged redis:alpine

# Analyser
python src/cli.py scan --detailed
```

## 🎯 Roadmap

- [x] Analyse ressources (CPU/RAM)
- [x] Analyse sécurité (8 checks)
- [x] Calcul coûts mensuels
- [ ] Performance analyzer
- [ ] Export rapports (JSON/HTML/Markdown)
- [ ] Tests unitaires
- [ ] Package PyPI

## 📄 License

MIT License - Voir [LICENSE](LICENSE)

## 👤 Auteur

**Nathanael Fetue Foko**
- GitHub: [@Pegasus04-Nathanael](https://github.com/Pegasus04-Nathanael)

## 🙏 Acknowledgments

- Docker SDK for Python
- Rich library pour terminal UI
- Cloud providers pricing data

---

⭐ **Star ce repo si cet outil vous aide à optimiser vos containers !**