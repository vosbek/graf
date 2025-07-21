# Codebase RAG Frontend

A React-based web interface for the Codebase RAG MVP that provides visual access to legacy application analysis capabilities.

## Features

- **Dashboard**: Overview of indexed repositories and system status
- **Repository Indexer**: Interface to index local Struts applications
- **Search Interface**: Semantic search across indexed code  
- **AI Chat**: Natural language queries about your codebase
- **Dependency Graph**: Visual representation of relationships (planned)
- **Migration Planner**: GraphQL migration recommendations

## Quick Start

### Prerequisites
- Node.js 14+ 
- npm or yarn
- Backend MVP running on localhost:8080

### Installation

```bash
# Install dependencies
npm install

# Start development server
npm start
```

The application will open at http://localhost:3000 and proxy API requests to the backend at http://localhost:8080.

### Building for Production

```bash
# Create production build
npm run build

# Files will be in the 'build' directory
# The FastAPI backend automatically serves these files when available
```

## Usage

1. **Start the Backend**: Ensure the MVP backend is running (`./start-mvp-simple.sh`)
2. **Index Repositories**: Use the Repository Indexer to add your Struts applications
3. **Search & Explore**: Use the Search interface or AI Chat to analyze your code
4. **Plan Migration**: Generate GraphQL migration recommendations

## Architecture

- **React 18** with functional components and hooks
- **Material-UI** for consistent design
- **Axios** for API communication with FastAPI backend
- **React Router** for navigation
- **Responsive design** for desktop and tablet usage

## API Integration

The frontend communicates with the FastAPI backend through:

- Repository indexing (`POST /index`)
- Semantic search (`GET /search`) 
- AI agent queries (`POST /agent/ask`)
- System status (`GET /health`, `/status`)
- Struts analysis (`GET /struts/*`)

## Development

### File Structure
```
src/
├── components/         # React components
├── services/          # API service layer  
├── App.js             # Main application
└── index.js           # Entry point
```

### Adding New Features
1. Create component in `src/components/`
2. Add API methods to `src/services/ApiService.js`
3. Add route to `App.js` navigation
4. Update this README

## Deployment

The frontend is designed to be served directly by the FastAPI backend. When you build the React app, the backend automatically serves the static files.

For standalone deployment, build the React app and serve the `build` directory with any static file server.