# src/analyzers/resources.py

from dataclasses import dataclass
from typing import Dict, List, Optional
import statistics

@dataclass
class ResourceMetrics:
    cpu_percent: float
    cpu_limit: float
    memory_usage_mb: float
    memory_limit_mb: float
    memory_percent: float
    network_rx_mb: float
    network_tx_mb: float
    block_io_read_mb: float
    block_io_write_mb: float

@dataclass
class ResourceWaste:
    resource_type: str  # 'cpu' or 'memory'
    allocated: float
    used: float
    waste_percent: float
    waste_amount: float
    monthly_cost_waste: float  # euros
    recommendation: str

class ResourceAnalyzer:
    """Analyse resource utilization et détecte over-provisioning"""
    
    # Prix cloud moyens (AWS/GCP/Azure avg)
    COST_PER_CPU_HOUR = 0.04  # €40/mois per vCPU
    COST_PER_GB_HOUR = 0.005  # €3.6/mois per GB
    
    WASTE_THRESHOLD_CPU = 20  # % - si <20% usage = waste
    WASTE_THRESHOLD_MEMORY = 30  # % - si <30% usage = waste
    
    def __init__(self, container):
        self.container = container
        self.metrics_history = []
    
    def collect_metrics_over_time(self, duration_seconds=60, 
                                   interval_seconds=5) -> List[ResourceMetrics]:
        """Collect metrics sur une période (plus précis qu'un snapshot)"""
        import time
        
        metrics = []
        iterations = duration_seconds // interval_seconds
        
        for _ in range(iterations):
            stats = self.container.stats(stream=False)
            metrics.append(self._parse_stats(stats))
            time.sleep(interval_seconds)
        
        self.metrics_history = metrics
        return metrics
    
    def _parse_stats(self, stats: dict) -> ResourceMetrics:
        """Parse Docker stats vers format clean"""
        
        # CPU calculation
        cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - \
                   stats['precpu_stats']['cpu_usage']['total_usage']
        system_delta = stats['cpu_stats']['system_cpu_usage'] - \
                      stats['precpu_stats']['system_cpu_usage']
        online_cpus = stats['cpu_stats'].get('online_cpus', 1)
        
        cpu_percent = 0.0
        if system_delta > 0:
            cpu_percent = (cpu_delta / system_delta) * online_cpus * 100
        
        # Memory
        mem_usage = stats['memory_stats']['usage']
        mem_limit = stats['memory_stats']['limit']
        mem_percent = (mem_usage / mem_limit) * 100
        
        # Network
        networks = stats.get('networks', {})
        rx_bytes = sum(net['rx_bytes'] for net in networks.values())
        tx_bytes = sum(net['tx_bytes'] for net in networks.values())
        
        # Block I/O
        blkio = stats.get('blkio_stats', {})
        io_read = sum(
            stat['value'] for stat in 
            blkio.get('io_service_bytes_recursive', [])
            if stat['op'] == 'Read'
        )
        io_write = sum(
            stat['value'] for stat in 
            blkio.get('io_service_bytes_recursive', [])
            if stat['op'] == 'Write'
        )
        
        return ResourceMetrics(
            cpu_percent=cpu_percent,
            cpu_limit=online_cpus,
            memory_usage_mb=mem_usage / (1024**2),
            memory_limit_mb=mem_limit / (1024**2),
            memory_percent=mem_percent,
            network_rx_mb=rx_bytes / (1024**2),
            network_tx_mb=tx_bytes / (1024**2),
            block_io_read_mb=io_read / (1024**2),
            block_io_write_mb=io_write / (1024**2)
        )
    
    def analyze(self) -> Dict[str, ResourceWaste]:
        """Analyse complète avec détection waste"""
        
        if not self.metrics_history:
            # Fallback: single snapshot si pas de history
            stats = self.container.stats(stream=False)
            self.metrics_history = [self._parse_stats(stats)]
        
        # Métriques moyennes sur la période
        avg_cpu = statistics.mean(m.cpu_percent for m in self.metrics_history)
        avg_mem_percent = statistics.mean(m.memory_percent for m in self.metrics_history)
        
        cpu_limit = self.metrics_history[0].cpu_limit
        mem_limit = self.metrics_history[0].memory_limit_mb
        
        wastes = {}
        
        # CPU Waste
        if avg_cpu < self.WASTE_THRESHOLD_CPU:
            cpu_waste_percent = 100 - (avg_cpu / self.WASTE_THRESHOLD_CPU * 100)
            cpu_waste_cores = cpu_limit * (cpu_waste_percent / 100)
            monthly_cost = cpu_waste_cores * self.COST_PER_CPU_HOUR * 730
            
            wastes['cpu'] = ResourceWaste(
                resource_type='cpu',
                allocated=cpu_limit,
                used=avg_cpu * cpu_limit / 100,
                waste_percent=cpu_waste_percent,
                waste_amount=cpu_waste_cores,
                monthly_cost_waste=monthly_cost,
                recommendation=f"Reduce CPU limit to {cpu_limit * 0.3:.2f} cores"
            )
        
        # Memory Waste
        if avg_mem_percent < self.WASTE_THRESHOLD_MEMORY:
            mem_waste_percent = 100 - (avg_mem_percent / self.WASTE_THRESHOLD_MEMORY * 100)
            mem_waste_mb = mem_limit * (mem_waste_percent / 100)
            monthly_cost = (mem_waste_mb / 1024) * self.COST_PER_GB_HOUR * 730
            
            avg_mem_usage = statistics.mean(m.memory_usage_mb for m in self.metrics_history)
            recommended_mb = avg_mem_usage * 1.5  # 50% buffer
            
            wastes['memory'] = ResourceWaste(
                resource_type='memory',
                allocated=mem_limit,
                used=avg_mem_usage,
                waste_percent=mem_waste_percent,
                waste_amount=mem_waste_mb,
                monthly_cost_waste=monthly_cost,
                recommendation=f"Reduce memory limit to {recommended_mb:.0f}MB"
            )
        
        return wastes