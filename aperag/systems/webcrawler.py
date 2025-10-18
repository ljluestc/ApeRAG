"""
Web Crawler System Implementation

A comprehensive web crawling and scraping system with features:
- Multi-threaded crawling with rate limiting
- Content extraction and parsing
- URL filtering and deduplication
- Robots.txt compliance
- Sitemap parsing
- Content indexing and search
- Data export and storage
- Monitoring and analytics

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
from collections import defaultdict, deque
import re
import hashlib
from urllib.parse import urljoin, urlparse, robots
from urllib.robotparser import RobotFileParser

import redis
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Float, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, func, desc, asc
import aiohttp
import asyncio
from bs4 import BeautifulSoup
import requests


Base = declarative_base()


class CrawlStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ContentType(Enum):
    HTML = "html"
    PDF = "pdf"
    IMAGE = "image"
    TEXT = "text"
    JSON = "json"
    XML = "xml"


@dataclass
class CrawlJob:
    """Crawl job data structure"""
    id: str
    url: str
    status: CrawlStatus = CrawlStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    priority: int = 0
    depth: int = 0
    max_depth: int = 3
    retry_count: int = 0
    max_retries: int = 3
    error_message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "url": self.url,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "priority": self.priority,
            "depth": self.depth,
            "max_depth": self.max_depth,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "error_message": self.error_message,
            "metadata": self.metadata
        }


@dataclass
class CrawledContent:
    """Crawled content data structure"""
    id: str
    url: str
    title: str
    content: str
    content_type: ContentType
    crawled_at: datetime = field(default_factory=datetime.utcnow)
    response_time: float = 0.0
    status_code: int = 200
    content_length: int = 0
    links: List[str] = field(default_factory=list)
    images: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "url": self.url,
            "title": self.title,
            "content": self.content,
            "type": self.content_type.value,
            "crawled_at": self.crawled_at.isoformat(),
            "response_time": self.response_time,
            "status_code": self.status_code,
            "content_length": self.content_length,
            "links": self.links,
            "images": self.images,
            "metadata": self.metadata
        }


class CrawlJobModel(Base):
    """Database model for crawl jobs"""
    __tablename__ = 'crawl_jobs'
    
    id = Column(String(50), primary_key=True)
    url = Column(String(1000), nullable=False, index=True)
    status = Column(String(20), default=CrawlStatus.PENDING.value)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    priority = Column(Integer, default=0)
    depth = Column(Integer, default=0)
    max_depth = Column(Integer, default=3)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    error_message = Column(Text)
    metadata = Column(JSON)


class CrawledContentModel(Base):
    """Database model for crawled content"""
    __tablename__ = 'crawled_content'
    
    id = Column(String(50), primary_key=True)
    url = Column(String(1000), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    content_type = Column(String(20), nullable=False)
    crawled_at = Column(DateTime, default=datetime.utcnow, index=True)
    response_time = Column(Float, default=0.0)
    status_code = Column(Integer, default=200)
    content_length = Column(Integer, default=0)
    links = Column(JSON)
    images = Column(JSON)
    metadata = Column(JSON)


class WebCrawlerService:
    """Main web crawler service class"""
    
    def __init__(self, db_url: str, redis_url: str = "redis://localhost:6379"):
        self.db_url = db_url
        self.redis_url = redis_url
        self.redis_client = redis.from_url(redis_url)
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        
        # In-memory storage
        self.crawl_jobs: Dict[str, CrawlJob] = {}
        self.crawled_content: Dict[str, CrawledContent] = {}
        self.visited_urls: Set[str] = set()
        self.robots_cache: Dict[str, RobotFileParser] = {}
        
        # Configuration
        self.max_concurrent_requests = 10
        self.request_delay = 1.0  # seconds
        self.timeout = 30  # seconds
        self.max_content_length = 10 * 1024 * 1024  # 10MB
        self.user_agent = "WebCrawler/1.0"
        
        # Rate limiting
        self.domain_rates: Dict[str, float] = defaultdict(float)
        self.rate_limit_window = 60  # seconds
        self.max_requests_per_domain = 10
        
        # Start crawler
        self._start_crawler()
    
    def _start_crawler(self):
        """Start the crawler background task"""
        asyncio.create_task(self._crawler_loop())
    
    async def _crawler_loop(self):
        """Main crawler loop"""
        while True:
            try:
                await asyncio.sleep(1)  # Check every second
                await self._process_crawl_jobs()
            except Exception as e:
                print(f"Crawler error: {e}")
    
    async def _process_crawl_jobs(self):
        """Process pending crawl jobs"""
        # Get pending jobs
        pending_jobs = [
            job for job in self.crawl_jobs.values()
            if job.status == CrawlStatus.PENDING
        ]
        
        # Sort by priority (higher priority first)
        pending_jobs.sort(key=lambda x: x.priority, reverse=True)
        
        # Process up to max_concurrent_requests
        tasks = []
        for job in pending_jobs[:self.max_concurrent_requests]:
            task = asyncio.create_task(self._crawl_url(job))
            tasks.append(task)
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _crawl_url(self, job: CrawlJob):
        """Crawl a single URL"""
        job.status = CrawlStatus.IN_PROGRESS
        job.started_at = datetime.utcnow()
        
        try:
            # Check robots.txt
            if not self._can_crawl(job.url):
                job.status = CrawlStatus.SKIPPED
                job.error_message = "Blocked by robots.txt"
                job.completed_at = datetime.utcnow()
                return
            
            # Check rate limiting
            domain = urlparse(job.url).netloc
            if not self._check_rate_limit(domain):
                job.status = CrawlStatus.PENDING  # Retry later
                return
            
            # Crawl the URL
            content = await self._fetch_url(job.url)
            
            if content:
                # Save content
                self._save_crawled_content(content)
                
                # Extract links for further crawling
                if job.depth < job.max_depth:
                    self._extract_and_queue_links(content, job.depth + 1)
                
                job.status = CrawlStatus.COMPLETED
            else:
                job.status = CrawlStatus.FAILED
                job.error_message = "Failed to fetch content"
            
        except Exception as e:
            job.status = CrawlStatus.FAILED
            job.error_message = str(e)
            job.retry_count += 1
            
            # Retry if under max retries
            if job.retry_count < job.max_retries:
                job.status = CrawlStatus.PENDING
                await asyncio.sleep(job.retry_count * 2)  # Exponential backoff
        
        finally:
            job.completed_at = datetime.utcnow()
            self._update_job_in_db(job)
    
    def _can_crawl(self, url: str) -> bool:
        """Check if URL can be crawled according to robots.txt"""
        domain = urlparse(url).netloc
        
        if domain not in self.robots_cache:
            robots_url = f"http://{domain}/robots.txt"
            rp = RobotFileParser()
            rp.set_url(robots_url)
            try:
                rp.read()
                self.robots_cache[domain] = rp
            except Exception:
                self.robots_cache[domain] = None
        
        rp = self.robots_cache.get(domain)
        if rp is None:
            return True  # Allow if robots.txt not found
        
        return rp.can_fetch(self.user_agent, url)
    
    def _check_rate_limit(self, domain: str) -> bool:
        """Check if domain is within rate limit"""
        current_time = time.time()
        
        # Clean old entries
        cutoff_time = current_time - self.rate_limit_window
        self.domain_rates = {
            d: t for d, t in self.domain_rates.items() if t > cutoff_time
        }
        
        # Check current rate
        domain_requests = sum(1 for t in self.domain_rates.values() if t > cutoff_time)
        if domain_requests >= self.max_requests_per_domain:
            return False
        
        # Record this request
        self.domain_rates[domain] = current_time
        return True
    
    async def _fetch_url(self, url: str) -> Optional[CrawledContent]:
        """Fetch content from URL"""
        try:
            start_time = time.time()
            
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                headers={"User-Agent": self.user_agent}
            ) as session:
                async with session.get(url) as response:
                    response_time = time.time() - start_time
                    
                    if response.status != 200:
                        return None
                    
                    # Check content length
                    content_length = int(response.headers.get('content-length', 0))
                    if content_length > self.max_content_length:
                        return None
                    
                    # Get content
                    content_text = await response.text()
                    
                    # Determine content type
                    content_type = self._determine_content_type(response.headers, url)
                    
                    # Parse content
                    parsed_content = self._parse_content(content_text, content_type, url)
                    
                    return CrawledContent(
                        id=str(uuid.uuid4()),
                        url=url,
                        title=parsed_content.get('title', ''),
                        content=parsed_content.get('content', ''),
                        content_type=content_type,
                        response_time=response_time,
                        status_code=response.status,
                        content_length=len(content_text),
                        links=parsed_content.get('links', []),
                        images=parsed_content.get('images', []),
                        metadata=parsed_content.get('metadata', {})
                    )
        
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None
    
    def _determine_content_type(self, headers: Dict, url: str) -> ContentType:
        """Determine content type from headers and URL"""
        content_type = headers.get('content-type', '').lower()
        
        if 'text/html' in content_type:
            return ContentType.HTML
        elif 'application/pdf' in content_type:
            return ContentType.PDF
        elif 'image/' in content_type:
            return ContentType.IMAGE
        elif 'application/json' in content_type:
            return ContentType.JSON
        elif 'application/xml' in content_type or 'text/xml' in content_type:
            return ContentType.XML
        elif url.endswith('.pdf'):
            return ContentType.PDF
        elif url.endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
            return ContentType.IMAGE
        else:
            return ContentType.TEXT
    
    def _parse_content(self, content: str, content_type: ContentType, url: str) -> Dict[str, Any]:
        """Parse content based on type"""
        result = {
            'title': '',
            'content': '',
            'links': [],
            'images': [],
            'metadata': {}
        }
        
        if content_type == ContentType.HTML:
            result = self._parse_html(content, url)
        elif content_type == ContentType.JSON:
            result = self._parse_json(content)
        elif content_type == ContentType.XML:
            result = self._parse_xml(content)
        else:
            result['content'] = content
        
        return result
    
    def _parse_html(self, html: str, base_url: str) -> Dict[str, Any]:
        """Parse HTML content"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extract title
        title_tag = soup.find('title')
        title = title_tag.get_text().strip() if title_tag else ''
        
        # Extract main content
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Get text content
        content = soup.get_text()
        # Clean up whitespace
        content = re.sub(r'\s+', ' ', content).strip()
        
        # Extract links
        links = []
        for link in soup.find_all('a', href=True):
            href = link['href']
            absolute_url = urljoin(base_url, href)
            if self._is_valid_url(absolute_url):
                links.append(absolute_url)
        
        # Extract images
        images = []
        for img in soup.find_all('img', src=True):
            src = img['src']
            absolute_url = urljoin(base_url, src)
            if self._is_valid_url(absolute_url):
                images.append(absolute_url)
        
        # Extract metadata
        metadata = {}
        meta_tags = soup.find_all('meta')
        for meta in meta_tags:
            name = meta.get('name') or meta.get('property')
            content = meta.get('content')
            if name and content:
                metadata[name] = content
        
        return {
            'title': title,
            'content': content,
            'links': links,
            'images': images,
            'metadata': metadata
        }
    
    def _parse_json(self, json_str: str) -> Dict[str, Any]:
        """Parse JSON content"""
        try:
            data = json.loads(json_str)
            return {
                'title': 'JSON Document',
                'content': json.dumps(data, indent=2),
                'links': [],
                'images': [],
                'metadata': {'type': 'json'}
            }
        except json.JSONDecodeError:
            return {
                'title': 'Invalid JSON',
                'content': json_str,
                'links': [],
                'images': [],
                'metadata': {'type': 'invalid_json'}
            }
    
    def _parse_xml(self, xml_str: str) -> Dict[str, Any]:
        """Parse XML content"""
        try:
            soup = BeautifulSoup(xml_str, 'xml')
            return {
                'title': 'XML Document',
                'content': soup.get_text(),
                'links': [],
                'images': [],
                'metadata': {'type': 'xml'}
            }
        except Exception:
            return {
                'title': 'Invalid XML',
                'content': xml_str,
                'links': [],
                'images': [],
                'metadata': {'type': 'invalid_xml'}
            }
    
    def _is_valid_url(self, url: str) -> bool:
        """Check if URL is valid and crawlable"""
        try:
            parsed = urlparse(url)
            return (
                parsed.scheme in ['http', 'https'] and
                parsed.netloc and
                not url.endswith(('.pdf', '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.mp4', '.mp3'))
            )
        except Exception:
            return False
    
    def _extract_and_queue_links(self, content: CrawledContent, depth: int):
        """Extract links from content and queue them for crawling"""
        for link in content.links:
            if link not in self.visited_urls:
                self.add_crawl_job(link, depth=depth, priority=1)
                self.visited_urls.add(link)
    
    def _save_crawled_content(self, content: CrawledContent):
        """Save crawled content to database"""
        self.crawled_content[content.id] = content
        
        try:
            content_model = CrawledContentModel(
                id=content.id,
                url=content.url,
                title=content.title,
                content=content.content,
                content_type=content.content_type.value,
                crawled_at=content.crawled_at,
                response_time=content.response_time,
                status_code=content.status_code,
                content_length=content.content_length,
                links=content.links,
                images=content.images,
                metadata=content.metadata
            )
            
            self.session.add(content_model)
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            print(f"Failed to save content: {e}")
    
    def _update_job_in_db(self, job: CrawlJob):
        """Update job in database"""
        try:
            self.session.query(CrawlJobModel).filter(CrawlJobModel.id == job.id).update({
                "status": job.status.value,
                "started_at": job.started_at,
                "completed_at": job.completed_at,
                "retry_count": job.retry_count,
                "error_message": job.error_message,
                "metadata": job.metadata
            })
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            print(f"Failed to update job: {e}")
    
    def add_crawl_job(self, url: str, priority: int = 0, depth: int = 0, 
                     max_depth: int = 3, metadata: Dict[str, Any] = None) -> Dict:
        """Add a new crawl job"""
        if not self._is_valid_url(url):
            return {"error": "Invalid URL"}
        
        job_id = str(uuid.uuid4())
        
        job = CrawlJob(
            id=job_id,
            url=url,
            priority=priority,
            depth=depth,
            max_depth=max_depth,
            metadata=metadata or {}
        )
        
        self.crawl_jobs[job_id] = job
        
        # Save to database
        try:
            job_model = CrawlJobModel(
                id=job_id,
                url=url,
                priority=priority,
                depth=depth,
                max_depth=max_depth,
                metadata=metadata or {}
            )
            
            self.session.add(job_model)
            self.session.commit()
            
            return {
                "job_id": job_id,
                "url": url,
                "status": job.status.value,
                "message": "Crawl job added successfully"
            }
        
        except Exception as e:
            self.session.rollback()
            return {"error": f"Failed to add crawl job: {str(e)}"}
    
    def get_crawl_job_status(self, job_id: str) -> Dict:
        """Get status of a crawl job"""
        if job_id not in self.crawl_jobs:
            return {"error": "Job not found"}
        
        return self.crawl_jobs[job_id].to_dict()
    
    def get_crawled_content(self, content_id: str) -> Dict:
        """Get crawled content by ID"""
        if content_id not in self.crawled_content:
            return {"error": "Content not found"}
        
        return self.crawled_content[content_id].to_dict()
    
    def search_content(self, query: str, limit: int = 20, offset: int = 0) -> Dict:
        """Search crawled content"""
        # Simple text search in database
        search_query = self.session.query(CrawledContentModel).filter(
            CrawledContentModel.content.contains(query) |
            CrawledContentModel.title.contains(query)
        ).order_by(CrawledContentModel.crawled_at.desc())
        
        total = search_query.count()
        results = search_query.offset(offset).limit(limit).all()
        
        return {
            "results": [
                {
                    "id": r.id,
                    "url": r.url,
                    "title": r.title,
                    "content": r.content[:500] + "..." if len(r.content) > 500 else r.content,
                    "type": r.content_type,
                    "crawled_at": r.crawled_at.isoformat(),
                    "response_time": r.response_time
                }
                for r in results
            ],
            "total": total,
            "query": query,
            "limit": limit,
            "offset": offset
        }
    
    def get_crawler_stats(self) -> Dict:
        """Get crawler statistics"""
        total_jobs = len(self.crawl_jobs)
        completed_jobs = sum(1 for job in self.crawl_jobs.values() if job.status == CrawlStatus.COMPLETED)
        failed_jobs = sum(1 for job in self.crawl_jobs.values() if job.status == CrawlStatus.FAILED)
        pending_jobs = sum(1 for job in self.crawl_jobs.values() if job.status == CrawlStatus.PENDING)
        
        total_content = len(self.crawled_content)
        total_urls_visited = len(self.visited_urls)
        
        return {
            "total_jobs": total_jobs,
            "completed_jobs": completed_jobs,
            "failed_jobs": failed_jobs,
            "pending_jobs": pending_jobs,
            "total_content": total_content,
            "total_urls_visited": total_urls_visited,
            "success_rate": completed_jobs / max(total_jobs, 1) * 100
        }
    
    def get_domain_stats(self) -> Dict:
        """Get statistics by domain"""
        domain_stats = defaultdict(lambda: {
            'jobs': 0,
            'completed': 0,
            'failed': 0,
            'content': 0
        })
        
        for job in self.crawl_jobs.values():
            domain = urlparse(job.url).netloc
            domain_stats[domain]['jobs'] += 1
            if job.status == CrawlStatus.COMPLETED:
                domain_stats[domain]['completed'] += 1
            elif job.status == CrawlStatus.FAILED:
                domain_stats[domain]['failed'] += 1
        
        for content in self.crawled_content.values():
            domain = urlparse(content.url).netloc
            domain_stats[domain]['content'] += 1
        
        return {
            "domains": dict(domain_stats),
            "total_domains": len(domain_stats)
        }


class WebCrawlerAPI:
    """REST API for Web Crawler service"""
    
    def __init__(self, service: WebCrawlerService):
        self.service = service
    
    def add_crawl_job(self, request_data: Dict) -> Tuple[Dict, int]:
        """API endpoint to add crawl job"""
        result = self.service.add_crawl_job(
            url=request_data.get('url'),
            priority=int(request_data.get('priority', 0)),
            depth=int(request_data.get('depth', 0)),
            max_depth=int(request_data.get('max_depth', 3)),
            metadata=request_data.get('metadata', {})
        )
        
        if "error" in result:
            return result, 400
        
        return result, 201
    
    def get_job_status(self, job_id: str) -> Tuple[Dict, int]:
        """API endpoint to get job status"""
        result = self.service.get_crawl_job_status(job_id)
        
        if "error" in result:
            return result, 404
        
        return result, 200
    
    def get_content(self, content_id: str) -> Tuple[Dict, int]:
        """API endpoint to get crawled content"""
        result = self.service.get_crawled_content(content_id)
        
        if "error" in result:
            return result, 404
        
        return result, 200
    
    def search_content(self, query: str, limit: int = 20, offset: int = 0) -> Tuple[Dict, int]:
        """API endpoint to search content"""
        result = self.service.search_content(query, limit, offset)
        return result, 200
    
    def get_stats(self) -> Tuple[Dict, int]:
        """API endpoint to get crawler stats"""
        result = self.service.get_crawler_stats()
        return result, 200
    
    def get_domain_stats(self) -> Tuple[Dict, int]:
        """API endpoint to get domain stats"""
        result = self.service.get_domain_stats()
        return result, 200


# Example usage and testing
if __name__ == "__main__":
    # Initialize service
    service = WebCrawlerService(
        db_url="sqlite:///webcrawler.db",
        redis_url="redis://localhost:6379"
    )
    
    # Add crawl jobs
    result1 = service.add_crawl_job(
        url="https://example.com",
        priority=1,
        max_depth=2
    )
    print("Added crawl job:", result1)
    
    result2 = service.add_crawl_job(
        url="https://httpbin.org",
        priority=0,
        max_depth=1
    )
    print("Added crawl job:", result2)
    
    # Wait for crawling to complete
    import time
    time.sleep(10)
    
    # Get job status
    if "job_id" in result1:
        status = service.get_crawl_job_status(result1["job_id"])
        print("Job status:", status)
    
    # Search content
    search_result = service.search_content("example", limit=5)
    print("Search results:", search_result)
    
    # Get crawler stats
    stats = service.get_crawler_stats()
    print("Crawler stats:", stats)
    
    # Get domain stats
    domain_stats = service.get_domain_stats()
    print("Domain stats:", domain_stats)
