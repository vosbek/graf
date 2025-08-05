import React, { useState, useEffect } from 'react';
import {
  Box, Typography, Grid, Card, CardContent, Button, Chip,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Paper, LinearProgress, Alert, Accordion, AccordionSummary, AccordionDetails,
  Dialog, DialogTitle, DialogContent, DialogActions, TextField,
  FormControlLabel, Checkbox, CircularProgress, Divider,
  List, ListItem, ListItemText, ListItemIcon
} from '@mui/material';
import {
  ExpandMore, AccountTree, Assessment, Speed, Warning,
  CheckCircle, Error, Timeline, Business, Search, PlayArrow
} from '@mui/icons-material';
import { ApiService } from '../services/ApiService';

const CrossRepositoryAnalysis = ({ repositories = [] }) => {
  // State management
  const [selectedRepos, setSelectedRepos] = useState([]);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [migrationPlan, setMigrationPlan] = useState(null);
  const [planLoading, setPlanLoading] = useState(false);
  const [sharedDepsResult, setSharedDepsResult] = useState(null);
  const [sharedDepsLoading, setSharedDepsLoading] = useState(false);
  
  // Dialog states
  const [analysisDialogOpen, setAnalysisDialogOpen] = useState(false);
  const [planDialogOpen, setPlanDialogOpen] = useState(false);
  const [batchDialogOpen, setBatchDialogOpen] = useState(false);
  
  // Analysis configuration
  const [analysisConfig, setAnalysisConfig] = useState({
    include_business_context: true,
    max_depth: 3
  });
  
  // Migration plan configuration
  const [planConfig, setPlanConfig] = useState({
    target_architecture: 'microservices',
    risk_tolerance: 'medium',
    timeline_months: 12
  });
  
  // Batch processing
  const [batchConfig, setBatchConfig] = useState({
    max_concurrent: 8,
    priority_mode: true
  });
  const [batchStatus, setBatchStatus] = useState(null);

  useEffect(() => {
    // Auto-select all repositories initially
    if (repositories.length > 0) {
      setSelectedRepos(repositories.map(r => r.name));
    }
  }, [repositories]);

  const handleRepoSelection = (repoName) => {
    setSelectedRepos(prev => 
      prev.includes(repoName) 
        ? prev.filter(name => name !== repoName)
        : [...prev, repoName]
    );
  };

  const startCrossRepoAnalysis = async () => {
    if (selectedRepos.length < 2) {
      setError('Please select at least 2 repositories for cross-repository analysis');
      return;
    }

    setLoading(true);
    setError('');
    
    try {
      const response = await ApiService.post('/cross-repository/analyze', {
        repository_names: selectedRepos,
        ...analysisConfig
      });
      
      setAnalysisResult(response);
      setAnalysisDialogOpen(false);
    } catch (err) {
      setError(`Analysis failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const generateMigrationPlan = async () => {
    if (!analysisResult) {
      setError('Please run cross-repository analysis first');
      return;
    }

    setPlanLoading(true);
    setError('');
    
    try {
      const response = await ApiService.get('/cross-repository/migration-plan', {
        params: {
          repository_names: selectedRepos,
          ...planConfig
        }
      });
      
      setMigrationPlan(response);
      setPlanDialogOpen(false);
    } catch (err) {
      setError(`Migration plan generation failed: ${err.message}`);
    } finally {
      setPlanLoading(false);
    }
  };

  const analyzeSharedDependencies = async () => {
    if (selectedRepos.length < 2) {
      setError('Please select at least 2 repositories for shared dependency analysis');
      return;
    }

    setSharedDepsLoading(true);
    setError('');
    
    try {
      const response = await ApiService.get('/cross-repository/shared-dependencies', {
        params: {
          repository_names: selectedRepos
        }
      });
      
      setSharedDepsResult(response);
    } catch (err) {
      setError(`Shared dependency analysis failed: ${err.message}`);
    } finally {
      setSharedDepsLoading(false);
    }
  };

  const startBatchProcessing = async () => {
    if (selectedRepos.length === 0) {
      setError('Please select repositories for batch processing');
      return;
    }

    try {
      const repositoriesData = selectedRepos.map(repoName => {
        const repo = repositories.find(r => r.name === repoName);
        return {
          repo_name: repoName,
          repo_path: repo?.path || `/data/repositories/${repoName}`,
          priority: repo?.priority || 5
        };
      });

      const response = await ApiService.post('/cross-repository/batch-process', {
        repositories: repositoriesData,
        ...batchConfig
      });
      
      setBatchStatus(response);
      setBatchDialogOpen(false);
      
      // Start monitoring batch status
      monitorBatchStatus(response.batch_id);
    } catch (err) {
      setError(`Batch processing failed: ${err.message}`);
    }
  };

  const monitorBatchStatus = async (batchId) => {
    const checkStatus = async () => {
      try {
        const response = await ApiService.get(`/cross-repository/batch-status/${batchId}`);
        setBatchStatus(response);
        
        // Continue monitoring if still in progress
        const progress = response.progress;
        if (progress.in_progress > 0 || progress.completed + progress.failed < progress.total) {
          setTimeout(checkStatus, 5000); // Check every 5 seconds
        }
      } catch (err) {
        console.error('Failed to check batch status:', err);
      }
    };
    
    checkStatus();
  };

  const getComplexityColor = (complexity) => {
    if (complexity >= 80) return 'error';
    if (complexity >= 60) return 'warning';
    if (complexity >= 30) return 'info';
    return 'success';
  };

  const getPriorityIcon = (priority) => {
    switch (priority) {
      case 'CRITICAL': return <Error color="error" />;
      case 'HIGH': return <Warning color="warning" />;
      case 'MEDIUM': return <CheckCircle color="info" />;
      default: return <CheckCircle color="success" />;
    }
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Cross-Repository Analysis
      </Typography>
      <Typography variant="body1" color="text.secondary" paragraph>
        Analyze business relationships, dependencies, and migration complexity across multiple repositories 
        for enterprise legacy system migration planning.
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {/* Repository Selection */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Repository Selection ({selectedRepos.length} selected)
          </Typography>
          <Grid container spacing={1}>
            {repositories.map((repo) => (
              <Grid item key={repo.name}>
                <Chip
                  label={repo.name}
                  onClick={() => handleRepoSelection(repo.name)}
                  color={selectedRepos.includes(repo.name) ? 'primary' : 'default'}
                  variant={selectedRepos.includes(repo.name) ? 'filled' : 'outlined'}
                  icon={selectedRepos.includes(repo.name) ? <CheckCircle /> : undefined}
                />
              </Grid>
            ))}
          </Grid>
        </CardContent>
      </Card>

      {/* Action Buttons */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item>
          <Button
            variant="contained"
            startIcon={<AccountTree />}
            onClick={() => setAnalysisDialogOpen(true)}
            disabled={selectedRepos.length < 2 || loading}
          >
            Analyze Cross-Repository Relationships
          </Button>
        </Grid>
        <Grid item>
          <Button
            variant="outlined"
            startIcon={<Timeline />}
            onClick={() => setPlanDialogOpen(true)}
            disabled={!analysisResult || planLoading}
          >
            Generate Migration Plan
          </Button>
        </Grid>
        <Grid item>
          <Button
            variant="outlined"
            startIcon={<Search />}
            onClick={analyzeSharedDependencies}
            disabled={selectedRepos.length < 2 || sharedDepsLoading}
          >
            Analyze Shared Dependencies
          </Button>
        </Grid>
        <Grid item>
          <Button
            variant="outlined"
            startIcon={<Speed />}
            onClick={() => setBatchDialogOpen(true)}
            disabled={selectedRepos.length === 0}
          >
            Batch Process Repositories
          </Button>
        </Grid>
      </Grid>

      {/* Loading States */}
      {loading && (
        <Box sx={{ mb: 3 }}>
          <LinearProgress />
          <Typography variant="body2" sx={{ mt: 1 }}>
            Analyzing cross-repository relationships...
          </Typography>
        </Box>
      )}

      {planLoading && (
        <Box sx={{ mb: 3 }}>
          <LinearProgress color="secondary" />
          <Typography variant="body2" sx={{ mt: 1 }}>
            Generating migration plan...
          </Typography>
        </Box>
      )}

      {sharedDepsLoading && (
        <Box sx={{ mb: 3 }}>
          <LinearProgress color="success" />
          <Typography variant="body2" sx={{ mt: 1 }}>
            Analyzing shared dependencies...
          </Typography>
        </Box>
      )}

      {/* Batch Status */}
      {batchStatus && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Batch Processing Status: {batchStatus.batch_id}
            </Typography>
            {batchStatus.progress && (
              <Box>
                <LinearProgress 
                  variant="determinate" 
                  value={batchStatus.progress.percentage} 
                  sx={{ mb: 1 }}
                />
                <Typography variant="body2">
                  {batchStatus.progress.completed}/{batchStatus.progress.total} completed 
                  ({batchStatus.progress.percentage.toFixed(1)}%)
                </Typography>
                {batchStatus.progress.failed > 0 && (
                  <Typography variant="body2" color="error">
                    {batchStatus.progress.failed} failed
                  </Typography>
                )}
              </Box>
            )}
          </CardContent>
        </Card>
      )}

      {/* Analysis Results */}
      {analysisResult && (
        <Box>
          {/* Summary Cards */}
          <Grid container spacing={3} sx={{ mb: 3 }}>
            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Typography color="text.secondary" gutterBottom>
                    Total Repositories
                  </Typography>
                  <Typography variant="h4">
                    {analysisResult.total_repositories}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Typography color="text.secondary" gutterBottom>
                    Cross-Repo Relationships
                  </Typography>
                  <Typography variant="h4">
                    {analysisResult.total_relationships}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Typography color="text.secondary" gutterBottom>
                    Business Domains
                  </Typography>
                  <Typography variant="h4">
                    {Object.keys(analysisResult.business_domains).length}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Typography color="text.secondary" gutterBottom>
                    Analysis Time
                  </Typography>
                  <Typography variant="h4">
                    {analysisResult.analysis_time.toFixed(1)}s
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          </Grid>

          {/* Repository Profiles */}
          <Accordion defaultExpanded sx={{ mb: 2 }}>
            <AccordionSummary expandIcon={<ExpandMore />}>
              <Typography variant="h6">Repository Migration Profiles</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <TableContainer component={Paper}>
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell>Repository</TableCell>
                      <TableCell>Complexity</TableCell>
                      <TableCell>Priority</TableCell>
                      <TableCell>Components</TableCell>
                      <TableCell>Effort (Days)</TableCell>
                      <TableCell>Dependencies</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {Object.entries(analysisResult.repository_profiles).map(([name, profile]) => (
                      <TableRow key={name}>
                        <TableCell>{name}</TableCell>
                        <TableCell>
                          <Box display="flex" alignItems="center" gap={1}>
                            <LinearProgress
                              variant="determinate"
                              value={profile.migration_complexity}
                              color={getComplexityColor(profile.migration_complexity)}
                              sx={{ width: 100, height: 8 }}
                            />
                            <Typography variant="body2">
                              {profile.migration_complexity.toFixed(0)}
                            </Typography>
                          </Box>
                        </TableCell>
                        <TableCell>
                          <Chip
                            icon={getPriorityIcon(profile.migration_priority)}
                            label={profile.migration_priority}
                            size="small"
                            color={getComplexityColor(profile.migration_complexity)}
                          />
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2">
                            BR: {profile.business_rules_count} |
                            SA: {profile.struts_actions_count} |
                            CORBA: {profile.corba_interfaces_count}
                          </Typography>
                        </TableCell>
                        <TableCell>{profile.estimated_effort_days}</TableCell>
                        <TableCell>
                          <Typography variant="body2">
                            Out: {profile.external_dependencies} |
                            In: {profile.internal_dependencies}
                          </Typography>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </AccordionDetails>
          </Accordion>

          {/* Migration Order */}
          <Accordion sx={{ mb: 2 }}>
            <AccordionSummary expandIcon={<ExpandMore />}>
              <Typography variant="h6">Recommended Migration Order</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <List>
                {analysisResult.migration_order.map((repo, index) => (
                  <ListItem key={repo}>
                    <ListItemIcon>
                      <Typography variant="h6" color="primary">
                        {index + 1}
                      </Typography>
                    </ListItemIcon>
                    <ListItemText
                      primary={repo}
                      secondary={`Priority based on dependencies and complexity`}
                    />
                  </ListItem>
                ))}
              </List>
            </AccordionDetails>
          </Accordion>

          {/* Critical Paths */}
          {analysisResult.critical_paths.length > 0 && (
            <Accordion sx={{ mb: 2 }}>
              <AccordionSummary expandIcon={<ExpandMore />}>
                <Typography variant="h6">
                  Critical Dependency Paths ({analysisResult.critical_paths.length})
                </Typography>
              </AccordionSummary>
              <AccordionDetails>
                {analysisResult.critical_paths.map((path, index) => (
                  <Box key={index} sx={{ mb: 2 }}>
                    <Typography variant="subtitle2" gutterBottom>
                      Path {index + 1}: {path.length} repositories
                    </Typography>
                    <Box display="flex" alignItems="center" gap={1} flexWrap="wrap">
                      {path.map((repo, repoIndex) => (
                        <React.Fragment key={repo}>
                          <Chip label={repo} size="small" />
                          {repoIndex < path.length - 1 && <Typography>→</Typography>}
                        </React.Fragment>
                      ))}
                    </Box>
                  </Box>
                ))}
              </AccordionDetails>
            </Accordion>
          )}

          {/* Recommendations */}
          <Accordion sx={{ mb: 2 }}>
            <AccordionSummary expandIcon={<ExpandMore />}>
              <Typography variant="h6">Analysis Recommendations</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <List>
                {analysisResult.recommendations.map((recommendation, index) => (
                  <ListItem key={index}>
                    <ListItemIcon>
                      <Business color="primary" />
                    </ListItemIcon>
                    <ListItemText primary={recommendation} />
                  </ListItem>
                ))}
              </List>
            </AccordionDetails>
          </Accordion>
        </Box>
      )}

      {/* Shared Dependencies Results */}
      {sharedDepsResult && (
        <Box sx={{ mt: 3 }}>
          <Typography variant="h5" gutterBottom>
            Shared Dependencies Analysis: {sharedDepsResult.analysis_id}
          </Typography>
          
          {/* Shared Dependencies Overview */}
          <Grid container spacing={3} sx={{ mb: 3 }}>
            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Typography color="text.secondary" gutterBottom>
                    Total Dependencies
                  </Typography>
                  <Typography variant="h6">
                    {sharedDepsResult.total_dependencies}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Typography color="text.secondary" gutterBottom>
                    Version Conflicts
                  </Typography>
                  <Typography variant="h6" color={sharedDepsResult.version_conflicts.length > 0 ? "error" : "success"}>
                    {sharedDepsResult.version_conflicts.length}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Typography color="text.secondary" gutterBottom>
                    Framework Types
                  </Typography>
                  <Typography variant="h6">
                    {Object.keys(sharedDepsResult.framework_distribution).length}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Typography color="text.secondary" gutterBottom>
                    Analysis Time
                  </Typography>
                  <Typography variant="h6">
                    {sharedDepsResult.analysis_time.toFixed(1)}s
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          </Grid>

          {/* Framework Distribution */}
          <Accordion defaultExpanded sx={{ mb: 2 }}>
            <AccordionSummary expandIcon={<ExpandMore />}>
              <Typography variant="h6">Framework Distribution</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Grid container spacing={2}>
                {Object.entries(sharedDepsResult.framework_distribution).map(([framework, count]) => (
                  <Grid item key={framework}>
                    <Chip
                      label={`${framework}: ${count}`}
                      color={framework === 'struts' || framework === 'corba' || framework === 'jsp' ? 'warning' : 'primary'}
                      variant="outlined"
                    />
                  </Grid>
                ))}
              </Grid>
            </AccordionDetails>
          </Accordion>

          {/* Version Conflicts */}
          {sharedDepsResult.version_conflicts.length > 0 && (
            <Accordion sx={{ mb: 2 }}>
              <AccordionSummary expandIcon={<ExpandMore />}>
                <Typography variant="h6">
                  Version Conflicts ({sharedDepsResult.version_conflicts.length})
                </Typography>
              </AccordionSummary>
              <AccordionDetails>
                <TableContainer component={Paper}>
                  <Table>
                    <TableHead>
                      <TableRow>
                        <TableCell>Dependency</TableCell>
                        <TableCell>Severity</TableCell>
                        <TableCell>Conflicting Versions</TableCell>
                        <TableCell>Affected Repositories</TableCell>
                        <TableCell>Resolution Strategy</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {sharedDepsResult.version_conflicts.map((conflict, index) => (
                        <TableRow key={index}>
                          <TableCell>
                            <Typography variant="body2" fontWeight="bold">
                              {conflict.group_id}:{conflict.artifact_id}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Chip
                              label={conflict.severity}
                              size="small"
                              color={
                                conflict.severity === 'CRITICAL' ? 'error' :
                                conflict.severity === 'HIGH' ? 'warning' :
                                conflict.severity === 'MEDIUM' ? 'info' : 'default'
                              }
                            />
                          </TableCell>
                          <TableCell>
                            <Box display="flex" gap={0.5} flexWrap="wrap">
                              {conflict.conflicting_versions.map(version => (
                                <Chip key={version} label={version} size="small" variant="outlined" />
                              ))}
                            </Box>
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2">
                              {conflict.affected_repositories.join(', ')}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2">
                              {conflict.resolution_strategy}
                            </Typography>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </AccordionDetails>
            </Accordion>
          )}

          {/* Shared Dependencies List */}
          <Accordion sx={{ mb: 2 }}>
            <AccordionSummary expandIcon={<ExpandMore />}>
              <Typography variant="h6">
                Shared Dependencies ({sharedDepsResult.shared_dependencies.length})
              </Typography>
            </AccordionSummary>
            <AccordionDetails>
              <TableContainer component={Paper}>
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell>Dependency</TableCell>
                      <TableCell>Framework Type</TableCell>
                      <TableCell>Usage Count</TableCell>
                      <TableCell>Versions</TableCell>
                      <TableCell>Priority</TableCell>
                      <TableCell>Repositories</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {sharedDepsResult.shared_dependencies.slice(0, 20).map((dep, index) => (
                      <TableRow key={index}>
                        <TableCell>
                          <Typography variant="body2" fontWeight="bold">
                            {dep.group_id}:{dep.artifact_id}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Chip
                            label={dep.framework_type}
                            size="small"
                            color={dep.framework_type === 'struts' || dep.framework_type === 'corba' || dep.framework_type === 'jsp' ? 'warning' : 'default'}
                          />
                        </TableCell>
                        <TableCell>{dep.usage_count}</TableCell>
                        <TableCell>
                          <Box display="flex" gap={0.5} flexWrap="wrap">
                            {dep.versions.slice(0, 3).map(version => (
                              <Chip 
                                key={version} 
                                label={version} 
                                size="small" 
                                variant="outlined"
                                color={dep.version_conflicts ? 'warning' : 'default'}
                              />
                            ))}
                            {dep.versions.length > 3 && (
                              <Chip label={`+${dep.versions.length - 3} more`} size="small" variant="outlined" />
                            )}
                          </Box>
                        </TableCell>
                        <TableCell>
                          <Chip
                            label={dep.migration_priority}
                            size="small"
                            color={
                              dep.migration_priority === 'HIGH' ? 'error' :
                              dep.migration_priority === 'MEDIUM' ? 'warning' : 'success'
                            }
                          />
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2">
                            {dep.repositories.join(', ')}
                          </Typography>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
              {sharedDepsResult.shared_dependencies.length > 20 && (
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  Showing first 20 of {sharedDepsResult.shared_dependencies.length} shared dependencies
                </Typography>
              )}
            </AccordionDetails>
          </Accordion>

          {/* Consolidation Opportunities */}
          {sharedDepsResult.consolidation_opportunities.length > 0 && (
            <Accordion sx={{ mb: 2 }}>
              <AccordionSummary expandIcon={<ExpandMore />}>
                <Typography variant="h6">
                  Consolidation Opportunities ({sharedDepsResult.consolidation_opportunities.length})
                </Typography>
              </AccordionSummary>
              <AccordionDetails>
                {sharedDepsResult.consolidation_opportunities.map((opportunity, index) => (
                  <Box key={index} sx={{ mb: 2, p: 2, border: 1, borderColor: 'divider', borderRadius: 1 }}>
                    <Typography variant="h6" gutterBottom>
                      {opportunity.framework} Framework Consolidation
                    </Typography>
                    <Grid container spacing={2}>
                      <Grid item xs={6} sm={3}>
                        <Typography variant="body2" color="text.secondary">
                          Dependencies: {opportunity.dependencies_count}
                        </Typography>
                      </Grid>
                      <Grid item xs={6} sm={3}>
                        <Typography variant="body2" color="text.secondary">
                          Total Usage: {opportunity.total_usage}
                        </Typography>
                      </Grid>
                      <Grid item xs={6} sm={3}>
                        <Chip
                          label={opportunity.impact}
                          size="small"
                          color={opportunity.impact === 'HIGH' ? 'error' : 'info'}
                        />
                      </Grid>
                      <Grid item xs={6} sm={3}>
                        <Typography variant="body2" color="text.secondary">
                          Conflicts: {opportunity.conflicts_count || 0}
                        </Typography>
                      </Grid>
                    </Grid>
                    <Typography variant="body2" sx={{ mt: 1 }}>
                      {opportunity.recommendation}
                    </Typography>
                    <Box sx={{ mt: 1 }}>
                      <Typography variant="caption" color="text.secondary">
                        Dependencies: {opportunity.dependencies.slice(0, 5).join(', ')}
                        {opportunity.dependencies.length > 5 && ` (+${opportunity.dependencies.length - 5} more)`}
                      </Typography>
                    </Box>
                  </Box>
                ))}
              </AccordionDetails>
            </Accordion>
          )}

          {/* Migration Recommendations */}
          <Accordion sx={{ mb: 2 }}>
            <AccordionSummary expandIcon={<ExpandMore />}>
              <Typography variant="h6">Migration Recommendations</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <List>
                {sharedDepsResult.migration_recommendations.map((recommendation, index) => (
                  <ListItem key={index}>
                    <ListItemIcon>
                      <Business color="primary" />
                    </ListItemIcon>
                    <ListItemText primary={recommendation} />
                  </ListItem>
                ))}
              </List>
            </AccordionDetails>
          </Accordion>
        </Box>
      )}

      {/* Migration Plan Results */}
      {migrationPlan && (
        <Box sx={{ mt: 3 }}>
          <Typography variant="h5" gutterBottom>
            Migration Plan: {migrationPlan.migration_plan_id}
          </Typography>
          
          {/* Plan Overview */}
          <Grid container spacing={3} sx={{ mb: 3 }}>
            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Typography color="text.secondary" gutterBottom>
                    Total Effort
                  </Typography>
                  <Typography variant="h6">
                    {migrationPlan.overall_metrics.total_effort_days} days
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Typography color="text.secondary" gutterBottom>
                    Timeline
                  </Typography>
                  <Typography variant="h6">
                    {migrationPlan.overall_metrics.estimated_timeline_weeks} weeks
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Typography color="text.secondary" gutterBottom>
                    Team Size
                  </Typography>
                  <Typography variant="h6">
                    {migrationPlan.overall_metrics.estimated_team_size} people
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Typography color="text.secondary" gutterBottom>
                    Risk Level
                  </Typography>
                  <Chip
                    label={migrationPlan.risk_assessment.overall_risk}
                    color={migrationPlan.risk_assessment.overall_risk === 'HIGH' ? 'error' : 'warning'}
                  />
                </CardContent>
              </Card>
            </Grid>
          </Grid>

          {/* Migration Phases */}
          <Accordion defaultExpanded sx={{ mb: 2 }}>
            <AccordionSummary expandIcon={<ExpandMore />}>
              <Typography variant="h6">Migration Phases</Typography>
            </AccordionSummary>
            <AccordionDetails>
              {migrationPlan.migration_phases.map((phase, index) => (
                <Box key={index} sx={{ mb: 2, p: 2, border: 1, borderColor: 'divider', borderRadius: 1 }}>
                  <Typography variant="h6" gutterBottom>
                    Phase {phase.phase}: {phase.repositories.join(', ')}
                  </Typography>
                  <Grid container spacing={2}>
                    <Grid item xs={6} sm={3}>
                      <Typography variant="body2" color="text.secondary">
                        Effort: {phase.estimated_effort_days} days
                      </Typography>
                    </Grid>
                    <Grid item xs={6} sm={3}>
                      <Typography variant="body2" color="text.secondary">
                        Duration: {phase.estimated_duration_weeks} weeks
                      </Typography>
                    </Grid>
                    <Grid item xs={6} sm={3}>
                      <Chip
                        label={phase.risk_level}
                        size="small"
                        color={phase.risk_level === 'HIGH' ? 'error' : 'info'}
                      />
                    </Grid>
                    <Grid item xs={6} sm={3}>
                      {phase.parallel_execution && (
                        <Chip label="Parallel" size="small" color="success" />
                      )}
                    </Grid>
                  </Grid>
                </Box>
              ))}
            </AccordionDetails>
          </Accordion>
        </Box>
      )}

      {/* Analysis Configuration Dialog */}
      <Dialog open={analysisDialogOpen} onClose={() => setAnalysisDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Configure Cross-Repository Analysis</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 1 }}>
            <FormControlLabel
              control={
                <Checkbox
                  checked={analysisConfig.include_business_context}
                  onChange={(e) => setAnalysisConfig(prev => ({
                    ...prev,
                    include_business_context: e.target.checked
                  }))}
                />
              }
              label="Include business context analysis"
            />
            <TextField
              fullWidth
              label="Maximum Depth"
              type="number"
              value={analysisConfig.max_depth}
              onChange={(e) => setAnalysisConfig(prev => ({
                ...prev,
                max_depth: parseInt(e.target.value) || 3
              }))}
              inputProps={{ min: 1, max: 5 }}
              sx={{ mt: 2 }}
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAnalysisDialogOpen(false)}>Cancel</Button>
          <Button onClick={startCrossRepoAnalysis} variant="contained" disabled={loading}>
            {loading ? <CircularProgress size={20} /> : 'Start Analysis'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Migration Plan Dialog */}
      <Dialog open={planDialogOpen} onClose={() => setPlanDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Configure Migration Plan</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 1 }}>
            <TextField
              fullWidth
              label="Target Architecture"
              value={planConfig.target_architecture}
              onChange={(e) => setPlanConfig(prev => ({
                ...prev,
                target_architecture: e.target.value
              }))}
              sx={{ mb: 2 }}
            />
            <TextField
              fullWidth
              label="Risk Tolerance"
              select
              SelectProps={{ native: true }}
              value={planConfig.risk_tolerance}
              onChange={(e) => setPlanConfig(prev => ({
                ...prev,
                risk_tolerance: e.target.value
              }))}
              sx={{ mb: 2 }}
            >
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </TextField>
            <TextField
              fullWidth
              label="Timeline (Months)"
              type="number"
              value={planConfig.timeline_months}
              onChange={(e) => setPlanConfig(prev => ({
                ...prev,
                timeline_months: parseInt(e.target.value) || 12
              }))}
              inputProps={{ min: 1, max: 60 }}
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPlanDialogOpen(false)}>Cancel</Button>
          <Button onClick={generateMigrationPlan} variant="contained" disabled={planLoading}>
            {planLoading ? <CircularProgress size={20} /> : 'Generate Plan'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Batch Processing Dialog */}
      <Dialog open={batchDialogOpen} onClose={() => setBatchDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Configure Batch Processing</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 1 }}>
            <TextField
              fullWidth
              label="Max Concurrent Processes"
              type="number"
              value={batchConfig.max_concurrent}
              onChange={(e) => setBatchConfig(prev => ({
                ...prev,
                max_concurrent: parseInt(e.target.value) || 8
              }))}
              inputProps={{ min: 1, max: 20 }}
              sx={{ mb: 2 }}
            />
            <FormControlLabel
              control={
                <Checkbox
                  checked={batchConfig.priority_mode}
                  onChange={(e) => setBatchConfig(prev => ({
                    ...prev,
                    priority_mode: e.target.checked
                  }))}
                />
              }
              label="Process high-priority repositories first"
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setBatchDialogOpen(false)}>Cancel</Button>
          <Button onClick={startBatchProcessing} variant="contained">
            Start Batch Processing
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default CrossRepositoryAnalysis;