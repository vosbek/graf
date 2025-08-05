import React, { useState, useEffect } from 'react';
import {
  Box, Typography, Paper, List, ListItem, ListItemText, ListItemIcon,
  Button, Chip, LinearProgress, Alert, Divider, IconButton, Tooltip
} from '@mui/material';
import {
  PlayArrow, CheckCircle, Error, Warning, Visibility, Refresh,
  Storage, Code, CloudSync, Analytics
} from '@mui/icons-material';
import { ApiService } from '../services/ApiService';

const STAGE_ICONS = {
  queued: <PlayArrow />,
  cloning: <CloudSync />,
  analyzing: <Analytics />,
  parsing: <Code />,
  embedding: <Storage />,
  storing: <Storage />,
  validating: <CheckCircle />,
  completed: <CheckCircle />,
  failed: <Error />
};

const STAGE_COLORS = {
  queued: 'info',
  cloning: 'primary',
  analyzing: 'primary', 
  parsing: 'primary',
  embedding: 'secondary',
  storing: 'secondary',
  validating: 'success',
  completed: 'success',
  failed: 'error'
};

const STAGE_LABELS = {
  queued: 'Queued',
  cloning: 'Cloning',
  analyzing: 'Analyzing',
  parsing: 'Parsing',
  embedding: 'Embedding',
  storing: 'Storing',
  validating: 'Validating',
  completed: 'Completed',
  failed: 'Failed'
};

function ActiveIndexingTasks({ onViewProgress }) {
  const [activeTasks, setActiveTasks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchActiveTasks();
    
    // Poll for updates every 5 seconds
    const interval = setInterval(fetchActiveTasks, 5000);
    return () => clearInterval(interval);
  }, []);

  const fetchActiveTasks = async () => {
    try {
      setLoading(true);
      setError('');
      
      // Fetch all indexing status
      const response = await ApiService.getIndexingStatus();
      
      // Filter for active tasks (not completed or failed)
      const active = response.tasks?.filter(task => 
        task.status === 'in_progress' || task.status === 'queued'
      ) || [];
      
      setActiveTasks(active);
    } catch (err) {
      console.error('Failed to fetch active tasks:', err);
      setError('Failed to load active indexing tasks');
    } finally {
      setLoading(false);
    }
  };

  const formatDuration = (seconds) => {
    if (seconds < 60) return `${seconds.toFixed(0)}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds.toFixed(0)}s`;
  };

  const handleViewProgress = (task) => {
    if (onViewProgress) {
      onViewProgress(task.task_id, task.repository_name);
    }
  };

  if (activeTasks.length === 0 && !loading && !error) {
    return null; // Don't show the section if no active tasks
  }

  return (
    <Paper sx={{ p: 3, mt: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6">
          Active Indexing Tasks ({activeTasks.length})
        </Typography>
        <Tooltip title="Refresh">
          <span>
            <IconButton onClick={fetchActiveTasks} disabled={loading}>
              <Refresh />
            </IconButton>
          </span>
        </Tooltip>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {loading && activeTasks.length === 0 && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, p: 2 }}>
          <LinearProgress sx={{ flexGrow: 1 }} />
          <Typography variant="body2" color="text.secondary">
            Loading active tasks...
          </Typography>
        </Box>
      )}

      {activeTasks.length > 0 && (
        <List>
          {activeTasks.map((task, index) => (
            <React.Fragment key={task.task_id}>
              <ListItem>
                <ListItemIcon>
                  {STAGE_ICONS[task.current_stage] || <PlayArrow />}
                </ListItemIcon>
                <ListItemText
                  primary={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                      <Typography variant="subtitle1">
                        {task.repository_name}
                      </Typography>
                      <Chip
                        size="small"
                        label={STAGE_LABELS[task.current_stage] || task.current_stage}
                        color={STAGE_COLORS[task.current_stage] || 'default'}
                      />
                    </Box>
                  }
                  secondary={
                    <Box>
                      <LinearProgress
                        variant="determinate"
                        value={task.overall_progress || 0}
                        sx={{ mb: 1, height: 6, borderRadius: 3 }}
                      />
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <Typography variant="body2" color="text.secondary">
                          {(task.overall_progress || 0).toFixed(1)}% complete
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          {formatDuration(task.processing_time || 0)}
                        </Typography>
                      </Box>
                      {task.current_file && (
                        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                          Processing: {task.current_file}
                        </Typography>
                      )}
                      <Box sx={{ display: 'flex', gap: 2, mt: 1 }}>
                        {task.processed_files > 0 && (
                          <Typography variant="body2" color="text.secondary">
                            Files: {task.processed_files}
                            {task.total_files && ` / ${task.total_files}`}
                          </Typography>
                        )}
                        {task.generated_chunks > 0 && (
                          <Typography variant="body2" color="text.secondary">
                            Chunks: {task.generated_chunks}
                          </Typography>
                        )}
                        {task.embedding_progress?.embedded_chunks > 0 && (
                          <Typography variant="body2" color="text.secondary">
                            Embeddings: {task.embedding_progress.embedded_chunks} / {task.embedding_progress.total_chunks}
                          </Typography>
                        )}
                      </Box>
                      {task.errors && task.errors.length > 0 && (
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1 }}>
                          <Warning color="warning" fontSize="small" />
                          <Typography variant="body2" color="warning.main">
                            {task.errors.length} error{task.errors.length !== 1 ? 's' : ''}
                          </Typography>
                        </Box>
                      )}
                    </Box>
                  }
                />
                <Button
                  variant="outlined"
                  size="small"
                  startIcon={<Visibility />}
                  onClick={() => handleViewProgress(task)}
                  sx={{ ml: 2 }}
                >
                  View Progress
                </Button>
              </ListItem>
              {index < activeTasks.length - 1 && <Divider />}
            </React.Fragment>
          ))}
        </List>
      )}

      {activeTasks.length > 0 && (
        <Box sx={{ mt: 2, p: 2, bgcolor: 'info.light', borderRadius: 1 }}>
          <Typography variant="body2" color="info.contrastText">
            💡 <strong>Tip:</strong> Click "View Progress" to see detailed real-time updates including 
            embedding generation progress, file processing stages, and any errors that occur during indexing.
          </Typography>
        </Box>
      )}
    </Paper>
  );
}

export default ActiveIndexingTasks;