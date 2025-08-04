import React, { useEffect, useState } from 'react';
import { Box, Card, CardContent, Typography, Chip, Grid, Button, IconButton, LinearProgress, Alert, Stack } from '@mui/material';
import { Refresh, CheckCircle, Warning, Error as ErrorIcon, Storage, AccountTree, Code, Psychology } from '@mui/icons-material';

/**
 * Minimal System Status page
 * - Single source of truth: /api/v1/health/ready
 * - Optional: /api/v1/health/detailed (best-effort system info)
 * - No diagnostics/* calls, no extra probes
 */
export default function SystemStatusDashboard() {
  const [loading, setLoading] = useState(false);
  const [ready, setReady] = useState(null);
  const [systemInfo, setSystemInfo] = useState(null);
  const [errors, setErrors] = useState([]);

  const fetchReady = async () => {
    setLoading(true);
    setErrors([]);
    try {
      const r = await fetch('/api/v1/health/ready');
      const json = await r.json();
      setReady(json);
    } catch (e) {
      setErrors(prev => [...prev, `Ready fetch failed: ${e?.message || e}`]);
      setReady(null);
    } finally {
      setLoading(false);
    }

    // best-effort detailed
    try {
      const d = await fetch('/api/v1/health/detailed');
      if (d.ok) {
        const dj = await d.json();
        setSystemInfo(dj?.system_info || null);
      } else {
        setSystemInfo(null);
      }
    } catch (_) {
      setSystemInfo(null);
    }
  };

  useEffect(() => {
    fetchReady();
    const id = setInterval(fetchReady, 30000);
    return () => clearInterval(id);
  }, []);

  const checks = ready?.checks || {};
  const readyStatus = ready?.status || 'unknown';
  const score = typeof ready?.health_score === 'number' ? Math.round(ready.health_score) : 0;

  const iconFor = (name) => {
    const n = (name || '').toLowerCase();
    if (n.includes('chroma')) return <Storage fontSize="small" />;
    if (n.includes('neo4j')) return <AccountTree fontSize="small" />;
    if (n.includes('processor')) return <Code fontSize="small" />;
    if (n.includes('embedding')) return <Psychology fontSize="small" />;
    return <Warning fontSize="small" />;
  };

  const readyChip = (r) => (
    <Chip
      size="small"
      label={r ? 'Healthy' : 'Unhealthy'}
      color={r ? 'success' : 'error'}
      icon={r ? <CheckCircle /> : <ErrorIcon />}
      variant={r ? 'filled' : 'outlined'}
    />
  );

  return (
    <Box>
      <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
        <Typography variant="h5">System Status</Typography>
        <IconButton onClick={fetchReady} disabled={loading} aria-label="refresh">
          <Refresh />
        </IconButton>
      </Box>

      {loading && <LinearProgress sx={{ mb: 2 }} />}

      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Box display="flex" alignItems="center" justifyContent="space-between">
            <Typography variant="h6">
              {readyStatus === 'ready' ? 'System Ready' : readyStatus === 'not_ready' ? 'System Not Ready' : 'Status Unknown'}
            </Typography>
            <Stack direction="row" spacing={1}>
              <Chip
                label={`Readiness: ${readyStatus}`}
                size="small"
                color={readyStatus === 'ready' ? 'success' : readyStatus === 'not_ready' ? 'warning' : 'default'}
                icon={readyStatus === 'ready' ? <CheckCircle /> : <Warning />}
              />
              <Chip
                label={`Health: ${score}%`}
                size="small"
                variant="outlined"
                color={score >= 80 ? 'success' : score >= 60 ? 'warning' : 'error'}
              />
            </Stack>
          </Box>
        </CardContent>
      </Card>

      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Typography variant="subtitle1" gutterBottom>Components</Typography>
          <Grid container spacing={2}>
            {Object.entries(checks).map(([name, c]) => (
              <Grid item xs={12} md={4} key={name}>
                <Card variant="outlined">
                  <CardContent>
                    <Box display="flex" alignItems="center" justifyContent="space-between">
                      <Box display="flex" gap={1} alignItems="center">
                        {iconFor(name)}
                        <Typography variant="subtitle2">{name}</Typography>
                      </Box>
                      {readyChip(!!c?.ready)}
                    </Box>
                    {c?.status && <Chip sx={{ mt: 1 }} size="small" variant="outlined" label={`Status: ${c.status}`} />}
                    {c?.error && <Alert sx={{ mt: 1 }} severity="error">{c.error}</Alert>}
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        </CardContent>
      </Card>

      {systemInfo && (
        <Card sx={{ mb: 2 }}>
          <CardContent>
            <Typography variant="subtitle1" gutterBottom>System Info</Typography>
            <Grid container spacing={2}>
              {'platform' in systemInfo && (
                <Grid item xs={12} sm={6}><Typography variant="body2">Platform: {systemInfo.platform}</Typography></Grid>
              )}
              {'python_version' in systemInfo && (
                <Grid item xs={12} sm={6}><Typography variant="body2">Python: {systemInfo.python_version}</Typography></Grid>
              )}
              {'cpu_usage' in systemInfo && (
                <Grid item xs={12} sm={6}><Typography variant="body2">CPU: {systemInfo.cpu_usage}%</Typography></Grid>
              )}
              {'memory_usage' in systemInfo && (
                <Grid item xs={12} sm={6}><Typography variant="body2">Memory: {systemInfo.memory_usage}%</Typography></Grid>
              )}
            </Grid>
          </CardContent>
        </Card>
      )}

      {errors.length > 0 && (
        <Card>
          <CardContent>
            <Typography variant="subtitle1" gutterBottom>Errors</Typography>
            {errors.map((e, i) => (
              <Alert key={i} severity="warning" sx={{ mb: 1 }}>{e}</Alert>
            ))}
          </CardContent>
        </Card>
      )}
    </Box>
  );
}