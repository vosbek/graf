import React, { useState } from 'react';
import {
  Box, Typography, Paper, Button, FormControl,
  InputLabel, Select, MenuItem, Alert, Card, CardContent,
  Chip, List, ListItem, ListItemText, Divider, CircularProgress
} from '@mui/material';
import { Assessment, GetApp } from '@mui/icons-material';
import { ApiService } from '../services/ApiService';

function MigrationPlanner({ repositories }) {
  const [selectedRepo, setSelectedRepo] = useState('');
  const [migrationPlan, setMigrationPlan] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const generateMigrationPlan = async () => {
    if (!selectedRepo) return;

    setLoading(true);
    setError('');

    try {
      const plan = await ApiService.getMigrationPlan(selectedRepo);
      setMigrationPlan(plan);
    } catch (error) {
      setError(error.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom>
        Migration Planner
      </Typography>
      <Typography variant="body1" color="text.secondary" paragraph>
        Generate AI-powered migration recommendations and GraphQL schema suggestions for your Struts applications.
      </Typography>

      {repositories.length === 0 ? (
        <Alert severity="info">
          No repositories indexed yet. Please index some repositories first.
        </Alert>
      ) : (
        <>
          {/* Repository Selection */}
          <Paper sx={{ p: 3, mb: 3 }}>
            <Box display="flex" gap={2} alignItems="center">
              <FormControl sx={{ minWidth: 200 }}>
                <InputLabel>Repository</InputLabel>
                <Select
                  value={selectedRepo}
                  label="Repository"
                  onChange={(e) => setSelectedRepo(e.target.value)}
                >
                  {repositories.map((repo, index) => (
                    <MenuItem key={index} value={repo}>
                      {repo}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <Button
                variant="contained"
                startIcon={<Assessment />}
                onClick={generateMigrationPlan}
                disabled={!selectedRepo || loading}
                size="large"
              >
                {loading ? 'Generating...' : 'Generate Migration Plan'}
              </Button>
            </Box>
          </Paper>

          {/* Loading */}
          {loading && (
            <Paper sx={{ p: 3, textAlign: 'center' }}>
              <CircularProgress sx={{ mb: 2 }} />
              <Typography>Analyzing codebase and generating migration recommendations...</Typography>
            </Paper>
          )}

          {/* Error */}
          {error && (
            <Alert severity="error" sx={{ mb: 3 }}>
              {error}
            </Alert>
          )}

          {/* Migration Plan Results */}
          {migrationPlan && !loading && (
            <Box>
              {/* Summary */}
              <Card sx={{ mb: 3 }}>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    📊 Analysis Summary
                  </Typography>
                  <Box display="flex" gap={2} flexWrap="wrap">
                    <Chip 
                      label={`${migrationPlan.analysis_summary.business_logic_components} Business Logic Components`}
                      color="primary"
                    />
                    <Chip 
                      label={`${migrationPlan.analysis_summary.data_models_found} Data Models`}
                      color="secondary"
                    />
                  </Box>
                </CardContent>
              </Card>

              {/* GraphQL Suggestions */}
              <Card sx={{ mb: 3 }}>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    🎯 GraphQL Schema Suggestions
                  </Typography>
                  
                  {migrationPlan.graphql_suggestions.recommended_types.length > 0 && (
                    <Box sx={{ mb: 2 }}>
                      <Typography variant="subtitle1" gutterBottom>
                        Recommended Types:
                      </Typography>
                      <Box display="flex" gap={1} flexWrap="wrap">
                        {migrationPlan.graphql_suggestions.recommended_types.map((type, index) => (
                          <Chip key={index} label={type} variant="outlined" />
                        ))}
                      </Box>
                    </Box>
                  )}
                  
                  <Alert severity="info">
                    Complete GraphQL schema generation will be available in the next phase.
                  </Alert>
                </CardContent>
              </Card>

              {/* Migration Steps */}
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    📋 Migration Roadmap
                  </Typography>
                  <List>
                    {migrationPlan.migration_steps.map((step, index) => (
                      <React.Fragment key={index}>
                        <ListItem>
                          <ListItemText
                            primary={step}
                            secondary={`Step ${index + 1}`}
                          />
                        </ListItem>
                        {index < migrationPlan.migration_steps.length - 1 && <Divider />}
                      </React.Fragment>
                    ))}
                  </List>
                </CardContent>
              </Card>
            </Box>
          )}

          {/* Instructions */}
          {!migrationPlan && !loading && (
            <Paper sx={{ p: 3, bgcolor: 'info.light', color: 'info.contrastText' }}>
              <Typography variant="h6" gutterBottom>
                🚀 How Migration Planning Works
              </Typography>
              <List>
                <ListItem>
                  <ListItemText primary="1. Select a repository from your indexed Struts applications" />
                </ListItem>
                <ListItem>
                  <ListItemText primary="2. AI analyzes business logic, data models, and endpoints" />
                </ListItem>
                <ListItem>
                  <ListItemText primary="3. Generate GraphQL schema suggestions based on existing patterns" />
                </ListItem>
                <ListItem>
                  <ListItemText primary="4. Receive step-by-step migration roadmap" />
                </ListItem>
                <ListItem>
                  <ListItemText primary="5. Export recommendations for your development team" />
                </ListItem>
              </List>
            </Paper>
          )}
        </>
      )}
    </Box>
  );
}

export default MigrationPlanner;