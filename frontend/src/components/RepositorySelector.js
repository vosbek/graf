import React, { useState, useEffect } from 'react';
import {
  Box, Typography, Card, CardContent, Checkbox, FormControlLabel,
  Chip, TextField, Button, Alert, CircularProgress, Grid,
  Accordion, AccordionSummary, AccordionDetails, FormGroup,
  Select, MenuItem, FormControl, InputLabel, Divider
} from '@mui/material';
import {
  ExpandMore, FilterList, Clear, CheckBox, CheckBoxOutlineBlank,
  Business, Code, Group, Assessment
} from '@mui/icons-material';
import { ApiService } from '../services/ApiService';

function RepositorySelector({ onSelectionChange, initialSelection = [], maxRepositories = 100 }) {
  const [repositories, setRepositories] = useState([]);
  const [selectedRepos, setSelectedRepos] = useState(new Set(initialSelection));
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  
  // Filters
  const [businessDomainFilter, setBusinessDomainFilter] = useState('');
  const [frameworkFilter, setFrameworkFilter] = useState('');
  const [teamOwnerFilter, setTeamOwnerFilter] = useState('');
  const [searchFilter, setSearchFilter] = useState('');
  
  // Filter options
  const [businessDomains, setBusinessDomains] = useState([]);
  const [frameworks, setFrameworks] = useState([]);
  const [teamOwners, setTeamOwners] = useState([]);
  
  // UI state
  const [showFilters, setShowFilters] = useState(false);
  const [filteredRepositories, setFilteredRepositories] = useState([]);

  useEffect(() => {
    loadRepositories();
  }, []);

  useEffect(() => {
    applyFilters();
  }, [repositories, businessDomainFilter, frameworkFilter, teamOwnerFilter, searchFilter]);

  useEffect(() => {
    if (onSelectionChange) {
      onSelectionChange(Array.from(selectedRepos));
    }
  }, [selectedRepos, onSelectionChange]);

  const loadRepositories = async () => {
    try {
      setLoading(true);
      const response = await ApiService.executeGraphQuery(
        `MATCH (r:Repository) 
         RETURN r.name as name,
                r.business_domains as business_domains,
                r.framework as framework,
                r.team_owner as team_owner,
                r.size_loc as size_loc,
                r.complexity_score as complexity_score,
                r.provides_services as provides_services,
                r.consumes_services as consumes_services
         ORDER BY r.name`,
        true
      );

      const repoData = response.records || [];
      setRepositories(repoData);

      // Extract filter options
      const domains = new Set();
      const frameworkSet = new Set();
      const owners = new Set();

      repoData.forEach(repo => {
        if (repo.business_domains) {
          repo.business_domains.forEach(domain => domains.add(domain));
        }
        if (repo.framework) frameworkSet.add(repo.framework);
        if (repo.team_owner) owners.add(repo.team_owner);
      });

      setBusinessDomains(Array.from(domains).sort());
      setFrameworks(Array.from(frameworkSet).sort());
      setTeamOwners(Array.from(owners).sort());

    } catch (error) {
      setError(`Failed to load repositories: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const applyFilters = () => {
    let filtered = repositories;

    // Apply business domain filter
    if (businessDomainFilter) {
      filtered = filtered.filter(repo => 
        repo.business_domains && repo.business_domains.includes(businessDomainFilter)
      );
    }

    // Apply framework filter
    if (frameworkFilter) {
      filtered = filtered.filter(repo => repo.framework === frameworkFilter);
    }

    // Apply team owner filter
    if (teamOwnerFilter) {
      filtered = filtered.filter(repo => repo.team_owner === teamOwnerFilter);
    }

    // Apply search filter
    if (searchFilter) {
      const searchLower = searchFilter.toLowerCase();
      filtered = filtered.filter(repo =>
        repo.name.toLowerCase().includes(searchLower) ||
        (repo.business_domains && repo.business_domains.some(domain => 
          domain.toLowerCase().includes(searchLower)
        )) ||
        (repo.provides_services && repo.provides_services.some(service =>
          service.toLowerCase().includes(searchLower)
        ))
      );
    }

    setFilteredRepositories(filtered);
  };

  const handleRepositoryToggle = (repoName) => {
    const newSelected = new Set(selectedRepos);
    
    if (newSelected.has(repoName)) {
      newSelected.delete(repoName);
    } else {
      if (newSelected.size < maxRepositories) {
        newSelected.add(repoName);
      } else {
        setError(`Maximum ${maxRepositories} repositories can be selected`);
        return;
      }
    }
    
    setSelectedRepos(newSelected);
    setError('');
  };

  const handleSelectAll = () => {
    const visibleRepoNames = filteredRepositories.slice(0, maxRepositories).map(repo => repo.name);
    setSelectedRepos(new Set(visibleRepoNames));
  };

  const handleClearSelection = () => {
    setSelectedRepos(new Set());
  };

  const clearFilters = () => {
    setBusinessDomainFilter('');
    setFrameworkFilter('');
    setTeamOwnerFilter('');
    setSearchFilter('');
  };

  const getRepositoryStats = () => {
    const selected = repositories.filter(repo => selectedRepos.has(repo.name));
    const totalLOC = selected.reduce((sum, repo) => sum + (repo.size_loc || 0), 0);
    const avgComplexity = selected.length > 0 
      ? selected.reduce((sum, repo) => sum + (repo.complexity_score || 0), 0) / selected.length 
      : 0;

    return {
      count: selected.length,
      totalLOC,
      avgComplexity: avgComplexity.toFixed(2)
    };
  };

  const stats = getRepositoryStats();

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight={200}>
        <CircularProgress />
        <Typography variant="body1" sx={{ ml: 2 }}>
          Loading repositories...
        </Typography>
      </Box>
    );
  }

  return (
    <Box>
      <Typography variant="h5" component="h2" gutterBottom>
        Repository Selection
      </Typography>
      
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {/* Selection Summary */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Grid container spacing={3} alignItems="center">
            <Grid item xs={12} md={3}>
              <Box display="flex" alignItems="center">
                <CheckBox color="primary" sx={{ mr: 1 }} />
                <Typography variant="h6">
                  {stats.count} / {maxRepositories} Selected
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={12} md={3}>
              <Box display="flex" alignItems="center">
                <Code sx={{ mr: 1, color: 'text.secondary' }} />
                <Typography variant="body2" color="text.secondary">
                  {stats.totalLOC.toLocaleString()} LOC
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={12} md={3}>
              <Box display="flex" alignItems="center">
                <Assessment sx={{ mr: 1, color: 'text.secondary' }} />
                <Typography variant="body2" color="text.secondary">
                  Avg Complexity: {stats.avgComplexity}
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={12} md={3}>
              <Box display="flex" gap={1}>
                <Button
                  size="small"
                  variant="outlined"
                  onClick={handleSelectAll}
                  disabled={filteredRepositories.length === 0}
                >
                  Select Visible
                </Button>
                <Button
                  size="small"
                  variant="outlined"
                  onClick={handleClearSelection}
                  disabled={selectedRepos.size === 0}
                >
                  Clear All
                </Button>
              </Box>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Filters */}
      <Accordion expanded={showFilters} onChange={(e, expanded) => setShowFilters(expanded)}>
        <AccordionSummary expandIcon={<ExpandMore />}>
          <Box display="flex" alignItems="center">
            <FilterList sx={{ mr: 1 }} />
            <Typography variant="h6">Filters</Typography>
            {(businessDomainFilter || frameworkFilter || teamOwnerFilter || searchFilter) && (
              <Chip
                label="Active"
                size="small"
                color="primary"
                sx={{ ml: 2 }}
              />
            )}
          </Box>
        </AccordionSummary>
        <AccordionDetails>
          <Grid container spacing={2}>
            <Grid item xs={12} md={6}>
              <TextField
                label="Search repositories"
                placeholder="Search by name, domain, or service..."
                value={searchFilter}
                onChange={(e) => setSearchFilter(e.target.value)}
                fullWidth
                size="small"
              />
            </Grid>
            <Grid item xs={12} md={2}>
              <FormControl fullWidth size="small">
                <InputLabel>Business Domain</InputLabel>
                <Select
                  value={businessDomainFilter}
                  onChange={(e) => setBusinessDomainFilter(e.target.value)}
                  label="Business Domain"
                >
                  <MenuItem value="">All Domains</MenuItem>
                  {businessDomains.map(domain => (
                    <MenuItem key={domain} value={domain}>{domain}</MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} md={2}>
              <FormControl fullWidth size="small">
                <InputLabel>Framework</InputLabel>
                <Select
                  value={frameworkFilter}
                  onChange={(e) => setFrameworkFilter(e.target.value)}
                  label="Framework"
                >
                  <MenuItem value="">All Frameworks</MenuItem>
                  {frameworks.map(framework => (
                    <MenuItem key={framework} value={framework}>{framework}</MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} md={2}>
              <FormControl fullWidth size="small">
                <InputLabel>Team Owner</InputLabel>
                <Select
                  value={teamOwnerFilter}
                  onChange={(e) => setTeamOwnerFilter(e.target.value)}
                  label="Team Owner"
                >
                  <MenuItem value="">All Teams</MenuItem>
                  {teamOwners.map(owner => (
                    <MenuItem key={owner} value={owner}>{owner}</MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} md={2} display="flex" alignItems="center">
              <Button
                startIcon={<Clear />}
                onClick={clearFilters}
                disabled={!businessDomainFilter && !frameworkFilter && !teamOwnerFilter && !searchFilter}
              >
                Clear Filters
              </Button>
            </Grid>
          </Grid>
        </AccordionDetails>
      </Accordion>

      {/* Repository List */}
      <Typography variant="body2" color="text.secondary" sx={{ mt: 2, mb: 1 }}>
        Showing {filteredRepositories.length} of {repositories.length} repositories
      </Typography>

      <Grid container spacing={2}>
        {filteredRepositories.map((repo) => (
          <Grid item xs={12} md={6} key={repo.name}>
            <Card
              sx={{
                cursor: 'pointer',
                border: selectedRepos.has(repo.name) ? '2px solid' : '1px solid',
                borderColor: selectedRepos.has(repo.name) ? 'primary.main' : 'divider',
                '&:hover': { borderColor: 'primary.main' }
              }}
              onClick={() => handleRepositoryToggle(repo.name)}
            >
              <CardContent>
                <Box display="flex" alignItems="flex-start" justifyContent="space-between">
                  <Box flex={1}>
                    <Box display="flex" alignItems="center" mb={1}>
                      <Checkbox
                        checked={selectedRepos.has(repo.name)}
                        onChange={() => handleRepositoryToggle(repo.name)}
                        onClick={(e) => e.stopPropagation()}
                      />
                      <Typography variant="h6" component="h3">
                        {repo.name}
                      </Typography>
                    </Box>

                    {/* Repository metadata */}
                    <Box mb={1}>
                      {repo.framework && (
                        <Chip 
                          label={repo.framework} 
                          size="small" 
                          variant="outlined" 
                          sx={{ mr: 1, mb: 0.5 }} 
                        />
                      )}
                      {repo.team_owner && (
                        <Chip 
                          label={repo.team_owner} 
                          size="small" 
                          variant="outlined"
                          icon={<Group />}
                          sx={{ mr: 1, mb: 0.5 }} 
                        />
                      )}
                    </Box>

                    {/* Business domains */}
                    {repo.business_domains && repo.business_domains.length > 0 && (
                      <Box mb={1}>
                        {repo.business_domains.map(domain => (
                          <Chip
                            key={domain}
                            label={domain}
                            size="small"
                            icon={<Business />}
                            sx={{ mr: 0.5, mb: 0.5 }}
                          />
                        ))}
                      </Box>
                    )}

                    {/* Services */}
                    {repo.provides_services && repo.provides_services.length > 0 && (
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          Provides: {repo.provides_services.join(', ')}
                        </Typography>
                      </Box>
                    )}

                    <Divider sx={{ my: 1 }} />

                    {/* Repository stats */}
                    <Box display="flex" justifyContent="space-between" alignItems="center">
                      <Typography variant="caption" color="text.secondary">
                        {repo.size_loc ? `${repo.size_loc.toLocaleString()} LOC` : 'Size unknown'}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        Complexity: {repo.complexity_score ? repo.complexity_score.toFixed(1) : 'N/A'}
                      </Typography>
                    </Box>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      {filteredRepositories.length === 0 && !loading && (
        <Box textAlign="center" py={4}>
          <Typography variant="body1" color="text.secondary">
            No repositories match the current filters.
          </Typography>
          <Button onClick={clearFilters} sx={{ mt: 1 }}>
            Clear Filters
          </Button>
        </Box>
      )}
    </Box>
  );
}

export default RepositorySelector;