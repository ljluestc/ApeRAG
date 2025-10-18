"""
Google Docs System Implementation

A comprehensive collaborative document editing system with features:
- Real-time collaborative editing
- Document versioning and history
- User permissions and access control
- Comments and suggestions
- Document sharing and collaboration
- Auto-save and conflict resolution
- Document templates
- Export to various formats

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
import difflib

import redis
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy import create_engine, func

Base = declarative_base()


class Permission(Enum):
    READ = "read"
    WRITE = "write"
    COMMENT = "comment"
    ADMIN = "admin"


class DocumentStatus(Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class OperationType(Enum):
    INSERT = "insert"
    DELETE = "delete"
    FORMAT = "format"
    COMMENT = "comment"
    SUGGEST = "suggest"


@dataclass
class DocumentOperation:
    """Represents a document operation for operational transformation"""
    id: str
    user_id: str
    document_id: str
    operation_type: OperationType
    position: int
    content: str = ""
    length: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    version: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "document_id": self.document_id,
            "operation_type": self.operation_type.value,
            "position": self.position,
            "content": self.content,
            "length": self.length,
            "timestamp": self.timestamp.isoformat(),
            "version": self.version
        }


@dataclass
class Document:
    """Document data structure"""
    id: str
    title: str
    content: str
    owner_id: str
    created_at: datetime
    updated_at: datetime
    status: DocumentStatus = DocumentStatus.DRAFT
    version: int = 1
    collaborators: Dict[str, Permission] = field(default_factory=dict)
    comments: List[Dict] = field(default_factory=list)
    suggestions: List[Dict] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "owner_id": self.owner_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "status": self.status.value,
            "version": self.version,
            "collaborators": {k: v.value for k, v in self.collaborators.items()},
            "comments": self.comments,
            "suggestions": self.suggestions
        }


class DocumentModel(Base):
    """Database model for documents"""
    __tablename__ = 'documents'
    
    id = Column(String(50), primary_key=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    owner_id = Column(String(50), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = Column(String(20), default=DocumentStatus.DRAFT.value)
    version = Column(Integer, default=1)
    collaborators = Column(JSON)  # {user_id: permission}
    comments = Column(JSON)  # List of comments
    suggestions = Column(JSON)  # List of suggestions


class DocumentVersionModel(Base):
    """Database model for document versions"""
    __tablename__ = 'document_versions'
    
    id = Column(Integer, primary_key=True)
    document_id = Column(String(50), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(50), nullable=False)
    change_summary = Column(Text)


class DocumentOperationModel(Base):
    """Database model for document operations"""
    __tablename__ = 'document_operations'
    
    id = Column(String(50), primary_key=True)
    document_id = Column(String(50), nullable=False, index=True)
    user_id = Column(String(50), nullable=False, index=True)
    operation_type = Column(String(20), nullable=False)
    position = Column(Integer, nullable=False)
    content = Column(Text)
    length = Column(Integer, default=0)
    timestamp = Column(DateTime, default=datetime.utcnow)
    version = Column(Integer, nullable=False)


class GoogleDocsService:
    """Main Google Docs service class"""
    
    def __init__(self, db_url: str, redis_url: str = "redis://localhost:6379"):
        self.db_url = db_url
        self.redis_url = redis_url
        self.redis_client = redis.from_url(redis_url)
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        
        # Configuration
        self.auto_save_interval = 30  # seconds
        self.max_operations_in_memory = 1000
        self.conflict_resolution_timeout = 5  # seconds
        
        # Active document sessions
        self.active_sessions = defaultdict(set)  # document_id -> set of user_ids
        self.document_operations = defaultdict(list)  # document_id -> list of operations
    
    def _get_document_cache_key(self, document_id: str) -> str:
        """Get Redis cache key for document"""
        return f"document:{document_id}"
    
    def _get_operations_cache_key(self, document_id: str) -> str:
        """Get Redis cache key for document operations"""
        return f"operations:{document_id}"
    
    def _get_user_session_key(self, user_id: str, document_id: str) -> str:
        """Get Redis cache key for user session"""
        return f"session:{user_id}:{document_id}"
    
    def _check_permission(self, user_id: str, document_id: str, required_permission: Permission) -> bool:
        """Check if user has required permission for document"""
        document = self.session.query(DocumentModel).filter(DocumentModel.id == document_id).first()
        if not document:
            return False
        
        # Owner has all permissions
        if document.owner_id == user_id:
            return True
        
        # Check collaborator permissions
        collaborators = document.collaborators or {}
        user_permission = collaborators.get(user_id)
        
        if not user_permission:
            return False
        
        # Check permission hierarchy
        permission_hierarchy = {
            Permission.READ: 1,
            Permission.COMMENT: 2,
            Permission.WRITE: 3,
            Permission.ADMIN: 4
        }
        
        return permission_hierarchy.get(user_permission, 0) >= permission_hierarchy.get(required_permission, 0)
    
    def create_document(self, title: str, owner_id: str, content: str = "", 
                       template_id: str = None) -> Dict:
        """Create a new document"""
        document_id = f"doc_{int(time.time() * 1000)}_{owner_id}"
        
        # Apply template if provided
        if template_id:
            template_content = self._get_template_content(template_id)
            if template_content:
                content = template_content
        
        document = DocumentModel(
            id=document_id,
            title=title,
            content=content,
            owner_id=owner_id,
            collaborators={owner_id: Permission.ADMIN.value}
        )
        
        try:
            self.session.add(document)
            
            # Create initial version
            version = DocumentVersionModel(
                document_id=document_id,
                version=1,
                content=content,
                created_by=owner_id,
                change_summary="Initial version"
            )
            self.session.add(version)
            
            self.session.commit()
            
            # Cache the document
            self._cache_document(document_id, content)
            
            return {
                "document_id": document_id,
                "title": title,
                "content": content,
                "owner_id": owner_id,
                "created_at": document.created_at.isoformat(),
                "version": 1,
                "status": DocumentStatus.DRAFT.value
            }
        
        except Exception as e:
            self.session.rollback()
            return {"error": f"Failed to create document: {str(e)}"}
    
    def get_document(self, document_id: str, user_id: str) -> Dict:
        """Get document with permission check"""
        if not self._check_permission(user_id, document_id, Permission.READ):
            return {"error": "Access denied"}
        
        # Check cache first
        cache_key = self._get_document_cache_key(document_id)
        cached_content = self.redis_client.get(cache_key)
        
        if cached_content:
            document = self.session.query(DocumentModel).filter(DocumentModel.id == document_id).first()
            if document:
                return {
                    "document_id": document_id,
                    "title": document.title,
                    "content": cached_content.decode(),
                    "owner_id": document.owner_id,
                    "created_at": document.created_at.isoformat(),
                    "updated_at": document.updated_at.isoformat(),
                    "version": document.version,
                    "status": document.status,
                    "collaborators": document.collaborators or {},
                    "cached": True
                }
        
        # Query database
        document = self.session.query(DocumentModel).filter(DocumentModel.id == document_id).first()
        if not document:
            return {"error": "Document not found"}
        
        # Cache the content
        self._cache_document(document_id, document.content)
        
        return {
            "document_id": document_id,
            "title": document.title,
            "content": document.content,
            "owner_id": document.owner_id,
            "created_at": document.created_at.isoformat(),
            "updated_at": document.updated_at.isoformat(),
            "version": document.version,
            "status": document.status,
            "collaborators": document.collaborators or {},
            "cached": False
        }
    
    def update_document(self, document_id: str, user_id: str, operations: List[Dict]) -> Dict:
        """Update document with operational transformation"""
        if not self._check_permission(user_id, document_id, Permission.WRITE):
            return {"error": "Access denied"}
        
        # Convert operations to DocumentOperation objects
        doc_operations = []
        for op_data in operations:
            operation = DocumentOperation(
                id=str(uuid.uuid4()),
                user_id=user_id,
                document_id=document_id,
                operation_type=OperationType(op_data["type"]),
                position=op_data["position"],
                content=op_data.get("content", ""),
                length=op_data.get("length", 0)
            )
            doc_operations.append(operation)
        
        # Apply operational transformation
        transformed_operations = self._apply_operational_transformation(document_id, doc_operations)
        
        # Apply operations to document content
        document = self.session.query(DocumentModel).filter(DocumentModel.id == document_id).first()
        if not document:
            return {"error": "Document not found"}
        
        # Apply operations to content
        new_content = self._apply_operations_to_content(document.content, transformed_operations)
        
        # Update document
        document.content = new_content
        document.version += 1
        document.updated_at = datetime.utcnow()
        
        # Save operations to database
        for operation in transformed_operations:
            op_model = DocumentOperationModel(
                id=operation.id,
                document_id=operation.document_id,
                user_id=operation.user_id,
                operation_type=operation.operation_type.value,
                position=operation.position,
                content=operation.content,
                length=operation.length,
                version=operation.version
            )
            self.session.add(op_model)
        
        # Create new version
        version = DocumentVersionModel(
            document_id=document_id,
            version=document.version,
            content=new_content,
            created_by=user_id,
            change_summary=f"Updated by {user_id}"
        )
        self.session.add(version)
        
        try:
            self.session.commit()
            
            # Update cache
            self._cache_document(document_id, new_content)
            
            # Notify other users
            self._notify_collaborators(document_id, user_id, transformed_operations)
            
            return {
                "document_id": document_id,
                "version": document.version,
                "content": new_content,
                "operations_applied": len(transformed_operations)
            }
        
        except Exception as e:
            self.session.rollback()
            return {"error": f"Failed to update document: {str(e)}"}
    
    def _apply_operational_transformation(self, document_id: str, new_operations: List[DocumentOperation]) -> List[DocumentOperation]:
        """Apply operational transformation to resolve conflicts"""
        # Get existing operations for this document
        existing_ops = self.document_operations.get(document_id, [])
        
        # Transform new operations against existing ones
        transformed_ops = []
        for new_op in new_operations:
            transformed_op = new_op
            for existing_op in existing_ops:
                transformed_op = self._transform_operation(transformed_op, existing_op)
            transformed_ops.append(transformed_op)
        
        # Add to in-memory operations
        self.document_operations[document_id].extend(transformed_ops)
        
        # Keep only recent operations in memory
        if len(self.document_operations[document_id]) > self.max_operations_in_memory:
            self.document_operations[document_id] = self.document_operations[document_id][-self.max_operations_in_memory:]
        
        return transformed_ops
    
    def _transform_operation(self, op1: DocumentOperation, op2: DocumentOperation) -> DocumentOperation:
        """Transform operation op1 against operation op2"""
        if op1.operation_type == OperationType.INSERT and op2.operation_type == OperationType.INSERT:
            if op1.position <= op2.position:
                return op1
            else:
                return DocumentOperation(
                    id=op1.id,
                    user_id=op1.user_id,
                    document_id=op1.document_id,
                    operation_type=op1.operation_type,
                    position=op1.position + len(op2.content),
                    content=op1.content,
                    length=op1.length,
                    timestamp=op1.timestamp,
                    version=op1.version
                )
        
        elif op1.operation_type == OperationType.INSERT and op2.operation_type == OperationType.DELETE:
            if op1.position <= op2.position:
                return op1
            else:
                return DocumentOperation(
                    id=op1.id,
                    user_id=op1.user_id,
                    document_id=op1.document_id,
                    operation_type=op1.operation_type,
                    position=op1.position - op2.length,
                    content=op1.content,
                    length=op1.length,
                    timestamp=op1.timestamp,
                    version=op1.version
                )
        
        elif op1.operation_type == OperationType.DELETE and op2.operation_type == OperationType.INSERT:
            if op1.position < op2.position:
                return op1
            else:
                return DocumentOperation(
                    id=op1.id,
                    user_id=op1.user_id,
                    document_id=op1.document_id,
                    operation_type=op1.operation_type,
                    position=op1.position + len(op2.content),
                    content=op1.content,
                    length=op1.length,
                    timestamp=op1.timestamp,
                    version=op1.version
                )
        
        elif op1.operation_type == OperationType.DELETE and op2.operation_type == OperationType.DELETE:
            if op1.position + op1.length <= op2.position:
                return op1
            elif op1.position >= op2.position + op2.length:
                return DocumentOperation(
                    id=op1.id,
                    user_id=op1.user_id,
                    document_id=op1.document_id,
                    operation_type=op1.operation_type,
                    position=op1.position - op2.length,
                    content=op1.content,
                    length=op1.length,
                    timestamp=op1.timestamp,
                    version=op1.version
                )
            else:
                # Overlapping deletes - merge them
                new_start = min(op1.position, op2.position)
                new_end = max(op1.position + op1.length, op2.position + op2.length)
                return DocumentOperation(
                    id=op1.id,
                    user_id=op1.user_id,
                    document_id=op1.document_id,
                    operation_type=op1.operation_type,
                    position=new_start,
                    content="",
                    length=new_end - new_start,
                    timestamp=op1.timestamp,
                    version=op1.version
                )
        
        return op1
    
    def _apply_operations_to_content(self, content: str, operations: List[DocumentOperation]) -> str:
        """Apply operations to document content"""
        # Sort operations by position (ascending) and timestamp (ascending)
        sorted_ops = sorted(operations, key=lambda x: (x.position, x.timestamp))
        
        result = content
        offset = 0
        
        for op in sorted_ops:
            pos = op.position + offset
            
            if op.operation_type == OperationType.INSERT:
                result = result[:pos] + op.content + result[pos:]
                offset += len(op.content)
            
            elif op.operation_type == OperationType.DELETE:
                end_pos = pos + op.length
                result = result[:pos] + result[end_pos:]
                offset -= op.length
        
        return result
    
    def share_document(self, document_id: str, owner_id: str, user_id: str, 
                      permission: Permission) -> Dict:
        """Share document with another user"""
        if not self._check_permission(owner_id, document_id, Permission.ADMIN):
            return {"error": "Only document owner can share"}
        
        document = self.session.query(DocumentModel).filter(DocumentModel.id == document_id).first()
        if not document:
            return {"error": "Document not found"}
        
        # Update collaborators
        collaborators = document.collaborators or {}
        collaborators[user_id] = permission.value
        document.collaborators = collaborators
        
        try:
            self.session.commit()
            return {"message": f"Document shared with {user_id} with {permission.value} permission"}
        except Exception as e:
            self.session.rollback()
            return {"error": f"Failed to share document: {str(e)}"}
    
    def add_comment(self, document_id: str, user_id: str, position: int, 
                   content: str, parent_comment_id: str = None) -> Dict:
        """Add a comment to the document"""
        if not self._check_permission(user_id, document_id, Permission.COMMENT):
            return {"error": "Access denied"}
        
        comment = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "position": position,
            "content": content,
            "parent_id": parent_comment_id,
            "created_at": datetime.utcnow().isoformat(),
            "replies": []
        }
        
        document = self.session.query(DocumentModel).filter(DocumentModel.id == document_id).first()
        if not document:
            return {"error": "Document not found"}
        
        comments = document.comments or []
        comments.append(comment)
        document.comments = comments
        
        try:
            self.session.commit()
            return {"comment_id": comment["id"], "message": "Comment added successfully"}
        except Exception as e:
            self.session.rollback()
            return {"error": f"Failed to add comment: {str(e)}"}
    
    def add_suggestion(self, document_id: str, user_id: str, position: int, 
                      original_text: str, suggested_text: str) -> Dict:
        """Add a suggestion to the document"""
        if not self._check_permission(user_id, document_id, Permission.WRITE):
            return {"error": "Access denied"}
        
        suggestion = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "position": position,
            "original_text": original_text,
            "suggested_text": suggested_text,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat()
        }
        
        document = self.session.query(DocumentModel).filter(DocumentModel.id == document_id).first()
        if not document:
            return {"error": "Document not found"}
        
        suggestions = document.suggestions or []
        suggestions.append(suggestion)
        document.suggestions = suggestions
        
        try:
            self.session.commit()
            return {"suggestion_id": suggestion["id"], "message": "Suggestion added successfully"}
        except Exception as e:
            self.session.rollback()
            return {"error": f"Failed to add suggestion: {str(e)}"}
    
    def get_document_history(self, document_id: str, user_id: str, limit: int = 20) -> Dict:
        """Get document version history"""
        if not self._check_permission(user_id, document_id, Permission.READ):
            return {"error": "Access denied"}
        
        versions = self.session.query(DocumentVersionModel).filter(
            DocumentVersionModel.document_id == document_id
        ).order_by(DocumentVersionModel.version.desc()).limit(limit).all()
        
        return {
            "document_id": document_id,
            "versions": [
                {
                    "version": v.version,
                    "created_at": v.created_at.isoformat(),
                    "created_by": v.created_by,
                    "change_summary": v.change_summary,
                    "content_preview": v.content[:200] + "..." if len(v.content) > 200 else v.content
                }
                for v in versions
            ]
        }
    
    def restore_version(self, document_id: str, user_id: str, version: int) -> Dict:
        """Restore document to a specific version"""
        if not self._check_permission(user_id, document_id, Permission.WRITE):
            return {"error": "Access denied"}
        
        version_record = self.session.query(DocumentVersionModel).filter(
            DocumentVersionModel.document_id == document_id,
            DocumentVersionModel.version == version
        ).first()
        
        if not version_record:
            return {"error": "Version not found"}
        
        document = self.session.query(DocumentModel).filter(DocumentModel.id == document_id).first()
        if not document:
            return {"error": "Document not found"}
        
        # Restore content
        document.content = version_record.content
        document.version += 1
        document.updated_at = datetime.utcnow()
        
        # Create new version record
        new_version = DocumentVersionModel(
            document_id=document_id,
            version=document.version,
            content=version_record.content,
            created_by=user_id,
            change_summary=f"Restored to version {version}"
        )
        self.session.add(new_version)
        
        try:
            self.session.commit()
            
            # Update cache
            self._cache_document(document_id, version_record.content)
            
            return {"message": f"Document restored to version {version}"}
        except Exception as e:
            self.session.rollback()
            return {"error": f"Failed to restore version: {str(e)}"}
    
    def export_document(self, document_id: str, user_id: str, format: str = "html") -> Dict:
        """Export document in various formats"""
        if not self._check_permission(user_id, document_id, Permission.READ):
            return {"error": "Access denied"}
        
        document = self.session.query(DocumentModel).filter(DocumentModel.id == document_id).first()
        if not document:
            return {"error": "Document not found"}
        
        if format == "html":
            content = self._convert_to_html(document.content)
        elif format == "markdown":
            content = self._convert_to_markdown(document.content)
        elif format == "plain":
            content = self._convert_to_plain_text(document.content)
        else:
            return {"error": "Unsupported format"}
        
        return {
            "document_id": document_id,
            "title": document.title,
            "content": content,
            "format": format,
            "exported_at": datetime.utcnow().isoformat()
        }
    
    def _convert_to_html(self, content: str) -> str:
        """Convert document content to HTML"""
        # Simple conversion - in practice, you'd use a proper rich text to HTML converter
        html_content = content.replace('\n', '<br>')
        return f"<html><body>{html_content}</body></html>"
    
    def _convert_to_markdown(self, content: str) -> str:
        """Convert document content to Markdown"""
        # Simple conversion - in practice, you'd use a proper rich text to Markdown converter
        return content
    
    def _convert_to_plain_text(self, content: str) -> str:
        """Convert document content to plain text"""
        # Remove HTML tags and convert to plain text
        import re
        plain_text = re.sub(r'<[^>]+>', '', content)
        return plain_text
    
    def _get_template_content(self, template_id: str) -> str:
        """Get template content by ID"""
        templates = {
            "blank": "",
            "meeting_notes": "# Meeting Notes\n\n## Attendees\n- \n\n## Agenda\n1. \n2. \n3. \n\n## Action Items\n- \n",
            "project_proposal": "# Project Proposal\n\n## Overview\n\n## Objectives\n\n## Timeline\n\n## Budget\n\n## Risks\n",
            "report": "# Report\n\n## Executive Summary\n\n## Introduction\n\n## Methodology\n\n## Results\n\n## Conclusion\n"
        }
        return templates.get(template_id, "")
    
    def _cache_document(self, document_id: str, content: str):
        """Cache document content"""
        cache_key = self._get_document_cache_key(document_id)
        self.redis_client.setex(cache_key, 3600, content)  # Cache for 1 hour
    
    def _notify_collaborators(self, document_id: str, user_id: str, operations: List[DocumentOperation]):
        """Notify other collaborators about changes"""
        # In a real implementation, this would use WebSockets or similar
        # to notify users in real-time
        pass
    
    def get_user_documents(self, user_id: str, limit: int = 20, offset: int = 0) -> Dict:
        """Get documents accessible to user"""
        # Get documents owned by user
        owned_docs = self.session.query(DocumentModel).filter(
            DocumentModel.owner_id == user_id
        ).order_by(DocumentModel.updated_at.desc())
        
        # Get documents shared with user
        shared_docs = self.session.query(DocumentModel).filter(
            DocumentModel.collaborators.contains({user_id: True})
        ).order_by(DocumentModel.updated_at.desc())
        
        # Combine and deduplicate
        all_docs = list(owned_docs) + list(shared_docs)
        unique_docs = {doc.id: doc for doc in all_docs}
        
        docs_list = list(unique_docs.values())
        docs_list.sort(key=lambda x: x.updated_at, reverse=True)
        
        total = len(docs_list)
        paginated_docs = docs_list[offset:offset + limit]
        
        return {
            "documents": [
                {
                    "id": doc.id,
                    "title": doc.title,
                    "owner_id": doc.owner_id,
                    "created_at": doc.created_at.isoformat(),
                    "updated_at": doc.updated_at.isoformat(),
                    "status": doc.status,
                    "version": doc.version,
                    "is_owner": doc.owner_id == user_id
                }
                for doc in paginated_docs
            ],
            "total": total,
            "limit": limit,
            "offset": offset
        }


class GoogleDocsAPI:
    """REST API for Google Docs service"""
    
    def __init__(self, service: GoogleDocsService):
        self.service = service
    
    def create_document(self, request_data: Dict) -> Tuple[Dict, int]:
        """API endpoint to create a document"""
        title = request_data.get('title')
        owner_id = request_data.get('owner_id')
        content = request_data.get('content', '')
        template_id = request_data.get('template_id')
        
        if not title or not owner_id:
            return {"error": "Title and owner_id are required"}, 400
        
        result = self.service.create_document(title, owner_id, content, template_id)
        
        if "error" in result:
            return result, 400
        
        return result, 201
    
    def get_document(self, document_id: str, user_id: str) -> Tuple[Dict, int]:
        """API endpoint to get a document"""
        result = self.service.get_document(document_id, user_id)
        
        if "error" in result:
            return result, 404 if "not found" in result["error"].lower() else 403
        
        return result, 200
    
    def update_document(self, document_id: str, user_id: str, request_data: Dict) -> Tuple[Dict, int]:
        """API endpoint to update a document"""
        operations = request_data.get('operations', [])
        
        if not operations:
            return {"error": "Operations are required"}, 400
        
        result = self.service.update_document(document_id, user_id, operations)
        
        if "error" in result:
            return result, 400
        
        return result, 200
    
    def share_document(self, document_id: str, request_data: Dict) -> Tuple[Dict, int]:
        """API endpoint to share a document"""
        owner_id = request_data.get('owner_id')
        user_id = request_data.get('user_id')
        permission = request_data.get('permission', 'read')
        
        if not owner_id or not user_id:
            return {"error": "Owner ID and user ID are required"}, 400
        
        try:
            permission_enum = Permission(permission)
        except ValueError:
            return {"error": "Invalid permission"}, 400
        
        result = self.service.share_document(document_id, owner_id, user_id, permission_enum)
        
        if "error" in result:
            return result, 400
        
        return result, 200
    
    def add_comment(self, document_id: str, request_data: Dict) -> Tuple[Dict, int]:
        """API endpoint to add a comment"""
        user_id = request_data.get('user_id')
        position = request_data.get('position')
        content = request_data.get('content')
        parent_comment_id = request_data.get('parent_comment_id')
        
        if not user_id or position is None or not content:
            return {"error": "User ID, position, and content are required"}, 400
        
        result = self.service.add_comment(document_id, user_id, position, content, parent_comment_id)
        
        if "error" in result:
            return result, 400
        
        return result, 201
    
    def export_document(self, document_id: str, user_id: str, format: str = "html") -> Tuple[Dict, int]:
        """API endpoint to export a document"""
        result = self.service.export_document(document_id, user_id, format)
        
        if "error" in result:
            return result, 404 if "not found" in result["error"].lower() else 403
        
        return result, 200


# Example usage and testing
if __name__ == "__main__":
    # Initialize service
    service = GoogleDocsService(
        db_url="sqlite:///googledocs.db",
        redis_url="redis://localhost:6379"
    )
    
    # Test creating a document
    result1 = service.create_document(
        title="My First Document",
        owner_id="user1",
        content="Hello, this is my first collaborative document!",
        template_id="blank"
    )
    print("Created document:", result1)
    
    # Test sharing document
    if "document_id" in result1:
        share_result = service.share_document(
            document_id=result1["document_id"],
            owner_id="user1",
            user_id="user2",
            permission=Permission.WRITE
        )
        print("Share result:", share_result)
        
        # Test adding a comment
        comment_result = service.add_comment(
            document_id=result1["document_id"],
            user_id="user2",
            position=10,
            content="Great document!"
        )
        print("Comment result:", comment_result)
        
        # Test updating document
        operations = [
            {
                "type": "insert",
                "position": 0,
                "content": "Updated: "
            }
        ]
        update_result = service.update_document(
            document_id=result1["document_id"],
            user_id="user2",
            operations=operations
        )
        print("Update result:", update_result)
        
        # Test getting document
        get_result = service.get_document(result1["document_id"], "user1")
        print("Get document:", get_result)
        
        # Test export
        export_result = service.export_document(
            document_id=result1["document_id"],
            user_id="user1",
            format="html"
        )
        print("Export result:", export_result)
        
        # Test document history
        history_result = service.get_document_history(result1["document_id"], "user1")
        print("Document history:", history_result)
