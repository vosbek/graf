import React, { useState } from 'react';
import {
  Box, Typography, Paper, TextField, Button, Alert, LinearProgress,
  List, ListItem, ListItemText, ListItemIcon, Divider, Chip, Card, CardContent
} from '@mui/material';
import { FolderOpen, PlayArrow, CheckCircle, Error, Info } from '@mui/icons-material';
import { ApiService } from '../services/ApiService';

function RepositoryIndexer({ repositories, onRefresh }) {
  const [repoPath, setRepoPath] = useState('');
  const [repoName, setRepoName] = useState('');
  const [indexing, setIndexing] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  const handlePathChange = (event) => {
    const path = event.target.value;
    setRepoPath(path);
    
    // Auto-generate repository name from path
    if (path && !repoName) {
      const pathParts = path.replace(/\\/g, '/').split('/');
      const lastPart = pathParts[pathParts.length - 1] || pathParts[pathParts.length - 2];
      if (lastPart) {
        setRepoName(lastPart);
      }
    }
  };

  const handleIndexRepository = async () => {
    if (!repoPath.trim() || !repoName.trim()) {
      setError('Please provide both repository path and name');
      return;
    }

    setIndexing(true);
    setError('');
    setResult(null);

    try {
      const indexResult = await ApiService.indexRepository(repoPath.trim(), repoName.trim());
      setResult(indexResult);
      
      // Refresh the repositories list
      if (onRefresh) {
        setTimeout(onRefresh, 1000); // Small delay to ensure backend is updated
      }
      
      // Clear form
      setRepoPath('');
      setRepoName('');
      
    } catch (error) {
      setError(error.message);
    } finally {
      setIndexing(false);
    }
  };

  const renderExamplePaths = () => (
    <Card sx={{ mt: 2 }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          💡 Example Repository Paths
        </Typography>
        <List dense>
          <ListItem>
            <ListItemIcon><FolderOpen /></ListItemIcon>
            <ListItemText 
              primary="Windows: C:\dev\projects\my-struts-app"
              secondary="Local project on Windows"
            />
          </ListItem>
          <ListItem>
            <ListItemIcon><FolderOpen /></ListItemIcon>
            <ListItemText 
              primary="Linux/Mac: /home/user/projects/legacy-app"
              secondary="Local project on Unix systems"
            />
          </ListItem>
          <ListItem>
            <ListItemIcon><FolderOpen /></ListItemIcon>
            <ListItemText 
              primary="Relative: ../my-projects/struts-application"
              secondary="Relative to the application directory"
            />
          </ListItem>
        </List>
      </CardContent>
    </Card>
  );

  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom>
        Repository Indexer
      </Typography>
      <Typography variant="body1" color="text.secondary" paragraph>
        Index your Struts applications and other repositories to make them searchable with AI.
      </Typography>

      {/* Indexing Form */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          Add New Repository
        </Typography>
        
        <Box component="form" sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <TextField
            label="Repository Path"
            placeholder="e.g., /path/to/your/struts-app or C:\dev\my-project"
            value={repoPath}
            onChange={handlePathChange}
            fullWidth
            required
            helperText="Full path to your repository directory"
          />
          
          <TextField
            label="Repository Name"
            placeholder="e.g., my-struts-app"
            value={repoName}
            onChange={(e) => setRepoName(e.target.value)}
            fullWidth
            required
            helperText="Friendly name for your repository"
          />
          
          <Button
            variant="contained"
            startIcon={indexing ? null : <PlayArrow />}
            onClick={handleIndexRepository}
            disabled={indexing || !repoPath.trim() || !repoName.trim()}
            size="large"
          >
            {indexing ? 'Indexing...' : 'Index Repository'}
          </Button>
        </Box>

        {indexing && (
          <Box sx={{ mt: 2 }}>
            <LinearProgress />
            <Typography variant="body2" sx={{ mt: 1, textAlign: 'center' }}>
              Analyzing repository structure and extracting code patterns...
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
            Files processed: {result.files_indexed}
            <br />
            Code chunks created: {result.chunks_created}
            <br />
            Processing time: {result.processing_time.toFixed(2)}s
          </Alert>
        )}
      </Paper>

      {/* Example Paths */}
      {renderExamplePaths()}

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
                    primary={repo}
                    secondary={`Repository ${index + 1}`}
                  />
                  <Chip label="Indexed" color="success" size="small" />
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
    </Box>
  );
}

export default RepositoryIndexer;