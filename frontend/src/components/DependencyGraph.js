import React, { useState, useEffect, useRef } from 'react';
import {
  Box, Typography, Paper, Alert, Button, FormControl,
  InputLabel, Select, MenuItem, CircularProgress, Card, CardContent,
  Chip, Grid, Divider, Switch, FormControlLabel, Slider,
  Tooltip, IconButton, Dialog, DialogTitle, DialogContent, List,
  ListItem, ListItemText, Badge
} from '@mui/material';
import {
  AccountTree, Refresh, ZoomIn, ZoomOut, CenterFocusStrong,
  FilterList, Info, Close, Fullscreen, Download
} from '@mui/icons-material';
import cytoscape from 'cytoscape';
import dagre from 'cytoscape-dagre';
import coseBilkent from 'cytoscape-cose-bilkent';
import euler from 'cytoscape-euler';

import { ApiService } from '../services/ApiService';
import { useSystemHealth } from '../context/SystemHealthContext';

// Register cytoscape extensions
cytoscape.use(dagre);
cytoscape.use(coseBilkent);
cytoscape.use(euler);

function DependencyGraph({ repositories }) {
  const [selectedRepo, setSelectedRepo] = useState('');
  const [graphData, setGraphData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [selectedNode, setSelectedNode] = useState(null);
  const [showNodeDetails, setShowNodeDetails] = useState(false);
  const [layout, setLayout] = useState('dagre');
  const [showLabels, setShowLabels] = useState(true);
  const [nodeSpacing, setNodeSpacing] = useState(100);
  const [graphStats, setGraphStats] = useState(null);
  const [fileDetails, setFileDetails] = useState(null);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const { isReady, isLoading: healthLoading, error: healthError } = useSystemHealth();
  
  const cyRef = useRef(null);
  const containerRef = useRef(null);

  // Layout options for different graph types
  const layoutOptions = {
    dagre: {
      name: 'dagre',
      rankDir: 'TB', // Top to bottom
      spacingFactor: 1.5,
      nodeDimensionsIncludeLabels: true,
      animate: true,
      animationDuration: 500
    },
    'cose-bilkent': {
      name: 'cose-bilkent',
      nodeRepulsion: 4500,
      idealEdgeLength: 50,
      edgeElasticity: 0.45,
      nestingFactor: 0.1,
      gravity: 0.25,
      numIter: 2500,
      animate: true,
      animationDuration: 500
    },
    euler: {
      name: 'euler',
      springLength: edge => 80,
      springCoeff: 0.0008,
      mass: 4,
      gravity: -1.2,
      pull: 0.001,
      theta: 0.666,
      dragCoeff: 0.02,
      movementThreshold: 1,
      timeStep: 20,
      refresh: 10,
      animate: true,
      animationDuration: 500
    }
  };

  useEffect(() => {
    if (!isReady) return;
    if (selectedRepo) {
      loadGraphData(selectedRepo);
    }
    // Cleanup Cytoscape instance on unmount to prevent leaks
    return () => {
      if (cyRef.current) {
        try {
          cyRef.current.destroy();
        } catch (_) {}
        cyRef.current = null;
      }
    };
  }, [selectedRepo, isReady]);

  const loadFileDetails = async (repoName, filePath) => {
    if (!filePath || filePath.startsWith('node_modules/')) return;
    
    setLoadingDetails(true);
    try {
      const details = await ApiService.analyzeFile(repoName, filePath);
      setFileDetails(details);
    } catch (error) {
      console.error('Failed to load file details:', error);
      setFileDetails(null);
    } finally {
      setLoadingDetails(false);
    }
  };

  const loadGraphData = async (repoName) => {
    if (!repoName || !isReady) return;

    setLoading(true);
    setError('');

    try {
      const viz = await ApiService.getRepositoryGraphVisualization(repoName, { depth: 2 });

      if (!viz || (!viz.nodes?.length && !viz.edges?.length)) {
        setGraphData(null);
        setGraphStats(null);
        setError('No graph data available. Index the repository to populate the knowledge graph, then refresh.');
        setLoading(false);
        return;
      }

      const normalized = {
        nodes: viz.nodes || [],
        edges: viz.edges || [],
        source: 'visualization_endpoint'
      };

      setGraphData(normalized);

      try {
        const statsData = await ApiService.getSystemStatus();
        setGraphStats(statsData);
      } catch (_) {
        setGraphStats(null);
      }

      setTimeout(() => initializeGraph(normalized, graphStats), 100);
    } catch (error) {
      setError(error.message);
    } finally {
      setLoading(false);
    }
  };

  const initializeGraph = async (data, stats) => {
    if (!containerRef.current || !data) return;

    // Generate graph elements from repository data
    const elements = generateGraphElements(data, stats);
    
    if (elements.length === 0) {
      setError('No graph data available for this repository');
      return;
    }

    // Destroy any existing instance before re-initializing to avoid duplicate listeners and memory leaks
    if (cyRef.current) {
      try {
        cyRef.current.destroy();
      } catch (_) {}
      cyRef.current = null;
    }

    // Initialize Cytoscape
    const cy = cytoscape({
      container: containerRef.current,
      elements: elements,
      style: getGraphStyles(),
      layout: layoutOptions[layout],
      minZoom: 0.1,
      maxZoom: 3,
      wheelSensitivity: 0.2
    });

    // Store reference
    cyRef.current = cy;

    // Add event listeners
    cy.on('tap', 'node', function(evt) {
      const node = evt.target;
      const nodeData = node.data();
      
      setSelectedNode({
        id: node.id(),
        data: nodeData,
        position: node.position(),
        degree: node.degree()
      });
      setShowNodeDetails(true);
      
      // Load detailed file analysis for file nodes
      if (nodeData.type === 'file' || nodeData.type === 'javascript' || nodeData.type === 'python') {
        const filePath = nodeData.path || nodeData.file_path;
        if (filePath) {
          loadFileDetails(selectedRepo, filePath);
        }
      }
    });

    cy.on('tap', function(evt) {
      if (evt.target === cy) {
        setSelectedNode(null);
        setShowNodeDetails(false);
      }
    });

    // Highlight connected nodes on hover
    cy.on('mouseover', 'node', function(evt) {
      const node = evt.target;
      const connectedEdges = node.connectedEdges();
      const connectedNodes = connectedEdges.connectedNodes();
      
      cy.elements().removeClass('highlighted');
      node.addClass('highlighted');
      connectedNodes.addClass('highlighted');
      connectedEdges.addClass('highlighted');
    });

    cy.on('mouseout', 'node', function(evt) {
      cy.elements().removeClass('highlighted');
    });
  };

  const generateGraphElements = (data, stats) => {
    const elements = [];
    const addedNodes = new Set();

    // Defensive: verify arrays
    const nodes = Array.isArray(data?.nodes) ? data.nodes : [];
    const edges = Array.isArray(data?.edges) ? data.edges : [];

    if (nodes.length === 0) {
      return elements;
    }

    nodes.forEach((nodeRaw) => {
      const node = nodeRaw || {};
      const id = String(node.id ?? '');
      if (!id || addedNodes.has(id)) return;

      // Ensure safe fields with fallbacks to avoid cytoscape warnings
      const type = node.type || 'unknown';
      const size = Number.isFinite(node.size) ? node.size : calculateNodeSizeFromType(type);
      const label = node.name || node.path || type || id;
      const description = node.path || node.name || `${type}`;

      const dataObj = {
        id,
        label,
        type,
        size,
        description
      };

      // Only attach optional fields if present to avoid undefined mappings
      if (node.color) dataObj.color = node.color;
      if (node.path) dataObj.path = node.path;
      if (node.name) dataObj.name = node.name;
      if (node.version) dataObj.version = node.version;
      if (Number.isFinite(node.count)) dataObj.count = node.count;

      elements.push({ data: dataObj });
      addedNodes.add(id);
    });

    edges.forEach((edgeRaw) => {
      const e = edgeRaw || {};
      const src = String(e.source ?? '');
      const tgt = String(e.target ?? '');
      if (!src || !tgt) return;
      if (!addedNodes.has(src) || !addedNodes.has(tgt)) return;

      const rel = e.relationship_type || e.type || 'rel';
      const eid = `edge-${src}-${tgt}-${rel}`;

      elements.push({
        data: {
          id: eid,
          source: src,
          target: tgt,
          type: mapRelationshipType(rel),
          label: rel,
          weight: Number.isFinite(e.weight) ? e.weight : 1
        }
      });
    });

    return elements;
  };

  // Helper functions for Neo4j data mapping
  const mapNeo4jNodeType = (neo4jType) => {
    const typeMap = {
      'Repository': 'repository',
      'File': 'file',
      'Package': 'package',
      'Class': 'class',
      'Dependency': 'dependency',
      'MavenArtifact': 'dependency',
      'Configuration': 'config'
    };
    return typeMap[neo4jType] || 'unknown';
  };

  const calculateNodeSize = (node) => {
    if (node.type === 'Repository') return 60;
    if (node.type === 'Package') return 45;
    if (node.type === 'Dependency' || node.type === 'MavenArtifact') return 40;
    if (node.size) return Math.min(Math.max(node.size / 100, 20), 50);
    return 30;
  };

  const calculateNodeSizeFromType = (nodeType) => {
    switch (nodeType) {
      case 'repository': return 60;
      case 'directory': return 45;
      case 'file': return 35;
      case 'javascript': return 40;
      case 'python': return 40;
      case 'config': return 35;
      case 'documentation': return 30;
      default: return 30;
    }
  };

  const generateNodeDescription = (node) => {
    if (node.type === 'Repository') return `Repository: ${node.name}`;
    if (node.type === 'File') return `File: ${node.path}`;
    if (node.type === 'Dependency' || node.type === 'MavenArtifact') {
      return `${node.groupId || 'Unknown'}:${node.artifactId || node.name} ${node.version ? `v${node.version}` : ''}`;
    }
    return `${node.type}: ${node.name || node.path || 'Unknown'}`;
  };

  const mapRelationshipType = (relationshipType) => {
    const typeMap = {
      'DEPENDS_ON': 'depends-on',
      'CONTAINS': 'contains',
      'USES': 'uses',
      'IMPORTS': 'imports',
      'CALLS': 'calls',
      'EXTENDS': 'extends',
      'IMPLEMENTS': 'implements'
    };
    return typeMap[relationshipType] || relationshipType.toLowerCase();
  };

  const getGraphStyles = () => [
    // Base node style with safe fallbacks to avoid cytoscape warnings when data fields are missing
    {
      selector: 'node',
      style: {
        'background-color': '#90caf9', // fallback color
        'label': showLabels ? 'data(label)' : '',
        'text-valign': 'center',
        'text-halign': 'center',
        'font-size': '12px',
        'font-weight': 'bold',
        'color': '#333',
        'text-outline-width': 2,
        'text-outline-color': '#fff',
        'width': 'mapData(size, 10, 120, 20, 60)', // bounded fallback
        'height': 'mapData(size, 10, 120, 20, 60)',
        'border-width': 2,
        'border-color': '#666',
        'transition-property': 'background-color, border-color, width, height',
        'transition-duration': '0.2s'
      }
    },
    // Only apply color mapping when a color is defined to suppress mapping warnings
    {
      selector: 'node[color]',
      style: {
        'background-color': 'data(color)'
      }
    },
    {
      selector: 'node[type="repository"]',
      style: {
        'background-color': '#1976d2',
        'border-color': '#1565c0',
        'shape': 'roundrectangle'
      }
    },
    {
      selector: 'node[type="dependency"]',
      style: {
        'background-color': '#ff9800',
        'border-color': '#f57c00',
        'shape': 'ellipse'
      }
    },
    {
      selector: 'node[type="package"]',
      style: {
        'background-color': '#4caf50',
        'border-color': '#388e3c',
        'shape': 'rectangle'
      }
    },
    {
      selector: 'node[type="config"]',
      style: {
        'background-color': '#9c27b0',
        'border-color': '#7b1fa2',
        'shape': 'triangle'
      }
    },
    {
      selector: 'node[type="file"]',
      style: {
        'background-color': '#795548',
        'border-color': '#5d4037',
        'shape': 'rectangle'
      }
    },
    {
      selector: 'node[type="class"]',
      style: {
        'background-color': '#607d8b',
        'border-color': '#455a64',
        'shape': 'hexagon'
      }
    },
    {
      selector: 'node[type="directory"]',
      style: {
        'background-color': '#ffc107',
        'border-color': '#ff8f00',
        'shape': 'roundrectangle'
      }
    },
    {
      selector: 'node[type="javascript"]',
      style: {
        'background-color': '#f7df1e',
        'border-color': '#d4c71a',
        'shape': 'rectangle'
      }
    },
    {
      selector: 'node[type="python"]',
      style: {
        'background-color': '#3776ab',
        'border-color': '#2b5a87',
        'shape': 'rectangle'
      }
    },
    {
      selector: 'node[type="documentation"]',
      style: {
        'background-color': '#17a2b8',
        'border-color': '#138496',
        'shape': 'ellipse'
      }
    },
    {
      selector: 'node[type="unknown"]',
      style: {
        'background-color': '#9e9e9e',
        'border-color': '#616161',
        'shape': 'ellipse'
      }
    },
    {
      selector: 'edge',
      style: {
        'width': 2,
        'line-color': '#ccc',
        'target-arrow-color': '#ccc',
        'target-arrow-shape': 'triangle',
        'curve-style': 'bezier',
        'label': showLabels ? 'data(label)' : '',
        'font-size': '10px',
        'text-rotation': 'autorotate',
        'text-margin-y': -10,
        'transition-property': 'line-color, target-arrow-color',
        'transition-duration': '0.2s'
      }
    },
    {
      selector: 'edge[type="depends-on"]',
      style: {
        'line-color': '#ff5722',
        'target-arrow-color': '#ff5722',
        'line-style': 'dashed'
      }
    },
    {
      selector: 'edge[type="uses"]',
      style: {
        'line-color': '#2196f3',
        'target-arrow-color': '#2196f3'
      }
    },
    {
      selector: 'edge[type="configures"]',
      style: {
        'line-color': '#9c27b0',
        'target-arrow-color': '#9c27b0',
        'line-style': 'dotted'
      }
    },
    {
      selector: 'edge[type="imports"]',
      style: {
        'line-color': '#795548',
        'target-arrow-color': '#795548'
      }
    },
    {
      selector: 'edge[type="calls"]',
      style: {
        'line-color': '#ff5722',
        'target-arrow-color': '#ff5722',
        'line-style': 'dashed'
      }
    },
    {
      selector: 'edge[type="extends"]',
      style: {
        'line-color': '#8bc34a',
        'target-arrow-color': '#8bc34a',
        'target-arrow-shape': 'diamond'
      }
    },
    {
      selector: 'edge[type="implements"]',
      style: {
        'line-color': '#00bcd4',
        'target-arrow-color': '#00bcd4',
        'target-arrow-shape': 'diamond',
        'line-style': 'dotted'
      }
    },
    {
      selector: '.highlighted',
      style: {
        'background-color': '#ffeb3b',
        'line-color': '#ffeb3b',
        'target-arrow-color': '#ffeb3b',
        'border-color': '#f57f17',
        'z-index': 10
      }
    }
  ];

  const handleLayoutChange = (newLayout) => {
    setLayout(newLayout);
    if (cyRef.current) {
      const layoutConfig = { ...layoutOptions[newLayout] };
      if (newLayout === 'dagre') {
        layoutConfig.spacingFactor = nodeSpacing / 100;
      }
      // Re-run layout safely
      try {
        cyRef.current.layout(layoutConfig).run();
      } catch (_) {}
    }
  };

  const handleNodeSpacingChange = (event, newValue) => {
    setNodeSpacing(newValue);
    if (cyRef.current && layout === 'dagre') {
      const layoutConfig = { ...layoutOptions.dagre };
      layoutConfig.spacingFactor = newValue / 100;
      cyRef.current.layout(layoutConfig).run();
    }
  };

  const handleToggleLabels = (event) => {
    setShowLabels(event.target.checked);
    if (cyRef.current) {
      try {
        cyRef.current.style().update();
      } catch (_) {}
    }
  };

  const handleZoomIn = () => {
    if (cyRef.current) {
      try {
        cyRef.current.zoom(cyRef.current.zoom() * 1.2);
        cyRef.current.center();
      } catch (_) {}
    }
  };

  const handleZoomOut = () => {
    if (cyRef.current) {
      try {
        cyRef.current.zoom(cyRef.current.zoom() * 0.8);
        cyRef.current.center();
      } catch (_) {}
    }
  };

  const handleFitToView = () => {
    if (cyRef.current) {
      try {
        cyRef.current.fit();
      } catch (_) {}
    }
  };

  const handleExportGraph = () => {
    if (cyRef.current) {
      try {
        const png64 = cyRef.current.png({ scale: 2 });
        const link = document.createElement('a');
        link.download = `${selectedRepo}-dependency-graph.png`;
        link.href = png64;
        link.click();
      } catch (_) {}
    }
  };

  const NodeDetailsDialog = () => (
    <Dialog 
      open={showNodeDetails} 
      onClose={() => {
        setShowNodeDetails(false);
        setFileDetails(null);
      }}
      maxWidth="md"
      fullWidth
    >
      <DialogTitle>
        <Box display="flex" justifyContent="space-between" alignItems="center">
          Node Details
          <IconButton onClick={() => {
            setShowNodeDetails(false);
            setFileDetails(null);
          }}>
            <Close />
          </IconButton>
        </Box>
      </DialogTitle>
      <DialogContent>
        {selectedNode && (
          <Box>
            <Typography variant="h6" gutterBottom>
              {selectedNode.data.label}
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              {selectedNode.data.description}
            </Typography>
            
            <Grid container spacing={2}>
              <Grid item xs={6}>
                <Chip label={`Type: ${selectedNode.data.type}`} size="small" />
              </Grid>
              <Grid item xs={6}>
                <Chip label={`Connections: ${selectedNode.degree}`} size="small" color="primary" />
              </Grid>
            </Grid>

            {selectedNode.data.version && (
              <Box sx={{ mt: 2 }}>
                <Typography variant="subtitle2">Version: {selectedNode.data.version}</Typography>
              </Box>
            )}

            {selectedNode.data.count && (
              <Box sx={{ mt: 2 }}>
                <Typography variant="subtitle2">Files: {selectedNode.data.count}</Typography>
              </Box>
            )}

            {/* File Details Section */}
            {(selectedNode.data.type === 'file' || selectedNode.data.type === 'javascript' || selectedNode.data.type === 'python') && (
              <Box sx={{ mt: 3 }}>
                <Divider sx={{ mb: 2 }} />
                <Typography variant="h6" gutterBottom>
                  File Analysis
                </Typography>
                
                {loadingDetails && (
                  <Box display="flex" alignItems="center" gap={1}>
                    <CircularProgress size={16} />
                    <Typography variant="body2">Loading file details...</Typography>
                  </Box>
                )}
                
                {fileDetails && (
                  <>
                    {/* Migration Complexity Overview */}
                    <Box sx={{ mb: 2, p: 2, bgcolor: 'grey.50', borderRadius: 1 }}>
                      <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
                        Migration Assessment
                      </Typography>
                      <Typography variant="body2" color="text.secondary" paragraph>
                        {fileDetails.migration_insights?.complexity_score}
                      </Typography>
                      
                      <Grid container spacing={2}>
                        <Grid item xs={6} sm={3}>
                          <Chip 
                            label={`${fileDetails.migration_insights?.api_endpoints_found || 0} API Endpoints`} 
                            size="small" 
                            color={fileDetails.migration_insights?.api_endpoints_found > 0 ? "error" : "default"}
                            variant={fileDetails.migration_insights?.api_endpoints_found > 0 ? "filled" : "outlined"}
                          />
                        </Grid>
                        <Grid item xs={6} sm={3}>
                          <Chip 
                            label={`${fileDetails.migration_insights?.database_operations || 0} DB Operations`} 
                            size="small" 
                            color={fileDetails.migration_insights?.database_operations > 0 ? "warning" : "default"}
                            variant={fileDetails.migration_insights?.database_operations > 0 ? "filled" : "outlined"}
                          />
                        </Grid>
                        <Grid item xs={6} sm={3}>
                          <Chip 
                            label={`${fileDetails.migration_insights?.critical_business_functions || 0} Business Logic`} 
                            size="small" 
                            color={fileDetails.migration_insights?.critical_business_functions > 0 ? "secondary" : "default"}
                            variant={fileDetails.migration_insights?.critical_business_functions > 0 ? "filled" : "outlined"}
                          />
                        </Grid>
                        <Grid item xs={6} sm={3}>
                          <Chip 
                            label={`${fileDetails.migration_insights?.external_integrations || 0} Integrations`} 
                            size="small" 
                            color={fileDetails.migration_insights?.external_integrations > 0 ? "info" : "default"}
                            variant={fileDetails.migration_insights?.external_integrations > 0 ? "filled" : "outlined"}
                          />
                        </Grid>
                      </Grid>
                    </Box>

                    {/* CRITICAL Business Insights */}
                    {fileDetails.business_analysis?.api_endpoints?.length > 0 && (
                      <Box sx={{ mb: 2 }}>
                        <Typography variant="subtitle2" gutterBottom color="error.main" fontWeight="bold">
                          🚨 API Endpoints (User-Facing):
                        </Typography>
                        <List dense>
                          {fileDetails.business_analysis.api_endpoints.map((endpoint, idx) => (
                            <ListItem key={idx} sx={{ bgcolor: 'error.light', mb: 1, borderRadius: 1 }}>
                              <ListItemText 
                                primary={`${endpoint.method} ${endpoint.endpoint}`}
                                secondary={`Line ${endpoint.line} - ${endpoint.migration_priority}`}
                              />
                            </ListItem>
                          ))}
                        </List>
                      </Box>
                    )}

                    {fileDetails.business_analysis?.database_operations?.length > 0 && (
                      <Box sx={{ mb: 2 }}>
                        <Typography variant="subtitle2" gutterBottom color="warning.main" fontWeight="bold">
                          💾 Database Operations:
                        </Typography>
                        <List dense>
                          {fileDetails.business_analysis.database_operations.map((op, idx) => (
                            <ListItem key={idx} sx={{ bgcolor: 'warning.light', mb: 1, borderRadius: 1 }}>
                              <ListItemText 
                                primary={op.operation}
                                secondary={`Line ${op.line} - ${op.migration_priority}`}
                              />
                            </ListItem>
                          ))}
                        </List>
                      </Box>
                    )}

                    {fileDetails.business_analysis?.business_logic?.length > 0 && (
                      <Box sx={{ mb: 2 }}>
                        <Typography variant="subtitle2" gutterBottom color="secondary.main" fontWeight="bold">
                          🎯 Business Logic (Core Functionality):
                        </Typography>
                        <List dense>
                          {fileDetails.business_analysis.business_logic.map((logic, idx) => (
                            <ListItem key={idx} sx={{ bgcolor: 'secondary.light', mb: 1, borderRadius: 1 }}>
                              <ListItemText 
                                primary={logic.logic_type}
                                secondary={`Line ${logic.line} - ${logic.migration_priority}`}
                              />
                            </ListItem>
                          ))}
                        </List>
                      </Box>
                    )}

                    {fileDetails.business_analysis?.business_validation?.length > 0 && (
                      <Box sx={{ mb: 2 }}>
                        <Typography variant="subtitle2" gutterBottom color="info.main" fontWeight="bold">
                          ✅ Business Validation Rules:
                        </Typography>
                        <List dense>
                          {fileDetails.business_analysis.business_validation.map((validation, idx) => (
                            <ListItem key={idx} sx={{ bgcolor: 'info.light', mb: 1, borderRadius: 1 }}>
                              <ListItemText 
                                primary={validation.validation_type}
                                secondary={`Line ${validation.line} - ${validation.migration_priority}`}
                              />
                            </ListItem>
                          ))}
                        </List>
                      </Box>
                    )}

                    {fileDetails.business_analysis?.external_integrations?.length > 0 && (
                      <Box sx={{ mb: 2 }}>
                        <Typography variant="subtitle2" gutterBottom color="primary.main" fontWeight="bold">
                          🔗 External Integrations:
                        </Typography>
                        <List dense>
                          {fileDetails.business_analysis.external_integrations.map((integration, idx) => (
                            <ListItem key={idx} sx={{ bgcolor: 'primary.light', mb: 1, borderRadius: 1 }}>
                              <ListItemText 
                                primary={`${integration.service_type} → ${integration.target}`}
                                secondary={`Line ${integration.line} - ${integration.migration_priority}`}
                              />
                            </ListItem>
                          ))}
                        </List>
                      </Box>
                    )}

                    {/* Technical Context (Collapsed by default) */}
                    {fileDetails.technical_details && (
                      <Box sx={{ mt: 3 }}>
                        <Typography variant="caption" color="text.secondary">
                          Technical Context ({fileDetails.migration_insights?.technical_functions} functions, {fileDetails.migration_insights?.lines_of_code} lines)
                        </Typography>
                      </Box>
                    )}
                  </>
                )}
              </Box>
            )}
          </Box>
        )}
      </DialogContent>
    </Dialog>
  );

  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom>
        Dependency Graph
      </Typography>
      <Typography variant="body1" color="text.secondary" paragraph>
        Interactive visualization of dependencies and relationships in your repositories.
      </Typography>

      {(!isReady || healthLoading || healthError) && (
        <Alert severity={healthError ? 'error' : 'info'} sx={{ mb: 2 }}>
          {!isReady ? 'System is starting up. Graph features are disabled until ready.' :
           healthLoading ? 'Checking system readiness...' :
           `Health error: ${healthError}`}
        </Alert>
      )}

      {repositories.length === 0 ? (
        <Alert severity="info">
          No repositories indexed yet. Please index some repositories first.
        </Alert>
      ) : (
        <>
          {/* Controls */}
          <Paper sx={{ p: 3, mb: 3 }}>
            <Grid container spacing={2} alignItems="center">
              <Grid item xs={12} md={3}>
                <FormControl fullWidth disabled={!isReady}>
                  <InputLabel>Repository</InputLabel>
                  <Select
                    value={selectedRepo}
                    label="Repository"
                    onChange={(e) => setSelectedRepo(e.target.value)}
                  >
                    {repositories.map((repo, index) => (
                      <MenuItem key={index} value={repo.name || repo}>
                        {repo.name || repo}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>

              <Grid item xs={12} md={2}>
                <FormControl fullWidth>
                  <InputLabel>Layout</InputLabel>
                  <Select
                    value={layout}
                    label="Layout"
                    onChange={(e) => handleLayoutChange(e.target.value)}
                    disabled={!graphData || !isReady}
                  >
                    <MenuItem value="dagre">Hierarchical</MenuItem>
                    <MenuItem value="cose-bilkent">Force-Directed</MenuItem>
                    <MenuItem value="euler">Physics</MenuItem>
                  </Select>
                </FormControl>
              </Grid>

              <Grid item xs={12} md={2}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={showLabels}
                      onChange={handleToggleLabels}
                      disabled={!graphData || !isReady}
                    />
                  }
                  label="Show Labels"
                />
              </Grid>

              <Grid item xs={12} md={2}>
                <Typography variant="body2" gutterBottom>
                  Node Spacing
                </Typography>
                <Slider
                  value={nodeSpacing}
                  onChange={handleNodeSpacingChange}
                  min={50}
                  max={200}
                  disabled={!graphData || layout !== 'dagre' || !isReady}
                  size="small"
                />
              </Grid>

              <Grid item xs={12} md={3}>
                <Box display="flex" gap={1}>
                  <Tooltip title="Refresh">
                    <span>
                      <IconButton
                        onClick={() => loadGraphData(selectedRepo)}
                        disabled={!isReady || !selectedRepo || loading}
                        size="small"
                      >
                        <Refresh />
                      </IconButton>
                    </span>
                  </Tooltip>
                  <Tooltip title="Zoom In">
                    <span>
                      <IconButton
                        onClick={handleZoomIn}
                        disabled={!graphData || !isReady}
                        size="small"
                      >
                        <ZoomIn />
                      </IconButton>
                    </span>
                  </Tooltip>
                  <Tooltip title="Zoom Out">
                    <span>
                      <IconButton
                        onClick={handleZoomOut}
                        disabled={!graphData || !isReady}
                        size="small"
                      >
                        <ZoomOut />
                      </IconButton>
                    </span>
                  </Tooltip>
                  <Tooltip title="Fit to View">
                    <span>
                      <IconButton
                        onClick={handleFitToView}
                        disabled={!graphData || !isReady}
                        size="small"
                      >
                        <CenterFocusStrong />
                      </IconButton>
                    </span>
                  </Tooltip>
                  <Tooltip title="Export PNG">
                    <span>
                      <IconButton
                        onClick={handleExportGraph}
                        disabled={!graphData || !isReady}
                        size="small"
                      >
                        <Download />
                      </IconButton>
                    </span>
                  </Tooltip>
                </Box>
              </Grid>
            </Grid>
          </Paper>

          {/* Graph Visualization */}
          <Paper sx={{ position: 'relative' }}>
            {loading && (
              <Box 
                display="flex" 
                justifyContent="center" 
                alignItems="center" 
                position="absolute"
                top={0}
                left={0}
                right={0}
                bottom={0}
                bgcolor="rgba(255,255,255,0.8)"
                zIndex={10}
              >
                <CircularProgress />
              </Box>
            )}

            {error && (
              <Alert severity="error" sx={{ m: 2 }}>
                {error}
              </Alert>
            )}
            {!isReady && !loading && (
              <Alert severity="info" sx={{ m: 2 }}>
                Waiting for system readiness to load graph data...
              </Alert>
            )}

            <div
              ref={containerRef}
              style={{
                width: '100%',
                height: '600px',
                border: '1px solid #e0e0e0',
                borderRadius: '4px'
              }}
            />

            {(!selectedRepo || (!!error && error.includes('Index'))) && !loading && (
              <Box
                display="flex"
                justifyContent="center"
                alignItems="center"
                position="absolute"
                top={0}
                left={0}
                right={0}
                bottom={0}
              >
                <Typography color="text.secondary">
                  {selectedRepo
                    ? 'No graph data available. Index the repository to populate the knowledge graph, then refresh.'
                    : 'Select a repository to view its dependency graph'}
                </Typography>
              </Box>
            )}
          </Paper>

          {/* Graph Statistics */}
          {graphStats && graphData && (
            <Grid container spacing={2} sx={{ mt: 2 }}>
              <Grid item xs={12} md={3}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" color="primary">
                      {graphStats.neo4j?.total_files || 0}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Total Files
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
              <Grid item xs={12} md={3}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" color="secondary">
                      {graphStats.neo4j?.total_dependencies || 0}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Dependencies
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
              <Grid item xs={12} md={3}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" color="success.main">
                      {graphStats.neo4j?.total_repositories || 0}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Repositories
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
              <Grid item xs={12} md={3}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" color="warning.main">
                      {graphStats.chromadb?.total_chunks || 0}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Code Chunks
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
            </Grid>
          )}

          {/* Legend */}
          <Card sx={{ mt: 2 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Graph Legend
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={12} sm={6} md={2}>
                  <Box display="flex" alignItems="center" mb={1}>
                    <Box
                      sx={{
                        width: 16,
                        height: 16,
                        bgcolor: '#1976d2',
                        borderRadius: 1,
                        mr: 1
                      }}
                    />
                    <Typography variant="body2">Repository</Typography>
                  </Box>
                </Grid>
                <Grid item xs={12} sm={6} md={2}>
                  <Box display="flex" alignItems="center" mb={1}>
                    <Box
                      sx={{
                        width: 16,
                        height: 16,
                        bgcolor: '#ff9800',
                        borderRadius: '50%',
                        mr: 1
                      }}
                    />
                    <Typography variant="body2">Dependencies</Typography>
                  </Box>
                </Grid>
                <Grid item xs={12} sm={6} md={2}>
                  <Box display="flex" alignItems="center" mb={1}>
                    <Box
                      sx={{
                        width: 16,
                        height: 16,
                        bgcolor: '#4caf50',
                        mr: 1
                      }}
                    />
                    <Typography variant="body2">Packages</Typography>
                  </Box>
                </Grid>
                <Grid item xs={12} sm={6} md={2}>
                  <Box display="flex" alignItems="center" mb={1}>
                    <Box
                      sx={{
                        width: 16,
                        height: 16,
                        bgcolor: '#795548',
                        mr: 1
                      }}
                    />
                    <Typography variant="body2">Files</Typography>
                  </Box>
                </Grid>
                <Grid item xs={12} sm={6} md={2}>
                  <Box display="flex" alignItems="center" mb={1}>
                    <Box
                      sx={{
                        width: 16,
                        height: 16,
                        bgcolor: '#607d8b',
                        borderRadius: 0,
                        mr: 1
                      }}
                    />
                    <Typography variant="body2">Classes</Typography>
                  </Box>
                </Grid>
                <Grid item xs={12} sm={6} md={2}>
                  <Box display="flex" alignItems="center" mb={1}>
                    <Box
                      sx={{
                        width: 0,
                        height: 0,
                        borderLeft: '8px solid transparent',
                        borderRight: '8px solid transparent',
                        borderBottom: '16px solid #9c27b0',
                        mr: 1
                      }}
                    />
                    <Typography variant="body2">Config</Typography>
                  </Box>
                </Grid>
              </Grid>
              
              <Divider sx={{ my: 2 }} />
              
              <Typography variant="subtitle2" gutterBottom>
                Interactions:
              </Typography>
              <Typography variant="body2" color="text.secondary" paragraph>
                • Click nodes to view details • Hover to highlight connections • Use controls to adjust layout and zoom
              </Typography>
              <Typography variant="subtitle2" gutterBottom>
                Layouts:
              </Typography>
              <Typography variant="body2" color="text.secondary">
                • <strong>Hierarchical:</strong> Top-down dependency flow • <strong>Force-Directed:</strong> Natural clustering • <strong>Physics:</strong> Dynamic positioning
              </Typography>
            </CardContent>
          </Card>

          {/* Node Details Dialog */}
          <NodeDetailsDialog />
        </>
      )}
    </Box>
  );
}

export default DependencyGraph;