#!/usr/bin/env python3
"""
Test script for enhanced indexing status tracking.
"""

import asyncio
import json
from datetime import datetime
from src.api.routes.index import (
    EnhancedIndexingStatus, ProcessingStage, ProcessingStatus,
    EmbeddingProgress, IndexingError, StatusUpdateManager
)

async def test_enhanced_status_tracking():
    """Test the enhanced status tracking functionality."""
    print("Testing Enhanced Indexing Status Tracking...")
    
    # Test 1: Create enhanced status object
    print("\n1. Testing EnhancedIndexingStatus creation...")
    status = EnhancedIndexingStatus(
        repository_name="test-repo",
        task_id="test_123",
        run_id="run_456",
        status=ProcessingStatus.IN_PROGRESS,
        current_stage=ProcessingStage.CLONING,
        started_at=datetime.now()
    )
    
    print(f"✓ Created status for {status.repository_name}")
    print(f"  Task ID: {status.task_id}")
    print(f"  Current stage: {status.current_stage}")
    print(f"  Overall progress: {status.overall_progress}%")
    
    # Test 2: Test embedding progress
    print("\n2. Testing EmbeddingProgress...")
    embedding_progress = EmbeddingProgress(
        total_chunks=100,
        embedded_chunks=75,
        embedding_rate=12.5,
        current_file="src/main/java/TestService.java"
    )
    
    status.embedding_progress = embedding_progress
    print(f"✓ Embedding progress: {embedding_progress.embedded_chunks}/{embedding_progress.total_chunks}")
    print(f"  Rate: {embedding_progress.embedding_rate} chunks/sec")
    print(f"  Current file: {embedding_progress.current_file}")
    
    # Test 3: Test error tracking
    print("\n3. Testing IndexingError...")
    error = IndexingError(
        error_type="parsing_error",
        error_message="Failed to parse Java file",
        file_path="src/main/java/BrokenFile.java",
        stage=ProcessingStage.PARSING,
        timestamp=datetime.now(),
        recoverable=True
    )
    
    status.errors.append(error)
    print(f"✓ Added error: {error.error_type}")
    print(f"  Message: {error.error_message}")
    print(f"  File: {error.file_path}")
    print(f"  Recoverable: {error.recoverable}")
    
    # Test 4: Test JSON serialization
    print("\n4. Testing JSON serialization...")
    try:
        status_dict = status.dict()
        json_str = json.dumps(status_dict, default=str, indent=2)
        print("✓ JSON serialization successful")
        print(f"  JSON length: {len(json_str)} characters")
        
        # Test deserialization
        parsed_dict = json.loads(json_str)
        print("✓ JSON deserialization successful")
        
    except Exception as e:
        print(f"✗ JSON serialization failed: {e}")
        return False
    
    # Test 5: Test status update manager (mock)
    print("\n5. Testing StatusUpdateManager (mock)...")
    
    # Mock the task_status dictionary
    from src.api.routes.index import task_status
    task_status["test_123"] = status
    
    try:
        await StatusUpdateManager.update_task_status("test_123", {
            "overall_progress": 85.0,
            "current_stage": ProcessingStage.STORING,
            "processed_files": 50
        })
        print("✓ Status update successful")
        print(f"  Updated progress: {status.overall_progress}%")
        print(f"  Updated stage: {status.current_stage}")
        print(f"  Processed files: {status.processed_files}")
        
    except Exception as e:
        print(f"✗ Status update failed: {e}")
        return False
    
    print("\n✅ All tests passed! Enhanced indexing status tracking is working correctly.")
    return True

if __name__ == "__main__":
    success = asyncio.run(test_enhanced_status_tracking())
    exit(0 if success else 1)