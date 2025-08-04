import React, { useState, useEffect } from 'react';
import {
  Box, Typography, Card, CardContent, Chip, Alert,
  LinearProgress, IconButton, Tooltip, CircularProgress,
  Grid, List, ListItem, ListItemText, ListItemIcon
} from '@mui/material';
import {
  Psychology, Refresh, CheckCircle, Error, Warning,
  Memory, Speed, ModelTraining, DataObject
} from '@mui/icons-material';
import { ApiService } from '../services/ApiService';

const EmbeddingSystemStatus = ({ 
  compact = false, 
  autoRefresh = true, 
  refreshInterval = 60000 
}) => {
  const [loading, setLoading] = useState(false);
  const [embeddingStatus, setEmbeddingStatus] = useState(null);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);

  useEffect(() => {
    loadEmbeddingStatus();
    
    if (autoRefresh) {
      const interval = setInterval(loadEmbeddingStatus, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [autoRefresh, refreshInterval]);

  const loadEmbeddingStatus = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Get health status which includes embedding system info
      const healthResponse = await ApiService.getStatus();
      const embeddingCheck = healthResponse.checks?.embedding_system;
      
      if (embeddingCheck) {
        setEmbeddingStatus(embeddingCheck);
      } else {
        setEmbeddingStatus({
          status: 'not_available',
          message: 'Embedding system information not available'
        });
      }
      
      setLastUpdate(new Date());
      
    } catch (err) {
      console.error('Failed to load embedding status:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'healthy':
        return <CheckCircle color="success" />;
      case 'unhealthy':
      case 'error':
        return <Error color="error" />;
      case 'timeout':
        return <Warning color="warning" />;
      case 'not_available':
        return <Warning color="info" />;
      default:
        return <CircularProgress size={20} />;
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'healthy':
        return 'success';
      case 'unhealthy':
      case 'error':
        return 'error';
      case 'timeout':
        return 'warning';
      case 'not_available':
        return 'info';
      default:
        return 'default';
    }
  };

  if (compact) {
    return (
      <Box display="flex" alignItems="center" gap={1}>
        {loading && <CircularProgress size={16} />}
        
        <Tooltip title={`CodeBERT Status: ${embeddingStatus?.status || 'Unknown'}`}>
          <Chip
            icon={<Psychology />}
            label="CodeBERT"
            color={getStatusColor(embeddingStatus?.status)}
            size="small"
            variant="outlined"
          />
        </Tooltip>
        
        <IconButton onClick={loadEmbeddingStatus} size="small" disabled={loading}>
          <Refresh />
        </IconButton>
      </Box>
    );
  }

  return (
    <Card>
      <CardContent>
        <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
          <Typography variant="h6" display="flex" alignItems="center">
            <Psychology sx={{ mr: 1 }} />
            CodeBERT Embedding System
          </Typography>
          <Box display="flex" alignItems="center" gap={1}>
            {lastUpdate && (
              <Typography variant="caption" color="text.secondary">
                {lastUpdate.toLocaleTimeString()}
              </Typography>
            )}
            <IconButton onClick={loadEmbeddingStatus} size="small" disabled={loading}>
              <Refresh />
            </IconButton>
          </Box>
        </Box>

        {loading && <LinearProgress sx={{ mb: 2 }} />}

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            Failed to load embedding system status: {error}
          </Alert>
        )}

        {embeddingStatus && (
          <Box>
            {/* Status Overview */}
            <Box display="flex" alignItems="center" mb={2}>
              {getStatusIcon(embeddingStatus.status)}
              <Chip
                label={embeddingStatus.status?.toUpperCase() || 'UNKNOWN'}
                color={getStatusColor(embeddingStatus.status)}
                size="small"
                sx={{ ml: 1 }}
              />
            </Box>

            {/* Status Message */}
            {embeddingStatus.message && (
              <Alert 
                severity={embeddingStatus.status === 'healthy' ? 'success' : 
                         embeddingStatus.status === 'not_available' ? 'info' : 'warning'}
                sx={{ mb: 2 }}
              >
                {embeddingStatus.message}
              </Alert>
            )}

            {/* Error Details */}
            {embeddingStatus.error && (
              <Alert severity="error" sx={{ mb: 2 }}>
                <Typography variant="subtitle2" gutterBottom>
                  Error Details:
                </Typography>
                {embeddingStatus.error}
              </Alert>
            )}

            {/* Troubleshooting */}
            {embeddingStatus.troubleshooting && (
              <Alert severity="info" sx={{ mb: 2 }}>
                <Typography variant="subtitle2" gutterBottom>
                  Troubleshooting:
                </Typography>
                {embeddingStatus.troubleshooting}
              </Alert>
            )}

            {/* Model Information */}
            {embeddingStatus.status === 'healthy' && (
              <Grid container spacing={2}>
                <Grid item xs={12} sm={6}>
                  <Box>
                    <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                      Model Information
                    </Typography>
                    <List dense>
                      <ListItem>
                        <ListItemIcon>
                          <ModelTraining />
                        </ListItemIcon>
                        <ListItemText
                          primary="Model"
                          secondary="microsoft/codebert-base"
                        />
                      </ListItem>
                      <ListItem>
                        <ListItemIcon>
                          <DataObject />
                        </ListItemIcon>
                        <ListItemText
                          primary="Embedding Dimension"
                          secondary="768"
                        />
                      </ListItem>
                    </List>
                  </Box>
                </Grid>

                <Grid item xs={12} sm={6}>
                  <Box>
                    <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                      Performance Metrics
                    </Typography>
                    <List dense>
                      <ListItem>
                        <ListItemIcon>
                          <Speed />
                        </ListItemIcon>
                        <ListItemText
                          primary="Avg. Embedding Time"
                          secondary={embeddingStatus.avg_embedding_time ? 
                            `${embeddingStatus.avg_embedding_time.toFixed(2)}ms` : 'N/A'}
                        />
                      </ListItem>
                      <ListItem>
                        <ListItemIcon>
                          <Memory />
                        </ListItemIcon>
                        <ListItemText
                          primary="Model Memory Usage"
                          secondary={embeddingStatus.memory_usage ? 
                            `${Math.round(embeddingStatus.memory_usage / 1024 / 1024)}MB` : 'N/A'}
                        />
                      </ListItem>
                    </List>
                  </Box>
                </Grid>
              </Grid>
            )}

            {/* Capabilities */}
            {embeddingStatus.status === 'healthy' && (
              <Box mt={2}>
                <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                  Capabilities
                </Typography>
                <Box display="flex" flexWrap="wrap" gap={1}>
                  <Chip label="Code Embedding" size="small" color="primary" />
                  <Chip label="Semantic Search" size="small" color="primary" />
                  <Chip label="Code Similarity" size="small" color="primary" />
                  <Chip label="Multi-language Support" size="small" color="primary" />
                </Box>
              </Box>
            )}

            {/* Fallback Information */}
            {embeddingStatus.status === 'not_available' && (
              <Box mt={2}>
                <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                  Fallback Mode
                </Typography>
                <Alert severity="info">
                  System is using ChromaDB's built-in embedding model. 
                  CodeBERT provides enhanced code understanding but is not required for basic functionality.
                </Alert>
              </Box>
            )}
          </Box>
        )}
      </CardContent>
    </Card>
  );
};

export default EmbeddingSystemStatus;