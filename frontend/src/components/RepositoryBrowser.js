import React, { useState } from 'react';
import {
  Box, Typography, Paper, List, ListItem, ListItemText,
  ListItemIcon, Breadcrumbs, Link, Alert, Chip
} from '@mui/material';
import { Folder, InsertDriveFile, Code } from '@mui/icons-material';

function RepositoryBrowser({ repositories }) {
  const [selectedRepo, setSelectedRepo] = useState(null);

  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom>
        Repository Browser
      </Typography>
      <Typography variant="body1" color="text.secondary" paragraph>
        Browse through your indexed repositories and explore the file structure.
      </Typography>

      {repositories.length === 0 ? (
        <Alert severity="info">
          No repositories indexed yet. Please index some repositories first.
        </Alert>
      ) : (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            Available Repositories
          </Typography>
          <List>
            {repositories.map((repo, index) => (
              <ListItem key={index} button onClick={() => setSelectedRepo(repo)}>
                <ListItemIcon>
                  <Folder />
                </ListItemIcon>
                <ListItemText 
                  primary={repo}
                  secondary={`Repository ${index + 1}`}
                />
                <Chip label="Indexed" color="success" size="small" />
              </ListItem>
            ))}
          </List>
          
          {selectedRepo && (
            <Box sx={{ mt: 3 }}>
              <Typography variant="h6" gutterBottom>
                Files in {selectedRepo}
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