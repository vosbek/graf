import React, { useState, useEffect } from 'react';
import {
  Box, Chip, Tooltip, CircularProgress, IconButton, Typography,
  Card, CardContent, Grid, LinearProgress, Alert
} from '@mui/material';
import {
  CheckCircle, Error, Warning, Info, Refresh, Storage,
  AccountTree, Code, Psychology, Speed
} from '@mui/icons-material';

const ServiceHealthIndicator = ({
  serviceName,
  status,
  error,
  metrics = {},
  showDetails = false
}) => {
  const getStatusIcon = (status) => {
    switch (status) {
      case 'healthy':
      case 'ready':
        return <CheckCircle color="success" />;
      case 'unhealthy':
      case 'not_ready':
      case 'error':
        return <Error color="error" />;
      case 'degraded':
      case 'warning':
        return <Warning color="warning" />;
      case 'timeout':
        return <Warning color="warning" />;
      case 'disabled':
        return <Info color="disabled" />;
      case 'not_available':
        return <Info color="info" />;
      default:
        return <CircularProgress size={20} />;
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'healthy':
      case 'ready':
        return 'success';
      case 'unhealthy':
      case 'not_ready':
      case 'error':
        return 'error';
      case 'degraded':
      case 'warning':
      case 'timeout':
        return 'warning';
      case 'disabled':
        return 'default';
      case 'not_available':
        return 'info';
      default:
        return 'default';
    }
  };

  const getServiceIcon = (serviceName) => {
    switch (serviceName?.toLowerCase()) {
      case 'chromadb':
      case 'chroma':
        return <Storage />;
      case 'neo4j':
        return <AccountTree />;
      case 'embedding_system':
      case 'codebert':
        return <Psychology />;
      case 'processor':
      case 'repository_processor':
        return <Code />;
      case 'api':
        return <Speed />;
      default:
        return <Storage />;
    }
  };

  const formatServiceName = (name) => {
    return name
      .replace(/_/g, ' ')
      .replace(/([A-Z])/g, ' $1')
      .replace(/^./, str => str.toUpperCase())
      .trim();
  };

  const getTooltipContent = () => {
    let content = `${formatServiceName(serviceName)}: ${status}`;
    if (error) {
      content += `\nError: ${error}`;
    }
    if (metrics.response_time) {
      content += `\nResponse Time: ${metrics.response_time.toFixed(2)}ms`;
    }
    if (metrics.last_check) {
      const lastCheck = new Date(metrics.last_check * 1000);
      content += `\nLast Check: ${lastCheck.toLocaleTimeString()}`;
    }
    return content;
  };

  if (showDetails) {
    return (
      <Card sx={{ height: '100%' }}>
        <CardContent>
          <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
            <Box display="flex" alignItems="center">
              {getServiceIcon(serviceName)}
              <Typography variant="h6" sx={{ ml: 1 }}>
                {formatServiceName(serviceName)}
              </Typography>
            </Box>
          </Box>

          <Box display="flex" alignItems="center" mb={2}>
            {getStatusIcon(status)}
            <Chip
              label={status?.toUpperCase() || 'UNKNOWN'}
              color={getStatusColor(status)}
              size="small"
              sx={{ ml: 1 }}
            />
          </Box>

          {error && (
            <Alert severity="error" size="small" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}

          {metrics && Object.keys(metrics).length > 0 && (
            <Box>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                Metrics
              </Typography>
              
              {metrics.response_time && (
                <Box mb={1}>
                  <Box display="flex" justifyContent="space-between" mb={0.5}>
                    <Typography variant="body2">Response Time</Typography>
                    <Typography variant="body2">
                      {metrics.response_time.toFixed(2)}ms
                    </Typography>
                  </Box>
                  <LinearProgress
                    variant="determinate"
                    value={Math.min((metrics.response_time / 1000) * 100, 100)}
                    color={metrics.response_time > 500 ? 'error' : metrics.response_time > 200 ? 'warning' : 'success'}
                    sx={{ height: 4, borderRadius: 2 }}
                  />
                </Box>
              )}

              {metrics.uptime && (
                <Box mb={1}>
                  <Typography variant="body2">
                    Uptime: {Math.round(metrics.uptime / 3600)}h
                  </Typography>
                </Box>
              )}

              {metrics.last_check && (
                <Box mb={1}>
                  <Typography variant="body2" color="text.secondary">
                    Last Check: {new Date(metrics.last_check * 1000).toLocaleTimeString()}
                  </Typography>
                </Box>
              )}

              {/* Service-specific metrics */}
              {serviceName === 'chromadb' && metrics.total_chunks && (
                <Box mb={1}>
                  <Typography variant="body2">
                    Total Chunks: {metrics.total_chunks.toLocaleString()}
                  </Typography>
                </Box>
              )}

              {serviceName === 'neo4j' && (
                <Box>
                  {metrics.total_nodes && (
                    <Typography variant="body2">
                      Nodes: {metrics.total_nodes.toLocaleString()}
                    </Typography>
                  )}
                  {metrics.total_relationships && (
                    <Typography variant="body2">
                      Relationships: {metrics.total_relationships.toLocaleString()}
                    </Typography>
                  )}
                </Box>
              )}

              {serviceName === 'embedding_system' && (
                <Box>
                  {metrics.model_loaded && (
                    <Typography variant="body2">
                      Model: {metrics.model_loaded ? 'Loaded' : 'Not Loaded'}
                    </Typography>
                  )}
                  {metrics.embedding_dimension && (
                    <Typography variant="body2">
                      Dimensions: {metrics.embedding_dimension}
                    </Typography>
                  )}
                </Box>
              )}
            </Box>
          )}
        </CardContent>
      </Card>
    );
  }

  // Compact view
  return (
    <Tooltip title={getTooltipContent()} arrow>
      <Chip
        icon={getStatusIcon(status)}
        label={formatServiceName(serviceName)}
        color={getStatusColor(status)}
        size="small"
        variant="outlined"
        sx={{
          '& .MuiChip-icon': {
            fontSize: '16px'
          }
        }}
      />
    </Tooltip>
  );
};

export default ServiceHealthIndicator;