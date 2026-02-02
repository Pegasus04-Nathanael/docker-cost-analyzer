"""
SQLite storage for container metrics history
Stores: CPU, memory, waste costs, security events over time
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict


class MetricsDB:
    """Persistent storage for container metrics"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            # Store in user home: ~/.docker-cost-analyzer/metrics.db
            db_path = Path.home() / ".docker-cost-analyzer" / "metrics.db"
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Create tables if not exist"""
        with sqlite3.connect(self.db_path) as conn:
            # Metrics table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    container_id TEXT NOT NULL,
                    container_name TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    cpu_percent REAL,
                    memory_usage_mb REAL,
                    memory_limit_mb REAL,
                    waste_cpu_cost REAL DEFAULT 0,
                    waste_memory_cost REAL DEFAULT 0
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_container_time 
                ON metrics(container_id, timestamp DESC)
            """)
            
            # Security events table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS security_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    container_id TEXT NOT NULL,
                    container_name TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    severity TEXT NOT NULL,
                    check_name TEXT NOT NULL,
                    title TEXT NOT NULL
                )
            """)
    
    def store_metric(self, container_id: str, container_name: str,
                     cpu_percent: float, memory_usage_mb: float,
                     memory_limit_mb: float, waste_cpu_cost: float = 0,
                     waste_memory_cost: float = 0):
        """Store single metric snapshot"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO metrics 
                (container_id, container_name, timestamp, cpu_percent,
                 memory_usage_mb, memory_limit_mb, waste_cpu_cost, waste_memory_cost)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (container_id, container_name, datetime.now(),
                  cpu_percent, memory_usage_mb, memory_limit_mb,
                  waste_cpu_cost, waste_memory_cost))
    
    def get_history(self, container_name: str, days: int = 7) -> List[Dict]:
        """Get metrics history for container by name"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM metrics
                WHERE container_name = ?
                AND timestamp >= datetime('now', '-' || ? || ' days')
                ORDER BY timestamp DESC
            """, (container_name, days))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_all_containers(self) -> List[str]:
        """List all monitored containers"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT DISTINCT container_name
                FROM metrics
                ORDER BY container_name
            """)
            return [row[0] for row in cursor.fetchall()]
    
    def store_security_event(self, container_id: str, container_name: str,
                            severity: str, check_name: str, title: str):
        """Store security issue detection"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO security_events
                (container_id, container_name, timestamp, severity, check_name, title)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (container_id, container_name, datetime.now(),
                  severity, check_name, title))
    
    def get_waste_trend(self, container_name: str, days: int = 30) -> Dict:
        """Calculate waste trend over time"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT 
                    AVG(waste_cpu_cost + waste_memory_cost) as avg_waste,
                    MAX(waste_cpu_cost + waste_memory_cost) as max_waste,
                    MIN(waste_cpu_cost + waste_memory_cost) as min_waste,
                    COUNT(*) as samples
                FROM metrics
                WHERE container_name = ?
                  AND timestamp >= datetime('now', '-' || ? || ' days')
            """, (container_name, days))
            
            row = cursor.fetchone()
            return {
                'avg_waste': row[0] or 0,
                'max_waste': row[1] or 0,
                'min_waste': row[2] or 0,
                'samples': row[3]
            }