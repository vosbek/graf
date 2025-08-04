# Enhanced Repository Indexing Status Tracking Implementation

## Overview

This implementation enhances the repository indexing status tracking system in `src/api/routes/index.py` according to task 5 requirements. The enhancements provide detailed progress information, real-time updates, comprehensive error logging, and stage tracking for the indexing process.

## Key Features Implemented

### 1. Enhanced Data Models

#### ProcessingStage Enum
- `QUEUED`: Task is queued for processing
- `CLONING`: Repository cloning/preparation phase
- `ANALYZING`: Repository structure analysis
- `PARSING`: Code file parsing and processing
- `EMBEDDING`: CodeBERT embedding generation
- `STORING`: Data storage in ChromaDB and Neo4j
- `VALIDATING`: Data validation and consistency checks
- `COMPLETED`: Processing completed successfully
- `FAILED`: Processing failed

#### StageProgress Model
- Tracks progress for individual processing stages
- Includes start/completion timestamps
- Progress percentage and current operation details
- Processed/total items tracking

#### EmbeddingProgress Model
- Detailed embedding generation tracking
- Total chunks vs embedded chunks
- Embedding rate (chunks per second)
- Current file being processed
- Embedding-specific error tracking

#### IndexingError Model
- Comprehensive error information
- Error type and detailed message
- File path where error occurred
- Processing stage when error happened
- Timestamp and recoverability flag

#### EnhancedIndexingStatus Model
- Complete status tracking with all above components
- Stage history and current stage progress
- File processing metrics and language breakdown
- Performance metrics (throughput calculations)
- Error and warning collections

### 2. Real-time Status Updates

#### StatusUpdateManager Class
- Manages real-time status updates across WebSocket connections
- Provides methods for updating task status, adding stage progress, and error tracking
- Handles WebSocket connection management and broadcasting
- Automatic cleanup of disconnected clients

#### WebSocket Endpoint
- `/status/{task_id}/stream`: Real-time status streaming
- Supports heartbeat/ping-pong for connection health
- Broadcasts status updates to all connected clients
- Handles client disconnections gracefully

### 3. Enhanced API Endpoints

#### Enhanced Status Retrieval
- `GET /status/{task_id}`: Returns comprehensive EnhancedIndexingStatus
- `GET /status`: Enhanced overview with summary statistics and recent tasks
- `GET /status/{task_id}/logs`: Structured log retrieval with filtering

#### New Metrics Endpoints
- `GET /metrics/stages`: Stage performance metrics across all tasks
- `GET /metrics/embedding`: Embedding-specific performance metrics

### 4. Progress Callback Integration

#### Repository Processor Enhancement
- Added progress callback support to `process_repository()` and `process_local_repository()`
- Progress callbacks during file processing batches
- Real-time updates for cloning, analyzing, parsing, embedding, and storing phases
- Detailed progress information including current file and throughput metrics

### 5. Improved Error Handling and Logging

#### Structured Error Tracking
- Categorized error types with detailed context
- File-level error tracking with stack traces
- Recoverable vs non-recoverable error classification
- Stage-specific error attribution

#### Enhanced Logging
- Stage history with timestamps and durations
- Performance metrics collection
- Warning and error aggregation
- Structured log format for debugging

## Technical Implementation Details

### WebSocket Connection Management
```python
# Global connection tracking
active_websockets: Dict[str, List[WebSocket]] = {}

# Automatic cleanup of disconnected clients
# Heartbeat mechanism for connection health
# Error handling for WebSocket failures
```

### Progress Callback System
```python
# Progress callback in repository processor
async def notify_progress(stage: str, progress: float, details: Optional[Dict] = None):
    if progress_callback:
        await progress_callback(stage, progress, details)

# File-level progress tracking during batch processing
# Embedding progress with rate calculations
# Stage transition notifications
```

### Status Broadcasting
```python
# Automatic status updates to WebSocket clients
await StatusUpdateManager.broadcast_status_update(task_id, status)

# JSON serialization with datetime handling
message = {"type": "status_update", "task_id": task_id, "data": status.dict()}
```

## Requirements Fulfilled

### Requirement 6.1 ✅
- Real-time progress indicators showing current indexing status
- WebSocket streaming for live updates
- Detailed progress percentages and stage information

### Requirement 6.2 ✅
- Comprehensive error logging with file paths and failure reasons
- Structured error tracking with categorization
- Real-time error broadcasting to connected clients

### Requirement 6.3 ✅
- Detailed stage tracking (cloning, parsing, embedding, storing)
- Stage history with timestamps and durations
- Current operation descriptions for each stage

### Requirement 6.4 ✅
- Final statistics including processed files, generated chunks, and processing time
- Performance metrics (throughput calculations)
- Language breakdown and file type analysis

### Requirement 7.1 ✅
- Enhanced error logging and reporting for indexing operations
- Structured error information with context and recoverability

### Requirement 7.2 ✅
- Real-time progress updates including embedding generation status
- Embedding-specific progress tracking with rate calculations

### Requirement 7.3 ✅
- Improved existing task status tracking with detailed progress information
- Enhanced status models with comprehensive metrics

## Testing

The implementation includes a comprehensive test script (`test_enhanced_indexing_status.py`) that validates:
- Enhanced status object creation and manipulation
- JSON serialization/deserialization
- Error tracking functionality
- Status update mechanisms
- Model validation and data integrity

## Usage Examples

### WebSocket Client Connection
```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/index/status/task_123/stream');
ws.onmessage = (event) => {
    const update = JSON.parse(event.data);
    if (update.type === 'status_update') {
        updateProgressBar(update.data.overall_progress);
        updateCurrentStage(update.data.current_stage);
        updateEmbeddingProgress(update.data.embedding_progress);
    }
};
```

### REST API Usage
```python
# Get comprehensive status
response = await client.get('/api/v1/index/status/task_123')
status = response.json()

# Get structured logs
logs = await client.get('/api/v1/index/status/task_123/logs?level=ERROR')

# Get performance metrics
metrics = await client.get('/api/v1/index/metrics/stages')
```

## Performance Considerations

- Asynchronous WebSocket handling to prevent blocking
- Efficient JSON serialization with datetime handling
- Connection cleanup to prevent memory leaks
- Progress callback error handling to prevent processing interruption
- Batch processing with yield points for responsiveness

## Future Enhancements

- Persistent status storage for task recovery
- Advanced filtering and search in logs endpoint
- Performance alerting based on metrics
- Historical trend analysis for optimization
- Integration with monitoring systems (Prometheus, etc.)