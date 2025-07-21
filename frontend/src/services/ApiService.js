import axios from 'axios';

// Configure axios defaults
const API_BASE_URL = process.env.REACT_APP_API_URL || '';
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000, // 60 seconds for long operations
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for debugging
api.interceptors.request.use(
  (config) => {
    console.log(`API Request: ${config.method?.toUpperCase()} ${config.url}`);
    return config;
  },
  (error) => {
    console.error('API Request Error:', error);
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    console.error('API Response Error:', error);
    
    // Handle different error types
    if (error.response) {
      // Server responded with error status
      const message = error.response.data?.detail || error.response.data?.error || error.message;
      throw new Error(`Server Error (${error.response.status}): ${message}`);
    } else if (error.request) {
      // Network error
      throw new Error('Network Error: Unable to connect to server. Please check if the backend is running.');
    } else {
      // Other error
      throw new Error(`Error: ${error.message}`);
    }
  }
);

export class ApiService {
  // Health and Status
  static async getHealth() {
    try {
      const response = await api.get('/health');
      return response.data;
    } catch (error) {
      return { status: 'unhealthy', error: error.message };
    }
  }

  static async getStatus() {
    const response = await api.get('/status');
    return response.data;
  }

  // Repository Management
  static async getRepositories() {
    const response = await api.get('/repositories');
    return response.data;
  }

  static async indexRepository(repoPath, repoName) {
    const response = await api.post('/index', {
      repo_path: repoPath,
      repo_name: repoName
    });
    return response.data;
  }

  static async deleteRepository(repoName) {
    const response = await api.delete(`/repositories/${repoName}`);
    return response.data;
  }

  static async getRepositoryStats(repoName) {
    const response = await api.get(`/repositories/${repoName}/stats`);
    return response.data;
  }

  // Search
  static async searchCode(query, options = {}) {
    const params = {
      q: query,
      limit: options.limit || 20,
      threshold: options.threshold || 0.7
    };
    const response = await api.get('/search', { params });
    return response.data;
  }

  static async searchLegacyPatterns(pattern, repository = null, limit = 20) {
    const params = { pattern, limit };
    if (repository) params.repository = repository;
    
    const response = await api.get('/search/legacy-patterns', { params });
    return response.data;
  }

  // AI Agent
  static async askAgent(question, repository = null) {
    const response = await api.post('/agent/ask', {
      question,
      repository
    });
    return response.data;
  }

  static async getAgentCapabilities() {
    const response = await api.get('/agent/capabilities');
    return response.data;
  }

  static async getAgentHealth() {
    const response = await api.get('/agent/health');
    return response.data;
  }

  // Struts Analysis
  static async analyzeStrutsRepository(repoPath, repoName) {
    const response = await api.post('/struts/analyze', {
      repo_path: repoPath,
      repo_name: repoName
    });
    return response.data;
  }

  static async getStrutsActions(repository = null) {
    const params = {};
    if (repository) params.repository = repository;
    
    const response = await api.get('/struts/actions', { params });
    return response.data;
  }

  static async getMigrationPlan(repository) {
    const response = await api.get(`/struts/migration-plan/${repository}`);
    return response.data;
  }

  // Neo4j Graph Queries
  static async getRepositoryGraph(repoName) {
    const response = await api.get(`/graph/repository/${repoName}`);
    return response.data;
  }

  static async getRepositoryGraphVisualization(repoName) {
    const response = await api.get(`/graph/repository/${repoName}/visualization`);
    return response.data;
  }

  static async executeGraphQuery(cypher, readOnly = true) {
    const response = await api.get('/graph/query', {
      params: { cypher, read_only: readOnly }
    });
    return response.data;
  }

  // Maven Dependencies
  static async getMavenDependencies(groupId, artifactId, version, options = {}) {
    const response = await api.get(`/maven/dependencies/${groupId}/${artifactId}/${version}`, {
      params: {
        transitive: options.transitive !== false,
        max_depth: options.maxDepth || 3
      }
    });
    return response.data;
  }

  static async getDependencyConflicts(repository = null) {
    const params = {};
    if (repository) params.repository = repository;
    
    const response = await api.get('/maven/conflicts', { params });
    return response.data;
  }

  // Utility methods
  static async ping() {
    try {
      const response = await api.get('/');
      return response.data;
    } catch (error) {
      throw new Error('Backend is not responding');
    }
  }

  // File system operations (for local development)
  static async browseDirectory(path) {
    // This would need a backend endpoint to list directories
    // For now, return mock data
    return {
      path,
      directories: ['src', 'test', 'docs'],
      files: ['pom.xml', 'README.md']
    };
  }

  // Batch operations
  static async indexMultipleRepositories(repositories, onProgress = null) {
    const results = [];
    
    for (let i = 0; i < repositories.length; i++) {
      const repo = repositories[i];
      
      try {
        if (onProgress) {
          onProgress({
            current: i + 1,
            total: repositories.length,
            repository: repo.name,
            status: 'indexing'
          });
        }
        
        const result = await this.indexRepository(repo.path, repo.name);
        results.push({ ...repo, result, success: true });
        
        if (onProgress) {
          onProgress({
            current: i + 1,
            total: repositories.length,
            repository: repo.name,
            status: 'completed'
          });
        }
        
      } catch (error) {
        results.push({ ...repo, error: error.message, success: false });
        
        if (onProgress) {
          onProgress({
            current: i + 1,
            total: repositories.length,
            repository: repo.name,
            status: 'failed',
            error: error.message
          });
        }
      }
    }
    
    return results;
  }
}

export default ApiService;