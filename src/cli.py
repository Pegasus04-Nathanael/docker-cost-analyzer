"""
CLI.PY - Point d'entrée avec analyse de gaspillage
"""

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
import docker
import sys

# Import de notre analyseur
from analyzers.resources import ResourceAnalyzer

console = Console()

@click.group()
@click.version_option(version="0.1.0")
def cli():
    """🐋 Docker Cost Analyzer"""
    pass

@cli.command()
@click.option('--detailed', is_flag=True, help='Analyse détaillée avec gaspillage')
def scan(detailed):
    """Scanner tous les containers"""
    
    console.print()
    console.print(Panel.fit(
        "[bold blue]🔍 Docker Cost Analyzer[/bold blue]\n"
        "[dim]Analyse en cours...[/dim]",
        box=box.DOUBLE
    ))
    console.print()
    
    try:
        client = docker.from_env()
        client.ping()
        console.print("[green]✓[/green] Connecté à Docker\n")
    except docker.errors.DockerException as e:
        console.print(f"[red]✗ Erreur : {e}[/red]")
        sys.exit(1)
    
    containers = client.containers.list()
    
    if not containers:
        console.print("[yellow]⚠[/yellow] Aucun container running\n")
        sys.exit(0)
    
    console.print(f"[green]✓[/green] Trouvé {len(containers)} container(s)\n")
    
    # ═══════════════════════════════════════════════════════════
    # Analyse basique OU détaillée
    # ═══════════════════════════════════════════════════════════
    
    if not detailed:
        # ─────── Mode basique (rapide) ───────
        _show_basic_table(containers)
    else:
        # ─────── Mode détaillé (avec gaspillage) ───────
        _show_detailed_analysis(containers)

def _show_basic_table(containers):
    """Affichage rapide sans analyse gaspillage"""
    
    table = Table(show_header=True, header_style="bold magenta", box=box.ROUNDED)
    table.add_column("Container", style="cyan", width=20)
    table.add_column("Image", style="green", width=25)
    table.add_column("Status", justify="center", width=12)
    table.add_column("CPU", justify="right", width=10)
    table.add_column("Memory", justify="right", width=15)
    
    for container in containers:
        stats = container.stats(stream=False)
        
        # CPU
        cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - \
                   stats['precpu_stats']['cpu_usage']['total_usage']
        system_delta = stats['cpu_stats']['system_cpu_usage'] - \
                      stats['precpu_stats']['system_cpu_usage']
        online_cpus = stats['cpu_stats'].get('online_cpus', 1)
        
        cpu_percent = 0.0
        if system_delta > 0 and cpu_delta > 0:
            cpu_percent = (cpu_delta / system_delta) * online_cpus * 100
        
        # Memory
        mem_usage = stats['memory_stats'].get('usage', 0)
        mem_limit = stats['memory_stats'].get('limit', 1)
        mem_percent = (mem_usage / mem_limit) * 100 if mem_limit > 0 else 0
        
        mem_usage_mb = mem_usage / (1024 ** 2)
        mem_limit_mb = mem_limit / (1024 ** 2)
        
        # Status
        status = "[green]● running[/green]" if container.status == "running" else f"[yellow]○ {container.status}[/yellow]"
        
        # CPU color
        if cpu_percent < 10:
            cpu_display = f"[green]{cpu_percent:.1f}%[/green]"
        elif cpu_percent < 50:
            cpu_display = f"[yellow]{cpu_percent:.1f}%[/yellow]"
        else:
            cpu_display = f"[red]{cpu_percent:.1f}%[/red]"
        
        # Memory color
        mem_display = f"{mem_usage_mb:.0f} / {mem_limit_mb:.0f} MB"
        if mem_percent < 30:
            mem_display = f"[green]{mem_display}[/green]"
        elif mem_percent < 70:
            mem_display = f"[yellow]{mem_display}[/yellow]"
        else:
            mem_display = f"[red]{mem_display}[/red]"
        
        # Image
        image_name = container.image.tags[0] if container.image.tags else "unknown"
        
        table.add_row(container.name, image_name, status, cpu_display, mem_display)
    
    console.print(table)
    console.print()
    
    console.print(Panel(
        f"[bold]Résumé[/bold]\n"
        f"• Containers analysés : {len(containers)}\n"
        f"• Pour analyse détaillée : [cyan]docker-cost-analyzer scan --detailed[/cyan]",
        title="📊 Scan terminé",
        border_style="green"
    ))
    console.print()

def _show_detailed_analysis(containers):
    """Analyse détaillée avec détection gaspillage"""
    
    console.print("[bold cyan]🔬 Analyse détaillée en cours...[/bold cyan]\n")
    
    total_waste_cost = 0
    containers_with_waste = []
    
    for i, container in enumerate(containers, 1):
        console.print(f"[dim]Analyse {i}/{len(containers)}: {container.name}...[/dim]")
        
        # Créer l'analyseur
        analyzer = ResourceAnalyzer(container)
        
        # Analyser (collecte 3 échantillons)
        wastes = analyzer.analyze()
        
        if wastes:
            containers_with_waste.append({
                'name': container.name,
                'wastes': wastes
            })
            
            # Accumuler coûts
            for waste in wastes.values():
                total_waste_cost += waste.monthly_cost_waste
    
    console.print()
    
    # ═══════════════════════════════════════════════════════════
    # Afficher résultats
    # ═══════════════════════════════════════════════════════════
    
    if not containers_with_waste:
        console.print(Panel(
            "[green]✓ Aucun gaspillage majeur détecté ![/green]\n"
            "Tous vos containers sont bien dimensionnés.",
            title="🎉 Excellent",
            border_style="green"
        ))
    else:
        # Tableau des gaspillages
        table = Table(title="⚠️  Gaspillages détectés", box=box.ROUNDED)
        table.add_column("Container", style="cyan")
        table.add_column("Ressource", style="yellow")
        table.add_column("Alloué", justify="right")
        table.add_column("Utilisé", justify="right")
        table.add_column("Gaspillage", justify="right", style="red")
        table.add_column("Coût/mois", justify="right", style="red bold")
        
        for item in containers_with_waste:
            for resource_type, waste in item['wastes'].items():
                unit = "vCPU" if resource_type == "cpu" else "GB"
                
                table.add_row(
                    item['name'],
                    resource_type.upper(),
                    f"{waste.allocated:.2f} {unit}",
                    f"{waste.used:.2f} {unit}",
                    f"{waste.waste_percent:.0f}%",
                    f"€{waste.monthly_cost_waste:.2f}"
                )
        
        console.print()
        console.print(table)
        console.print()
        
        # Recommandations
        console.print(Panel.fit(
            "[bold yellow]💡 Recommandations[/bold yellow]",
            border_style="yellow"
        ))
        console.print()
        
        for item in containers_with_waste:
            console.print(f"[cyan]Container: {item['name']}[/cyan]")
            for waste in item['wastes'].values():
                console.print(f"  • {waste.recommendation}")
            console.print()
        
        # Résumé final
        console.print(Panel(
            f"[bold]Résumé financier[/bold]\n\n"
            f"• Containers analysés : {len(containers)}\n"
            f"• Containers avec gaspillage : {len(containers_with_waste)}\n"
            f"• [red bold]Coût gaspillé total : €{total_waste_cost:.2f}/mois[/red bold]\n\n"
            f"💰 Économie potentielle annuelle : [green bold]€{total_waste_cost * 12:.2f}[/green bold]",
            title="💸 Impact financier",
            border_style="red"
        ))
    
    console.print()

if __name__ == "__main__":
    cli()