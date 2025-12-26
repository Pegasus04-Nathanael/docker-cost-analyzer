# Documenter toutes les métriques disponibles:

# 1. Container Stats Stream
stats = container.stats(stream=False)
"""
Disponible:
- cpu_stats: usage, system_cpu_usage, online_cpus
- memory_stats: usage, limit, stats (cache, rss, etc)
- blkio_stats: io_service_bytes_recursive
- networks: rx_bytes, tx_bytes, rx_packets, tx_packets
- pids_stats: current
"""

# 2. Container Inspect
inspect = container.attrs
"""
Disponible:
- Config: User, ExposedPorts, Env, Cmd
- HostConfig: Memory, NanoCpus, SecurityOpt, CapAdd
- NetworkSettings: Ports, Networks
- State: Status, Running, StartedAt
- Mounts: volumes info
"""

# 3. Image Inspect
image = client.images.get(container.image.id)
"""
Disponible:
- Size: image size bytes
- RepoTags, RepoDigests
- Os, Architecture
- History: layer info
"""