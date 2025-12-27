"""
Continuous monitoring daemon
Scans containers at intervals and stores metrics
"""

import time
import docker
from rich.console import Console
from datetime import datetime

from analyzers.resources import ResourceAnalyzer
from analyzers.security import SecurityAnalyzer, Severity
from monitoring.database import MetricsDB


console = Console()


class ContainerMonitor:
    """Background monitoring of containers"""
    
    def __init__(self, interval_seconds: int = 300, 
                 alert_threshold: float = 100):
        """
        Args:
            interval_seconds: Time between scans (default 5min)
            alert_threshold: Alert if waste > this amount (€/month)
        """
        self.interval = interval_seconds
        self.alert_threshold = alert_threshold
        self.db = MetricsDB()
        
        try:
            self.client = docker.from_env()
            self.client.ping()
        except Exception as e:
            console.print(f"[red]Failed to connect to Docker: {e}[/red]")
            raise
    
    def run(self):
        """Main monitoring loop (blocking)"""
        console.print("\n[bold green]🔄 Monitoring started[/bold green]")
        console.print(f"├─ Interval: {self.interval}s ({self.interval/60:.1f}min)")
        console.print(f"├─ Alert threshold: €{self.alert_threshold}/month")
        console.print(f"└─ Database: {self.db.db_path}\n")
        
        scan_count = 0
        
        try:
            while True:
                scan_count += 1
                self._scan_all_containers(scan_count)
                
                console.print(f"\n[dim]Next scan in {self.interval}s... (Ctrl+C to stop)[/dim]")
                time.sleep(self.interval)
        
        except KeyboardInterrupt:
            console.print("\n\n[yellow]Monitoring stopped[/yellow]")
            console.print(f"Total scans: {scan_count}")
    
    def _scan_all_containers(self, scan_number: int):
        """Single scan of all containers"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        console.print(f"\n[cyan]📊 Scan #{scan_number} at {timestamp}[/cyan]")
        
        containers = self.client.containers.list()
        
        if not containers:
            console.print("[dim]No running containers[/dim]")
            return
        
        total_waste = 0
        critical_count = 0
        
        for container in containers:
            try:
                waste, critical = self._analyze_container(container)
                total_waste += waste
                critical_count += critical
            except Exception as e:
                console.print(f"[red]Error analyzing {container.name}: {e}[/red]")
        
        # Summary
        console.print(f"\n├─ Total waste: [yellow]€{total_waste:.2f}/month[/yellow]")
        if critical_count > 0:
            console.print(f"└─ Security: [red]{critical_count} CRITICAL issues[/red]")
        
        # Alert if threshold exceeded
        if total_waste > self.alert_threshold:
            console.print(f"\n[bold red]⚠️  ALERT: Waste €{total_waste:.2f}/mo > threshold €{self.alert_threshold}/mo[/bold red]")
    
    def _analyze_container(self, container) -> tuple:
        """
        Analyze single container
        Returns: (waste_cost, critical_count)
        """
        # Resources
        res_analyzer = ResourceAnalyzer(container)
        res_analyzer.collect_metrics(samples=1, interval=1)
        summary = res_analyzer.get_summary()
        wastes = res_analyzer.analyze()
        
        waste_cpu = wastes.get('cpu', type('obj', (), {'monthly_cost_waste': 0})).monthly_cost_waste
        waste_mem = wastes.get('memory', type('obj', (), {'monthly_cost_waste': 0})).monthly_cost_waste
        total_waste = waste_cpu + waste_mem
        
        # Store in DB
        self.db.store_metric(
            container.id,
            container.name,
            summary['cpu_percent'],
            summary['memory_usage_mb'],
            summary['memory_limit_mb'],
            waste_cpu,
            waste_mem
        )
        
        # Security
        sec_analyzer = SecurityAnalyzer(container)
        issues = sec_analyzer.analyze()
        
        critical_count = 0
        for issue in issues:
            if issue.severity == Severity.CRITICAL:
                critical_count += 1
                self.db.store_security_event(
                    container.id,
                    container.name,
                    issue.severity.value,
                    issue.check_name,
                    issue.title
                )
        
        # Display
        status_icon = "💰" if total_waste > 10 else "✓"
        security_icon = "🔒" if critical_count > 0 else ""
        
        console.print(f"  {status_icon} [cyan]{container.name:20}[/cyan] "
                     f"€{total_waste:6.2f}/mo {security_icon}")
        
        return total_waste, critical_count