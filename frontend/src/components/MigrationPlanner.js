import React, { useState } from 'react';
import {
  Box, Typography, Paper, Button, FormControl,
  InputLabel, Select, MenuItem, Alert, Card, CardContent,
  Chip, List, ListItem, ListItemText, Divider, CircularProgress
} from '@mui/material';
import { Assessment, GetApp } from '@mui/icons-material';
import { ApiService } from '../services/ApiService';
import { useSystemHealth } from '../context/SystemHealthContext';

function MigrationPlanner({ repositories }) {
  const [selectedRepos, setSelectedRepos] = useState([]);
  const [migrationPlan, setMigrationPlan] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const { isReady, isLoading: healthLoading, error: healthError } = useSystemHealth();

  const generateMigrationPlan = async () => {
    if (!isReady) {
      setError('System is not ready. Planning is disabled until the system is ready.');
      return;
    }
    if (!selectedRepos || selectedRepos.length === 0) {
      setError('Please select at least one repository.');
      return;
    }

    setLoading(true);
    setError('');

    try {
      // Call canonical multi-repo endpoint
      const repoNames = selectedRepos.map(r => (typeof r === 'string' ? r : (r.name || r)));
      const plan = await ApiService.getMultiRepoMigrationPlan(repoNames);
      setMigrationPlan(plan);
    } catch (error) {
      const msg = error?.response?.data?.detail;
      setError(typeof msg === 'string' ? msg : (msg?.error || error.message));
    } finally {
      setLoading(false);
    }
  };

  // Helper projections for legacy chips when only one repo selected
  const singleRepoSummary = migrationPlan ? {
    business_logic_components: ((migrationPlan?.summary?.totals?.services || 0) + (migrationPlan?.summary?.totals?.actions || 0)),
    data_models_found: migrationPlan?.summary?.totals?.data_models || 0
  } : null;

  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom>
        Migration Planner
      </Typography>
      <Typography variant="body1" color="text.secondary" paragraph>
        Generate AI-powered migration recommendations, cross-repository impact, and GraphQL schema suggestions.
      </Typography>

      {(!isReady || healthLoading || healthError) && (
        <Alert severity={healthError ? 'error' : 'info'} sx={{ mb: 2 }}>
          {!isReady ? 'System is starting up. Planning is disabled until the system is ready.' :
           healthLoading ? 'Checking system readiness...' :
           `Health error: ${healthError}`}
        </Alert>
      )}

      {(!repositories || repositories.length === 0) ? (
        <Alert severity="info">
          No repositories indexed yet. Please index some repositories first.
        </Alert>
      ) : (
        <>
          {/* Repository Multi-Selection */}
          <Paper sx={{ p: 3, mb: 3 }}>
            <Box display="flex" gap={2} alignItems="center" flexWrap="wrap">
              <FormControl sx={{ minWidth: 260 }}>
                <InputLabel>Repositories</InputLabel>
                <Select
                  multiple
                  value={selectedRepos}
                  label="Repositories"
                  onChange={(e) => setSelectedRepos(e.target.value)}
                  renderValue={(selected) => {
                    const names = selected.map(r => (typeof r === 'string' ? r : (r.name || r)));
                    return names.join(', ');
                  }}
                >
                  {repositories.map((repo, index) => {
                    const value = repo; // support objects or strings
                    const name = repo.name || repo;
                    return (
                      <MenuItem key={index} value={value}>
                        {name}
                      </MenuItem>
                    );
                  })}
                </Select>
              </FormControl>
              <Button
                variant="contained"
                startIcon={<Assessment />}
                onClick={generateMigrationPlan}
                disabled={!isReady || selectedRepos.length === 0 || loading}
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
              <Typography>Analyzing repositories and generating multi-repo migration plan...</Typography>
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
              {/* Summary (multi-repo) */}
              <Card sx={{ mb: 3 }}>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    📊 Cross-Repository Summary
                  </Typography>
                  <Box display="flex" gap={1.5} flexWrap="wrap">
                    <Chip label={`${migrationPlan?.plan_scope?.repositories?.length || 0} Repositories`} />
                    <Chip label={`${migrationPlan?.summary?.totals?.actions || 0} Actions`} color="primary" />
                    <Chip label={`${migrationPlan?.summary?.totals?.services || 0} Services`} color="primary" variant="outlined" />
                    <Chip label={`${migrationPlan?.summary?.totals?.data_models || 0} Data Models`} color="secondary" />
                    <Chip label={`Risk ${Math.round(migrationPlan?.summary?.risk_score || 0)}/100`} />
                    <Chip label={`Effort ${Math.round(migrationPlan?.summary?.effort_score || 0)}/100`} />
                    <Chip label={`Coupling ${Math.round((migrationPlan?.summary?.complexity?.coupling_index || 0) * 100) / 100}`} />
                  </Box>
                </CardContent>
              </Card>

              {/* Dependencies overview */}
              {Array.isArray(migrationPlan?.cross_repo?.dependencies) && migrationPlan.cross_repo.dependencies.length > 0 && (
                <Card sx={{ mb: 3 }}>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      🔗 Cross-Repo Dependencies (Top)
                    </Typography>
                    <List dense>
                      {migrationPlan.cross_repo.dependencies.slice(0, 10).map((dep, idx) => (
                        <ListItem key={idx}>
                          <ListItemText
                            primary={<Typography component="span">{`${dep.from_repo} → ${dep.to_repo}`}</Typography>}
                            secondary={<Typography component="span" variant="body2" color="text.secondary">{`weight=${dep.weight ?? 0} types=${(dep.types || []).join(', ')}`}</Typography>}
                          />
                        </ListItem>
                      ))}
                    </List>
                  </CardContent>
                </Card>
              )}

              {/* Slices and sequence */}
              {Array.isArray(migrationPlan?.slices?.items) && migrationPlan.slices.items.length > 0 && (
                <Card sx={{ mb: 3 }}>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      🧩 Proposed Slices & Sequence
                    </Typography>
                    <List dense>
                      {migrationPlan.slices.items.map((s, idx) => (
                        <ListItem key={idx}>
                          <ListItemText
                            primary={<Typography component="span">{`${s.name} (effort ${s.effort}/5, risk ${s.risk}/5)`}</Typography>}
                            secondary={<Typography component="span" variant="body2" color="text.secondary">{`repos: ${(s.repos || []).join(', ')} | deps: ${(s.dependencies || []).join(', ')}`}</Typography>}
                          />
                        </ListItem>
                      ))}
                    </List>
                    {Array.isArray(migrationPlan?.slices?.sequence) && migrationPlan.slices.sequence.length > 0 && (
                      <>
                        <Divider sx={{ my: 1.5 }} />
                        <Typography variant="body2">Suggested Sequence: {migrationPlan.slices.sequence.join(' → ')}</Typography>
                      </>
                    )}
                  </CardContent>
                </Card>
              )}

              {/* GraphQL Suggestions */}
              <Card sx={{ mb: 3 }}>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    🎯 GraphQL Schema Suggestions
                  </Typography>
                  {Array.isArray(migrationPlan?.graphql?.recommended_types) && migrationPlan.graphql.recommended_types.length > 0 && (
                    <Box sx={{ mb: 2 }}>
                      <Typography variant="subtitle1" gutterBottom>
                        Recommended Types:
                      </Typography>
                      <Box display="flex" gap={1} flexWrap="wrap">
                        {migrationPlan.graphql.recommended_types.map((type, index) => (
                          <Chip key={index} label={type} variant="outlined" />
                        ))}
                      </Box>
                    </Box>
                  )}
                  {migrationPlan?.graphql?.sdl_preview && (
                    <Paper variant="outlined" sx={{ p: 2, whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: 12 }}>
                      {migrationPlan.graphql.sdl_preview}
                    </Paper>
                  )}
                  <Alert severity="info" sx={{ mb: 2 }}>
                    Complete GraphQL schema generation will be available in the next phase.
                  </Alert>

                  {/* Export buttons */}
                  <Box display="flex" gap={1} flexWrap="wrap">
                    <Button
                      variant="outlined"
                      startIcon={<GetApp />}
                      onClick={() => {
                        try {
                          const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
                          const blob = new Blob([JSON.stringify(migrationPlan, null, 2)], { type: 'application/json;charset=utf-8' });
                          const url = URL.createObjectURL(blob);
                          const a = document.createElement('a');
                          a.href = url;
                          a.download = `migration-plan-${timestamp}.json`;
                          document.body.appendChild(a);
                          a.click();
                          a.remove();
                          URL.revokeObjectURL(url);
                        } catch (e) {
                          console.error('Export JSON failed', e);
                        }
                      }}
                    >
                      Export JSON
                    </Button>

                    <Button
                      variant="outlined"
                      startIcon={<GetApp />}
                      onClick={() => {
                        try {
                          const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
                          // Dependencies CSV
                          const deps = Array.isArray(migrationPlan?.cross_repo?.dependencies) ? migrationPlan.cross_repo.dependencies : [];
                          const depsHeader = ['from_repo', 'to_repo', 'weight', 'types'];
                          const depsRows = deps.map(d => [
                            d.from_repo || '',
                            d.to_repo || '',
                            (d.weight ?? 0).toString(),
                            Array.isArray(d.types) ? d.types.join(';') : ''
                          ]);
                          const depsCsv = [depsHeader, ...depsRows]
                            .map(row => row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(','))
                            .join('\n');
                          const depsBlob = new Blob([depsCsv], { type: 'text/csv;charset=utf-8' });
                          const depsUrl = URL.createObjectURL(depsBlob);
                          const a1 = document.createElement('a');
                          a1.href = depsUrl;
                          a1.download = `migration-dependencies-${timestamp}.csv`;
                          document.body.appendChild(a1);
                          a1.click();
                          a1.remove();
                          URL.revokeObjectURL(depsUrl);

                          // Slices CSV
                          const slices = Array.isArray(migrationPlan?.slices?.items) ? migrationPlan.slices.items : [];
                          const slicesHeader = ['name', 'repos', 'effort', 'risk'];
                          const slicesRows = slices.map(s => [
                            s.name || '',
                            Array.isArray(s.repos) ? s.repos.join(';') : '',
                            (s.effort ?? '').toString(),
                            (s.risk ?? '').toString()
                          ]);
                          const slicesCsv = [slicesHeader, ...slicesRows]
                            .map(row => row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(','))
                            .join('\n');
                          const slicesBlob = new Blob([slicesCsv], { type: 'text/csv;charset=utf-8' });
                          const slicesUrl = URL.createObjectURL(slicesBlob);
                          const a2 = document.createElement('a');
                          a2.href = slicesUrl;
                          a2.download = `migration-slices-${timestamp}.csv`;
                          document.body.appendChild(a2);
                          a2.click();
                          a2.remove();
                          URL.revokeObjectURL(slicesUrl);
                        } catch (e) {
                          console.error('Export CSV failed', e);
                        }
                      }}
                    >
                      Export CSV
                    </Button>
                  </Box>
                </CardContent>
              </Card>

              {/* Roadmap */}
              {Array.isArray(migrationPlan?.roadmap?.steps) && migrationPlan.roadmap.steps.length > 0 && (
                <Card sx={{ mb: 3 }}>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      📋 Migration Roadmap
                    </Typography>
                    <List>
                      {migrationPlan.roadmap.steps.map((step, index) => (
                        <React.Fragment key={index}>
                          <ListItem>
                            <ListItemText
                              primary={<Typography component="span">{step}</Typography>}
                              secondary={<Typography component="span" variant="body2" color="text.secondary">{`Step ${index + 1}`}</Typography>}
                            />
                          </ListItem>
                          {index < migrationPlan.roadmap.steps.length - 1 && <Divider />}
                        </React.Fragment>
                      ))}
                    </List>
                  </CardContent>
                </Card>
              )}

              {/* Legacy single-repo chips for continuity when a single repo is selected */}
              {selectedRepos.length === 1 && (
                <Card sx={{ mb: 3 }}>
                  <CardContent>
                    <Typography variant="subtitle1" gutterBottom>
                      Single Repository Summary
                    </Typography>
                    <Box display="flex" gap={2} flexWrap="wrap">
                      <Chip
                        label={`${singleRepoSummary?.business_logic_components || 0} Business Logic Components`}
                        color="primary"
                      />
                      <Chip
                        label={`${singleRepoSummary?.data_models_found || 0} Data Models`}
                        color="secondary"
                      />
                    </Box>
                  </CardContent>
                </Card>
              )}
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
                  <ListItemText primary={<Typography component="span">1. Select one or more repositories from your indexed applications</Typography>} />
                </ListItem>
                <ListItem>
                  <ListItemText primary={<Typography component="span">2. AI analyzes business logic, data models, dependencies, and endpoints</Typography>} />
                </ListItem>
                <ListItem>
                  <ListItemText primary={<Typography component="span">3. Get GraphQL schema suggestions and vertical slice proposals</Typography>} />
                </ListItem>
                <ListItem>
                  <ListItemText primary={<Typography component="span">4. Review a prioritized, step-by-step migration roadmap</Typography>} />
                </ListItem>
                <ListItem>
                  <ListItemText primary={<Typography component="span">5. Export recommendations for your development team</Typography>} />
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