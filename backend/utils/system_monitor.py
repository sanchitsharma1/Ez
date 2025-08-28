import asyncio
import logging
import psutil
import platform
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import json

from core.config import settings
from core.redis_client import redis_client

logger = logging.getLogger(__name__)

class SystemMonitor:
    """System monitoring service for Alex agent"""
    
    def __init__(self):
        self.monitoring_interval = settings.SYSTEM_MONITORING_INTERVAL
        self.metrics_retention = settings.SYSTEM_METRICS_RETENTION
        self.monitoring_task: Optional[asyncio.Task] = None
        self.initialized = False
    
    async def initialize(self):
        """Initialize system monitor"""
        try:
            # Test system access
            psutil.cpu_percent()  # Initialize CPU monitoring
            psutil.virtual_memory()
            psutil.disk_usage('/')
            
            # Start monitoring task
            self.monitoring_task = asyncio.create_task(self._monitoring_loop())
            
            self.initialized = True
            logger.info("System monitor initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize system monitor: {e}")
            raise
    
    async def _monitoring_loop(self):
        """Background monitoring loop"""
        while True:
            try:
                await asyncio.sleep(self.monitoring_interval)
                await self._collect_metrics()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
    
    async def _collect_metrics(self):
        """Collect and store system metrics"""
        try:
            metrics = await self.get_current_metrics()
            
            # Store in Redis with timestamp
            timestamp = datetime.utcnow().isoformat()
            await redis_client.list_push(
                "system_metrics:history",
                {
                    "timestamp": timestamp,
                    "metrics": metrics
                }
            )
            
            # Keep only recent metrics (last 24 hours by default)
            max_items = int(24 * 3600 / self.monitoring_interval)  # 24 hours worth
            
            # Trim the list to keep only recent metrics
            current_length = await redis_client.redis.llen("system_metrics:history")
            if current_length > max_items:
                await redis_client.redis.ltrim("system_metrics:history", 0, max_items - 1)
            
            # Store latest metrics separately for quick access
            await redis_client.set("system_metrics:latest", metrics, expire=self.monitoring_interval * 2)
            
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")
    
    async def get_current_metrics(self) -> Dict[str, Any]:
        """Get current system metrics"""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()
            
            # Memory metrics
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            # Disk metrics
            disk_usage = psutil.disk_usage('/')
            disk_io = psutil.disk_io_counters()
            
            # Network metrics
            network_io = psutil.net_io_counters()
            
            # System info
            boot_time = psutil.boot_time()
            uptime = datetime.now().timestamp() - boot_time
            
            # Process info
            process_count = len(psutil.pids())
            
            return {
                # System identification
                "hostname": platform.node(),
                "os": f"{platform.system()} {platform.release()}",
                "architecture": platform.architecture()[0],
                
                # CPU metrics
                "cpu_percent": cpu_percent,
                "cpu_count": cpu_count,
                "cpu_freq_current": cpu_freq.current if cpu_freq else None,
                "cpu_freq_max": cpu_freq.max if cpu_freq else None,
                
                # Memory metrics
                "memory_total": memory.total,
                "memory_used": memory.used,
                "memory_free": memory.free,
                "memory_percent": memory.percent,
                "memory_available": memory.available,
                
                # Swap metrics
                "swap_total": swap.total,
                "swap_used": swap.used,
                "swap_free": swap.free,
                "swap_percent": swap.percent,
                
                # Disk metrics
                "disk_total": disk_usage.total,
                "disk_used": disk_usage.used,
                "disk_free": disk_usage.free,
                "disk_percent": disk_usage.percent,
                "disk_read_bytes": disk_io.read_bytes if disk_io else 0,
                "disk_write_bytes": disk_io.write_bytes if disk_io else 0,
                
                # Network metrics
                "network_sent": network_io.bytes_sent if network_io else 0,
                "network_recv": network_io.bytes_recv if network_io else 0,
                "network_packets_sent": network_io.packets_sent if network_io else 0,
                "network_packets_recv": network_io.packets_recv if network_io else 0,
                
                # System metrics
                "uptime": uptime,
                "boot_time": boot_time,
                "process_count": process_count,
                
                # Timestamp
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting current metrics: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def get_historical_metrics(self, hours: int = 1) -> List[Dict[str, Any]]:
        """Get historical metrics for the specified time period"""
        try:
            # Calculate how many entries to fetch
            entries_needed = int(hours * 3600 / self.monitoring_interval)
            
            # Get metrics from Redis
            metrics_list = await redis_client.list_range(
                "system_metrics:history", 
                0, 
                entries_needed - 1
            )
            
            # Filter by time if needed
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            filtered_metrics = []
            for metric_entry in metrics_list:
                if isinstance(metric_entry, dict):
                    timestamp_str = metric_entry.get("timestamp")
                    if timestamp_str:
                        try:
                            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                            if timestamp >= cutoff_time:
                                filtered_metrics.append(metric_entry.get("metrics", {}))
                        except ValueError:
                            continue
            
            return filtered_metrics
            
        except Exception as e:
            logger.error(f"Error getting historical metrics: {e}")
            return []
    
    async def get_process_list(self, sort_by: str = "cpu_percent") -> List[Dict[str, Any]]:
        """Get list of running processes"""
        try:
            processes = []
            
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'memory_info', 'status', 'create_time']):
                try:
                    proc_info = proc.info
                    proc_info['memory_info'] = proc_info['memory_info'].rss if proc_info['memory_info'] else 0
                    proc_info['create_time'] = datetime.fromtimestamp(proc_info['create_time']).isoformat() if proc_info['create_time'] else None
                    processes.append(proc_info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # Sort processes
            if sort_by in ["cpu_percent", "memory_percent"]:
                processes.sort(key=lambda x: x.get(sort_by, 0), reverse=True)
            elif sort_by == "name":
                processes.sort(key=lambda x: x.get("name", "").lower())
            
            return processes
            
        except Exception as e:
            logger.error(f"Error getting process list: {e}")
            return []
    
    async def get_network_connections(self) -> List[Dict[str, Any]]:
        """Get active network connections"""
        try:
            connections = []
            
            for conn in psutil.net_connections():
                if conn.status == psutil.CONN_ESTABLISHED:
                    connections.append({
                        "local_address": f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else "unknown",
                        "remote_address": f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else "unknown",
                        "status": conn.status,
                        "pid": conn.pid,
                        "family": conn.family.name if hasattr(conn.family, 'name') else str(conn.family),
                        "type": conn.type.name if hasattr(conn.type, 'name') else str(conn.type)
                    })
            
            return connections
            
        except Exception as e:
            logger.error(f"Error getting network connections: {e}")
            return []
    
    async def get_disk_io_stats(self) -> Dict[str, Any]:
        """Get disk I/O statistics"""
        try:
            disk_io = psutil.disk_io_counters(perdisk=True)
            
            stats = {}
            for device, counters in disk_io.items():
                stats[device] = {
                    "read_count": counters.read_count,
                    "write_count": counters.write_count,
                    "read_bytes": counters.read_bytes,
                    "write_bytes": counters.write_bytes,
                    "read_time": counters.read_time,
                    "write_time": counters.write_time
                }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting disk I/O stats: {e}")
            return {}
    
    async def detect_anomalies(self, threshold_multiplier: float = 2.0) -> List[Dict[str, Any]]:
        """Detect system anomalies based on historical data"""
        try:
            anomalies = []
            current_metrics = await self.get_current_metrics()
            historical_metrics = await self.get_historical_metrics(hours=24)
            
            if len(historical_metrics) < 10:
                return []  # Need enough historical data
            
            # Check CPU anomalies
            cpu_values = [m.get('cpu_percent', 0) for m in historical_metrics]
            cpu_avg = sum(cpu_values) / len(cpu_values)
            cpu_current = current_metrics.get('cpu_percent', 0)
            
            if cpu_current > cpu_avg * threshold_multiplier:
                anomalies.append({
                    "type": "cpu_spike",
                    "metric": "cpu_percent",
                    "current_value": cpu_current,
                    "average_value": cpu_avg,
                    "severity": "high" if cpu_current > 90 else "medium",
                    "description": f"CPU usage ({cpu_current:.1f}%) is {cpu_current/cpu_avg:.1f}x higher than average"
                })
            
            # Check memory anomalies
            memory_values = [m.get('memory_percent', 0) for m in historical_metrics]
            memory_avg = sum(memory_values) / len(memory_values)
            memory_current = current_metrics.get('memory_percent', 0)
            
            if memory_current > memory_avg * threshold_multiplier:
                anomalies.append({
                    "type": "memory_spike",
                    "metric": "memory_percent",
                    "current_value": memory_current,
                    "average_value": memory_avg,
                    "severity": "high" if memory_current > 90 else "medium",
                    "description": f"Memory usage ({memory_current:.1f}%) is {memory_current/memory_avg:.1f}x higher than average"
                })
            
            # Check disk space
            disk_percent = current_metrics.get('disk_percent', 0)
            if disk_percent > 95:
                anomalies.append({
                    "type": "disk_space_critical",
                    "metric": "disk_percent",
                    "current_value": disk_percent,
                    "severity": "critical",
                    "description": f"Disk usage ({disk_percent:.1f}%) is critically high"
                })
            elif disk_percent > 90:
                anomalies.append({
                    "type": "disk_space_warning",
                    "metric": "disk_percent",
                    "current_value": disk_percent,
                    "severity": "high",
                    "description": f"Disk usage ({disk_percent:.1f}%) is approaching full capacity"
                })
            
            return anomalies
            
        except Exception as e:
            logger.error(f"Error detecting anomalies: {e}")
            return []
    
    async def generate_health_report(self) -> Dict[str, Any]:
        """Generate comprehensive system health report"""
        try:
            current_metrics = await self.get_current_metrics()
            anomalies = await self.detect_anomalies()
            
            # Calculate health scores
            cpu_health = max(0, 100 - current_metrics.get('cpu_percent', 0))
            memory_health = max(0, 100 - current_metrics.get('memory_percent', 0))
            disk_health = max(0, 100 - current_metrics.get('disk_percent', 0))
            
            overall_health = int((cpu_health + memory_health + disk_health) / 3)
            
            # Determine status
            if overall_health >= 80:
                status = "excellent"
            elif overall_health >= 60:
                status = "good"
            elif overall_health >= 40:
                status = "fair"
            else:
                status = "poor"
            
            return {
                "overall_health_score": overall_health,
                "status": status,
                "individual_scores": {
                    "cpu_health": int(cpu_health),
                    "memory_health": int(memory_health),
                    "disk_health": int(disk_health)
                },
                "current_metrics": current_metrics,
                "anomalies": anomalies,
                "recommendations": self._generate_recommendations(current_metrics, anomalies),
                "generated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating health report: {e}")
            return {
                "overall_health_score": 0,
                "status": "unknown",
                "error": str(e),
                "generated_at": datetime.utcnow().isoformat()
            }
    
    def _generate_recommendations(self, metrics: Dict[str, Any], anomalies: List[Dict[str, Any]]) -> List[str]:
        """Generate system recommendations based on metrics and anomalies"""
        recommendations = []
        
        try:
            cpu_percent = metrics.get('cpu_percent', 0)
            memory_percent = metrics.get('memory_percent', 0)
            disk_percent = metrics.get('disk_percent', 0)
            
            # CPU recommendations
            if cpu_percent > 90:
                recommendations.append("Critical: Investigate high CPU usage processes and consider closing unnecessary applications")
            elif cpu_percent > 75:
                recommendations.append("Consider closing resource-intensive applications to reduce CPU load")
            
            # Memory recommendations
            if memory_percent > 90:
                recommendations.append("Critical: System is low on memory - close unnecessary applications or restart memory-intensive processes")
            elif memory_percent > 80:
                recommendations.append("Memory usage is high - consider restarting applications or adding more RAM")
            
            # Disk recommendations
            if disk_percent > 95:
                recommendations.append("Critical: Disk space is nearly full - immediate cleanup required")
            elif disk_percent > 90:
                recommendations.append("Disk space is running low - run disk cleanup or move files to external storage")
            elif disk_percent > 80:
                recommendations.append("Consider cleaning up temporary files and old downloads")
            
            # Process recommendations
            process_count = metrics.get('process_count', 0)
            if process_count > 200:
                recommendations.append("High number of running processes - review and close unnecessary applications")
            
            # Anomaly-based recommendations
            for anomaly in anomalies:
                if anomaly['type'] == 'cpu_spike':
                    recommendations.append("Investigate recent CPU spike - check for resource-intensive processes")
                elif anomaly['type'] == 'memory_spike':
                    recommendations.append("Memory usage has spiked - monitor for memory leaks in applications")
            
            # General recommendations
            uptime = metrics.get('uptime', 0)
            if uptime > 7 * 24 * 3600:  # More than 7 days
                recommendations.append("System has been running for over a week - consider restarting to clear memory and apply updates")
            
            if not recommendations:
                recommendations.append("System performance is optimal - no immediate actions required")
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            return ["Unable to generate recommendations due to error"]
    
    async def cleanup(self):
        """Cleanup system monitor resources"""
        try:
            if self.monitoring_task:
                self.monitoring_task.cancel()
                try:
                    await self.monitoring_task
                except asyncio.CancelledError:
                    pass
            
            logger.info("System monitor cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during system monitor cleanup: {e}")