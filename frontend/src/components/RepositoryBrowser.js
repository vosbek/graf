import React, { useState } from 'react';
import {
  Box, Typography, Paper, List, ListItem, ListItemText,
  ListItemIcon, Alert, Chip
} from '@mui/material';
import { Folder } from '@mui/icons-material';
import { useSystemHealth } from '../context/SystemHealthContext';

function RepositoryBrowser({ repositories = [] }) {
  const [selectedRepo, setSelectedRepo] = useState(null);
  const { isReady, isLoading: healthLoading, isInitialLoad, error: healthError } = useSystemHealth();

  const readinessBanner = (!isReady || isInitialLoad || healthError) ? (
    <Alert severity={healthError ? 'error' : 'info'} sx={{ mb: 2 }}>
      {!isReady ? 'System is starting up. Repository Browser is disabled until the system is ready.' :
       isInitialLoad ? 'Checking system readiness...' :
       `Health error: ${healthError}`}
    </Alert>
  ) : null;

  const disabled = !isReady;

  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom>
        Repository Browser
      </Typography>
      <Typography variant="body1" color="text.secondary" paragraph>
        Browse through your indexed repositories and explore the file structure.
      </Typography>

      {readinessBanner}

      {repositories.length === 0 ? (
        <Alert severity="info">
          No repositories indexed yet. Please index some repositories first.
        </Alert>
      ) : (
        <Paper sx={{ p: 3, opacity: disabled ? 0.6 : 1 }}>
          <Typography variant="h6" gutterBottom>
            Available Repositories
          </Typography>
          <List>
            {repositories.map((repo, index) => (
              <ListItem
                key={index}
                button
                disabled={disabled}
                onClick={() => !disabled && setSelectedRepo(repo)}
              >
                <ListItemIcon>
                  <Folder />
                </ListItemIcon>
                <ListItemText
                  primary={
                    <Typography component="span" variant="body1">
                      {repo.name || repo}
                    </Typography>
                  }
                  secondary={
                    <Typography component="span" variant="body2" color="text.secondary">
                      {repo.status ? `Status: ${repo.status} | Files: ${repo.indexed_files || 0}` : `Repository ${index + 1}`}
                    </Typography>
                  }
                />
                <Chip label="Indexed" color="success" size="small" />
              </ListItem>
            ))}
          </List>
          
          {selectedRepo && (
            <Box sx={{ mt: 3 }}>
              <Typography variant="h6" gutterBottom>
                Files in {selectedRepo.name || selectedRepo}
              </Typography>
              <Alert severity="info">
                File browser functionality will be implemented in the next phase.
                For now, use the Search interface to find specific files and code.
              </Alert>
            </Box>
          )}
        </Paper>
      )}
    </Box>
  );
}

export default RepositoryBrowser;