# 💰 Méthodologie de Calcul des Coûts

## Vue d'ensemble

Docker Cost Analyzer estime les coûts mensuels du gaspillage de ressources basé sur les tarifs moyens des principaux cloud providers.

## Prix utilisés (Décembre 2025)
```python
COST_PER_CPU_HOUR = 0.04 €    # Par vCPU par heure
COST_PER_GB_HOUR = 0.005 €    # Par GB RAM par heure
HOURS_PER_MONTH = 730         # Moyenne (365 jours / 12 mois × 24h)
```

## Sources des prix

### AWS EC2 (région eu-west-3 Paris)

**Instances compute-optimized (c5) :**
- c5.large : 2 vCPU, 4GB → €0.092/h
- Prix par vCPU : €0.046/h
- Prix par GB : €0.023/h

**Instances standard (t3) :**
- t3.medium : 2 vCPU, 4GB → €0.0456/h
- Prix par vCPU : €0.0228/h
- Prix par GB : €0.0114/h

Source : https://aws.amazon.com/ec2/pricing/

### Google Cloud Platform (région europe-west1)

**n1-standard-1 :**
- 1 vCPU, 3.75GB → €0.04/h
- Prix par vCPU : €0.04/h
- Prix par GB : €0.0106/h

Source : https://cloud.google.com/compute/vm-instance-pricing

### Azure (région West Europe)

**Standard_B2s :**
- 2 vCPU, 4GB → €0.048/h
- Prix par vCPU : €0.024/h
- Prix par GB : €0.012/h

Source : https://azure.microsoft.com/pricing/calculator/

## Notre approche

**Nous utilisons une moyenne CONSERVATIVE :**
```
Prix vCPU/h :
- AWS c5 : €0.046
- GCP n1 : €0.040
- Azure B : €0.024
→ Moyenne : €0.037
→ Arrondi utilisé : €0.04 (conservateur)

Prix GB/h :
- AWS t3 : €0.0114
- GCP n1 : €0.0106
- Azure B : €0.012
→ Moyenne : €0.0113
→ Arrondi utilisé : €0.005 (sous-estimé volontairement)
```

**Pourquoi sous-estimer la RAM ?**
- Mieux vaut annoncer €100 d'économie et réaliser €150
- Que l'inverse (perte de crédibilité)

## Précision attendue

**±30-50% selon :**
- Votre cloud provider exact
- Votre région (US vs EU vs Asia)
- Type d'instance (burstable vs compute vs memory-optimized)
- Remises (reserved instances, committed use, spot)

## Cas d'usage des prix

### ✅ Pertinent pour :
- Infrastructure Kubernetes (tarification au pod)
- Serveurs mutualisés (plusieurs containers par VM)
- Calcul de coûts d'opportunité

### ⚠️ Moins pertinent pour :
- VM dédiées (DigitalOcean, Linode)
- Serveurs bare-metal
- Offres forfaitaires

## Objectif

**Identifier les gaspillages RELATIFS, pas calculer votre facture exacte.**

Exemples :
- Container A gaspille €100/mois → Priorité haute
- Container B gaspille €5/mois → Priorité basse

**Le ratio est juste, même si les montants absolus varient.**

## Configuration personnalisée (roadmap)

Version future : permettre de configurer vos propres prix.
```yaml
# config.yaml (futur)
pricing:
  cpu_per_hour: 0.025
  ram_per_hour: 0.008
  currency: EUR
  provider: aws
  region: eu-west-1
```

## Comparaison avec outils du marché

| Outil | Prix CPU/h | Prix RAM/h | Source |
|-------|------------|------------|--------|
| **Docker Cost Analyzer** | €0.04 | €0.005 | Moyenne AWS/GCP/Azure |
| Kubecost | $0.0316 | $0.0042 | AWS t3.medium moyenne |
| Infracost | $0.0416 | Variable | Database propriétaire |

## Questions fréquentes

**Q: Pourquoi mes coûts réels sont différents ?**  
R: Normal. Ces prix sont des moyennes. Utilisez-les pour comparer vos containers entre eux.

**Q: Mon DigitalOcean coûte 7€/mois pour 2GB, vous dites 7.27€ juste pour la RAM ?**  
R: DigitalOcean vend des packages (CPU+RAM+stockage). Nous calculons le coût MARGINAL de chaque ressource isolée.

**Q: Comment être plus précis ?**  
R: Configurez vos prix exacts dans la config (feature à venir).

---

*Dernière mise à jour : Décembre 2025*  
*Prix vérifiés sur sites officiels AWS, GCP, Azure*