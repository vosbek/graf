import React, { useState, useEffect } from 'react';
import {
  Box, Typography, Card, CardContent, Button, Alert, CircularProgress,
  Grid, Tabs, Tab, Table, TableBody, TableCell, TableContainer,
  TableHead, TableRow, Paper, Chip, LinearProgress, Divider,
  Accordion, AccordionSummary, AccordionDetails, List, ListItem,
  ListItemText, ListItemIcon, IconButton, Tooltip
} from '@mui/material';
import {
  ExpandMore, BusinessCenter, AccountTree, Assessment,
  Hub, Warning, CheckCircle, Error, Info,
  Timeline, PlayArrow, Schedule, TrendingUp
} from '@mui/icons-material';
import { ApiService } from '../services/ApiService';
import RepositorySelector from './RepositorySelector';
import { useSystemHealth } from '../context/SystemHealthContext';

function MultiRepoAnalysis() {
  const [selectedRepositories, setSelectedRepositories] = useState([]);
  const [analysisResults, setAnalysisResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState(0);

  // Analysis options
  const [includeBusinessFlows, setIncludeBusinessFlows] = useState(true);
  const [includeDependencies, setIncludeDependencies] = useState(true);
  const [includeMigrationImpact, setIncludeMigrationImpact] = useState(false);

  const { isReady, isLoading: healthLoading, error: healthError } = useSystemHealth();

  const handleAnalyze = async () => {
    if (!isReady) {
      setError('System is not ready. Please wait for readiness before running analysis.');
      return;
    }
    if (selectedRepositories.length === 0) {
      setError('Please select at least one repository');
      return;
    }

    try {
      setLoading(true);
      setError('');

      // Use canonical multi-repo GET endpoint
      const repoNames = selectedRepositories.map(r => (typeof r === 'string' ? r : (r.name || r)));
      const results = await ApiService.getMultiRepoMigrationPlan(repoNames);
      setAnalysisResults({
        repository_count: repoNames.length,
        ...results
      });

    } catch (error) {
      // ApiService interceptor normalizes to Error(message)
      setError(error?.message || 'Analysis failed');
    } finally {
      setLoading(false);
    }
  };

  const renderAnalysisSummary = () => {
    if (!analysisResults) return null;

    const { summary } = analysisResults;

    return (
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Analysis Summary
          </Typography>
          <Grid container spacing={3}>
            <Grid item xs={12} sm={6} md={3}>
              <Box textAlign="center">
                <Typography variant="h4" color="primary">
                  {analysisResults.repository_count}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Repositories
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Box textAlign="center">
                <Typography variant="h4" color="secondary">
                  {summary.total_business_flows || 0}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Business Flows
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Box textAlign="center">
                <Typography variant="h4" color="info.main">
                  {summary.total_dependencies || 0}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Cross-Repo Dependencies
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Box textAlign="center">
                <Typography variant="h4" color="warning.main">
                  {summary.total_integrations || 0}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Integration Points
                </Typography>
              </Box>
            </Grid>
          </Grid>
        </CardContent>
      </Card>
    );
  };

  const renderBusinessFlows = () => {
    const businessFlows = analysisResults?.analysis_results?.business_flows || [];

    if (businessFlows.length === 0) {
      return (
        <Alert severity="info">
          No cross-repository business flows found for the selected repositories.
        </Alert>
      );
    }

    return (
      <Box>
        <Typography variant="h6" gutterBottom>
          Cross-Repository Business Flows
        </Typography>
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Flow Name</TableCell>
                <TableCell>Repositories</TableCell>
                <TableCell>Business Value</TableCell>
                <TableCell>Migration Order</TableCell>
                <TableCell>Risk Level</TableCell>
                <TableCell>Effort (Weeks)</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {businessFlows.map((flow, index) => (
                <TableRow key={index}>
                  <TableCell>
                    <Box display="flex" alignItems="center">
                      <BusinessCenter sx={{ mr: 1 }} />
                      {flow.name || 'Unnamed Flow'}
                    </Box>
                  </TableCell>
                  <TableCell>
                    {flow.involved_repositories?.map(repo => (
                      <Chip key={repo} label={repo} size="small" sx={{ mr: 0.5 }} />
                    )) || 'N/A'}
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={flow.business_value || 'medium'}
                      color={flow.business_value === 'high' ? 'success' : 
                             flow.business_value === 'low' ? 'default' : 'primary'}
                      size="small"
                    />
                  </TableCell>
                  <TableCell>{flow.migration_order || 'N/A'}</TableCell>
                  <TableCell>
                    <Chip
                      label={flow.risk_level || 'medium'}
                      color={flow.risk_level === 'high' ? 'error' : 
                             flow.risk_level === 'low' ? 'success' : 'warning'}
                      size="small"
                    />
                  </TableCell>
                  <TableCell>{flow.estimated_effort_weeks || 'N/A'}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Box>
    );
  };

  const renderDependencies = () => {
    const dependencies = analysisResults?.analysis_results?.cross_repo_dependencies || [];
    const sharedOperations = analysisResults?.analysis_results?.shared_business_operations || [];

    return (
      <Box>
        {/* Cross-Repository Dependencies */}
        <Accordion defaultExpanded>
          <AccordionSummary expandIcon={<ExpandMore />}>
            <Typography variant="h6">
              Cross-Repository Dependencies ({dependencies.length})
            </Typography>
          </AccordionSummary>
          <AccordionDetails>
            {dependencies.length === 0 ? (
              <Alert severity="info">
                No cross-repository dependencies found.
              </Alert>
            ) : (
              <TableContainer component={Paper}>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Source</TableCell>
                      <TableCell>Target</TableCell>
                      <TableCell>Dependency Type</TableCell>
                      <TableCell>Strength</TableCell>
                      <TableCell>Criticality</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {dependencies.map((dep, index) => (
                      <TableRow key={index}>
                        <TableCell>{dep.source_name || dep.source}</TableCell>
                        <TableCell>{dep.target_name || dep.target}</TableCell>
                        <TableCell>{dep.dependency_type || 'N/A'}</TableCell>
                        <TableCell>
                          <Box display="flex" alignItems="center">
                            <LinearProgress
                              variant="determinate"
                              value={dep.strength === 'high' ? 100 : dep.strength === 'medium' ? 60 : 30}
                              sx={{ width: 60, mr: 1 }}
                            />
                            {dep.strength || 'medium'}
                          </Box>
                        </TableCell>
                        <TableCell>
                          <Chip
                            label={dep.criticality || 'medium'}
                            color={dep.criticality === 'critical' ? 'error' : 
                                   dep.criticality === 'high' ? 'warning' : 'default'}
                            size="small"
                          />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </AccordionDetails>
        </Accordion>

        {/* Shared Business Operations */}
        <Accordion sx={{ mt: 2 }}>
          <AccordionSummary expandIcon={<ExpandMore />}>
            <Typography variant="h6">
              Shared Business Operations ({sharedOperations.length})
            </Typography>
          </AccordionSummary>
          <AccordionDetails>
            {sharedOperations.length === 0 ? (
              <Alert severity="info">
                No shared business operations found across the selected repositories.
              </Alert>
            ) : (
              <List>
                {sharedOperations.map((operation, index) => (
                  <ListItem key={index}>
                    <ListItemIcon>
                      <BusinessCenter />
                    </ListItemIcon>
                    <ListItemText
                      primary={<Typography component="span">{operation.name}</Typography>}
                      secondary={
                        <Box>
                          <Typography variant="body2" color="text.secondary" component="span" sx={{ display: 'block' }}>
                            Domain: {operation.business_domain} |
                            Implementing repositories: {operation.implementing_repos?.join(', ')}
                          </Typography>
                          <Chip
                            label={`Complexity: ${operation.migration_complexity || 'N/A'}`}
                            size="small"
                            sx={{ mt: 0.5 }}
                          />
                        </Box>
                      }
                    />
                  </ListItem>
                ))}
              </List>
            )}
          </AccordionDetails>
        </Accordion>
      </Box>
    );
  };

  const renderMigrationImpact = () => {
    const migrationImpact = analysisResults?.analysis_results?.migration_impact || [];

    if (migrationImpact.length === 0) {
      return (
        <Alert severity="info">
          No migration impact data available. Enable migration impact analysis to see detailed information.
        </Alert>
      );
    }

    const totalEffort = migrationImpact.reduce((sum, flow) => sum + (flow.estimated_effort_weeks || 0), 0);
    const highRiskFlows = migrationImpact.filter(flow => flow.risk_level === 'high');

    return (
      <Box>
        {/* Migration Summary */}
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Migration Impact Summary
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={12} sm={4}>
                <Box textAlign="center">
                  <Typography variant="h4" color="primary">
                    {migrationImpact.length}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Affected Flows
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={12} sm={4}>
                <Box textAlign="center">
                  <Typography variant="h4" color="info.main">
                    {totalEffort}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Total Effort (Weeks)
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={12} sm={4}>
                <Box textAlign="center">
                  <Typography variant="h4" color="error.main">
                    {highRiskFlows.length}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    High Risk Flows
                  </Typography>
                </Box>
              </Grid>
            </Grid>
          </CardContent>
        </Card>

        {/* Migration Flows */}
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Flow Name</TableCell>
                <TableCell>Affected Repositories</TableCell>
                <TableCell>Risk Level</TableCell>
                <TableCell>Effort (Weeks)</TableCell>
                <TableCell>Affected Components</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {migrationImpact.map((flow, index) => (
                <TableRow key={index}>
                  <TableCell>
                    <Box display="flex" alignItems="center">
                      <Timeline sx={{ mr: 1 }} />
                      {flow.name}
                    </Box>
                  </TableCell>
                  <TableCell>
                    {flow.affected_repositories?.map(repo => (
                      <Chip key={repo} label={repo} size="small" sx={{ mr: 0.5 }} />
                    )) || 'N/A'}
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={flow.risk_level || 'medium'}
                      color={flow.risk_level === 'high' ? 'error' : 
                             flow.risk_level === 'low' ? 'success' : 'warning'}
                      size="small"
                    />
                  </TableCell>
                  <TableCell>{flow.estimated_effort_weeks || 'N/A'}</TableCell>
                  <TableCell>{flow.affected_components || 0}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Box>
    );
  };

  const renderIntegrationPoints = () => {
    const integrationPoints = analysisResults?.analysis_results?.integration_points || [];

    if (integrationPoints.length === 0) {
      return (
        <Alert severity="info">
          No integration points found for the selected repositories.
        </Alert>
      );
    }

    return (
      <Box>
        <Typography variant="h6" gutterBottom>
          Integration Points
        </Typography>
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Integration Name</TableCell>
                <TableCell>Repository</TableCell>
                <TableCell>Integration Type</TableCell>
                <TableCell>External System</TableCell>
                <TableCell>Data Sensitivity</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {integrationPoints.map((integration, index) => (
                <TableRow key={index}>
                  <TableCell>
                    <Box display="flex" alignItems="center">
                      <Hub sx={{ mr: 1 }} />
                      {integration.name}
                    </Box>
                  </TableCell>
                  <TableCell>{integration.repository}</TableCell>
                  <TableCell>{integration.integration_type || 'N/A'}</TableCell>
                  <TableCell>{integration.external_system || 'N/A'}</TableCell>
                  <TableCell>
                    <Chip
                      label={integration.data_sensitivity || 'unknown'}
                      color={integration.data_sensitivity === 'high' ? 'error' : 
                             integration.data_sensitivity === 'medium' ? 'warning' : 'default'}
                      size="small"
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Box>
    );
  };

  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom>
        Multi-Repository Analysis
      </Typography>
      <Typography variant="body1" color="text.secondary" paragraph>
        Analyze business flows, dependencies, and relationships across multiple repositories for enterprise-scale insights.
      </Typography>

      {(!isReady || healthLoading || healthError) && (
        <Alert severity={healthError ? 'error' : 'info'} sx={{ mb: 2 }}>
          {!isReady ? 'System is starting up. Analysis is disabled until the system is ready.' :
           healthLoading ? 'Checking system readiness...' :
           `Health error: ${healthError}`}
        </Alert>
      )}

      {/* Repository Selection */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          {/* Wrap disabled interactive content in span to avoid MUI Tooltip disabled-child warnings if RepoSelector uses Tooltips */}
          <span style={{ display: 'block' }}>
            <RepositorySelector
              onSelectionChange={setSelectedRepositories}
              initialSelection={selectedRepositories}
              maxRepositories={100}
            />
          </span>
        </CardContent>
      </Card>

      {/* Analysis Options */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Analysis Options
          </Typography>
          <Grid container spacing={2} alignItems="center">
            <Grid item>
              <span>
                <Button
                  variant={includeBusinessFlows ? "contained" : "outlined"}
                  onClick={() => setIncludeBusinessFlows(!includeBusinessFlows)}
                  startIcon={<BusinessCenter />}
                  disabled={!isReady}
                >
                  Business Flows
                </Button>
              </span>
            </Grid>
            <Grid item>
              <span>
                <Button
                  variant={includeDependencies ? "contained" : "outlined"}
                  onClick={() => setIncludeDependencies(!includeDependencies)}
                  startIcon={<AccountTree />}
                  disabled={!isReady}
                >
                  Dependencies
                </Button>
              </span>
            </Grid>
            <Grid item>
              <span>
                <Button
                  variant={includeMigrationImpact ? "contained" : "outlined"}
                  onClick={() => setIncludeMigrationImpact(!includeMigrationImpact)}
                  startIcon={<Assessment />}
                  disabled={!isReady}
                >
                  Migration Impact
                </Button>
              </span>
            </Grid>
            <Grid item>
              <span>
                <Button
                  variant="contained"
                  color="primary"
                  onClick={handleAnalyze}
                  disabled={!isReady || loading || selectedRepositories.length === 0}
                  startIcon={loading ? <CircularProgress size={20} /> : <PlayArrow />}
                >
                  {loading ? 'Analyzing...' : 'Analyze Repositories'}
                </Button>
              </span>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {/* Analysis Results */}
      {analysisResults && (
        <Box>
          {renderAnalysisSummary()}

          <Paper sx={{ mb: 3 }}>
            <Tabs
              value={activeTab}
              onChange={(e, newValue) => setActiveTab(newValue)}
              indicatorColor="primary"
              textColor="primary"
            >
              <Tab label="Business Flows" icon={<BusinessCenter />} />
              <Tab label="Dependencies" icon={<AccountTree />} />
              <Tab label="Migration Impact" icon={<Assessment />} />
              <Tab label="Integration Points" icon={<Hub />} />
            </Tabs>
            <Box sx={{ p: 3 }}>
              {activeTab === 0 && renderBusinessFlows()}
              {activeTab === 1 && renderDependencies()}
              {activeTab === 2 && renderMigrationImpact()}
              {activeTab === 3 && renderIntegrationPoints()}
            </Box>
          </Paper>
        </Box>
      )}
    </Box>
  );
}

export default MultiRepoAnalysis;