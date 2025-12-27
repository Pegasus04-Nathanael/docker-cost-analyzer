"""
CLI.PY - Point d'entrée avec analyse ressources + sécurité
"""

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
import docker
import sys

# Imports des analyseurs
from analyzers.resources import ResourceAnalyzer
from analyzers.security import SecurityAnalyzer, Severity

console = Console()

@click.group()
@click.version_option(version="0.1.0")
def cli():
    """🐋 Docker Cost Analyzer"""
    pass

@cli.command()
@click.option('--detailed', is_flag=True, help='Analyse détaillée (ressources + sécurité)')
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
        console.print("[dim]Lancez un container de test :[/dim]")
        console.print("[dim]  docker run -d --name test nginx:alpine[/dim]\n")
        sys.exit(0)
    
    console.print(f"[green]✓[/green] Trouvé {len(containers)} container(s)\n")
    
    if not detailed:
        _show_basic_table(containers)
    else:
        _show_detailed_analysis(containers)

def _show_basic_table(containers):
    """Affichage rapide sans analyse"""
    
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
    """Analyse détaillée : ressources + sécurité"""
    
    console.print("[bold cyan]🔬 Analyse détaillée en cours...[/bold cyan]\n")
    
    # ═══════════════════════════════════════════════════════════
    # PHASE 1 : Analyse RESSOURCES
    # ═══════════════════════════════════════════════════════════
    
    console.print("[dim]Phase 1/2 : Analyse des ressources...[/dim]\n")
    
    total_waste_cost = 0
    containers_with_waste = []
    
    for i, container in enumerate(containers, 1):
        console.print(f"[dim]  Ressources {i}/{len(containers)}: {container.name}...[/dim]")
        
        analyzer = ResourceAnalyzer(container)
        wastes = analyzer.analyze()
        
        if wastes:
            containers_with_waste.append({
                'name': container.name,
                'wastes': wastes
            })
            
            for waste in wastes.values():
                total_waste_cost += waste.monthly_cost_waste
    
    console.print()
    
    # ═══════════════════════════════════════════════════════════
    # PHASE 2 : Analyse SÉCURITÉ
    # ═══════════════════════════════════════════════════════════
    
    console.print("[dim]Phase 2/2 : Analyse de sécurité...[/dim]\n")
    
    containers_with_issues = []
    total_critical = 0
    total_high = 0
    total_medium = 0
    
    for i, container in enumerate(containers, 1):
        console.print(f"[dim]  Sécurité {i}/{len(containers)}: {container.name}...[/dim]")
        
        sec_analyzer = SecurityAnalyzer(container)
        issues = sec_analyzer.analyze()
        
        if issues:
            containers_with_issues.append({
                'name': container.name,
                'issues': issues
            })
            
            # Compter par sévérité
            for issue in issues:
                if issue.severity == Severity.CRITICAL:
                    total_critical += 1
                elif issue.severity == Severity.HIGH:
                    total_high += 1
                elif issue.severity == Severity.MEDIUM:
                    total_medium += 1
    
    console.print()
    console.print("─" * 80)
    console.print()
    
    # ═══════════════════════════════════════════════════════════
    # AFFICHAGE : Gaspillage ressources
    # ═══════════════════════════════════════════════════════════
    
    if containers_with_waste:
        console.print("[bold yellow]💰 GASPILLAGE DE RESSOURCES[/bold yellow]\n")
        
        table = Table(box=box.ROUNDED)
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
        
        console.print(table)
        console.print()
    else:
        console.print("[green]✓ Pas de gaspillage ressources détecté[/green]\n")
    
    # ═══════════════════════════════════════════════════════════
    # AFFICHAGE : Issues de sécurité
    # ═══════════════════════════════════════════════════════════
    
    if containers_with_issues:
        console.print("[bold red]🔒 PROBLÈMES DE SÉCURITÉ[/bold red]\n")
        
        for item in containers_with_issues:
            console.print(f"[bold cyan]Container: {item['name']}[/bold cyan]")
            console.print()
            
            for issue in item['issues']:
                # Couleur selon sévérité
                if issue.severity == Severity.CRITICAL:
                    color = "red bold"
                    icon = "🔴"
                elif issue.severity == Severity.HIGH:
                    color = "red"
                    icon = "🟠"
                elif issue.severity == Severity.MEDIUM:
                    color = "yellow"
                    icon = "🟡"
                else:
                    color = "blue"
                    icon = "🔵"
                
                console.print(f"  {icon} [{color}][{issue.severity.value}][/{color}] {issue.title}")
                console.print(f"     [dim]Impact : {issue.impact}[/dim]")
                console.print(f"     [green]Fix : {issue.recommendation}[/green]")
                console.print()
        
        console.print()
    else:
        console.print("[green]✓ Aucun problème de sécurité majeur détecté[/green]\n")
    
    # ═══════════════════════════════════════════════════════════
    # RÉSUMÉ FINAL
    # ═══════════════════════════════════════════════════════════
    
    console.print("─" * 80)
    console.print()
    
    # Résumé ressources
    if containers_with_waste:
        console.print(Panel(
            f"[bold]💰 Impact financier[/bold]\n\n"
            f"• Containers avec gaspillage : {len(containers_with_waste)}/{len(containers)}\n"
            f"• [red bold]Coût gaspillé : €{total_waste_cost:.2f}/mois[/red bold]\n"
            f"• [green bold]Économie annuelle potentielle : €{total_waste_cost * 12:.2f}[/green bold]",
            border_style="yellow"
        ))
        console.print()
    
    # Résumé sécurité
    if containers_with_issues:
        total_issues = total_critical + total_high + total_medium
        
        severity_text = ""
        if total_critical > 0:
            severity_text += f"• [red bold]CRITICAL : {total_critical}[/red bold]\n"
        if total_high > 0:
            severity_text += f"• [red]HIGH : {total_high}[/red]\n"
        if total_medium > 0:
            severity_text += f"• [yellow]MEDIUM : {total_medium}[/yellow]\n"
        
        console.print(Panel(
            f"[bold]🔒 Risques de sécurité[/bold]\n\n"
            f"• Containers avec issues : {len(containers_with_issues)}/{len(containers)}\n"
            f"• Total issues : {total_issues}\n\n"
            f"{severity_text}",
            border_style="red"
        ))
        console.print()
    
    # Message final
    if not containers_with_waste and not containers_with_issues:
        console.print(Panel(
            "[green bold]🎉 EXCELLENT ![/green bold]\n\n"
            "Vos containers sont bien configurés :\n"
            "• ✓ Ressources optimisées\n"
            "• ✓ Sécurité correcte",
            border_style="green"
        ))
        console.print()

if __name__ == "__main__":
    cli()