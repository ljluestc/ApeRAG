"""
Newsfeed System Implementation

A comprehensive social media newsfeed system with features:
- Post creation and management
- User following/followers
- Feed generation algorithms
- Real-time updates
- Content filtering and moderation
- Analytics and engagement tracking
- Caching and performance optimization

Author: AI Assistant
Date: 2024
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
from enum import Enum
from dataclasses import dataclass
from collections import defaultdict, deque

import redis
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy import create_engine, func

Base = declarative_base()


class PostType(Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    LINK = "link"
    POLL = "poll"


class FeedAlgorithm(Enum):
    CHRONOLOGICAL = "chronological"
    RELEVANCE = "relevance"
    ENGAGEMENT = "engagement"
    MIXED = "mixed"


@dataclass
class Post:
    """Post data structure"""
    id: str
    user_id: str
    content: str
    post_type: PostType
    created_at: datetime
    likes: int = 0
    comments: int = 0
    shares: int = 0
    is_public: bool = True
    tags: List[str] = None
    media_urls: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.media_urls is None:
            self.media_urls = []


@dataclass
class User:
    """User data structure"""
    id: str
    username: str
    display_name: str
    bio: str = ""
    followers_count: int = 0
    following_count: int = 0
    posts_count: int = 0
    is_verified: bool = False
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()


class PostModel(Base):
    """Database model for posts"""
    __tablename__ = 'posts'
    
    id = Column(String(50), primary_key=True)
    user_id = Column(String(50), nullable=False, index=True)
    content = Column(Text, nullable=False)
    post_type = Column(String(20), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    likes_count = Column(Integer, default=0)
    comments_count = Column(Integer, default=0)
    shares_count = Column(Integer, default=0)
    is_public = Column(Boolean, default=True)
    tags = Column(Text)  # JSON string
    media_urls = Column(Text)  # JSON string
    engagement_score = Column(Float, default=0.0)


class UserModel(Base):
    """Database model for users"""
    __tablename__ = 'users'
    
    id = Column(String(50), primary_key=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    display_name = Column(String(100), nullable=False)
    bio = Column(Text, default="")
    followers_count = Column(Integer, default=0)
    following_count = Column(Integer, default=0)
    posts_count = Column(Integer, default=0)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class FollowModel(Base):
    """Database model for user follows"""
    __tablename__ = 'follows'
    
    id = Column(Integer, primary_key=True)
    follower_id = Column(String(50), nullable=False, index=True)
    following_id = Column(String(50), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        {'extend_existing': True}
    )


class LikeModel(Base):
    """Database model for post likes"""
    __tablename__ = 'likes'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String(50), nullable=False, index=True)
    post_id = Column(String(50), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        {'extend_existing': True}
    )


class NewsfeedService:
    """Main newsfeed service class"""
    
    def __init__(self, db_url: str, redis_url: str = "redis://localhost:6379"):
        self.db_url = db_url
        self.redis_url = redis_url
        self.redis_client = redis.from_url(redis_url)
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        
        # Configuration
        self.feed_cache_ttl = 300  # 5 minutes
        self.max_feed_size = 100
        self.engagement_decay_factor = 0.95
        self.relevance_weights = {
            'recency': 0.3,
            'engagement': 0.4,
            'user_affinity': 0.3
        }
    
    def _get_feed_cache_key(self, user_id: str, algorithm: FeedAlgorithm) -> str:
        """Get Redis cache key for user feed"""
        return f"newsfeed:{user_id}:{algorithm.value}"
    
    def _get_user_cache_key(self, user_id: str) -> str:
        """Get Redis cache key for user data"""
        return f"user:{user_id}"
    
    def _calculate_engagement_score(self, post: Post) -> float:
        """Calculate engagement score for a post"""
        # Weighted engagement score
        score = (
            post.likes * 1.0 +
            post.comments * 2.0 +
            post.shares * 3.0
        )
        
        # Apply time decay
        hours_old = (datetime.utcnow() - post.created_at).total_seconds() / 3600
        decay_factor = self.engagement_decay_factor ** hours_old
        
        return score * decay_factor
    
    def _calculate_relevance_score(self, post: Post, user_id: str) -> float:
        """Calculate relevance score for a post based on user preferences"""
        # This is a simplified version - in practice, you'd use ML models
        base_score = 1.0
        
        # Check if user follows the post author
        is_following = self._is_user_following(user_id, post.user_id)
        if is_following:
            base_score *= 1.5
        
        # Check for common tags/interests
        user_interests = self._get_user_interests(user_id)
        common_tags = set(post.tags) & set(user_interests)
        if common_tags:
            base_score *= (1 + len(common_tags) * 0.2)
        
        return base_score
    
    def _is_user_following(self, follower_id: str, following_id: str) -> bool:
        """Check if user is following another user"""
        follow = self.session.query(FollowModel).filter(
            FollowModel.follower_id == follower_id,
            FollowModel.following_id == following_id
        ).first()
        return follow is not None
    
    def _get_user_interests(self, user_id: str) -> List[str]:
        """Get user interests based on their activity"""
        # Simplified - in practice, you'd analyze user's liked posts, etc.
        return ["technology", "programming", "ai"]
    
    def create_post(self, user_id: str, content: str, post_type: PostType = PostType.TEXT,
                   tags: List[str] = None, media_urls: List[str] = None,
                   is_public: bool = True) -> Dict:
        """Create a new post"""
        if not content.strip():
            return {"error": "Content cannot be empty"}
        
        post_id = f"post_{int(time.time() * 1000)}_{user_id}"
        
        post = PostModel(
            id=post_id,
            user_id=user_id,
            content=content,
            post_type=post_type.value,
            tags=json.dumps(tags or []),
            media_urls=json.dumps(media_urls or []),
            is_public=is_public
        )
        
        try:
            self.session.add(post)
            
            # Update user's post count
            user = self.session.query(UserModel).filter(UserModel.id == user_id).first()
            if user:
                user.posts_count += 1
            
            self.session.commit()
            
            # Invalidate user's feed cache
            self._invalidate_user_feed_cache(user_id)
            
            return {
                "post_id": post_id,
                "user_id": user_id,
                "content": content,
                "post_type": post_type.value,
                "created_at": post.created_at.isoformat(),
                "tags": tags or [],
                "media_urls": media_urls or []
            }
        
        except Exception as e:
            self.session.rollback()
            return {"error": f"Failed to create post: {str(e)}"}
    
    def get_user_feed(self, user_id: str, algorithm: FeedAlgorithm = FeedAlgorithm.MIXED,
                     limit: int = 20, offset: int = 0) -> Dict:
        """Get user's personalized newsfeed"""
        # Check cache first
        cache_key = self._get_feed_cache_key(user_id, algorithm)
        cached_feed = self.redis_client.get(cache_key)
        
        if cached_feed:
            try:
                feed_data = json.loads(cached_feed)
                return {
                    "posts": feed_data[offset:offset + limit],
                    "total": len(feed_data),
                    "algorithm": algorithm.value,
                    "cached": True
                }
            except Exception:
                pass  # Fall back to database
        
        # Get following users
        following_users = self.session.query(FollowModel.following_id).filter(
            FollowModel.follower_id == user_id
        ).all()
        following_ids = [f[0] for f in following_users]
        
        # Add self to see own posts
        following_ids.append(user_id)
        
        # Get posts from following users
        query = self.session.query(PostModel).filter(
            PostModel.user_id.in_(following_ids),
            PostModel.is_public == True
        ).order_by(PostModel.created_at.desc())
        
        posts = query.limit(1000).all()  # Get more than needed for ranking
        
        # Convert to Post objects and calculate scores
        post_objects = []
        for post in posts:
            post_obj = Post(
                id=post.id,
                user_id=post.user_id,
                content=post.content,
                post_type=PostType(post.post_type),
                created_at=post.created_at,
                likes=post.likes_count,
                comments=post.comments_count,
                shares=post.shares_count,
                is_public=post.is_public,
                tags=json.loads(post.tags or "[]"),
                media_urls=json.loads(post.media_urls or "[]")
            )
            
            # Calculate scores based on algorithm
            if algorithm == FeedAlgorithm.CHRONOLOGICAL:
                score = post.created_at.timestamp()
            elif algorithm == FeedAlgorithm.ENGAGEMENT:
                score = self._calculate_engagement_score(post_obj)
            elif algorithm == FeedAlgorithm.RELEVANCE:
                score = self._calculate_relevance_score(post_obj, user_id)
            else:  # MIXED
                engagement_score = self._calculate_engagement_score(post_obj)
                relevance_score = self._calculate_relevance_score(post_obj, user_id)
                recency_score = 1.0 / (1.0 + (datetime.utcnow() - post.created_at).total_seconds() / 3600)
                
                score = (
                    self.relevance_weights['recency'] * recency_score +
                    self.relevance_weights['engagement'] * engagement_score +
                    self.relevance_weights['user_affinity'] * relevance_score
                )
            
            post_objects.append((score, post_obj))
        
        # Sort by score
        post_objects.sort(key=lambda x: x[0], reverse=True)
        
        # Extract posts and format for response
        feed_posts = []
        for score, post in post_objects:
            feed_posts.append({
                "id": post.id,
                "user_id": post.user_id,
                "content": post.content,
                "post_type": post.post_type.value,
                "created_at": post.created_at.isoformat(),
                "likes": post.likes,
                "comments": post.comments,
                "shares": post.shares,
                "tags": post.tags,
                "media_urls": post.media_urls,
                "score": score
            })
        
        # Cache the full feed
        self.redis_client.setex(cache_key, self.feed_cache_ttl, json.dumps(feed_posts))
        
        return {
            "posts": feed_posts[offset:offset + limit],
            "total": len(feed_posts),
            "algorithm": algorithm.value,
            "cached": False
        }
    
    def follow_user(self, follower_id: str, following_id: str) -> Dict:
        """Follow a user"""
        if follower_id == following_id:
            return {"error": "Cannot follow yourself"}
        
        # Check if already following
        existing = self.session.query(FollowModel).filter(
            FollowModel.follower_id == follower_id,
            FollowModel.following_id == following_id
        ).first()
        
        if existing:
            return {"error": "Already following this user"}
        
        # Create follow relationship
        follow = FollowModel(
            follower_id=follower_id,
            following_id=following_id
        )
        
        try:
            self.session.add(follow)
            
            # Update follower counts
            follower = self.session.query(UserModel).filter(UserModel.id == follower_id).first()
            following = self.session.query(UserModel).filter(UserModel.id == following_id).first()
            
            if follower:
                follower.following_count += 1
            if following:
                following.followers_count += 1
            
            self.session.commit()
            
            # Invalidate follower's feed cache
            self._invalidate_user_feed_cache(follower_id)
            
            return {"message": "Successfully followed user"}
        
        except Exception as e:
            self.session.rollback()
            return {"error": f"Failed to follow user: {str(e)}"}
    
    def unfollow_user(self, follower_id: str, following_id: str) -> Dict:
        """Unfollow a user"""
        follow = self.session.query(FollowModel).filter(
            FollowModel.follower_id == follower_id,
            FollowModel.following_id == following_id
        ).first()
        
        if not follow:
            return {"error": "Not following this user"}
        
        try:
            self.session.delete(follow)
            
            # Update follower counts
            follower = self.session.query(UserModel).filter(UserModel.id == follower_id).first()
            following = self.session.query(UserModel).filter(UserModel.id == following_id).first()
            
            if follower:
                follower.following_count -= 1
            if following:
                following.followers_count -= 1
            
            self.session.commit()
            
            # Invalidate follower's feed cache
            self._invalidate_user_feed_cache(follower_id)
            
            return {"message": "Successfully unfollowed user"}
        
        except Exception as e:
            self.session.rollback()
            return {"error": f"Failed to unfollow user: {str(e)}"}
    
    def like_post(self, user_id: str, post_id: str) -> Dict:
        """Like a post"""
        # Check if already liked
        existing = self.session.query(LikeModel).filter(
            LikeModel.user_id == user_id,
            LikeModel.post_id == post_id
        ).first()
        
        if existing:
            return {"error": "Already liked this post"}
        
        # Create like
        like = LikeModel(user_id=user_id, post_id=post_id)
        
        try:
            self.session.add(like)
            
            # Update post like count
            post = self.session.query(PostModel).filter(PostModel.id == post_id).first()
            if post:
                post.likes_count += 1
                # Update engagement score
                post.engagement_score = self._calculate_engagement_score(
                    Post(
                        id=post.id,
                        user_id=post.user_id,
                        content=post.content,
                        post_type=PostType(post.post_type),
                        created_at=post.created_at,
                        likes=post.likes_count,
                        comments=post.comments_count,
                        shares=post.shares_count,
                        is_public=post.is_public,
                        tags=json.loads(post.tags or "[]"),
                        media_urls=json.loads(post.media_urls or "[]")
                    )
                )
            
            self.session.commit()
            
            return {"message": "Post liked successfully"}
        
        except Exception as e:
            self.session.rollback()
            return {"error": f"Failed to like post: {str(e)}"}
    
    def unlike_post(self, user_id: str, post_id: str) -> Dict:
        """Unlike a post"""
        like = self.session.query(LikeModel).filter(
            LikeModel.user_id == user_id,
            LikeModel.post_id == post_id
        ).first()
        
        if not like:
            return {"error": "Post not liked"}
        
        try:
            self.session.delete(like)
            
            # Update post like count
            post = self.session.query(PostModel).filter(PostModel.id == post_id).first()
            if post:
                post.likes_count -= 1
                # Update engagement score
                post.engagement_score = self._calculate_engagement_score(
                    Post(
                        id=post.id,
                        user_id=post.user_id,
                        content=post.content,
                        post_type=PostType(post.post_type),
                        created_at=post.created_at,
                        likes=post.likes_count,
                        comments=post.comments_count,
                        shares=post.shares_count,
                        is_public=post.is_public,
                        tags=json.loads(post.tags or "[]"),
                        media_urls=json.loads(post.media_urls or "[]")
                    )
                )
            
            self.session.commit()
            
            return {"message": "Post unliked successfully"}
        
        except Exception as e:
            self.session.rollback()
            return {"error": f"Failed to unlike post: {str(e)}"}
    
    def get_user_posts(self, user_id: str, limit: int = 20, offset: int = 0) -> Dict:
        """Get posts by a specific user"""
        query = self.session.query(PostModel).filter(
            PostModel.user_id == user_id,
            PostModel.is_public == True
        ).order_by(PostModel.created_at.desc())
        
        total = query.count()
        posts = query.offset(offset).limit(limit).all()
        
        return {
            "posts": [
                {
                    "id": post.id,
                    "user_id": post.user_id,
                    "content": post.content,
                    "post_type": post.post_type,
                    "created_at": post.created_at.isoformat(),
                    "likes": post.likes_count,
                    "comments": post.comments_count,
                    "shares": post.shares_count,
                    "tags": json.loads(post.tags or "[]"),
                    "media_urls": json.loads(post.media_urls or "[]")
                }
                for post in posts
            ],
            "total": total,
            "limit": limit,
            "offset": offset
        }
    
    def search_posts(self, query: str, limit: int = 20, offset: int = 0) -> Dict:
        """Search posts by content"""
        search_query = self.session.query(PostModel).filter(
            PostModel.content.contains(query),
            PostModel.is_public == True
        ).order_by(PostModel.created_at.desc())
        
        total = search_query.count()
        posts = search_query.offset(offset).limit(limit).all()
        
        return {
            "posts": [
                {
                    "id": post.id,
                    "user_id": post.user_id,
                    "content": post.content,
                    "post_type": post.post_type,
                    "created_at": post.created_at.isoformat(),
                    "likes": post.likes_count,
                    "comments": post.comments_count,
                    "shares": post.shares_count,
                    "tags": json.loads(post.tags or "[]"),
                    "media_urls": json.loads(post.media_urls or "[]")
                }
                for post in posts
            ],
            "total": total,
            "query": query,
            "limit": limit,
            "offset": offset
        }
    
    def get_trending_posts(self, limit: int = 20) -> Dict:
        """Get trending posts based on recent engagement"""
        # Get posts from last 24 hours with high engagement
        since = datetime.utcnow() - timedelta(hours=24)
        
        query = self.session.query(PostModel).filter(
            PostModel.created_at >= since,
            PostModel.is_public == True
        ).order_by(PostModel.engagement_score.desc())
        
        posts = query.limit(limit).all()
        
        return {
            "posts": [
                {
                    "id": post.id,
                    "user_id": post.user_id,
                    "content": post.content,
                    "post_type": post.post_type,
                    "created_at": post.created_at.isoformat(),
                    "likes": post.likes_count,
                    "comments": post.comments_count,
                    "shares": post.shares_count,
                    "engagement_score": post.engagement_score,
                    "tags": json.loads(post.tags or "[]"),
                    "media_urls": json.loads(post.media_urls or "[]")
                }
                for post in posts
            ],
            "total": len(posts)
        }
    
    def _invalidate_user_feed_cache(self, user_id: str):
        """Invalidate user's feed cache"""
        for algorithm in FeedAlgorithm:
            cache_key = self._get_feed_cache_key(user_id, algorithm)
            self.redis_client.delete(cache_key)
    
    def get_analytics(self, user_id: str) -> Dict:
        """Get user analytics"""
        user = self.session.query(UserModel).filter(UserModel.id == user_id).first()
        if not user:
            return {"error": "User not found"}
        
        # Get user's posts
        posts = self.session.query(PostModel).filter(PostModel.user_id == user_id).all()
        
        total_likes = sum(post.likes_count for post in posts)
        total_comments = sum(post.comments_count for post in posts)
        total_shares = sum(post.shares_count for post in posts)
        
        # Get most engaging posts
        top_posts = sorted(posts, key=lambda x: x.engagement_score, reverse=True)[:5]
        
        return {
            "user_id": user_id,
            "followers_count": user.followers_count,
            "following_count": user.following_count,
            "posts_count": user.posts_count,
            "total_likes": total_likes,
            "total_comments": total_comments,
            "total_shares": total_shares,
            "average_engagement": (total_likes + total_comments + total_shares) / max(len(posts), 1),
            "top_posts": [
                {
                    "id": post.id,
                    "content": post.content[:100] + "..." if len(post.content) > 100 else post.content,
                    "engagement_score": post.engagement_score
                }
                for post in top_posts
            ]
        }


class NewsfeedAPI:
    """REST API for Newsfeed service"""
    
    def __init__(self, service: NewsfeedService):
        self.service = service
    
    def create_post(self, request_data: Dict) -> Tuple[Dict, int]:
        """API endpoint to create a post"""
        user_id = request_data.get('user_id')
        content = request_data.get('content')
        post_type = request_data.get('post_type', 'text')
        tags = request_data.get('tags', [])
        media_urls = request_data.get('media_urls', [])
        is_public = request_data.get('is_public', True)
        
        if not user_id or not content:
            return {"error": "User ID and content are required"}, 400
        
        try:
            post_type_enum = PostType(post_type)
        except ValueError:
            return {"error": "Invalid post type"}, 400
        
        result = self.service.create_post(
            user_id=user_id,
            content=content,
            post_type=post_type_enum,
            tags=tags,
            media_urls=media_urls,
            is_public=is_public
        )
        
        if "error" in result:
            return result, 400
        
        return result, 201
    
    def get_feed(self, user_id: str, algorithm: str = "mixed", 
                 limit: int = 20, offset: int = 0) -> Tuple[Dict, int]:
        """API endpoint to get user feed"""
        try:
            algorithm_enum = FeedAlgorithm(algorithm)
        except ValueError:
            return {"error": "Invalid algorithm"}, 400
        
        result = self.service.get_user_feed(
            user_id=user_id,
            algorithm=algorithm_enum,
            limit=limit,
            offset=offset
        )
        
        return result, 200
    
    def follow_user(self, request_data: Dict) -> Tuple[Dict, int]:
        """API endpoint to follow a user"""
        follower_id = request_data.get('follower_id')
        following_id = request_data.get('following_id')
        
        if not follower_id or not following_id:
            return {"error": "Follower ID and following ID are required"}, 400
        
        result = self.service.follow_user(follower_id, following_id)
        
        if "error" in result:
            return result, 400
        
        return result, 200
    
    def like_post(self, request_data: Dict) -> Tuple[Dict, int]:
        """API endpoint to like a post"""
        user_id = request_data.get('user_id')
        post_id = request_data.get('post_id')
        
        if not user_id or not post_id:
            return {"error": "User ID and post ID are required"}, 400
        
        result = self.service.like_post(user_id, post_id)
        
        if "error" in result:
            return result, 400
        
        return result, 200
    
    def search_posts(self, query: str, limit: int = 20, offset: int = 0) -> Tuple[Dict, int]:
        """API endpoint to search posts"""
        if not query:
            return {"error": "Search query is required"}, 400
        
        result = self.service.search_posts(query, limit, offset)
        return result, 200
    
    def get_trending(self, limit: int = 20) -> Tuple[Dict, int]:
        """API endpoint to get trending posts"""
        result = self.service.get_trending_posts(limit)
        return result, 200


# Example usage and testing
if __name__ == "__main__":
    # Initialize service
    service = NewsfeedService(
        db_url="sqlite:///newsfeed.db",
        redis_url="redis://localhost:6379"
    )
    
    # Test creating posts
    result1 = service.create_post(
        user_id="user1",
        content="Hello world! This is my first post.",
        post_type=PostType.TEXT,
        tags=["hello", "first_post"]
    )
    print("Created post:", result1)
    
    result2 = service.create_post(
        user_id="user2",
        content="Check out this amazing photo!",
        post_type=PostType.IMAGE,
        media_urls=["https://example.com/photo.jpg"],
        tags=["photo", "amazing"]
    )
    print("Created image post:", result2)
    
    # Test following
    follow_result = service.follow_user("user1", "user2")
    print("Follow result:", follow_result)
    
    # Test getting feed
    feed = service.get_user_feed("user1", FeedAlgorithm.MIXED, limit=10)
    print("User feed:", feed)
    
    # Test liking posts
    if "post_id" in result2:
        like_result = service.like_post("user1", result2["post_id"])
        print("Like result:", like_result)
    
    # Test search
    search_result = service.search_posts("amazing", limit=5)
    print("Search results:", search_result)
    
    # Test trending
    trending = service.get_trending_posts(limit=5)
    print("Trending posts:", trending)
    
    # Test analytics
    analytics = service.get_analytics("user1")
    print("User analytics:", analytics)
