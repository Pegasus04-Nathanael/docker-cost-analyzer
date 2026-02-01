# Docker Cost Analyzer

CLI tool to analyze Docker containers for resource waste and security vulnerabilities.

## Features

**Resource Analysis**
- Detect over-provisioned containers (CPU/RAM under 20-30% usage)
- Calculate monthly waste costs in EUR
- Generate optimized resource recommendations
- Historical trend analysis with SQLite storage

**Security Analysis**
- 8 security checks with severity levels (CRITICAL/HIGH/MEDIUM/LOW)
- Root user detection
- Privileged mode and dangerous capabilities
- Exposed ports and secrets in environment variables
- Outdated images and security options

**Automation**
- Continuous monitoring with configurable intervals
- Auto-generate fix scripts (bash)
- Alert when waste exceeds threshold

## Installation
```bash
git clone https://github.com/Pegasus04-Nathanael/docker-cost-analyzer.git
cd docker-cost-analyzer
pip install -e .
```

## Quick Start
```bash
# One-time scan
docker-cost-analyzer scan --detailed

# Continuous monitoring (5min intervals)
docker-cost-analyzer monitor

# Generate fix script
docker-cost-analyzer fix container-name

# View trends
docker-cost-analyzer trends container-name
```

## Commands

### scan
Analyze all running containers.
```bash
docker-cost-analyzer scan              # Quick overview
docker-cost-analyzer scan --detailed   # Full analysis with security
```

### monitor
Continuous background monitoring with alerts.
```bash
docker-cost-analyzer monitor                        # Default: 5min intervals
docker-cost-analyzer monitor --interval=60          # Custom interval (seconds)
docker-cost-analyzer monitor --threshold=100        # Alert threshold (EUR/month)
```

### fix
Generate bash script to optimize a container.
```bash
docker-cost-analyzer fix nginx-prod                 # Generate fix-nginx-prod.sh
docker-cost-analyzer fix api --output=optimize.sh   # Custom output file
```

### trends
View historical metrics from monitoring data.
```bash
docker-cost-analyzer trends                    # List all monitored containers
docker-cost-analyzer trends nginx-prod         # Show specific container
docker-cost-analyzer trends api --days=30      # 30-day history
```

## How It Works

### Resource Waste Detection

The tool collects metrics from Docker Stats API and compares against configured limits:
```
Waste detected when:
- CPU usage < 20% of allocated
- Memory usage < 30% of allocated

Cost calculation:
- CPU: 0.025 EUR/vCPU/hour
- Memory: 0.008 EUR/GB/hour
- Based on AWS/GCP/Azure averages (EU region)
```

### Security Checks

Inspects container configuration via Docker Inspect API:

| Check | Severity | Detection |
|-------|----------|-----------|
| Running as root | CRITICAL | User == root or empty |
| Privileged mode | CRITICAL | Privileged == true |
| Sensitive ports exposed | CRITICAL/HIGH | Ports bound to 0.0.0.0 |
| Dangerous capabilities | HIGH | CAP_SYS_ADMIN, CAP_NET_ADMIN, etc. |
| Secrets in env vars | MEDIUM | PASSWORD, SECRET, KEY patterns |
| Writable filesystem | LOW | ReadonlyRootfs == false |
| Outdated image | MEDIUM | Created > 180 days ago |

### Continuous Monitoring

Runs in background, collecting metrics at intervals:
```
Loop:
  1. Scan all containers
  2. Calculate waste and costs
  3. Check security issues
  4. Store metrics in SQLite (~/.docker-cost-analyzer/metrics.db)
  5. Alert if threshold exceeded
  6. Sleep (interval seconds)
```

## Example Output
```
RESOURCE WASTE
Container     Resource   Allocated    Used      Waste    Cost/mo
api-backend   CPU        2.00 vCPU    0.15 vCPU   92%    €33.58
api-backend   MEMORY     4.00 GB      0.50 GB     87%    €20.42

SECURITY ISSUES
api-backend
  [CRITICAL] Container running as root
     Impact: Full container escape if compromised
     Fix: Add 'USER 1000' to Dockerfile

Financial Impact
- Monthly waste: €53.00
- Annual savings potential: €636.00
```

## Technical Details

**Architecture**
```
src/
├── cli.py                  # Click-based CLI
├── analyzers/
│   ├── resources.py        # Docker Stats API integration
│   └── security.py         # Docker Inspect analysis
├── monitoring/
│   ├── database.py         # SQLite persistence
│   └── monitor.py          # Background daemon
└── generators/
    └── fixes.py            # Bash script generation
```

**Requirements**
- Python 3.10+
- Docker daemon accessible
- Linux, macOS, or Windows WSL2

**Pricing Methodology**

Costs based on averages from:
- AWS EC2 (eu-west-3): t3.medium, c5 instances
- GCP Compute (europe-west1): n1-standard instances  
- Azure VMs (West Europe): Standard_B series

See `docs/PRICING.md` for detailed breakdown with sources.

**Accuracy**: ±30-50% depending on:
- Your cloud provider and region
- Instance type (burstable vs compute-optimized)
- Reserved instance discounts
- Spot/preemptible pricing

## Limitations

- Only analyzes running containers (stopped containers ignored)
- Docker only (Kubernetes not yet supported)
- No CVE scanning (use Trivy for that)
- No automated remediation (generates scripts only)
- SQLite may be slow with >100 containers
- Cost estimates are averages, not exact billing

## Development Status

**Current: v0.2.0 (Alpha)**

Working:
- Core analysis (CPU, memory, security)
- CLI with 4 commands
- SQLite monitoring
- Script generation
- pip install -e . installation

Not yet:
- Automated tests
- PyPI package
- Kubernetes support
- JSON/HTML exports
- Webhook/Slack alerts

## Roadmap

- Automated test suite (pytest)
- Error handling and input validation
- PyPI publication
- Kubernetes pod analysis
- Export formats (JSON, HTML, CSV)
- Alert integrations (Slack, Discord, webhooks)
- Docker image distribution
- Multi-server/cluster support

## Contributing

This is a portfolio project for PhD applications. Contributions welcome after v1.0 release.

## Author

Nathanael Fetue Foko  
Student: ISAE-SUPAERO / ENSEEIHT  
GitHub: [@Pegasus04-Nathanael](https://github.com/Pegasus04-Nathanael)

## License

MIT License - see LICENSE file

## Acknowledgments

Built with:
- Docker SDK for Python
- Click (CLI framework)
- Rich (terminal UI)
- SQLite (data persistence)

Pricing data from AWS, GCP, Azure public documentation.