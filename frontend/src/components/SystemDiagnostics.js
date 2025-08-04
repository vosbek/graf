import React, { useState, useEffect } from 'react';
import {
  Box, Typography, Grid, Paper, Card, CardContent, Chip, Alert,
  LinearProgress, Button, List, ListItem, ListItemText, ListItemIcon,
  Accordion, AccordionSummary, AccordionDetails, IconButton, Tooltip,
  Dialog, DialogTitle, DialogContent, DialogActions, Divider,
  CircularProgress, Table, TableBody, TableCell, TableContainer,
  TableHead, TableRow, Tabs, Tab
} from '@mui/material';
import {
  ExpandMore, Refresh, Download, Warning, Error, Info, CheckCircle,
  Computer, Storage, Speed, Settings, BugReport, Healing, Timeline,
  Assessment, Build, Close
} from '@mui/icons-material';
import { ApiService } from '../services/ApiService';

function SystemDiagnostics({ open, onClose }) {
  const [loading, setLoading] = useState(false);
  const [diagnostics, setDiagnostics] = useState(null);
  const [issues, setIssues] = useState([]);
  const [recommendations, setRecommendations] = useState(null);
  const [performanceHistory, setPerformanceHistory] = useState([]);
  const [selectedTab, setSelectedTab] = useState(0);
  const [selectedIssue, setSelectedIssue] = useState(null);
  const [troubleshootingGuide, setTroubleshootingGuide] = useState(null);
  const [autoFixes, setAutoFixes] = useState([]);

  useEffect(() => {
    if (open) {
      loadDiagnosticData();
    }
  }, [open]);

  const loadDiagnosticData = async () => {
    try {
      setLoading(true);
      
      const [diagnosticsData, issuesData, recommendationsData, historyData, autoFixData] = await Promise.all([
        ApiService.getSystemDiagnostics(true),
        ApiService.getCurrentIssues(),
        ApiService.getSystemRecommendations(),
        ApiService.getPerformanceHistory(),
        ApiService.getAutoFixSuggestions()
      ]);
      
      setDiagnostics(diagnosticsData);
      setIssues(issuesData.issues || []);
      setRecommendations(recommendationsData);
      setPerformanceHistory(historyData.history || []);
      setAutoFixes(autoFixData.auto_fixes || []);
      
    } catch (error) {
      console.error('Failed to load diagnostic data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = () => {
    loadDiagnosticData();
  };

  const handleExportDiagnostics = async (format = 'json') => {
    try {
      await ApiService.exportDiagnosticData(format);
    } catch (error) {
      console.error('Failed to export diagnostics:', error);
    }
  };

  const handleIssueClick = async (issue) => {
    try {
      setSelectedIssue(issue);
      const guide = await ApiService.getTroubleshootingGuide(issue.id);
      setTroubleshootingGuide(guide);
    } catch (error) {
      console.error('Failed to load troubleshooting guide:', error);
    }
  };

  const getHealthScoreColor = (score) => {
    if (score >= 80) return 'success';
    if (score >= 60) return 'warning';
    return 'error';
  };

  const getIssueIcon = (level) => {
    switch (level) {
      case 'critical': return <Error color="error" />;
      case 'error': return <Warning color="error" />;
      case 'warning': return <Warning color="warning" />;
      case 'info': return <Info color="info" />;
      default: return <Info />;
    }
  };

  const getIssueColor = (level) => {
    switch (level) {
      case 'critical': return 'error';
      case 'error': return 'error';
      case 'warning': return 'warning';
      case 'info': return 'info';
      default: return 'default';
    }
  };

  const renderOverviewTab = () => (
    <Box>
      {/* Health Score Card */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
            <Typography variant="h6" display="flex" alignItems="center">
              <Assessment sx={{ mr: 1 }} />
              System Health Score
            </Typography>
            <Tooltip title="Refresh">
              <IconButton onClick={handleRefresh} disabled={loading}>
                <Refresh />
              </IconButton>
            </Tooltip>
          </Box>
          
          {loading ? (
            <CircularProgress />
          ) : diagnostics ? (
            <Box>
              <Box display="flex" alignItems="center" mb={2}>
                <Box sx={{ minWidth: 35 }}>
                  <Typography variant="body2" color="text.secondary">
                    {Math.round(diagnostics.health_score)}/100
                  </Typography>
                </Box>
                <Box sx={{ width: '100%', mr: 1 }}>
                  <LinearProgress
                    variant="determinate"
                    value={diagnostics.health_score}
                    color={getHealthScoreColor(diagnostics.health_score)}
                    sx={{ height: 10, borderRadius: 5 }}
                  />
                </Box>
              </Box>
              
              <Chip
                label={diagnostics.overall_health.toUpperCase()}
                color={getHealthScoreColor(diagnostics.health_score)}
                size="small"
              />
              
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                Last checked: {new Date(diagnostics.timestamp).toLocaleString()}
              </Typography>
            </Box>
          ) : (
            <Alert severity="error">Failed to load diagnostics</Alert>
          )}
        </CardContent>
      </Card>

      {/* Component Status */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" display="flex" alignItems="center" mb={2}>
            <Computer sx={{ mr: 1 }} />
            Component Status
          </Typography>
          
          {diagnostics?.component_status && (
            <Grid container spacing={2}>
              {Object.entries(diagnostics.component_status).map(([name, status]) => (
                <Grid item xs={12} sm={6} md={4} key={name}>
                  <Paper sx={{ p: 2, textAlign: 'center' }}>
                    <Box display="flex" alignItems="center" justifyContent="center" mb={1}>
                      {status.healthy ? (
                        <CheckCircle color="success" />
                      ) : (
                        <Error color="error" />
                      )}
                      <Typography variant="subtitle2" sx={{ ml: 1 }}>
                        {name.replace('_', ' ').toUpperCase()}
                      </Typography>
                    </Box>
                    <Chip
                      label={status.healthy ? 'Healthy' : 'Unhealthy'}
                      color={status.healthy ? 'success' : 'error'}
                      size="small"
                    />
                  </Paper>
                </Grid>
              ))}
            </Grid>
          )}
        </CardContent>
      </Card>

      {/* Performance Metrics */}
      <Card>
        <CardContent>
          <Typography variant="h6" display="flex" alignItems="center" mb={2}>
            <Speed sx={{ mr: 1 }} />
            Performance Metrics
          </Typography>
          
          {diagnostics?.performance_metrics && (
            <Grid container spacing={2}>
              <Grid item xs={12} sm={4}>
                <Box textAlign="center">
                  <Typography variant="h4" color="primary">
                    {Math.round(diagnostics.performance_metrics.cpu_percent)}%
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    CPU Usage
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={12} sm={4}>
                <Box textAlign="center">
                  <Typography variant="h4" color="secondary">
                    {Math.round(diagnostics.performance_metrics.memory_percent)}%
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Memory Usage
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={12} sm={4}>
                <Box textAlign="center">
                  <Typography variant="h4" color="info.main">
                    {Math.round(diagnostics.performance_metrics.disk_percent)}%
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Disk Usage
                  </Typography>
                </Box>
              </Grid>
            </Grid>
          )}
        </CardContent>
      </Card>
    </Box>
  );

  const renderIssuesTab = () => (
    <Box>
      {issues.length === 0 ? (
        <Alert severity="success" sx={{ mb: 2 }}>
          <Typography variant="h6">No Issues Detected</Typography>
          <Typography>Your system is operating normally with no detected issues.</Typography>
        </Alert>
      ) : (
        <Alert severity="warning" sx={{ mb: 2 }}>
          <Typography variant="h6">{issues.length} Issues Detected</Typography>
          <Typography>Click on any issue below for detailed troubleshooting guidance.</Typography>
        </Alert>
      )}

      {issues.map((issue, index) => (
        <Accordion key={index} sx={{ mb: 1 }}>
          <AccordionSummary expandIcon={<ExpandMore />}>
            <Box display="flex" alignItems="center" width="100%">
              {getIssueIcon(issue.level)}
              <Box sx={{ ml: 2, flexGrow: 1 }}>
                <Typography variant="subtitle1">{issue.title}</Typography>
                <Typography variant="body2" color="text.secondary">
                  {issue.component} • {issue.description}
                </Typography>
              </Box>
              <Chip
                label={issue.level.toUpperCase()}
                color={getIssueColor(issue.level)}
                size="small"
              />
            </Box>
          </AccordionSummary>
          <AccordionDetails>
            <Box>
              <Typography variant="body2" paragraph>
                <strong>Component:</strong> {issue.component}
              </Typography>
              <Typography variant="body2" paragraph>
                <strong>Detected:</strong> {new Date(issue.detected_at).toLocaleString()}
              </Typography>
              <Typography variant="body2" paragraph>
                <strong>Description:</strong> {issue.description}
              </Typography>
              
              <Typography variant="subtitle2" sx={{ mt: 2, mb: 1 }}>
                Remediation Steps:
              </Typography>
              <List dense>
                {issue.remediation_steps.map((step, stepIndex) => (
                  <ListItem key={stepIndex}>
                    <ListItemText
                      primary={`${stepIndex + 1}. ${step}`}
                      primaryTypographyProps={{ variant: 'body2' }}
                    />
                  </ListItem>
                ))}
              </List>
              
              <Box sx={{ mt: 2 }}>
                <Button
                  variant="outlined"
                  size="small"
                  onClick={() => handleIssueClick(issue)}
                >
                  View Detailed Guide
                </Button>
                {issue.auto_fixable && (
                  <Chip
                    label="Auto-fixable"
                    color="info"
                    size="small"
                    icon={<Healing />}
                    sx={{ ml: 1 }}
                  />
                )}
              </Box>
            </Box>
          </AccordionDetails>
        </Accordion>
      ))}
    </Box>
  );

  const renderRecommendationsTab = () => (
    <Box>
      {recommendations && (
        <>
          {recommendations.recommendations.critical.length > 0 && (
            <Card sx={{ mb: 2, border: '1px solid', borderColor: 'error.main' }}>
              <CardContent>
                <Typography variant="h6" color="error" display="flex" alignItems="center" mb={2}>
                  <Error sx={{ mr: 1 }} />
                  Critical Recommendations
                </Typography>
                <List>
                  {recommendations.recommendations.critical.map((rec, index) => (
                    <ListItem key={index}>
                      <ListItemIcon>
                        <Error color="error" />
                      </ListItemIcon>
                      <ListItemText primary={rec} />
                    </ListItem>
                  ))}
                </List>
              </CardContent>
            </Card>
          )}

          {recommendations.recommendations.performance.length > 0 && (
            <Card sx={{ mb: 2, border: '1px solid', borderColor: 'warning.main' }}>
              <CardContent>
                <Typography variant="h6" color="warning.main" display="flex" alignItems="center" mb={2}>
                  <Speed sx={{ mr: 1 }} />
                  Performance Recommendations
                </Typography>
                <List>
                  {recommendations.recommendations.performance.map((rec, index) => (
                    <ListItem key={index}>
                      <ListItemIcon>
                        <Speed color="warning" />
                      </ListItemIcon>
                      <ListItemText primary={rec} />
                    </ListItem>
                  ))}
                </List>
              </CardContent>
            </Card>
          )}

          {recommendations.recommendations.maintenance.length > 0 && (
            <Card sx={{ mb: 2 }}>
              <CardContent>
                <Typography variant="h6" color="info.main" display="flex" alignItems="center" mb={2}>
                  <Build sx={{ mr: 1 }} />
                  Maintenance Recommendations
                </Typography>
                <List>
                  {recommendations.recommendations.maintenance.map((rec, index) => (
                    <ListItem key={index}>
                      <ListItemIcon>
                        <Build color="info" />
                      </ListItemIcon>
                      <ListItemText primary={rec} />
                    </ListItem>
                  ))}
                </List>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </Box>
  );

  const renderPerformanceTab = () => (
    <Box>
      <Card>
        <CardContent>
          <Typography variant="h6" display="flex" alignItems="center" mb={2}>
            <Timeline sx={{ mr: 1 }} />
            Performance History
          </Typography>
          
          {performanceHistory.length > 0 ? (
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Timestamp</TableCell>
                    <TableCell align="right">Health Score</TableCell>
                    <TableCell align="right">Issues</TableCell>
                    <TableCell align="right">Critical Issues</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {performanceHistory.slice(-10).map((entry, index) => (
                    <TableRow key={index}>
                      <TableCell>
                        {new Date(entry.timestamp).toLocaleString()}
                      </TableCell>
                      <TableCell align="right">
                        <Chip
                          label={Math.round(entry.health_score)}
                          color={getHealthScoreColor(entry.health_score)}
                          size="small"
                        />
                      </TableCell>
                      <TableCell align="right">{entry.issue_count}</TableCell>
                      <TableCell align="right">
                        {entry.critical_issues > 0 ? (
                          <Chip
                            label={entry.critical_issues}
                            color="error"
                            size="small"
                          />
                        ) : (
                          '0'
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          ) : (
            <Alert severity="info">
              No performance history available yet. Data will appear after running diagnostics multiple times.
            </Alert>
          )}
        </CardContent>
      </Card>
    </Box>
  );

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="lg"
      fullWidth
      PaperProps={{
        sx: { height: '90vh' }
      }}
    >
      <DialogTitle>
        <Box display="flex" alignItems="center" justifyContent="space-between">
          <Box display="flex" alignItems="center">
            <BugReport sx={{ mr: 1 }} />
            System Diagnostics
          </Box>
          <Box>
            <Tooltip title="Export JSON">
              <IconButton onClick={() => handleExportDiagnostics('json')}>
                <Download />
              </IconButton>
            </Tooltip>
            <Tooltip title="Export Text">
              <IconButton onClick={() => handleExportDiagnostics('text')}>
                <Download />
              </IconButton>
            </Tooltip>
            <IconButton onClick={onClose}>
              <Close />
            </IconButton>
          </Box>
        </Box>
      </DialogTitle>
      
      <DialogContent>
        <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
          <Tabs value={selectedTab} onChange={(e, newValue) => setSelectedTab(newValue)}>
            <Tab label="Overview" />
            <Tab label={`Issues (${issues.length})`} />
            <Tab label="Recommendations" />
            <Tab label="Performance" />
          </Tabs>
        </Box>

        {selectedTab === 0 && renderOverviewTab()}
        {selectedTab === 1 && renderIssuesTab()}
        {selectedTab === 2 && renderRecommendationsTab()}
        {selectedTab === 3 && renderPerformanceTab()}
      </DialogContent>

      <DialogActions>
        <Button onClick={handleRefresh} disabled={loading} startIcon={<Refresh />}>
          Refresh
        </Button>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>

      {/* Troubleshooting Guide Dialog */}
      <Dialog
        open={Boolean(selectedIssue)}
        onClose={() => {
          setSelectedIssue(null);
          setTroubleshootingGuide(null);
        }}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          Troubleshooting Guide: {selectedIssue?.title}
        </DialogTitle>
        <DialogContent>
          {troubleshootingGuide ? (
            <Box>
              <Typography variant="body1" paragraph>
                <strong>Description:</strong> {troubleshootingGuide.description}
              </Typography>
              
              <Typography variant="body1" paragraph>
                <strong>Component Type:</strong> {troubleshootingGuide.component_type}
              </Typography>
              
              <Typography variant="h6" sx={{ mt: 2, mb: 1 }}>
                Step-by-Step Resolution:
              </Typography>
              <List>
                {troubleshootingGuide.remediation_steps.map((step, index) => (
                  <ListItem key={index}>
                    <ListItemText
                      primary={`${index + 1}. ${step}`}
                      primaryTypographyProps={{ variant: 'body1' }}
                    />
                  </ListItem>
                ))}
              </List>
              
              {troubleshootingGuide.additional_resources && (
                <>
                  <Typography variant="h6" sx={{ mt: 2, mb: 1 }}>
                    Additional Resources:
                  </Typography>
                  <List>
                    {troubleshootingGuide.additional_resources.map((resource, index) => (
                      <ListItem key={index}>
                        <ListItemText primary={resource} />
                      </ListItem>
                    ))}
                  </List>
                </>
              )}
            </Box>
          ) : (
            <CircularProgress />
          )}
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => {
              setSelectedIssue(null);
              setTroubleshootingGuide(null);
            }}
          >
            Close
          </Button>
        </DialogActions>
      </Dialog>
    </Dialog>
  );
}

export default SystemDiagnostics;