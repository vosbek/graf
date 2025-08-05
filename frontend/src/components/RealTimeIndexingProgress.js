import React, { useState, useEffect, useRef } from 'react';
import {
  Box, Typography, Paper, LinearProgress, Alert, Chip, Card, CardContent,
  List, ListItem, ListItemText, ListItemIcon, Divider, Collapse,
  IconButton, Accordion, AccordionSummary, AccordionDetails
} from '@mui/material';
import {
  PlayArrow, CheckCircle, Error, Warning, Info, ExpandMore,
  Code, Storage, CloudSync, Analytics, Folder, Speed
} from '@mui/icons-material';
import IndexingTroubleshootingGuide from './IndexingTroubleshootingGuide';
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
  cloning: 'Cloning Repository',
  analyzing: 'Analyzing Structure',
  parsing: 'Parsing Files',
  embedding: 'Generating Embeddings',
  storing: 'Storing Data',
  validating: 'Validating Results',
  completed: 'Completed',
  failed: 'Failed'
};

function RealTimeIndexingProgress({ taskId, repositoryName, onComplete, onError }) {
  const [status, setStatus] = useState(null);
  const [connected, setConnected] = useState(false);
  const [connectionError, setConnectionError] = useState(null);
  const [expandedSections, setExpandedSections] = useState({
    stages: true,
    embedding: true,
    errors: true,
    troubleshooting: false
  });
  
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const pollingIntervalRef = useRef(null);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 5;

  useEffect(() => {
    if (taskId) {
      connectWebSocket();
    }

    return () => {
      cleanup();
    };
  }, [taskId]);

  const cleanup = () => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
  };

  const startPolling = () => {
    console.log('Starting polling fallback for task:', taskId);
    pollingIntervalRef.current = setInterval(async () => {
      try {
        const statusData = await ApiService.getIndexingStatus(taskId);
        setStatus(statusData);
        
        // Check if indexing is complete
        if (statusData.status === 'completed' && onComplete) {
          clearInterval(pollingIntervalRef.current);
          onComplete(statusData);
        } else if (statusData.status === 'failed' && onError) {
          clearInterval(pollingIntervalRef.current);
          onError(statusData);
        }
      } catch (error) {
        console.error('Polling error:', error);
        setConnectionError('Failed to fetch status updates');
      }
    }, 2000); // Poll every 2 seconds
  };

  const connectWebSocket = () => {
    try {
      // Respect REACT_APP_API_URL for WebSocket connections, providing a robust fallback
      // for various development and production environments.
      const apiUrl = process.env.REACT_APP_API_URL;
      let wsUrl;

      if (apiUrl) {
        // Base the WebSocket URL on the explicit API URL
        const url = new URL(apiUrl);
        const protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
        wsUrl = `${protocol}//${url.host}/api/v1/index/status/${taskId}/stream`;
      } else {
        // Fallback for standard local development (e.g., create-react-app proxy)
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        wsUrl = `${protocol}//${host}/api/v1/index/status/${taskId}/stream`;
      }
      
      console.log('Connecting to WebSocket:', wsUrl);
      wsRef.current = new WebSocket(wsUrl);

      wsRef.current.onopen = () => {
        console.log('WebSocket connected for task:', taskId);
        setConnected(true);
        setConnectionError(null);
        reconnectAttempts.current = 0;
      };

      wsRef.current.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          
          if (message.type === 'status_update' && message.data) {
            setStatus(message.data);
            
            // Check if indexing is complete
            if (message.data.status === 'completed' && onComplete) {
              onComplete(message.data);
            } else if (message.data.status === 'failed' && onError) {
              onError(message.data);
            }
          } else if (message.type === 'error') {
            setConnectionError(message.message);
            if (onError) {
              onError({ error_message: message.message });
            }
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };

      wsRef.current.onclose = (event) => {
        console.log('WebSocket closed:', event.code, event.reason);
        setConnected(false);
        
        // Attempt to reconnect if not a normal closure
        if (event.code !== 1000 && reconnectAttempts.current < maxReconnectAttempts) {
          const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000);
          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttempts.current++;
            console.log(`Reconnecting... attempt ${reconnectAttempts.current}`);
            connectWebSocket();
          }, delay);
        } else if (reconnectAttempts.current >= maxReconnectAttempts) {
          // Fall back to polling if WebSocket fails
          console.log('WebSocket reconnection failed, falling back to polling');
          startPolling();
        }
      };

      wsRef.current.onerror = (error) => {
        console.error('WebSocket error:', error);
        setConnectionError('Connection error occurred');
      };

    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
      setConnectionError('Failed to establish connection');
    }
  };

  const handleSectionToggle = (section) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }));
  };

  const formatDuration = (seconds) => {
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds.toFixed(1)}s`;
  };

  const formatRate = (rate) => {
    if (rate < 1) return `${(rate * 1000).toFixed(1)}/s`;
    return `${rate.toFixed(1)}/s`;
  };

  const renderConnectionStatus = () => {
    let statusLabel = 'Disconnected';
    let statusColor = 'error';
    let statusIcon = <Error />;
    let connectionMessage = null;

    if (connected) {
      statusLabel = 'Connected';
      statusColor = 'success';
      statusIcon = <CheckCircle />;
    } else if (reconnectAttempts.current > 0) {
      statusLabel = `Reconnecting (attempt ${reconnectAttempts.current})`;
      statusColor = 'warning';
      statusIcon = <CloudSync />;
      connectionMessage = "Attempting to re-establish connection...";
    }

    return (
      <Box sx={{ mb: 2 }}>
        <Chip
          icon={statusIcon}
          label={statusLabel}
          color={statusColor}
          size="medium" // Make it slightly larger
          sx={{ fontSize: '0.9rem', padding: '4px 8px' }} // Adjust padding/font size
        />
        {connectionMessage && (
          <Alert severity="info" sx={{ mt: 1 }}>
            {connectionMessage}
          </Alert>
        )}
        {connectionError && (
          <Alert severity="error" sx={{ mt: 1 }}>
            Connection issue: {connectionError}
          </Alert>
        )}
      </Box>
    );
  };

  const renderOverallProgress = () => {
    if (!status) return null;

    return (
      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h6">
              {repositoryName || status.repository_name}
            </Typography>
            <Chip
              icon={STAGE_ICONS[status.current_stage]}
              label={STAGE_LABELS[status.current_stage]}
              color={STAGE_COLORS[status.current_stage]}
            />
          </Box>
          
          <LinearProgress
            variant="determinate"
            value={status.overall_progress}
            sx={{ mb: 1, height: 8, borderRadius: 4 }}
          />
          
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="body2" color="text.secondary">
              {status.overall_progress.toFixed(1)}% complete
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {formatDuration(status.processing_time)}
            </Typography>
          </Box>

          {status.current_file && (
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              Current: {status.current_file}
            </Typography>
          )}
        </CardContent>
      </Card>
    );
  };

  const renderStageProgress = () => {
    if (!status || !status.stage_history) return null;

    return (
      <Accordion expanded={expandedSections.stages} onChange={() => handleSectionToggle('stages')}>
        <AccordionSummary expandIcon={<ExpandMore />}>
          <Typography variant="h6">Processing Stages</Typography>
        </AccordionSummary>
        <AccordionDetails>
          <List>
            {status.stage_history.map((stage, index) => (
              <React.Fragment key={index}>
                <ListItem>
                  <ListItemIcon>
                    {STAGE_ICONS[stage.stage]}
                  </ListItemIcon>
                  <ListItemText
                    primary={
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Typography>{STAGE_LABELS[stage.stage]}</Typography>
                        <Chip
                          size="small"
                          label={stage.completed_at ? 'Completed' : 'In Progress'}
                          color={stage.completed_at ? 'success' : 'primary'}
                        />
                      </Box>
                    }
                    secondary={
                      <Box>
                        <Typography variant="body2">
                          Started: {new Date(stage.started_at).toLocaleTimeString()}
                          {stage.completed_at && (
                            <> • Completed: {new Date(stage.completed_at).toLocaleTimeString()}</>
                          )}
                        </Typography>
                        {stage.current_operation && (
                          <Typography variant="body2" color="text.secondary">
                            {stage.current_operation}
                          </Typography>
                        )}
                        {stage.progress_percentage > 0 && (
                          <LinearProgress
                            variant="determinate"
                            value={stage.progress_percentage}
                            sx={{ mt: 1, height: 4 }}
                          />
                        )}
                      </Box>
                    }
                  />
                </ListItem>
                {index < status.stage_history.length - 1 && <Divider />}
              </React.Fragment>
            ))}
          </List>
        </AccordionDetails>
      </Accordion>
    );
  };

  const renderEmbeddingProgress = () => {
    if (!status || !status.embedding_progress || status.embedding_progress.total_chunks === 0) {
      return null;
    }

    const embeddingProgress = status.embedding_progress;
    const progressPercentage = embeddingProgress.total_chunks > 0 
      ? (embeddingProgress.embedded_chunks / embeddingProgress.total_chunks) * 100 
      : 0;

    return (
      <Accordion expanded={expandedSections.embedding} onChange={() => handleSectionToggle('embedding')}>
        <AccordionSummary expandIcon={<ExpandMore />}>
          <Typography variant="h6">Embedding Generation</Typography>
        </AccordionSummary>
        <AccordionDetails>
          <Box>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
              <Typography variant="body2">
                {embeddingProgress.embedded_chunks} / {embeddingProgress.total_chunks} chunks
              </Typography>
              <Typography variant="body2">
                {formatRate(embeddingProgress.embedding_rate)} chunks/sec
              </Typography>
            </Box>
            
            <LinearProgress
              variant="determinate"
              value={progressPercentage}
              sx={{ mb: 2, height: 6, borderRadius: 3 }}
            />

            {embeddingProgress.current_file && (
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                Processing: {embeddingProgress.current_file}
              </Typography>
            )}

            {embeddingProgress.estimated_completion && (
              <Typography variant="body2" color="text.secondary">
                Estimated completion: {new Date(embeddingProgress.estimated_completion).toLocaleTimeString()}
              </Typography>
            )}

            {embeddingProgress.embedding_errors && embeddingProgress.embedding_errors.length > 0 && (
              <Alert severity="warning" sx={{ mt: 2 }}>
                <Typography variant="body2">
                  {embeddingProgress.embedding_errors.length} embedding errors occurred
                </Typography>
                <List dense>
                  {embeddingProgress.embedding_errors.slice(0, 3).map((error, index) => (
                    <ListItem key={index} sx={{ py: 0 }}>
                      <ListItemText primary={error} />
                    </ListItem>
                  ))}
                  {embeddingProgress.embedding_errors.length > 3 && (
                    <Typography variant="body2" color="text.secondary">
                      ... and {embeddingProgress.embedding_errors.length - 3} more
                    </Typography>
                  )}
                </List>
              </Alert>
            )}
          </Box>
        </AccordionDetails>
      </Accordion>
    );
  };

  const renderFileProgress = () => {
    if (!status) return null;

    return (
      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>File Processing</Typography>
          
          <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 2 }}>
            <Box>
              <Typography variant="body2" color="text.secondary">Files Processed</Typography>
              <Typography variant="h6">
                {status.processed_files}
                {status.total_files && ` / ${status.total_files}`}
              </Typography>
            </Box>
            
            <Box>
              <Typography variant="body2" color="text.secondary">Chunks Generated</Typography>
              <Typography variant="h6">{status.generated_chunks}</Typography>
            </Box>
            
            <Box>
              <Typography variant="body2" color="text.secondary">Chunks Stored</Typography>
              <Typography variant="h6">{status.stored_chunks}</Typography>
            </Box>
            
            {status.throughput_files_per_second > 0 && (
              <Box>
                <Typography variant="body2" color="text.secondary">File Rate</Typography>
                <Typography variant="h6">
                  {formatRate(status.throughput_files_per_second)} files/sec
                </Typography>
              </Box>
            )}
          </Box>

          {status.files_by_language && Object.keys(status.files_by_language).length > 0 && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Files by Language
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {Object.entries(status.files_by_language).map(([language, count]) => (
                  <Chip
                    key={language}
                    label={`${language}: ${count}`}
                    size="small"
                    variant="outlined"
                  />
                ))}
              </Box>
            </Box>
          )}
        </CardContent>
      </Card>
    );
  };

  const renderErrors = () => {
    if (!status || !status.errors || status.errors.length === 0) return null;

    return (
      <Accordion expanded={expandedSections.errors} onChange={() => handleSectionToggle('errors')}>
        <AccordionSummary expandIcon={<ExpandMore />}>
          <Typography variant="h6" color="error">
            Errors ({status.errors.length})
          </Typography>
        </AccordionSummary>
        <AccordionDetails>
          <List>
            {status.errors.map((error, index) => (
              <React.Fragment key={index}>
                <ListItem alignItems="flex-start">
                  <ListItemIcon sx={{ mt: 1 }}>
                    <Error color="error" />
                  </ListItemIcon>
                  <ListItemText
                    primary={
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                        <Typography variant="subtitle1" color="error">
                          {error.error_type}
                        </Typography>
                        <Chip
                          size="small"
                          label={error.recoverable ? 'Recoverable' : 'Fatal'}
                          color={error.recoverable ? 'warning' : 'error'}
                        />
                        <Typography variant="caption" color="text.secondary" sx={{ ml: 'auto' }}>
                          {new Date(error.timestamp).toLocaleString()}
                        </Typography>
                      </Box>
                    }
                    secondary={
                      <Box sx={{ mt: 0.5 }}>
                        <Typography variant="body2" color="text.primary" sx={{ mb: 0.5 }}>
                          {error.error_message}
                        </Typography>
                        {error.file_path && (
                          <Typography variant="body2" color="text.secondary">
                            <strong>File:</strong> {error.file_path}
                          </Typography>
                        )}
                        <Typography variant="body2" color="text.secondary">
                          <strong>Stage:</strong> {STAGE_LABELS[error.stage]}
                        </Typography>
                        {error.stack_trace && (
                          <Box sx={{ mt: 1, bgcolor: 'error.light', p: 1, borderRadius: 1, overflowX: 'auto' }}>
                            <Typography variant="caption" component="pre" sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                              {error.stack_trace}
                            </Typography>
                          </Box>
                        )}
                      </Box>
                    }
                  />
                </ListItem>
                {index < status.errors.length - 1 && <Divider component="li" />}
              </React.Fragment>
            ))}
          </List>
        </AccordionDetails>
      </Accordion>
    );
  };

  const renderTroubleshooting = () => {
    if (!status || !status.errors || status.errors.length === 0) return null;

    return (
      <Accordion expanded={expandedSections.troubleshooting} onChange={() => handleSectionToggle('troubleshooting')}>
        <AccordionSummary expandIcon={<ExpandMore />}>
          <Typography variant="h6" color="primary">
            Troubleshooting Guide
          </Typography>
        </AccordionSummary>
        <AccordionDetails>
          <IndexingTroubleshootingGuide 
            errors={status.errors} 
            showGeneralTips={false}
          />
        </AccordionDetails>
      </Accordion>
    );
  };

  const renderWarnings = () => {
    if (!status || !status.warnings || status.warnings.length === 0) return null;

    return (
      <Alert severity="warning" sx={{ mb: 2 }}>
        <Typography variant="body2" gutterBottom>
          Warnings ({status.warnings.length}):
        </Typography>
        <List dense>
          {status.warnings.slice(0, 5).map((warning, index) => (
            <ListItem key={index} sx={{ py: 0 }}>
              <ListItemIcon sx={{ minWidth: 24 }}>
                <Warning fontSize="small" />
              </ListItemIcon>
              <ListItemText primary={warning} />
            </ListItem>
          ))}
          {status.warnings.length > 5 && (
            <Typography variant="body2" color="text.secondary">
              ... and {status.warnings.length - 5} more warnings
            </Typography>
          )}
        </List>
      </Alert>
    );
  };

  if (!taskId) {
    return (
      <Alert severity="info">
        No active indexing task to monitor.
      </Alert>
    );
  }

  return (
    <Box>
      {renderConnectionStatus()}
      {renderOverallProgress()}
      {renderFileProgress()}
      {renderStageProgress()}
      {renderEmbeddingProgress()}
      {renderWarnings()}
      {renderErrors()}
      {renderTroubleshooting()}
    </Box>
  );
}

export default RealTimeIndexingProgress;