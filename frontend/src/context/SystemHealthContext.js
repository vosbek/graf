import React, { createContext, useContext, useEffect, useRef, useState, useCallback } from 'react';
import { ApiService } from '../services/ApiService';

const SystemHealthContext = createContext(null);

export function SystemHealthProvider({ children, intervalMs = 5000, maxBackoffMs = 60000 }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);

  const timerRef = useRef(null);
  const backoffRef = useRef(intervalMs);
  const stoppedRef = useRef(false);

  const scheduleNextPoll = useCallback((delay) => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }
    timerRef.current = setTimeout(() => {
      if (!stoppedRef.current) {
        poll();
      }
    }, delay);
  }, []);

  const poll = useCallback(async () => {
    try {
      setIsLoading(true);
      setError('');
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
      // reset backoff on success
      backoffRef.current = intervalMs;
      scheduleNextPoll(intervalMs);
    } catch (e) {
      const msg = e?.message || String(e);
      setError(msg);
      // Exponential backoff with cap
      const next = Math.min(backoffRef.current * 2, maxBackoffMs);
      backoffRef.current = next;
      scheduleNextPoll(next);
    } finally {
      setIsLoading(false);
    }
  }, [intervalMs, maxBackoffMs, scheduleNextPoll]);

  const refresh = useCallback(() => {
    // Manual refresh resets backoff and polls immediately
    backoffRef.current = intervalMs;
    if (timerRef.current) clearTimeout(timerRef.current);
    poll();
  }, [intervalMs, poll]);

  useEffect(() => {
    stoppedRef.current = false;
    poll();
    return () => {
      stoppedRef.current = true;
      if (timerRef.current) clearTimeout(timerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const isReady = (data?.status === 'ready');
  const value = {
    data,
    status: data?.status || 'unknown',
    checks: data?.checks || {},
    lastUpdated,
    error,
    isLoading,
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