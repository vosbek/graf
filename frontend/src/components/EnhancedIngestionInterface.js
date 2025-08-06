import React, { useState, useEffect, useRef } from 'react';
import {
  Box, Typography, Paper, TextField, Button, Alert, LinearProgress,
  Grid, Card, CardContent, ToggleButton, ToggleButtonGroup, Divider,
  List, ListItem, ListItemText, ListItemIcon, Tabs, Tab, Chip, Badge,
  Accordion, AccordionSummary, AccordionDetails, IconButton, Tooltip,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Snackbar, Slide, Collapse, Timeline, TimelineItem, TimelineSeparator,
  TimelineConnector, TimelineContent, TimelineDot
} from '@mui/material';
import {
  FolderOpen, PlayArrow, CheckCircle, Error, Warning, Info, GitHub,
  Computer, Visibility, ExpandMore, Refresh, Speed, Storage, Analytics,
  Code, CloudSync, History, Timeline as TimelineIcon, QueueMusic,
  NotificationImportant, Close, Launch
} from '@mui/icons-material';
import { ApiService } from '../services/ApiService';
import RealTimeIndexingProgress from './RealTimeIndexingProgress';
import ActiveIndexingTasks from './ActiveIndexingTasks';
import { useSystemHealth } from '../context/SystemHealthContext';

const STAGE_ICONS = {
  queued: <QueueMusic />,
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

function EnhancedIngestionInterface({ repositories, onRefresh }) {
  // Form state
  const [indexMode, setIndexMode] = useState('local');
  const [repoPath, setRepoPath] = useState('');
  const [repoName, setRepoName] = useState('');
  const [indexing, setIndexing] = useState(false);

  // Enhanced feedback state
  const [submissionSuccess, setSubmissionSuccess] = useState(null);
  const [connectionStatus, setConnectionStatus] = useState('connecting'); // connecting, connected, disconnected, error
  const [queuedTasks, setQueuedTasks] = useState([]);
  const [completedTasks, setCompletedTasks] = useState([]);
  const [activeTasks, setActiveTasks] = useState([]);
  
  // UI state
  const [currentTab, setCurrentTab] = useState(0); // 0=Submit, 1=Queue, 2=Active, 3=Completed
  const [expandedAccordions, setExpandedAccordions] = useState({
    form: true,
    connectionStatus: true,
    recentActivity: true
  });
  
  // Enhanced error and messaging state
  const [errorDetails, setErrorDetails] = useState(null);
  const [notifications, setNotifications] = useState([]);
  
  const { isReady, status } = useSystemHealth();
  const wsRef = useRef(null);
  const pollingInterval = useRef(null);

  // Initialize enhanced connection monitoring
  useEffect(() => {
    initializeConnectionMonitoring();
    startDataPolling();
    
    return () => {
      cleanupConnections();
    };
  }, []);

  const initializeConnectionMonitoring = async () => {
    setConnectionStatus('connecting');
    
    try {
      // Test API connectivity first
      await ApiService.getSystemHealth();
      setConnectionStatus('connected');
      
      // Initialize WebSocket for real-time updates
      connectWebSocket();
      
    } catch (error) {
      setConnectionStatus('error');
      addNotification('Connection Error', 'Failed to connect to API server', 'error');
    }
  };

  const connectWebSocket = () => {
    const wsUrl = getWebSocketUrl();
    wsRef.current = new WebSocket(wsUrl);
    
    wsRef.current.onopen = () => {
      setConnectionStatus('connected');
      addNotification('Connected', 'Real-time monitoring active', 'success');
    };
    
    wsRef.current.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        handleWebSocketMessage(message);
      } catch (error) {
        console.error('WebSocket message parsing error:', error);
      }
    };
    
    wsRef.current.onerror = () => {
      setConnectionStatus('error');
      addNotification('Connection Error', 'WebSocket connection failed', 'error');
    };
    
    wsRef.current.onclose = () => {
      setConnectionStatus('disconnected');
      // Attempt reconnection after 5 seconds
      setTimeout(connectWebSocket, 5000);
    };
  };

  const getWebSocketUrl = () => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    return `${protocol}//${host}/api/v1/index/status/all/stream`;
  };

  const handleWebSocketMessage = (message) => {
    if (message.type === 'task_status') {
      const taskData = message.data;
      
      // Update appropriate task list based on status
      switch (taskData.status) {
        case 'queued':
          updateTaskInList(setQueuedTasks, taskData);
          break;
        case 'in_progress':
          updateTaskInList(setActiveTasks, taskData);
          removeTaskFromList(setQueuedTasks, taskData.task_id);
          break;
        case 'completed':
        case 'failed':
          updateTaskInList(setCompletedTasks, taskData);
          removeTaskFromList(setActiveTasks, taskData.task_id);
          addNotification(
            taskData.status === 'completed' ? 'Indexing Complete' : 'Indexing Failed',
            `Repository: ${taskData.repository_name}`,
            taskData.status === 'completed' ? 'success' : 'error'
          );
          break;
      }
    }
  };

  const updateTaskInList = (setList, taskData) => {
    setList(prev => {
      const existing = prev.find(t => t.task_id === taskData.task_id);
      if (existing) {
        return prev.map(t => t.task_id === taskData.task_id ? taskData : t);
      } else {
        return [...prev, taskData];
      }
    });
  };

  const removeTaskFromList = (setList, taskId) => {
    setList(prev => prev.filter(t => t.task_id !== taskId));
  };

  const startDataPolling = () => {
    // Poll for task updates every 10 seconds as backup to WebSocket
    pollingInterval.current = setInterval(async () => {
      try {
        const response = await ApiService.getIndexingStatus();
        const tasks = response.tasks || [];
        
        setQueuedTasks(tasks.filter(t => t.status === 'queued'));
        setActiveTasks(tasks.filter(t => t.status === 'in_progress'));
        setCompletedTasks(tasks.filter(t => ['completed', 'failed'].includes(t.status)));
      } catch (error) {
        console.error('Polling error:', error);
      }
    }, 10000);
  };

  const cleanupConnections = () => {
    if (wsRef.current) {
      wsRef.current.close();
    }
    if (pollingInterval.current) {
      clearInterval(pollingInterval.current);
    }
  };

  const addNotification = (title, message, severity = 'info', duration = 6000) => {
    const notification = {
      id: Date.now(),
      title,
      message,
      severity,
      timestamp: new Date(),
      duration
    };
    
    setNotifications(prev => [notification, ...prev.slice(0, 9)]); // Keep last 10
    
    // Auto-remove after duration
    setTimeout(() => {
      setNotifications(prev => prev.filter(n => n.id !== notification.id));
    }, duration);
  };

  const handleSubmitRepository = async () => {
    if (!isReady) {
      setErrorDetails({
        type: 'system_not_ready',
        message: 'System is not ready. Please wait for all services to be healthy.',
        details: status
      });
      return;
    }

    if (!repoPath.trim() || !repoName.trim()) {
      setErrorDetails({
        type: 'validation_error',
        message: `Please provide both repository ${indexMode === 'local' ? 'path' : 'URL'} and name`,
        details: { repoPath, repoName, indexMode }
      });
      return;
    }

    setIndexing(true);
    setErrorDetails(null);
    setSubmissionSuccess(null);

    try {
      let result;
      const requestData = {
        name: repoName.trim(),
        priority: 'medium',
        is_golden_repo: false
      };

      if (indexMode === 'local') {
        requestData.local_path = repoPath.trim();
        result = await ApiService.indexLocalRepository(requestData);
      } else {
        requestData.url = repoPath.trim();
        requestData.branch = 'main';
        requestData.maven_enabled = true;
        result = await ApiService.indexRepository(requestData);
      }

      // Enhanced success feedback
      setSubmissionSuccess({
        taskId: result.task_id,
        repositoryName: repoName.trim(),
        submittedAt: new Date(),
        estimatedDuration: '5-15 minutes',
        type: indexMode
      });

      // Add to queued tasks immediately
      const queuedTask = {
        task_id: result.task_id,
        repository_name: repoName.trim(),
        status: 'queued',
        submitted_at: new Date().toISOString(),
        type: indexMode
      };
      setQueuedTasks(prev => [queuedTask, ...prev]);

      addNotification(
        'Repository Queued Successfully!',
        `${repoName.trim()} has been added to the indexing queue`,
        'success'
      );

      // Switch to Active Monitoring tab
      setCurrentTab(1);

      // Clear form
      setRepoPath('');
      setRepoName('');

    } catch (error) {
      setErrorDetails({
        type: 'submission_error',
        message: error.message,
        details: error.response?.data || error
      });
      
      addNotification('Submission Failed', error.message, 'error');
    } finally {
      setIndexing(false);
    }
  };

  const handleTabChange = (event, newValue) => {
    setCurrentTab(newValue);
  };

  const formatDuration = (seconds) => {
    if (!seconds) return 'Unknown';
    if (seconds < 60) return `${seconds.toFixed(0)}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds.toFixed(0)}s`;
  };

  const formatTimestamp = (timestamp) => {
    return new Date(timestamp).toLocaleString();
  };

  const getConnectionStatusColor = () => {
    switch (connectionStatus) {
      case 'connected': return 'success';
      case 'connecting': return 'info';
      case 'disconnected': return 'warning';
      case 'error': return 'error';
      default: return 'default';
    }
  };

  const renderConnectionStatus = () => (
    <Card sx={{ mb: 2 }}>
      <CardContent>
        <Box display="flex" alignItems="center" gap={1}>
          <Chip
            icon={connectionStatus === 'connected' ? <CheckCircle /> : <Warning />}
            label={`Connection: ${connectionStatus.charAt(0).toUpperCase() + connectionStatus.slice(1)}`}
            color={getConnectionStatusColor()}
            variant="outlined"
          />
          <Chip
            icon={isReady ? <CheckCircle /> : <Warning />}
            label={`System: ${isReady ? 'Ready' : 'Not Ready'}`}
            color={isReady ? 'success' : 'warning'}
            variant="outlined"
          />
          <Box flexGrow={1} />
          <IconButton onClick={() => window.location.reload()} size="small">
            <Refresh />
          </IconButton>
        </Box>
      </CardContent>
    </Card>
  );

  const renderSubmissionForm = () => (
    <Card>
      <CardContent>
        <Box display="flex" alignItems="center" gap={1} mb={2}>
          <FolderOpen />
          <Typography variant="h6">Submit Repository for Indexing</Typography>
        </Box>

        <ToggleButtonGroup
          value={indexMode}
          exclusive
          onChange={(e, newMode) => newMode && setIndexMode(newMode)}
          fullWidth
          sx={{ mb: 3 }}
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

        <TextField
          fullWidth
          label={indexMode === 'local' ? 'Repository Path' : 'Git Repository URL'}
          value={repoPath}
          onChange={(e) => setRepoPath(e.target.value)}
          placeholder={indexMode === 'local' ? 'C:\\dev\\projects\\my-app' : 'https://github.com/user/repo'}
          sx={{ mb: 2 }}
        />

        <TextField
          fullWidth
          label="Repository Name"
          value={repoName}
          onChange={(e) => setRepoName(e.target.value)}
          placeholder="my-app"
          sx={{ mb: 3 }}
        />

        <Box display="flex" gap={2}>
          <Button
            variant="contained"
            onClick={handleSubmitRepository}
            disabled={!isReady || indexing || !repoPath.trim() || !repoName.trim()}
            startIcon={indexing ? <LinearProgress /> : <PlayArrow />}
            fullWidth
          >
            {indexing ? 'Submitting...' : 'Add to Queue'}
          </Button>
        </Box>

        {/* Enhanced Success Feedback */}
        <Collapse in={!!submissionSuccess}>
          <Alert severity="success" sx={{ mt: 2 }}>
            <Typography variant="subtitle2">Successfully Queued!</Typography>
            <Typography variant="body2">
              Repository "{submissionSuccess?.repositoryName}" has been added to the indexing queue.
            </Typography>
            <Box mt={1} display="flex" gap={1}>
              <Chip label={`Task ID: ${submissionSuccess?.taskId}`} size="small" />
              <Chip label={`Est. Duration: ${submissionSuccess?.estimatedDuration}`} size="small" />
            </Box>
          </Alert>
        </Collapse>

        {/* Enhanced Error Display */}
        <Collapse in={!!errorDetails}>
          <Alert severity="error" sx={{ mt: 2 }}>
            <Typography variant="subtitle2">{errorDetails?.type?.replace(/_/g, ' ').toUpperCase()}</Typography>
            <Typography variant="body2">{errorDetails?.message}</Typography>
            {errorDetails?.details && (
              <Box mt={1}>
                <Typography variant="caption">Details:</Typography>
                <pre style={{ fontSize: '10px', overflow: 'auto', maxHeight: '100px' }}>
                  {JSON.stringify(errorDetails.details, null, 2)}
                </pre>
              </Box>
            )}
          </Alert>
        </Collapse>
      </CardContent>
    </Card>
  );

  const renderTaskList = (tasks, title, emptyMessage) => (
    <Card>
      <CardContent>
        <Box display="flex" alignItems="center" gap={1} mb={2}>
          <Badge badgeContent={tasks.length} color="primary">
            <QueueMusic />
          </Badge>
          <Typography variant="h6">{title}</Typography>
        </Box>

        {tasks.length === 0 ? (
          <Alert severity="info">{emptyMessage}</Alert>
        ) : (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Repository</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Progress</TableCell>
                  <TableCell>Started</TableCell>
                  <TableCell>Duration</TableCell>
                  <TableCell>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {tasks.map((task) => (
                  <TableRow key={task.task_id}>
                    <TableCell>{task.repository_name}</TableCell>
                    <TableCell>
                      <Chip
                        icon={STAGE_ICONS[task.current_stage] || STAGE_ICONS[task.status]}
                        label={task.current_stage || task.status}
                        color={STAGE_COLORS[task.current_stage] || STAGE_COLORS[task.status]}
                        size="small"
                      />
                    </TableCell>
                    <TableCell>
                      <Box display="flex" alignItems="center" gap={1}>
                        <LinearProgress 
                          variant="determinate" 
                          value={task.overall_progress || 0} 
                          sx={{ width: 60 }}
                        />
                        <Typography variant="caption">
                          {Math.round(task.overall_progress || 0)}%
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Typography variant="caption">
                        {formatTimestamp(task.started_at || task.submitted_at)}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="caption">
                        {formatDuration(task.processing_time)}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <IconButton size="small">
                        <Visibility />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </CardContent>
    </Card>
  );

  const renderNotifications = () => (
    <Box sx={{ position: 'fixed', top: 80, right: 16, zIndex: 1000, maxWidth: 400 }}>
      {notifications.slice(0, 3).map((notification) => (
        <Slide direction="left" in={true} key={notification.id}>
          <Alert 
            severity={notification.severity}
            sx={{ mb: 1 }}
            onClose={() => setNotifications(prev => prev.filter(n => n.id !== notification.id))}
          >
            <Typography variant="subtitle2">{notification.title}</Typography>
            <Typography variant="body2">{notification.message}</Typography>
          </Alert>
        </Slide>
      ))}
    </Box>
  );

  return (
    <Box>
      {renderNotifications()}
      
      {renderConnectionStatus()}

      <Paper sx={{ mb: 3 }}>
        <Tabs value={currentTab} onChange={handleTabChange} variant="fullWidth">
          <Tab label="Submit Repository" icon={<PlayArrow />} />
          <Tab 
            label={
              <Badge badgeContent={queuedTasks.length} color="info">
                <span>Queue ({queuedTasks.length})</span>
              </Badge>
            } 
            icon={<QueueMusic />} 
          />
          <Tab 
            label={
              <Badge badgeContent={activeTasks.length} color="primary">
                <span>Active ({activeTasks.length})</span>
              </Badge>
            } 
            icon={<Speed />} 
          />
          <Tab 
            label={
              <Badge badgeContent={completedTasks.length} color="success">
                <span>Completed ({completedTasks.length})</span>
              </Badge>
            } 
            icon={<History />} 
          />
        </Tabs>
      </Paper>

      {currentTab === 0 && renderSubmissionForm()}
      {currentTab === 1 && renderTaskList(queuedTasks, "Queued Tasks", "No repositories queued for indexing")}
      {currentTab === 2 && renderTaskList(activeTasks, "Active Indexing Tasks", "No repositories currently being indexed")}
      {currentTab === 3 && renderTaskList(completedTasks, "Indexing History", "No completed indexing tasks")}
    </Box>
  );
}

export default EnhancedIngestionInterface;