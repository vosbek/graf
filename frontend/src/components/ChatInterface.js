import React, { useState, useRef, useEffect } from 'react';
import {
  Box, Typography, TextField, Button, Paper, List, ListItem,
  Alert, CircularProgress, Divider, ListItemText
} from '@mui/material';
import { Send } from '@mui/icons-material';
import { ApiService } from '../services/ApiService';
import { useSystemHealth } from '../context/SystemHealthContext';

function ChatInterface({ repositories }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const { isReady, isLoading: healthLoading, isInitialLoad, error: healthError } = useSystemHealth();
  const listRef = useRef(null);

  const readinessBanner = (!isReady || isInitialLoad || healthError) ? (
    <Alert severity={healthError ? 'error' : 'info'} sx={{ mb: 2 }}>
      {!isReady ? 'System is starting up. Chat is disabled until the system is ready.' :
       isInitialLoad ? 'Checking system readiness...' :
       `Health error: ${healthError}`}
    </Alert>
  ) : null;

  const handleSend = async () => {
    if (!isReady) {
      setError('System is not ready. Please wait for readiness before chatting.');
      return;
    }
    const content = input.trim();
    if (!content) return;

    setLoading(true);
    setError('');
    const userMsg = { role: 'user', content };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');

    try {
      const resp = await ApiService.askAgent(content, null, { top_k: 8, min_score: 0.0, mode: 'semantic' });
      const answer = resp?.answer || 'No response.';
      const citations = Array.isArray(resp?.citations) ? resp.citations.length : 0;
      const botMsg = { role: 'assistant', content: citations > 0 ? `${answer}\n\n(${citations} citation${citations === 1 ? '' : 's'})` : answer };
      setMessages((prev) => [...prev, botMsg]);
    } catch (e) {
      // ApiService interceptor normalizes to Error(message)
      setError(e?.message || 'Request failed');
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  };

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages]);

  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom>
        AI Chat
      </Typography>
      <Typography variant="body1" color="text.secondary" paragraph>
        Ask questions about your codebase, repositories, and migration strategies.
      </Typography>

      {readinessBanner}

      {repositories && repositories.length === 0 && (
        <Alert severity="info" sx={{ mb: 2 }}>
          No repositories indexed yet. Responses may be limited until repositories are indexed.
        </Alert>
      )}

      <Paper sx={{ p: 2, mb: 2 }}>
        <Box display="flex" gap={1} alignItems="center">
          <TextField
            label="Type your message"
            placeholder="Ask about dependencies, services, or migration steps..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyPress}
            fullWidth
            multiline
            minRows={1}
            maxRows={6}
            disabled={!isReady}
          />
          <Button
            variant="contained"
            startIcon={<Send />}
            onClick={handleSend}
            disabled={!isReady || loading || !input.trim()}
          >
            Send
          </Button>
        </Box>
        {loading && (
          <Box display="flex" justifyContent="center" mt={2}>
            <CircularProgress size={24} />
          </Box>
        )}
        {error && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {error}
          </Alert>
        )}
      </Paper>

      <Paper sx={{ p: 2, maxHeight: 420, overflow: 'auto' }} ref={listRef}>
        <List>
          {messages.map((m, idx) => (
            <React.Fragment key={idx}>
              <ListItem alignItems="flex-start">
                <ListItemText
                  primary={
                    <Typography component="span" variant="subtitle2" color={m.role === 'user' ? 'primary.main' : 'secondary.main'}>
                      {m.role === 'user' ? 'You' : 'Assistant'}
                    </Typography>
                  }
                  secondary={
                    <Typography component="span" variant="body2" color="text.secondary" sx={{ display: 'block', whiteSpace: 'pre-wrap' }}>
                      {m.content}
                    </Typography>
                  }
                />
              </ListItem>
              {idx < messages.length - 1 && <Divider />}
            </React.Fragment>
          ))}
        </List>
      </Paper>
    </Box>
  );
}

export default ChatInterface;