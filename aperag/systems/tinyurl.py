"""
TinyURL System Implementation

A comprehensive URL shortening service with features:
- URL shortening and expansion
- Analytics and tracking
- Custom short codes
- Rate limiting
- Caching
- Database persistence
- API endpoints

Author: AI Assistant
Date: 2024
"""

import hashlib
import random
import string
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import redis
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

Base = declarative_base()


class URLMapping(Base):
    """Database model for URL mappings"""
    __tablename__ = 'url_mappings'
    
    id = Column(Integer, primary_key=True)
    short_code = Column(String(10), unique=True, index=True, nullable=False)
    original_url = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    click_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    user_id = Column(String(50), nullable=True)
    custom_code = Column(String(10), nullable=True, unique=True, index=True)


class TinyURLService:
    """Main TinyURL service class"""
    
    def __init__(self, db_url: str, redis_url: str = "redis://localhost:6379"):
        self.db_url = db_url
        self.redis_url = redis_url
        self.redis_client = redis.from_url(redis_url)
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        
        # Configuration
        self.short_code_length = 6
        self.max_retries = 5
        self.cache_ttl = 3600  # 1 hour
        self.rate_limit_window = 60  # 1 minute
        self.rate_limit_requests = 100  # 100 requests per minute
    
    def _generate_short_code(self, length: int = None) -> str:
        """Generate a random short code"""
        if length is None:
            length = self.short_code_length
        
        characters = string.ascii_letters + string.digits
        return ''.join(random.choices(characters, k=length))
    
    def _is_valid_url(self, url: str) -> bool:
        """Validate if URL is properly formatted"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    
    def _get_cache_key(self, short_code: str) -> str:
        """Get Redis cache key for short code"""
        return f"tinyurl:{short_code}"
    
    def _get_rate_limit_key(self, user_id: str) -> str:
        """Get Redis rate limit key for user"""
        return f"rate_limit:{user_id}"
    
    def _check_rate_limit(self, user_id: str) -> bool:
        """Check if user has exceeded rate limit"""
        key = self._get_rate_limit_key(user_id)
        current_requests = self.redis_client.get(key)
        
        if current_requests is None:
            self.redis_client.setex(key, self.rate_limit_window, 1)
            return True
        
        if int(current_requests) >= self.rate_limit_requests:
            return False
        
        self.redis_client.incr(key)
        return True
    
    def create_short_url(self, original_url: str, custom_code: str = None, 
                        user_id: str = None, expires_in_days: int = None) -> Dict:
        """Create a short URL"""
        # Validate input
        if not self._is_valid_url(original_url):
            return {"error": "Invalid URL format"}
        
        # Check rate limit
        if user_id and not self._check_rate_limit(user_id):
            return {"error": "Rate limit exceeded"}
        
        # Check if custom code is provided and available
        if custom_code:
            if len(custom_code) < 3 or len(custom_code) > 10:
                return {"error": "Custom code must be 3-10 characters"}
            
            if not custom_code.isalnum():
                return {"error": "Custom code must contain only alphanumeric characters"}
            
            # Check if custom code already exists
            existing = self.session.query(URLMapping).filter(
                URLMapping.custom_code == custom_code
            ).first()
            
            if existing:
                return {"error": "Custom code already exists"}
        
        # Generate short code if not custom
        if not custom_code:
            for _ in range(self.max_retries):
                short_code = self._generate_short_code()
                existing = self.session.query(URLMapping).filter(
                    URLMapping.short_code == short_code
                ).first()
                
                if not existing:
                    break
            else:
                return {"error": "Unable to generate unique short code"}
        else:
            short_code = custom_code
        
        # Calculate expiration date
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        
        # Create URL mapping
        url_mapping = URLMapping(
            short_code=short_code,
            original_url=original_url,
            expires_at=expires_at,
            user_id=user_id,
            custom_code=custom_code
        )
        
        try:
            self.session.add(url_mapping)
            self.session.commit()
            
            # Cache the mapping
            cache_key = self._get_cache_key(short_code)
            cache_data = {
                'original_url': original_url,
                'expires_at': expires_at.isoformat() if expires_at else None,
                'is_active': True
            }
            self.redis_client.setex(cache_key, self.cache_ttl, str(cache_data))
            
            return {
                "short_code": short_code,
                "short_url": f"https://tiny.url/{short_code}",
                "original_url": original_url,
                "expires_at": expires_at.isoformat() if expires_at else None,
                "created_at": url_mapping.created_at.isoformat()
            }
        
        except Exception as e:
            self.session.rollback()
            return {"error": f"Database error: {str(e)}"}
    
    def expand_url(self, short_code: str) -> Dict:
        """Expand a short URL to original URL"""
        # Check cache first
        cache_key = self._get_cache_key(short_code)
        cached_data = self.redis_client.get(cache_key)
        
        if cached_data:
            try:
                import ast
                cache_data = ast.literal_eval(cached_data.decode())
                
                # Check if expired
                if cache_data.get('expires_at'):
                    expires_at = datetime.fromisoformat(cache_data['expires_at'])
                    if datetime.utcnow() > expires_at:
                        return {"error": "URL has expired"}
                
                if not cache_data.get('is_active', True):
                    return {"error": "URL is inactive"}
                
                # Increment click count
                self._increment_click_count(short_code)
                
                return {
                    "original_url": cache_data['original_url'],
                    "short_code": short_code
                }
            except Exception:
                pass  # Fall back to database
        
        # Query database
        url_mapping = self.session.query(URLMapping).filter(
            URLMapping.short_code == short_code
        ).first()
        
        if not url_mapping:
            return {"error": "Short URL not found"}
        
        # Check if expired
        if url_mapping.expires_at and datetime.utcnow() > url_mapping.expires_at:
            return {"error": "URL has expired"}
        
        # Check if active
        if not url_mapping.is_active:
            return {"error": "URL is inactive"}
        
        # Update click count
        url_mapping.click_count += 1
        self.session.commit()
        
        # Cache the result
        cache_data = {
            'original_url': url_mapping.original_url,
            'expires_at': url_mapping.expires_at.isoformat() if url_mapping.expires_at else None,
            'is_active': url_mapping.is_active
        }
        self.redis_client.setex(cache_key, self.cache_ttl, str(cache_data))
        
        return {
            "original_url": url_mapping.original_url,
            "short_code": short_code,
            "click_count": url_mapping.click_count
        }
    
    def _increment_click_count(self, short_code: str):
        """Increment click count for analytics"""
        try:
            url_mapping = self.session.query(URLMapping).filter(
                URLMapping.short_code == short_code
            ).first()
            
            if url_mapping:
                url_mapping.click_count += 1
                self.session.commit()
        except Exception:
            pass  # Don't fail if analytics update fails
    
    def get_analytics(self, short_code: str, user_id: str = None) -> Dict:
        """Get analytics for a short URL"""
        url_mapping = self.session.query(URLMapping).filter(
            URLMapping.short_code == short_code
        ).first()
        
        if not url_mapping:
            return {"error": "Short URL not found"}
        
        # Check if user owns this URL
        if user_id and url_mapping.user_id != user_id:
            return {"error": "Access denied"}
        
        return {
            "short_code": short_code,
            "original_url": url_mapping.original_url,
            "click_count": url_mapping.click_count,
            "created_at": url_mapping.created_at.isoformat(),
            "expires_at": url_mapping.expires_at.isoformat() if url_mapping.expires_at else None,
            "is_active": url_mapping.is_active
        }
    
    def get_user_urls(self, user_id: str, limit: int = 50, offset: int = 0) -> Dict:
        """Get all URLs created by a user"""
        query = self.session.query(URLMapping).filter(
            URLMapping.user_id == user_id
        ).order_by(URLMapping.created_at.desc())
        
        total = query.count()
        urls = query.offset(offset).limit(limit).all()
        
        return {
            "urls": [
                {
                    "short_code": url.short_code,
                    "original_url": url.original_url,
                    "click_count": url.click_count,
                    "created_at": url.created_at.isoformat(),
                    "expires_at": url.expires_at.isoformat() if url.expires_at else None,
                    "is_active": url.is_active
                }
                for url in urls
            ],
            "total": total,
            "limit": limit,
            "offset": offset
        }
    
    def deactivate_url(self, short_code: str, user_id: str = None) -> Dict:
        """Deactivate a short URL"""
        url_mapping = self.session.query(URLMapping).filter(
            URLMapping.short_code == short_code
        ).first()
        
        if not url_mapping:
            return {"error": "Short URL not found"}
        
        # Check if user owns this URL
        if user_id and url_mapping.user_id != user_id:
            return {"error": "Access denied"}
        
        url_mapping.is_active = False
        self.session.commit()
        
        # Remove from cache
        cache_key = self._get_cache_key(short_code)
        self.redis_client.delete(cache_key)
        
        return {"message": "URL deactivated successfully"}
    
    def cleanup_expired_urls(self) -> int:
        """Clean up expired URLs"""
        expired_urls = self.session.query(URLMapping).filter(
            URLMapping.expires_at < datetime.utcnow()
        ).all()
        
        count = 0
        for url in expired_urls:
            url.is_active = False
            count += 1
        
        self.session.commit()
        return count
    
    def get_stats(self) -> Dict:
        """Get overall service statistics"""
        total_urls = self.session.query(URLMapping).count()
        active_urls = self.session.query(URLMapping).filter(
            URLMapping.is_active == True
        ).count()
        
        total_clicks = self.session.query(URLMapping).with_entities(
            URLMapping.click_count
        ).all()
        total_clicks = sum(click[0] for click in total_clicks)
        
        return {
            "total_urls": total_urls,
            "active_urls": active_urls,
            "total_clicks": total_clicks,
            "average_clicks_per_url": total_clicks / total_urls if total_urls > 0 else 0
        }


class TinyURLAPI:
    """REST API for TinyURL service"""
    
    def __init__(self, service: TinyURLService):
        self.service = service
    
    def create_short_url(self, request_data: Dict) -> Dict:
        """API endpoint to create short URL"""
        original_url = request_data.get('url')
        custom_code = request_data.get('custom_code')
        user_id = request_data.get('user_id')
        expires_in_days = request_data.get('expires_in_days')
        
        if not original_url:
            return {"error": "URL is required"}, 400
        
        result = self.service.create_short_url(
            original_url=original_url,
            custom_code=custom_code,
            user_id=user_id,
            expires_in_days=expires_in_days
        )
        
        if "error" in result:
            return result, 400
        
        return result, 201
    
    def expand_url(self, short_code: str) -> Dict:
        """API endpoint to expand short URL"""
        result = self.service.expand_url(short_code)
        
        if "error" in result:
            return result, 404
        
        return result, 200
    
    def get_analytics(self, short_code: str, user_id: str = None) -> Dict:
        """API endpoint to get analytics"""
        result = self.service.get_analytics(short_code, user_id)
        
        if "error" in result:
            return result, 404 if "not found" in result["error"].lower() else 403
        
        return result, 200
    
    def get_user_urls(self, user_id: str, limit: int = 50, offset: int = 0) -> Dict:
        """API endpoint to get user's URLs"""
        if not user_id:
            return {"error": "User ID is required"}, 400
        
        result = self.service.get_user_urls(user_id, limit, offset)
        return result, 200
    
    def deactivate_url(self, short_code: str, user_id: str = None) -> Dict:
        """API endpoint to deactivate URL"""
        result = self.service.deactivate_url(short_code, user_id)
        
        if "error" in result:
            return result, 404 if "not found" in result["error"].lower() else 403
        
        return result, 200
    
    def get_stats(self) -> Dict:
        """API endpoint to get service stats"""
        result = self.service.get_stats()
        return result, 200


# Example usage and testing
if __name__ == "__main__":
    # Initialize service
    service = TinyURLService(
        db_url="sqlite:///tinyurl.db",
        redis_url="redis://localhost:6379"
    )
    
    # Test creating short URLs
    result1 = service.create_short_url("https://www.google.com", user_id="user123")
    print("Created short URL:", result1)
    
    result2 = service.create_short_url(
        "https://www.github.com", 
        custom_code="github",
        user_id="user123",
        expires_in_days=30
    )
    print("Created custom short URL:", result2)
    
    # Test expanding URLs
    if "short_code" in result1:
        expanded = service.expand_url(result1["short_code"])
        print("Expanded URL:", expanded)
    
    # Test analytics
    if "short_code" in result1:
        analytics = service.get_analytics(result1["short_code"], "user123")
        print("Analytics:", analytics)
    
    # Test user URLs
    user_urls = service.get_user_urls("user123")
    print("User URLs:", user_urls)
    
    # Test stats
    stats = service.get_stats()
    print("Service stats:", stats)
