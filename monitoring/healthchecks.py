"""
Health check and monitoring system for CloudFix Changelog automation.
Provides comprehensive monitoring, alerting, and self-healing capabilities.
"""

import asyncio
import aiohttp
import logging
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import os
import psutil

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"

@dataclass
class HealthCheck:
    name: str
    status: HealthStatus
    response_time: float
    message: str
    timestamp: datetime
    metadata: Dict[str, Any] = None

@dataclass
class SystemMetrics:
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    network_io: Dict[str, int]
    process_count: int
    uptime: float

class HealthMonitor:
    """Comprehensive health monitoring system."""
    
    def __init__(self):
        self.checks = {}
        self.metrics_history = []
        self.alert_thresholds = {
            'api_response_time': 5.0,  # seconds
            'memory_usage': 85.0,      # percent
            'cpu_usage': 80.0,         # percent
            'disk_usage': 90.0,        # percent
            'error_rate': 5.0          # percent
        }
        
    async def run_all_checks(self) -> Dict[str, HealthCheck]:
        """Run all health checks concurrently."""
        checks = await asyncio.gather(
            self.check_api_health(),
            self.check_github_api(),
            self.check_openai_api(),
            self.check_database_health(),
            self.check_redis_health(),
            self.check_n8n_health(),
            self.check_disk_space(),
            self.check_memory_usage(),
            return_exceptions=True
        )
        
        # Process results
        results = {}
        check_names = [
            'api_health', 'github_api', 'openai_api',
            'database', 'redis', 'n8n',
            'disk_space', 'memory_usage'
        ]
        
        for name, check in zip(check_names, checks):
            if isinstance(check, Exception):
                results[name] = HealthCheck(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    response_time=0.0,
                    message=f"Check failed: {str(check)}",
                    timestamp=datetime.utcnow()
                )
            else:
                results[name] = check
        
        self.checks = results
        return results
    
    async def check_api_health(self) -> HealthCheck:
        """Check changelog API health."""
        start_time = time.time()
        
        try:
            api_url = os.getenv('CHANGELOG_API_URL', 'http://localhost:8000')
            
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{api_url}/health", timeout=10) as response:
                    response_time = time.time() - start_time
                    
                    if response.status == 200:
                        data = await response.json()
                        
                        # Check if dependencies are healthy
                        deps = data.get('dependencies', {})
                        unhealthy_deps = [k for k, v in deps.items() if v != 'configured']
                        
                        if unhealthy_deps:
                            return HealthCheck(
                                name="api_health",
                                status=HealthStatus.DEGRADED,
                                response_time=response_time,
                                message=f"API healthy but dependencies missing: {', '.join(unhealthy_deps)}",
                                timestamp=datetime.utcnow(),
                                metadata=data
                            )
                        
                        return HealthCheck(
                            name="api_health",
                            status=HealthStatus.HEALTHY,
                            response_time=response_time,
                            message="API is healthy",
                            timestamp=datetime.utcnow(),
                            metadata=data
                        )
                    else:
                        return HealthCheck(
                            name="api_health",
                            status=HealthStatus.UNHEALTHY,
                            response_time=response_time,
                            message=f"API returned status {response.status}",
                            timestamp=datetime.utcnow()
                        )
        except asyncio.TimeoutError:
            return HealthCheck(
                name="api_health",
                status=HealthStatus.UNHEALTHY,
                response_time=time.time() - start_time,
                message="API health check timed out",
                timestamp=datetime.utcnow()
            )
        except Exception as e:
            return HealthCheck(
                name="api_health",
                status=HealthStatus.UNHEALTHY,
                response_time=time.time() - start_time,
                message=f"API health check failed: {str(e)}",
                timestamp=datetime.utcnow()
            )
    
    async def check_github_api(self) -> HealthCheck:
        """Check GitHub API connectivity and rate limits."""
        start_time = time.time()
        
        try:
            github_token = os.getenv('GITHUB_API_KEY')
            if not github_token:
                return HealthCheck(
                    name="github_api",
                    status=HealthStatus.UNHEALTHY,
                    response_time=0.0,
                    message="GitHub API token not configured",
                    timestamp=datetime.utcnow()
                )
            
            headers = {
                'Authorization': f'Bearer {github_token}',
                'Accept': 'application/vnd.github+json'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    'https://api.github.com/rate_limit',
                    headers=headers,
                    timeout=10
                ) as response:
                    response_time = time.time() - start_time
                    
                    if response.status == 200:
                        data = await response.json()
                        core_limit = data.get('resources', {}).get('core', {})
                        remaining = core_limit.get('remaining', 0)
                        limit = core_limit.get('limit', 0)
                        
                        if remaining < 100:
                            status = HealthStatus.DEGRADED
                            message = f"GitHub API rate limit low: {remaining}/{limit}"
                        else:
                            status = HealthStatus.HEALTHY
                            message = f"GitHub API healthy: {remaining}/{limit} requests remaining"
                        
                        return HealthCheck(
                            name="github_api",
                            status=status,
                            response_time=response_time,
                            message=message,
                            timestamp=datetime.utcnow(),
                            metadata=data
                        )
                    else:
                        return HealthCheck(
                            name="github_api",
                            status=HealthStatus.UNHEALTHY,
                            response_time=response_time,
                            message=f"GitHub API returned status {response.status}",
                            timestamp=datetime.utcnow()
                        )
        except Exception as e:
            return HealthCheck(
                name="github_api",
                status=HealthStatus.UNHEALTHY,
                response_time=time.time() - start_time,
                message=f"GitHub API check failed: {str(e)}",
                timestamp=datetime.utcnow()
            )
    
    async def check_openai_api(self) -> HealthCheck:
        """Check OpenAI API connectivity."""
        start_time = time.time()
        
        try:
            openai_key = os.getenv('OPENAI_API_KEY')
            if not openai_key:
                return HealthCheck(
                    name="openai_api",
                    status=HealthStatus.UNHEALTHY,
                    response_time=0.0,
                    message="OpenAI API key not configured",
                    timestamp=datetime.utcnow()
                )
            
            headers = {
                'Authorization': f'Bearer {openai_key}',
                'Content-Type': 'application/json'
            }
            
            # Simple test request to check API connectivity
            test_payload = {
                'model': 'gpt-3.5-turbo',
                'messages': [{'role': 'user', 'content': 'test'}],
                'max_tokens': 1
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    'https://api.openai.com/v1/chat/completions',
                    headers=headers,
                    json=test_payload,
                    timeout=15
                ) as response:
                    response_time = time.time() - start_time
                    
                    if response.status == 200:
                        return HealthCheck(
                            name="openai_api",
                            status=HealthStatus.HEALTHY,
                            response_time=response_time,
                            message="OpenAI API is healthy",
                            timestamp=datetime.utcnow()
                        )
                    elif response.status == 401:
                        return HealthCheck(
                            name="openai_api",
                            status=HealthStatus.UNHEALTHY,
                            response_time=response_time,
                            message="OpenAI API key is invalid",
                            timestamp=datetime.utcnow()
                        )
                    elif response.status == 429:
                        return HealthCheck(
                            name="openai_api",
                            status=HealthStatus.DEGRADED,
                            response_time=response_time,
                            message="OpenAI API rate limit exceeded",
                            timestamp=datetime.utcnow()
                        )
                    else:
                        return HealthCheck(
                            name="openai_api",
                            status=HealthStatus.UNHEALTHY,
                            response_time=response_time,
                            message=f"OpenAI API returned status {response.status}",
                            timestamp=datetime.utcnow()
                        )
        except Exception as e:
            return HealthCheck(
                name="openai_api",
                status=HealthStatus.UNHEALTHY,
                response_time=time.time() - start_time,
                message=f"OpenAI API check failed: {str(e)}",
                timestamp=datetime.utcnow()
            )
    
    async def check_database_health(self) -> HealthCheck:
        """Check PostgreSQL database health."""
        start_time = time.time()
        
        try:
            # This would typically use asyncpg or similar
            # For now, we'll do a simple connection test
            import subprocess
            
            result = subprocess.run([
                'pg_isready',
                '-h', os.getenv('POSTGRES_HOST', 'localhost'),
                '-p', str(os.getenv('POSTGRES_PORT', 5432)),
                '-U', os.getenv('POSTGRES_USER', 'n8n')
            ], capture_output=True, timeout=10)
            
            response_time = time.time() - start_time
            
            if result.returncode == 0:
                return HealthCheck(
                    name="database",
                    status=HealthStatus.HEALTHY,
                    response_time=response_time,
                    message="PostgreSQL is healthy",
                    timestamp=datetime.utcnow()
                )
            else:
                return HealthCheck(
                    name="database",
                    status=HealthStatus.UNHEALTHY,
                    response_time=response_time,
                    message=f"PostgreSQL check failed: {result.stderr.decode()}",
                    timestamp=datetime.utcnow()
                )
        except subprocess.TimeoutExpired:
            return HealthCheck(
                name="database",
                status=HealthStatus.UNHEALTHY,
                response_time=time.time() - start_time,
                message="Database health check timed out",
                timestamp=datetime.utcnow()
            )
        except Exception as e:
            return HealthCheck(
                name="database",
                status=HealthStatus.UNKNOWN,
                response_time=time.time() - start_time,
                message=f"Database check failed: {str(e)}",
                timestamp=datetime.utcnow()
            )
    
    async def check_redis_health(self) -> HealthCheck:
        """Check Redis health."""
        start_time = time.time()
        
        try:
            import redis.asyncio as redis
            
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
            r = redis.from_url(redis_url)
            
            # Simple ping test
            response = await r.ping()
            response_time = time.time() - start_time
            
            if response:
                # Get some basic info
                info = await r.info()
                memory_usage = info.get('used_memory_human', 'unknown')
                
                await r.close()
                
                return HealthCheck(
                    name="redis",
                    status=HealthStatus.HEALTHY,
                    response_time=response_time,
                    message=f"Redis is healthy (Memory: {memory_usage})",
                    timestamp=datetime.utcnow(),
                    metadata={'memory_usage': memory_usage}
                )
            else:
                await r.close()
                return HealthCheck(
                    name="redis",
                    status=HealthStatus.UNHEALTHY,
                    response_time=response_time,
                    message="Redis ping failed",
                    timestamp=datetime.utcnow()
                )
        except Exception as e:
            return HealthCheck(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                response_time=time.time() - start_time,
                message=f"Redis check failed: {str(e)}",
                timestamp=datetime.utcnow()
            )
    
    async def check_n8n_health(self) -> HealthCheck:
        """Check n8n workflow platform health."""
        start_time = time.time()
        
        try:
            n8n_url = os.getenv('N8N_WEBHOOK_URL', 'http://localhost:5678')
            
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{n8n_url}/healthz", timeout=10) as response:
                    response_time = time.time() - start_time
                    
                    if response.status == 200:
                        return HealthCheck(
                            name="n8n",
                            status=HealthStatus.HEALTHY,
                            response_time=response_time,
                            message="n8n is healthy",
                            timestamp=datetime.utcnow()
                        )
                    else:
                        return HealthCheck(
                            name="n8n",
                            status=HealthStatus.UNHEALTHY,
                            response_time=response_time,
                            message=f"n8n returned status {response.status}",
                            timestamp=datetime.utcnow()
                        )
        except Exception as e:
            return HealthCheck(
                name="n8n",
                status=HealthStatus.UNHEALTHY,
                response_time=time.time() - start_time,
                message=f"n8n check failed: {str(e)}",
                timestamp=datetime.utcnow()
            )
    
    async def check_disk_space(self) -> HealthCheck:
        """Check disk space usage."""
        start_time = time.time()
        
        try:
            disk_usage = psutil.disk_usage('/')
            usage_percent = (disk_usage.used / disk_usage.total) * 100
            
            response_time = time.time() - start_time
            
            if usage_percent > self.alert_thresholds['disk_usage']:
                status = HealthStatus.UNHEALTHY
                message = f"Disk usage critical: {usage_percent:.1f}%"
            elif usage_percent > self.alert_thresholds['disk_usage'] - 10:
                status = HealthStatus.DEGRADED
                message = f"Disk usage high: {usage_percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"Disk usage normal: {usage_percent:.1f}%"
            
            return HealthCheck(
                name="disk_space",
                status=status,
                response_time=response_time,
                message=message,
                timestamp=datetime.utcnow(),
                metadata={
                    'usage_percent': usage_percent,
                    'free_gb': disk_usage.free / (1024**3),
                    'total_gb': disk_usage.total / (1024**3)
                }
            )
        except Exception as e:
            return HealthCheck(
                name="disk_space",
                status=HealthStatus.UNKNOWN,
                response_time=time.time() - start_time,
                message=f"Disk space check failed: {str(e)}",
                timestamp=datetime.utcnow()
            )
    
    async def check_memory_usage(self) -> HealthCheck:
        """Check memory usage."""
        start_time = time.time()
        
        try:
            memory = psutil.virtual_memory()
            usage_percent = memory.percent
            
            response_time = time.time() - start_time
            
            if usage_percent > self.alert_thresholds['memory_usage']:
                status = HealthStatus.UNHEALTHY
                message = f"Memory usage critical: {usage_percent:.1f}%"
            elif usage_percent > self.alert_thresholds['memory_usage'] - 10:
                status = HealthStatus.DEGRADED
                message = f"Memory usage high: {usage_percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"Memory usage normal: {usage_percent:.1f}%"
            
            return HealthCheck(
                name="memory_usage",
                status=status,
                response_time=response_time,
                message=message,
                timestamp=datetime.utcnow(),
                metadata={
                    'usage_percent': usage_percent,
                    'available_gb': memory.available / (1024**3),
                    'total_gb': memory.total / (1024**3)
                }
            )
        except Exception as e:
            return HealthCheck(
                name="memory_usage",
                status=HealthStatus.UNKNOWN,
                response_time=time.time() - start_time,
                message=f"Memory check failed: {str(e)}",
                timestamp=datetime.utcnow()
            )
    
    def get_system_metrics(self) -> SystemMetrics:
        """Get comprehensive system metrics."""
        try:
            return SystemMetrics(
                cpu_percent=psutil.cpu_percent(interval=1),
                memory_percent=psutil.virtual_memory().percent,
                disk_percent=psutil.disk_usage('/').used / psutil.disk_usage('/').total * 100,
                network_io=dict(psutil.net_io_counters()._asdict()),
                process_count=len(psutil.pids()),
                uptime=time.time() - psutil.boot_time()
            )
        except Exception as e:
            logger.error(f"Failed to get system metrics: {e}")
            return None
    
    def generate_health_report(self) -> Dict[str, Any]:
        """Generate comprehensive health report."""
        if not self.checks:
            return {"error": "No health checks have been run"}
        
        # Calculate overall health
        healthy_count = sum(1 for check in self.checks.values() if check.status == HealthStatus.HEALTHY)
        total_count = len(self.checks)
        overall_health = healthy_count / total_count
        
        if overall_health == 1.0:
            overall_status = HealthStatus.HEALTHY
        elif overall_health >= 0.8:
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.UNHEALTHY
        
        # Get system metrics
        metrics = self.get_system_metrics()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_status": overall_status.value,
            "overall_health_score": overall_health,
            "individual_checks": {
                name: {
                    "status": check.status.value,
                    "response_time": check.response_time,
                    "message": check.message,
                    "timestamp": check.timestamp.isoformat(),
                    "metadata": check.metadata or {}
                }
                for name, check in self.checks.items()
            },
            "system_metrics": asdict(metrics) if metrics else None,
            "alerts": self.get_active_alerts(),
            "recommendations": self.get_recommendations()
        }
    
    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get list of active alerts based on current health status."""
        alerts = []
        
        for name, check in self.checks.items():
            if check.status in [HealthStatus.UNHEALTHY, HealthStatus.DEGRADED]:
                severity = "critical" if check.status == HealthStatus.UNHEALTHY else "warning"
                alerts.append({
                    "component": name,
                    "severity": severity,
                    "message": check.message,
                    "timestamp": check.timestamp.isoformat()
                })
        
        return alerts
    
    def get_recommendations(self) -> List[str]:
        """Get recommendations based on current health status."""
        recommendations = []
        
        for name, check in self.checks.items():
            if check.status == HealthStatus.UNHEALTHY:
                if name == "github_api":
                    recommendations.append("Check GitHub API token permissions and rate limits")
                elif name == "openai_api":
                    recommendations.append("Verify OpenAI API key and check account credits")
                elif name == "database":
                    recommendations.append("Check PostgreSQL connection and ensure database is running")
                elif name == "redis":
                    recommendations.append("Check Redis connection and memory usage")
                elif name == "disk_space":
                    recommendations.append("Free up disk space or increase storage capacity")
                elif name == "memory_usage":
                    recommendations.append("Reduce memory usage or increase available RAM")
        
        return recommendations

# Alerting system
class AlertManager:
    """Manages alerting for health check failures."""
    
    def __init__(self):
        self.alert_history = []
        self.cooldown_periods = {
            'slack': 300,  # 5 minutes
            'datadog': 60,  # 1 minute
            'email': 900   # 15 minutes
        }
        self.last_alerts = {}
    
    async def send_alert(self, health_report: Dict[str, Any]):
        """Send alerts based on health report."""
        alerts = health_report.get('alerts', [])
        
        if not alerts:
            return
        
        # Send to different channels
        await asyncio.gather(
            self.send_slack_alert(health_report),
            self.send_datadog_alert(health_report),
            return_exceptions=True
        )
    
    async def send_slack_alert(self, health_report: Dict[str, Any]):
        """Send alert to Slack."""
        try:
            webhook_url = os.getenv('SLACK_WEBHOOK_URL')
            if not webhook_url:
                return
            
            # Check cooldown
            if self._is_in_cooldown('slack'):
                return
            
            overall_status = health_report['overall_status']
            alerts = health_report['alerts']
            
            color = {
                'healthy': 'good',
                'degraded': 'warning',
                'unhealthy': 'danger'
            }.get(overall_status, 'warning')
            
            message = {
                "text": f"🚨 CloudFix Changelog System Health Alert",
                "attachments": [{
                    "color": color,
                    "title": f"System Status: {overall_status.title()}",
                    "fields": [
                        {
                            "title": alert['component'],
                            "value": f"{alert['severity'].upper()}: {alert['message']}",
                            "short": False
                        }
                        for alert in alerts[:5]  # Limit to 5 alerts
                    ],
                    "footer": f"Health Score: {health_report['overall_health_score']:.2%}",
                    "ts": int(datetime.utcnow().timestamp())
                }]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=message) as response:
                    if response.status == 200:
                        self.last_alerts['slack'] = time.time()
                        logger.info("Slack alert sent successfully")
                    else:
                        logger.error(f"Failed to send Slack alert: {response.status}")
        
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
    
    async def send_datadog_alert(self, health_report: Dict[str, Any]):
        """Send metrics to Datadog."""
        try:
            api_key = os.getenv('DATADOG_API_KEY')
            api_url = os.getenv('DATADOG_API_URL', 'https://api.datadoghq.com')
            
            if not api_key:
                return
            
            # Check cooldown
            if self._is_in_cooldown('datadog'):
                return
            
            headers = {
                'DD-API-KEY': api_key,
                'Content-Type': 'application/json'
            }
            
            # Create event for unhealthy status
            if health_report['overall_status'] == 'unhealthy':
                event = {
                    "title": "CloudFix Changelog System Unhealthy",
                    "text": f"System health degraded with {len(health_report['alerts'])} alerts",
                    "tags": ["changelog", "health-check", "alert"],
                    "alert_type": "error"
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{api_url}/api/v1/events",
                        headers=headers,
                        json=event
                    ) as response:
                        if response.status in [200, 202]:
                            self.last_alerts['datadog'] = time.time()
                            logger.info("Datadog alert sent successfully")
                        else:
                            logger.error(f"Failed to send Datadog alert: {response.status}")
        
        except Exception as e:
            logger.error(f"Failed to send Datadog alert: {e}")
    
    def _is_in_cooldown(self, channel: str) -> bool:
        """Check if alert channel is in cooldown period."""
        last_alert = self.last_alerts.get(channel, 0)
        cooldown = self.cooldown_periods.get(channel, 300)
        return time.time() - last_alert < cooldown

# Main monitoring function
async def run_health_monitoring():
    """Run comprehensive health monitoring cycle."""
    monitor = HealthMonitor()
    alert_manager = AlertManager()
    
    try:
        # Run all health checks
        logger.info("Starting health monitoring cycle")
        await monitor.run_all_checks()
        
        # Generate report
        report = monitor.generate_health_report()
        logger.info(f"Health monitoring complete. Overall status: {report['overall_status']}")
        
        # Send alerts if needed
        if report['overall_status'] != 'healthy':
            await alert_manager.send_alert(report)
        
        return report
    
    except Exception as e:
        logger.error(f"Health monitoring failed: {e}")
        return {"error": str(e), "timestamp": datetime.utcnow().isoformat()}

if __name__ == "__main__":
    # Run health checks
    report = asyncio.run(run_health_monitoring())
    print(json.dumps(report, indent=2))