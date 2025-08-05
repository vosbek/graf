import React, { useState, useEffect } from 'react';
import {
  Box, Typography, Grid, Paper, Card, CardContent, Chip,
  LinearProgress, Button, Alert, List, ListItem, ListItemText,
  ListItemIcon, Divider, IconButton, Tooltip
} from '@mui/material';
import {
  Storage, Code, AccountTree, Timeline, Refresh,
  CheckCircle, FolderOpen, Search, Chat, Business,
  BugReport, Assessment
} from '@mui/icons-material';
import { ApiService } from '../services/ApiService';
import SystemDiagnostics from './SystemDiagnostics';
import SystemHealthOverview from './SystemHealthOverview';
import { useSystemHealth } from '../context/SystemHealthContext';

function Dashboard({ repositories }) {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [diagnosticsOpen, setDiagnosticsOpen] = useState(false);
  const [systemDiagnostics, setSystemDiagnostics] = useState(null);
  const { isReady, isLoading: healthLoading, isInitialLoad, error: healthError, refresh } = useSystemHealth();

  // Gate dashboard data by readiness to avoid premature calls
  useEffect(() => {
    if (!isReady) return;
    loadDashboardData();
  }, [repositories, isReady]);

  const loadDashboardData = async () => {
    try {
      setLoading(true);
      const [statusData, diagnosticsData] = await Promise.all([
        ApiService.getSystemStatus(),
        ApiService.getSystemDiagnostics(false, 10).catch(() => null)
      ]);

      setStats(statusData);

      const normalized = diagnosticsData && typeof diagnosticsData === 'object'
        ? {
            health_score: typeof diagnosticsData.health_score === 'number'
              ? diagnosticsData.health_score
              : (typeof statusData?.health_score === 'number' ? statusData.health_score : 0),
            overall_health:
              (diagnosticsData.overall_health
                || (statusData?.status === 'ready' ? 'healthy' : 'unhealthy')
                || 'unknown'),
            issues: Array.isArray(diagnosticsData.issues) ? diagnosticsData.issues : []
          }
        : {
            health_score: typeof statusData?.health_score === 'number' ? statusData.health_score : 0,
            overall_health: (statusData?.status === 'ready' ? 'healthy' : 'unhealthy'),
            issues: []
          };
      setSystemDiagnostics(normalized);
    } catch (error) {
      console.error('Failed to load dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = () => {
    // Centralized health refresh via context; safe optional chaining if not present
    try { refresh?.(); } catch (_) {}
    if (isReady) {
      loadDashboardData();
    }
  };

  const readinessBanner = (!isReady || isInitialLoad || healthError) ? (
    <Alert severity={healthError ? 'error' : 'info'} sx={{ mb: 3 }}>
      {!isReady ? 'System is starting up. Dashboard metrics will appear once the system is ready.' :
       isInitialLoad ? 'Checking system readiness...' :
       `Health error: ${healthError}`}
    </Alert>
  ) : null;

  const renderSystemStatusCard = () => (
    <Card>
      <CardContent>
        <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
          <Typography variant="h6" display="flex" alignItems="center">
            <Storage sx={{ mr: 1 }} />
            System Status
          </Typography>
          <Tooltip title="Refresh">
            <span>
              <IconButton onClick={handleRefresh} size="small" disabled={!isReady || loading}>
                <Refresh />
              </IconButton>
            </span>
          </Tooltip>
        </Box>
        
        {loading && <LinearProgress sx={{ mb: 2 }} />}
        
        <Grid container spacing={2}>
          <Grid item xs={6}>
            <Box textAlign="center">
              <Typography variant="h4" color="primary.main">
                {repositories.length}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Indexed Repositories
              </Typography>
            </Box>
          </Grid>
          <Grid item xs={6}>
            <Box textAlign="center">
              <Typography variant="h4" color="success.main">
                {stats?.chromadb?.total_chunks || 0}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Code Chunks
              </Typography>
            </Box>
          </Grid>
        </Grid>

        <Divider sx={{ my: 2 }} />

        <SystemHealthOverview compact />

        {systemDiagnostics && (
          <Box mb={2} mt={2}>
            <Box display="flex" alignItems="center" justifyContent="space-between" mb={1}>
              <Typography variant="body2" color="text.secondary">
                System Health Score
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {Math.round(systemDiagnostics.health_score)}/100
              </Typography>
            </Box>
            <LinearProgress
              variant="determinate"
              value={systemDiagnostics.health_score}
              color={systemDiagnostics.health_score >= 80 ? 'success' : systemDiagnostics.health_score >= 60 ? 'warning' : 'error'}
              sx={{ height: 6, borderRadius: 3, mb: 1 }}
            />
            <Box display="flex" alignItems="center" justifyContent="space-between">
              <Chip
                label={(systemDiagnostics?.overall_health || 'unknown').toString().toUpperCase()}
                color={systemDiagnostics.health_score >= 80 ? 'success' : systemDiagnostics.health_score >= 60 ? 'warning' : 'error'}
                size="small"
              />
              <Button
                size="small"
                startIcon={<BugReport />}
                onClick={() => setDiagnosticsOpen(true)}
              >
                Diagnostics
              </Button>
            </Box>
          </Box>
        )}

        {systemDiagnostics?.issues && systemDiagnostics.issues.length > 0 && (
          <Alert
            severity={systemDiagnostics.issues.some(i => i.level === 'critical') ? 'error' : 'warning'}
            size="small"
            sx={{ mb: 1 }}
          >
            {systemDiagnostics.issues.length} system issue{systemDiagnostics.issues.length > 1 ? 's' : ''} detected
          </Alert>
        )}
      </CardContent>
    </Card>
  );

  const renderRepositoryListCard = () => (
    <Card>
      <CardContent>
        <Typography variant="h6" display="flex" alignItems="center" mb={2}>
          <FolderOpen sx={{ mr: 1 }} />
          Indexed Repositories
        </Typography>
        
        {repositories.length === 0 ? (
          <Alert severity="info">
            No repositories indexed yet. Use the "Index Repositories" section to get started.
          </Alert>
        ) : (
          <List dense>
            {repositories.slice(0, 5).map((repo, index) => (
              <ListItem key={index} divider>
                <ListItemIcon>
                  <Code />
                </ListItemIcon>
                <ListItemText
                  primary={<Typography component="span">{repo.name || repo}</Typography>}
                  secondary={
                    <Typography component="span" variant="body2" color="text.secondary">
                      {repo.status ? `Status: ${repo.status} | Files: ${repo.indexed_files || 0}` : `Repository ${index + 1}`}
                    </Typography>
                  }
                />
              </ListItem>
            ))}
            {repositories.length > 5 && (
              <ListItem>
                <ListItemText
                  primary={<Typography component="span">{`... and ${repositories.length - 5} more repositories`}</Typography>}
                  sx={{ fontStyle: 'italic', color: 'text.secondary' }}
                />
              </ListItem>
            )}
          </List>
        )}
      </CardContent>
    </Card>
  );

  const renderQuickActionsCard = () => (
    <Card>
      <CardContent>
        <Typography variant="h6" mb={2}>
          Quick Actions
        </Typography>
        
        <Box display="flex" flexDirection="column" gap={2}>
          <Button
            variant="outlined"
            startIcon={<FolderOpen />}
            href="/index"
            fullWidth
          >
            Index New Repository
          </Button>
          
          <Button
            variant="outlined"
            startIcon={<Search />}
            href="/search"
            fullWidth
            disabled={!isReady || repositories.length === 0}
          >
            Search Code
          </Button>
          
          <Button
            variant="outlined"
            startIcon={<Chat />}
            href="/chat"
            fullWidth
            disabled={!isReady || repositories.length === 0}
          >
            Ask AI Agent
          </Button>
          
          <Button
            variant="outlined"
            startIcon={<AccountTree />}
            href="/graph"
            fullWidth
            disabled={!isReady || repositories.length === 0}
          >
            View Dependencies
          </Button>

          <Button
            variant="outlined"
            startIcon={<Business />}
            href="/multi-repo"
            fullWidth
            disabled={!isReady || repositories.length < 2}
          >
            Multi-Repo Analysis
          </Button>
          
          <Button
            variant="outlined"
            startIcon={<Assessment />}
            onClick={() => setDiagnosticsOpen(true)}
            fullWidth
          >
            System Diagnostics
          </Button>
        </Box>
      </CardContent>
    </Card>
  );

  const renderStatsCard = () => (
    <Card>
      <CardContent>
        <Typography variant="h6" display="flex" alignItems="center" mb={2}>
          <Timeline sx={{ mr: 1 }} />
          Analytics Overview
        </Typography>
        
        {isReady && stats ? (
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6}>
              <Box textAlign="center" py={2}>
                <Typography variant="h3" color="primary.main">
                  {stats.neo4j?.total_files || 0}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Total Files
                </Typography>
              </Box>
            </Grid>
            
            <Grid item xs={12} sm={6}>
              <Box textAlign="center" py={2}>
                <Typography variant="h3" color="secondary.main">
                  {stats.neo4j?.total_dependencies || 0}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Dependencies
                </Typography>
              </Box>
            </Grid>
          </Grid>
        ) : (
          <Alert severity="info">
            {isReady ? 'Analytics available after indexing repositories' : 'Waiting for system readiness...'}
          </Alert>
        )}
      </CardContent>
    </Card>
  );

  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom>
        Dashboard
      </Typography>
      <Typography variant="body1" color="text.secondary" paragraph>
        Welcome to Codebase RAG - your AI-powered legacy application analysis platform.
      </Typography>

      {readinessBanner}

      <Grid container spacing={3}>
        {/* System Status */}
        <Grid item xs={12} md={6}>
          {renderSystemStatusCard()}
        </Grid>

        {/* Repository List */}
        <Grid item xs={12} md={6}>
          {renderRepositoryListCard()}
        </Grid>

        {/* Quick Actions */}
        <Grid item xs={12} md={4}>
          {renderQuickActionsCard()}
        </Grid>

        {/* Analytics Overview */}
        <Grid item xs={12} md={8}>
          {renderStatsCard()}
        </Grid>
      </Grid>

      {/* Getting Started Section */}
      {repositories.length === 0 && (
        <Paper sx={{ p: 3, mt: 3, bgcolor: 'primary.light', color: 'white' }}>
          <Typography variant="h5" gutterBottom>
            🚀 Getting Started
          </Typography>
          <Typography variant="body1" paragraph>
            Transform your Struts application into an intelligently searchable knowledge base in 3 simple steps:
          </Typography>
          <Box component="ol" sx={{ pl: 3 }}>
            <li><strong>Index Your Repositories:</strong> Point to your local Struts application directories</li>
            <li><strong>Explore with AI:</strong> Ask questions in plain English about your codebase</li>
            <li><strong>Plan Migration:</strong> Get GraphQL migration recommendations and roadmaps</li>
          </Box>
          <Button
            variant="contained"
            sx={{ mt: 2, bgcolor: 'white', color: 'primary.main' }}
            href="/index"
          >
            Start Indexing Repositories
          </Button>
        </Paper>
      )}

      {/* System Diagnostics Dialog */}
      <SystemDiagnostics
        open={diagnosticsOpen}
        onClose={() => setDiagnosticsOpen(false)}
      />
    </Box>
  );
}

export default Dashboard;