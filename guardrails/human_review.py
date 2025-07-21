"""
Human-in-the-loop review guardrails and workflows.
"""

import asyncio
import os
from typing import Any, Dict, List, Optional, Callable, Union
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
from .base import BaseGuardrail, GuardrailResult, GuardrailSeverity


class ReviewStatus(Enum):
    """Status of a human review."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"
    TIMEOUT = "timeout"


@dataclass
class ReviewRequest:
    """A request for human review."""
    id: str
    content: str
    context: Dict[str, Any]
    created_at: datetime = field(default_factory=datetime.now)
    status: ReviewStatus = ReviewStatus.PENDING
    reviewer: Optional[str] = None
    review_notes: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    timeout_at: Optional[datetime] = None


class ReviewQueue:
    """Manages human review requests."""
    
    def __init__(self, max_queue_size: int = 1000):
        self.max_queue_size = max_queue_size
        self._queue: List[ReviewRequest] = []
        self._completed_reviews: Dict[str, ReviewRequest] = {}
    
    def add_request(self, request: ReviewRequest) -> bool:
        """Add a review request to the queue."""
        if len(self._queue) >= self.max_queue_size:
            return False
        
        self._queue.append(request)
        return True
    
    def get_pending_requests(self) -> List[ReviewRequest]:
        """Get all pending review requests."""
        return [req for req in self._queue if req.status == ReviewStatus.PENDING]
    
    def get_request(self, request_id: str) -> Optional[ReviewRequest]:
        """Get a specific review request."""
        # Check queue first
        for req in self._queue:
            if req.id == request_id:
                return req
        
        # Check completed reviews
        return self._completed_reviews.get(request_id)
    
    def complete_review(self, request_id: str, status: ReviewStatus, 
                       reviewer: str, notes: Optional[str] = None) -> bool:
        """Complete a review request."""
        for i, req in enumerate(self._queue):
            if req.id == request_id:
                req.status = status
                req.reviewer = reviewer
                req.review_notes = notes
                req.reviewed_at = datetime.now()
                
                # Move to completed reviews
                completed_req = self._queue.pop(i)
                self._completed_reviews[request_id] = completed_req
                return True
        
        return False
    
    def cleanup_expired_requests(self, timeout_seconds: int = 300) -> List[ReviewRequest]:
        """Remove expired requests from the queue."""
        now = datetime.now()
        expired = []
        
        for i, req in enumerate(self._queue):
            if req.timeout_at and now > req.timeout_at:
                req.status = ReviewStatus.TIMEOUT
                expired.append(req)
        
        # Remove expired requests
        self._queue = [req for req in self._queue if req.status != ReviewStatus.TIMEOUT]
        
        return expired


class HumanReviewManager(BaseGuardrail):
    """Manages human review workflows for content that requires manual approval."""
    
    def __init__(self, 
                 enabled: bool = True,
                 timeout_seconds: int = 300,
                 auto_approve_threshold: Optional[float] = None,
                 escalation_threshold: Optional[float] = None):
        super().__init__("human_review_manager", enabled)
        self.timeout_seconds = int(os.getenv("REVIEW_TIMEOUT_SECONDS", timeout_seconds))
        self.auto_approve_threshold = auto_approve_threshold
        self.escalation_threshold = escalation_threshold
        self.review_queue = ReviewQueue()
        self._review_handlers: Dict[str, Callable] = {}
    
    def register_review_handler(self, handler_name: str, handler: Callable) -> None:
        """Register a custom review handler."""
        self._review_handlers[handler_name] = handler
    
    async def check(self, content: str, context: Optional[Dict[str, Any]] = None) -> GuardrailResult:
        """Check if content requires human review."""
        if not self.enabled:
            return GuardrailResult(
                passed=True,
                severity=GuardrailSeverity.LOW,
                message="Human review disabled",
                violations=[],
                metadata={"human_review_enabled": False}
            )
        
        # Determine if review is needed based on context
        review_required = self._should_require_review(content, context or {})
        
        if not review_required:
            return GuardrailResult(
                passed=True,
                severity=GuardrailSeverity.LOW,
                message="No human review required",
                violations=[],
                metadata={"review_required": False}
            )
        
        # Create review request
        request_id = self._generate_request_id()
        timeout_at = datetime.now() + timedelta(seconds=self.timeout_seconds)
        
        review_request = ReviewRequest(
            id=request_id,
            content=content,
            context=context or {},
            timeout_at=timeout_at
        )
        
        # Add to review queue
        if not self.review_queue.add_request(review_request):
            return GuardrailResult(
                passed=False,
                severity=GuardrailSeverity.HIGH,
                message="Review queue full - cannot process request",
                violations=["Review queue at capacity"],
                metadata={"review_required": True, "queue_full": True}
            )
        
        # Wait for review or timeout
        result = await self._wait_for_review(request_id)
        
        return result
    
    def _should_require_review(self, content: str, context: Dict[str, Any]) -> bool:
        """Determine if content requires human review."""
        # Check context flags
        if context.get("requires_human_review", False):
            return True
        
        # Check for high-risk content indicators
        high_risk_keywords = [
            "delete", "remove", "ban", "suspend", "terminate",
            "legal", "lawsuit", "compliance", "violation",
            "sensitive", "confidential", "private"
        ]
        
        content_lower = content.lower()
        if any(keyword in content_lower for keyword in high_risk_keywords):
            return True
        
        # Check content length (very long content might need review)
        if len(content) > 5000:
            return True
        
        return False
    
    async def _wait_for_review(self, request_id: str) -> GuardrailResult:
        """Wait for human review to complete."""
        start_time = datetime.now()
        timeout_at = start_time + timedelta(seconds=self.timeout_seconds)
        
        while datetime.now() < timeout_at:
            request = self.review_queue.get_request(request_id)
            if not request:
                break
            
            if request.status != ReviewStatus.PENDING:
                return self._create_result_from_review(request)
            
            # Wait before checking again
            await asyncio.sleep(1)
        
        # Timeout occurred
        self.review_queue.complete_review(request_id, ReviewStatus.TIMEOUT, "system")
        
        return GuardrailResult(
            passed=False,
            severity=GuardrailSeverity.HIGH,
            message="Human review timeout",
            violations=["Review request timed out"],
            metadata={"request_id": request_id, "timeout_seconds": self.timeout_seconds}
        )
    
    def _create_result_from_review(self, request: ReviewRequest) -> GuardrailResult:
        """Create a GuardrailResult from a completed review."""
        if request.status == ReviewStatus.APPROVED:
            return GuardrailResult(
                passed=True,
                severity=GuardrailSeverity.LOW,
                message="Content approved by human reviewer",
                violations=[],
                metadata={
                    "request_id": request.id,
                    "reviewer": request.reviewer,
                    "review_notes": request.review_notes
                }
            )
        elif request.status == ReviewStatus.REJECTED:
            return GuardrailResult(
                passed=False,
                severity=GuardrailSeverity.HIGH,
                message="Content rejected by human reviewer",
                violations=[f"Rejected: {request.review_notes or 'No reason provided'}"],
                metadata={
                    "request_id": request.id,
                    "reviewer": request.reviewer,
                    "review_notes": request.review_notes
                }
            )
        elif request.status == ReviewStatus.ESCALATED:
            return GuardrailResult(
                passed=False,
                severity=GuardrailSeverity.CRITICAL,
                message="Content escalated for further review",
                violations=["Content requires escalated review"],
                metadata={
                    "request_id": request.id,
                    "reviewer": request.reviewer,
                    "review_notes": request.review_notes
                }
            )
        else:  # TIMEOUT
            return GuardrailResult(
                passed=False,
                severity=GuardrailSeverity.HIGH,
                message="Human review timeout",
                violations=["Review request timed out"],
                metadata={"request_id": request.id}
            )
    
    def _generate_request_id(self) -> str:
        """Generate a unique request ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"review_{timestamp}_{id(self) % 10000}"
    
    # Manual review interface methods
    def get_pending_reviews(self) -> List[ReviewRequest]:
        """Get all pending review requests."""
        return self.review_queue.get_pending_requests()
    
    def approve_request(self, request_id: str, reviewer: str, notes: Optional[str] = None) -> bool:
        """Approve a review request."""
        return self.review_queue.complete_review(request_id, ReviewStatus.APPROVED, reviewer, notes)
    
    def reject_request(self, request_id: str, reviewer: str, notes: Optional[str] = None) -> bool:
        """Reject a review request."""
        return self.review_queue.complete_review(request_id, ReviewStatus.REJECTED, reviewer, notes)
    
    def escalate_request(self, request_id: str, reviewer: str, notes: Optional[str] = None) -> bool:
        """Escalate a review request."""
        return self.review_queue.complete_review(request_id, ReviewStatus.ESCALATED, reviewer, notes)


class ApprovalWorkflow(BaseGuardrail):
    """Simple approval workflow for sensitive operations."""
    
    def __init__(self, approval_keywords: Optional[List[str]] = None, enabled: bool = True):
        super().__init__("approval_workflow", enabled)
        self.approval_keywords = approval_keywords or [
            "delete", "remove", "ban", "suspend", "terminate",
            "refund", "credit", "payment", "billing"
        ]
    
    async def check(self, content: str, context: Optional[Dict[str, Any]] = None) -> GuardrailResult:
        """Check if content requires approval."""
        requires_approval = False
        triggered_keywords = []
        
        content_lower = content.lower()
        for keyword in self.approval_keywords:
            if keyword in content_lower:
                requires_approval = True
                triggered_keywords.append(keyword)
        
        if requires_approval:
            return GuardrailResult(
                passed=False,
                severity=GuardrailSeverity.HIGH,
                message="Content requires manual approval",
                violations=[f"Approval required due to keywords: {', '.join(triggered_keywords)}"],
                metadata={"triggered_keywords": triggered_keywords}
            )
        
        return GuardrailResult(
            passed=True,
            severity=GuardrailSeverity.LOW,
            message="No approval required",
            violations=[],
            metadata={"triggered_keywords": []}
        )