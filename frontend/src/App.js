import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import {
  AppBar, Toolbar, Typography, Container, Box, Drawer, List, ListItem,
  ListItemButton, ListItemIcon, ListItemText, CssBaseline, Paper,
  Alert, CircularProgress, Chip
} from '@mui/material';
import {
  Dashboard, Search, Chat, AccountTree, FolderOpen, Assessment,
  Home, Storage, Code
} from '@mui/icons-material';

import DashboardComponent from './components/Dashboard';
import SearchInterface from './components/SearchInterface';
import ChatInterface from './components/ChatInterface';
import RepositoryBrowser from './components/RepositoryBrowser';
import DependencyGraph from './components/DependencyGraph';
import MigrationPlanner from './components/MigrationPlanner';
import RepositoryIndexer from './components/RepositoryIndexer';
import { ApiService } from './services/ApiService';

const drawerWidth = 240;

// Navigation items
const navigationItems = [
  { text: 'Dashboard', icon: <Dashboard />, path: '/', component: 'Dashboard' },
  { text: 'Index Repositories', icon: <FolderOpen />, path: '/index', component: 'RepositoryIndexer' },
  { text: 'Search Code', icon: <Search />, path: '/search', component: 'SearchInterface' },
  { text: 'AI Chat', icon: <Chat />, path: '/chat', component: 'ChatInterface' },
  { text: 'Repository Browser', icon: <Code />, path: '/browse', component: 'RepositoryBrowser' },
  { text: 'Dependency Graph', icon: <AccountTree />, path: '/graph', component: 'DependencyGraph' },
  { text: 'Migration Planner', icon: <Assessment />, path: '/migrate', component: 'MigrationPlanner' }
];

// Component to render based on current route
function AppContent() {
  const location = useLocation();
  const [systemHealth, setSystemHealth] = useState(null);
  const [repositories, setRepositories] = useState([]);
  const [loading, setLoading] = useState(true);

  // Load system health and repositories on mount
  useEffect(() => {
    loadSystemStatus();
  }, []);

  const loadSystemStatus = async () => {
    try {
      setLoading(true);
      const [healthData, reposData] = await Promise.all([
        ApiService.getHealth(),
        ApiService.getRepositories()
      ]);
      
      setSystemHealth(healthData);
      setRepositories(reposData.repositories || []);
    } catch (error) {
      console.error('Failed to load system status:', error);
      setSystemHealth({ status: 'unhealthy', error: error.message });
    } finally {
      setLoading(false);
    }
  };

  const renderCurrentComponent = () => {
    const currentPath = location.pathname;
    const currentNav = navigationItems.find(item => item.path === currentPath);
    
    if (!currentNav) {
      return <DashboardComponent repositories={repositories} systemHealth={systemHealth} onRefresh={loadSystemStatus} />;
    }

    const commonProps = {
      repositories,
      systemHealth,
      onRefresh: loadSystemStatus
    };

    switch (currentNav.component) {
      case 'Dashboard':
        return <DashboardComponent {...commonProps} />;
      case 'RepositoryIndexer':
        return <RepositoryIndexer {...commonProps} />;
      case 'SearchInterface':
        return <SearchInterface {...commonProps} />;
      case 'ChatInterface':
        return <ChatInterface {...commonProps} />;
      case 'RepositoryBrowser':
        return <RepositoryBrowser {...commonProps} />;
      case 'DependencyGraph':
        return <DependencyGraph {...commonProps} />;
      case 'MigrationPlanner':
        return <MigrationPlanner {...commonProps} />;
      default:
        return <DashboardComponent {...commonProps} />;
    }
  };

  return (
    <Box sx={{ display: 'flex' }}>
      <CssBaseline />
      
      {/* App Bar */}
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
          
          {/* System Health Indicator */}
          {systemHealth && (
            <Chip
              label={systemHealth.status === 'healthy' ? 'System Healthy' : 'System Issues'}
              color={systemHealth.status === 'healthy' ? 'success' : 'error'}
              size="small"
              variant="outlined"
              sx={{ color: 'white', borderColor: 'white' }}
            />
          )}
          
          {/* Repository Count */}
          {repositories.length > 0 && (
            <Chip
              label={`${repositories.length} Repositories`}
              color="info"
              size="small"
              variant="outlined"
              sx={{ ml: 1, color: 'white', borderColor: 'white' }}
            />
          )}
        </Toolbar>
      </AppBar>

      {/* Side Navigation Drawer */}
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
                <ListItemText primary={item.text} />
              </ListItemButton>
            </ListItem>
          ))}
        </List>
      </Drawer>

      {/* Main Content */}
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
        
        {loading ? (
          <Box display="flex" justifyContent="center" alignItems="center" minHeight="50vh">
            <CircularProgress />
          </Box>
        ) : (
          <>
            {/* System Health Alert */}
            {systemHealth && systemHealth.status !== 'healthy' && (
              <Alert severity="error" sx={{ mb: 2 }}>
                System Health Issue: {systemHealth.error || 'Unknown error'}
              </Alert>
            )}
            
            {/* Render Current Component */}
            {renderCurrentComponent()}
          </>
        )}
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