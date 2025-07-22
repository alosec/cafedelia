/**
 * Integration tests for API endpoints using real services
 */

import { describe, test, expect, beforeAll, afterAll } from '@jest/globals';
import request from 'supertest';
import express from 'express';
import cors from 'cors';
import { getClaudeDiscovery } from '../../services/claude-discovery.js';
import { existsSync } from 'fs';
import { join } from 'path';
import { homedir } from 'os';

// Create test app (simplified version of main app)
function createTestApp() {
  const app = express();
  
  app.use(cors());
  app.use(express.json());
  
  // Health check
  app.get('/health', (req, res) => {
    res.json({ 
      status: 'ok', 
      service: 'cafed-test',
      version: '1.0.0',
      timestamp: new Date().toISOString()
    });
  });
  
  // API Routes (copy from main app)
  app.get('/api/sessions', async (req, res) => {
    try {
      const discovery = getClaudeDiscovery();
      const sessions = await discovery.findAllSessions();
      
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
      
      res.json({
        success: true,
        data: formattedSessions,
        total: formattedSessions.length
      });
    } catch (error) {
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
      
      res.json({
        success: true,
        data: projects,
        total: projects.length
      });
    } catch (error) {
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
      
      res.json({
        success: true,
        data: summary
      });
    } catch (error) {
      res.status(500).json({
        success: false,
        error: 'Failed to fetch summary',
        message: error instanceof Error ? error.message : 'Unknown error'
      });
    }
  });
  
  // 404 handler
  app.use('*', (req, res) => {
    res.status(404).json({
      success: false,
      error: 'Not found',
      message: `Route ${req.originalUrl} not found`
    });
  });
  
  return app;
}

describe('API Integration Tests', () => {
  let app: express.Application;
  const claudeDir = join(homedir(), '.claude', 'projects');

  beforeAll(() => {
    app = createTestApp();
  });

  test('GET /health should return healthy status', async () => {
    const response = await request(app)
      .get('/health')
      .expect(200);
    
    expect(response.body).toHaveProperty('status', 'ok');
    expect(response.body).toHaveProperty('service', 'cafed-test');
    expect(response.body).toHaveProperty('version');
    expect(response.body).toHaveProperty('timestamp');
  });

  test('GET /api/sessions should return real session data', async () => {
    const response = await request(app)
      .get('/api/sessions')
      .expect(200);
    
    expect(response.body).toHaveProperty('success', true);
    expect(response.body).toHaveProperty('data');
    expect(response.body).toHaveProperty('total');
    expect(Array.isArray(response.body.data)).toBe(true);
    expect(typeof response.body.total).toBe('number');
    expect(response.body.data.length).toBe(response.body.total);
    
    // If sessions exist, validate structure
    if (response.body.data.length > 0) {
      const session = response.body.data[0];
      expect(session).toHaveProperty('id');
      expect(session).toHaveProperty('session_uuid');
      expect(session).toHaveProperty('project_name');
      expect(session).toHaveProperty('project_path');
      expect(session).toHaveProperty('status');
      expect(session).toHaveProperty('created_at');
      expect(session).toHaveProperty('last_activity');
      expect(session).toHaveProperty('conversation_turns');
      expect(session).toHaveProperty('total_cost_usd');
      expect(session).toHaveProperty('file_operations');
      expect(session).toHaveProperty('jsonl_file_path');
      
      // Validate data types
      expect(typeof session.id).toBe('string');
      expect(typeof session.project_name).toBe('string');
      expect(typeof session.conversation_turns).toBe('number');
      expect(typeof session.total_cost_usd).toBe('number');
      expect(Array.isArray(session.file_operations)).toBe(true);
      expect(['active', 'inactive']).toContain(session.status);
    }
  });

  test('GET /api/projects should return real project data', async () => {
    const response = await request(app)
      .get('/api/projects')
      .expect(200);
    
    expect(response.body).toHaveProperty('success', true);
    expect(response.body).toHaveProperty('data');
    expect(response.body).toHaveProperty('total');
    expect(Array.isArray(response.body.data)).toBe(true);
    expect(typeof response.body.total).toBe('number');
    
    // If projects exist, validate structure
    if (response.body.data.length > 0) {
      const project = response.body.data[0];
      expect(project).toHaveProperty('path');
      expect(project).toHaveProperty('name');
      expect(project).toHaveProperty('sessionCount');
      expect(project).toHaveProperty('lastActivity');
      expect(project).toHaveProperty('sessions');
      
      expect(typeof project.path).toBe('string');
      expect(typeof project.name).toBe('string');
      expect(typeof project.sessionCount).toBe('number');
      expect(Array.isArray(project.sessions)).toBe(true);
    }
  });

  test('GET /api/sessions/:sessionId should return specific session', async () => {
    // First get all sessions to find a valid ID
    const sessionsResponse = await request(app)
      .get('/api/sessions')
      .expect(200);
    
    if (sessionsResponse.body.data.length === 0) {
      console.log('No sessions available for testing individual session endpoint');
      return;
    }
    
    const sessionId = sessionsResponse.body.data[0].id;
    
    const response = await request(app)
      .get(`/api/sessions/${sessionId}`)
      .expect(200);
    
    expect(response.body).toHaveProperty('success', true);
    expect(response.body).toHaveProperty('data');
    expect(response.body.data.id).toBe(sessionId);
  });

  test('GET /api/sessions/:sessionId should return 404 for non-existent session', async () => {
    const fakeSessionId = '00000000-0000-0000-0000-000000000000';
    
    const response = await request(app)
      .get(`/api/sessions/${fakeSessionId}`)
      .expect(404);
    
    expect(response.body).toHaveProperty('success', false);
    expect(response.body).toHaveProperty('error', 'Session not found');
  });

  test('GET /api/summary should return session statistics', async () => {
    const response = await request(app)
      .get('/api/summary')
      .expect(200);
    
    expect(response.body).toHaveProperty('success', true);
    expect(response.body).toHaveProperty('data');
    
    const summary = response.body.data;
    expect(summary).toHaveProperty('totalSessions');
    expect(summary).toHaveProperty('activeSessions');
    expect(summary).toHaveProperty('totalProjects');
    expect(summary).toHaveProperty('totalCost');
    
    expect(typeof summary.totalSessions).toBe('number');
    expect(typeof summary.activeSessions).toBe('number');
    expect(typeof summary.totalProjects).toBe('number');
    expect(typeof summary.totalCost).toBe('number');
    
    // Logical constraints
    expect(summary.activeSessions).toBeLessThanOrEqual(summary.totalSessions);
    expect(summary.totalCost).toBeGreaterThanOrEqual(0);
  });

  test('GET /nonexistent should return 404', async () => {
    const response = await request(app)
      .get('/nonexistent')
      .expect(404);
    
    expect(response.body).toHaveProperty('success', false);
    expect(response.body).toHaveProperty('error', 'Not found');
  });

  test('API should handle CORS correctly', async () => {
    const response = await request(app)
      .options('/api/sessions')
      .set('Origin', 'http://localhost:3000')
      .set('Access-Control-Request-Method', 'GET');
    
    expect(response.headers).toHaveProperty('access-control-allow-origin');
  });

  test('API endpoints should handle errors gracefully', async () => {
    // This test simulates error conditions by potentially triggering
    // filesystem errors or other issues in the discovery service
    
    // If no Claude directory exists, endpoints should still respond properly
    if (!existsSync(claudeDir)) {
      const sessionsResponse = await request(app)
        .get('/api/sessions')
        .expect(200);
      
      expect(sessionsResponse.body.success).toBe(true);
      expect(sessionsResponse.body.data).toEqual([]);
      expect(sessionsResponse.body.total).toBe(0);
    }
  });
});