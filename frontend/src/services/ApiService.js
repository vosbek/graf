import axios from 'axios';

 // Configure axios defaults
 const API_BASE_URL = process.env.REACT_APP_API_URL || '';
 // Emit targeted diagnostics to validate frontend->backend connectivity assumptions
 if (typeof window !== 'undefined') {
   const debugFlag = String(process.env.REACT_APP_API_DEBUG || '').toLowerCase() === 'true';
   if (debugFlag) {
     // eslint-disable-next-line no-console
     console.log('[ApiService] init', {
       API_BASE_URL: API_BASE_URL || '(empty -> using relative URLs with dev proxy)',
       location: window.location.href,
       proxyHint: 'Dev server proxy configured in package.json -> http://localhost:8080'
     });
   }
 }
 const api = axios.create({
   baseURL: API_BASE_URL,
   timeout: 60000, // 60 seconds for long operations
   headers: {
     'Content-Type': 'application/json',
   },
 });

// Request interceptor for debugging (toggle via REACT_APP_API_DEBUG=true)
const DEBUG = String(process.env.REACT_APP_API_DEBUG || '').toLowerCase() === 'true';
api.interceptors.request.use(
  (config) => {
    if (DEBUG) {
      // eslint-disable-next-line no-console
      console.log(`API Request: ${config.method?.toUpperCase()} ${config.baseURL || ''}${config.url}`, {
        params: config.params,
        data: config.data,
      });
    }
    return config;
  },
  (error) => {
    if (DEBUG) {
      // eslint-disable-next-line no-console
      console.error('API Request Error:', error);
    }
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    if (DEBUG) {
      console.error('API Response Error:', error);
    }
    
    // Helper function to parse API errors properly
    const parseApiError = (err) => {
      const res = err.response;
      if (!res) return err.message || "Network Error";
      
      // Try to extract meaningful error message
      const detail = res.data?.detail ?? res.data?.error ?? res.data?.message;
      if (detail && typeof detail === 'string') {
        return detail;
      }
      
      // Handle array of error details (validation errors)
      if (Array.isArray(detail)) {
        return detail.map(d => d.msg || d.message || JSON.stringify(d)).join(', ');
      }
      
      // Fall back to JSON stringify if detail is an object
      if (detail && typeof detail === 'object') {
        return JSON.stringify(detail);
      }
      
      // Last resort
      try {
        return typeof res.data === 'string' ? res.data : JSON.stringify(res.data);
      } catch {
        return err.message || 'Unknown error';
      }
    };
    
    // Handle different error types
    if (error.response) {
      // Server responded with error status
      const status = error.response.status;
      const message = parseApiError(error);
      // Normalize common statuses with concise messages
      if (status === 422) {
        throw new Error(`Validation Error (422): ${message}`);
      }
      if (status === 404) {
        throw new Error(`Not Found (404): ${message}`);
      }
      if (status === 400) {
        throw new Error(`Bad Request (400): ${message}`);
      }
      throw new Error(`Server Error (${status}): ${message}`);
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
  // Health and Status (canonical)
  static async getSystemStatus() {
    try {
      const response = await api.get('/api/v1/health/ready');
      if (String(process.env.REACT_APP_API_DEBUG || '').toLowerCase() === 'true') {
        // eslint-disable-next-line no-console
        console.log('[ApiService] readiness payload', response?.data);
      }
      return response.data;
    } catch (error) {
      if (String(process.env.REACT_APP_API_DEBUG || '').toLowerCase() === 'true') {
        // eslint-disable-next-line no-console
        console.error('[ApiService] readiness fetch failed', error?.message || error);
      }
      return { status: 'error', error: error.message };
    }
  }

  // Deprecated: keep for backward compatibility. Prefer getSystemStatus().
  static async getHealth() {
    return await this.getSystemStatus();
  }

  // Deprecated alias: Prefer getSystemStatus() going forward.
  static async getStatus() {
    return await this.getSystemStatus();
  }

  // Repository Management
  static async getRepositories() {
    // Avoid hard dependency during status checks; keep method for explicit use
    const response = await api.get('/api/v1/index/repositories');
    return response.data;
  }

  static async indexRepository(repoData) {
    // Support both old (path, name) and new (object) formats for backwards compatibility
    let requestData;
    if (typeof repoData === 'string') {
      // Old format: indexRepository(repoPath, repoName)
      const repoName = arguments[1];
      requestData = {
        name: repoName,
        url: repoData,
        branch: 'main',
        priority: 'medium',
        maven_enabled: true,
        is_golden_repo: false
      };
    } else {
      // New format: indexRepository({ name, url, branch, ... })
      requestData = repoData;
    }
    
    const response = await api.post('/api/v1/index/repository', requestData);
    return response.data;
  }

  static async indexLocalRepository(localRepoData) {
    const response = await api.post('/api/v1/index/repository/local', localRepoData);
    return response.data;
  }

  static async deleteRepository(repoName) {
    const response = await api.delete(`/api/v1/index/repository/${repoName}`);
    return response.data;
  }

  static async getRepositoryStats(repoName) {
    const response = await api.get(`/api/v1/index/repositories/${repoName}`);
    return response.data;
  }

  static async getIndexingStatus(taskId = null) {
    if (taskId) {
      // Get status for specific task
      const response = await api.get(`/api/v1/index/status/${taskId}`);
      return response.data;
    } else {
      // Get status for all tasks
      const response = await api.get('/api/v1/index/status');
      return response.data;
    }
  }

  // Search
  static async searchCode(query, options = {}) {
    const searchRequest = {
      query: query,
      limit: options.limit || 20,
      min_score: typeof options.threshold === 'number' ? options.threshold : 0.7,
      include_metadata: true
    };
    const response = await api.post('/api/v1/query/semantic', searchRequest);
    return response.data;
  }

  static async searchLegacyPatterns(pattern, repository = null, limit = 20) {
    // Legacy patterns search - use semantic search with pattern matching
    const searchRequest = {
      query: pattern,
      limit: limit,
      repository_filter: repository || undefined, // backend expects string filter
      min_score: 0.6,
      include_metadata: true
    };
    const response = await api.post('/api/v1/query/semantic', searchRequest);
    return response.data;
  }

  // AI Agent
  static async askAgent(question, repository = null, options = {}) {
    // POST to /api/v1/chat/ask
    const payload = {
      question: question,
      repository_scope: repository ? [repository] : options.repository_scope || null,
      top_k: typeof options.top_k === 'number' ? Math.min(Math.max(options.top_k, 1), 20) : 8,
      min_score: typeof options.min_score === 'number' ? Math.min(Math.max(options.min_score, 0.0), 1.0) : 0.0,
      mode: options.mode === 'hybrid' ? 'hybrid' : 'semantic',
    };

    const response = await api.post('/api/v1/chat/ask', payload);
    // Expected shape:
    // {
    //   answer: string,
    //   citations: [{ chunk_id, repository, file_path, score }],
    //   diagnostics: { retrieval, graph, llm }
    // }
    return response.data;
  }

  static async getAgentCapabilities() {
    // Agent capabilities not yet implemented
    return {
      capabilities: [],
      status: "not_implemented",
      message: "AI Agent capabilities are not yet available"
    };
  }

  static async getAgentHealth() {
    // Agent health is same as general health for now
    return await this.getHealth();
  }

  // Struts Analysis
  static async analyzeStrutsRepository(repoPath, repoName) {
    // Struts analysis not yet implemented in backend
    return {
      status: "not_implemented",
      message: "Struts analysis is not yet available",
      repository: repoName
    };
  }

  static async getStrutsActions(repository = null) {
    // Struts actions not yet implemented
    return {
      actions: [],
      status: "not_implemented",
      message: "Struts actions analysis is not yet available"
    };
  }

  static async getMigrationPlan(repository) {
    // Back-compat single-repo helper: call canonical multi-repo GET and project if needed
    if (!repository) {
      throw new Error('Repository is required');
    }
    const plan = await this.getMultiRepoMigrationPlan([typeof repository === 'string' ? repository : repository.name]);
    // If the UI still expects the legacy single-repo shape, project minimal fields
    // analysis_summary.business_logic_components -> summary.totals.services (fallback to actions+services)
    // analysis_summary.data_models_found -> summary.totals.data_models
    // graphql_suggestions.recommended_types -> graphql.recommended_types
    // migration_steps -> roadmap.steps
    const totals = plan?.summary?.totals || {};
    const businessLogic = (totals.services ?? 0) + (totals.actions ?? 0);
    return {
      analysis_summary: {
        business_logic_components: businessLogic,
        data_models_found: totals.data_models ?? 0,
      },
      graphql_suggestions: {
        recommended_types: plan?.graphql?.recommended_types || [],
      },
      migration_steps: plan?.roadmap?.steps || [],
      // Also return the full canonical plan for upgraded UIs
      _canonical: plan,
    };
  }

  // Neo4j Graph Queries
  static async getRepositoryGraph(repoName) {
    // Use graph query to get repository data
    const cypher = `MATCH (r:Repository {name: $repoName})-[:CONTAINS]->(c:Chunk) RETURN r, c LIMIT 100`;
    return await this.executeGraphQuery(cypher, { repoName });
  }

  static async getRepositoryGraphVisualization(repoName, options = {}) {
    if (!repoName) {
      throw new Error('Repository name is required');
    }
    // Send params explicitly (not serialized into URL) to avoid browser/proxy encoding quirks
    const params = {
      repository: repoName,
      depth: Number.isFinite(options.depth) ? options.depth : 2,
      limit_nodes: Number.isFinite(options.limitNodes) ? options.limitNodes : 300,
      limit_edges: Number.isFinite(options.limitEdges) ? options.limitEdges : 800,
      trace: !!options.trace
    };
    const response = await api.get('/api/v1/graph/visualization', { params });
    // Expected: { nodes: [{id,type,name,path,size,metadata}], edges: [{source,target,relationship_type,weight,metadata}], diagnostics? }
    return response.data;
  }

  static async executeGraphQuery(cypher, parameters = {}) {
    if (!cypher || !String(cypher).trim()) {
      throw new Error('Invalid graph query: cypher must be a non-empty string');
    }
    if (parameters == null || typeof parameters !== 'object' || Array.isArray(parameters)) {
      throw new Error('Invalid graph parameters: expected a plain object of key/value pairs');
    }
    try {
      const response = await api.post('/api/v1/query/graph', {
        cypher: String(cypher),
        parameters: parameters,
        read_only: true
      });
      return response.data;
    } catch (e) {
      // The interceptor throws Error(message); add context for graph queries
      const msg = e?.message || 'Graph query failed';
      throw new Error(`Graph query failed: ${msg}`);
    }
  }

  // File Analysis
  static async analyzeFile(repoName, filePath) {
    // File analysis - use semantic search to find file content
    const searchRequest = {
      query: `file:${filePath}`,
      repository_filter: [repoName],
      limit: 1,
      include_metadata: true
    };
    const response = await api.post('/api/v1/query/semantic', searchRequest);
    const data = response.data || {};
    // Normalize to structure expected by UI panels (defensive defaults)
    return {
      migration_insights: {
        complexity_score: data?.migration_insights?.complexity_score || 'No assessment available',
        api_endpoints_found: data?.migration_insights?.api_endpoints_found ?? 0,
        database_operations: data?.migration_insights?.database_operations ?? 0,
        critical_business_functions: data?.migration_insights?.critical_business_functions ?? 0,
        external_integrations: data?.migration_insights?.external_integrations ?? 0,
        technical_functions: data?.migration_insights?.technical_functions ?? 0,
        lines_of_code: data?.migration_insights?.lines_of_code ?? 0
      },
      business_analysis: {
        api_endpoints: Array.isArray(data?.business_analysis?.api_endpoints) ? data.business_analysis.api_endpoints : [],
        database_operations: Array.isArray(data?.business_analysis?.database_operations) ? data.business_analysis.database_operations : [],
        business_logic: Array.isArray(data?.business_analysis?.business_logic) ? data.business_analysis.business_logic : [],
        business_validation: Array.isArray(data?.business_analysis?.business_validation) ? data.business_analysis.business_validation : [],
        external_integrations: Array.isArray(data?.business_analysis?.external_integrations) ? data.business_analysis.external_integrations : []
      },
      technical_details: data?.technical_details || null
    };
  }

  // Maven Dependencies
  static async getMavenDependencies(groupId, artifactId, version, options = {}) {
    // Use transitive dependencies endpoint
    const artifactCoordinates = `${groupId}:${artifactId}:${version}`;
    const response = await api.get(`/api/v1/query/dependencies/transitive/${artifactCoordinates}`, {
      params: {
        max_depth: options.maxDepth || 3
      }
    });
    return response.data;
  }

  static async getDependencyConflicts(repository = null) {
    const response = await api.get('/api/v1/query/dependencies/conflicts', {
      params: repository ? { repository } : {}
    });
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

  // Multi-repository analysis
  static async analyzeMultipleRepositories(analysisRequest) {
    const response = await api.post('/api/v1/query/multi-repo/analyze', analysisRequest);
    return response.data;
  }


  static async getAvailableRepositories(filters = {}) {
    const params = {};
    if (filters.businessDomain) params.business_domain = filters.businessDomain;
    if (filters.framework) params.framework = filters.framework;
    if (filters.teamOwner) params.team_owner = filters.teamOwner;

    const response = await api.get('/api/v1/query/multi-repo/repositories', { params });
    return response.data;
  }

 static async getBusinessFlowsForRepositories(repositorySelection) {
   const response = await api.post('/api/v1/query/multi-repo/business-flows', repositorySelection);
   return response.data;
 }

  static async getCrossRepositoryDependencies(repositorySelection) {
    const response = await api.post('/api/v1/query/multi-repo/dependencies/cross-repo', repositorySelection);
    return response.data;
  }

 static async analyzeMigrationImpact(repositorySelection) {
   const response = await api.post('/api/v1/query/multi-repo/migration-impact', repositorySelection);
   return response.data;
 }

 // NEW: Multi-repo canonical migration plan
 static async getMultiRepoMigrationPlan(repositories) {
   if (!repositories || !Array.isArray(repositories) || repositories.length === 0) {
     throw new Error('getMultiRepoMigrationPlan requires a non-empty array of repository names');
   }
   const params = new URLSearchParams();
   // encode as CSV for GET endpoint
   params.set('repositories', repositories.join(','));
   const response = await api.get(`/api/v1/migration-plan?${params.toString()}`);
   return response.data; // canonical schema
 }

 // Helper: project canonical plan into legacy single-repo shape for current UI chips (optional)
 static projectCanonicalToLegacy(plan) {
   if (!plan) return null;
   const summary = plan.summary || {};
   const totals = summary.totals || {};
   const graphql = plan.graphql || {};
   const roadmap = plan.roadmap || {};

   return {
     analysis_summary: {
       business_logic_components: (totals.services || 0), // or totals.actions + totals.services
       data_models_found: (totals.data_models || 0),
     },
     graphql_suggestions: {
       recommended_types: graphql.recommended_types || [],
     },
     migration_steps: roadmap.steps || [],
   };
 }

  static async getIntegrationPoints(repositoryNames) {
    const params = { repository_names: repositoryNames };
    const response = await api.get('/api/v1/query/multi-repo/integration-points', { params });
    return response.data;
  }

  // Diagnostic and Troubleshooting
  static async getSystemDiagnostics(includeHistory = false, timeout = 30) {
    // Deprecated endpoint removed on server; provide graceful fallback to health/ready
    try {
      const ready = await api.get('/api/v1/health/ready', {
        params: { timeout }
      });
      return {
        status: ready.data?.status || 'unknown',
        source: 'health_ready_fallback',
        checks: ready.data?.checks || {},
        timestamp: ready.data?.timestamp || Date.now()/1000
      };
    } catch (e) {
      return {
        status: 'error',
        source: 'health_ready_fallback',
        error: e?.message || String(e)
      };
    }
  }

  static async getCurrentIssues(severity = null, component = null) {
    const params = new URLSearchParams();
    if (severity) params.set('severity', severity);
    if (component) params.set('component', component);
    
    const response = await api.get(`/api/v1/diagnostics/issues?${params.toString()}`);
    return response.data;
  }

  static async getTroubleshootingGuide(issueId) {
    const response = await api.get(`/api/v1/diagnostics/troubleshooting/${issueId}`);
    return response.data;
  }

  static async getHealthReport(format = 'json') {
    const params = new URLSearchParams({ format });
    const response = await api.get(`/api/v1/diagnostics/health-report?${params.toString()}`);
    return response.data;
  }

  static async getPerformanceHistory() {
    const response = await api.get('/api/v1/diagnostics/performance-history');
    return response.data;
  }

  static async getAutoFixSuggestions() {
    const response = await api.get('/api/v1/diagnostics/auto-fixes');
    return response.data;
  }

  static async getComponentStatus(componentName) {
    const response = await api.get(`/api/v1/diagnostics/component-status/${componentName}`);
    return response.data;
  }

  static async getSystemRecommendations() {
    const response = await api.get('/api/v1/diagnostics/recommendations');
    return response.data;
  }

  static async exportDiagnosticData(format = 'json') {
    const response = await api.get(`/api/v1/diagnostics/health-report?format=${format}`);
    
    if (format === 'text') {
      // Create downloadable file
      const blob = new Blob([response.data], { type: 'text/plain' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `system_diagnostics_${new Date().toISOString().split('T')[0]}.txt`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      return { success: true, message: 'Diagnostic report downloaded' };
    }
    
    return response.data;
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