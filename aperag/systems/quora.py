"""
Quora System Implementation

A comprehensive Q&A platform with features:
- Question and answer management
- User reputation and expertise tracking
- Topic and category organization
- Voting and ranking system
- Content moderation and quality control
- Search and recommendation engine
- User following and notifications
- Analytics and insights

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
import math

import redis
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Float, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy import create_engine, func, desc, asc

Base = declarative_base()


class ContentStatus(Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    MODERATED = "moderated"
    HIDDEN = "hidden"
    DELETED = "deleted"


class VoteType(Enum):
    UP = "up"
    DOWN = "down"


class NotificationType(Enum):
    ANSWER = "answer"
    COMMENT = "comment"
    VOTE = "vote"
    FOLLOW = "follow"
    MENTION = "mention"


@dataclass
class User:
    """User data structure"""
    id: str
    username: str
    display_name: str
    bio: str = ""
    reputation: int = 0
    expertise_topics: List[str] = field(default_factory=list)
    followers_count: int = 0
    following_count: int = 0
    answers_count: int = 0
    questions_count: int = 0
    is_verified: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "username": self.username,
            "display_name": self.display_name,
            "bio": self.bio,
            "reputation": self.reputation,
            "expertise_topics": self.expertise_topics,
            "followers_count": self.followers_count,
            "following_count": self.following_count,
            "answers_count": self.answers_count,
            "questions_count": self.questions_count,
            "is_verified": self.is_verified,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class Question:
    """Question data structure"""
    id: str
    title: str
    content: str
    author_id: str
    topics: List[str]
    created_at: datetime
    updated_at: datetime
    status: ContentStatus = ContentStatus.PUBLISHED
    views_count: int = 0
    answers_count: int = 0
    votes_count: int = 0
    is_anonymous: bool = False
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "author_id": self.author_id,
            "topics": self.topics,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "status": self.status.value,
            "views_count": self.views_count,
            "answers_count": self.answers_count,
            "votes_count": self.votes_count,
            "is_anonymous": self.is_anonymous
        }


@dataclass
class Answer:
    """Answer data structure"""
    id: str
    question_id: str
    content: str
    author_id: str
    created_at: datetime
    updated_at: datetime
    status: ContentStatus = ContentStatus.PUBLISHED
    votes_count: int = 0
    comments_count: int = 0
    is_accepted: bool = False
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "question_id": self.question_id,
            "content": self.content,
            "author_id": self.author_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "status": self.status.value,
            "votes_count": self.votes_count,
            "comments_count": self.comments_count,
            "is_accepted": self.is_accepted
        }


class UserModel(Base):
    """Database model for users"""
    __tablename__ = 'users'
    
    id = Column(String(50), primary_key=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    display_name = Column(String(100), nullable=False)
    bio = Column(Text, default="")
    reputation = Column(Integer, default=0)
    expertise_topics = Column(JSON)  # List of topic strings
    followers_count = Column(Integer, default=0)
    following_count = Column(Integer, default=0)
    answers_count = Column(Integer, default=0)
    questions_count = Column(Integer, default=0)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class QuestionModel(Base):
    """Database model for questions"""
    __tablename__ = 'questions'
    
    id = Column(String(50), primary_key=True)
    title = Column(String(500), nullable=False, index=True)
    content = Column(Text, nullable=False)
    author_id = Column(String(50), nullable=False, index=True)
    topics = Column(JSON)  # List of topic strings
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = Column(String(20), default=ContentStatus.PUBLISHED.value)
    views_count = Column(Integer, default=0)
    answers_count = Column(Integer, default=0)
    votes_count = Column(Integer, default=0)
    is_anonymous = Column(Boolean, default=False)


class AnswerModel(Base):
    """Database model for answers"""
    __tablename__ = 'answers'
    
    id = Column(String(50), primary_key=True)
    question_id = Column(String(50), nullable=False, index=True)
    content = Column(Text, nullable=False)
    author_id = Column(String(50), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = Column(String(20), default=ContentStatus.PUBLISHED.value)
    votes_count = Column(Integer, default=0)
    comments_count = Column(Integer, default=0)
    is_accepted = Column(Boolean, default=False)


class VoteModel(Base):
    """Database model for votes"""
    __tablename__ = 'votes'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String(50), nullable=False, index=True)
    content_id = Column(String(50), nullable=False, index=True)
    content_type = Column(String(20), nullable=False)  # 'question' or 'answer'
    vote_type = Column(String(10), nullable=False)  # 'up' or 'down'
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        {'extend_existing': True}
    )


class CommentModel(Base):
    """Database model for comments"""
    __tablename__ = 'comments'
    
    id = Column(String(50), primary_key=True)
    content_id = Column(String(50), nullable=False, index=True)
    content_type = Column(String(20), nullable=False)  # 'question' or 'answer'
    author_id = Column(String(50), nullable=False, index=True)
    content = Column(Text, nullable=False)
    parent_comment_id = Column(String(50), nullable=True)  # For nested comments
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), default=ContentStatus.PUBLISHED.value)


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


class TopicFollowModel(Base):
    """Database model for topic follows"""
    __tablename__ = 'topic_follows'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String(50), nullable=False, index=True)
    topic = Column(String(100), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        {'extend_existing': True}
    )


class NotificationModel(Base):
    """Database model for notifications"""
    __tablename__ = 'notifications'
    
    id = Column(String(50), primary_key=True)
    user_id = Column(String(50), nullable=False, index=True)
    notification_type = Column(String(20), nullable=False)
    content_id = Column(String(50), nullable=True)
    actor_id = Column(String(50), nullable=True)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class QuoraService:
    """Main Quora service class"""
    
    def __init__(self, db_url: str, redis_url: str = "redis://localhost:6379"):
        self.db_url = db_url
        self.redis_url = redis_url
        self.redis_client = redis.from_url(redis_url)
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        
        # Configuration
        self.reputation_weights = {
            'answer_upvote': 10,
            'answer_downvote': -2,
            'question_upvote': 5,
            'question_downvote': -1,
            'accepted_answer': 15,
            'best_answer': 25
        }
        self.trending_window_hours = 24
        self.max_search_results = 100
    
    def _get_question_cache_key(self, question_id: str) -> str:
        """Get Redis cache key for question"""
        return f"question:{question_id}"
    
    def _get_user_cache_key(self, user_id: str) -> str:
        """Get Redis cache key for user"""
        return f"user:{user_id}"
    
    def _get_trending_cache_key(self) -> str:
        """Get Redis cache key for trending questions"""
        return "trending:questions"
    
    def _calculate_reputation(self, user_id: str) -> int:
        """Calculate user reputation based on votes"""
        # Get all votes for user's content
        question_votes = self.session.query(VoteModel).join(QuestionModel).filter(
            QuestionModel.author_id == user_id
        ).all()
        
        answer_votes = self.session.query(VoteModel).join(AnswerModel).filter(
            AnswerModel.author_id == user_id
        ).all()
        
        reputation = 0
        
        # Calculate reputation from question votes
        for vote in question_votes:
            if vote.vote_type == VoteType.UP.value:
                reputation += self.reputation_weights['question_upvote']
            elif vote.vote_type == VoteType.DOWN.value:
                reputation += self.reputation_weights['question_downvote']
        
        # Calculate reputation from answer votes
        for vote in answer_votes:
            if vote.vote_type == VoteType.UP.value:
                reputation += self.reputation_weights['answer_upvote']
            elif vote.vote_type == VoteType.DOWN.value:
                reputation += self.reputation_weights['answer_downvote']
        
        # Check for accepted answers
        accepted_answers = self.session.query(AnswerModel).filter(
            AnswerModel.author_id == user_id,
            AnswerModel.is_accepted == True
        ).count()
        reputation += accepted_answers * self.reputation_weights['accepted_answer']
        
        return max(0, reputation)
    
    def _update_user_reputation(self, user_id: str):
        """Update user reputation"""
        reputation = self._calculate_reputation(user_id)
        user = self.session.query(UserModel).filter(UserModel.id == user_id).first()
        if user:
            user.reputation = reputation
            self.session.commit()
    
    def _send_notification(self, user_id: str, notification_type: NotificationType,
                          content_id: str = None, actor_id: str = None, message: str = ""):
        """Send notification to user"""
        notification = NotificationModel(
            id=str(uuid.uuid4()),
            user_id=user_id,
            notification_type=notification_type.value,
            content_id=content_id,
            actor_id=actor_id,
            message=message
        )
        
        try:
            self.session.add(notification)
            self.session.commit()
        except Exception:
            self.session.rollback()
    
    def create_question(self, title: str, content: str, author_id: str, 
                       topics: List[str] = None, is_anonymous: bool = False) -> Dict:
        """Create a new question"""
        if not title.strip() or not content.strip():
            return {"error": "Title and content are required"}
        
        question_id = f"q_{int(time.time() * 1000)}_{author_id}"
        
        question = QuestionModel(
            id=question_id,
            title=title,
            content=content,
            author_id=author_id,
            topics=topics or [],
            is_anonymous=is_anonymous
        )
        
        try:
            self.session.add(question)
            
            # Update user's question count
            user = self.session.query(UserModel).filter(UserModel.id == author_id).first()
            if user:
                user.questions_count += 1
            
            self.session.commit()
            
            # Cache the question
            self._cache_question(question_id, question)
            
            return {
                "question_id": question_id,
                "title": title,
                "content": content,
                "author_id": author_id,
                "topics": topics or [],
                "created_at": question.created_at.isoformat(),
                "is_anonymous": is_anonymous
            }
        
        except Exception as e:
            self.session.rollback()
            return {"error": f"Failed to create question: {str(e)}"}
    
    def create_answer(self, question_id: str, content: str, author_id: str) -> Dict:
        """Create a new answer"""
        if not content.strip():
            return {"error": "Content is required"}
        
        # Check if question exists
        question = self.session.query(QuestionModel).filter(QuestionModel.id == question_id).first()
        if not question:
            return {"error": "Question not found"}
        
        answer_id = f"a_{int(time.time() * 1000)}_{author_id}"
        
        answer = AnswerModel(
            id=answer_id,
            question_id=question_id,
            content=content,
            author_id=author_id
        )
        
        try:
            self.session.add(answer)
            
            # Update question's answer count
            question.answers_count += 1
            
            # Update user's answer count
            user = self.session.query(UserModel).filter(UserModel.id == author_id).first()
            if user:
                user.answers_count += 1
            
            self.session.commit()
            
            # Send notification to question author
            if question.author_id != author_id:
                self._send_notification(
                    user_id=question.author_id,
                    notification_type=NotificationType.ANSWER,
                    content_id=question_id,
                    actor_id=author_id,
                    message=f"Someone answered your question: {question.title[:50]}..."
                )
            
            return {
                "answer_id": answer_id,
                "question_id": question_id,
                "content": content,
                "author_id": author_id,
                "created_at": answer.created_at.isoformat()
            }
        
        except Exception as e:
            self.session.rollback()
            return {"error": f"Failed to create answer: {str(e)}"}
    
    def vote_content(self, user_id: str, content_id: str, content_type: str, 
                    vote_type: VoteType) -> Dict:
        """Vote on question or answer"""
        # Check if user already voted
        existing_vote = self.session.query(VoteModel).filter(
            VoteModel.user_id == user_id,
            VoteModel.content_id == content_id,
            VoteModel.content_type == content_type
        ).first()
        
        if existing_vote:
            if existing_vote.vote_type == vote_type.value:
                return {"error": "Already voted with this type"}
            else:
                # Change vote type
                existing_vote.vote_type = vote_type.value
                existing_vote.created_at = datetime.utcnow()
        else:
            # Create new vote
            vote = VoteModel(
                user_id=user_id,
                content_id=content_id,
                content_type=content_type,
                vote_type=vote_type.value
            )
            self.session.add(vote)
        
        # Update content vote count
        if content_type == "question":
            content = self.session.query(QuestionModel).filter(QuestionModel.id == content_id).first()
        else:
            content = self.session.query(AnswerModel).filter(AnswerModel.id == content_id).first()
        
        if not content:
            return {"error": "Content not found"}
        
        # Recalculate vote count
        votes = self.session.query(VoteModel).filter(
            VoteModel.content_id == content_id,
            VoteModel.content_type == content_type
        ).all()
        
        vote_count = sum(1 for v in votes if v.vote_type == VoteType.UP.value) - \
                    sum(1 for v in votes if v.vote_type == VoteType.DOWN.value)
        
        content.votes_count = vote_count
        
        try:
            self.session.commit()
            
            # Update author reputation
            if content_type == "question":
                self._update_user_reputation(content.author_id)
            else:
                self._update_user_reputation(content.author_id)
            
            # Send notification
            if content.author_id != user_id:
                self._send_notification(
                    user_id=content.author_id,
                    notification_type=NotificationType.VOTE,
                    content_id=content_id,
                    actor_id=user_id,
                    message=f"Someone voted on your {content_type}"
                )
            
            return {"message": f"Vote recorded successfully", "vote_count": vote_count}
        
        except Exception as e:
            self.session.rollback()
            return {"error": f"Failed to vote: {str(e)}"}
    
    def accept_answer(self, question_id: str, answer_id: str, user_id: str) -> Dict:
        """Accept an answer as the best answer"""
        # Check if user owns the question
        question = self.session.query(QuestionModel).filter(
            QuestionModel.id == question_id,
            QuestionModel.author_id == user_id
        ).first()
        
        if not question:
            return {"error": "Question not found or access denied"}
        
        # Check if answer exists and belongs to the question
        answer = self.session.query(AnswerModel).filter(
            AnswerModel.id == answer_id,
            AnswerModel.question_id == question_id
        ).first()
        
        if not answer:
            return {"error": "Answer not found"}
        
        # Unaccept any previously accepted answer
        self.session.query(AnswerModel).filter(
            AnswerModel.question_id == question_id,
            AnswerModel.is_accepted == True
        ).update({"is_accepted": False})
        
        # Accept the new answer
        answer.is_accepted = True
        
        try:
            self.session.commit()
            
            # Update answer author reputation
            self._update_user_reputation(answer.author_id)
            
            # Send notification
            if answer.author_id != user_id:
                self._send_notification(
                    user_id=answer.author_id,
                    notification_type=NotificationType.VOTE,
                    content_id=answer_id,
                    actor_id=user_id,
                    message="Your answer was accepted as the best answer!"
                )
            
            return {"message": "Answer accepted successfully"}
        
        except Exception as e:
            self.session.rollback()
            return {"error": f"Failed to accept answer: {str(e)}"}
    
    def get_question(self, question_id: str, user_id: str = None) -> Dict:
        """Get question with answers"""
        # Check cache first
        cache_key = self._get_question_cache_key(question_id)
        cached_question = self.redis_client.get(cache_key)
        
        if cached_question:
            question_data = json.loads(cached_question)
        else:
            # Query database
            question = self.session.query(QuestionModel).filter(QuestionModel.id == question_id).first()
            if not question:
                return {"error": "Question not found"}
            
            question_data = {
                "id": question.id,
                "title": question.title,
                "content": question.content,
                "author_id": question.author_id,
                "topics": question.topics or [],
                "created_at": question.created_at.isoformat(),
                "updated_at": question.updated_at.isoformat(),
                "status": question.status,
                "views_count": question.views_count,
                "answers_count": question.answers_count,
                "votes_count": question.votes_count,
                "is_anonymous": question.is_anonymous
            }
            
            # Cache the question
            self.redis_client.setex(cache_key, 3600, json.dumps(question_data))
        
        # Increment view count
        if user_id:
            self.session.query(QuestionModel).filter(QuestionModel.id == question_id).update({
                "views_count": QuestionModel.views_count + 1
            })
            self.session.commit()
        
        # Get answers
        answers = self.session.query(AnswerModel).filter(
            AnswerModel.question_id == question_id,
            AnswerModel.status == ContentStatus.PUBLISHED.value
        ).order_by(desc(AnswerModel.is_accepted), desc(AnswerModel.votes_count)).all()
        
        answers_data = []
        for answer in answers:
            answers_data.append({
                "id": answer.id,
                "content": answer.content,
                "author_id": answer.author_id,
                "created_at": answer.created_at.isoformat(),
                "updated_at": answer.updated_at.isoformat(),
                "votes_count": answer.votes_count,
                "comments_count": answer.comments_count,
                "is_accepted": answer.is_accepted
            })
        
        question_data["answers"] = answers_data
        return question_data
    
    def search_questions(self, query: str, topics: List[str] = None, 
                        limit: int = 20, offset: int = 0) -> Dict:
        """Search questions by title and content"""
        search_query = self.session.query(QuestionModel).filter(
            QuestionModel.status == ContentStatus.PUBLISHED.value
        )
        
        if query:
            search_query = search_query.filter(
                QuestionModel.title.contains(query) | 
                QuestionModel.content.contains(query)
            )
        
        if topics:
            for topic in topics:
                search_query = search_query.filter(QuestionModel.topics.contains([topic]))
        
        total = search_query.count()
        questions = search_query.order_by(desc(QuestionModel.created_at)).offset(offset).limit(limit).all()
        
        return {
            "questions": [
                {
                    "id": q.id,
                    "title": q.title,
                    "content": q.content[:200] + "..." if len(q.content) > 200 else q.content,
                    "author_id": q.author_id,
                    "topics": q.topics or [],
                    "created_at": q.created_at.isoformat(),
                    "views_count": q.views_count,
                    "answers_count": q.answers_count,
                    "votes_count": q.votes_count,
                    "is_anonymous": q.is_anonymous
                }
                for q in questions
            ],
            "total": total,
            "query": query,
            "topics": topics or [],
            "limit": limit,
            "offset": offset
        }
    
    def get_trending_questions(self, limit: int = 20) -> Dict:
        """Get trending questions based on recent activity"""
        # Check cache first
        cache_key = self._get_trending_cache_key()
        cached_trending = self.redis_client.get(cache_key)
        
        if cached_trending:
            return json.loads(cached_trending)
        
        # Get questions from last 24 hours with high engagement
        since = datetime.utcnow() - timedelta(hours=self.trending_window_hours)
        
        trending_questions = self.session.query(QuestionModel).filter(
            QuestionModel.created_at >= since,
            QuestionModel.status == ContentStatus.PUBLISHED.value
        ).order_by(
            desc(QuestionModel.views_count + QuestionModel.answers_count + QuestionModel.votes_count)
        ).limit(limit).all()
        
        result = {
            "questions": [
                {
                    "id": q.id,
                    "title": q.title,
                    "content": q.content[:200] + "..." if len(q.content) > 200 else q.content,
                    "author_id": q.author_id,
                    "topics": q.topics or [],
                    "created_at": q.created_at.isoformat(),
                    "views_count": q.views_count,
                    "answers_count": q.answers_count,
                    "votes_count": q.votes_count,
                    "trending_score": q.views_count + q.answers_count + q.votes_count
                }
                for q in trending_questions
            ],
            "total": len(trending_questions)
        }
        
        # Cache for 1 hour
        self.redis_client.setex(cache_key, 3600, json.dumps(result))
        
        return result
    
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
        follow = FollowModel(follower_id=follower_id, following_id=following_id)
        
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
            
            # Send notification
            self._send_notification(
                user_id=following_id,
                notification_type=NotificationType.FOLLOW,
                actor_id=follower_id,
                message=f"Someone started following you"
            )
            
            return {"message": "Successfully followed user"}
        
        except Exception as e:
            self.session.rollback()
            return {"error": f"Failed to follow user: {str(e)}"}
    
    def follow_topic(self, user_id: str, topic: str) -> Dict:
        """Follow a topic"""
        # Check if already following
        existing = self.session.query(TopicFollowModel).filter(
            TopicFollowModel.user_id == user_id,
            TopicFollowModel.topic == topic
        ).first()
        
        if existing:
            return {"error": "Already following this topic"}
        
        # Create topic follow
        topic_follow = TopicFollowModel(user_id=user_id, topic=topic)
        
        try:
            self.session.add(topic_follow)
            self.session.commit()
            return {"message": f"Successfully following topic: {topic}"}
        except Exception as e:
            self.session.rollback()
            return {"error": f"Failed to follow topic: {str(e)}"}
    
    def get_user_feed(self, user_id: str, limit: int = 20, offset: int = 0) -> Dict:
        """Get personalized feed for user"""
        # Get followed users
        followed_users = self.session.query(FollowModel.following_id).filter(
            FollowModel.follower_id == user_id
        ).all()
        followed_user_ids = [f[0] for f in followed_users]
        
        # Get followed topics
        followed_topics = self.session.query(TopicFollowModel.topic).filter(
            TopicFollowModel.user_id == user_id
        ).all()
        followed_topic_list = [f[0] for f in followed_topics]
        
        # Get questions from followed users or topics
        query = self.session.query(QuestionModel).filter(
            QuestionModel.status == ContentStatus.PUBLISHED.value
        )
        
        if followed_user_ids or followed_topic_list:
            conditions = []
            if followed_user_ids:
                conditions.append(QuestionModel.author_id.in_(followed_user_ids))
            if followed_topic_list:
                for topic in followed_topic_list:
                    conditions.append(QuestionModel.topics.contains([topic]))
            
            if conditions:
                from sqlalchemy import or_
                query = query.filter(or_(*conditions))
        
        total = query.count()
        questions = query.order_by(desc(QuestionModel.created_at)).offset(offset).limit(limit).all()
        
        return {
            "questions": [
                {
                    "id": q.id,
                    "title": q.title,
                    "content": q.content[:200] + "..." if len(q.content) > 200 else q.content,
                    "author_id": q.author_id,
                    "topics": q.topics or [],
                    "created_at": q.created_at.isoformat(),
                    "views_count": q.views_count,
                    "answers_count": q.answers_count,
                    "votes_count": q.votes_count
                }
                for q in questions
            ],
            "total": total,
            "limit": limit,
            "offset": offset
        }
    
    def get_user_profile(self, user_id: str) -> Dict:
        """Get user profile with stats"""
        user = self.session.query(UserModel).filter(UserModel.id == user_id).first()
        if not user:
            return {"error": "User not found"}
        
        # Get user's top answers
        top_answers = self.session.query(AnswerModel).filter(
            AnswerModel.author_id == user_id,
            AnswerModel.status == ContentStatus.PUBLISHED.value
        ).order_by(desc(AnswerModel.votes_count)).limit(5).all()
        
        # Get user's recent questions
        recent_questions = self.session.query(QuestionModel).filter(
            QuestionModel.author_id == user_id,
            QuestionModel.status == ContentStatus.PUBLISHED.value
        ).order_by(desc(QuestionModel.created_at)).limit(5).all()
        
        return {
            "user": {
                "id": user.id,
                "username": user.username,
                "display_name": user.display_name,
                "bio": user.bio,
                "reputation": user.reputation,
                "expertise_topics": user.expertise_topics or [],
                "followers_count": user.followers_count,
                "following_count": user.following_count,
                "answers_count": user.answers_count,
                "questions_count": user.questions_count,
                "is_verified": user.is_verified,
                "created_at": user.created_at.isoformat()
            },
            "top_answers": [
                {
                    "id": a.id,
                    "question_id": a.question_id,
                    "content": a.content[:200] + "..." if len(a.content) > 200 else a.content,
                    "votes_count": a.votes_count,
                    "is_accepted": a.is_accepted,
                    "created_at": a.created_at.isoformat()
                }
                for a in top_answers
            ],
            "recent_questions": [
                {
                    "id": q.id,
                    "title": q.title,
                    "content": q.content[:200] + "..." if len(q.content) > 200 else q.content,
                    "answers_count": q.answers_count,
                    "votes_count": q.votes_count,
                    "created_at": q.created_at.isoformat()
                }
                for q in recent_questions
            ]
        }
    
    def get_notifications(self, user_id: str, limit: int = 20, offset: int = 0) -> Dict:
        """Get user notifications"""
        notifications = self.session.query(NotificationModel).filter(
            NotificationModel.user_id == user_id
        ).order_by(desc(NotificationModel.created_at)).offset(offset).limit(limit).all()
        
        total = self.session.query(NotificationModel).filter(
            NotificationModel.user_id == user_id
        ).count()
        
        return {
            "notifications": [
                {
                    "id": n.id,
                    "type": n.notification_type,
                    "content_id": n.content_id,
                    "actor_id": n.actor_id,
                    "message": n.message,
                    "is_read": n.is_read,
                    "created_at": n.created_at.isoformat()
                }
                for n in notifications
            ],
            "total": total,
            "limit": limit,
            "offset": offset
        }
    
    def mark_notification_read(self, user_id: str, notification_id: str) -> Dict:
        """Mark notification as read"""
        notification = self.session.query(NotificationModel).filter(
            NotificationModel.id == notification_id,
            NotificationModel.user_id == user_id
        ).first()
        
        if not notification:
            return {"error": "Notification not found"}
        
        notification.is_read = True
        
        try:
            self.session.commit()
            return {"message": "Notification marked as read"}
        except Exception as e:
            self.session.rollback()
            return {"error": f"Failed to mark notification as read: {str(e)}"}
    
    def _cache_question(self, question_id: str, question: QuestionModel):
        """Cache question data"""
        cache_key = self._get_question_cache_key(question_id)
        question_data = {
            "id": question.id,
            "title": question.title,
            "content": question.content,
            "author_id": question.author_id,
            "topics": question.topics or [],
            "created_at": question.created_at.isoformat(),
            "updated_at": question.updated_at.isoformat(),
            "status": question.status,
            "views_count": question.views_count,
            "answers_count": question.answers_count,
            "votes_count": question.votes_count,
            "is_anonymous": question.is_anonymous
        }
        self.redis_client.setex(cache_key, 3600, json.dumps(question_data))


class QuoraAPI:
    """REST API for Quora service"""
    
    def __init__(self, service: QuoraService):
        self.service = service
    
    def create_question(self, request_data: Dict) -> Tuple[Dict, int]:
        """API endpoint to create a question"""
        title = request_data.get('title')
        content = request_data.get('content')
        author_id = request_data.get('author_id')
        topics = request_data.get('topics', [])
        is_anonymous = request_data.get('is_anonymous', False)
        
        if not title or not content or not author_id:
            return {"error": "Title, content, and author_id are required"}, 400
        
        result = self.service.create_question(title, content, author_id, topics, is_anonymous)
        
        if "error" in result:
            return result, 400
        
        return result, 201
    
    def create_answer(self, request_data: Dict) -> Tuple[Dict, int]:
        """API endpoint to create an answer"""
        question_id = request_data.get('question_id')
        content = request_data.get('content')
        author_id = request_data.get('author_id')
        
        if not question_id or not content or not author_id:
            return {"error": "Question ID, content, and author_id are required"}, 400
        
        result = self.service.create_answer(question_id, content, author_id)
        
        if "error" in result:
            return result, 400
        
        return result, 201
    
    def vote_content(self, request_data: Dict) -> Tuple[Dict, int]:
        """API endpoint to vote on content"""
        user_id = request_data.get('user_id')
        content_id = request_data.get('content_id')
        content_type = request_data.get('content_type')
        vote_type = request_data.get('vote_type')
        
        if not all([user_id, content_id, content_type, vote_type]):
            return {"error": "All fields are required"}, 400
        
        try:
            vote_type_enum = VoteType(vote_type)
        except ValueError:
            return {"error": "Invalid vote type"}, 400
        
        if content_type not in ["question", "answer"]:
            return {"error": "Invalid content type"}, 400
        
        result = self.service.vote_content(user_id, content_id, content_type, vote_type_enum)
        
        if "error" in result:
            return result, 400
        
        return result, 200
    
    def get_question(self, question_id: str, user_id: str = None) -> Tuple[Dict, int]:
        """API endpoint to get a question"""
        result = self.service.get_question(question_id, user_id)
        
        if "error" in result:
            return result, 404 if "not found" in result["error"].lower() else 400
        
        return result, 200
    
    def search_questions(self, query: str = "", topics: List[str] = None, 
                        limit: int = 20, offset: int = 0) -> Tuple[Dict, int]:
        """API endpoint to search questions"""
        result = self.service.search_questions(query, topics, limit, offset)
        return result, 200
    
    def get_trending_questions(self, limit: int = 20) -> Tuple[Dict, int]:
        """API endpoint to get trending questions"""
        result = self.service.get_trending_questions(limit)
        return result, 200
    
    def get_user_feed(self, user_id: str, limit: int = 20, offset: int = 0) -> Tuple[Dict, int]:
        """API endpoint to get user feed"""
        result = self.service.get_user_feed(user_id, limit, offset)
        return result, 200
    
    def get_user_profile(self, user_id: str) -> Tuple[Dict, int]:
        """API endpoint to get user profile"""
        result = self.service.get_user_profile(user_id)
        
        if "error" in result:
            return result, 404
        
        return result, 200
    
    def get_notifications(self, user_id: str, limit: int = 20, offset: int = 0) -> Tuple[Dict, int]:
        """API endpoint to get user notifications"""
        result = self.service.get_notifications(user_id, limit, offset)
        return result, 200


# Example usage and testing
if __name__ == "__main__":
    # Initialize service
    service = QuoraService(
        db_url="sqlite:///quora.db",
        redis_url="redis://localhost:6379"
    )
    
    # Test creating a question
    result1 = service.create_question(
        title="What is the best way to learn machine learning?",
        content="I'm a beginner and want to learn machine learning. What are the best resources and approaches?",
        author_id="user1",
        topics=["machine-learning", "education", "programming"]
    )
    print("Created question:", result1)
    
    # Test creating an answer
    if "question_id" in result1:
        result2 = service.create_answer(
            question_id=result1["question_id"],
            content="I recommend starting with Python and scikit-learn. Here are some great resources...",
            author_id="user2"
        )
        print("Created answer:", result2)
        
        # Test voting
        vote_result = service.vote_content(
            user_id="user1",
            content_id=result2["answer_id"],
            content_type="answer",
            vote_type=VoteType.UP
        )
        print("Vote result:", vote_result)
        
        # Test getting question
        question = service.get_question(result1["question_id"], "user1")
        print("Question details:", question)
        
        # Test search
        search_result = service.search_questions("machine learning", limit=5)
        print("Search results:", search_result)
        
        # Test trending
        trending = service.get_trending_questions(limit=5)
        print("Trending questions:", trending)
        
        # Test user profile
        profile = service.get_user_profile("user1")
        print("User profile:", profile)
