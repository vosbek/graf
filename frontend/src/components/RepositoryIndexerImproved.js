import React, { useState, useRef, useEffect } from 'react';
import {
  Box, Typography, Paper, TextField, Button, Alert, LinearProgress,
  Grid, Chip, Card, CardContent, ToggleButton, ToggleButtonGroup,
  Divider, List, ListItem, ListItemText, ListItemIcon, Collapse
} from '@mui/material';
import { 
  FolderOpen, PlayArrow, CheckCircle, Error, Info, GitHub, Computer,
  ExpandMore, ExpandLess, WifiOff, Wifi, Speed, Storage
} from '@mui/icons-material';
import { ApiService } from '../services/ApiService';
import { useSystemHealth } from '../context/SystemHealthContext';

function RepositoryIndexerImproved({ repositories, onRefresh }) {
  // Form state
  const [indexMode, setIndexMode] = useState('local');
  const [repoPath, setRepoPath] = useState('');
  const [repoName, setRepoName] = useState('');
  const [indexing, setIndexing] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  
  // WebSocket connection state
  const [wsConnected, setWsConnected] = useState(false);
  const [wsError, setWsError] = useState(null);
  const [currentTask, setCurrentTask] = useState(null); // { taskId, repositoryName }
  const [indexingStatus, setIndexingStatus] = useState(null);
  
  // UI state
  const [expandedSections, setExpandedSections] = useState({
    form: true,
    progress: true,
    details: false
  });
  
  // Refs for WebSocket management
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 5;
  
  const { isReady, status, isLoading: healthLoading } = useSystemHealth();

  // Pre-connect WebSocket on component mount
  useEffect(() => {
    initializeWebSocketConnection();
    
    return () => {
      cleanupWebSocket();
    };
  }, []);

  const initializeWebSocketConnection = () => {
    // Connect to a general indexing WebSocket endpoint (not task-specific)
    const apiUrl = process.env.REACT_APP_API_URL;
    let wsUrl;

    if (apiUrl) {
      const url = new URL(apiUrl);
      const protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
      wsUrl = `${protocol}//${url.host}/api/v1/index/live-status`;
    } else {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.host;
      wsUrl = `${protocol}//${host}/api/v1/index/live-status`;
    }

    connectWebSocket(wsUrl);
  };

  const connectWebSocket = (wsUrl) => {
    try {
      console.log('Pre-connecting to WebSocket:', wsUrl);
      wsRef.current = new WebSocket(wsUrl);

      wsRef.current.onopen = () => {
        console.log('WebSocket pre-connected successfully');
        setWsConnected(true);
        setWsError(null);
        reconnectAttempts.current = 0;
      };

      wsRef.current.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          
          if (message.type === 'task_status' && message.data) {
            // Update status if it's for our current task
            if (currentTask && message.data.task_id === currentTask.taskId) {
              setIndexingStatus(message.data);
              
              // Handle completion
              if (message.data.status === 'completed') {
                setIndexing(false);
                setResult('Repository indexed successfully!');
                if (onRefresh) onRefresh();
              } else if (message.data.status === 'failed') {
                setIndexing(false);
                setError(message.data.error_message || 'Indexing failed');
              }
            }
          } else if (message.type === 'connection_info') {
            console.log('WebSocket connection info:', message.data);
          } else if (message.type === 'error') {
            setWsError(message.message);
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };

      wsRef.current.onclose = (event) => {
        console.log('WebSocket closed:', event.code, event.reason);
        setWsConnected(false);
        
        // Attempt to reconnect if not a normal closure
        if (event.code !== 1000 && reconnectAttempts.current < maxReconnectAttempts) {
          const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 10000);
          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttempts.current++;
            console.log(`Reconnecting WebSocket... attempt ${reconnectAttempts.current}`);
            connectWebSocket(wsUrl);
          }, delay);
        } else if (reconnectAttempts.current >= maxReconnectAttempts) {
          setWsError('Failed to maintain WebSocket connection. Real-time updates disabled.');
        }
      };

      wsRef.current.onerror = (error) => {
        console.error('WebSocket error:', error);
        // Don't immediately show error - let reconnection handle it
      };

    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
      // Don't immediately show error - let reconnection handle it
    }
  };

  const cleanupWebSocket = () => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    if (wsRef.current) {
      wsRef.current.close(1000, 'Component unmounting');
    }
  };

  const handlePathChange = (event) => {
    const path = event.target.value;
    setRepoPath(path);
    
    // Auto-generate repository name from path or URL
    if (path && !repoName) {
      if (indexMode === 'local') {
        const pathParts = path.replace(/\\/g, '/').split('/');
        const lastPart = pathParts[pathParts.length - 1] || pathParts[pathParts.length - 2];
        if (lastPart) {
          setRepoName(lastPart);
        }
      } else {
        const urlMatch = path.match(/[\/\\]([^\/\\]+)(?:\.git)?(?:[\/\\]?$)/);
        if (urlMatch && urlMatch[1]) {
          setRepoName(urlMatch[1]);
        }
      }
    }
  };

  const handleModeChange = (event, newMode) => {
    if (newMode !== null) {
      setIndexMode(newMode);
      setRepoPath('');
      setRepoName('');
      setError('');
      setResult('');
    }
  };

  const handleIndexRepository = async () => {
    if (!repoPath.trim() || !repoName.trim()) {
      setError('Please provide both repository path/URL and name');
      return;
    }

    if (!isReady) {
      setError('System is not ready. Please wait for all services to initialize.');
      return;
    }

    setIndexing(true);
    setError('');
    setResult('');
    setIndexingStatus(null);

    try {
      let response;
      if (indexMode === 'local') {
        response = await ApiService.indexLocalRepository({
          repo_path: repoPath,
          repo_name: repoName
        });
      } else {
        response = await ApiService.indexRepository({
          repo_url: repoPath,
          repo_name: repoName
        });
      }

      if (response.task_id) {
        // Set current task for WebSocket message filtering
        setCurrentTask({
          taskId: response.task_id,
          repositoryName: repoName
        });
        
        // If WebSocket is not connected, show a message but continue
        if (!wsConnected) {
          setResult('Indexing started. Real-time updates may not be available due to connection issues.');
        } else {
          // Send task subscription message to WebSocket
          if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({
              type: 'subscribe_task',
              task_id: response.task_id
            }));
          }
        }
      } else {
        setIndexing(false);
        setError('Failed to start indexing: No task ID received');
      }
    } catch (error) {
      console.error('Indexing error:', error);
      setIndexing(false);
      setError(error.message || 'Failed to start indexing');
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

  const getConnectionStatusIcon = () => {
    if (wsConnected) {
      return <Wifi color="success" />;
    } else if (wsError) {
      return <WifiOff color="error" />;
    } else {
      return <WifiOff color="disabled" />;
    }
  };

  const getConnectionStatusText = () => {
    if (wsConnected) {
      return 'Real-time updates connected';
    } else if (wsError) {
      return `Connection error: ${wsError}`;
    } else {
      return 'Connecting...';
    }
  };

  return (
    <Box sx={{ maxWidth: 1000, margin: '0 auto', p: 2 }}>
      {/* Header with connection status */}
      <Paper elevation={1} sx={{ p: 2, mb: 2 }}>
        <Grid container alignItems="center" spacing={2}>
          <Grid item xs>
            <Typography variant="h5" component="h2">
              Repository Indexer
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Index repositories for AI-powered code analysis
            </Typography>
          </Grid>
          <Grid item>
            <Chip
              icon={getConnectionStatusIcon()}
              label={getConnectionStatusText()}
              color={wsConnected ? 'success' : wsError ? 'error' : 'default'}
              variant="outlined"
              size="small"
            />
          </Grid>
        </Grid>
      </Paper>

      <Grid container spacing={3}>
        {/* Repository Form - Always Visible */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" mb={2}>
                <Typography variant="h6" sx={{ flexGrow: 1 }}>
                  Repository Details
                </Typography>
                <Button
                  size="small"
                  onClick={() => handleSectionToggle('form')}
                  endIcon={expandedSections.form ? <ExpandLess /> : <ExpandMore />}
                >
                  {expandedSections.form ? 'Hide' : 'Show'}
                </Button>
              </Box>

              <Collapse in={expandedSections.form}>
                <Box>
                  {/* System Health Status */}
                  {healthLoading && (
                    <Alert severity="info" sx={{ mb: 2 }}>
                      Checking system health...
                    </Alert>
                  )}
                  
                  {!isReady && !healthLoading && (
                    <Alert severity="warning" sx={{ mb: 2 }}>
                      System not ready. Some services may be starting up.
                    </Alert>
                  )}

                  {/* Mode Selection */}
                  <ToggleButtonGroup
                    value={indexMode}
                    exclusive
                    onChange={handleModeChange}
                    sx={{ mb: 2 }}
                    size="small"
                  >
                    <ToggleButton value="local">
                      <Computer sx={{ mr: 1 }} />
                      Local Path
                    </ToggleButton>
                    <ToggleButton value="remote">
                      <GitHub sx={{ mr: 1 }} />
                      Git URL
                    </ToggleButton>
                  </ToggleButtonGroup>

                  {/* Repository Input */}
                  <TextField
                    fullWidth
                    label={indexMode === 'local' ? 'Repository Path' : 'Git Repository URL'}
                    value={repoPath}
                    onChange={handlePathChange}
                    placeholder={
                      indexMode === 'local'
                        ? 'C:\\path\\to\\repository'
                        : 'https://github.com/user/repo.git'
                    }
                    disabled={indexing}
                    sx={{ mb: 2 }}
                    InputProps={{
                      startAdornment: indexMode === 'local' ? <FolderOpen sx={{ mr: 1 }} /> : <GitHub sx={{ mr: 1 }} />
                    }}
                  />

                  {/* Repository Name */}
                  <TextField
                    fullWidth
                    label="Repository Name"
                    value={repoName}
                    onChange={(e) => setRepoName(e.target.value)}
                    placeholder="my-project"
                    disabled={indexing}
                    sx={{ mb: 2 }}
                  />

                  {/* Action Button */}
                  <Button
                    variant="contained"
                    onClick={handleIndexRepository}
                    disabled={!repoPath || !repoName || indexing || !isReady}
                    startIcon={indexing ? <Speed /> : <PlayArrow />}
                    fullWidth
                    size="large"
                  >
                    {indexing ? 'Indexing...' : 'Index Repository'}
                  </Button>

                  {/* Messages */}
                  {error && (
                    <Alert severity="error" sx={{ mt: 2 }}>
                      {error}
                    </Alert>
                  )}

                  {result && (
                    <Alert severity="success" sx={{ mt: 2 }}>
                      {result}
                    </Alert>
                  )}
                </Box>
              </Collapse>
            </CardContent>
          </Card>
        </Grid>

        {/* Real-time Progress - Always Visible When Active */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" mb={2}>
                <Typography variant="h6" sx={{ flexGrow: 1 }}>
                  Indexing Progress
                </Typography>
                {currentTask && (
                  <Button
                    size="small"
                    onClick={() => handleSectionToggle('progress')}
                    endIcon={expandedSections.progress ? <ExpandLess /> : <ExpandMore />}
                  >
                    {expandedSections.progress ? 'Hide' : 'Show'}
                  </Button>
                )}
              </Box>

              {!currentTask && (
                <Box textAlign="center" py={4}>
                  <Storage sx={{ fontSize: 48, color: 'text.disabled', mb: 2 }} />
                  <Typography color="text.secondary">
                    No active indexing task
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Start indexing a repository to see real-time progress
                  </Typography>
                </Box>
              )}

              {currentTask && (
                <Collapse in={expandedSections.progress}>
                  <Box>
                    {/* Task Info */}
                    <Box mb={2}>
                      <Typography variant="subtitle2" color="text.secondary">
                        Current Task
                      </Typography>
                      <Typography variant="body1" fontWeight="bold">
                        {currentTask.repositoryName}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Task ID: {currentTask.taskId}
                      </Typography>
                    </Box>

                    {/* Progress Indicator */}
                    {indexing && (
                      <Box mb={2}>
                        <LinearProgress />
                        <Typography variant="body2" color="text.secondary" mt={1}>
                          Indexing in progress...
                        </Typography>
                      </Box>
                    )}

                    {/* Detailed Status */}
                    {indexingStatus && (
                      <Box>
                        <Typography variant="subtitle2" gutterBottom>
                          Status: {indexingStatus.status}
                        </Typography>
                        
                        {indexingStatus.progress && (
                          <Box mb={2}>
                            <Typography variant="body2">
                              Files: {indexingStatus.progress.files_processed || 0} processed
                            </Typography>
                            <Typography variant="body2">
                              Chunks: {indexingStatus.progress.chunks_generated || 0} generated
                            </Typography>
                            {indexingStatus.progress.current_stage && (
                              <Typography variant="body2">
                                Stage: {indexingStatus.progress.current_stage}
                              </Typography>
                            )}
                          </Box>
                        )}

                        {indexingStatus.elapsed_time && (
                          <Typography variant="body2" color="text.secondary">
                            Elapsed: {formatDuration(indexingStatus.elapsed_time)}
                          </Typography>
                        )}
                      </Box>
                    )}
                  </Box>
                </Collapse>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Existing Repositories */}
        {repositories && repositories.length > 0 && (
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Indexed Repositories ({repositories.length})
                </Typography>
                <List>
                  {repositories.slice(0, 5).map((repo, index) => (
                    <React.Fragment key={repo.id || index}>
                      <ListItem>
                        <ListItemIcon>
                          <CheckCircle color="success" />
                        </ListItemIcon>
                        <ListItemText
                          primary={repo.name}
                          secondary={`${repo.total_files || 0} files, ${repo.total_chunks || 0} chunks`}
                        />
                      </ListItem>
                      {index < Math.min(4, repositories.length - 1) && <Divider />}
                    </React.Fragment>
                  ))}
                </List>
                {repositories.length > 5 && (
                  <Typography variant="body2" color="text.secondary" textAlign="center">
                    ... and {repositories.length - 5} more repositories
                  </Typography>
                )}
              </CardContent>
            </Card>
          </Grid>
        )}
      </Grid>
    </Box>
  );
}

export default RepositoryIndexerImproved;