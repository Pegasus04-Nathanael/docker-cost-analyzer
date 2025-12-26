# src/analyzers/security.py

from enum import Enum
from dataclasses import dataclass
from typing import List

class Severity(Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"

@dataclass
class SecurityIssue:
    check_name: str
    severity: Severity
    description: str
    impact: str
    recommendation: str
    references: List[str]

class SecurityAnalyzer:
    """Comprehensive security analysis"""
    
    DANGEROUS_CAPS = {'ALL', 'SYS_ADMIN', 'NET_ADMIN', 'SYS_PTRACE'}
    DANGEROUS_PORTS = {22, 3306, 5432, 6379, 27017}  # SSH, MySQL, Postgres, Redis, Mongo
    
    def __init__(self, container):
        self.container = container
        self.inspect = container.attrs
    
    def analyze(self) -> List[SecurityIssue]:
        """Run all security checks"""
        issues = []
        
        issues.extend(self._check_user())
        issues.extend(self._check_capabilities())
        issues.extend(self._check_exposed_ports())
        issues.extend(self._check_privileged())
        issues.extend(self._check_secrets())
        issues.extend(self._check_readonly_rootfs())
        issues.extend(self._check_security_opts())
        issues.extend(self._check_image_age())
        
        return issues
    
    def _check_user(self) -> List[SecurityIssue]:
        """Check if running as root"""
        user = self.inspect['Config'].get('User', '')
        
        if user in ['', 'root', '0', '0:0']:
            return [SecurityIssue(
                check_name="user_root",
                severity=Severity.CRITICAL,
                description="Container running as root user",
                impact="If container compromised, attacker has root access",
                recommendation="Add 'USER 1000' to Dockerfile or use --user flag",
                references=[
                    "https://docs.docker.com/develop/develop-images/dockerfile_best-practices/#user"
                ]
            )]
        return []
    
    def _check_capabilities(self) -> List[SecurityIssue]:
        """Check dangerous Linux capabilities"""
        issues = []
        caps_add = set(self.inspect['HostConfig'].get('CapAdd') or [])
        
        dangerous = caps_add & self.DANGEROUS_CAPS
        if dangerous:
            issues.append(SecurityIssue(
                check_name="dangerous_capabilities",
                severity=Severity.HIGH,
                description=f"Dangerous capabilities granted: {', '.join(dangerous)}",
                impact="Elevated privileges can be exploited",
                recommendation=f"Remove capabilities: {', '.join(dangerous)}",
                references=[
                    "https://man7.org/linux/man-pages/man7/capabilities.7.html"
                ]
            ))
        
        return issues
    
    def _check_exposed_ports(self) -> List[SecurityIssue]:
        """Check publicly exposed sensitive ports"""
        issues = []
        ports = self.inspect['NetworkSettings']['Ports'] or {}
        
        for container_port, bindings in ports.items():
            if not bindings:
                continue
            
            port_num = int(container_port.split('/')[0])
            
            for binding in bindings:
                host_ip = binding.get('HostIp', '')
                
                # Port exposed to all interfaces
                if host_ip == '0.0.0.0':
                    severity = Severity.CRITICAL if port_num in self.DANGEROUS_PORTS else Severity.HIGH
                    
                    issues.append(SecurityIssue(
                        check_name="public_port_exposure",
                        severity=severity,
                        description=f"Port {port_num} exposed to 0.0.0.0 (public internet)",
                        impact="Service accessible from anywhere, potential attack vector",
                        recommendation=f"Bind to 127.0.0.1:{port_num} or use firewall",
                        references=["https://docs.docker.com/config/containers/container-networking/"]
                    ))
        
        return issues
    
    def _check_privileged(self) -> List[SecurityIssue]:
        """Check if container runs in privileged mode"""
        if self.inspect['HostConfig'].get('Privileged', False):
            return [SecurityIssue(
                check_name="privileged_mode",
                severity=Severity.CRITICAL,
                description="Container running in privileged mode",
                impact="Full access to host system, can escape container",
                recommendation="Remove --privileged flag, use specific capabilities instead",
                references=["https://docs.docker.com/engine/reference/run/#runtime-privilege-and-linux-capabilities"]
            )]
        return []
    
    def _check_secrets(self) -> List[SecurityIssue]:
        """Check for secrets in environment variables"""
        issues = []
        env_vars = self.inspect['Config'].get('Env', [])
        
        secret_patterns = ['PASSWORD', 'SECRET', 'KEY', 'TOKEN', 'API_KEY']
        
        for env in env_vars:
            if '=' not in env:
                continue
            
            key, value = env.split('=', 1)
            
            # Check if looks like a secret
            if any(pattern in key.upper() for pattern in secret_patterns):
                if value and len(value) > 5:  # Not empty
                    issues.append(SecurityIssue(
                        check_name="secret_in_env",
                        severity=Severity.MEDIUM,
                        description=f"Potential secret in environment variable: {key}",
                        impact="Secrets visible in docker inspect, logs",
                        recommendation="Use Docker secrets or secret management tool",
                        references=["https://docs.docker.com/engine/swarm/secrets/"]
                    ))
        
        return issues
    
    def _check_readonly_rootfs(self) -> List[SecurityIssue]:
        """Check if root filesystem is read-only"""
        if not self.inspect['HostConfig'].get('ReadonlyRootfs', False):
            return [SecurityIssue(
                check_name="writable_rootfs",
                severity=Severity.LOW,
                description="Root filesystem is writable",
                impact="Attacker can modify container filesystem",
                recommendation="Use --read-only flag with tmpfs mounts for /tmp",
                references=["https://docs.docker.com/engine/reference/run/#security-configuration"]
            )]
        return []
    
    def _check_security_opts(self) -> List[SecurityIssue]:
        """Check security options (AppArmor, SELinux, Seccomp)"""
        issues = []
        sec_opts = self.inspect['HostConfig'].get('SecurityOpt', [])
        
        # Check if security features disabled
        if 'apparmor=unconfined' in sec_opts:
            issues.append(SecurityIssue(
                check_name="apparmor_disabled",
                severity=Severity.MEDIUM,
                description="AppArmor disabled",
                impact="Reduced kernel security protections",
                recommendation="Remove apparmor=unconfined",
                references=[]
            ))
        
        if 'seccomp=unconfined' in sec_opts:
            issues.append(SecurityIssue(
                check_name="seccomp_disabled",
                severity=Severity.HIGH,
                description="Seccomp disabled",
                impact="No syscall filtering, increased attack surface",
                recommendation="Remove seccomp=unconfined or use custom profile",
                references=["https://docs.docker.com/engine/security/seccomp/"]
            ))
        
        return issues
    
    def _check_image_age(self) -> List[SecurityIssue]:
        """Check if image is outdated"""
        from datetime import datetime, timedelta
        import docker
        
        
        try:
            client = docker.from_env()
            image = client.images.get(self.container.image.id)
            
            created = image.attrs['Created']
            created_date = datetime.fromisoformat(created.replace('Z', '+00:00'))
            age_days = (datetime.now(created_date.tzinfo) - created_date).days
            
            if age_days > 180:  # 6 months
                return [SecurityIssue(
                    check_name="outdated_image",
                    severity=Severity.MEDIUM,
                    description=f"Image is {age_days} days old",
                    impact="Missing security patches and updates",
                    recommendation="Rebuild image with latest base image",
                    references=[]
                )]
        except:
            pass
        
        return []