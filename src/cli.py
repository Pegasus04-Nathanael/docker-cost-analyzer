"""
CLI.PY - Point d'entrée de l'application

Rôle: Gérer les commandes utilisateur
Comment ça marche:
  1. User tape: python cli.py scan
  2. Click capture "scan" et appelle la fonction scan()
  3. La fonction scan() appelle le scanner principal
"""

import click
from rich.console import Console
import docker

# Console Rich pour affichage coloré
console = Console()

@click.group()
def cli():
    """Container Performance Profiler - Analyser vos containers Docker"""
    pass

@cli.command()
def scan():
    """Scanner tous les containers en cours d'exécution"""
    
    # Affichage joli avec Rich
    console.print("\n[bold blue]🔍 Démarrage du scan...[/bold blue]\n")
    
    try:
        # Se connecter à Docker
        # docker.from_env() lit les variables d'environnement Docker
        client = docker.from_env()
        
        # Récupérer tous les containers qui tournent
        containers = client.containers.list()
        
        # Afficher combien on a trouvé
        console.print(f"[green]✓[/green] Trouvé {len(containers)} container(s) en cours d'exécution\n")
        
        # Lister chaque container
        for container in containers:
            console.print(f"  • [cyan]{container.name}[/cyan] (ID: {container.short_id})")
            console.print(f"    Image: {container.image.tags[0] if container.image.tags else 'N/A'}")
            console.print(f"    Status: {container.status}\n")
        
    except docker.errors.DockerException as e:
        console.print(f"[red]✗ Erreur de connexion Docker:[/red] {e}")
        console.print("\n[yellow]💡 Vérifiez que Docker est démarré[/yellow]")

if __name__ == "__main__":
    cli()