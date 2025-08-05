import React, { useState } from 'react';
import {
  Box, Typography, Grid, Card, CardContent, Alert,
  LinearProgress, Chip, IconButton, Tooltip, CircularProgress,
  Button, Dialog, DialogTitle, DialogContent, DialogActions,
  FormControlLabel, Checkbox, Snackbar
} from '@mui/material';
import {
  Refresh, CheckCircle, Error, Warning, Assessment,
  DeleteSweep, Backup
} from '@mui/icons-material';
import ServiceHealthIndicator from './ServiceHealthIndicator';
import { useSystemHealth } from '../context/SystemHealthContext';

const SystemHealthOverview = ({
  compact = false
}) => {
  // Rely solely on context; remove external callbacks/side-effects and internal timers
  const { data: healthData, error, isLoading, lastUpdated, refresh } = useSystemHealth();

  // Database reset state
  const [resetDialogOpen, setResetDialogOpen] = useState(false);
  const [resetOptions, setResetOptions] = useState({
    reset_neo4j: true,
    reset_chromadb: true,
    create_backup: false,
    confirm: false
  });
  const [resetLoading, setResetLoading] = useState(false);
  const [resetSnackbar, setResetSnackbar] = useState({ open: false, message: '', severity: 'info' });

  // Normalize backend payload to avoid false "unhealthy" when top-level is ready
  const normalizedChecks = React.useMemo(() => {
    const checks = healthData?.checks && typeof healthData.checks === 'object' ? healthData.checks : {};
    // If top-level says ready, coerce missing/unknown checks to ready=true
    if (healthData?.status === 'ready') {
      const coerced = {};
      Object.keys(checks).forEach((k) => {
        const c = checks[k] || {};
        coerced[k] = { ...c, ready: true, error: undefined };
      });
      return coerced;
    }
    // Otherwise, pass through as-is but sanitize shapes
    const sanitized = {};
    Object.keys(checks).forEach((k) => {
      const c = checks[k] || {};
      sanitized[k] = { ready: !!c.ready, error: c.error, ...c };
    });
    return sanitized;
  }, [healthData]);

  const getOverallHealthStatus = () => {
    // Treat "ok" or "ready" (string or boolean) as healthy
    const top = (healthData?.status || '').toString().toLowerCase();
    if (top === 'ready' || top === 'ok' || top === 'healthy' || healthData?.ready === true) {
      return 'healthy';
    }
    const checks = normalizedChecks || {};
    const values = Object.values(checks).map(c => !!c.ready);
    if (values.length === 0) return healthData ? 'unknown' : 'unknown';
    if (values.every(Boolean)) return 'healthy';
    if (values.some(Boolean)) return 'degraded';
    return 'unhealthy';
  };

  const getOverallHealthScore = () => {
    if (healthData?.status === 'ready') return 100;
    const score = Number(healthData?.health_score);
    if (Number.isFinite(score) && score >= 0) return score;
    // Derive a basic score from checks if provided
    const checks = normalizedChecks || {};
    const total = Object.keys(checks).length;
    if (total > 0) {
      const readyCount = Object.values(checks).filter(c => !!c.ready).length;
      return Math.round((readyCount / total) * 100);
    }
    return 0;
  };

  const getSystemReadiness = () => {
    const top = (healthData?.status || '').toString().toLowerCase();
    return top === 'ready' || top === 'ok' || top === 'healthy' || healthData?.ready === true;
  };

  const getCriticalIssues = () => {
    // If system is ready, suppress critical issues display
    if (healthData?.status === 'ready') return [];
    const checks = normalizedChecks || {};
    return Object.entries(checks)
      .filter(([_, check]) => !check.ready)
      .map(([name, check]) => ({
        service: name,
        error: check?.error || 'Service not ready'
      }));
  };

  // Database reset functions
  const handleResetDatabases = async () => {
    if (!resetOptions.confirm) {
      setResetSnackbar({
        open: true,
        message: 'Please confirm the operation by checking the confirmation box',
        severity: 'warning'
      });
      return;
    }

    setResetLoading(true);
    try {
      const response = await fetch('/api/v1/admin/database/reset', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(resetOptions),
      });

      const result = await response.json();

      if (response.ok && result.success) {
        setResetSnackbar({
          open: true,
          message: `Database reset successful! ${result.message}`,
          severity: 'success'
        });
        setResetDialogOpen(false);
        // Refresh system health after reset
        setTimeout(() => refresh(), 2000);
      } else {
        throw new Error(result.detail || result.message || 'Database reset failed');
      }
    } catch (error) {
      setResetSnackbar({
        open: true,
        message: `Database reset failed: ${error.message}`,
        severity: 'error'
      });
    } finally {
      setResetLoading(false);
    }
  };

  const handleResetOptionChange = (option) => (event) => {
    setResetOptions(prev => ({
      ...prev,
      [option]: event.target.checked
    }));
  };

  if (compact) {
    return (
      <Box display="flex" alignItems="center" gap={1}>
        {isLoading && <CircularProgress size={16} />}
        <Tooltip title={`System Health: ${getOverallHealthStatus()}`} arrow>
          <Chip
            icon={getOverallHealthStatus() === 'healthy' ? <CheckCircle /> :
                  getOverallHealthStatus() === 'degraded' ? <Warning /> : <Error />}
            label={getSystemReadiness() ? 'System Ready' : 'System Issues'}
            color={getOverallHealthStatus() === 'healthy' ? 'success' :
                   getOverallHealthStatus() === 'degraded' ? 'warning' : 'error'}
            size="small"
            variant="outlined"
          />
        </Tooltip>
        {healthData && healthData.checks && (
          <Box display="flex" gap={0.5}>
            {Object.entries(healthData.checks).map(([serviceName, check]) => (
              <ServiceHealthIndicator
                key={serviceName}
                serviceName={serviceName}
                status={check.ready ? 'healthy' : 'unhealthy'}
                error={check.error}
                metrics={check}
                showDetails={false}
              />
            ))}
          </Box>
        )}
        <IconButton onClick={refresh} size="small" disabled={isLoading}>
          <Refresh />
        </IconButton>
      </Box>
    );
  }

  return (
    <Box>
      <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
        <Typography variant="h6" display="flex" alignItems="center">
          <Assessment sx={{ mr: 1 }} />
          System Health Overview
        </Typography>
        <Box display="flex" alignItems="center" gap={1}>
          {lastUpdated && (
            <Typography variant="caption" color="text.secondary">
              Updated: {lastUpdated.toLocaleTimeString()}
            </Typography>
          )}
          <IconButton onClick={refresh} size="small" disabled={isLoading}>
            <Refresh />
          </IconButton>
        </Box>
      </Box>

      {isLoading && <LinearProgress sx={{ mb: 2 }} />}

      {/* Only show fetch error if not ready; when ready, avoid overriding healthy UI */}
      {error && !getSystemReadiness() && (
        <Alert severity="error" sx={{ mb: 2 }}>
          Failed to load system health: {error}
        </Alert>
      )}

      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Grid container spacing={3}>
            <Grid item xs={12} md={4}>
              <Box textAlign="center">
                <Box display="flex" alignItems="center" justifyContent="center" mb={1}>
                  {getOverallHealthStatus() === 'healthy' ? (
                    <CheckCircle color="success" sx={{ fontSize: 40 }} />
                  ) : getOverallHealthStatus() === 'degraded' ? (
                    <Warning color="warning" sx={{ fontSize: 40 }} />
                  ) : (
                    <Error color="error" sx={{ fontSize: 40 }} />
                  )}
                </Box>
                <Typography variant="h6">
                  {getSystemReadiness() ? 'System Ready' : 'System Issues'}
                </Typography>
                <Chip
                  label={getOverallHealthStatus().toUpperCase()}
                  color={getOverallHealthStatus() === 'healthy' ? 'success' :
                         getOverallHealthStatus() === 'degraded' ? 'warning' : 'error'}
                  size="small"
                />
              </Box>
            </Grid>

            <Grid item xs={12} md={4}>
              <Box textAlign="center">
                <Typography variant="h4" color="primary">
                  {Math.round(getOverallHealthScore())}
                </Typography>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Health Score
                </Typography>
                <LinearProgress
                  variant="determinate"
                  value={getOverallHealthScore()}
                  color={getOverallHealthScore() >= 80 ? 'success' :
                         getOverallHealthScore() >= 60 ? 'warning' : 'error'}
                  sx={{ height: 8, borderRadius: 4 }}
                />
              </Box>
            </Grid>

            <Grid item xs={12} md={4}>
              <Box textAlign="center">
                <Typography variant="h4" color={getCriticalIssues().length > 0 ? 'error.main' : 'success.main'}>
                  {getCriticalIssues().length}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Critical Issues
                </Typography>
                {healthData?.validation_time && (
                  <Typography variant="caption" color="text.secondary" display="block">
                    Validated in {(healthData.validation_time * 1000).toFixed(0)}ms
                  </Typography>
                )}
              </Box>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Suppress issues panel entirely when the system is reported ready/ok */}
      {!getSystemReadiness() && getCriticalIssues().length > 0 && (
        <Alert severity="error" sx={{ mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            {getCriticalIssues().length} Critical Issue{getCriticalIssues().length > 1 ? 's' : ''} Detected
          </Typography>
          <Box component="ul" sx={{ mt: 1, mb: 0 }}>
            {getCriticalIssues().map((issue, index) => (
              <li key={index}>
                <strong>{issue.service}:</strong> {issue.error}
              </li>
            ))}
          </Box>
        </Alert>
      )}

      {(normalizedChecks && Object.keys(normalizedChecks).length > 0) && (
        <Grid container spacing={2}>
          {Object.entries(normalizedChecks).map(([serviceName, check]) => {
            const isReady = getSystemReadiness();
            const status = isReady ? 'healthy' : (check.ready ? 'healthy' : 'unhealthy');
            return (
              <Grid item xs={12} sm={6} md={4} key={serviceName}>
                <ServiceHealthIndicator
                  serviceName={serviceName}
                  status={status}
                  error={isReady ? undefined : check.error}
                  metrics={{
                    response_time: check.response_time,
                    last_check: Date.now() / 1000,
                    ...check
                  }}
                  showDetails={true}
                />
              </Grid>
            );
          })}
        </Grid>
      )}

      {/* Database Reset Section */}
      <Card sx={{ mt: 3 }}>
        <CardContent>
          <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
            <Typography variant="h6" gutterBottom>
              Database Management
            </Typography>
            <Button
              variant="outlined"
              color="error"
              startIcon={<DeleteSweep />}
              onClick={() => setResetDialogOpen(true)}
              disabled={resetLoading}
            >
              Reset Databases
            </Button>
          </Box>
          
          <Alert severity="info" sx={{ mb: 2 }}>
            <Typography variant="body2">
              Use database reset to clear Neo4j and ChromaDB for clean re-indexing with the enhanced business relationship extraction pipeline.
              This is useful for testing the enhanced ingestion or clearing corrupted data.
            </Typography>
          </Alert>

          <Grid container spacing={2}>
            <Grid item xs={12} sm={6}>
              <Typography variant="subtitle2" gutterBottom>
                Neo4j Database
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Graph database containing business relationships, Struts actions, CORBA interfaces, and business rules.
              </Typography>
            </Grid>
            <Grid item xs={12} sm={6}>
              <Typography variant="subtitle2" gutterBottom>
                ChromaDB Vector Store
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Vector database containing code embeddings and enhanced metadata for semantic search.
              </Typography>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Database Reset Dialog */}
      <Dialog open={resetDialogOpen} onClose={() => setResetDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>
          <Box display="flex" alignItems="center" gap={1}>
            <DeleteSweep color="error" />
            Reset Databases
          </Box>
        </DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 3 }}>
            <Typography variant="body2" gutterBottom>
              <strong>⚠️ WARNING: This operation permanently deletes all data!</strong>
            </Typography>
            <Typography variant="body2">
              This will clear all indexed repositories, business relationships, and embeddings. 
              You will need to re-index your repositories after this operation.
            </Typography>
          </Alert>

          <Box sx={{ mb: 2 }}>
            <Typography variant="subtitle1" gutterBottom>
              Reset Options:
            </Typography>
            
            <FormControlLabel
              control={
                <Checkbox
                  checked={resetOptions.reset_neo4j}
                  onChange={handleResetOptionChange('reset_neo4j')}
                />
              }
              label="Reset Neo4j (Business relationships, graph data)"
            />
            
            <FormControlLabel
              control={
                <Checkbox
                  checked={resetOptions.reset_chromadb}
                  onChange={handleResetOptionChange('reset_chromadb')}
                />
              }
              label="Reset ChromaDB (Code embeddings, semantic search)"
            />
            
            <FormControlLabel
              control={
                <Checkbox
                  checked={resetOptions.create_backup}
                  onChange={handleResetOptionChange('create_backup')}
                />
              }
              label={
                <Box display="flex" alignItems="center" gap={1}>
                  <Backup fontSize="small" />
                  Create backup before reset (recommended)
                </Box>
              }
            />
          </Box>

          <Alert severity="error" sx={{ mb: 2 }}>
            <FormControlLabel
              control={
                <Checkbox
                  checked={resetOptions.confirm}
                  onChange={handleResetOptionChange('confirm')}
                  color="error"
                />
              }
              label="I understand this will permanently delete all data and cannot be undone"
            />
          </Alert>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setResetDialogOpen(false)}>
            Cancel
          </Button>
          <Button
            onClick={handleResetDatabases}
            color="error"
            variant="contained"
            disabled={!resetOptions.confirm || resetLoading}
            startIcon={resetLoading ? <CircularProgress size={16} /> : <DeleteSweep />}
          >
            {resetLoading ? 'Resetting...' : 'Reset Databases'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Snackbar for reset notifications */}
      <Snackbar
        open={resetSnackbar.open}
        autoHideDuration={6000}
        onClose={() => setResetSnackbar({ ...resetSnackbar, open: false })}
      >
        <Alert
          onClose={() => setResetSnackbar({ ...resetSnackbar, open: false })}
          severity={resetSnackbar.severity}
          sx={{ width: '100%' }}
        >
          {resetSnackbar.message}
        </Alert>
      </Snackbar>

      {healthData?.troubleshooting && (
        <Card sx={{ mt: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Troubleshooting Information
            </Typography>
            {healthData.troubleshooting.failed_components && (
              <Box mb={2}>
                <Typography variant="subtitle2" color="error" gutterBottom>
                  Failed Components: {healthData.troubleshooting.failed_components.join(', ')}
                </Typography>
              </Box>
            )}
            {healthData.troubleshooting.general_suggestions && (
              <Box mb={2}>
                <Typography variant="subtitle2" gutterBottom>
                  General Suggestions:
                </Typography>
                <Box component="ul" sx={{ mt: 0, pl: 2 }}>
                  {healthData.troubleshooting.general_suggestions.map((suggestion, index) => (
                    <li key={index}>
                      <Typography variant="body2">{suggestion}</Typography>
                    </li>
                  ))}
                </Box>
              </Box>
            )}
            {healthData.troubleshooting.component_specific && (
              <Box>
                <Typography variant="subtitle2" gutterBottom>
                  Component-Specific Issues:
                </Typography>
                {Object.entries(healthData.troubleshooting.component_specific).map(([component, issue]) => (
                  <Alert key={component} severity="warning" size="small" sx={{ mb: 1 }}>
                    <strong>{component}:</strong> {issue}
                  </Alert>
                ))}
              </Box>
            )}
          </CardContent>
        </Card>
      )}
    </Box>
  );
};

export default SystemHealthOverview;