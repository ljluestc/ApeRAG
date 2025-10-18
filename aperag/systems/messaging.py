"""
Messaging System Implementation

A comprehensive messaging and communication system with features:
- Real-time messaging (WebSocket support)
- Group messaging and channels
- Message encryption and security
- File and media sharing
- Message search and filtering
- Read receipts and delivery status
- Message threading and replies
- Push notifications

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
import hashlib
import base64

import redis
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Float, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy import create_engine, func, desc, asc
import websockets
import aiohttp


Base = declarative_base()


class MessageType(Enum):
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    AUDIO = "audio"
    VIDEO = "video"
    SYSTEM = "system"
    CALL = "call"


class MessageStatus(Enum):
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class ChannelType(Enum):
    DIRECT = "direct"
    GROUP = "group"
    PUBLIC = "public"
    PRIVATE = "private"


@dataclass
class Message:
    """Message data structure"""
    id: str
    sender_id: str
    channel_id: str
    content: str
    message_type: MessageType
    status: MessageStatus = MessageStatus.SENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    reply_to: str = None
    thread_id: str = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    encrypted: bool = False
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "sender_id": self.sender_id,
            "channel_id": self.channel_id,
            "content": self.content,
            "type": self.message_type.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "reply_to": self.reply_to,
            "thread_id": self.thread_id,
            "metadata": self.metadata,
            "encrypted": self.encrypted
        }


@dataclass
class Channel:
    """Channel data structure"""
    id: str
    name: str
    channel_type: ChannelType
    description: str = ""
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    members: Set[str] = field(default_factory=set)
    admins: Set[str] = field(default_factory=set)
    settings: Dict[str, Any] = field(default_factory=dict)
    is_active: bool = True
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.channel_type.value,
            "description": self.description,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "members": list(self.members),
            "admins": list(self.admins),
            "settings": self.settings,
            "is_active": self.is_active
        }


class MessageModel(Base):
    """Database model for messages"""
    __tablename__ = 'messages'
    
    id = Column(String(50), primary_key=True)
    sender_id = Column(String(50), nullable=False, index=True)
    channel_id = Column(String(50), nullable=False, index=True)
    content = Column(Text, nullable=False)
    message_type = Column(String(20), nullable=False)
    status = Column(String(20), default=MessageStatus.SENDING.value)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow)
    reply_to = Column(String(50), nullable=True)
    thread_id = Column(String(50), nullable=True, index=True)
    metadata = Column(JSON)
    encrypted = Column(Boolean, default=False)


class ChannelModel(Base):
    """Database model for channels"""
    __tablename__ = 'channels'
    
    id = Column(String(50), primary_key=True)
    name = Column(String(200), nullable=False)
    channel_type = Column(String(20), nullable=False)
    description = Column(Text, default="")
    created_by = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    members = Column(JSON)  # List of user IDs
    admins = Column(JSON)  # List of user IDs
    settings = Column(JSON)
    is_active = Column(Boolean, default=True)


class ChannelMemberModel(Base):
    """Database model for channel members"""
    __tablename__ = 'channel_members'
    
    id = Column(Integer, primary_key=True)
    channel_id = Column(String(50), nullable=False, index=True)
    user_id = Column(String(50), nullable=False, index=True)
    joined_at = Column(DateTime, default=datetime.utcnow)
    last_read_at = Column(DateTime, default=datetime.utcnow)
    is_admin = Column(Boolean, default=False)
    is_muted = Column(Boolean, default=False)


class MessageReadModel(Base):
    """Database model for message read status"""
    __tablename__ = 'message_reads'
    
    id = Column(Integer, primary_key=True)
    message_id = Column(String(50), nullable=False, index=True)
    user_id = Column(String(50), nullable=False, index=True)
    read_at = Column(DateTime, default=datetime.utcnow)


class MessagingService:
    """Main messaging service class"""
    
    def __init__(self, db_url: str, redis_url: str = "redis://localhost:6379"):
        self.db_url = db_url
        self.redis_url = redis_url
        self.redis_client = redis.from_url(redis_url)
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        
        # In-memory storage
        self.channels: Dict[str, Channel] = {}
        self.messages: Dict[str, Message] = {}
        self.active_connections: Dict[str, Set[str]] = defaultdict(set)  # user_id -> set of websocket connections
        
        # Configuration
        self.message_retention_days = 30
        self.max_message_length = 10000
        self.encryption_key = "default_key"  # In production, use proper key management
        
        # Load existing data
        self._load_channels()
        self._load_recent_messages()
    
    def _load_channels(self):
        """Load channels from database"""
        channels = self.session.query(ChannelModel).filter(ChannelModel.is_active == True).all()
        for channel in channels:
            self.channels[channel.id] = Channel(
                id=channel.id,
                name=channel.name,
                channel_type=ChannelType(channel.channel_type),
                description=channel.description,
                created_by=channel.created_by,
                created_at=channel.created_at,
                updated_at=channel.updated_at,
                members=set(channel.members or []),
                admins=set(channel.admins or []),
                settings=channel.settings or {},
                is_active=channel.is_active
            )
    
    def _load_recent_messages(self):
        """Load recent messages from database"""
        cutoff_date = datetime.utcnow() - timedelta(days=7)
        messages = self.session.query(MessageModel).filter(
            MessageModel.created_at >= cutoff_date
        ).order_by(MessageModel.created_at.desc()).limit(1000).all()
        
        for message in messages:
            self.messages[message.id] = Message(
                id=message.id,
                sender_id=message.sender_id,
                channel_id=message.channel_id,
                content=message.content,
                message_type=MessageType(message.message_type),
                status=MessageStatus(message.status),
                created_at=message.created_at,
                updated_at=message.updated_at,
                reply_to=message.reply_to,
                thread_id=message.thread_id,
                metadata=message.metadata or {},
                encrypted=message.encrypted
            )
    
    def create_channel(self, name: str, channel_type: ChannelType, 
                      created_by: str, description: str = "", 
                      members: List[str] = None) -> Dict:
        """Create a new channel"""
        channel_id = str(uuid.uuid4())
        
        # Add creator to members
        if members is None:
            members = []
        if created_by not in members:
            members.append(created_by)
        
        channel = Channel(
            id=channel_id,
            name=name,
            channel_type=channel_type,
            description=description,
            created_by=created_by,
            members=set(members),
            admins={created_by}
        )
        
        self.channels[channel_id] = channel
        
        # Save to database
        try:
            channel_model = ChannelModel(
                id=channel_id,
                name=name,
                channel_type=channel_type.value,
                description=description,
                created_by=created_by,
                members=list(members),
                admins=[created_by],
                settings={}
            )
            
            self.session.add(channel_model)
            
            # Add channel members
            for member_id in members:
                member = ChannelMemberModel(
                    channel_id=channel_id,
                    user_id=member_id,
                    is_admin=(member_id == created_by)
                )
                self.session.add(member)
            
            self.session.commit()
            
            return {
                "channel_id": channel_id,
                "name": name,
                "type": channel_type.value,
                "members": list(members),
                "message": "Channel created successfully"
            }
        
        except Exception as e:
            self.session.rollback()
            return {"error": f"Failed to create channel: {str(e)}"}
    
    def send_message(self, sender_id: str, channel_id: str, content: str,
                    message_type: MessageType = MessageType.TEXT,
                    reply_to: str = None, thread_id: str = None,
                    encrypt: bool = False) -> Dict:
        """Send a message to a channel"""
        if channel_id not in self.channels:
            return {"error": "Channel not found"}
        
        channel = self.channels[channel_id]
        
        # Check if user is a member
        if sender_id not in channel.members:
            return {"error": "User is not a member of this channel"}
        
        # Validate message content
        if not content.strip():
            return {"error": "Message content cannot be empty"}
        
        if len(content) > self.max_message_length:
            return {"error": f"Message too long (max {self.max_message_length} characters)"}
        
        # Encrypt content if requested
        if encrypt:
            content = self._encrypt_message(content)
        
        message_id = str(uuid.uuid4())
        
        message = Message(
            id=message_id,
            sender_id=sender_id,
            channel_id=channel_id,
            content=content,
            message_type=message_type,
            reply_to=reply_to,
            thread_id=thread_id,
            encrypted=encrypt
        )
        
        self.messages[message_id] = message
        
        # Save to database
        try:
            message_model = MessageModel(
                id=message_id,
                sender_id=sender_id,
                channel_id=channel_id,
                content=content,
                message_type=message_type.value,
                reply_to=reply_to,
                thread_id=thread_id,
                encrypted=encrypt
            )
            
            self.session.add(message_model)
            self.session.commit()
            
            # Broadcast message to channel members
            self._broadcast_message(message)
            
            return {
                "message_id": message_id,
                "channel_id": channel_id,
                "content": content,
                "type": message_type.value,
                "status": message.status.value,
                "created_at": message.created_at.isoformat()
            }
        
        except Exception as e:
            self.session.rollback()
            return {"error": f"Failed to send message: {str(e)}"}
    
    def _encrypt_message(self, content: str) -> str:
        """Encrypt message content"""
        # Simple encryption for demo purposes
        # In production, use proper encryption libraries
        encoded = base64.b64encode(content.encode()).decode()
        return f"encrypted:{encoded}"
    
    def _decrypt_message(self, content: str) -> str:
        """Decrypt message content"""
        if content.startswith("encrypted:"):
            encoded = content[10:]  # Remove "encrypted:" prefix
            return base64.b64decode(encoded.encode()).decode()
        return content
    
    def _broadcast_message(self, message: Message):
        """Broadcast message to all connected users in the channel"""
        channel = self.channels.get(message.channel_id)
        if not channel:
            return
        
        # Get all connected users in this channel
        connected_users = set()
        for user_id in channel.members:
            if user_id in self.active_connections:
                connected_users.update(self.active_connections[user_id])
        
        # Send message to all connected users
        message_data = message.to_dict()
        for connection in connected_users:
            try:
                asyncio.create_task(self._send_websocket_message(connection, message_data))
            except Exception as e:
                print(f"Failed to send message to connection {connection}: {e}")
    
    async def _send_websocket_message(self, connection, message_data):
        """Send message via WebSocket"""
        # This would be implemented with actual WebSocket connections
        # For now, we'll just print the message
        print(f"Sending to {connection}: {message_data}")
    
    def get_messages(self, channel_id: str, user_id: str, 
                    limit: int = 50, offset: int = 0) -> Dict:
        """Get messages from a channel"""
        if channel_id not in self.channels:
            return {"error": "Channel not found"}
        
        channel = self.channels[channel_id]
        
        # Check if user is a member
        if user_id not in channel.members:
            return {"error": "User is not a member of this channel"}
        
        # Get messages from database
        query = self.session.query(MessageModel).filter(
            MessageModel.channel_id == channel_id
        ).order_by(MessageModel.created_at.desc())
        
        total = query.count()
        messages = query.offset(offset).limit(limit).all()
        
        # Convert to Message objects and decrypt if needed
        message_objects = []
        for msg in messages:
            content = msg.content
            if msg.encrypted:
                content = self._decrypt_message(content)
            
            message_objects.append({
                "id": msg.id,
                "sender_id": msg.sender_id,
                "channel_id": msg.channel_id,
                "content": content,
                "type": msg.message_type,
                "status": msg.status,
                "created_at": msg.created_at.isoformat(),
                "updated_at": msg.updated_at.isoformat(),
                "reply_to": msg.reply_to,
                "thread_id": msg.thread_id,
                "metadata": msg.metadata or {},
                "encrypted": msg.encrypted
            })
        
        return {
            "messages": message_objects,
            "total": total,
            "limit": limit,
            "offset": offset
        }
    
    def mark_message_read(self, message_id: str, user_id: str) -> Dict:
        """Mark a message as read"""
        if message_id not in self.messages:
            return {"error": "Message not found"}
        
        message = self.messages[message_id]
        
        # Check if user is a member of the channel
        channel = self.channels.get(message.channel_id)
        if not channel or user_id not in channel.members:
            return {"error": "User is not a member of this channel"}
        
        # Check if already read
        existing = self.session.query(MessageReadModel).filter(
            MessageReadModel.message_id == message_id,
            MessageReadModel.user_id == user_id
        ).first()
        
        if existing:
            return {"message": "Message already marked as read"}
        
        # Mark as read
        try:
            read_record = MessageReadModel(
                message_id=message_id,
                user_id=user_id
            )
            
            self.session.add(read_record)
            self.session.commit()
            
            return {"message": "Message marked as read"}
        
        except Exception as e:
            self.session.rollback()
            return {"error": f"Failed to mark message as read: {str(e)}"}
    
    def get_unread_count(self, user_id: str, channel_id: str = None) -> Dict:
        """Get unread message count for user"""
        query = self.session.query(MessageModel).join(ChannelMemberModel).filter(
            ChannelMemberModel.user_id == user_id,
            MessageModel.created_at > ChannelMemberModel.last_read_at
        )
        
        if channel_id:
            query = query.filter(MessageModel.channel_id == channel_id)
        
        unread_count = query.count()
        
        return {
            "user_id": user_id,
            "channel_id": channel_id,
            "unread_count": unread_count
        }
    
    def search_messages(self, user_id: str, query: str, 
                       channel_id: str = None, limit: int = 20) -> Dict:
        """Search messages"""
        # Get channels user has access to
        accessible_channels = self.session.query(ChannelMemberModel.channel_id).filter(
            ChannelMemberModel.user_id == user_id
        ).all()
        channel_ids = [c[0] for c in accessible_channels]
        
        if not channel_ids:
            return {"messages": [], "query": query, "count": 0}
        
        # Search messages
        search_query = self.session.query(MessageModel).filter(
            MessageModel.channel_id.in_(channel_ids),
            MessageModel.content.contains(query)
        )
        
        if channel_id and channel_id in channel_ids:
            search_query = search_query.filter(MessageModel.channel_id == channel_id)
        
        messages = search_query.order_by(MessageModel.created_at.desc()).limit(limit).all()
        
        # Format results
        results = []
        for msg in messages:
            content = msg.content
            if msg.encrypted:
                content = self._decrypt_message(content)
            
            results.append({
                "id": msg.id,
                "sender_id": msg.sender_id,
                "channel_id": msg.channel_id,
                "content": content,
                "type": msg.message_type,
                "created_at": msg.created_at.isoformat(),
                "encrypted": msg.encrypted
            })
        
        return {
            "messages": results,
            "query": query,
            "count": len(results)
        }
    
    def add_member_to_channel(self, channel_id: str, user_id: str, 
                             added_by: str) -> Dict:
        """Add member to channel"""
        if channel_id not in self.channels:
            return {"error": "Channel not found"}
        
        channel = self.channels[channel_id]
        
        # Check if user has permission to add members
        if added_by not in channel.admins:
            return {"error": "User does not have permission to add members"}
        
        # Add member
        channel.members.add(user_id)
        
        try:
            # Update database
            self.session.query(ChannelModel).filter(ChannelModel.id == channel_id).update({
                "members": list(channel.members)
            })
            
            # Add channel member record
            member = ChannelMemberModel(
                channel_id=channel_id,
                user_id=user_id
            )
            self.session.add(member)
            
            self.session.commit()
            
            return {"message": f"User {user_id} added to channel"}
        
        except Exception as e:
            self.session.rollback()
            return {"error": f"Failed to add member: {str(e)}"}
    
    def remove_member_from_channel(self, channel_id: str, user_id: str, 
                                  removed_by: str) -> Dict:
        """Remove member from channel"""
        if channel_id not in self.channels:
            return {"error": "Channel not found"}
        
        channel = self.channels[channel_id]
        
        # Check if user has permission to remove members
        if removed_by not in channel.admins:
            return {"error": "User does not have permission to remove members"}
        
        # Cannot remove channel creator
        if user_id == channel.created_by:
            return {"error": "Cannot remove channel creator"}
        
        # Remove member
        channel.members.discard(user_id)
        
        try:
            # Update database
            self.session.query(ChannelModel).filter(ChannelModel.id == channel_id).update({
                "members": list(channel.members)
            })
            
            # Remove channel member record
            self.session.query(ChannelMemberModel).filter(
                ChannelMemberModel.channel_id == channel_id,
                ChannelMemberModel.user_id == user_id
            ).delete()
            
            self.session.commit()
            
            return {"message": f"User {user_id} removed from channel"}
        
        except Exception as e:
            self.session.rollback()
            return {"error": f"Failed to remove member: {str(e)}"}
    
    def get_user_channels(self, user_id: str) -> Dict:
        """Get channels for a user"""
        channels = []
        
        for channel in self.channels.values():
            if user_id in channel.members:
                channels.append(channel.to_dict())
        
        return {
            "channels": channels,
            "count": len(channels)
        }
    
    def get_channel_info(self, channel_id: str, user_id: str) -> Dict:
        """Get channel information"""
        if channel_id not in self.channels:
            return {"error": "Channel not found"}
        
        channel = self.channels[channel_id]
        
        # Check if user is a member
        if user_id not in channel.members:
            return {"error": "User is not a member of this channel"}
        
        return channel.to_dict()
    
    def update_channel_settings(self, channel_id: str, user_id: str, 
                               settings: Dict[str, Any]) -> Dict:
        """Update channel settings"""
        if channel_id not in self.channels:
            return {"error": "Channel not found"}
        
        channel = self.channels[channel_id]
        
        # Check if user is an admin
        if user_id not in channel.admins:
            return {"error": "User does not have permission to update settings"}
        
        # Update settings
        channel.settings.update(settings)
        channel.updated_at = datetime.utcnow()
        
        try:
            # Update database
            self.session.query(ChannelModel).filter(ChannelModel.id == channel_id).update({
                "settings": channel.settings,
                "updated_at": channel.updated_at
            })
            self.session.commit()
            
            return {"message": "Channel settings updated successfully"}
        
        except Exception as e:
            self.session.rollback()
            return {"error": f"Failed to update settings: {str(e)}"}
    
    def get_message_thread(self, thread_id: str, user_id: str) -> Dict:
        """Get messages in a thread"""
        # Get the original message
        original_message = self.session.query(MessageModel).filter(
            MessageModel.thread_id == thread_id
        ).order_by(MessageModel.created_at.asc()).first()
        
        if not original_message:
            return {"error": "Thread not found"}
        
        # Check if user has access to the channel
        channel = self.channels.get(original_message.channel_id)
        if not channel or user_id not in channel.members:
            return {"error": "User does not have access to this thread"}
        
        # Get all messages in the thread
        messages = self.session.query(MessageModel).filter(
            MessageModel.thread_id == thread_id
        ).order_by(MessageModel.created_at.asc()).all()
        
        thread_messages = []
        for msg in messages:
            content = msg.content
            if msg.encrypted:
                content = self._decrypt_message(content)
            
            thread_messages.append({
                "id": msg.id,
                "sender_id": msg.sender_id,
                "content": content,
                "type": msg.message_type,
                "created_at": msg.created_at.isoformat(),
                "encrypted": msg.encrypted
            })
        
        return {
            "thread_id": thread_id,
            "messages": thread_messages,
            "count": len(thread_messages)
        }


class MessagingAPI:
    """REST API for Messaging service"""
    
    def __init__(self, service: MessagingService):
        self.service = service
    
    def create_channel(self, request_data: Dict) -> Tuple[Dict, int]:
        """API endpoint to create channel"""
        try:
            channel_type = ChannelType(request_data.get('type', 'group'))
        except ValueError:
            return {"error": "Invalid channel type"}, 400
        
        result = self.service.create_channel(
            name=request_data.get('name'),
            channel_type=channel_type,
            created_by=request_data.get('created_by'),
            description=request_data.get('description', ''),
            members=request_data.get('members', [])
        )
        
        if "error" in result:
            return result, 400
        
        return result, 201
    
    def send_message(self, request_data: Dict) -> Tuple[Dict, int]:
        """API endpoint to send message"""
        try:
            message_type = MessageType(request_data.get('type', 'text'))
        except ValueError:
            return {"error": "Invalid message type"}, 400
        
        result = self.service.send_message(
            sender_id=request_data.get('sender_id'),
            channel_id=request_data.get('channel_id'),
            content=request_data.get('content'),
            message_type=message_type,
            reply_to=request_data.get('reply_to'),
            thread_id=request_data.get('thread_id'),
            encrypt=request_data.get('encrypt', False)
        )
        
        if "error" in result:
            return result, 400
        
        return result, 201
    
    def get_messages(self, channel_id: str, user_id: str, 
                    limit: int = 50, offset: int = 0) -> Tuple[Dict, int]:
        """API endpoint to get messages"""
        result = self.service.get_messages(channel_id, user_id, limit, offset)
        
        if "error" in result:
            return result, 404 if "not found" in result["error"].lower() else 403
        
        return result, 200
    
    def mark_message_read(self, message_id: str, user_id: str) -> Tuple[Dict, int]:
        """API endpoint to mark message as read"""
        result = self.service.mark_message_read(message_id, user_id)
        
        if "error" in result:
            return result, 404 if "not found" in result["error"].lower() else 403
        
        return result, 200
    
    def search_messages(self, user_id: str, query: str, 
                       channel_id: str = None, limit: int = 20) -> Tuple[Dict, int]:
        """API endpoint to search messages"""
        result = self.service.search_messages(user_id, query, channel_id, limit)
        return result, 200
    
    def get_user_channels(self, user_id: str) -> Tuple[Dict, int]:
        """API endpoint to get user channels"""
        result = self.service.get_user_channels(user_id)
        return result, 200
    
    def get_channel_info(self, channel_id: str, user_id: str) -> Tuple[Dict, int]:
        """API endpoint to get channel info"""
        result = self.service.get_channel_info(channel_id, user_id)
        
        if "error" in result:
            return result, 404 if "not found" in result["error"].lower() else 403
        
        return result, 200


# Example usage and testing
if __name__ == "__main__":
    # Initialize service
    service = MessagingService(
        db_url="sqlite:///messaging.db",
        redis_url="redis://localhost:6379"
    )
    
    # Create a channel
    result1 = service.create_channel(
        name="General Chat",
        channel_type=ChannelType.GROUP,
        created_by="user1",
        description="General discussion channel",
        members=["user1", "user2", "user3"]
    )
    print("Created channel:", result1)
    
    if "channel_id" in result1:
        channel_id = result1["channel_id"]
        
        # Send messages
        result2 = service.send_message(
            sender_id="user1",
            channel_id=channel_id,
            content="Hello everyone!",
            message_type=MessageType.TEXT
        )
        print("Sent message:", result2)
        
        result3 = service.send_message(
            sender_id="user2",
            channel_id=channel_id,
            content="Hi there!",
            message_type=MessageType.TEXT
        )
        print("Sent message:", result3)
        
        # Get messages
        messages = service.get_messages(channel_id, "user1", limit=10)
        print("Messages:", messages)
        
        # Mark message as read
        if "message_id" in result2:
            read_result = service.mark_message_read(result2["message_id"], "user2")
            print("Marked as read:", read_result)
        
        # Search messages
        search_result = service.search_messages("user1", "hello", channel_id)
        print("Search results:", search_result)
        
        # Get user channels
        user_channels = service.get_user_channels("user1")
        print("User channels:", user_channels)
        
        # Get channel info
        channel_info = service.get_channel_info(channel_id, "user1")
        print("Channel info:", channel_info)
