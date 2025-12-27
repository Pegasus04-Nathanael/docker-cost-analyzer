"""
SECURITY.PY - Analyseur de sécurité Docker

Détecte les vulnérabilités et mauvaises pratiques de sécurité
"""

from dataclasses import dataclass
from typing import List
from enum import Enum


class Severity(Enum):
    """Niveaux de sévérité des issues"""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


@dataclass
class SecurityIssue:
    """Issue de sécurité détectée"""
    check_name: str          # Nom du check (ex: "user_root")
    severity: Severity       # Niveau de gravité
    title: str              # Titre court
    description: str        # Description du problème
    impact: str             # Impact si exploité
    recommendation: str     # Comment corriger
    
    def __str__(self):
        """Affichage lisible"""
        return f"[{self.severity.value}] {self.title}"


class SecurityAnalyzer:
    """
    Analyse la sécurité d'un container Docker
    
    Checks implémentés :
    1. User root
    2. Ports exposés publiquement
    3. Capabilities Linux dangereuses
    4. Mode privileged
    5. Secrets dans env vars
    6. Root filesystem writable
    7. Security options désactivées
    8. Image outdated
    """
    
    # Capabilities Linux dangereuses
    DANGEROUS_CAPS = {
        'ALL',           # Toutes les capabilities
        'SYS_ADMIN',     # Administration système
        'NET_ADMIN',     # Administration réseau
        'SYS_PTRACE',    # Tracer d'autres processus
        'SYS_MODULE',    # Charger modules kernel
        'DAC_OVERRIDE',  # Bypass permissions fichiers
    }
    
    # Ports sensibles (services critiques)
    SENSITIVE_PORTS = {
        22: 'SSH',
        3306: 'MySQL',
        5432: 'PostgreSQL',
        6379: 'Redis',
        27017: 'MongoDB',
        9200: 'Elasticsearch',
        5984: 'CouchDB',
        3389: 'RDP',
    }
    
    def __init__(self, container):
        """
        Args:
            container: Objet Docker container
        """
        self.container = container
        self.inspect = container.attrs  # Infos complètes du container
    
    def analyze(self) -> List[SecurityIssue]:
        """
        Exécute tous les checks de sécurité
        
        Returns:
            Liste des issues détectées (vide si aucun problème)
        """
        issues = []
        
        # Exécuter tous les checks
        issues.extend(self._check_user())
        issues.extend(self._check_exposed_ports())
        issues.extend(self._check_capabilities())
        issues.extend(self._check_privileged())
        issues.extend(self._check_secrets_in_env())
        issues.extend(self._check_readonly_rootfs())
        issues.extend(self._check_security_opts())
        issues.extend(self._check_image_age())
        
        # Trier par sévérité (CRITICAL en premier)
        severity_order = {
            Severity.CRITICAL: 0,
            Severity.HIGH: 1,
            Severity.MEDIUM: 2,
            Severity.LOW: 3,
            Severity.INFO: 4
        }
        issues.sort(key=lambda x: severity_order[x.severity])
        
        return issues
    
    def _check_user(self) -> List[SecurityIssue]:
        """Check si le container tourne en root"""
        user = self.inspect['Config'].get('User', '')
        
        # Valeurs qui signifient "root"
        if user in ['', 'root', '0', '0:0']:
            return [SecurityIssue(
                check_name="user_root",
                severity=Severity.CRITICAL,
                title="Container running as root",
                description=f"Le container tourne avec l'utilisateur root (UID 0)",
                impact="Si le container est compromis, l'attaquant a accès root et peut échapper du container",
                recommendation="Ajouter 'USER 1000' dans le Dockerfile ou utiliser --user=1000:1000"
            )]
        
        return []
    
    def _check_exposed_ports(self) -> List[SecurityIssue]:
        """Check les ports exposés à internet (0.0.0.0)"""
        issues = []
        ports = self.inspect['NetworkSettings']['Ports'] or {}
        
        for container_port, bindings in ports.items():
            if not bindings:
                continue
            
            # Extraire le numéro de port
            port_num = int(container_port.split('/')[0])
            port_proto = container_port.split('/')[1] if '/' in container_port else 'tcp'
            
            for binding in bindings:
                host_ip = binding.get('HostIp', '')
                host_port = binding.get('HostPort', '')
                
                # Port exposé sur toutes interfaces (0.0.0.0 = internet)
                if host_ip in ['0.0.0.0', '']:
                    # Déterminer sévérité selon le port
                    if port_num in self.SENSITIVE_PORTS:
                        severity = Severity.CRITICAL
                        service = self.SENSITIVE_PORTS[port_num]
                        title = f"{service} exposed to internet"
                    else:
                        severity = Severity.HIGH
                        service = "Service"
                        title = f"Port {port_num} exposed to internet"
                    
                    issues.append(SecurityIssue(
                        check_name="public_port_exposure",
                        severity=severity,
                        title=title,
                        description=f"Port {port_num}/{port_proto} est accessible depuis internet (0.0.0.0:{host_port})",
                        impact=f"N'importe qui sur internet peut accéder à ce service. Risque de brute-force, exploitation de CVE",
                        recommendation=f"Bind sur 127.0.0.1 uniquement : -p 127.0.0.1:{host_port}:{port_num} ou utilisez un firewall"
                    ))
        
        return issues
    
    def _check_capabilities(self) -> List[SecurityIssue]:
        """Check les capabilities Linux ajoutées"""
        issues = []
        caps_add = set(self.inspect['HostConfig'].get('CapAdd') or [])
        
        # Trouver les capabilities dangereuses
        dangerous = caps_add & self.DANGEROUS_CAPS
        
        if dangerous:
            caps_list = ', '.join(sorted(dangerous))
            
            # ALL est particulièrement dangereux
            if 'ALL' in dangerous:
                severity = Severity.CRITICAL
                title = "All capabilities granted"
            else:
                severity = Severity.HIGH
                title = f"Dangerous capabilities: {caps_list}"
            
            issues.append(SecurityIssue(
                check_name="dangerous_capabilities",
                severity=severity,
                title=title,
                description=f"Capabilities dangereuses accordées : {caps_list}",
                impact="Ces capabilities donnent des privilèges kernel élevés qui peuvent être exploités pour échapper du container",
                recommendation=f"Retirer capabilities : --cap-drop={caps_list} ou n'ajouter que les capabilities nécessaires"
            ))
        
        return issues
    
    def _check_privileged(self) -> List[SecurityIssue]:
        """Check si le container est en mode privileged"""
        if self.inspect['HostConfig'].get('Privileged', False):
            return [SecurityIssue(
                check_name="privileged_mode",
                severity=Severity.CRITICAL,
                title="Container running in privileged mode",
                description="Le container tourne avec --privileged",
                impact="Accès complet au host système. Le container peut faire absolument n'importe quoi : charger modules kernel, accéder devices, etc. Équivaut à root sur le host",
                recommendation="Retirer --privileged. Utiliser --cap-add pour ajouter seulement les capabilities nécessaires"
            )]
        
        return []
    
    def _check_secrets_in_env(self) -> List[SecurityIssue]:
        """Check les secrets potentiels dans variables d'environnement"""
        issues = []
        env_vars = self.inspect['Config'].get('Env', [])
        
        # Patterns de noms de variables sensibles
        secret_patterns = [
            'PASSWORD', 'PASSWD', 'PWD',
            'SECRET', 'KEY', 'TOKEN',
            'API_KEY', 'APIKEY',
            'AUTH', 'CREDENTIAL',
            'PRIVATE'
        ]
        
        for env in env_vars:
            if '=' not in env:
                continue
            
            key, value = env.split('=', 1)
            key_upper = key.upper()
            
            # Check si le nom contient un pattern suspect
            if any(pattern in key_upper for pattern in secret_patterns):
                # Vérifier que ce n'est pas vide ou une valeur placeholder
                if value and value not in ['', 'changeme', 'TODO', 'xxx']:
                    issues.append(SecurityIssue(
                        check_name="secret_in_env",
                        severity=Severity.MEDIUM,
                        title=f"Potential secret in env: {key}",
                        description=f"Variable d'environnement '{key}' semble contenir un secret",
                        impact="Secrets visibles via 'docker inspect', logs, /proc/. Peuvent fuiter dans monitoring, crash dumps",
                        recommendation="Utiliser Docker secrets (Swarm) ou secrets manager (Kubernetes, Vault). Ou monter fichier via volume read-only"
                    ))
        
        return issues
    
    def _check_readonly_rootfs(self) -> List[SecurityIssue]:
        """Check si le filesystem root est read-only"""
        if not self.inspect['HostConfig'].get('ReadonlyRootfs', False):
            return [SecurityIssue(
                check_name="writable_rootfs",
                severity=Severity.LOW,
                title="Root filesystem is writable",
                description="Le filesystem root du container est modifiable",
                impact="Un attaquant peut modifier binaires, installer backdoors, persister sur le filesystem",
                recommendation="Utiliser --read-only avec tmpfs pour /tmp : --read-only --tmpfs /tmp"
            )]
        
        return []
    
    def _check_security_opts(self) -> List[SecurityIssue]:
        """Check les security options (AppArmor, SELinux, Seccomp)"""
        issues = []
        sec_opts = self.inspect['HostConfig'].get('SecurityOpt', [])
        
        # Check si AppArmor désactivé
        if 'apparmor=unconfined' in sec_opts:
            issues.append(SecurityIssue(
                check_name="apparmor_disabled",
                severity=Severity.MEDIUM,
                title="AppArmor disabled",
                description="AppArmor est désactivé (apparmor=unconfined)",
                impact="Pas de Mandatory Access Control. Le kernel ne limite pas les actions du container",
                recommendation="Retirer 'apparmor=unconfined' pour utiliser le profil par défaut"
            ))
        
        # Check si Seccomp désactivé
        if 'seccomp=unconfined' in sec_opts:
            issues.append(SecurityIssue(
                check_name="seccomp_disabled",
                severity=Severity.HIGH,
                title="Seccomp disabled",
                description="Seccomp est désactivé (seccomp=unconfined)",
                impact="Aucun filtrage des syscalls. Le container peut appeler n'importe quel syscall kernel, y compris les dangereux",
                recommendation="Retirer 'seccomp=unconfined' ou créer profil seccomp custom"
            ))
        
        return issues
    
    def _check_image_age(self) -> List[SecurityIssue]:
        """Check si l'image est ancienne (non mise à jour)"""
        try:
            from datetime import datetime, timedelta
            import docker
            
            client = docker.from_env()
            image = client.images.get(self.container.image.id)
            
            # Date de création de l'image
            created_str = image.attrs['Created']
            # Format: "2024-01-15T10:30:00.000000000Z"
            created_date = datetime.fromisoformat(created_str.replace('Z', '+00:00'))
            
            # Calculer l'âge
            now = datetime.now(created_date.tzinfo)
            age_days = (now - created_date).days
            
            # Alerte si image > 180 jours (6 mois)
            if age_days > 180:
                severity = Severity.MEDIUM if age_days > 365 else Severity.LOW
                
                return [SecurityIssue(
                    check_name="outdated_image",
                    severity=severity,
                    title=f"Image is {age_days} days old",
                    description=f"L'image Docker a {age_days} jours ({age_days//30} mois)",
                    impact="Image potentiellement avec CVE connus, packages non patchés",
                    recommendation=f"Rebuild l'image avec la dernière version de base. Tag actuel : {image.tags[0] if image.tags else 'none'}"
                )]
        
        except Exception as e:
            # Si erreur, ne pas bloquer l'analyse
            pass
        
        return []
    
    def get_summary(self) -> dict:
        """Résumé rapide des issues par sévérité"""
        issues = self.analyze()
        
        summary = {
            'total': len(issues),
            'critical': sum(1 for i in issues if i.severity == Severity.CRITICAL),
            'high': sum(1 for i in issues if i.severity == Severity.HIGH),
            'medium': sum(1 for i in issues if i.severity == Severity.MEDIUM),
            'low': sum(1 for i in issues if i.severity == Severity.LOW),
        }
        
        return summary