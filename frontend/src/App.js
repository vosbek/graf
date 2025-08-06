import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Link, useLocation } from 'react-router-dom';
import {
  AppBar, Toolbar, Typography, Box, Drawer, List, ListItem,
  ListItemButton, ListItemIcon, ListItemText, CssBaseline,
  Alert, CircularProgress, Chip
} from '@mui/material';
import {
  Dashboard, Search, Chat, AccountTree, FolderOpen, Assessment,
  Storage, Code, Business
} from '@mui/icons-material';

import DashboardComponent from './components/Dashboard';
import SearchInterface from './components/SearchInterface';
import ChatInterface from './components/ChatInterface';
import RepositoryBrowser from './components/RepositoryBrowser';
import DependencyGraph from './components/DependencyGraph';
import MigrationPlanner from './components/MigrationPlanner';
import RepositoryIndexer from './components/RepositoryIndexer';
import EnhancedIngestionInterface from './components/EnhancedIngestionInterface';
import CrossRepositoryAnalysis from './components/CrossRepositoryAnalysis';
// Replace legacy SystemStatusDashboard import with SystemHealthOverview page if the former doesn't exist
// If SystemStatusDashboard exists elsewhere, adjust the import accordingly.
import SystemHealthOverview from './components/SystemHealthOverview';
import { ApiService } from './services/ApiService';
import { useSystemHealth } from './context/SystemHealthContext';

const DEBUG = String(process.env.REACT_APP_API_DEBUG || '').toLowerCase() === 'true';
const dlog = (...args) => {
  if (DEBUG && typeof window !== 'undefined') {
    // eslint-disable-next-line no-console
    console.log('[App]', ...args);
  }
};

const drawerWidth = 240;

// Navigation items
const navigationItems = [
  { text: 'Dashboard', icon: <Dashboard />, path: '/', component: 'Dashboard' },
  { text: 'Index Repositories', icon: <FolderOpen />, path: '/index', component: 'EnhancedIngestionInterface' },
  { text: 'Search Code', icon: <Search />, path: '/search', component: 'SearchInterface' },
  { text: 'AI Chat', icon: <Chat />, path: '/chat', component: 'ChatInterface' },
  { text: 'Repository Browser', icon: <Code />, path: '/browse', component: 'RepositoryBrowser' },
  { text: 'Dependency Graph', icon: <AccountTree />, path: '/graph', component: 'DependencyGraph' },
  { text: 'Cross-Repository Analysis', icon: <Business />, path: '/cross-repo', component: 'CrossRepositoryAnalysis' },
  { text: 'Migration Planner', icon: <Assessment />, path: '/migrate', component: 'MigrationPlanner' },
  // Route label kept as System Status but routes to SystemHealthOverview
  { text: 'System Status', icon: <Storage />, path: '/status', component: 'SystemHealthOverview' }
];

// Simple route renderer (kept without React Router v6 Routes to minimize churn)
function RouteRenderer({ path, children }) {
  const location = useLocation();
  return location.pathname === path ? children : null;
}

// Component to render based on current route with readiness gating
function AppContent() {
  const location = useLocation();
  const { data: healthData, isReady, isLoading: healthLoading, error: healthError, refresh } = useSystemHealth();
  const [repositories, setRepositories] = useState([]);
  const [loadingRepos, setLoadingRepos] = useState(false);
  const [repoError, setRepoError] = useState('');

  // Fetch repositories only when system is ready
  useEffect(() => {
    let ignore = false;
    const loadRepos = async () => {
      if (!isReady) return;
      setLoadingRepos(true);
      setRepoError('');
      const t0 = Date.now();
      dlog('repositories:load:start', { route: location.pathname });
      try {
        const reposData = await ApiService.getRepositories();
        if (!ignore) {
          setRepositories(reposData.repositories || []);
          dlog('repositories:load:success', { ms: Date.now() - t0, count: (reposData.repositories || []).length });
        }
      } catch (e) {
        if (!ignore) {
          const msg = e?.message || 'Failed to load repositories';
          setRepoError(msg);
          dlog('repositories:load:error', { ms: Date.now() - t0, message: msg });
        }
      } finally {
        if (!ignore) setLoadingRepos(false);
      }
    };
    loadRepos();
    return () => {
      ignore = true;
    };
  }, [isReady]);

  const systemHealth = undefined; // eliminate legacy prop usage; components use context directly

  const commonProps = {
    repositories
  };

  const renderBody = () => {
    // Health loading gate
    if (healthLoading && !healthData) {
      return (
        <Box display="flex" justifyContent="center" alignItems="center" minHeight="50vh">
          <CircularProgress />
        </Box>
      );
    }

    // Health error (context already backs off)
    if (healthError && !isReady) {
      return (
        <>
          <Alert severity="error" sx={{ mb: 2 }}>
            System startup issue detected. Some features are disabled until ready.
          </Alert>
          <DashboardComponent {...commonProps} />
        </>
      );
    }

    // Optional repos loading indicator independent from health
    if (loadingRepos && location.pathname !== '/status') {
      // show spinner overlay only for repo-dependent views
    }
 
    return (
      <>
        {/* Removed global system health alert visibility per request */}
 
        <RouteRenderer path="/">
          <DashboardComponent {...commonProps} />
        </RouteRenderer>
        <RouteRenderer path="/index">
          <EnhancedIngestionInterface {...commonProps} />
        </RouteRenderer>
        <RouteRenderer path="/search">
          <SearchInterface {...commonProps} />
        </RouteRenderer>
        <RouteRenderer path="/chat">
          <ChatInterface {...commonProps} />
        </RouteRenderer>
        <RouteRenderer path="/browse">
          <RepositoryBrowser {...commonProps} />
        </RouteRenderer>
        <RouteRenderer path="/graph">
          <DependencyGraph {...commonProps} />
        </RouteRenderer>
        <RouteRenderer path="/cross-repo">
          <CrossRepositoryAnalysis {...commonProps} />
        </RouteRenderer>
        <RouteRenderer path="/migrate">
          <MigrationPlanner {...commonProps} />
        </RouteRenderer>
        <RouteRenderer path="/status">
          <SystemHealthOverview {...commonProps} />
        </RouteRenderer>
      </>
    );
  };

  return (
    <Box sx={{ display: 'flex' }}>
      <CssBaseline />

      <AppBar
        position="fixed"
        sx={{
          width: `calc(100% - ${drawerWidth}px)`,
          ml: `${drawerWidth}px`,
          bgcolor: 'primary.main'
        }}
      >
        <Toolbar>
          <Typography variant="h6" noWrap component="div" sx={{ flexGrow: 1 }}>
            Codebase RAG - Legacy Application Analysis
          </Typography>

          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            {/* Header status chips removed per request */}
            {repositories.length > 0 && (
              <Chip
                label={`${repositories.length} Repositories`}
                color="info"
                size="small"
                variant="outlined"
                sx={{ color: 'white', borderColor: 'white' }}
              />
            )}
          </Box>
        </Toolbar>
      </AppBar>

      <Drawer
        sx={{
          width: drawerWidth,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: drawerWidth,
            boxSizing: 'border-box',
            bgcolor: 'grey.50'
          },
        }}
        variant="permanent"
        anchor="left"
      >
        <Toolbar>
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <Storage sx={{ mr: 1, color: 'primary.main' }} />
            <Typography variant="h6" color="primary.main" fontWeight="bold">
              CodeRAG
            </Typography>
          </Box>
        </Toolbar>

        <List>
          {navigationItems.map((item) => (
            <ListItem key={item.text} disablePadding>
              <ListItemButton
                component={Link}
                to={item.path}
                selected={location.pathname === item.path}
                sx={{
                  '&.Mui-selected': {
                    bgcolor: 'primary.light',
                    color: 'primary.main',
                    '& .MuiListItemIcon-root': {
                      color: 'primary.main',
                    },
                  },
                }}
              >
                <ListItemIcon>
                  {item.icon}
                </ListItemIcon>
                <ListItemText
                  primary={
                    <Typography component="span" variant="body1">
                      {item.text}
                    </Typography>
                  }
                />
              </ListItemButton>
            </ListItem>
          ))}
        </List>
      </Drawer>

      <Box
        component="main"
        sx={{
          flexGrow: 1,
          bgcolor: 'grey.50',
          p: 3,
          minHeight: '100vh'
        }}
      >
        <Toolbar />
        {renderBody()}
      </Box>
    </Box>
  );
}

function App() {
  return (
    <Router>
      <AppContent />
    </Router>
  );
}

export default App;