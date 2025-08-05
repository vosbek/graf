import React, { useState } from 'react';
import {
  Box, Typography, Paper, TextField, Button, Alert, LinearProgress,
  List, ListItem, ListItemText, ListItemIcon, Divider, Chip, Card, CardContent,
  ToggleButton, ToggleButtonGroup, Dialog, DialogTitle, DialogContent, DialogActions
} from '@mui/material';
import { FolderOpen, PlayArrow, CheckCircle, Error, Info, GitHub, Computer, Visibility } from '@mui/icons-material';
import { ApiService } from '../services/ApiService';
import RealTimeIndexingProgress from './RealTimeIndexingProgress';
import ActiveIndexingTasks from './ActiveIndexingTasks';
import { useSystemHealth } from '../context/SystemHealthContext';

function RepositoryIndexer({ repositories, onRefresh }) {
  const [indexMode, setIndexMode] = useState('local'); // 'local' or 'remote'
  const [repoPath, setRepoPath] = useState('');
  const [repoName, setRepoName] = useState('');
  const [indexing, setIndexing] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const { isReady, status, isLoading: healthLoading, isInitialLoad, error: healthError } = useSystemHealth();
  
  // Real-time progress tracking
  const [indexingTask, setIndexingTask] = useState(null); // { taskId, repositoryName }
  const [showProgressDialog, setShowProgressDialog] = useState(false);

  const handlePathChange = (event) => {
    const path = event.target.value;
    setRepoPath(path);
    
    // Auto-generate repository name from path or URL
    if (path && !repoName) {
      if (indexMode === 'local') {
        // Local path: extract directory name
        const pathParts = path.replace(/\\/g, '/').split('/');
        const lastPart = pathParts[pathParts.length - 1] || pathParts[pathParts.length - 2];
        if (lastPart) {
          setRepoName(lastPart);
        }
      } else {
        // Remote URL: extract repository name from Git URL
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
      setResult(null);
    }
  };

  const handleIndexRepository = async () => {
    if (!isReady) {
      setError('System is not ready. Please wait until readiness is reported before indexing.');
      return;
    }
    if (!repoPath.trim() || !repoName.trim()) {
      setError(`Please provide both repository ${indexMode === 'local' ? 'path' : 'URL'} and name`);
      return;
    }

    setIndexing(true);
    setError('');
    setResult(null);

    try {
      let indexResult;
      if (indexMode === 'local') {
        indexResult = await ApiService.indexLocalRepository({
          name: repoName.trim(),
          local_path: repoPath.trim(),
          priority: 'medium',
          is_golden_repo: false
        });
      } else {
        indexResult = await ApiService.indexRepository({
          name: repoName.trim(),
          url: repoPath.trim(),
          branch: 'main',
          priority: 'medium',
          maven_enabled: true,
          is_golden_repo: false
        });
      }
      
      // Use the official task_id from the backend response
      const taskId = indexResult.task_id;
      if (!taskId) {
        throw new Error('Backend did not return a task_id for progress tracking.');
      }

      setIndexingTask({ taskId: taskId, repositoryName: repoName.trim() });
      setShowProgressDialog(true);
      
      // Do not show immediate success, wait for the progress component to report completion
      // setResult(indexResult); 
      
      // Clear form
      setRepoPath('');
      setRepoName('');
      
    } catch (error) {
      setError(error.message);
      setIndexing(false);
    }
  };

  const handleProgressComplete = (finalStatus) => {
    setIndexing(false);
    setShowProgressDialog(false);
    setIndexingTask(null);
    
    // Refresh the repositories list
    if (onRefresh) {
      setTimeout(onRefresh, 1000);
    }
    
    // Show completion message
    setResult({
      repository: finalStatus.repository_name,
      files_indexed: finalStatus.processed_files,
      chunks_created: finalStatus.generated_chunks,
      processing_time: finalStatus.processing_time
    });
  };

  const handleProgressError = (errorStatus) => {
    setIndexing(false);
    setShowProgressDialog(false);
    setIndexingTask(null);
    
    setError(errorStatus.error_message || 'Indexing failed with unknown error');
  };

  const handleCloseProgressDialog = () => {
    setShowProgressDialog(false);
    setIndexingTask(null);
    setIndexing(false);
  };

  const renderExamplePaths = () => (
    <Card sx={{ mt: 2 }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          💡 Example {indexMode === 'local' ? 'Repository Paths' : 'Git URLs'}
        </Typography>
        <List dense>
          {indexMode === 'local' ? (
            <>
              <ListItem>
                <ListItemIcon><FolderOpen /></ListItemIcon>
                <ListItemText
                  primary={<Typography component="span">Windows: C:\dev\projects\my-struts-app</Typography>}
                  secondary={<Typography component="span">Local project on Windows</Typography>}
                />
              </ListItem>
              <ListItem>
                <ListItemIcon><FolderOpen /></ListItemIcon>
                <ListItemText
                  primary={<Typography component="span">Linux/Mac: /home/user/projects/legacy-app</Typography>}
                  secondary={<Typography component="span">Local project on Unix systems</Typography>}
                />
              </ListItem>
              <ListItem>
                <ListItemIcon><FolderOpen /></ListItemIcon>
                <ListItemText
                  primary={<Typography component="span">Relative: ../my-projects/struts-application</Typography>}
                  secondary={<Typography component="span">Relative to the application directory</Typography>}
                />
              </ListItem>
            </>
          ) : (
            <>
              <ListItem>
                <ListItemIcon><GitHub /></ListItemIcon>
                <ListItemText
                  primary={<Typography component="span">GitHub: https://github.com/username/my-struts-app</Typography>}
                  secondary={<Typography component="span">Public GitHub repository</Typography>}
                />
              </ListItem>
              <ListItem>
                <ListItemIcon><GitHub /></ListItemIcon>
                <ListItemText
                  primary={<Typography component="span">GitLab: https://gitlab.com/team/legacy-app</Typography>}
                  secondary={<Typography component="span">GitLab repository</Typography>}
                />
              </ListItem>
              <ListItem>
                <ListItemIcon><GitHub /></ListItemIcon>
                <ListItemText
                  primary={<Typography component="span">Private: https://git.company.com/team/app.git</Typography>}
                  secondary={<Typography component="span">Private Git repository</Typography>}
                />
              </ListItem>
            </>
          )}
        </List>
      </CardContent>
    </Card>
  );

  const readinessBanner = (!isReady || isInitialLoad || healthError) ? (
    <Alert severity={healthError ? 'error' : 'info'} sx={{ mb: 2 }}>
      {!isReady ? 'System is starting up. Indexing is disabled until the system is ready.' :
       isInitialLoad ? 'Checking system readiness...' :
       `Health error: ${healthError}`}
    </Alert>
  ) : null;

  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom>
        Repository Indexer
      </Typography>
      <Typography variant="body1" color="text.secondary" paragraph>
        Index your Struts applications and other repositories to make them searchable with AI.
      </Typography>

      {readinessBanner}

      {/* Indexing Form */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          Add New Repository
        </Typography>
        
        <Box component="form" sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {/* Mode Toggle */}
          <Box>
            <Typography variant="subtitle2" gutterBottom>
              Repository Source
            </Typography>
            <ToggleButtonGroup
              value={indexMode}
              exclusive
              onChange={handleModeChange}
              aria-label="indexing mode"
              fullWidth
            >
              <ToggleButton value="local" aria-label="local path">
                <Computer sx={{ mr: 1 }} />
                Local Path
              </ToggleButton>
              <ToggleButton value="remote" aria-label="remote git">
                <GitHub sx={{ mr: 1 }} />
                Git URL
              </ToggleButton>
            </ToggleButtonGroup>
          </Box>

          <TextField
            label={indexMode === 'local' ? 'Repository Path' : 'Git Repository URL'}
            placeholder={indexMode === 'local'
              ? 'e.g., /path/to/your/struts-app or C:\\dev\\my-project'
              : 'e.g., https://github.com/username/repository-name'
            }
            value={repoPath}
            onChange={handlePathChange}
            fullWidth
            required
            helperText={!isReady ? 'System not ready yet. You can fill the form, but indexing is disabled.' :
              indexMode === 'local'
              ? 'Full path to your local repository directory'
              : 'URL to Git repository (GitHub, GitLab, etc.)'
            }
            disabled={!isReady}
          />
          
          <TextField
            label="Repository Name"
            placeholder="e.g., my-struts-app"
            value={repoName}
            onChange={(e) => setRepoName(e.target.value)}
            fullWidth
            required
            helperText="Friendly name for your repository"
            disabled={!isReady}
          />
          
          <Button
            variant="contained"
            startIcon={indexing ? null : <PlayArrow />}
            onClick={handleIndexRepository}
            disabled={!isReady || indexing || !repoPath.trim() || !repoName.trim()}
            size="large"
          >
            {indexing ? 'Indexing...' : 'Index Repository'}
          </Button>
        </Box>

        {indexing && !showProgressDialog && (
          <Box sx={{ mt: 2 }}>
            <LinearProgress />
            <Typography variant="body2" sx={{ mt: 1, textAlign: 'center' }}>
              Starting repository indexing...
            </Typography>
          </Box>
        )}

        {error && (
          <Alert severity="error" sx={{ mt: 2 }}>
            <strong>Indexing Failed:</strong> {error}
          </Alert>
        )}

        {result && (
          <Alert severity="success" sx={{ mt: 2 }}>
            <strong>Successfully Indexed!</strong>
            <br />
            Repository: {result.repository}
            <br />
            Files processed: {result.files_indexed || 'N/A'}
            <br />
            Code chunks created: {result.chunks_created || 'N/A'}
            <br />
            Processing time: {result.processing_time ? result.processing_time.toFixed(2) + 's' : 'N/A'}
          </Alert>
        )}
      </Paper>

      {/* Example Paths */}
      {renderExamplePaths()}

      {/* Active Indexing Tasks */}
      <ActiveIndexingTasks onViewProgress={(taskId, repositoryName) => {
        setIndexingTask({ taskId, repositoryName });
        setShowProgressDialog(true);
      }} />

      {/* Current Repositories */}
      {repositories.length > 0 && (
        <Paper sx={{ p: 3, mt: 3 }}>
          <Typography variant="h6" gutterBottom>
            Currently Indexed Repositories
          </Typography>
          
          <List>
            {repositories.map((repo, index) => (
              <React.Fragment key={index}>
                <ListItem>
                  <ListItemIcon>
                    <CheckCircle color="success" />
                  </ListItemIcon>
                  <ListItemText
                    primary={<Typography component="span">{repo.name || repo}</Typography>}
                    secondary={
                      <Box component="span">
                        <Typography variant="body2" component="span">
                          {repo.status ? `Status: ${repo.status} | Files: ${repo.indexed_files || 0}` : `Repository ${index + 1}`}
                        </Typography>
                        {repo.chunks_created && (
                          <Typography variant="body2" color="text.secondary" component="span" sx={{ display: 'block' }}>
                            Chunks: {repo.chunks_created} | Processing time: {repo.processing_time ? `${repo.processing_time.toFixed(1)}s` : 'N/A'}
                          </Typography>
                        )}
                      </Box>
                    }
                  />
                  <Box sx={{ display: 'flex', gap: 1 }}>
                    <Chip label="Indexed" color="success" size="small" />
                    {repo.embedding_enabled && (
                      <Chip label="Embeddings" color="secondary" size="small" />
                    )}
                  </Box>
                </ListItem>
                {index < repositories.length - 1 && <Divider />}
              </React.Fragment>
            ))}
          </List>
        </Paper>
      )}

      {/* Instructions */}
      <Paper sx={{ p: 3, mt: 3, bgcolor: 'info.light', color: 'info.contrastText' }}>
        <Typography variant="h6" gutterBottom display="flex" alignItems="center">
          <Info sx={{ mr: 1 }} />
          How Repository Indexing Works
        </Typography>
        <Box component="ul" sx={{ pl: 3, mb: 0 }}>
          <li><strong>Code Analysis:</strong> Parses Java, JSP, XML, and configuration files</li>
          <li><strong>Struts Detection:</strong> Identifies Actions, Forms, and JSP patterns</li>
          <li><strong>Dependency Mapping:</strong> Extracts Maven dependencies and relationships</li>
          <li><strong>Semantic Indexing:</strong> Creates searchable embeddings for AI queries</li>
          <li><strong>Knowledge Graph:</strong> Builds relationships for dependency analysis</li>
        </Box>
      </Paper>

      {/* Real-time Progress Dialog */}
      <Dialog
        open={showProgressDialog}
        onClose={handleCloseProgressDialog}
        maxWidth="md"
        fullWidth
        PaperProps={{
          sx: { minHeight: '60vh' }
        }}
      >
        <DialogTitle>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Visibility />
            <Typography variant="h6">
              Indexing Progress: {indexingTask?.repositoryName}
            </Typography>
          </Box>
        </DialogTitle>
        <DialogContent>
          <RealTimeIndexingProgress
            taskId={indexingTask?.taskId}
            repositoryName={indexingTask?.repositoryName}
            onComplete={handleProgressComplete}
            onError={handleProgressError}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseProgressDialog} color="primary">
            Close
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

export default RepositoryIndexer;