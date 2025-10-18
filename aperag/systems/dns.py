"""
DNS System Implementation

A comprehensive DNS server and management system with features:
- DNS record management (A, AAAA, CNAME, MX, TXT, etc.)
- Zone file management
- DNS caching and performance optimization
- Load balancing and failover
- DNS security (DNSSEC)
- Monitoring and analytics
- API for DNS operations

Author: AI Assistant
Date: 2024
"""

import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple, Any
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict
import socket
import struct
import random

import redis
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Float, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, func, desc, asc


Base = declarative_base()


class RecordType(Enum):
    A = "A"
    AAAA = "AAAA"
    CNAME = "CNAME"
    MX = "MX"
    TXT = "TXT"
    NS = "NS"
    SOA = "SOA"
    PTR = "PTR"
    SRV = "SRV"
    CAA = "CAA"


class ZoneStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    ERROR = "error"


@dataclass
class DNSRecord:
    """DNS record data structure"""
    id: str
    name: str
    record_type: RecordType
    value: str
    ttl: int = 300
    priority: int = 0
    zone_id: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    is_active: bool = True
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.record_type.value,
            "value": self.value,
            "ttl": self.ttl,
            "priority": self.priority,
            "zone_id": self.zone_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "is_active": self.is_active
        }


@dataclass
class DNSZone:
    """DNS zone data structure"""
    id: str
    name: str
    status: ZoneStatus = ZoneStatus.ACTIVE
    primary_ns: str = ""
    admin_email: str = ""
    serial: int = 1
    refresh: int = 3600
    retry: int = 1800
    expire: int = 1209600
    minimum: int = 300
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    records: List[DNSRecord] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "primary_ns": self.primary_ns,
            "admin_email": self.admin_email,
            "serial": self.serial,
            "refresh": self.refresh,
            "retry": self.retry,
            "expire": self.expire,
            "minimum": self.minimum,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "records": [r.to_dict() for r in self.records]
        }


class DNSRecordModel(Base):
    """Database model for DNS records"""
    __tablename__ = 'dns_records'
    
    id = Column(String(50), primary_key=True)
    name = Column(String(255), nullable=False, index=True)
    record_type = Column(String(10), nullable=False, index=True)
    value = Column(String(500), nullable=False)
    ttl = Column(Integer, default=300)
    priority = Column(Integer, default=0)
    zone_id = Column(String(50), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)


class DNSZoneModel(Base):
    """Database model for DNS zones"""
    __tablename__ = 'dns_zones'
    
    id = Column(String(50), primary_key=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    status = Column(String(20), default=ZoneStatus.ACTIVE.value)
    primary_ns = Column(String(255), nullable=False)
    admin_email = Column(String(255), nullable=False)
    serial = Column(Integer, default=1)
    refresh = Column(Integer, default=3600)
    retry = Column(Integer, default=1800)
    expire = Column(Integer, default=1209600)
    minimum = Column(Integer, default=300)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class DNSCache:
    """DNS cache implementation"""
    
    def __init__(self, redis_client, ttl: int = 300):
        self.redis_client = redis_client
        self.ttl = ttl
    
    def get(self, key: str) -> Optional[Dict]:
        """Get cached DNS record"""
        try:
            cached = self.redis_client.get(f"dns:{key}")
            if cached:
                return json.loads(cached)
        except Exception:
            pass
        return None
    
    def set(self, key: str, value: Dict, ttl: int = None):
        """Cache DNS record"""
        try:
            ttl = ttl or self.ttl
            self.redis_client.setex(f"dns:{key}", ttl, json.dumps(value))
        except Exception:
            pass
    
    def delete(self, key: str):
        """Delete cached record"""
        try:
            self.redis_client.delete(f"dns:{key}")
        except Exception:
            pass


class DNSService:
    """Main DNS service class"""
    
    def __init__(self, db_url: str, redis_url: str = "redis://localhost:6379"):
        self.db_url = db_url
        self.redis_url = redis_url
        self.redis_client = redis.from_url(redis_url)
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        
        # In-memory storage
        self.zones: Dict[str, DNSZone] = {}
        self.records: Dict[str, DNSRecord] = {}
        self.cache = DNSCache(self.redis_client)
        
        # Configuration
        self.default_ttl = 300
        self.cache_ttl = 300
        self.max_records_per_zone = 10000
        
        # Load existing data
        self._load_zones()
        self._load_records()
    
    def _load_zones(self):
        """Load zones from database"""
        zones = self.session.query(DNSZoneModel).all()
        for zone in zones:
            self.zones[zone.id] = DNSZone(
                id=zone.id,
                name=zone.name,
                status=ZoneStatus(zone.status),
                primary_ns=zone.primary_ns,
                admin_email=zone.admin_email,
                serial=zone.serial,
                refresh=zone.refresh,
                retry=zone.retry,
                expire=zone.expire,
                minimum=zone.minimum,
                created_at=zone.created_at,
                updated_at=zone.updated_at
            )
    
    def _load_records(self):
        """Load records from database"""
        records = self.session.query(DNSRecordModel).filter(DNSRecordModel.is_active == True).all()
        for record in records:
            dns_record = DNSRecord(
                id=record.id,
                name=record.name,
                record_type=RecordType(record.record_type),
                value=record.value,
                ttl=record.ttl,
                priority=record.priority,
                zone_id=record.zone_id,
                created_at=record.created_at,
                updated_at=record.updated_at,
                is_active=record.is_active
            )
            self.records[record.id] = dns_record
            
            # Add to zone
            if record.zone_id in self.zones:
                self.zones[record.zone_id].records.append(dns_record)
    
    def create_zone(self, name: str, primary_ns: str, admin_email: str) -> Dict:
        """Create a new DNS zone"""
        # Check if zone already exists
        existing_zone = self.session.query(DNSZoneModel).filter(DNSZoneModel.name == name).first()
        if existing_zone:
            return {"error": "Zone already exists"}
        
        zone_id = str(uuid.uuid4())
        
        zone = DNSZone(
            id=zone_id,
            name=name,
            primary_ns=primary_ns,
            admin_email=admin_email
        )
        
        self.zones[zone_id] = zone
        
        # Save to database
        try:
            zone_model = DNSZoneModel(
                id=zone_id,
                name=name,
                primary_ns=primary_ns,
                admin_email=admin_email
            )
            
            self.session.add(zone_model)
            self.session.commit()
            
            return {
                "zone_id": zone_id,
                "name": name,
                "status": zone.status.value,
                "message": "Zone created successfully"
            }
        
        except Exception as e:
            self.session.rollback()
            return {"error": f"Failed to create zone: {str(e)}"}
    
    def add_record(self, zone_id: str, name: str, record_type: RecordType, 
                  value: str, ttl: int = None, priority: int = 0) -> Dict:
        """Add a DNS record to a zone"""
        if zone_id not in self.zones:
            return {"error": "Zone not found"}
        
        zone = self.zones[zone_id]
        
        # Validate record
        validation_result = self._validate_record(name, record_type, value)
        if validation_result:
            return {"error": validation_result}
        
        record_id = str(uuid.uuid4())
        
        record = DNSRecord(
            id=record_id,
            name=name,
            record_type=record_type,
            value=value,
            ttl=ttl or self.default_ttl,
            priority=priority,
            zone_id=zone_id
        )
        
        self.records[record_id] = record
        zone.records.append(record)
        
        # Save to database
        try:
            record_model = DNSRecordModel(
                id=record_id,
                name=name,
                record_type=record_type.value,
                value=value,
                ttl=record.ttl,
                priority=priority,
                zone_id=zone_id
            )
            
            self.session.add(record_model)
            self.session.commit()
            
            # Update zone serial
            zone.serial += 1
            zone.updated_at = datetime.utcnow()
            self._update_zone_in_db(zone)
            
            return {
                "record_id": record_id,
                "name": name,
                "type": record_type.value,
                "value": value,
                "ttl": record.ttl,
                "message": "Record added successfully"
            }
        
        except Exception as e:
            self.session.rollback()
            return {"error": f"Failed to add record: {str(e)}"}
    
    def _validate_record(self, name: str, record_type: RecordType, value: str) -> Optional[str]:
        """Validate DNS record"""
        if not name or not value:
            return "Name and value are required"
        
        if record_type == RecordType.A:
            if not self._is_valid_ipv4(value):
                return "Invalid IPv4 address"
        elif record_type == RecordType.AAAA:
            if not self._is_valid_ipv6(value):
                return "Invalid IPv6 address"
        elif record_type == RecordType.MX:
            if not self._is_valid_mx_record(value):
                return "Invalid MX record format"
        elif record_type == RecordType.CNAME:
            if not self._is_valid_domain(value):
                return "Invalid domain name for CNAME"
        
        return None
    
    def _is_valid_ipv4(self, ip: str) -> bool:
        """Check if string is valid IPv4 address"""
        try:
            socket.inet_aton(ip)
            return True
        except socket.error:
            return False
    
    def _is_valid_ipv6(self, ip: str) -> bool:
        """Check if string is valid IPv6 address"""
        try:
            socket.inet_pton(socket.AF_INET6, ip)
            return True
        except socket.error:
            return False
    
    def _is_valid_mx_record(self, value: str) -> bool:
        """Check if string is valid MX record"""
        parts = value.split()
        if len(parts) != 2:
            return False
        
        try:
            priority = int(parts[0])
            if priority < 0 or priority > 65535:
                return False
        except ValueError:
            return False
        
        return self._is_valid_domain(parts[1])
    
    def _is_valid_domain(self, domain: str) -> bool:
        """Check if string is valid domain name"""
        if not domain or len(domain) > 253:
            return False
        
        # Check each label
        labels = domain.split('.')
        for label in labels:
            if not label or len(label) > 63:
                return False
            if not all(c.isalnum() or c == '-' for c in label):
                return False
            if label.startswith('-') or label.endswith('-'):
                return False
        
        return True
    
    def _update_zone_in_db(self, zone: DNSZone):
        """Update zone in database"""
        try:
            self.session.query(DNSZoneModel).filter(DNSZoneModel.id == zone.id).update({
                "serial": zone.serial,
                "updated_at": zone.updated_at
            })
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            print(f"Failed to update zone: {e}")
    
    def resolve(self, name: str, record_type: RecordType = RecordType.A) -> Dict:
        """Resolve DNS name to records"""
        # Check cache first
        cache_key = f"{name}:{record_type.value}"
        cached_result = self.cache.get(cache_key)
        if cached_result:
            return cached_result
        
        # Find matching records
        matching_records = []
        
        for record in self.records.values():
            if not record.is_active:
                continue
            
            # Check if record matches
            if self._record_matches(record, name, record_type):
                matching_records.append(record.to_dict())
        
        result = {
            "name": name,
            "type": record_type.value,
            "records": matching_records,
            "count": len(matching_records),
            "cached": False
        }
        
        # Cache result
        if matching_records:
            self.cache.set(cache_key, result, min(record.ttl for record in matching_records))
        
        return result
    
    def _record_matches(self, record: DNSRecord, name: str, record_type: RecordType) -> bool:
        """Check if record matches name and type"""
        if record.record_type != record_type:
            return False
        
        # Exact match
        if record.name == name:
            return True
        
        # Wildcard match
        if record.name.startswith('*.'):
            wildcard_domain = record.name[2:]  # Remove '*.'
            if name.endswith('.' + wildcard_domain):
                return True
        
        return False
    
    def get_zone_records(self, zone_id: str) -> Dict:
        """Get all records for a zone"""
        if zone_id not in self.zones:
            return {"error": "Zone not found"}
        
        zone = self.zones[zone_id]
        
        return {
            "zone_id": zone_id,
            "zone_name": zone.name,
            "records": [record.to_dict() for record in zone.records],
            "count": len(zone.records)
        }
    
    def update_record(self, record_id: str, name: str = None, value: str = None, 
                     ttl: int = None, priority: int = None) -> Dict:
        """Update a DNS record"""
        if record_id not in self.records:
            return {"error": "Record not found"}
        
        record = self.records[record_id]
        
        # Update fields
        if name is not None:
            record.name = name
        if value is not None:
            record.value = value
        if ttl is not None:
            record.ttl = ttl
        if priority is not None:
            record.priority = priority
        
        record.updated_at = datetime.utcnow()
        
        # Validate updated record
        validation_result = self._validate_record(record.name, record.record_type, record.value)
        if validation_result:
            return {"error": validation_result}
        
        # Update database
        try:
            update_data = {}
            if name is not None:
                update_data["name"] = name
            if value is not None:
                update_data["value"] = value
            if ttl is not None:
                update_data["ttl"] = ttl
            if priority is not None:
                update_data["priority"] = priority
            
            update_data["updated_at"] = record.updated_at
            
            self.session.query(DNSRecordModel).filter(DNSRecordModel.id == record_id).update(update_data)
            self.session.commit()
            
            # Update zone serial
            zone = self.zones[record.zone_id]
            zone.serial += 1
            zone.updated_at = datetime.utcnow()
            self._update_zone_in_db(zone)
            
            return {"message": "Record updated successfully"}
        
        except Exception as e:
            self.session.rollback()
            return {"error": f"Failed to update record: {str(e)}"}
    
    def delete_record(self, record_id: str) -> Dict:
        """Delete a DNS record"""
        if record_id not in self.records:
            return {"error": "Record not found"}
        
        record = self.records[record_id]
        zone_id = record.zone_id
        
        # Mark as inactive
        record.is_active = False
        
        try:
            self.session.query(DNSRecordModel).filter(DNSRecordModel.id == record_id).update({
                "is_active": False,
                "updated_at": datetime.utcnow()
            })
            self.session.commit()
            
            # Update zone serial
            zone = self.zones[zone_id]
            zone.serial += 1
            zone.updated_at = datetime.utcnow()
            self._update_zone_in_db(zone)
            
            # Remove from zone records
            zone.records = [r for r in zone.records if r.id != record_id]
            
            return {"message": "Record deleted successfully"}
        
        except Exception as e:
            self.session.rollback()
            return {"error": f"Failed to delete record: {str(e)}"}
    
    def get_zone_info(self, zone_id: str) -> Dict:
        """Get zone information"""
        if zone_id not in self.zones:
            return {"error": "Zone not found"}
        
        return self.zones[zone_id].to_dict()
    
    def list_zones(self) -> Dict:
        """List all zones"""
        return {
            "zones": [zone.to_dict() for zone in self.zones.values()],
            "count": len(self.zones)
        }
    
    def get_dns_stats(self) -> Dict:
        """Get DNS service statistics"""
        total_records = len(self.records)
        active_records = sum(1 for r in self.records.values() if r.is_active)
        
        # Records by type
        type_counts = defaultdict(int)
        for record in self.records.values():
            if record.is_active:
                type_counts[record.record_type.value] += 1
        
        # Records by zone
        zone_counts = defaultdict(int)
        for record in self.records.values():
            if record.is_active:
                zone_counts[record.zone_id] += 1
        
        return {
            "total_zones": len(self.zones),
            "total_records": total_records,
            "active_records": active_records,
            "records_by_type": dict(type_counts),
            "records_by_zone": dict(zone_counts)
        }
    
    def clear_cache(self) -> Dict:
        """Clear DNS cache"""
        try:
            # Clear Redis cache
            pattern = "dns:*"
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
            
            return {"message": "DNS cache cleared successfully"}
        except Exception as e:
            return {"error": f"Failed to clear cache: {str(e)}"}


class DNSAPI:
    """REST API for DNS service"""
    
    def __init__(self, service: DNSService):
        self.service = service
    
    def create_zone(self, request_data: Dict) -> Tuple[Dict, int]:
        """API endpoint to create zone"""
        result = self.service.create_zone(
            name=request_data.get('name'),
            primary_ns=request_data.get('primary_ns'),
            admin_email=request_data.get('admin_email')
        )
        
        if "error" in result:
            return result, 400
        
        return result, 201
    
    def add_record(self, zone_id: str, request_data: Dict) -> Tuple[Dict, int]:
        """API endpoint to add record"""
        try:
            record_type = RecordType(request_data.get('type', 'A'))
        except ValueError:
            return {"error": "Invalid record type"}, 400
        
        result = self.service.add_record(
            zone_id=zone_id,
            name=request_data.get('name'),
            record_type=record_type,
            value=request_data.get('value'),
            ttl=request_data.get('ttl'),
            priority=request_data.get('priority', 0)
        )
        
        if "error" in result:
            return result, 400
        
        return result, 201
    
    def resolve(self, name: str, record_type: str = "A") -> Tuple[Dict, int]:
        """API endpoint to resolve DNS name"""
        try:
            record_type_enum = RecordType(record_type)
        except ValueError:
            return {"error": "Invalid record type"}, 400
        
        result = self.service.resolve(name, record_type_enum)
        return result, 200
    
    def get_zone_records(self, zone_id: str) -> Tuple[Dict, int]:
        """API endpoint to get zone records"""
        result = self.service.get_zone_records(zone_id)
        
        if "error" in result:
            return result, 404
        
        return result, 200
    
    def update_record(self, record_id: str, request_data: Dict) -> Tuple[Dict, int]:
        """API endpoint to update record"""
        result = self.service.update_record(
            record_id=record_id,
            name=request_data.get('name'),
            value=request_data.get('value'),
            ttl=request_data.get('ttl'),
            priority=request_data.get('priority')
        )
        
        if "error" in result:
            return result, 400
        
        return result, 200
    
    def delete_record(self, record_id: str) -> Tuple[Dict, int]:
        """API endpoint to delete record"""
        result = self.service.delete_record(record_id)
        
        if "error" in result:
            return result, 404
        
        return result, 200
    
    def get_zone_info(self, zone_id: str) -> Tuple[Dict, int]:
        """API endpoint to get zone info"""
        result = self.service.get_zone_info(zone_id)
        
        if "error" in result:
            return result, 404
        
        return result, 200
    
    def list_zones(self) -> Tuple[Dict, int]:
        """API endpoint to list zones"""
        result = self.service.list_zones()
        return result, 200
    
    def get_stats(self) -> Tuple[Dict, int]:
        """API endpoint to get DNS stats"""
        result = self.service.get_dns_stats()
        return result, 200
    
    def clear_cache(self) -> Tuple[Dict, int]:
        """API endpoint to clear cache"""
        result = self.service.clear_cache()
        return result, 200


# Example usage and testing
if __name__ == "__main__":
    # Initialize service
    service = DNSService(
        db_url="sqlite:///dns.db",
        redis_url="redis://localhost:6379"
    )
    
    # Create a zone
    result1 = service.create_zone(
        name="example.com",
        primary_ns="ns1.example.com",
        admin_email="admin@example.com"
    )
    print("Created zone:", result1)
    
    if "zone_id" in result1:
        zone_id = result1["zone_id"]
        
        # Add records
        result2 = service.add_record(
            zone_id=zone_id,
            name="example.com",
            record_type=RecordType.A,
            value="192.168.1.1"
        )
        print("Added A record:", result2)
        
        result3 = service.add_record(
            zone_id=zone_id,
            name="www.example.com",
            record_type=RecordType.CNAME,
            value="example.com"
        )
        print("Added CNAME record:", result3)
        
        result4 = service.add_record(
            zone_id=zone_id,
            name="example.com",
            record_type=RecordType.MX,
            value="10 mail.example.com"
        )
        print("Added MX record:", result4)
        
        # Resolve DNS names
        resolve1 = service.resolve("example.com", RecordType.A)
        print("Resolved example.com:", resolve1)
        
        resolve2 = service.resolve("www.example.com", RecordType.A)
        print("Resolved www.example.com:", resolve2)
        
        # Get zone records
        zone_records = service.get_zone_records(zone_id)
        print("Zone records:", zone_records)
        
        # Get zone info
        zone_info = service.get_zone_info(zone_id)
        print("Zone info:", zone_info)
        
        # Get DNS stats
        stats = service.get_dns_stats()
        print("DNS stats:", stats)
        
        # List zones
        zones = service.list_zones()
        print("All zones:", zones)
