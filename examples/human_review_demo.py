"""
Human-in-the-loop review workflow demonstration.

This shows how to set up human review processes for content that requires
manual approval, including approval workflows and review queues.
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import List

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from guardrails import (
    HumanReviewManager, ApprovalWorkflow, ReviewStatus,
    ToxicityFilter, BusinessRuleChecker
)


class HumanReviewDemo:
    """Demonstrates human-in-the-loop review workflows."""
    
    def __init__(self):
        # Create review manager with short timeout for demo
        self.review_manager = HumanReviewManager(
            enabled=True,
            timeout_seconds=5,  # Very short for demo purposes
        )
        
        self.approval_workflow = ApprovalWorkflow(
            approval_keywords=["delete", "ban", "refund", "credit", "legal action"]
        )
    
    async def simulate_human_reviewer(self, review_manager: HumanReviewManager, delay: int = 2):
        """Simulate a human reviewer making decisions."""
        print("🧑‍💼 Human reviewer is standing by...")
        
        await asyncio.sleep(delay)  # Simulate review time
        
        # Check for pending reviews
        pending_reviews = review_manager.get_pending_reviews()
        
        for review in pending_reviews:
            print(f"🧑‍💼 Reviewing request {review.id}")
            print(f"   Content: {review.content[:50]}...")
            
            # Simple approval logic for demo
            content_lower = review.content.lower()
            
            if any(word in content_lower for word in ["delete", "ban", "remove"]):
                # Escalate sensitive operations
                review_manager.escalate_request(
                    review.id, 
                    "demo_reviewer",
                    "Sensitive operation requires manager approval"
                )
                print(f"   🔺 ESCALATED: Sensitive operation detected")
                
            elif any(word in content_lower for word in ["hate", "stupid", "idiot"]):
                # Reject toxic content
                review_manager.reject_request(
                    review.id,
                    "demo_reviewer", 
                    "Content violates community guidelines"
                )
                print(f"   ❌ REJECTED: Inappropriate content")
                
            else:
                # Approve normal content
                review_manager.approve_request(
                    review.id,
                    "demo_reviewer",
                    "Content approved after human review"
                )
                print(f"   ✅ APPROVED: Content meets guidelines")
    
    async def demo_human_review_workflow(self):
        """Demonstrate the human review workflow."""
        print("="*60)
        print("HUMAN REVIEW WORKFLOW DEMO")
        print("="*60)
        
        test_cases = [
            {
                "content": "Please help me delete my account permanently",
                "expected": "Should require human review due to 'delete' keyword"
            },
            {
                "content": "I hate this stupid system and want it banned",
                "expected": "Should be escalated or rejected due to toxic language"
            },
            {
                "content": "What's the weather like today?",
                "expected": "Should not require human review"
            },
            {
                "content": "Can you help me process a refund for my order?",
                "expected": "Should require human review due to 'refund' keyword"
            }
        ]
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n--- Test {i}: Human Review Check ---")
            print(f"Content: {test_case['content']}")
            print(f"Expected: {test_case['expected']}")
            
            # Start the human reviewer simulation
            reviewer_task = asyncio.create_task(
                self.simulate_human_reviewer(self.review_manager, delay=1)
            )
            
            try:
                # Check if content requires human review
                result = await self.review_manager.check(
                    test_case['content'],
                    context={"demo": True, "test_id": i}
                )
                
                print(f"Result: {result.message}")
                print(f"Passed: {result.passed}")
                
                if result.violations:
                    print("Violations:")
                    for violation in result.violations:
                        print(f"  - {violation}")
                
                if result.metadata:
                    print(f"Metadata: {result.metadata}")
            
            except Exception as e:
                print(f"Error: {e}")
            
            finally:
                # Cancel the reviewer task
                reviewer_task.cancel()
                try:
                    await reviewer_task
                except asyncio.CancelledError:
                    pass
    
    async def demo_approval_workflow(self):
        """Demonstrate the approval workflow."""
        print("\n" + "="*60)
        print("APPROVAL WORKFLOW DEMO")
        print("="*60)
        
        test_cases = [
            "Please delete all my data from the system",
            "I want to ban this user permanently",
            "Can you help me with my order?",
            "Process a refund for transaction #12345",
            "What are your business hours?"
        ]
        
        for i, content in enumerate(test_cases, 1):
            print(f"\n--- Test {i}: Approval Check ---")
            print(f"Content: {content}")
            
            try:
                result = await self.approval_workflow.check(
                    content,
                    context={"demo": True}
                )
                
                if result.passed:
                    print("✅ No approval required")
                else:
                    print("❌ Approval required")
                    print(f"Reason: {result.message}")
                    if result.violations:
                        for violation in result.violations:
                            print(f"  - {violation}")
            
            except Exception as e:
                print(f"Error: {e}")
    
    async def demo_review_queue_management(self):
        """Demonstrate review queue management."""
        print("\n" + "="*60)
        print("REVIEW QUEUE MANAGEMENT DEMO")
        print("="*60)
        
        # Add several items to the review queue by checking content that requires review
        review_contents = [
            "Delete my account and all associated data",
            "Ban this user for violating terms",
            "Process emergency refund for customer",
            "Remove all content from this thread"
        ]
        
        print("Adding items to review queue...")
        
        # Disable the review manager to prevent automatic timeouts
        self.review_manager.enabled = False
        
        # Manually add items to demonstrate queue management
        for content in review_contents:
            # Force add to queue for demo
            import uuid
            from datetime import datetime, timedelta
            from guardrails.human_review import ReviewRequest
            
            request = ReviewRequest(
                id=f"demo_{uuid.uuid4().hex[:8]}",
                content=content,
                context={"demo": True},
                timeout_at=datetime.now() + timedelta(seconds=30)
            )
            
            self.review_manager.review_queue.add_request(request)
        
        # Show queue status
        pending = self.review_manager.get_pending_reviews()
        print(f"📋 Queue status: {len(pending)} items pending review")
        
        for i, request in enumerate(pending, 1):
            print(f"  {i}. [{request.id}] {request.content[:50]}...")
        
        # Simulate reviewer processing the queue
        print(f"\n🧑‍💼 Processing review queue...")
        
        for request in pending[:2]:  # Process first 2 items
            if "delete" in request.content.lower():
                self.review_manager.escalate_request(
                    request.id,
                    "senior_reviewer", 
                    "Deletion request requires senior approval"
                )
                print(f"  🔺 Escalated: {request.id}")
            else:
                self.review_manager.approve_request(
                    request.id,
                    "reviewer",
                    "Approved after review"
                )
                print(f"  ✅ Approved: {request.id}")
        
        # Reject one item
        if len(pending) > 2:
            self.review_manager.reject_request(
                pending[2].id,
                "reviewer",
                "Request denied - policy violation"
            )
            print(f"  ❌ Rejected: {pending[2].id}")
        
        # Show final queue status
        remaining_pending = self.review_manager.get_pending_reviews()
        print(f"\n📋 Final queue status: {len(remaining_pending)} items still pending")
        
        # Re-enable for future tests
        self.review_manager.enabled = True


async def main():
    """Run human review demonstration."""
    print("LangGraph Guardrails - Human Review Workflow Demo")
    print("This demonstrates human-in-the-loop review processes")
    
    demo = HumanReviewDemo()
    
    try:
        await demo.demo_approval_workflow()
        await demo.demo_human_review_workflow()
        await demo.demo_review_queue_management()
        
        print("\n" + "="*60)
        print("HUMAN REVIEW DEMOS COMPLETED")
        print("="*60)
        print("✅ Human review workflow demonstration completed!")
        print("\nKey features demonstrated:")
        print("- Approval workflows for sensitive operations")
        print("- Human review queues and management")
        print("- Different review outcomes (approve/reject/escalate)")
        print("- Integration with automated guardrails")
        print("- Queue management and processing")
        print("\nIn production:")
        print("- Use longer timeouts for real human review")
        print("- Integrate with external review systems")
        print("- Implement persistent storage for review requests")
        print("- Add notification systems for reviewers")
        
    except Exception as e:
        print(f"Error running human review demo: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())