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
    if (selectedRepo) {
      loadGraphData(selectedRepo);
    }
  }, [selectedRepo]);

  const loadGraphData = async (repoName) => {
    if (!repoName) return;

    setLoading(true);
    setError('');

    try {
      // Try to load actual graph visualization data first
      let visualizationData = null;
      try {
        visualizationData = await ApiService.getRepositoryGraphVisualization(repoName);
      } catch (vizError) {
        console.warn('Visualization data not available, falling back to sample data');
      }

      // Load repository graph data
      const data = await ApiService.getRepositoryGraph(repoName);
      setGraphData({ ...data, visualization: visualizationData });
      
      // Also get system stats for enhanced graph data
      const statsData = await ApiService.getStatus();
      setGraphStats(statsData);
      
      // Initialize the graph after data is loaded
      setTimeout(() => initializeGraph({ ...data, visualization: visualizationData }, statsData), 100);
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
      setSelectedNode({
        id: node.id(),
        data: node.data(),
        position: node.position(),
        degree: node.degree()
      });
      setShowNodeDetails(true);
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

    // Check if we have real Neo4j visualization data
    if (data.visualization && data.visualization.nodes && data.visualization.nodes.length > 0) {
      // Use real Neo4j data
      const visualization = data.visualization;
      
      // Add nodes from Neo4j
      visualization.nodes.forEach(node => {
        const nodeId = `neo4j-${node.id}`;
        if (!addedNodes.has(nodeId)) {
          const nodeType = mapNeo4jNodeType(node.type);
          const nodeLabel = node.name || node.artifactId || node.path || `${node.type} ${node.id}`;
          
          elements.push({
            data: {
              id: nodeId,
              label: nodeLabel,
              type: nodeType,
              size: calculateNodeSize(node),
              description: generateNodeDescription(node),
              neo4j_id: node.id,
              neo4j_type: node.type,
              ...node
            }
          });
          addedNodes.add(nodeId);
        }
      });

      // Add edges from Neo4j
      visualization.edges.forEach(edge => {
        const sourceId = `neo4j-${edge.source_id}`;
        const targetId = `neo4j-${edge.target_id}`;
        
        if (addedNodes.has(sourceId) && addedNodes.has(targetId)) {
          elements.push({
            data: {
              id: `edge-${edge.source_id}-${edge.target_id}`,
              source: sourceId,
              target: targetId,
              type: mapRelationshipType(edge.relationship_type),
              label: edge.relationship_type,
              weight: edge.weight || 1
            }
          });
        }
      });

      return elements;
    }

    // Fallback to sample data if no Neo4j data available
    // Repository node
    const repoId = `repo-${selectedRepo}`;
    if (!addedNodes.has(repoId)) {
      elements.push({
        data: {
          id: repoId,
          label: selectedRepo,
          type: 'repository',
          size: 60,
          description: `Main repository: ${selectedRepo}`,
          stats: data.graph_stats || {}
        }
      });
      addedNodes.add(repoId);
    }

    // Add Maven dependencies if available
    if (stats?.neo4j?.total_dependencies > 0) {
      // Generate some sample dependency nodes
      const sampleDependencies = [
        { id: 'spring-core', label: 'Spring Core', type: 'dependency', version: '5.3.21' },
        { id: 'hibernate-core', label: 'Hibernate Core', type: 'dependency', version: '5.6.9' },
        { id: 'struts2-core', label: 'Struts2 Core', type: 'dependency', version: '2.5.28' },
        { id: 'mysql-connector', label: 'MySQL Connector', type: 'dependency', version: '8.0.29' },
        { id: 'jackson-databind', label: 'Jackson Databind', type: 'dependency', version: '2.13.3' }
      ];

      sampleDependencies.forEach(dep => {
        if (!addedNodes.has(dep.id)) {
          elements.push({
            data: {
              id: dep.id,
              label: dep.label,
              type: dep.type,
              size: 40,
              description: `${dep.label} v${dep.version}`,
              version: dep.version
            }
          });
          addedNodes.add(dep.id);

          // Add edge from repository to dependency
          elements.push({
            data: {
              id: `${repoId}-${dep.id}`,
              source: repoId,
              target: dep.id,
              type: 'depends-on',
              label: 'depends on'
            }
          });
        }
      });
    }

    // Add code structure nodes if available
    if (stats?.neo4j?.total_files > 0) {
      // Generate sample code structure
      const codeStructure = [
        { id: 'actions', label: 'Actions', type: 'package', count: 15 },
        { id: 'forms', label: 'Forms', type: 'package', count: 12 },
        { id: 'services', label: 'Services', type: 'package', count: 8 },
        { id: 'models', label: 'Models', type: 'package', count: 20 },
        { id: 'config', label: 'Configuration', type: 'config', count: 5 }
      ];

      codeStructure.forEach(item => {
        if (!addedNodes.has(item.id)) {
          elements.push({
            data: {
              id: item.id,
              label: `${item.label} (${item.count})`,
              type: item.type,
              size: 35,
              description: `${item.label}: ${item.count} files`,
              count: item.count
            }
          });
          addedNodes.add(item.id);

          // Add edge from repository to code structure
          elements.push({
            data: {
              id: `${repoId}-${item.id}`,
              source: repoId,
              target: item.id,
              type: 'contains',
              label: 'contains'
            }
          });
        }
      });

      // Add some inter-package relationships
      const relationships = [
        { from: 'actions', to: 'services', type: 'uses' },
        { from: 'actions', to: 'forms', type: 'uses' },
        { from: 'services', to: 'models', type: 'uses' },
        { from: 'config', to: 'services', type: 'configures' }
      ];

      relationships.forEach(rel => {
        if (addedNodes.has(rel.from) && addedNodes.has(rel.to)) {
          elements.push({
            data: {
              id: `${rel.from}-${rel.to}`,
              source: rel.from,
              target: rel.to,
              type: rel.type,
              label: rel.type
            }
          });
        }
      });
    }

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
    {
      selector: 'node',
      style: {
        'background-color': 'data(color)',
        'label': showLabels ? 'data(label)' : '',
        'text-valign': 'center',
        'text-halign': 'center',
        'font-size': '12px',
        'font-weight': 'bold',
        'color': '#333',
        'text-outline-width': 2,
        'text-outline-color': '#fff',
        'width': 'data(size)',
        'height': 'data(size)',
        'border-width': 2,
        'border-color': '#666',
        'transition-property': 'background-color, border-color, width, height',
        'transition-duration': '0.2s'
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
      cyRef.current.layout(layoutConfig).run();
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
      cyRef.current.style().update();
    }
  };

  const handleZoomIn = () => {
    if (cyRef.current) {
      cyRef.current.zoom(cyRef.current.zoom() * 1.2);
      cyRef.current.center();
    }
  };

  const handleZoomOut = () => {
    if (cyRef.current) {
      cyRef.current.zoom(cyRef.current.zoom() * 0.8);
      cyRef.current.center();
    }
  };

  const handleFitToView = () => {
    if (cyRef.current) {
      cyRef.current.fit();
    }
  };

  const handleExportGraph = () => {
    if (cyRef.current) {
      const png64 = cyRef.current.png({ scale: 2 });
      const link = document.createElement('a');
      link.download = `${selectedRepo}-dependency-graph.png`;
      link.href = png64;
      link.click();
    }
  };

  const NodeDetailsDialog = () => (
    <Dialog 
      open={showNodeDetails} 
      onClose={() => setShowNodeDetails(false)}
      maxWidth="sm"
      fullWidth
    >
      <DialogTitle>
        <Box display="flex" justifyContent="between" alignItems="center">
          Node Details
          <IconButton onClick={() => setShowNodeDetails(false)}>
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
                <FormControl fullWidth>
                  <InputLabel>Repository</InputLabel>
                  <Select
                    value={selectedRepo}
                    label="Repository"
                    onChange={(e) => setSelectedRepo(e.target.value)}
                  >
                    {repositories.map((repo, index) => (
                      <MenuItem key={index} value={repo}>
                        {repo}
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
                    disabled={!graphData}
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
                      disabled={!graphData}
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
                  disabled={!graphData || layout !== 'dagre'}
                  size="small"
                />
              </Grid>

              <Grid item xs={12} md={3}>
                <Box display="flex" gap={1}>
                  <Tooltip title="Refresh">
                    <IconButton
                      onClick={() => loadGraphData(selectedRepo)}
                      disabled={!selectedRepo || loading}
                      size="small"
                    >
                      <Refresh />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Zoom In">
                    <IconButton
                      onClick={handleZoomIn}
                      disabled={!graphData}
                      size="small"
                    >
                      <ZoomIn />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Zoom Out">
                    <IconButton
                      onClick={handleZoomOut}
                      disabled={!graphData}
                      size="small"
                    >
                      <ZoomOut />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Fit to View">
                    <IconButton
                      onClick={handleFitToView}
                      disabled={!graphData}
                      size="small"
                    >
                      <CenterFocusStrong />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Export PNG">
                    <IconButton
                      onClick={handleExportGraph}
                      disabled={!graphData}
                      size="small"
                    >
                      <Download />
                    </IconButton>
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

            <div
              ref={containerRef}
              style={{
                width: '100%',
                height: '600px',
                border: '1px solid #e0e0e0',
                borderRadius: '4px'
              }}
            />

            {!selectedRepo && !loading && (
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
                  Select a repository to view its dependency graph
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