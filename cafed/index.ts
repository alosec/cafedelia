import express from 'express';
import cors from 'cors';
import { createLogger, format, transports } from 'winston';
import { getClaudeDiscovery } from './services/claude-discovery.js';

// Initialize logger
const logger = createLogger({
  level: 'info',
  format: format.combine(
    format.timestamp(),
    format.errors({ stack: true }),
    format.json()
  ),
  transports: [
    new transports.Console({
      format: format.combine(
        format.colorize(),
        format.simple()
      )
    })
  ]
});

const app = express();
const port = process.env.CAFED_PORT || 8001;

// Middleware
app.use(cors({
  origin: 'http://localhost:*', // Allow any localhost port for development
  credentials: true
}));
app.use(express.json());

// Request logging
app.use((req, res, next) => {
  logger.info(`${req.method} ${req.path}`, { 
    ip: req.ip,
    userAgent: req.get('user-agent')
  });
  next();
});

// Health check
app.get('/health', (req, res) => {
  res.json({ 
    status: 'ok', 
    service: 'cafed',
    version: '1.0.0',
    timestamp: new Date().toISOString()
  });
});

// API Routes
app.get('/api/sessions', async (req, res) => {
  try {
    const discovery = getClaudeDiscovery();
    const sessions = await discovery.findAllSessions();
    
    // Transform for Elia consumption
    const formattedSessions = sessions.map(session => ({
      id: session.sessionUuid,
      session_uuid: session.sessionUuid,
      project_name: session.projectName,
      project_path: session.projectPath,
      status: session.isActive ? 'active' : 'inactive',
      created_at: session.createdAt.toISOString(),
      last_activity: session.lastActivity.toISOString(),
      conversation_turns: session.conversationTurns,
      total_cost_usd: session.totalCostUsd,
      file_operations: session.fileOperations,
      jsonl_file_path: session.jsonlFilePath
    }));
    
    logger.info(`Found ${sessions.length} Claude Code sessions`);
    res.json({
      success: true,
      data: formattedSessions,
      total: formattedSessions.length
    });
  } catch (error) {
    logger.error('Failed to fetch sessions:', error);
    res.status(500).json({
      success: false,
      error: 'Failed to fetch sessions',
      message: error instanceof Error ? error.message : 'Unknown error'
    });
  }
});

app.get('/api/projects', async (req, res) => {
  try {
    const discovery = getClaudeDiscovery();
    const projects = await discovery.findAllProjects();
    
    logger.info(`Found ${projects.length} Claude Code projects`);
    res.json({
      success: true,
      data: projects,
      total: projects.length
    });
  } catch (error) {
    logger.error('Failed to fetch projects:', error);
    res.status(500).json({
      success: false,
      error: 'Failed to fetch projects',
      message: error instanceof Error ? error.message : 'Unknown error'
    });
  }
});

app.get('/api/sessions/:sessionId', async (req, res) => {
  try {
    const { sessionId } = req.params;
    const discovery = getClaudeDiscovery();
    const sessions = await discovery.findAllSessions();
    const session = sessions.find(s => s.sessionUuid === sessionId);
    
    if (!session) {
      return res.status(404).json({
        success: false,
        error: 'Session not found',
        message: `Session ${sessionId} does not exist`
      });
    }
    
    logger.info(`Retrieved session ${sessionId}`);
    res.json({
      success: true,
      data: {
        id: session.sessionUuid,
        session_uuid: session.sessionUuid,
        project_name: session.projectName,
        project_path: session.projectPath,
        status: session.isActive ? 'active' : 'inactive',
        created_at: session.createdAt.toISOString(),
        last_activity: session.lastActivity.toISOString(),
        conversation_turns: session.conversationTurns,
        total_cost_usd: session.totalCostUsd,
        file_operations: session.fileOperations,
        jsonl_file_path: session.jsonlFilePath
      }
    });
  } catch (error) {
    logger.error(`Failed to fetch session ${req.params.sessionId}:`, error);
    res.status(500).json({
      success: false,
      error: 'Failed to fetch session',
      message: error instanceof Error ? error.message : 'Unknown error'
    });
  }
});

app.get('/api/summary', async (req, res) => {
  try {
    const discovery = getClaudeDiscovery();
    const summary = await discovery.getSessionSummary();
    
    logger.info('Retrieved session summary', summary);
    res.json({
      success: true,
      data: summary
    });
  } catch (error) {
    logger.error('Failed to fetch summary:', error);
    res.status(500).json({
      success: false,
      error: 'Failed to fetch summary',
      message: error instanceof Error ? error.message : 'Unknown error'
    });
  }
});

// Error handling middleware
app.use((err: Error, req: express.Request, res: express.Response, next: express.NextFunction) => {
  logger.error('Unhandled error:', err);
  res.status(500).json({
    success: false,
    error: 'Internal server error',
    message: process.env.NODE_ENV === 'development' ? err.message : 'Something went wrong'
  });
});

// 404 handler
app.use('*', (req, res) => {
  res.status(404).json({
    success: false,
    error: 'Not found',
    message: `Route ${req.originalUrl} not found`
  });
});

// Start server
app.listen(port, () => {
  logger.info(`Cafed backend server running on http://localhost:${port}`);
  logger.info('Available endpoints:');
  logger.info('  GET /health - Health check');
  logger.info('  GET /api/sessions - List all Claude Code sessions');
  logger.info('  GET /api/sessions/:id - Get specific session');
  logger.info('  GET /api/projects - List all projects');
  logger.info('  GET /api/summary - Session summary statistics');
});

// Graceful shutdown
process.on('SIGTERM', () => {
  logger.info('SIGTERM received, shutting down gracefully');
  process.exit(0);
});

process.on('SIGINT', () => {
  logger.info('SIGINT received, shutting down gracefully');
  process.exit(0);
});

export default app;
