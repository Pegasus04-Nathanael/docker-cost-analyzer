"""
Generate executable bash scripts to fix detected issues
"""

from typing import Dict, List
from datetime import datetime


class FixGenerator:
    """Auto-generate fix scripts"""
    
    @staticmethod
    def generate_script(container_name: str, wastes: Dict = None, 
                       issues: List = None) -> str:
        """
        Generate bash script to fix container
        
        Args:
            container_name: Name of container
            wastes: Dict from ResourceAnalyzer
            issues: List from SecurityAnalyzer
        """
        lines = [
            "#!/bin/bash",
            f"# Auto-fix for: {container_name}",
            f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "set -e  # Exit on error",
            ""
        ]
        
        # Calculate optimizations
        new_memory = None
        new_cpu = None
        savings = 0
        
        if wastes:
            if 'memory' in wastes:
                w = wastes['memory']
                new_memory_mb = int(w.used * 1.5)
                new_memory = f"{new_memory_mb}m"
                savings += w.monthly_cost_waste
                lines.append(f"# Memory: {w.allocated:.1f}GB → {new_memory_mb/1024:.2f}GB (saves €{w.monthly_cost_waste:.2f}/mo)")
            
            if 'cpu' in wastes:
                w = wastes['cpu']
                new_cpu = max(0.25, w.used * 1.5)
                savings += w.monthly_cost_waste
                lines.append(f"# CPU: {w.allocated:.1f} → {new_cpu:.2f} cores (saves €{w.monthly_cost_waste:.2f}/mo)")
        
        # Security fixes
        needs_user = False
        needs_readonly = False
        
        if issues:
            for issue in issues:
                if issue.check_name == "user_root":
                    needs_user = True
                    lines.append("# Security: Add non-root user")
                elif issue.check_name == "writable_rootfs":
                    needs_readonly = True
                    lines.append("# Security: Make filesystem read-only")
        
        lines.extend([
            "",
            f"# TOTAL SAVINGS: €{savings:.2f}/month (€{savings*12:.2f}/year)",
            "",
            "echo '⚠️  This will restart the container'",
            "read -p 'Continue? (y/n) ' -n 1 -r",
            "echo",
            "[[ ! $REPLY =~ ^[Yy]$ ]] && exit 1",
            "",
            "echo '🔄 Stopping container...'",
            f"docker stop {container_name}",
            f"docker rm {container_name}",
            "",
            "echo '🚀 Starting optimized container...'",
            "docker run -d \\"
        ])
        
        # Add optimizations
        if new_memory:
            lines.append(f"  --memory={new_memory} \\")
        if new_cpu:
            lines.append(f"  --cpus={new_cpu:.2f} \\")
        if needs_user:
            lines.append("  --user=1000:1000 \\")
        if needs_readonly:
            lines.append("  --read-only \\")
            lines.append("  --tmpfs /tmp \\")
        
        lines.extend([
            f"  --name {container_name} \\",
            "  # TODO: Replace with your image and other flags",
            "  YOUR_IMAGE:TAG",
            "",
            "echo '✅ Done!'",
            f"echo '💰 Saving €{savings:.2f}/month'",
            ""
        ])
        
        return "\n".join(lines)