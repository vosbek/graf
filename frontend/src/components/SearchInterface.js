import React, { useState } from 'react';
import {
  Box, Typography, TextField, Button, Paper, List, ListItem,
  ListItemText, Chip, Alert, CircularProgress, Divider
} from '@mui/material';
import { Search } from '@mui/icons-material';
import { ApiService } from '../services/ApiService';
import { useSystemHealth } from '../context/SystemHealthContext';

function SearchInterface({ repositories }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const { isReady, isLoading: healthLoading, isInitialLoad, error: healthError } = useSystemHealth();

  const handleSearch = async () => {
    if (!isReady) {
      setError('System is not ready. Please wait for readiness before searching.');
      return;
    }
    if (!query.trim()) return;

    setLoading(true);
    setError('');

    try {
      const searchResults = await ApiService.searchCode(query, {
        limit: 20,
        threshold: 0.7
      });
      setResults(searchResults);
    } catch (error) {
      setError(error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (event) => {
    if (event.key === 'Enter') {
      handleSearch();
    }
  };

  const readinessBanner = (!isReady || isInitialLoad || healthError) ? (
    <Alert severity={healthError ? 'error' : 'info'} sx={{ mb: 3 }}>
      {!isReady ? 'System is starting up. Search is disabled until the system is ready.' :
       isInitialLoad ? 'Checking system readiness...' :
       `Health error: ${healthError}`}
    </Alert>
  ) : null;

  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom>
        Search Code
      </Typography>
      <Typography variant="body1" color="text.secondary" paragraph>
        Search across all indexed repositories using semantic understanding.
      </Typography>

      {readinessBanner}

      {repositories.length === 0 && (
        <Alert severity="info" sx={{ mb: 3 }}>
          No repositories indexed yet. Please index some repositories first.
        </Alert>
      )}

      {/* Search Box */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Box display="flex" gap={2} alignItems="center">
          <TextField
            label="Search query"
            placeholder="e.g., authentication logic, payment processing, user validation"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyPress={handleKeyPress}
            fullWidth
            variant="outlined"
            disabled={!isReady}
            helperText={!isReady ? 'System not ready yet. Searching is disabled.' : ''}
          />
          <Button
            variant="contained"
            startIcon={<Search />}
            onClick={handleSearch}
            disabled={!isReady || loading || !query.trim() || repositories.length === 0}
            size="large"
          >
            Search
          </Button>
        </Box>

        {loading && (
          <Box display="flex" justifyContent="center" mt={2}>
            <CircularProgress />
          </Box>
        )}
      </Paper>

      {/* Error Display */}
      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Results */}
      {results.length > 0 && (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            Search Results ({results.length})
          </Typography>
          
          <List>
            {results.map((result, index) => (
              <React.Fragment key={index}>
                <ListItem alignItems="flex-start">
                  <ListItemText
                    primary={
                      <Box display="flex" alignItems="center" gap={1}>
                        <Typography variant="subtitle1" component="span">
                          {result.file_path}
                        </Typography>
                        <Chip
                          label={`${(result.score * 100).toFixed(0)}%`}
                          size="small"
                          color="primary"
                        />
                      </Box>
                    }
                    secondary={
                      <Box sx={{ mt: 1 }}>
                        <Typography
                          variant="body2"
                          component="pre"
                          sx={{
                            whiteSpace: 'pre-wrap',
                            bgcolor: 'grey.50',
                            p: 1,
                            borderRadius: 1,
                            fontSize: '0.875rem',
                            fontFamily: 'monospace'
                          }}
                        >
                          {result.content.slice(0, 500)}
                          {result.content.length > 500 && '...'}
                        </Typography>
                      </Box>
                    }
                  />
                </ListItem>
                {index < results.length - 1 && <Divider />}
              </React.Fragment>
            ))}
          </List>
        </Paper>
      )}

      {/* No Results */}
      {!loading && results.length === 0 && query && (
        <Alert severity="info">
          No results found for "{query}". Try using different keywords or check if repositories are properly indexed.
        </Alert>
      )}
    </Box>
  );
}

export default SearchInterface;