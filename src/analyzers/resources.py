"""
RESOURCES.PY - Analyseur de gaspillage de ressources

Détecte les containers sur-provisionnés et calcule les coûts
"""

from dataclasses import dataclass
from typing import Dict, Optional
import statistics


@dataclass
class ResourceWaste:
    """Données d'un gaspillage détecté"""
    resource_type: str              # 'cpu' ou 'memory'
    allocated: float                # Quantité allouée
    used: float                     # Quantité utilisée
    waste_percent: float            # % de gaspillage
    waste_amount: float             # Quantité gaspillée
    monthly_cost_waste: float       # €/mois gaspillés
    recommendation: str             # Texte de recommandation


class ResourceAnalyzer:
    """
    Analyse gaspillage de ressources et calcule coûts
    
    Prix basés sur moyennes cloud (AWS/GCP/Azure, EU West, Jan 2025):
    - AWS EC2 t3.medium: €0.0456/h
    - GCP n1-standard-1: €0.04/h  
    - Azure Standard_B2s: €0.048/h
    
    Sources:
    - https://aws.amazon.com/ec2/pricing/
    - https://cloud.google.com/compute/vm-instance-pricing
    - https://azure.microsoft.com/pricing/
    """
    
    # Prix moyens cloud (€/heure)
    COST_PER_CPU_HOUR = 0.04        # €/vCPU/h
    COST_PER_GB_HOUR = 0.005        # €/GB/h
    
    # Conversion mensuel (730h = moyenne mois)
    HOURS_PER_MONTH = 730
    
    # Seuils de gaspillage
    WASTE_THRESHOLD_CPU = 20        # Si <20% utilisé = waste
    WASTE_THRESHOLD_MEMORY = 30     # Si <30% utilisé = waste
    
    def __init__(self, container):
        """
        Args:
            container: Objet Docker container
        """
        self.container = container
        self.metrics_history = []
    
    def collect_metrics(self, samples=3, interval=2):
        """
        Collecte plusieurs échantillons de métriques
        
        Args:
            samples: Nombre d'échantillons à prendre
            interval: Secondes entre échantillons
            
        Returns:
            List de métriques
        """
        import time
        
        metrics = []
        for i in range(samples):
            try:
                stats = self.container.stats(stream=False)
                metric = self._parse_stats(stats)
                metrics.append(metric)
                
                if i < samples - 1:  # Pas de sleep après le dernier
                    time.sleep(interval)
            except Exception as e:
                print(f"Erreur collecte métrique {i}: {e}")
                continue
        
        self.metrics_history = metrics
        return metrics
    
    def _parse_stats(self, stats: dict) -> dict:
        """Parse stats Docker vers format simple"""
        
        # ─────── CPU ───────
        cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - \
                   stats['precpu_stats']['cpu_usage']['total_usage']
        system_delta = stats['cpu_stats']['system_cpu_usage'] - \
                      stats['precpu_stats']['system_cpu_usage']
        online_cpus = stats['cpu_stats'].get('online_cpus', 1)
        
        cpu_percent = 0.0
        if system_delta > 0 and cpu_delta > 0:
            cpu_percent = (cpu_delta / system_delta) * online_cpus * 100
        
        # ─────── Memory ───────
        mem_usage = stats['memory_stats'].get('usage', 0)
        mem_limit = stats['memory_stats'].get('limit', 1)
        
        # Si pas de limite définie, utiliser total système
        if mem_limit == 0:
            mem_limit = stats['memory_stats'].get('max_usage', mem_usage * 2)
        
        mem_percent = (mem_usage / mem_limit) * 100 if mem_limit > 0 else 0
        
        return {
            'cpu_percent': cpu_percent,
            'cpu_limit': online_cpus,
            'memory_usage_bytes': mem_usage,
            'memory_limit_bytes': mem_limit,
            'memory_percent': mem_percent
        }
    
    def analyze(self) -> Dict[str, ResourceWaste]:
        """
        Analyse complète : détecte gaspillage CPU + Memory
        
        Returns:
            Dict avec clés 'cpu' et/ou 'memory' si gaspillage
        """
        
        # Collecter métriques si pas déjà fait
        if not self.metrics_history:
            self.collect_metrics(samples=3, interval=2)
        
        if not self.metrics_history:
            return {}
        
        wastes = {}
        
        # Moyennes sur tous les échantillons
        avg_cpu_percent = statistics.mean(
            m['cpu_percent'] for m in self.metrics_history
        )
        avg_mem_percent = statistics.mean(
            m['memory_percent'] for m in self.metrics_history
        )
        
        # Limites (prendre du premier échantillon)
        cpu_limit = self.metrics_history[0]['cpu_limit']
        mem_limit_bytes = self.metrics_history[0]['memory_limit_bytes']
        mem_limit_gb = mem_limit_bytes / (1024 ** 3)
        
        # ═══════════════════════════════════════════════════
        # Analyse CPU
        # ═══════════════════════════════════════════════════
        if avg_cpu_percent < self.WASTE_THRESHOLD_CPU:
            # Calcul gaspillage
            cpu_used = (avg_cpu_percent / 100) * cpu_limit
            cpu_wasted = cpu_limit - cpu_used
            waste_percent = (cpu_wasted / cpu_limit) * 100
            
            # Calcul coût mensuel gaspillé
            monthly_cost = cpu_wasted * self.COST_PER_CPU_HOUR * self.HOURS_PER_MONTH
            
            # Recommandation : usage × 1.5 (buffer 50%)
            recommended_cpu = max(0.25, cpu_used * 1.5)  # Min 0.25 CPU
            
            wastes['cpu'] = ResourceWaste(
                resource_type='cpu',
                allocated=cpu_limit,
                used=cpu_used,
                waste_percent=waste_percent,
                waste_amount=cpu_wasted,
                monthly_cost_waste=round(monthly_cost, 2),
                recommendation=f"Réduire à {recommended_cpu:.2f} vCPUs (--cpus={recommended_cpu:.2f})"
            )
        
        # ═══════════════════════════════════════════════════
        # Analyse Memory
        # ═══════════════════════════════════════════════════
        if avg_mem_percent < self.WASTE_THRESHOLD_MEMORY:
            # Calcul gaspillage
            avg_mem_usage_bytes = statistics.mean(
                m['memory_usage_bytes'] for m in self.metrics_history
            )
            mem_used_gb = avg_mem_usage_bytes / (1024 ** 3)
            mem_wasted_gb = mem_limit_gb - mem_used_gb
            waste_percent = (mem_wasted_gb / mem_limit_gb) * 100 if mem_limit_gb > 0 else 0
            
            # Calcul coût mensuel
            monthly_cost = mem_wasted_gb * self.COST_PER_GB_HOUR * self.HOURS_PER_MONTH
            
            # Recommandation : usage × 1.5 (buffer 50%)
            recommended_mb = max(128, (mem_used_gb * 1.5) * 1024)  # Min 128MB
            
            wastes['memory'] = ResourceWaste(
                resource_type='memory',
                allocated=mem_limit_gb,
                used=mem_used_gb,
                waste_percent=waste_percent,
                waste_amount=mem_wasted_gb,
                monthly_cost_waste=round(monthly_cost, 2),
                recommendation=f"Réduire à {recommended_mb:.0f}MB (--memory={recommended_mb:.0f}m)"
            )
        
        return wastes
    
    def get_summary(self) -> dict:
        """Résumé simple des métriques actuelles"""
        if not self.metrics_history:
            self.collect_metrics(samples=1)
        
        if not self.metrics_history:
            return {}
        
        latest = self.metrics_history[-1]
        
        return {
            'cpu_percent': round(latest['cpu_percent'], 1),
            'cpu_limit': latest['cpu_limit'],
            'memory_usage_mb': round(latest['memory_usage_bytes'] / (1024**2), 0),
            'memory_limit_mb': round(latest['memory_limit_bytes'] / (1024**2), 0),
            'memory_percent': round(latest['memory_percent'], 1)
        }