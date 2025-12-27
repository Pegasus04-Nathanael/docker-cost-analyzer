"""
CLI - Docker Cost Analyzer
Commands: scan, monitor, fix, trends
"""

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
import docker
import sys
from pathlib import Path

from analyzers.resources import ResourceAnalyzer
from analyzers.security import SecurityAnalyzer, Severity
from monitoring.monitor import ContainerMonitor
from monitoring.database import MetricsDB
from generators.fixes import FixGenerator

console = Console()


@click.group()
@click.version_option(version="0.2.0")
def cli():
    """🐋 Docker Cost Analyzer - Optimize containers & cut costs"""
    pass


@cli.command()
@click.option('--detailed', is_flag=True, help='Full analysis (resources + security)')
def scan(detailed):
    """Scan running containers (one-time)"""
    
    console.print()
    console.print(Panel.fit(
        "[bold blue]🔍 Docker Cost Analyzer[/bold blue]\n"
        "[dim]Analyzing containers...[/dim]",
        box=box.DOUBLE
    ))
    console.print()
    
    try:
        client = docker.from_env()
        client.ping()
        console.print("[green]✓[/green] Connected to Docker\n")
    except docker.errors.DockerException as e:
        console.print(f"[red]✗ Docker error: {e}[/red]")
        sys.exit(1)
    
    containers = client.containers.list()
    
    if not containers:
        console.print("[yellow]⚠[/yellow] No running containers\n")
        console.print("[dim]Start a container:[/dim]")
        console.print("[dim]  docker run -d --name test nginx:alpine[/dim]\n")
        sys.exit(0)
    
    console.print(f"[green]✓[/green] Found {len(containers)} container(s)\n")
    
    if not detailed:
        _show_basic_table(containers)
    else:
        _show_detailed_analysis(containers)


@cli.command()
@click.option('--interval', default=300, help='Scan interval in seconds (default: 300 = 5min)')
@click.option('--threshold', default=100, help='Alert threshold in €/month (default: 100)')
def monitor(interval, threshold):
    """
    Continuous monitoring (runs until Ctrl+C)
    
    Scans containers at intervals and stores metrics in SQLite database.
    Alerts when waste exceeds threshold.
    
    Examples:
      docker-cost-analyzer monitor                    # 5min intervals
      docker-cost-analyzer monitor --interval=60      # 1min intervals
      docker-cost-analyzer monitor --threshold=200    # Alert at €200/mo
    """
    monitor = ContainerMonitor(interval_seconds=interval, alert_threshold=threshold)
    monitor.run()


@cli.command()
@click.argument('container_name')
@click.option('--output', default=None, help='Output file (default: fix-CONTAINER.sh)')
@click.option('--execute', is_flag=True, help='Execute the fix immediately (careful!)')
def fix(container_name, output, execute):
    """
    Generate fix script for a container
    
    Analyzes the container and generates a bash script to:
    - Optimize resource allocation (CPU/RAM)
    - Fix security issues (root user, readonly, etc.)
    
    Examples:
      docker-cost-analyzer fix nginx-prod
      docker-cost-analyzer fix api-backend --output=optimize.sh
      docker-cost-analyzer fix redis --execute  # Careful!
    """
    try:
        client = docker.from_env()
        container = client.containers.get(container_name)
    except docker.errors.NotFound:
        console.print(f"[red]Container '{container_name}' not found[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
    
    console.print(f"\n[cyan]Analyzing {container_name}...[/cyan]\n")
    
    # Analyze resources
    res_analyzer = ResourceAnalyzer(container)
    wastes = res_analyzer.analyze()
    
    # Analyze security
    sec_analyzer = SecurityAnalyzer(container)
    issues = sec_analyzer.analyze()
    
    # Check if any fixes needed
    if not wastes and not issues:
        console.print("[green]✓ Container is already optimized![/green]")
        console.print("  • Resources: Well-sized")
        console.print("  • Security: No major issues\n")
        return
    
    # Display findings
    if wastes:
        total_waste = sum(w.monthly_cost_waste for w in wastes.values())
        console.print(f"[yellow]💰 Waste detected: €{total_waste:.2f}/month[/yellow]")
        for resource, waste in wastes.items():
            console.print(f"  • {resource.upper()}: {waste.waste_percent:.0f}% wasted")
    
    if issues:
        critical = sum(1 for i in issues if i.severity == Severity.CRITICAL)
        console.print(f"[red]🔒 Security: {len(issues)} issues ({critical} critical)[/red]")
    
    console.print()
    
    # Generate fix script
    generator = FixGenerator()
    script = generator.generate_script(container_name, wastes, issues)
    
    # Save to file
    if output is None:
        output = f"fix-{container_name}.sh"
    
    Path(output).write_text(script)
    console.print(f"[green]✓ Fix script generated: {output}[/green]")
    console.print(f"\n[dim]To apply fixes:[/dim]")
    console.print(f"[dim]  chmod +x {output}[/dim]")
    console.print(f"[dim]  ./{output}[/dim]\n")
    
    if execute:
        import subprocess
        console.print("[yellow]⚠️  Executing fix script...[/yellow]")
        result = subprocess.run(['bash', output], capture_output=True, text=True)
        if result.returncode == 0:
            console.print("[green]✓ Fix applied successfully[/green]")
        else:
            console.print(f"[red]✗ Fix failed: {result.stderr}[/red]")


@cli.command()
@click.argument('container_name', required=False)
@click.option('--days', default=7, help='Number of days to show (default: 7)')
def trends(container_name, days):
    """
    Show historical trends for containers
    
    Displays CPU, memory, and waste trends over time from monitoring database.
    
    Examples:
      docker-cost-analyzer trends              # List all containers
      docker-cost-analyzer trends nginx-prod   # Show trends for nginx-prod
      docker-cost-analyzer trends api --days=30
    """
    db = MetricsDB()
    
    if container_name is None:
        # List all containers
        containers = db.get_all_containers()
        
        if not containers:
            console.print("[yellow]No monitoring data yet[/yellow]")
            console.print("\n[dim]Start monitoring:[/dim]")
            console.print("[dim]  docker-cost-analyzer monitor[/dim]\n")
            return
        
        console.print(f"\n[bold]Monitored containers:[/bold]\n")
        for name in containers:
            trend = db.get_waste_trend(name, days)
            console.print(f"  • [cyan]{name:20}[/cyan] "
                         f"avg €{trend['avg_waste']:.2f}/mo "
                         f"({trend['samples']} samples)")
        
        console.print(f"\n[dim]View details:[/dim]")
        console.print(f"[dim]  docker-cost-analyzer trends CONTAINER_NAME[/dim]\n")
    
    else:
        # Show specific container trends
        history = db.get_history(container_name, days)
        
        if not history:
            console.print(f"[yellow]No data for '{container_name}'[/yellow]")
            console.print(f"\n[dim]Container not monitored or name incorrect[/dim]\n")
            return
        
        # Display trends
        console.print(f"\n[bold cyan]{container_name}[/bold cyan] - Last {days} days\n")
        
        # Calculate stats
        cpu_vals = [h['cpu_percent'] for h in history]
        mem_vals = [h['memory_usage_mb'] for h in history]
        waste_vals = [h['waste_cpu_cost'] + h['waste_memory_cost'] for h in history]
        
        table = Table(box=box.SIMPLE)
        table.add_column("Metric")
        table.add_column("Average", justify="right")
        table.add_column("Min", justify="right")
        table.add_column("Max", justify="right")
        
        table.add_row("CPU %", f"{sum(cpu_vals)/len(cpu_vals):.1f}%",
                     f"{min(cpu_vals):.1f}%", f"{max(cpu_vals):.1f}%")
        table.add_row("Memory", f"{sum(mem_vals)/len(mem_vals):.0f} MB",
                     f"{min(mem_vals):.0f} MB", f"{max(mem_vals):.0f} MB")
        table.add_row("Waste/mo", f"€{sum(waste_vals)/len(waste_vals):.2f}",
                     f"€{min(waste_vals):.2f}", f"€{max(waste_vals):.2f}")
        
        console.print(table)
        console.print(f"\n[dim]Samples: {len(history)}[/dim]\n")


def _show_basic_table(containers):
    """Quick overview (no deep analysis)"""
    
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
        
        # Colors
        status = "[green]● running[/green]" if container.status == "running" else f"[yellow]○ {container.status}[/yellow]"
        
        if cpu_percent < 10:
            cpu_display = f"[green]{cpu_percent:.1f}%[/green]"
        elif cpu_percent < 50:
            cpu_display = f"[yellow]{cpu_percent:.1f}%[/yellow]"
        else:
            cpu_display = f"[red]{cpu_percent:.1f}%[/red]"
        
        mem_display = f"{mem_usage_mb:.0f} / {mem_limit_mb:.0f} MB"
        if mem_percent < 30:
            mem_display = f"[green]{mem_display}[/green]"
        elif mem_percent < 70:
            mem_display = f"[yellow]{mem_display}[/yellow]"
        else:
            mem_display = f"[red]{mem_display}[/red]"
        
        image_name = container.image.tags[0] if container.image.tags else "unknown"
        
        table.add_row(container.name, image_name, status, cpu_display, mem_display)
    
    console.print(table)
    console.print()
    
    console.print(Panel(
        f"[bold]Quick scan complete[/bold]\n"
        f"• Containers: {len(containers)}\n"
        f"• For detailed analysis: [cyan]docker-cost-analyzer scan --detailed[/cyan]\n"
        f"• Start monitoring: [cyan]docker-cost-analyzer monitor[/cyan]",
        title="📊 Summary",
        border_style="green"
    ))
    console.print()


def _show_detailed_analysis(containers):
    """Full analysis (resources + security)"""
    
    console.print("[bold cyan]🔬 Detailed analysis...[/bold cyan]\n")
    console.print("[dim]Phase 1/2: Resources...[/dim]\n")
    
    total_waste = 0
    containers_with_waste = []
    
    for i, container in enumerate(containers, 1):
        console.print(f"[dim]  {i}/{len(containers)}: {container.name}...[/dim]")
        
        analyzer = ResourceAnalyzer(container)
        wastes = analyzer.analyze()
        
        if wastes:
            containers_with_waste.append({
                'name': container.name,
                'wastes': wastes
            })
            
            for waste in wastes.values():
                total_waste += waste.monthly_cost_waste
    
    console.print()
    console.print("[dim]Phase 2/2: Security...[/dim]\n")
    
    containers_with_issues = []
    total_critical = 0
    total_high = 0
    
    for i, container in enumerate(containers, 1):
        console.print(f"[dim]  {i}/{len(containers)}: {container.name}...[/dim]")
        
        sec_analyzer = SecurityAnalyzer(container)
        issues = sec_analyzer.analyze()
        
        if issues:
            containers_with_issues.append({
                'name': container.name,
                'issues': issues
            })
            
            for issue in issues:
                if issue.severity == Severity.CRITICAL:
                    total_critical += 1
                elif issue.severity == Severity.HIGH:
                    total_high += 1
    
    console.print()
    console.print("─" * 80)
    console.print()
    
    # Display results
    if containers_with_waste:
        console.print("[bold yellow]💰 RESOURCE WASTE[/bold yellow]\n")
        
        table = Table(box=box.ROUNDED)
        table.add_column("Container", style="cyan")
        table.add_column("Resource", style="yellow")
        table.add_column("Allocated", justify="right")
        table.add_column("Used", justify="right")
        table.add_column("Waste", justify="right", style="red")
        table.add_column("Cost/mo", justify="right", style="red bold")
        
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
        console.print("[green]✓ No resource waste detected[/green]\n")
    
    if containers_with_issues:
        console.print("[bold red]🔒 SECURITY ISSUES[/bold red]\n")
        
        for item in containers_with_issues:
            console.print(f"[bold cyan]{item['name']}[/bold cyan]")
            
            for issue in item['issues']:
                if issue.severity == Severity.CRITICAL:
                    icon, color = "🔴", "red bold"
                elif issue.severity == Severity.HIGH:
                    icon, color = "🟠", "red"
                elif issue.severity == Severity.MEDIUM:
                    icon, color = "🟡", "yellow"
                else:
                    icon, color = "🔵", "blue"
                
                console.print(f"  {icon} [{color}][{issue.severity.value}][/{color}] {issue.title}")
                console.print(f"     [dim]{issue.impact}[/dim]")
                console.print(f"     [green]Fix: {issue.recommendation}[/green]")
            
            console.print()
    else:
        console.print("[green]✓ No major security issues[/green]\n")
    
    console.print("─" * 80)
    console.print()
    
    # Summary panels
    if containers_with_waste:
        console.print(Panel(
            f"[bold]💰 Financial Impact[/bold]\n\n"
            f"• Containers with waste: {len(containers_with_waste)}/{len(containers)}\n"
            f"• [red bold]Monthly waste: €{total_waste:.2f}[/red bold]\n"
            f"• [green bold]Annual savings potential: €{total_waste * 12:.2f}[/green bold]",
            border_style="yellow"
        ))
        console.print()
    
    if containers_with_issues:
        console.print(Panel(
            f"[bold]🔒 Security Summary[/bold]\n\n"
            f"• Containers with issues: {len(containers_with_issues)}/{len(containers)}\n"
            f"• Total issues: {sum(len(c['issues']) for c in containers_with_issues)}\n"
            f"• [red bold]CRITICAL: {total_critical}[/red bold]\n"
            f"• [red]HIGH: {total_high}[/red]",
            border_style="red"
        ))
        console.print()
    
    if not containers_with_waste and not containers_with_issues:
        console.print(Panel(
            "[green bold]🎉 EXCELLENT![/green bold]\n\n"
            "All containers are well-configured:\n"
            "• ✓ Resources optimized\n"
            "• ✓ Security good",
            border_style="green"
        ))
        console.print()


if __name__ == "__main__":
    cli()