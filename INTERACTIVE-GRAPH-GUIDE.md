# 🎯 Interactive Dependency Graph Guide

## Overview

The Interactive Dependency Graph provides a comprehensive visual representation of your legacy application's architecture, dependencies, and relationships. Built with Cytoscape.js, it offers multiple layout algorithms and real-time interaction capabilities.

## Features

### 🎨 **Multi-Layout Support**
- **Hierarchical (Dagre)**: Top-down dependency flow, ideal for understanding architecture layers
- **Force-Directed (COSE-Bilkent)**: Natural clustering based on relationships, shows communities  
- **Physics (Euler)**: Dynamic positioning with physics simulation, reveals natural groupings

### 🔍 **Interactive Exploration**
- **Click nodes** to view detailed information
- **Hover nodes** to highlight connected components
- **Zoom and pan** for detailed exploration
- **Export graphs** as high-resolution PNG images

### 🎛️ **Customizable Views**
- Toggle node labels on/off
- Adjust node spacing (hierarchical layout)
- Real-time layout switching
- Fit-to-view and zoom controls

## Node Types & Meanings

| Visual | Type | Description | Use Case |
|--------|------|-------------|----------|
| 🔷 Blue Rectangle | Repository | Main codebase container | Starting point for analysis |
| 🟠 Orange Circle | Dependencies | External libraries/artifacts | Identify external dependencies |
| 🟢 Green Rectangle | Packages | Code organization units | Understand modular structure |
| 🟤 Brown Rectangle | Files | Individual code files | Trace specific implementations |
| ⚫ Gray Hexagon | Classes | Object-oriented components | Identify key business objects |
| 🔺 Purple Triangle | Configuration | Settings and config files | Understand system configuration |

## Relationship Types

| Visual | Type | Meaning | Example |
|--------|------|---------|---------|
| 🔴 Red Dashed | Depends On | External dependency | Repository → Maven artifact |
| 🔵 Blue Solid | Uses | Internal usage | Package → Package |
| 🟣 Purple Dotted | Configures | Configuration relationship | Config → Service |
| 🟤 Brown Solid | Imports | Code imports | Class → Class |
| 🔴 Red Dashed | Calls | Method/function calls | Class → Class |
| 🟢 Green Diamond | Extends | Inheritance | Class → Parent Class |
| 🔵 Cyan Dotted Diamond | Implements | Interface implementation | Class → Interface |

## Using the Graph

### 🚀 **Getting Started**
1. **Select Repository**: Choose from your indexed repositories
2. **Pick Layout**: Start with "Hierarchical" for clear architecture view
3. **Explore**: Click nodes to see details, hover to highlight connections
4. **Adjust**: Use layout controls to find the best view for your analysis

### 🔄 **Layout Recommendations**

**For Architecture Understanding:**
- Use **Hierarchical** layout
- Enable labels
- Adjust spacing for clarity
- Look for top-level dependencies flowing down

**For Relationship Analysis:**
- Use **Force-Directed** layout  
- Disable labels initially for cleaner view
- Look for natural clusters and communities
- Click nodes to understand specific relationships

**For Dynamic Exploration:**
- Use **Physics** layout
- Watch components settle into natural positions
- Identify highly connected nodes (hubs)
- Explore outliers and isolated components

### 📊 **Analysis Patterns**

**Dependency Hotspots:**
- Nodes with many incoming connections = widely used components
- Nodes with many outgoing connections = potential refactoring candidates
- Isolated nodes = potential technical debt or unused code

**Architectural Layers:**
- Hierarchical view shows clear separation of concerns
- Repository → Package → File → Class progression
- Configuration nodes typically at edges

**Migration Planning:**
- External dependencies (orange) show what needs compatibility analysis
- Package relationships show modular boundaries
- File-level connections show refactoring complexity

## Data Sources

### 🏗️ **Neo4j Integration**
When connected to populated Neo4j database:
- Real node and relationship data from your codebase
- Actual Maven dependencies and versions
- True file structure and code relationships
- Dynamic queries based on repository selection

### 📋 **Sample Data Mode**
When Neo4j data unavailable:
- Representative sample structure
- Common Struts application patterns  
- Typical Java enterprise dependencies
- Demonstration of visualization capabilities

## Controls Reference

### 🎮 **Graph Controls**
| Control | Action | Shortcut |
|---------|--------|----------|
| Zoom In | Increase magnification | Mouse wheel up |
| Zoom Out | Decrease magnification | Mouse wheel down |
| Pan | Move view around | Click + drag empty space |
| Fit to View | Show entire graph | Fit button |
| Export | Save as PNG | Download button |

### ⚙️ **Layout Settings**
- **Repository Dropdown**: Select which repository to visualize
- **Layout Dropdown**: Choose visualization algorithm
- **Show Labels Toggle**: Display/hide node text
- **Node Spacing Slider**: Adjust spacing in hierarchical layout (only)

## Troubleshooting

### 🔧 **Common Issues**

**Graph Not Loading:**
- Check that repository is properly indexed
- Verify backend connectivity
- Look for errors in browser developer console

**Empty or Sparse Graph:**
- Repository may have limited indexing data
- Try different repository selection
- Check indexing was completed successfully

**Performance Issues:**
- Large repositories may take time to render
- Try disabling labels for better performance
- Use hierarchical layout for faster rendering

**Layout Problems:**
- Different layouts work better for different graph types
- Try multiple layouts to find best visualization
- Adjust node spacing if nodes are too crowded

### 🛠️ **Optimization Tips**

**For Large Codebases:**
1. Start with hierarchical layout
2. Disable labels initially
3. Use zoom controls to focus on areas of interest
4. Export specific sections for detailed analysis

**For Complex Dependencies:**
1. Use force-directed layout to identify clusters
2. Click high-degree nodes to understand their role
3. Look for unexpected connections across packages
4. Export findings for team discussion

## Integration with Other Features

### 🔗 **Workflow Integration**
- Use graph to identify components for **AI Chat** queries
- Export node information to guide **Search Interface** exploration  
- Graph insights inform **Migration Planner** recommendations
- File nodes link to **Repository Browser** for code examination

### 📈 **Business Value**
- **Visual Architecture Documentation**: Replace outdated diagrams
- **Dependency Risk Assessment**: Identify critical external dependencies
- **Migration Planning**: Understand component boundaries and relationships
- **Team Communication**: Shared visual language for discussing architecture

## Best Practices

### 🎯 **Effective Analysis**
1. **Start High-Level**: Begin with repository-level view
2. **Drill Down**: Click interesting nodes for details
3. **Cross-Reference**: Use multiple layouts for different perspectives
4. **Document Findings**: Export graphs with annotations
5. **Share Results**: Use exports in team meetings and documentation

### ⚡ **Performance Tips**
- Close node details dialog when exploring
- Use layout controls to optimize for your analysis goal
- Export sections rather than trying to view entire large graphs
- Refresh graph data when repository indexing updates

---

**The Interactive Dependency Graph transforms complex legacy architectures into understandable visual representations, making architecture analysis accessible to both technical and business stakeholders.**