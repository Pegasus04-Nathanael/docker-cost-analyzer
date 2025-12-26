"""
CLI.PY - Point d'entrée de Docker Cost Analyzer

Rôle : Interface en ligne de commande pour l'utilisateur
Comment ça marche :
  1. User tape : python src/cli.py scan
  2. Click détecte la commande "scan"
  3. On se connecte à Docker
  4. On liste et analyse les containers
  5. On affiche les résultats
"""

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
import docker
import sys

# Console Rich pour affichage coloré et élégant
console = Console()

@click.group()
@click.version_option(version="0.1.0")
def cli():
    """
    🐋 Docker Cost Analyzer
    
    Analyse vos containers Docker pour détecter :
    - Gaspillage de ressources (CPU/RAM)
    - Problèmes de sécurité
    - Opportunités d'optimisation
    - Calcul des coûts en €
    """
    pass

@cli.command()
@click.option('--format', type=click.Choice(['table', 'json']), default='table',
              help='Format de sortie (table ou json)')
def scan(format):
    """Scanner tous les containers en cours d'exécution"""
    
    # Affichage du header
    console.print()
    console.print(Panel.fit(
        "[bold blue]🔍 Docker Cost Analyzer[/bold blue]\n"
        "[dim]Analyse en cours...[/dim]",
        box=box.DOUBLE
    ))
    console.print()
    
    try:
        # ═══════════════════════════════════════════════════════════
        # ÉTAPE 1 : Se connecter à Docker
        # ═══════════════════════════════════════════════════════════
        # docker.from_env() lit les variables d'environnement Docker
        # (DOCKER_HOST, etc.) et crée une connexion
        client = docker.from_env()
        
        # Test de connexion
        client.ping()
        console.print("[green]✓[/green] Connecté à Docker\n")
        
    except docker.errors.DockerException as e:
        console.print(f"[red]✗ Erreur de connexion à Docker[/red]")
        console.print(f"[dim]{str(e)}[/dim]\n")
        console.print("[yellow]💡 Vérifiez que Docker est démarré[/yellow]")
        sys.exit(1)
    
    try:
        # ═══════════════════════════════════════════════════════════
        # ÉTAPE 2 : Récupérer les containers
        # ═══════════════════════════════════════════════════════════
        # .list() retourne seulement les containers running
        # .list(all=True) retournerait tous les containers (stopped aussi)
        containers = client.containers.list()
        
        if not containers:
            console.print("[yellow]⚠[/yellow] Aucun container en cours d'exécution\n")
            console.print("[dim]Lancez un container de test :[/dim]")
            console.print("[dim]  docker run -d --name test-nginx nginx:alpine[/dim]\n")
            sys.exit(0)
        
        console.print(f"[green]✓[/green] Trouvé {len(containers)} container(s)\n")
        
        # ═══════════════════════════════════════════════════════════
        # ÉTAPE 3 : Créer le tableau d'affichage
        # ═══════════════════════════════════════════════════════════
        table = Table(show_header=True, header_style="bold magenta", box=box.ROUNDED)
        table.add_column("Container", style="cyan", width=20)
        table.add_column("Image", style="green", width=25)
        table.add_column("Status", justify="center", width=12)
        table.add_column("CPU", justify="right", width=10)
        table.add_column("Memory", justify="right", width=15)
        
        # ═══════════════════════════════════════════════════════════
        # ÉTAPE 4 : Analyser chaque container
        # ═══════════════════════════════════════════════════════════
        for container in containers:
            # Récupérer les statistiques en temps réel
            # stream=False signifie "donne-moi un snapshot, pas un flux continu"
            stats = container.stats(stream=False)
            
            # ─────────────────────────────────────────────────────
            # Calcul CPU usage
            # ─────────────────────────────────────────────────────
            # Docker donne l'usage CPU cumulé, on doit calculer le %
            cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - \
                       stats['precpu_stats']['cpu_usage']['total_usage']
            system_delta = stats['cpu_stats']['system_cpu_usage'] - \
                          stats['precpu_stats']['system_cpu_usage']
            online_cpus = stats['cpu_stats'].get('online_cpus', 1)
            
            cpu_percent = 0.0
            if system_delta > 0 and cpu_delta > 0:
                # Formule : (cpu_delta / system_delta) * nb_cores * 100
                cpu_percent = (cpu_delta / system_delta) * online_cpus * 100
            
            # ─────────────────────────────────────────────────────
            # Calcul Memory usage
            # ─────────────────────────────────────────────────────
            mem_usage = stats['memory_stats'].get('usage', 0)
            mem_limit = stats['memory_stats'].get('limit', 1)
            mem_percent = (mem_usage / mem_limit) * 100 if mem_limit > 0 else 0
            
            # Conversion en MB pour affichage
            mem_usage_mb = mem_usage / (1024 ** 2)
            mem_limit_mb = mem_limit / (1024 ** 2)
            
            # ─────────────────────────────────────────────────────
            # Déterminer le statut (avec couleur)
            # ─────────────────────────────────────────────────────
            status = container.status
            if status == "running":
                status_display = "[green]● running[/green]"
            else:
                status_display = f"[yellow]○ {status}[/yellow]"
            
            # ─────────────────────────────────────────────────────
            # Formater CPU avec couleur selon usage
            # ─────────────────────────────────────────────────────
            if cpu_percent < 10:
                cpu_display = f"[green]{cpu_percent:.1f}%[/green]"
            elif cpu_percent < 50:
                cpu_display = f"[yellow]{cpu_percent:.1f}%[/yellow]"
            else:
                cpu_display = f"[red]{cpu_percent:.1f}%[/red]"
            
            # ─────────────────────────────────────────────────────
            # Formater Memory avec couleur
            # ─────────────────────────────────────────────────────
            mem_display = f"{mem_usage_mb:.0f} / {mem_limit_mb:.0f} MB"
            if mem_percent < 30:
                mem_display = f"[green]{mem_display}[/green]"
            elif mem_percent < 70:
                mem_display = f"[yellow]{mem_display}[/yellow]"
            else:
                mem_display = f"[red]{mem_display}[/red]"
            
            # ─────────────────────────────────────────────────────
            # Récupérer nom image (avec fallback)
            # ─────────────────────────────────────────────────────
            image_name = "unknown"
            if container.image.tags:
                image_name = container.image.tags[0]
            
            # ─────────────────────────────────────────────────────
            # Ajouter la ligne au tableau
            # ─────────────────────────────────────────────────────
            table.add_row(
                container.name,
                image_name,
                status_display,
                cpu_display,
                mem_display
            )
        
        # ═══════════════════════════════════════════════════════════
        # ÉTAPE 5 : Afficher le tableau
        # ═══════════════════════════════════════════════════════════
        console.print(table)
        console.print()
        
        # ═══════════════════════════════════════════════════════════
        # ÉTAPE 6 : Afficher un résumé rapide
        # ═══════════════════════════════════════════════════════════
        console.print(Panel(
            f"[bold]Résumé[/bold]\n"
            f"• Containers analysés : {len(containers)}\n"
            f"• Analyse détaillée : [dim]Prochainement[/dim]\n"
            f"• Rapport complet : [dim]En développement[/dim]",
            title="📊 Analyse terminée",
            border_style="green"
        ))
        console.print()
        
    except Exception as e:
        console.print(f"[red]✗ Erreur lors de l'analyse[/red]")
        console.print(f"[dim]{str(e)}[/dim]\n")
        sys.exit(1)

# ═══════════════════════════════════════════════════════════════════
# Point d'entrée du programme
# ═══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    cli()