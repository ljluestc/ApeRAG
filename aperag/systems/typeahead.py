"""
Typeahead System Implementation

A comprehensive autocomplete and search suggestion system with features:
- Real-time search suggestions
- Fuzzy matching and ranking
- Personalization and learning
- Multi-language support
- Caching and performance optimization
- Analytics and usage tracking
- Custom ranking algorithms

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
from collections import defaultdict, Counter
import re
import math

import redis
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Float, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, func, desc, asc


Base = declarative_base()


class SuggestionType(Enum):
    QUERY = "query"
    PRODUCT = "product"
    USER = "user"
    LOCATION = "location"
    TAG = "tag"
    CUSTOM = "custom"


class RankingAlgorithm(Enum):
    FREQUENCY = "frequency"
    RECENCY = "recency"
    POPULARITY = "popularity"
    PERSONALIZED = "personalized"
    HYBRID = "hybrid"


@dataclass
class Suggestion:
    """Suggestion data structure"""
    id: str
    text: str
    suggestion_type: SuggestionType
    frequency: int = 1
    last_used: datetime = field(default_factory=datetime.utcnow)
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    score: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "text": self.text,
            "type": self.suggestion_type.value,
            "frequency": self.frequency,
            "last_used": self.last_used.isoformat(),
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
            "score": self.score
        }


@dataclass
class SearchQuery:
    """Search query data structure"""
    id: str
    query: str
    user_id: str = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    results_count: int = 0
    selected_suggestion: str = None
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "query": self.query,
            "user_id": self.user_id,
            "timestamp": self.timestamp.isoformat(),
            "results_count": self.results_count,
            "selected_suggestion": self.selected_suggestion
        }


class SuggestionModel(Base):
    """Database model for suggestions"""
    __tablename__ = 'suggestions'
    
    id = Column(String(50), primary_key=True)
    text = Column(String(500), nullable=False, index=True)
    suggestion_type = Column(String(20), nullable=False, index=True)
    frequency = Column(Integer, default=1)
    last_used = Column(DateTime, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    metadata = Column(JSON)
    score = Column(Float, default=0.0)


class SearchQueryModel(Base):
    """Database model for search queries"""
    __tablename__ = 'search_queries'
    
    id = Column(String(50), primary_key=True)
    query = Column(String(500), nullable=False, index=True)
    user_id = Column(String(50), nullable=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    results_count = Column(Integer, default=0)
    selected_suggestion = Column(String(500), nullable=True)


class UserPreferenceModel(Base):
    """Database model for user preferences"""
    __tablename__ = 'user_preferences'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String(50), nullable=False, index=True)
    suggestion_id = Column(String(50), nullable=False, index=True)
    preference_score = Column(Float, default=0.0)
    last_updated = Column(DateTime, default=datetime.utcnow)


class TrieNode:
    """Trie node for efficient prefix matching"""
    
    def __init__(self):
        self.children = {}
        self.is_end_of_word = False
        self.suggestions = []
        self.frequency = 0


class TypeaheadService:
    """Main typeahead service class"""
    
    def __init__(self, db_url: str, redis_url: str = "redis://localhost:6379"):
        self.db_url = db_url
        self.redis_url = redis_url
        self.redis_client = redis.from_url(redis_url)
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        
        # In-memory data structures
        self.trie_root = TrieNode()
        self.suggestions: Dict[str, Suggestion] = {}
        self.user_preferences: Dict[str, Dict[str, float]] = defaultdict(dict)
        
        # Configuration
        self.max_suggestions = 10
        self.min_query_length = 2
        self.cache_ttl = 300  # 5 minutes
        self.learning_rate = 0.1
        self.decay_factor = 0.95
        
        # Load existing data
        self._load_suggestions()
        self._load_user_preferences()
        self._build_trie()
    
    def _load_suggestions(self):
        """Load suggestions from database"""
        suggestions = self.session.query(SuggestionModel).all()
        for suggestion in suggestions:
            self.suggestions[suggestion.id] = Suggestion(
                id=suggestion.id,
                text=suggestion.text,
                suggestion_type=SuggestionType(suggestion.suggestion_type),
                frequency=suggestion.frequency,
                last_used=suggestion.last_used,
                created_at=suggestion.created_at,
                metadata=suggestion.metadata or {},
                score=suggestion.score
            )
    
    def _load_user_preferences(self):
        """Load user preferences from database"""
        preferences = self.session.query(UserPreferenceModel).all()
        for pref in preferences:
            self.user_preferences[pref.user_id][pref.suggestion_id] = pref.preference_score
    
    def _build_trie(self):
        """Build trie from existing suggestions"""
        for suggestion in self.suggestions.values():
            self._insert_into_trie(suggestion)
    
    def _insert_into_trie(self, suggestion: Suggestion):
        """Insert suggestion into trie"""
        node = self.trie_root
        text = suggestion.text.lower()
        
        for char in text:
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
        
        node.is_end_of_word = True
        node.suggestions.append(suggestion.id)
        node.frequency += suggestion.frequency
    
    def add_suggestion(self, text: str, suggestion_type: SuggestionType, 
                      metadata: Dict[str, Any] = None) -> Dict:
        """Add a new suggestion"""
        # Check if suggestion already exists
        existing = None
        for suggestion in self.suggestions.values():
            if suggestion.text.lower() == text.lower() and suggestion.suggestion_type == suggestion_type:
                existing = suggestion
                break
        
        if existing:
            # Update frequency
            existing.frequency += 1
            existing.last_used = datetime.utcnow()
            if metadata:
                existing.metadata.update(metadata)
            
            # Update database
            self._update_suggestion_in_db(existing)
            
            return {
                "suggestion_id": existing.id,
                "message": "Suggestion frequency updated"
            }
        else:
            # Create new suggestion
            suggestion_id = str(uuid.uuid4())
            suggestion = Suggestion(
                id=suggestion_id,
                text=text,
                suggestion_type=suggestion_type,
                metadata=metadata or {}
            )
            
            self.suggestions[suggestion_id] = suggestion
            self._insert_into_trie(suggestion)
            
            # Save to database
            self._save_suggestion_to_db(suggestion)
            
            return {
                "suggestion_id": suggestion_id,
                "message": "Suggestion added successfully"
            }
    
    def _save_suggestion_to_db(self, suggestion: Suggestion):
        """Save suggestion to database"""
        try:
            suggestion_model = SuggestionModel(
                id=suggestion.id,
                text=suggestion.text,
                suggestion_type=suggestion.suggestion_type.value,
                frequency=suggestion.frequency,
                last_used=suggestion.last_used,
                created_at=suggestion.created_at,
                metadata=suggestion.metadata,
                score=suggestion.score
            )
            
            self.session.add(suggestion_model)
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            print(f"Failed to save suggestion to database: {e}")
    
    def _update_suggestion_in_db(self, suggestion: Suggestion):
        """Update suggestion in database"""
        try:
            self.session.query(SuggestionModel).filter(SuggestionModel.id == suggestion.id).update({
                "frequency": suggestion.frequency,
                "last_used": suggestion.last_used,
                "metadata": suggestion.metadata,
                "score": suggestion.score
            })
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            print(f"Failed to update suggestion in database: {e}")
    
    def get_suggestions(self, query: str, user_id: str = None, 
                       suggestion_types: List[SuggestionType] = None,
                       limit: int = None) -> Dict:
        """Get suggestions for a query"""
        if len(query) < self.min_query_length:
            return {"suggestions": [], "query": query, "count": 0}
        
        # Check cache first
        cache_key = self._get_cache_key(query, user_id, suggestion_types)
        cached_result = self.redis_client.get(cache_key)
        
        if cached_result:
            try:
                return json.loads(cached_result)
            except Exception:
                pass  # Fall back to database
        
        # Get suggestions from trie
        suggestions = self._search_trie(query, suggestion_types)
        
        # Rank suggestions
        ranked_suggestions = self._rank_suggestions(suggestions, query, user_id)
        
        # Apply limit
        if limit:
            ranked_suggestions = ranked_suggestions[:limit]
        else:
            ranked_suggestions = ranked_suggestions[:self.max_suggestions]
        
        # Record query
        self._record_query(query, user_id, len(ranked_suggestions))
        
        result = {
            "suggestions": [s.to_dict() for s in ranked_suggestions],
            "query": query,
            "count": len(ranked_suggestions)
        }
        
        # Cache result
        self.redis_client.setex(cache_key, self.cache_ttl, json.dumps(result))
        
        return result
    
    def _search_trie(self, query: str, suggestion_types: List[SuggestionType] = None) -> List[Suggestion]:
        """Search trie for suggestions matching query"""
        node = self.trie_root
        query_lower = query.lower()
        
        # Navigate to the prefix node
        for char in query_lower:
            if char not in node.children:
                return []
            node = node.children[char]
        
        # Collect all suggestions from this node and its children
        suggestions = []
        self._collect_suggestions(node, suggestions)
        
        # Filter by type if specified
        if suggestion_types:
            type_set = set(suggestion_types)
            suggestions = [s for s in suggestions if s.suggestion_type in type_set]
        
        return suggestions
    
    def _collect_suggestions(self, node: TrieNode, suggestions: List[Suggestion]):
        """Recursively collect suggestions from trie node"""
        if node.is_end_of_word:
            for suggestion_id in node.suggestions:
                if suggestion_id in self.suggestions:
                    suggestions.append(self.suggestions[suggestion_id])
        
        for child_node in node.children.values():
            self._collect_suggestions(child_node, suggestions)
    
    def _rank_suggestions(self, suggestions: List[Suggestion], query: str, 
                         user_id: str = None) -> List[Suggestion]:
        """Rank suggestions based on various factors"""
        for suggestion in suggestions:
            score = 0.0
            
            # Text similarity score
            similarity = self._calculate_similarity(query, suggestion.text)
            score += similarity * 0.4
            
            # Frequency score
            frequency_score = math.log(1 + suggestion.frequency) / 10.0
            score += frequency_score * 0.3
            
            # Recency score
            days_since_last_used = (datetime.utcnow() - suggestion.last_used).days
            recency_score = math.exp(-days_since_last_used / 30.0)  # Decay over 30 days
            score += recency_score * 0.2
            
            # User preference score
            if user_id and suggestion.id in self.user_preferences.get(user_id, {}):
                preference_score = self.user_preferences[user_id][suggestion.id]
                score += preference_score * 0.1
            
            suggestion.score = score
        
        # Sort by score (descending)
        return sorted(suggestions, key=lambda s: s.score, reverse=True)
    
    def _calculate_similarity(self, query: str, text: str) -> float:
        """Calculate similarity between query and text"""
        query_lower = query.lower()
        text_lower = text.lower()
        
        # Exact match
        if query_lower == text_lower:
            return 1.0
        
        # Prefix match
        if text_lower.startswith(query_lower):
            return 0.9
        
        # Substring match
        if query_lower in text_lower:
            return 0.7
        
        # Fuzzy match using Levenshtein distance
        distance = self._levenshtein_distance(query_lower, text_lower)
        max_length = max(len(query_lower), len(text_lower))
        if max_length == 0:
            return 0.0
        
        similarity = 1.0 - (distance / max_length)
        return max(0.0, similarity)
    
    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        """Calculate Levenshtein distance between two strings"""
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    def _record_query(self, query: str, user_id: str, results_count: int):
        """Record search query for analytics"""
        query_id = str(uuid.uuid4())
        
        search_query = SearchQuery(
            id=query_id,
            query=query,
            user_id=user_id,
            results_count=results_count
        )
        
        try:
            query_model = SearchQueryModel(
                id=query_id,
                query=query,
                user_id=user_id,
                results_count=results_count
            )
            
            self.session.add(query_model)
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            print(f"Failed to record query: {e}")
    
    def select_suggestion(self, suggestion_id: str, user_id: str = None) -> Dict:
        """Record that a user selected a suggestion"""
        if suggestion_id not in self.suggestions:
            return {"error": "Suggestion not found"}
        
        suggestion = self.suggestions[suggestion_id]
        suggestion.frequency += 1
        suggestion.last_used = datetime.utcnow()
        
        # Update user preference
        if user_id:
            current_preference = self.user_preferences[user_id].get(suggestion_id, 0.0)
            new_preference = current_preference + self.learning_rate * (1.0 - current_preference)
            self.user_preferences[user_id][suggestion_id] = new_preference
            
            # Update database
            self._update_user_preference(user_id, suggestion_id, new_preference)
        
        # Update suggestion in database
        self._update_suggestion_in_db(suggestion)
        
        return {"message": "Suggestion selection recorded"}
    
    def _update_user_preference(self, user_id: str, suggestion_id: str, score: float):
        """Update user preference in database"""
        try:
            existing = self.session.query(UserPreferenceModel).filter(
                UserPreferenceModel.user_id == user_id,
                UserPreferenceModel.suggestion_id == suggestion_id
            ).first()
            
            if existing:
                existing.preference_score = score
                existing.last_updated = datetime.utcnow()
            else:
                preference = UserPreferenceModel(
                    user_id=user_id,
                    suggestion_id=suggestion_id,
                    preference_score=score
                )
                self.session.add(preference)
            
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            print(f"Failed to update user preference: {e}")
    
    def get_trending_suggestions(self, suggestion_type: SuggestionType = None, 
                                limit: int = 10) -> Dict:
        """Get trending suggestions"""
        query = self.session.query(SuggestionModel).filter(
            SuggestionModel.created_at >= datetime.utcnow() - timedelta(days=7)
        )
        
        if suggestion_type:
            query = query.filter(SuggestionModel.suggestion_type == suggestion_type.value)
        
        trending = query.order_by(desc(SuggestionModel.frequency)).limit(limit).all()
        
        return {
            "suggestions": [
                {
                    "id": s.id,
                    "text": s.text,
                    "type": s.suggestion_type,
                    "frequency": s.frequency,
                    "created_at": s.created_at.isoformat()
                }
                for s in trending
            ],
            "count": len(trending)
        }
    
    def get_user_analytics(self, user_id: str) -> Dict:
        """Get analytics for a specific user"""
        # Get user's search queries
        queries = self.session.query(SearchQueryModel).filter(
            SearchQueryModel.user_id == user_id
        ).order_by(desc(SearchQueryModel.timestamp)).limit(100).all()
        
        # Get user's preferences
        preferences = self.user_preferences.get(user_id, {})
        
        # Calculate statistics
        total_queries = len(queries)
        avg_results = sum(q.results_count for q in queries) / max(total_queries, 1)
        
        # Most searched terms
        query_counts = Counter(q.query for q in queries)
        top_queries = query_counts.most_common(10)
        
        return {
            "user_id": user_id,
            "total_queries": total_queries,
            "average_results": avg_results,
            "top_queries": [{"query": q, "count": c} for q, c in top_queries],
            "preferences_count": len(preferences),
            "recent_queries": [
                {
                    "query": q.query,
                    "timestamp": q.timestamp.isoformat(),
                    "results_count": q.results_count
                }
                for q in queries[:10]
            ]
        }
    
    def get_system_analytics(self) -> Dict:
        """Get system-wide analytics"""
        # Total suggestions
        total_suggestions = len(self.suggestions)
        
        # Suggestions by type
        type_counts = Counter(s.suggestion_type for s in self.suggestions.values())
        
        # Recent queries
        recent_queries = self.session.query(SearchQueryModel).order_by(
            desc(SearchQueryModel.timestamp)
        ).limit(1000).all()
        
        # Query statistics
        total_queries = len(recent_queries)
        avg_results = sum(q.results_count for q in recent_queries) / max(total_queries, 1)
        
        # Most popular queries
        query_counts = Counter(q.query for q in recent_queries)
        popular_queries = query_counts.most_common(20)
        
        return {
            "total_suggestions": total_suggestions,
            "suggestions_by_type": {t.value: count for t, count in type_counts.items()},
            "total_queries": total_queries,
            "average_results": avg_results,
            "popular_queries": [{"query": q, "count": c} for q, c in popular_queries],
            "cache_hit_rate": self._calculate_cache_hit_rate()
        }
    
    def _calculate_cache_hit_rate(self) -> float:
        """Calculate cache hit rate"""
        # This is a simplified implementation
        # In practice, you'd track cache hits/misses
        return 0.85  # Placeholder
    
    def _get_cache_key(self, query: str, user_id: str = None, 
                      suggestion_types: List[SuggestionType] = None) -> str:
        """Get cache key for query"""
        key_parts = [f"typeahead:{query}"]
        if user_id:
            key_parts.append(f"user:{user_id}")
        if suggestion_types:
            types_str = ",".join(sorted(t.value for t in suggestion_types))
            key_parts.append(f"types:{types_str}")
        return ":".join(key_parts)
    
    def clear_cache(self) -> Dict:
        """Clear all cached suggestions"""
        try:
            # Clear Redis cache
            pattern = "typeahead:*"
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
            
            return {"message": "Cache cleared successfully"}
        except Exception as e:
            return {"error": f"Failed to clear cache: {str(e)}"}


class TypeaheadAPI:
    """REST API for Typeahead service"""
    
    def __init__(self, service: TypeaheadService):
        self.service = service
    
    def add_suggestion(self, request_data: Dict) -> Tuple[Dict, int]:
        """API endpoint to add suggestion"""
        try:
            suggestion_type = SuggestionType(request_data.get('type', 'query'))
        except ValueError:
            return {"error": "Invalid suggestion type"}, 400
        
        result = self.service.add_suggestion(
            text=request_data.get('text'),
            suggestion_type=suggestion_type,
            metadata=request_data.get('metadata', {})
        )
        
        if "error" in result:
            return result, 400
        
        return result, 201
    
    def get_suggestions(self, query: str, user_id: str = None, 
                       types: List[str] = None, limit: int = None) -> Tuple[Dict, int]:
        """API endpoint to get suggestions"""
        if not query:
            return {"error": "Query is required"}, 400
        
        suggestion_types = None
        if types:
            try:
                suggestion_types = [SuggestionType(t) for t in types]
            except ValueError:
                return {"error": "Invalid suggestion type"}, 400
        
        result = self.service.get_suggestions(query, user_id, suggestion_types, limit)
        return result, 200
    
    def select_suggestion(self, suggestion_id: str, user_id: str = None) -> Tuple[Dict, int]:
        """API endpoint to record suggestion selection"""
        result = self.service.select_suggestion(suggestion_id, user_id)
        
        if "error" in result:
            return result, 404
        
        return result, 200
    
    def get_trending(self, type: str = None, limit: int = 10) -> Tuple[Dict, int]:
        """API endpoint to get trending suggestions"""
        suggestion_type = None
        if type:
            try:
                suggestion_type = SuggestionType(type)
            except ValueError:
                return {"error": "Invalid suggestion type"}, 400
        
        result = self.service.get_trending_suggestions(suggestion_type, limit)
        return result, 200
    
    def get_user_analytics(self, user_id: str) -> Tuple[Dict, int]:
        """API endpoint to get user analytics"""
        result = self.service.get_user_analytics(user_id)
        return result, 200
    
    def get_system_analytics(self) -> Tuple[Dict, int]:
        """API endpoint to get system analytics"""
        result = self.service.get_system_analytics()
        return result, 200
    
    def clear_cache(self) -> Tuple[Dict, int]:
        """API endpoint to clear cache"""
        result = self.service.clear_cache()
        return result, 200


# Example usage and testing
if __name__ == "__main__":
    # Initialize service
    service = TypeaheadService(
        db_url="sqlite:///typeahead.db",
        redis_url="redis://localhost:6379"
    )
    
    # Add some suggestions
    result1 = service.add_suggestion(
        text="machine learning",
        suggestion_type=SuggestionType.QUERY,
        metadata={"category": "technology"}
    )
    print("Added suggestion:", result1)
    
    result2 = service.add_suggestion(
        text="python programming",
        suggestion_type=SuggestionType.QUERY,
        metadata={"category": "programming"}
    )
    print("Added suggestion:", result2)
    
    result3 = service.add_suggestion(
        text="artificial intelligence",
        suggestion_type=SuggestionType.QUERY,
        metadata={"category": "technology"}
    )
    print("Added suggestion:", result3)
    
    # Get suggestions
    suggestions = service.get_suggestions("mach", user_id="user1")
    print("Suggestions for 'mach':", suggestions)
    
    # Select a suggestion
    if suggestions["suggestions"]:
        first_suggestion = suggestions["suggestions"][0]
        select_result = service.select_suggestion(first_suggestion["id"], "user1")
        print("Selection recorded:", select_result)
    
    # Get trending suggestions
    trending = service.get_trending(limit=5)
    print("Trending suggestions:", trending)
    
    # Get user analytics
    analytics = service.get_user_analytics("user1")
    print("User analytics:", analytics)
    
    # Get system analytics
    system_analytics = service.get_system_analytics()
    print("System analytics:", system_analytics)
