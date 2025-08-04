import React, { useState } from 'react';
import {
  Box, Typography, Paper, Button, TextField, Alert
} from '@mui/material';
import { PlayArrow } from '@mui/icons-material';
import RealTimeIndexingProgress from './RealTimeIndexingProgress';

function IndexingProgressTest() {
  const [taskId, setTaskId] = useState('');
  const [repositoryName, setRepositoryName] = useState('');
  const [showProgress, setShowProgress] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  const handleStartTest = () => {
    if (!taskId.trim() || !repositoryName.trim()) {
      setError('Please provide both task ID and repository name');
      return;
    }
    
    setError('');
    setResult(null);
    setShowProgress(true);
  };

  const handleComplete = (finalStatus) => {
    setShowProgress(false);
    setResult({
      message: 'Indexing completed successfully!',
      details: finalStatus
    });
  };

  const handleError = (errorStatus) => {
    setShowProgress(false);
    setError(`Indexing failed: ${errorStatus.error_message || 'Unknown error'}`);
  };

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>
        Real-Time Indexing Progress Test
      </Typography>
      
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          Test Real-Time Progress Monitoring
        </Typography>
        
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mb: 2 }}>
          <TextField
            label="Task ID"
            placeholder="e.g., test-repo_1691234567"
            value={taskId}
            onChange={(e) => setTaskId(e.target.value)}
            fullWidth
            helperText="Enter a task ID from an active indexing operation"
          />
          
          <TextField
            label="Repository Name"
            placeholder="e.g., test-repository"
            value={repositoryName}
            onChange={(e) => setRepositoryName(e.target.value)}
            fullWidth
            helperText="Enter the repository name being indexed"
          />
          
          <Button
            variant="contained"
            startIcon={<PlayArrow />}
            onClick={handleStartTest}
            disabled={showProgress}
          >
            {showProgress ? 'Monitoring...' : 'Start Monitoring'}
          </Button>
        </Box>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {result && (
          <Alert severity="success" sx={{ mb: 2 }}>
            <Typography variant="body2">
              <strong>{result.message}</strong>
            </Typography>
            {result.details && (
              <Typography variant="body2" sx={{ mt: 1 }}>
                Files: {result.details.processed_files} | 
                Chunks: {result.details.generated_chunks} | 
                Time: {result.details.processing_time?.toFixed(1)}s
              </Typography>
            )}
          </Alert>
        )}
      </Paper>

      {showProgress && (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            Live Progress Monitor
          </Typography>
          <RealTimeIndexingProgress
            taskId={taskId}
            repositoryName={repositoryName}
            onComplete={handleComplete}
            onError={handleError}
          />
        </Paper>
      )}

      <Paper sx={{ p: 3, mt: 3, bgcolor: 'info.light' }}>
        <Typography variant="h6" gutterBottom>
          How to Test
        </Typography>
        <Box component="ul" sx={{ pl: 3, mb: 0 }}>
          <li>Start a repository indexing operation from the Repository Indexer page</li>
          <li>Copy the task ID from the indexing operation (format: repository_timestamp)</li>
          <li>Enter the task ID and repository name in the form above</li>
          <li>Click "Start Monitoring" to see real-time progress updates</li>
          <li>The component will show live updates via WebSocket or polling fallback</li>
        </Box>
      </Paper>
    </Box>
  );
}

export default IndexingProgressTest;