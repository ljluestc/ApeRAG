"""
Monitoring System Implementation

A comprehensive monitoring and observability system with features:
- Real-time metrics collection and aggregation
- Alerting and notification system
- Dashboard and visualization
- Log aggregation and analysis
- Performance monitoring
- Health checks and uptime monitoring
- Distributed tracing
- Custom metrics and events

Author: AI Assistant
Date: 2024
"""

import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple, Any, Callable
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict, deque
import statistics
import threading
import psutil
import socket

import redis
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Float, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, func, desc, asc
import aiohttp


Base = declarative_base()


class MetricType(Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class AlertSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(Enum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


class HealthStatus(Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class Metric:
    """Metric data structure"""
    name: str
    value: float
    metric_type: MetricType
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    description: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "value": self.value,
            "type": self.metric_type.value,
            "labels": self.labels,
            "timestamp": self.timestamp.isoformat(),
            "description": self.description
        }


@dataclass
class Alert:
    """Alert data structure"""
    id: str
    name: str
    description: str
    severity: AlertSeverity
    status: AlertStatus
    metric_name: str
    threshold: float
    operator: str  # ">", "<", ">=", "<=", "==", "!="
    current_value: float
    created_at: datetime
    resolved_at: Optional[datetime] = None
    labels: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "severity": self.severity.value,
            "status": self.status.value,
            "metric_name": self.metric_name,
            "threshold": self.threshold,
            "operator": self.operator,
            "current_value": self.current_value,
            "created_at": self.created_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "labels": self.labels
        }


@dataclass
class HealthCheck:
    """Health check data structure"""
    id: str
    name: str
    service: str
    endpoint: str
    status: HealthStatus
    response_time: float
    last_check: datetime
    error_message: str = ""
    retry_count: int = 0
    max_retries: int = 3
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "service": self.service,
            "endpoint": self.endpoint,
            "status": self.status.value,
            "response_time": self.response_time,
            "last_check": self.last_check.isoformat(),
            "error_message": self.error_message,
            "retry_count": self.retry_count
        }


class MetricModel(Base):
    """Database model for metrics"""
    __tablename__ = 'metrics'
    
    id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False, index=True)
    value = Column(Float, nullable=False)
    metric_type = Column(String(20), nullable=False)
    labels = Column(JSON)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    description = Column(Text)


class AlertModel(Base):
    """Database model for alerts"""
    __tablename__ = 'alerts'
    
    id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    severity = Column(String(20), nullable=False)
    status = Column(String(20), default=AlertStatus.ACTIVE.value)
    metric_name = Column(String(100), nullable=False, index=True)
    threshold = Column(Float, nullable=False)
    operator = Column(String(10), nullable=False)
    current_value = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    labels = Column(JSON)


class HealthCheckModel(Base):
    """Database model for health checks"""
    __tablename__ = 'health_checks'
    
    id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    service = Column(String(100), nullable=False, index=True)
    endpoint = Column(String(500), nullable=False)
    status = Column(String(20), default=HealthStatus.UNKNOWN.value)
    response_time = Column(Float, default=0.0)
    last_check = Column(DateTime, default=datetime.utcnow)
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)


class MonitoringService:
    """Main monitoring service class"""
    
    def __init__(self, db_url: str, redis_url: str = "redis://localhost:6379"):
        self.db_url = db_url
        self.redis_url = redis_url
        self.redis_client = redis.from_url(redis_url)
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        
        # In-memory storage
        self.metrics: Dict[str, List[Metric]] = defaultdict(list)
        self.alerts: Dict[str, Alert] = {}
        self.health_checks: Dict[str, HealthCheck] = {}
        self.alert_rules: Dict[str, Dict] = {}
        
        # Configuration
        self.metrics_retention_days = 30
        self.alert_cooldown_minutes = 5
        self.health_check_interval = 60  # seconds
        
        # Start background tasks
        self._start_background_tasks()
    
    def _start_background_tasks(self):
        """Start background monitoring tasks"""
        threading.Thread(target=self._metrics_cleanup_loop, daemon=True).start()
        threading.Thread(target=self._alert_evaluation_loop, daemon=True).start()
        threading.Thread(target=self._health_check_loop, daemon=True).start()
    
    def record_metric(self, metric: Metric) -> Dict:
        """Record a metric"""
        try:
            # Store in memory
            self.metrics[metric.name].append(metric)
            
            # Keep only recent metrics in memory
            if len(self.metrics[metric.name]) > 1000:
                self.metrics[metric.name] = self.metrics[metric.name][-1000:]
            
            # Store in database
            metric_model = MetricModel(
                id=str(uuid.uuid4()),
                name=metric.name,
                value=metric.value,
                metric_type=metric.metric_type.value,
                labels=metric.labels,
                timestamp=metric.timestamp,
                description=metric.description
            )
            
            self.session.add(metric_model)
            self.session.commit()
            
            # Evaluate alerts
            self._evaluate_alerts_for_metric(metric)
            
            return {"message": "Metric recorded successfully"}
        
        except Exception as e:
            self.session.rollback()
            return {"error": f"Failed to record metric: {str(e)}"}
    
    def get_metrics(self, metric_name: str, start_time: datetime = None, 
                   end_time: datetime = None, labels: Dict[str, str] = None) -> Dict:
        """Get metrics for a specific metric name"""
        query = self.session.query(MetricModel).filter(MetricModel.name == metric_name)
        
        if start_time:
            query = query.filter(MetricModel.timestamp >= start_time)
        if end_time:
            query = query.filter(MetricModel.timestamp <= end_time)
        
        metrics = query.order_by(MetricModel.timestamp.desc()).limit(1000).all()
        
        # Filter by labels if provided
        filtered_metrics = []
        for metric in metrics:
            if labels:
                match = True
                for key, value in labels.items():
                    if metric.labels.get(key) != value:
                        match = False
                        break
                if match:
                    filtered_metrics.append(metric)
            else:
                filtered_metrics.append(metric)
        
        return {
            "metric_name": metric_name,
            "metrics": [
                {
                    "value": m.value,
                    "labels": m.labels or {},
                    "timestamp": m.timestamp.isoformat()
                }
                for m in filtered_metrics
            ],
            "count": len(filtered_metrics)
        }
    
    def get_metric_summary(self, metric_name: str, start_time: datetime = None, 
                          end_time: datetime = None) -> Dict:
        """Get metric summary statistics"""
        query = self.session.query(MetricModel).filter(MetricModel.name == metric_name)
        
        if start_time:
            query = query.filter(MetricModel.timestamp >= start_time)
        if end_time:
            query = query.filter(MetricModel.timestamp <= end_time)
        
        metrics = query.all()
        
        if not metrics:
            return {"error": "No metrics found"}
        
        values = [m.value for m in metrics]
        
        return {
            "metric_name": metric_name,
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "std_dev": statistics.stdev(values) if len(values) > 1 else 0,
            "percentile_95": sorted(values)[int(len(values) * 0.95)] if values else 0,
            "percentile_99": sorted(values)[int(len(values) * 0.99)] if values else 0
        }
    
    def create_alert_rule(self, name: str, metric_name: str, threshold: float, 
                         operator: str, severity: AlertSeverity, 
                         description: str = "") -> Dict:
        """Create an alert rule"""
        rule_id = str(uuid.uuid4())
        
        self.alert_rules[rule_id] = {
            "id": rule_id,
            "name": name,
            "metric_name": metric_name,
            "threshold": threshold,
            "operator": operator,
            "severity": severity,
            "description": description,
            "created_at": datetime.utcnow()
        }
        
        return {
            "rule_id": rule_id,
            "message": "Alert rule created successfully"
        }
    
    def _evaluate_alerts_for_metric(self, metric: Metric):
        """Evaluate alerts for a specific metric"""
        for rule_id, rule in self.alert_rules.items():
            if rule["metric_name"] != metric.name:
                continue
            
            # Check if alert condition is met
            condition_met = False
            if rule["operator"] == ">":
                condition_met = metric.value > rule["threshold"]
            elif rule["operator"] == "<":
                condition_met = metric.value < rule["threshold"]
            elif rule["operator"] == ">=":
                condition_met = metric.value >= rule["threshold"]
            elif rule["operator"] == "<=":
                condition_met = metric.value <= rule["threshold"]
            elif rule["operator"] == "==":
                condition_met = metric.value == rule["threshold"]
            elif rule["operator"] == "!=":
                condition_met = metric.value != rule["threshold"]
            
            if condition_met:
                # Check if alert already exists and is active
                existing_alert = None
                for alert in self.alerts.values():
                    if (alert.metric_name == metric.name and 
                        alert.status == AlertStatus.ACTIVE and
                        alert.name == rule["name"]):
                        existing_alert = alert
                        break
                
                if not existing_alert:
                    # Create new alert
                    alert = Alert(
                        id=str(uuid.uuid4()),
                        name=rule["name"],
                        description=rule["description"],
                        severity=rule["severity"],
                        status=AlertStatus.ACTIVE,
                        metric_name=metric.name,
                        threshold=rule["threshold"],
                        operator=rule["operator"],
                        current_value=metric.value,
                        created_at=datetime.utcnow(),
                        labels=metric.labels
                    )
                    
                    self.alerts[alert.id] = alert
                    self._save_alert_to_db(alert)
                    self._send_alert_notification(alert)
            else:
                # Check if we need to resolve existing alert
                for alert in self.alerts.values():
                    if (alert.metric_name == metric.name and 
                        alert.status == AlertStatus.ACTIVE and
                        alert.name == rule["name"]):
                        alert.status = AlertStatus.RESOLVED
                        alert.resolved_at = datetime.utcnow()
                        self._update_alert_in_db(alert)
                        self._send_alert_resolution_notification(alert)
    
    def _save_alert_to_db(self, alert: Alert):
        """Save alert to database"""
        try:
            alert_model = AlertModel(
                id=alert.id,
                name=alert.name,
                description=alert.description,
                severity=alert.severity.value,
                status=alert.status.value,
                metric_name=alert.metric_name,
                threshold=alert.threshold,
                operator=alert.operator,
                current_value=alert.current_value,
                created_at=alert.created_at,
                resolved_at=alert.resolved_at,
                labels=alert.labels
            )
            
            self.session.add(alert_model)
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            print(f"Failed to save alert to database: {e}")
    
    def _update_alert_in_db(self, alert: Alert):
        """Update alert in database"""
        try:
            self.session.query(AlertModel).filter(AlertModel.id == alert.id).update({
                "status": alert.status.value,
                "resolved_at": alert.resolved_at
            })
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            print(f"Failed to update alert in database: {e}")
    
    def _send_alert_notification(self, alert: Alert):
        """Send alert notification"""
        # In a real implementation, this would send notifications via email, Slack, etc.
        print(f"ALERT: {alert.name} - {alert.description}")
        print(f"Severity: {alert.severity.value}")
        print(f"Current value: {alert.current_value} {alert.operator} {alert.threshold}")
    
    def _send_alert_resolution_notification(self, alert: Alert):
        """Send alert resolution notification"""
        print(f"ALERT RESOLVED: {alert.name}")
    
    def get_active_alerts(self) -> Dict:
        """Get all active alerts"""
        active_alerts = [
            alert for alert in self.alerts.values()
            if alert.status == AlertStatus.ACTIVE
        ]
        
        return {
            "alerts": [alert.to_dict() for alert in active_alerts],
            "count": len(active_alerts)
        }
    
    def resolve_alert(self, alert_id: str) -> Dict:
        """Manually resolve an alert"""
        if alert_id not in self.alerts:
            return {"error": "Alert not found"}
        
        alert = self.alerts[alert_id]
        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = datetime.utcnow()
        
        self._update_alert_in_db(alert)
        
        return {"message": "Alert resolved successfully"}
    
    def create_health_check(self, name: str, service: str, endpoint: str, 
                           max_retries: int = 3) -> Dict:
        """Create a health check"""
        health_check_id = str(uuid.uuid4())
        
        health_check = HealthCheck(
            id=health_check_id,
            name=name,
            service=service,
            endpoint=endpoint,
            status=HealthStatus.UNKNOWN,
            response_time=0.0,
            last_check=datetime.utcnow(),
            max_retries=max_retries
        )
        
        self.health_checks[health_check_id] = health_check
        
        # Save to database
        try:
            health_check_model = HealthCheckModel(
                id=health_check_id,
                name=name,
                service=service,
                endpoint=endpoint,
                status=HealthStatus.UNKNOWN.value,
                response_time=0.0,
                last_check=datetime.utcnow(),
                max_retries=max_retries
            )
            
            self.session.add(health_check_model)
            self.session.commit()
            
            return {
                "health_check_id": health_check_id,
                "message": "Health check created successfully"
            }
        
        except Exception as e:
            self.session.rollback()
            return {"error": f"Failed to create health check: {str(e)}"}
    
    def _health_check_loop(self):
        """Health check monitoring loop"""
        while True:
            try:
                time.sleep(self.health_check_interval)
                asyncio.run(self._perform_health_checks())
            except Exception as e:
                print(f"Health check error: {e}")
    
    async def _perform_health_checks(self):
        """Perform all health checks"""
        tasks = []
        for health_check in self.health_checks.values():
            task = asyncio.create_task(self._check_health(health_check))
            tasks.append(task)
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _check_health(self, health_check: HealthCheck):
        """Check health of a single service"""
        try:
            start_time = time.time()
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get(health_check.endpoint) as response:
                    response_time = time.time() - start_time
                    
                    if response.status == 200:
                        health_check.status = HealthStatus.HEALTHY
                        health_check.retry_count = 0
                        health_check.error_message = ""
                    else:
                        health_check.status = HealthStatus.WARNING
                        health_check.error_message = f"HTTP {response.status}"
                    
                    health_check.response_time = response_time
                    health_check.last_check = datetime.utcnow()
        
        except Exception as e:
            health_check.retry_count += 1
            health_check.error_message = str(e)
            
            if health_check.retry_count >= health_check.max_retries:
                health_check.status = HealthStatus.CRITICAL
            else:
                health_check.status = HealthStatus.WARNING
            
            health_check.last_check = datetime.utcnow()
        
        # Update database
        self._update_health_check_in_db(health_check)
    
    def _update_health_check_in_db(self, health_check: HealthCheck):
        """Update health check in database"""
        try:
            self.session.query(HealthCheckModel).filter(
                HealthCheckModel.id == health_check.id
            ).update({
                "status": health_check.status.value,
                "response_time": health_check.response_time,
                "last_check": health_check.last_check,
                "error_message": health_check.error_message,
                "retry_count": health_check.retry_count
            })
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            print(f"Failed to update health check in database: {e}")
    
    def get_health_status(self) -> Dict:
        """Get overall health status"""
        health_checks = list(self.health_checks.values())
        
        if not health_checks:
            return {"status": "unknown", "message": "No health checks configured"}
        
        critical_count = sum(1 for hc in health_checks if hc.status == HealthStatus.CRITICAL)
        warning_count = sum(1 for hc in health_checks if hc.status == HealthStatus.WARNING)
        healthy_count = sum(1 for hc in health_checks if hc.status == HealthStatus.HEALTHY)
        
        if critical_count > 0:
            overall_status = "critical"
        elif warning_count > 0:
            overall_status = "warning"
        elif healthy_count > 0:
            overall_status = "healthy"
        else:
            overall_status = "unknown"
        
        return {
            "status": overall_status,
            "total_checks": len(health_checks),
            "healthy": healthy_count,
            "warning": warning_count,
            "critical": critical_count,
            "health_checks": [hc.to_dict() for hc in health_checks]
        }
    
    def get_system_metrics(self) -> Dict:
        """Get system-level metrics"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            
            # Disk usage
            disk = psutil.disk_usage('/')
            
            # Network I/O
            network = psutil.net_io_counters()
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "cpu": {
                    "usage_percent": cpu_percent,
                    "count": psutil.cpu_count()
                },
                "memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "used": memory.used,
                    "usage_percent": memory.percent
                },
                "disk": {
                    "total": disk.total,
                    "used": disk.used,
                    "free": disk.free,
                    "usage_percent": (disk.used / disk.total) * 100
                },
                "network": {
                    "bytes_sent": network.bytes_sent,
                    "bytes_recv": network.bytes_recv,
                    "packets_sent": network.packets_sent,
                    "packets_recv": network.packets_recv
                }
            }
        
        except Exception as e:
            return {"error": f"Failed to get system metrics: {str(e)}"}
    
    def _metrics_cleanup_loop(self):
        """Cleanup old metrics"""
        while True:
            try:
                time.sleep(3600)  # Run every hour
                
                # Delete old metrics
                cutoff_date = datetime.utcnow() - timedelta(days=self.metrics_retention_days)
                self.session.query(MetricModel).filter(
                    MetricModel.timestamp < cutoff_date
                ).delete()
                self.session.commit()
                
            except Exception as e:
                print(f"Metrics cleanup error: {e}")
    
    def _alert_evaluation_loop(self):
        """Alert evaluation loop"""
        while True:
            try:
                time.sleep(60)  # Run every minute
                
                # Evaluate alerts for all metrics
                for metric_name, metrics in self.metrics.items():
                    if metrics:
                        latest_metric = max(metrics, key=lambda m: m.timestamp)
                        self._evaluate_alerts_for_metric(latest_metric)
                
            except Exception as e:
                print(f"Alert evaluation error: {e}")
    
    def get_dashboard_data(self) -> Dict:
        """Get data for monitoring dashboard"""
        # Get recent metrics
        recent_metrics = {}
        for metric_name in self.metrics.keys():
            recent_data = self.get_metrics(
                metric_name,
                start_time=datetime.utcnow() - timedelta(hours=1)
            )
            recent_metrics[metric_name] = recent_data
        
        # Get active alerts
        active_alerts = self.get_active_alerts()
        
        # Get health status
        health_status = self.get_health_status()
        
        # Get system metrics
        system_metrics = self.get_system_metrics()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": recent_metrics,
            "alerts": active_alerts,
            "health": health_status,
            "system": system_metrics
        }


class MonitoringAPI:
    """REST API for Monitoring service"""
    
    def __init__(self, service: MonitoringService):
        self.service = service
    
    def record_metric(self, request_data: Dict) -> Tuple[Dict, int]:
        """API endpoint to record a metric"""
        try:
            metric_type = MetricType(request_data.get('type', 'gauge'))
        except ValueError:
            return {"error": "Invalid metric type"}, 400
        
        metric = Metric(
            name=request_data.get('name'),
            value=float(request_data.get('value', 0)),
            metric_type=metric_type,
            labels=request_data.get('labels', {}),
            description=request_data.get('description', '')
        )
        
        if not metric.name:
            return {"error": "Metric name is required"}, 400
        
        result = self.service.record_metric(metric)
        
        if "error" in result:
            return result, 400
        
        return result, 200
    
    def get_metrics(self, metric_name: str, start_time: str = None, 
                   end_time: str = None, labels: Dict[str, str] = None) -> Tuple[Dict, int]:
        """API endpoint to get metrics"""
        start_dt = None
        end_dt = None
        
        if start_time:
            start_dt = datetime.fromisoformat(start_time)
        if end_time:
            end_dt = datetime.fromisoformat(end_time)
        
        result = self.service.get_metrics(metric_name, start_dt, end_dt, labels)
        return result, 200
    
    def get_metric_summary(self, metric_name: str, start_time: str = None, 
                          end_time: str = None) -> Tuple[Dict, int]:
        """API endpoint to get metric summary"""
        start_dt = None
        end_dt = None
        
        if start_time:
            start_dt = datetime.fromisoformat(start_time)
        if end_time:
            end_dt = datetime.fromisoformat(end_time)
        
        result = self.service.get_metric_summary(metric_name, start_dt, end_dt)
        return result, 200
    
    def create_alert_rule(self, request_data: Dict) -> Tuple[Dict, int]:
        """API endpoint to create alert rule"""
        try:
            severity = AlertSeverity(request_data.get('severity', 'medium'))
        except ValueError:
            return {"error": "Invalid severity"}, 400
        
        result = self.service.create_alert_rule(
            name=request_data.get('name'),
            metric_name=request_data.get('metric_name'),
            threshold=float(request_data.get('threshold', 0)),
            operator=request_data.get('operator', '>'),
            severity=severity,
            description=request_data.get('description', '')
        )
        
        if "error" in result:
            return result, 400
        
        return result, 201
    
    def get_alerts(self) -> Tuple[Dict, int]:
        """API endpoint to get active alerts"""
        result = self.service.get_active_alerts()
        return result, 200
    
    def resolve_alert(self, alert_id: str) -> Tuple[Dict, int]:
        """API endpoint to resolve alert"""
        result = self.service.resolve_alert(alert_id)
        
        if "error" in result:
            return result, 404
        
        return result, 200
    
    def create_health_check(self, request_data: Dict) -> Tuple[Dict, int]:
        """API endpoint to create health check"""
        result = self.service.create_health_check(
            name=request_data.get('name'),
            service=request_data.get('service'),
            endpoint=request_data.get('endpoint'),
            max_retries=int(request_data.get('max_retries', 3))
        )
        
        if "error" in result:
            return result, 400
        
        return result, 201
    
    def get_health_status(self) -> Tuple[Dict, int]:
        """API endpoint to get health status"""
        result = self.service.get_health_status()
        return result, 200
    
    def get_dashboard_data(self) -> Tuple[Dict, int]:
        """API endpoint to get dashboard data"""
        result = self.service.get_dashboard_data()
        return result, 200


# Example usage and testing
if __name__ == "__main__":
    # Initialize service
    service = MonitoringService(
        db_url="sqlite:///monitoring.db",
        redis_url="redis://localhost:6379"
    )
    
    # Record some metrics
    metric1 = Metric(
        name="cpu_usage",
        value=75.5,
        metric_type=MetricType.GAUGE,
        labels={"host": "server1", "service": "web"},
        description="CPU usage percentage"
    )
    
    result1 = service.record_metric(metric1)
    print("Recorded metric:", result1)
    
    metric2 = Metric(
        name="response_time",
        value=150.0,
        metric_type=MetricType.HISTOGRAM,
        labels={"endpoint": "/api/users", "method": "GET"},
        description="API response time in milliseconds"
    )
    
    result2 = service.record_metric(metric2)
    print("Recorded metric:", result2)
    
    # Create alert rule
    result3 = service.create_alert_rule(
        name="High CPU Usage",
        metric_name="cpu_usage",
        threshold=80.0,
        operator=">",
        severity=AlertSeverity.HIGH,
        description="CPU usage is above 80%"
    )
    print("Created alert rule:", result3)
    
    # Create health check
    result4 = service.create_health_check(
        name="Web Service Health",
        service="web",
        endpoint="http://localhost:8000/health",
        max_retries=3
    )
    print("Created health check:", result4)
    
    # Get metrics
    metrics = service.get_metrics("cpu_usage")
    print("CPU usage metrics:", metrics)
    
    # Get metric summary
    summary = service.get_metric_summary("response_time")
    print("Response time summary:", summary)
    
    # Get active alerts
    alerts = service.get_active_alerts()
    print("Active alerts:", alerts)
    
    # Get health status
    health = service.get_health_status()
    print("Health status:", health)
    
    # Get system metrics
    system = service.get_system_metrics()
    print("System metrics:", system)
    
    # Get dashboard data
    dashboard = service.get_dashboard_data()
    print("Dashboard data:", dashboard)
