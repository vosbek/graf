import React, { useState, useRef, useEffect } from 'react';
import {
  Box, Typography, TextField, Button, Paper, List, ListItem,
  Alert, CircularProgress, Chip, Divider, Card, CardContent
} from '@mui/material';
import { Chat, Send, SmartToy, Person } from '@mui/icons-material';
import { ApiService } from '../services/ApiService';

function ChatInterface({ repositories }) {
  const [messages, setMessages] = useState([]);
  const [currentMessage, setCurrentMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Welcome message
  useEffect(() => {
    if (messages.length === 0) {
      setMessages([{
        type: 'bot',
        content: `Hello! I'm your AI assistant for analyzing legacy applications. I can help you understand your Struts codebase, find business logic, and plan migrations.

Try asking questions like:
• "What are all the payment processing endpoints?"
• "Show me the user authentication business logic"
• "How complex would it be to migrate the order management system?"
• "What security patterns are implemented?"`,
        timestamp: new Date()
      }]);
    }
  }, []);

  const handleSendMessage = async () => {
    if (!currentMessage.trim()) return;

    const userMessage = {
      type: 'user',
      content: currentMessage,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setCurrentMessage('');
    setLoading(true);
    setError('');

    try {
      const response = await ApiService.askAgent(currentMessage);
      
      const botMessage = {
        type: 'bot',
        content: response.answer,
        timestamp: new Date()
      };
      
      setMessages(prev => [...prev, botMessage]);
    } catch (error) {
      setError(error.message);
      
      const errorMessage = {
        type: 'bot',
        content: `I apologize, but I encountered an error: ${error.message}`,
        timestamp: new Date(),
        isError: true
      };
      
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSendMessage();
    }
  };

  const exampleQuestions = [
    "What are the main features of this application?",
    "Show me all payment processing endpoints",
    "What business logic handles user authentication?",
    "How should I migrate this to GraphQL?",
    "What security measures are implemented?",
    "Which features would be easiest to migrate first?"
  ];

  const handleExampleClick = (question) => {
    setCurrentMessage(question);
  };

  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom>
        AI Chat Assistant
      </Typography>
      <Typography variant="body1" color="text.secondary" paragraph>
        Ask questions about your codebase in natural language. The AI will analyze your repositories and provide insights.
      </Typography>

      {repositories.length === 0 && (
        <Alert severity="info" sx={{ mb: 3 }}>
          No repositories indexed yet. Please index some repositories first to get meaningful insights.
        </Alert>
      )}

      {/* Example Questions */}
      {messages.length <= 1 && (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            💡 Example Questions
          </Typography>
          <Box display="flex" flexWrap="wrap" gap={1}>
            {exampleQuestions.map((question, index) => (
              <Chip
                key={index}
                label={question}
                variant="outlined"
                clickable
                onClick={() => handleExampleClick(question)}
                sx={{ mb: 1 }}
              />
            ))}
          </Box>
        </Paper>
      )}

      {/* Chat Messages */}
      <Paper sx={{ height: '500px', display: 'flex', flexDirection: 'column' }}>
        {/* Messages Area */}
        <Box sx={{ flexGrow: 1, overflow: 'auto', p: 2 }}>
          {messages.map((message, index) => (
            <Box key={index} sx={{ mb: 2 }}>
              <Box
                display="flex"
                justifyContent={message.type === 'user' ? 'flex-end' : 'flex-start'}
                mb={1}
              >
                <Box
                  sx={{
                    maxWidth: '80%',
                    bgcolor: message.type === 'user' ? 'primary.main' : message.isError ? 'error.main' : 'grey.100',
                    color: message.type === 'user' ? 'white' : message.isError ? 'white' : 'text.primary',
                    p: 2,
                    borderRadius: 2,
                    borderTopLeftRadius: message.type === 'user' ? 2 : 0,
                    borderTopRightRadius: message.type === 'user' ? 0 : 2,
                  }}
                >
                  <Box display="flex" alignItems="center" mb={1}>
                    {message.type === 'user' ? <Person sx={{ mr: 1 }} /> : <SmartToy sx={{ mr: 1 }} />}
                    <Typography variant="subtitle2">
                      {message.type === 'user' ? 'You' : 'AI Assistant'}
                    </Typography>
                  </Box>
                  <Typography 
                    variant="body1" 
                    sx={{ 
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word'
                    }}
                  >
                    {message.content}
                  </Typography>
                  <Typography 
                    variant="caption" 
                    sx={{ 
                      opacity: 0.7,
                      mt: 1,
                      display: 'block'
                    }}
                  >
                    {message.timestamp.toLocaleTimeString()}
                  </Typography>
                </Box>
              </Box>
            </Box>
          ))}
          
          {loading && (
            <Box display="flex" alignItems="center" mb={2}>
              <SmartToy sx={{ mr: 1 }} />
              <CircularProgress size={20} sx={{ mr: 2 }} />
              <Typography variant="body2" color="text.secondary">
                AI is analyzing your codebase...
              </Typography>
            </Box>
          )}
          
          <div ref={messagesEndRef} />
        </Box>

        {/* Input Area */}
        <Divider />
        <Box sx={{ p: 2, bgcolor: 'grey.50' }}>
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}
          
          <Box display="flex" gap={2} alignItems="flex-end">
            <TextField
              label="Ask a question about your codebase..."
              placeholder="e.g., What are the main features of this application?"
              value={currentMessage}
              onChange={(e) => setCurrentMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              multiline
              maxRows={3}
              fullWidth
              variant="outlined"
              disabled={loading || repositories.length === 0}
            />
            <Button
              variant="contained"
              endIcon={<Send />}
              onClick={handleSendMessage}
              disabled={loading || !currentMessage.trim() || repositories.length === 0}
              sx={{ minWidth: 'auto', px: 3 }}
            >
              Send
            </Button>
          </Box>
          
          <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
            Press Enter to send, Shift+Enter for new line
          </Typography>
        </Box>
      </Paper>
    </Box>
  );
}

export default ChatInterface;