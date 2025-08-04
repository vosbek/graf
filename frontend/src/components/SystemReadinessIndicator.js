import React from 'react';
import { Box, Typography, Chip, Tooltip, CircularProgress } from '@mui/material';
import { Error as ErrorIcon, Warning as WarningIcon, Pending as PendingIcon, PlayArrow, Stop } from '@mui/icons-material';
import { useSystemHealth } from '../context/SystemHealthContext';

const SystemReadinessIndicator = ({ compact = true }) => {
  // Consume fields provided by SystemHealthContext
  const { data, isReady, isLoading, error } = useSystemHealth();

  const getReadinessStatus = () => {
    if (isLoading) return 'loading';
    if (error && !isReady) return 'error';
    return isReady ? 'ready' : 'not_ready';
  };

  const getReadinessIcon = () => {
    const s = getReadinessStatus();
    if (s === 'loading') return <CircularProgress size={16} />;
    switch (s) {
      case 'ready':
        return <PlayArrow color="success" />;
      case 'not_ready':
        return <PendingIcon color="warning" />;
      case 'error':
        return <ErrorIcon color="error" />;
      default:
        return <Stop color="disabled" />;
    }
  };

  const getReadinessColor = () => {
    const s = getReadinessStatus();
    switch (s) {
      case 'ready':
        return 'success';
      case 'not_ready':
        return 'warning';
      case 'error':
        return 'error';
      default:
        return 'default';
    }
  };

  const getReadinessLabel = () => {
    const s = getReadinessStatus();
    switch (s) {
      case 'ready':
        return 'System Ready';
      case 'not_ready':
        return 'Starting Up';
      case 'error':
        return 'System Error';
      case 'loading':
        return 'Checking...';
      default:
        return 'Unknown';
    }
  };

  const getTooltipContent = () => {
    // Always reference hook-scoped variables; avoid free identifiers
    if (error && !isReady) {
      const msg = typeof error === 'string' ? error : (error?.message || 'Unknown error');
      return `Error: ${msg}`;
    }
    if (isLoading && !data) return 'Loading system status...';

    const statusLabel = getReadinessStatus();
    const score = Number.isFinite(data?.health_score) ? Math.round(data.health_score) : null;
    const validationMs = Number.isFinite(data?.validation_time) ? (data.validation_time * 1000).toFixed(0) : null;

    return [
      `Status: ${statusLabel}`,
      score !== null ? `Health Score: ${score}%` : null,
      validationMs !== null ? `Validation Time: ${validationMs}ms` : null,
    ].filter(Boolean).join('\n');
  };

  if (compact) {
    return (
      <Tooltip title={getTooltipContent()} arrow>
        <Chip
          icon={getReadinessIcon()}
          label={getReadinessLabel()}
          color={getReadinessColor()}
          size="small"
          variant={getReadinessStatus() === 'ready' ? 'filled' : 'outlined'}
        />
      </Tooltip>
    );
  }

  return (
    <Box display="flex" alignItems="center" gap={1}>
      {getReadinessIcon()}
      <Typography variant="body2">
        {getReadinessLabel()}
      </Typography>
      {Number.isFinite(data?.health_score) && (
        <Chip
          label={`${Math.round(data.health_score)}%`}
          size="small"
          color={getReadinessColor()}
        />
      )}
    </Box>
  );
};

export default SystemReadinessIndicator;