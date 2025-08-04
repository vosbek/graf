import React from 'react';
import {
  Box, Typography, Alert, Accordion, AccordionSummary, AccordionDetails,
  List, ListItem, ListItemText, ListItemIcon, Chip, Link
} from '@mui/material';
import {
  ExpandMore, Error, Warning, Info, CheckCircle, Code, Storage,
  CloudSync, Analytics, Wifi, Security, Settings
} from '@mui/icons-material';

const TROUBLESHOOTING_GUIDES = {
  connection_timeout: {
    title: 'Connection Timeout',
    icon: <Wifi color="error" />,
    severity: 'error',
    description: 'The system failed to connect to the repository or database within the timeout period.',
    causes: [
      'Network connectivity issues',
      'Repository server is down or slow',
      'Database connection pool exhausted',
      'Firewall blocking connections'
    ],
    solutions: [
      'Check your internet connection',
      'Verify the repository URL is accessible',
      'Try again in a few minutes',
      'Contact your network administrator if the issue persists'
    ]
  },
  
  authentication_failed: {
    title: 'Authentication Failed',
    icon: <Security color="error" />,
    severity: 'error',
    description: 'Failed to authenticate with the repository or required services.',
    causes: [
      'Invalid or expired credentials',
      'Repository requires authentication',
      'SSH key not configured',
      'Token permissions insufficient'
    ],
    solutions: [
      'Verify your repository credentials',
      'Check if the repository is public or requires authentication',
      'Update your access tokens or SSH keys',
      'Ensure your account has read access to the repository'
    ]
  },

  repository_not_found: {
    title: 'Repository Not Found',
    icon: <Error color="error" />,
    severity: 'error',
    description: 'The specified repository could not be found or accessed.',
    causes: [
      'Repository URL is incorrect',
      'Repository has been deleted or moved',
      'Branch name is incorrect',
      'Access permissions denied'
    ],
    solutions: [
      'Double-check the repository URL',
      'Verify the repository exists and is accessible',
      'Check if the branch name is correct (default: main)',
      'Ensure you have access to the repository'
    ]
  },

  parsing_error: {
    title: 'File Parsing Error',
    icon: <Code color="warning" />,
    severity: 'warning',
    description: 'Some files could not be parsed or processed correctly.',
    causes: [
      'Unsupported file formats',
      'Corrupted or binary files',
      'Very large files exceeding limits',
      'Encoding issues'
    ],
    solutions: [
      'Check if the files are in supported formats (Java, JSP, XML, etc.)',
      'Verify files are not corrupted',
      'Consider excluding very large files',
      'Ensure files use standard text encoding (UTF-8)'
    ]
  },

  embedding_generation_failed: {
    title: 'Embedding Generation Failed',
    icon: <Storage color="error" />,
    severity: 'error',
    description: 'Failed to generate embeddings for code chunks using CodeBERT.',
    causes: [
      'CodeBERT model not loaded',
      'Insufficient memory for embedding generation',
      'Code chunks too large or malformed',
      'Embedding service unavailable'
    ],
    solutions: [
      'Restart the system to reload the CodeBERT model',
      'Check system memory usage',
      'Try processing smaller repositories first',
      'Contact support if the embedding service is down'
    ]
  },

  storage_error: {
    title: 'Storage Error',
    icon: <Storage color="error" />,
    severity: 'error',
    description: 'Failed to store processed data in ChromaDB or Neo4j.',
    causes: [
      'Database connection lost',
      'Insufficient disk space',
      'Database permissions issues',
      'Data validation failures'
    ],
    solutions: [
      'Check database connectivity',
      'Verify sufficient disk space is available',
      'Restart database services if needed',
      'Check database logs for specific errors'
    ]
  },

  memory_exhausted: {
    title: 'Memory Exhausted',
    icon: <Warning color="warning" />,
    severity: 'warning',
    description: 'The system ran out of memory during processing.',
    causes: [
      'Repository is very large',
      'Too many concurrent indexing operations',
      'Memory leak in processing',
      'Insufficient system memory'
    ],
    solutions: [
      'Try processing smaller repositories',
      'Wait for other indexing operations to complete',
      'Restart the system to free memory',
      'Consider increasing system memory'
    ]
  },

  validation_failed: {
    title: 'Validation Failed',
    icon: <CheckCircle color="warning" />,
    severity: 'warning',
    description: 'Post-processing validation detected inconsistencies in the indexed data.',
    causes: [
      'Data corruption during processing',
      'Incomplete indexing operation',
      'Database synchronization issues',
      'Concurrent modifications'
    ],
    solutions: [
      'Re-run the indexing operation',
      'Check for any concurrent operations',
      'Verify database integrity',
      'Contact support if validation continues to fail'
    ]
  }
};

const GENERAL_TIPS = [
  {
    title: 'Repository Size Optimization',
    icon: <Analytics />,
    tips: [
      'Large repositories (>1GB) may take longer to process',
      'Consider excluding unnecessary files (logs, binaries, etc.)',
      'Use .gitignore patterns to skip irrelevant content',
      'Process critical repositories during off-peak hours'
    ]
  },
  {
    title: 'Performance Best Practices',
    icon: <Settings />,
    tips: [
      'Index one large repository at a time for best performance',
      'Ensure stable network connection for remote repositories',
      'Monitor system resources during indexing',
      'Use local repositories when possible for faster processing'
    ]
  },
  {
    title: 'Embedding Quality',
    icon: <Storage />,
    tips: [
      'CodeBERT works best with Java, JavaScript, and similar languages',
      'Clean, well-structured code produces better embeddings',
      'Comments and documentation improve search relevance',
      'Regular code formatting helps with parsing accuracy'
    ]
  }
];

function IndexingTroubleshootingGuide({ errors = [], showGeneralTips = true }) {
  const getGuideForError = (errorType) => {
    // Try exact match first
    if (TROUBLESHOOTING_GUIDES[errorType]) {
      return TROUBLESHOOTING_GUIDES[errorType];
    }
    
    // Try partial matches
    const lowerErrorType = errorType.toLowerCase();
    for (const [key, guide] of Object.entries(TROUBLESHOOTING_GUIDES)) {
      if (lowerErrorType.includes(key.toLowerCase()) || key.toLowerCase().includes(lowerErrorType)) {
        return guide;
      }
    }
    
    return null;
  };

  const uniqueErrorTypes = [...new Set(errors.map(error => error.error_type))];
  const relevantGuides = uniqueErrorTypes
    .map(errorType => ({ errorType, guide: getGuideForError(errorType) }))
    .filter(item => item.guide !== null);

  if (relevantGuides.length === 0 && !showGeneralTips) {
    return null;
  }

  return (
    <Box>
      {relevantGuides.length > 0 && (
        <Box sx={{ mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            Troubleshooting Guide
          </Typography>
          
          {relevantGuides.map(({ errorType, guide }) => (
            <Accordion key={errorType} sx={{ mb: 1 }}>
              <AccordionSummary expandIcon={<ExpandMore />}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  {guide.icon}
                  <Typography variant="subtitle1">{guide.title}</Typography>
                  <Chip
                    size="small"
                    label={guide.severity}
                    color={guide.severity === 'error' ? 'error' : 'warning'}
                  />
                </Box>
              </AccordionSummary>
              <AccordionDetails>
                <Box>
                  <Typography variant="body2" paragraph>
                    {guide.description}
                  </Typography>
                  
                  <Typography variant="subtitle2" gutterBottom>
                    Common Causes:
                  </Typography>
                  <List dense>
                    {guide.causes.map((cause, index) => (
                      <ListItem key={index} sx={{ py: 0 }}>
                        <ListItemIcon sx={{ minWidth: 24 }}>
                          <Warning fontSize="small" color="warning" />
                        </ListItemIcon>
                        <ListItemText primary={cause} />
                      </ListItem>
                    ))}
                  </List>
                  
                  <Typography variant="subtitle2" gutterBottom sx={{ mt: 2 }}>
                    Recommended Solutions:
                  </Typography>
                  <List dense>
                    {guide.solutions.map((solution, index) => (
                      <ListItem key={index} sx={{ py: 0 }}>
                        <ListItemIcon sx={{ minWidth: 24 }}>
                          <CheckCircle fontSize="small" color="success" />
                        </ListItemIcon>
                        <ListItemText primary={solution} />
                      </ListItem>
                    ))}
                  </List>
                </Box>
              </AccordionDetails>
            </Accordion>
          ))}
        </Box>
      )}

      {showGeneralTips && (
        <Box>
          <Typography variant="h6" gutterBottom>
            General Tips & Best Practices
          </Typography>
          
          {GENERAL_TIPS.map((section, index) => (
            <Accordion key={index} sx={{ mb: 1 }}>
              <AccordionSummary expandIcon={<ExpandMore />}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  {section.icon}
                  <Typography variant="subtitle1">{section.title}</Typography>
                </Box>
              </AccordionSummary>
              <AccordionDetails>
                <List dense>
                  {section.tips.map((tip, tipIndex) => (
                    <ListItem key={tipIndex} sx={{ py: 0 }}>
                      <ListItemIcon sx={{ minWidth: 24 }}>
                        <Info fontSize="small" color="info" />
                      </ListItemIcon>
                      <ListItemText primary={tip} />
                    </ListItem>
                  ))}
                </List>
              </AccordionDetails>
            </Accordion>
          ))}
        </Box>
      )}

      <Alert severity="info" sx={{ mt: 2 }}>
        <Typography variant="body2">
          <strong>Need more help?</strong> If you continue to experience issues, check the system logs 
          or contact your administrator. You can also try restarting the indexing process or 
          processing a smaller repository first to isolate the problem.
        </Typography>
      </Alert>
    </Box>
  );
}

export default IndexingTroubleshootingGuide;