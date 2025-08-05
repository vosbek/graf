import React, { createContext, useContext, useEffect, useRef, useState, useCallback } from 'react';
import { ApiService } from '../services/ApiService';

const SystemHealthContext = createContext(null);

const DEBUG = String(process.env.REACT_APP_API_DEBUG || '').toLowerCase() === 'true';
const dlog = (...args) => {
  if (DEBUG && typeof window !== 'undefined') {
    // eslint-disable-next-line no-console
    console.log('[SystemHealth]', ...args);
  }
};

// Get polling interval from environment variable or use default (30 seconds)
const DEFAULT_POLL_INTERVAL = 30000; // 30 seconds
const ENV_POLL_INTERVAL = process.env.REACT_APP_HEALTH_POLL_INTERVAL ?
  parseInt(process.env.REACT_APP_HEALTH_POLL_INTERVAL, 10) : DEFAULT_POLL_INTERVAL;

// Check if polling should be disabled entirely
const POLLING_DISABLED = String(process.env.REACT_APP_DISABLE_HEALTH_POLLING || '').toLowerCase() === 'true';

export function SystemHealthProvider({ children, intervalMs = ENV_POLL_INTERVAL, maxBackoffMs = 60000, disablePolling = POLLING_DISABLED }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isInitialLoad, setIsInitialLoad] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(null);

  const timerRef = useRef(null);
  const backoffRef = useRef(intervalMs);
  const stoppedRef = useRef(false);
  const pollIdRef = useRef(0);

  const scheduleNextPoll = useCallback((delay) => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }
    
    // Don't schedule next poll if polling is disabled
    if (disablePolling) {
      dlog('scheduleNextPoll skipped (polling disabled)');
      return;
    }
    
    dlog('scheduleNextPoll', { delay });
    timerRef.current = setTimeout(() => {
      if (!stoppedRef.current) {
        poll();
      }
    }, delay);
  }, [disablePolling]);

  const poll = useCallback(async () => {
    const id = ++pollIdRef.current;
    const t0 = Date.now();
    try {
      // Only show loading state on initial load or manual refresh, not on routine polls
      if (isInitialLoad) {
        setIsLoading(true);
      }
      setError('');
      dlog('poll:start', { id, backoffMs: backoffRef.current, isInitialLoad });
      const status = await ApiService.getSystemStatus();
      // If server returned an error envelope, normalize
      if (status && typeof status === 'object' && status.status) {
        setData(status);
      } else {
        setData({
          status: 'unknown',
          checks: {},
          message: 'Unexpected health payload shape',
          raw: status
        });
      }
      setLastUpdated(new Date());
      // Mark initial load as complete
      if (isInitialLoad) {
        setIsInitialLoad(false);
      }
      // reset backoff on success
      backoffRef.current = intervalMs;
      dlog('poll:success', { id, ms: Date.now() - t0 });
      scheduleNextPoll(intervalMs);
    } catch (e) {
      const msg = e?.message || String(e);
      setError(msg);
      // Exponential backoff with cap
      const next = Math.min(backoffRef.current * 2, maxBackoffMs);
      backoffRef.current = next;
      dlog('poll:error', { id, ms: Date.now() - t0, message: msg, nextDelay: next });
      scheduleNextPoll(next);
    } finally {
      if (isInitialLoad) {
        setIsLoading(false);
      }
    }
  }, [intervalMs, maxBackoffMs, scheduleNextPoll, disablePolling, isInitialLoad]);

  const refresh = useCallback(() => {
    // Manual refresh resets backoff and polls immediately
    // For manual refresh, we want to show loading state
    backoffRef.current = intervalMs;
    if (timerRef.current) clearTimeout(timerRef.current);
    setIsInitialLoad(true); // Treat manual refresh like initial load
    dlog('refresh');
    poll();
  }, [intervalMs, poll]);

  useEffect(() => {
    stoppedRef.current = false;
    dlog('mount', { pollingDisabled: disablePolling });
    
    // Only start polling if not disabled
    if (!disablePolling) {
      poll();
    } else {
      // If polling is disabled, still do an initial fetch
      poll();
      // But don't schedule the next one
      stoppedRef.current = true;
    }
    
    return () => {
      stoppedRef.current = true;
      if (timerRef.current) clearTimeout(timerRef.current);
      dlog('unmount');
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [disablePolling]);

  const isReady = (data?.status === 'ready');
  const value = {
    data,
    status: data?.status || 'unknown',
    checks: data?.checks || {},
    lastUpdated,
    error,
    isLoading,
    isInitialLoad,
    isReady,
    refresh
  };

  return (
    <SystemHealthContext.Provider value={value}>
      {children}
    </SystemHealthContext.Provider>
  );
}

export function useSystemHealth() {
  const ctx = useContext(SystemHealthContext);
  if (!ctx) {
    throw new Error('useSystemHealth must be used within a SystemHealthProvider');
  }
  return ctx;
}