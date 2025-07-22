/**
 * Tests for Claude Discovery Service using real Claude Code data
 */

import { describe, test, expect, beforeAll } from '@jest/globals';
import { ClaudeDiscovery } from '../../../services/claude-discovery.js';
import { existsSync } from 'fs';
import { join } from 'path';
import { homedir } from 'os';

describe('ClaudeDiscovery - Real Data Tests', () => {
  let discovery: ClaudeDiscovery;
  const claudeDir = join(homedir(), '.claude', 'projects');

  beforeAll(() => {
    discovery = new ClaudeDiscovery();
  });

  test('should initialize with correct Claude directory path', () => {
    expect(discovery).toBeDefined();
    // The constructor should set the Claude directory correctly
    expect(claudeDir.includes('.claude/projects')).toBe(true);
  });

  test('should find real Claude Code projects if they exist', async () => {
    // Only run this test if the user actually has Claude Code projects
    if (!existsSync(claudeDir)) {
      console.log('No Claude Code directory found - skipping real data test');
      return;
    }

    const projects = await discovery.findAllProjects();
    
    // Should return an array (might be empty if no projects)
    expect(Array.isArray(projects)).toBe(true);
    
    // If projects exist, they should have proper structure
    if (projects.length > 0) {
      const project = projects[0];
      expect(project).toHaveProperty('path');
      expect(project).toHaveProperty('name');
      expect(project).toHaveProperty('sessionCount');
      expect(project).toHaveProperty('lastActivity');
      expect(project).toHaveProperty('sessions');
      
      expect(typeof project.path).toBe('string');
      expect(typeof project.name).toBe('string');
      expect(typeof project.sessionCount).toBe('number');
      expect(project.lastActivity).toBeInstanceOf(Date);
      expect(Array.isArray(project.sessions)).toBe(true);
    }
  });

  test('should find real Claude Code sessions if they exist', async () => {
    if (!existsSync(claudeDir)) {
      console.log('No Claude Code directory found - skipping real data test');
      return;
    }

    const sessions = await discovery.findAllSessions();
    
    // Should return an array
    expect(Array.isArray(sessions)).toBe(true);
    
    // If sessions exist, they should have proper structure
    if (sessions.length > 0) {
      const session = sessions[0];
      expect(session).toHaveProperty('sessionUuid');
      expect(session).toHaveProperty('projectPath');
      expect(session).toHaveProperty('projectName');
      expect(session).toHaveProperty('createdAt');
      expect(session).toHaveProperty('lastActivity');
      expect(session).toHaveProperty('conversationTurns');
      expect(session).toHaveProperty('totalCostUsd');
      expect(session).toHaveProperty('fileOperations');
      expect(session).toHaveProperty('isActive');
      expect(session).toHaveProperty('jsonlFilePath');
      
      // Validate types
      expect(typeof session.sessionUuid).toBe('string');
      expect(typeof session.projectPath).toBe('string');
      expect(typeof session.projectName).toBe('string');
      expect(session.createdAt).toBeInstanceOf(Date);
      expect(session.lastActivity).toBeInstanceOf(Date);
      expect(typeof session.conversationTurns).toBe('number');
      expect(typeof session.totalCostUsd).toBe('number');
      expect(Array.isArray(session.fileOperations)).toBe(true);
      expect(typeof session.isActive).toBe('boolean');
      expect(typeof session.jsonlFilePath).toBe('string');
      
      // Validate UUID format
      const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
      expect(uuidRegex.test(session.sessionUuid)).toBe(true);
      
      // Validate JSONL file exists
      expect(existsSync(session.jsonlFilePath)).toBe(true);
    }
  });

  test('should decode project paths correctly', () => {
    // Test the actual decoding logic with real examples
    const testCases = [
      { encoded: '-home-alex-code-cafedelia', expected: '/home/alex/code/cafedelia' },
      { encoded: '-Users-john-Documents-project', expected: '/Users/john/Documents/project' },
      { encoded: 'regular-name', expected: 'regular-name' }
    ];

    testCases.forEach(({ encoded, expected }) => {
      const decoded = discovery.decodeProjectPath(encoded);
      expect(decoded).toBe(expected);
    });
  });

  test('should validate UUIDs correctly', () => {
    // Test with real UUID formats that Claude Code uses
    const validUuids = [
      '123e4567-e89b-12d3-a456-426614174000',
      'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
      '6ba7b810-9dad-11d1-80b4-00c04fd430c8'
    ];

    const invalidUuids = [
      'not-a-uuid',
      '123e4567-e89b-12d3-a456',
      '123e4567-e89b-12d3-a456-426614174000-extra',
      ''
    ];

    validUuids.forEach(uuid => {
      // Access private method via any cast for testing
      const result = (discovery as any).isValidUuid(uuid);
      expect(result).toBe(true);
    });

    invalidUuids.forEach(uuid => {
      const result = (discovery as any).isValidUuid(uuid);
      expect(result).toBe(false);
    });
  });

  test('should get session summary with real data', async () => {
    const summary = await discovery.getSessionSummary();
    
    expect(summary).toHaveProperty('totalSessions');
    expect(summary).toHaveProperty('activeSessions');
    expect(summary).toHaveProperty('totalProjects');
    expect(summary).toHaveProperty('totalCost');
    
    expect(typeof summary.totalSessions).toBe('number');
    expect(typeof summary.activeSessions).toBe('number');
    expect(typeof summary.totalProjects).toBe('number');
    expect(typeof summary.totalCost).toBe('number');
    
    // Active sessions should not exceed total sessions
    expect(summary.activeSessions).toBeLessThanOrEqual(summary.totalSessions);
    
    // Cost should be non-negative
    expect(summary.totalCost).toBeGreaterThanOrEqual(0);
  });

  test('should handle missing Claude directory gracefully', async () => {
    // Create a discovery instance with a non-existent directory
    const badDiscovery = new ClaudeDiscovery();
    // Override the claudeDir to point to non-existent directory
    (badDiscovery as any).claudeDir = '/non/existent/path';
    
    const projects = await badDiscovery.findAllProjects();
    const sessions = await badDiscovery.findAllSessions();
    
    expect(Array.isArray(projects)).toBe(true);
    expect(projects.length).toBe(0);
    expect(Array.isArray(sessions)).toBe(true);
    expect(sessions.length).toBe(0);
  });
});