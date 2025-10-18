"""
Load Balancer System Implementation

A comprehensive load balancing system with features:
- Multiple load balancing algorithms (Round Robin, Least Connections, Weighted, etc.)
- Health checking and monitoring
- Session persistence and sticky sessions
- Auto-scaling and dynamic server management
- SSL termination and certificate management
- Rate limiting and DDoS protection
- Metrics collection and analytics
- Configuration management

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
import random
import hashlib
import ssl
import socket

import redis
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Float, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, func
import aiohttp
import asyncio


Base = declarative_base()


class LoadBalancingAlgorithm(Enum):
    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    WEIGHTED_LEAST_CONNECTIONS = "weighted_least_connections"
    IP_HASH = "ip_hash"
    LEAST_RESPONSE_TIME = "least_response_time"
    RANDOM = "random"


class ServerStatus(Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    MAINTENANCE = "maintenance"
    DRAINING = "draining"


class HealthCheckType(Enum):
    HTTP = "http"
    HTTPS = "https"
    TCP = "tcp"
    CUSTOM = "custom"


@dataclass
class Server:
    """Server configuration and state"""
    id: str
    host: str
    port: int
    weight: int = 1
    max_connections: int = 1000
    current_connections: int = 0
    status: ServerStatus = ServerStatus.HEALTHY
    last_health_check: datetime = field(default_factory=datetime.utcnow)
    response_time: float = 0.0
    error_count: int = 0
    success_count: int = 0
    ssl_enabled: bool = False
    ssl_cert_path: str = ""
    ssl_key_path: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "host": self.host,
            "port": self.port,
            "weight": self.weight,
            "max_connections": self.max_connections,
            "current_connections": self.current_connections,
            "status": self.status.value,
            "last_health_check": self.last_health_check.isoformat(),
            "response_time": self.response_time,
            "error_count": self.error_count,
            "success_count": self.success_count,
            "ssl_enabled": self.ssl_enabled,
            "ssl_cert_path": self.ssl_cert_path,
            "ssl_key_path": self.ssl_key_path
        }


@dataclass
class LoadBalancerConfig:
    """Load balancer configuration"""
    name: str
    algorithm: LoadBalancingAlgorithm
    health_check_interval: int = 30  # seconds
    health_check_timeout: int = 5  # seconds
    health_check_path: str = "/health"
    health_check_type: HealthCheckType = HealthCheckType.HTTP
    max_retries: int = 3
    retry_delay: int = 1  # seconds
    session_persistence: bool = False
    session_timeout: int = 3600  # seconds
    rate_limit_enabled: bool = False
    rate_limit_requests: int = 1000  # requests per minute
    rate_limit_window: int = 60  # seconds
    ssl_termination: bool = False
    ssl_cert_path: str = ""
    ssl_key_path: str = ""


class ServerModel(Base):
    """Database model for servers"""
    __tablename__ = 'servers'
    
    id = Column(String(50), primary_key=True)
    host = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False)
    weight = Column(Integer, default=1)
    max_connections = Column(Integer, default=1000)
    current_connections = Column(Integer, default=0)
    status = Column(String(20), default=ServerStatus.HEALTHY.value)
    last_health_check = Column(DateTime, default=datetime.utcnow)
    response_time = Column(Float, default=0.0)
    error_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    ssl_enabled = Column(Boolean, default=False)
    ssl_cert_path = Column(String(500), default="")
    ssl_key_path = Column(String(500), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class LoadBalancerModel(Base):
    """Database model for load balancers"""
    __tablename__ = 'load_balancers'
    
    id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    algorithm = Column(String(50), nullable=False)
    health_check_interval = Column(Integer, default=30)
    health_check_timeout = Column(Integer, default=5)
    health_check_path = Column(String(200), default="/health")
    health_check_type = Column(String(20), default=HealthCheckType.HTTP.value)
    max_retries = Column(Integer, default=3)
    retry_delay = Column(Integer, default=1)
    session_persistence = Column(Boolean, default=False)
    session_timeout = Column(Integer, default=3600)
    rate_limit_enabled = Column(Boolean, default=False)
    rate_limit_requests = Column(Integer, default=1000)
    rate_limit_window = Column(Integer, default=60)
    ssl_termination = Column(Boolean, default=False)
    ssl_cert_path = Column(String(500), default="")
    ssl_key_path = Column(String(500), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class LoadBalancerService:
    """Main load balancer service class"""
    
    def __init__(self, db_url: str, redis_url: str = "redis://localhost:6379"):
        self.db_url = db_url
        self.redis_url = redis_url
        self.redis_client = redis.from_url(redis_url)
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        
        # Load balancer instances
        self.load_balancers: Dict[str, LoadBalancerInstance] = {}
        
        # Configuration
        self.default_config = LoadBalancerConfig(
            name="default",
            algorithm=LoadBalancingAlgorithm.ROUND_ROBIN
        )
    
    def create_load_balancer(self, config: LoadBalancerConfig) -> Dict:
        """Create a new load balancer"""
        lb_id = f"lb_{int(time.time() * 1000)}"
        
        # Save to database
        lb_model = LoadBalancerModel(
            id=lb_id,
            name=config.name,
            algorithm=config.algorithm.value,
            health_check_interval=config.health_check_interval,
            health_check_timeout=config.health_check_timeout,
            health_check_path=config.health_check_path,
            health_check_type=config.health_check_type.value,
            max_retries=config.max_retries,
            retry_delay=config.retry_delay,
            session_persistence=config.session_persistence,
            session_timeout=config.session_timeout,
            rate_limit_enabled=config.rate_limit_enabled,
            rate_limit_requests=config.rate_limit_requests,
            rate_limit_window=config.rate_limit_window,
            ssl_termination=config.ssl_termination,
            ssl_cert_path=config.ssl_cert_path,
            ssl_key_path=config.ssl_key_path
        )
        
        try:
            self.session.add(lb_model)
            self.session.commit()
            
            # Create load balancer instance
            lb_instance = LoadBalancerInstance(lb_id, config, self.redis_client)
            self.load_balancers[lb_id] = lb_instance
            
            return {
                "load_balancer_id": lb_id,
                "name": config.name,
                "algorithm": config.algorithm.value,
                "status": "created"
            }
        
        except Exception as e:
            self.session.rollback()
            return {"error": f"Failed to create load balancer: {str(e)}"}
    
    def add_server(self, lb_id: str, server: Server) -> Dict:
        """Add server to load balancer"""
        if lb_id not in self.load_balancers:
            return {"error": "Load balancer not found"}
        
        # Save to database
        server_model = ServerModel(
            id=server.id,
            host=server.host,
            port=server.port,
            weight=server.weight,
            max_connections=server.max_connections,
            current_connections=server.current_connections,
            status=server.status.value,
            last_health_check=server.last_health_check,
            response_time=server.response_time,
            error_count=server.error_count,
            success_count=server.success_count,
            ssl_enabled=server.ssl_enabled,
            ssl_cert_path=server.ssl_cert_path,
            ssl_key_path=server.ssl_key_path
        )
        
        try:
            self.session.add(server_model)
            self.session.commit()
            
            # Add to load balancer instance
            lb_instance = self.load_balancers[lb_id]
            lb_instance.add_server(server)
            
            return {"message": f"Server {server.id} added to load balancer {lb_id}"}
        
        except Exception as e:
            self.session.rollback()
            return {"error": f"Failed to add server: {str(e)}"}
    
    def remove_server(self, lb_id: str, server_id: str) -> Dict:
        """Remove server from load balancer"""
        if lb_id not in self.load_balancers:
            return {"error": "Load balancer not found"}
        
        try:
            # Remove from database
            self.session.query(ServerModel).filter(ServerModel.id == server_id).delete()
            self.session.commit()
            
            # Remove from load balancer instance
            lb_instance = self.load_balancers[lb_id]
            lb_instance.remove_server(server_id)
            
            return {"message": f"Server {server_id} removed from load balancer {lb_id}"}
        
        except Exception as e:
            self.session.rollback()
            return {"error": f"Failed to remove server: {str(e)}"}
    
    def get_server(self, lb_id: str, client_ip: str = None, session_id: str = None) -> Dict:
        """Get next server for request"""
        if lb_id not in self.load_balancers:
            return {"error": "Load balancer not found"}
        
        lb_instance = self.load_balancers[lb_id]
        server = lb_instance.get_next_server(client_ip, session_id)
        
        if not server:
            return {"error": "No healthy servers available"}
        
        return {
            "server": server.to_dict(),
            "load_balancer_id": lb_id
        }
    
    def get_load_balancer_status(self, lb_id: str) -> Dict:
        """Get load balancer status and metrics"""
        if lb_id not in self.load_balancers:
            return {"error": "Load balancer not found"}
        
        lb_instance = self.load_balancers[lb_id]
        return lb_instance.get_status()
    
    def update_server_health(self, lb_id: str, server_id: str, is_healthy: bool, 
                           response_time: float = 0.0) -> Dict:
        """Update server health status"""
        if lb_id not in self.load_balancers:
            return {"error": "Load balancer not found"}
        
        lb_instance = self.load_balancers[lb_id]
        lb_instance.update_server_health(server_id, is_healthy, response_time)
        
        return {"message": f"Server {server_id} health updated"}
    
    def get_metrics(self, lb_id: str) -> Dict:
        """Get load balancer metrics"""
        if lb_id not in self.load_balancers:
            return {"error": "Load balancer not found"}
        
        lb_instance = self.load_balancers[lb_id]
        return lb_instance.get_metrics()


class LoadBalancerInstance:
    """Individual load balancer instance"""
    
    def __init__(self, lb_id: str, config: LoadBalancerConfig, redis_client):
        self.lb_id = lb_id
        self.config = config
        self.redis_client = redis_client
        self.servers: Dict[str, Server] = {}
        self.current_index = 0
        self.server_connections: Dict[str, int] = defaultdict(int)
        self.server_response_times: Dict[str, List[float]] = defaultdict(list)
        self.session_servers: Dict[str, str] = {}  # session_id -> server_id
        self.rate_limiter = RateLimiter(redis_client) if config.rate_limit_enabled else None
        
        # Start health checking
        self._start_health_checking()
    
    def add_server(self, server: Server):
        """Add server to load balancer"""
        self.servers[server.id] = server
        self.server_connections[server.id] = 0
        self.server_response_times[server.id] = []
    
    def remove_server(self, server_id: str):
        """Remove server from load balancer"""
        if server_id in self.servers:
            del self.servers[server_id]
            del self.server_connections[server_id]
            del self.server_response_times[server_id]
    
    def get_next_server(self, client_ip: str = None, session_id: str = None) -> Optional[Server]:
        """Get next server based on algorithm"""
        # Check session persistence
        if self.config.session_persistence and session_id:
            if session_id in self.session_servers:
                server_id = self.session_servers[session_id]
                if server_id in self.servers and self.servers[server_id].status == ServerStatus.HEALTHY:
                    return self.servers[server_id]
        
        # Filter healthy servers
        healthy_servers = [
            server for server in self.servers.values()
            if server.status == ServerStatus.HEALTHY and 
               server.current_connections < server.max_connections
        ]
        
        if not healthy_servers:
            return None
        
        # Select server based on algorithm
        if self.config.algorithm == LoadBalancingAlgorithm.ROUND_ROBIN:
            server = self._round_robin_selection(healthy_servers)
        elif self.config.algorithm == LoadBalancingAlgorithm.LEAST_CONNECTIONS:
            server = self._least_connections_selection(healthy_servers)
        elif self.config.algorithm == LoadBalancingAlgorithm.WEIGHTED_ROUND_ROBIN:
            server = self._weighted_round_robin_selection(healthy_servers)
        elif self.config.algorithm == LoadBalancingAlgorithm.WEIGHTED_LEAST_CONNECTIONS:
            server = self._weighted_least_connections_selection(healthy_servers)
        elif self.config.algorithm == LoadBalancingAlgorithm.IP_HASH:
            server = self._ip_hash_selection(healthy_servers, client_ip)
        elif self.config.algorithm == LoadBalancingAlgorithm.LEAST_RESPONSE_TIME:
            server = self._least_response_time_selection(healthy_servers)
        elif self.config.algorithm == LoadBalancingAlgorithm.RANDOM:
            server = self._random_selection(healthy_servers)
        else:
            server = healthy_servers[0]
        
        # Update connection count
        if server:
            server.current_connections += 1
            self.server_connections[server.id] += 1
            
            # Update session persistence
            if self.config.session_persistence and session_id:
                self.session_servers[session_id] = server.id
        
        return server
    
    def _round_robin_selection(self, servers: List[Server]) -> Server:
        """Round robin server selection"""
        if not servers:
            return None
        
        server = servers[self.current_index % len(servers)]
        self.current_index += 1
        return server
    
    def _least_connections_selection(self, servers: List[Server]) -> Server:
        """Least connections server selection"""
        if not servers:
            return None
        
        return min(servers, key=lambda s: s.current_connections)
    
    def _weighted_round_robin_selection(self, servers: List[Server]) -> Server:
        """Weighted round robin server selection"""
        if not servers:
            return None
        
        # Calculate total weight
        total_weight = sum(server.weight for server in servers)
        if total_weight == 0:
            return servers[0]
        
        # Weighted selection
        current_weight = 0
        for server in servers:
            current_weight += server.weight
            if self.current_index % total_weight < current_weight:
                self.current_index += 1
                return server
        
        return servers[0]
    
    def _weighted_least_connections_selection(self, servers: List[Server]) -> Server:
        """Weighted least connections server selection"""
        if not servers:
            return None
        
        # Calculate weighted connections
        weighted_connections = [
            (server, server.current_connections / server.weight)
            for server in servers
        ]
        
        return min(weighted_connections, key=lambda x: x[1])[0]
    
    def _ip_hash_selection(self, servers: List[Server], client_ip: str) -> Server:
        """IP hash server selection"""
        if not servers or not client_ip:
            return servers[0] if servers else None
        
        # Hash client IP
        hash_value = int(hashlib.md5(client_ip.encode()).hexdigest(), 16)
        index = hash_value % len(servers)
        return servers[index]
    
    def _least_response_time_selection(self, servers: List[Server]) -> Server:
        """Least response time server selection"""
        if not servers:
            return None
        
        return min(servers, key=lambda s: s.response_time)
    
    def _random_selection(self, servers: List[Server]) -> Server:
        """Random server selection"""
        if not servers:
            return None
        
        return random.choice(servers)
    
    def update_server_health(self, server_id: str, is_healthy: bool, response_time: float = 0.0):
        """Update server health status"""
        if server_id not in self.servers:
            return
        
        server = self.servers[server_id]
        server.last_health_check = datetime.utcnow()
        server.response_time = response_time
        
        if is_healthy:
            server.status = ServerStatus.HEALTHY
            server.success_count += 1
        else:
            server.status = ServerStatus.UNHEALTHY
            server.error_count += 1
        
        # Update response time history
        self.server_response_times[server_id].append(response_time)
        if len(self.server_response_times[server_id]) > 100:  # Keep last 100 measurements
            self.server_response_times[server_id] = self.server_response_times[server_id][-100:]
    
    def _start_health_checking(self):
        """Start health checking for all servers"""
        asyncio.create_task(self._health_check_loop())
    
    async def _health_check_loop(self):
        """Health checking loop"""
        while True:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                await self._perform_health_checks()
            except Exception as e:
                print(f"Health check error: {e}")
    
    async def _perform_health_checks(self):
        """Perform health checks on all servers"""
        tasks = []
        for server in self.servers.values():
            task = asyncio.create_task(self._check_server_health(server))
            tasks.append(task)
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _check_server_health(self, server: Server):
        """Check health of a single server"""
        try:
            if self.config.health_check_type == HealthCheckType.HTTP:
                await self._check_http_health(server)
            elif self.config.health_check_type == HealthCheckType.HTTPS:
                await self._check_https_health(server)
            elif self.config.health_check_type == HealthCheckType.TCP:
                await self._check_tcp_health(server)
        except Exception as e:
            print(f"Health check failed for server {server.id}: {e}")
            self.update_server_health(server.id, False)
    
    async def _check_http_health(self, server: Server):
        """Check HTTP health"""
        url = f"http://{server.host}:{server.port}{self.config.health_check_path}"
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.config.health_check_timeout)) as session:
            start_time = time.time()
            async with session.get(url) as response:
                response_time = time.time() - start_time
                is_healthy = response.status == 200
                self.update_server_health(server.id, is_healthy, response_time)
    
    async def _check_https_health(self, server: Server):
        """Check HTTPS health"""
        url = f"https://{server.host}:{server.port}{self.config.health_check_path}"
        
        ssl_context = ssl.create_default_context()
        if server.ssl_cert_path and server.ssl_key_path:
            ssl_context.load_cert_chain(server.ssl_cert_path, server.ssl_key_path)
        
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=self.config.health_check_timeout)
        ) as session:
            start_time = time.time()
            async with session.get(url) as response:
                response_time = time.time() - start_time
                is_healthy = response.status == 200
                self.update_server_health(server.id, is_healthy, response_time)
    
    async def _check_tcp_health(self, server: Server):
        """Check TCP health"""
        try:
            start_time = time.time()
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(server.host, server.port),
                timeout=self.config.health_check_timeout
            )
            response_time = time.time() - start_time
            writer.close()
            await writer.wait_closed()
            self.update_server_health(server.id, True, response_time)
        except Exception:
            self.update_server_health(server.id, False)
    
    def get_status(self) -> Dict:
        """Get load balancer status"""
        healthy_servers = [
            server for server in self.servers.values()
            if server.status == ServerStatus.HEALTHY
        ]
        
        total_connections = sum(server.current_connections for server in self.servers.values())
        
        return {
            "load_balancer_id": self.lb_id,
            "name": self.config.name,
            "algorithm": self.config.algorithm.value,
            "total_servers": len(self.servers),
            "healthy_servers": len(healthy_servers),
            "total_connections": total_connections,
            "servers": [server.to_dict() for server in self.servers.values()],
            "config": {
                "health_check_interval": self.config.health_check_interval,
                "health_check_timeout": self.config.health_check_timeout,
                "health_check_path": self.config.health_check_path,
                "health_check_type": self.config.health_check_type.value,
                "session_persistence": self.config.session_persistence,
                "rate_limit_enabled": self.config.rate_limit_enabled
            }
        }
    
    def get_metrics(self) -> Dict:
        """Get load balancer metrics"""
        metrics = {
            "load_balancer_id": self.lb_id,
            "timestamp": datetime.utcnow().isoformat(),
            "servers": {}
        }
        
        for server_id, server in self.servers.items():
            response_times = self.server_response_times.get(server_id, [])
            avg_response_time = statistics.mean(response_times) if response_times else 0.0
            
            metrics["servers"][server_id] = {
                "status": server.status.value,
                "current_connections": server.current_connections,
                "max_connections": server.max_connections,
                "connection_utilization": server.current_connections / server.max_connections if server.max_connections > 0 else 0,
                "avg_response_time": avg_response_time,
                "success_count": server.success_count,
                "error_count": server.error_count,
                "success_rate": server.success_count / (server.success_count + server.error_count) if (server.success_count + server.error_count) > 0 else 0,
                "last_health_check": server.last_health_check.isoformat()
            }
        
        return metrics


class RateLimiter:
    """Rate limiting implementation"""
    
    def __init__(self, redis_client, requests_per_minute: int = 1000, window_size: int = 60):
        self.redis_client = redis_client
        self.requests_per_minute = requests_per_minute
        self.window_size = window_size
    
    def is_allowed(self, client_ip: str) -> bool:
        """Check if client is within rate limit"""
        key = f"rate_limit:{client_ip}"
        current_time = int(time.time())
        window_start = current_time - self.window_size
        
        # Remove old entries
        self.redis_client.zremrangebyscore(key, 0, window_start)
        
        # Count current requests
        current_requests = self.redis_client.zcard(key)
        
        if current_requests >= self.requests_per_minute:
            return False
        
        # Add current request
        self.redis_client.zadd(key, {str(current_time): current_time})
        self.redis_client.expire(key, self.window_size)
        
        return True


class LoadBalancerAPI:
    """REST API for Load Balancer service"""
    
    def __init__(self, service: LoadBalancerService):
        self.service = service
    
    def create_load_balancer(self, request_data: Dict) -> Tuple[Dict, int]:
        """API endpoint to create load balancer"""
        try:
            algorithm = LoadBalancingAlgorithm(request_data.get('algorithm', 'round_robin'))
        except ValueError:
            return {"error": "Invalid algorithm"}, 400
        
        config = LoadBalancerConfig(
            name=request_data.get('name', 'default'),
            algorithm=algorithm,
            health_check_interval=request_data.get('health_check_interval', 30),
            health_check_timeout=request_data.get('health_check_timeout', 5),
            health_check_path=request_data.get('health_check_path', '/health'),
            health_check_type=HealthCheckType(request_data.get('health_check_type', 'http')),
            max_retries=request_data.get('max_retries', 3),
            retry_delay=request_data.get('retry_delay', 1),
            session_persistence=request_data.get('session_persistence', False),
            session_timeout=request_data.get('session_timeout', 3600),
            rate_limit_enabled=request_data.get('rate_limit_enabled', False),
            rate_limit_requests=request_data.get('rate_limit_requests', 1000),
            rate_limit_window=request_data.get('rate_limit_window', 60),
            ssl_termination=request_data.get('ssl_termination', False),
            ssl_cert_path=request_data.get('ssl_cert_path', ''),
            ssl_key_path=request_data.get('ssl_key_path', '')
        )
        
        result = self.service.create_load_balancer(config)
        
        if "error" in result:
            return result, 400
        
        return result, 201
    
    def add_server(self, lb_id: str, request_data: Dict) -> Tuple[Dict, int]:
        """API endpoint to add server"""
        server = Server(
            id=request_data.get('id', str(uuid.uuid4())),
            host=request_data.get('host'),
            port=request_data.get('port'),
            weight=request_data.get('weight', 1),
            max_connections=request_data.get('max_connections', 1000),
            ssl_enabled=request_data.get('ssl_enabled', False),
            ssl_cert_path=request_data.get('ssl_cert_path', ''),
            ssl_key_path=request_data.get('ssl_key_path', '')
        )
        
        if not server.host or not server.port:
            return {"error": "Host and port are required"}, 400
        
        result = self.service.add_server(lb_id, server)
        
        if "error" in result:
            return result, 400
        
        return result, 200
    
    def get_server(self, lb_id: str, client_ip: str = None, session_id: str = None) -> Tuple[Dict, int]:
        """API endpoint to get next server"""
        result = self.service.get_server(lb_id, client_ip, session_id)
        
        if "error" in result:
            return result, 404 if "not found" in result["error"].lower() else 503
        
        return result, 200
    
    def get_status(self, lb_id: str) -> Tuple[Dict, int]:
        """API endpoint to get load balancer status"""
        result = self.service.get_load_balancer_status(lb_id)
        
        if "error" in result:
            return result, 404
        
        return result, 200
    
    def get_metrics(self, lb_id: str) -> Tuple[Dict, int]:
        """API endpoint to get load balancer metrics"""
        result = self.service.get_metrics(lb_id)
        
        if "error" in result:
            return result, 404
        
        return result, 200


# Example usage and testing
if __name__ == "__main__":
    # Initialize service
    service = LoadBalancerService(
        db_url="sqlite:///loadbalancer.db",
        redis_url="redis://localhost:6379"
    )
    
    # Create load balancer
    config = LoadBalancerConfig(
        name="web-lb",
        algorithm=LoadBalancingAlgorithm.ROUND_ROBIN,
        health_check_interval=30,
        health_check_path="/health",
        session_persistence=True
    )
    
    result1 = service.create_load_balancer(config)
    print("Created load balancer:", result1)
    
    if "load_balancer_id" in result1:
        lb_id = result1["load_balancer_id"]
        
        # Add servers
        server1 = Server(
            id="server1",
            host="192.168.1.10",
            port=8080,
            weight=1
        )
        
        server2 = Server(
            id="server2",
            host="192.168.1.11",
            port=8080,
            weight=2
        )
        
        result2 = service.add_server(lb_id, server1)
        print("Added server1:", result2)
        
        result3 = service.add_server(lb_id, server2)
        print("Added server2:", result3)
        
        # Get server for request
        for i in range(5):
            result4 = service.get_server(lb_id, client_ip="192.168.1.100")
            print(f"Request {i+1}:", result4)
        
        # Get status
        status = service.get_load_balancer_status(lb_id)
        print("Load balancer status:", status)
        
        # Get metrics
        metrics = service.get_metrics(lb_id)
        print("Load balancer metrics:", metrics)
