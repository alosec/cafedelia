/**
 * Tests for SQLite Service using real database operations
 */

import { describe, test, expect, beforeEach, afterEach } from '@jest/globals';
import { SQLiteService } from '../../../services/sqlite-service.js';
import { unlink } from 'fs/promises';
import { existsSync } from 'fs';
import { join } from 'path';

describe('SQLiteService - Real Database Tests', () => {
  let service: SQLiteService;
  const testDbPath = join(process.cwd(), 'tests', 'test-real.db');

  beforeEach(async () => {
    // Clean up any existing test database
    if (existsSync(testDbPath)) {
      await unlink(testDbPath);
    }
    service = new SQLiteService(testDbPath);
  });

  afterEach(async () => {
    // Clean up test database
    if (service) {
      await service.close();
    }
    if (existsSync(testDbPath)) {
      await unlink(testDbPath);
    }
  });

  test('should initialize and create database schema', async () => {
    await service.initialize();
    
    // Database should not be initialized yet (no tables)
    const isInitialized = await service.isInitialized();
    expect(isInitialized).toBe(false);
    
    // Initialize schema
    await service.initializeSchema();
    
    // Now it should be initialized
    const isInitializedAfter = await service.isInitialized();
    expect(isInitializedAfter).toBe(true);
  });

  test('should create and retrieve projects', async () => {
    await service.initialize();
    await service.initializeSchema();
    
    // Create a test project
    const projectData = {
      name: 'Test Project',
      path: '/home/test/project',
      description: 'A test project for unit testing',
      hasGit: true,
      gitRemoteUrl: 'https://github.com/test/project.git',
      discoveredFrom: 'manual' as const
    };
    
    const projectId = await service.createProject(projectData);
    expect(typeof projectId).toBe('string');
    expect(projectId).toMatch(/^p\d+$/); // Should match pattern p1, p2, etc.
    
    // Retrieve projects
    const projects = await service.getProjects();
    expect(Array.isArray(projects)).toBe(true);
    expect(projects.length).toBe(1);
    
    const project = projects[0];
    expect(project.short_id).toBe(projectId);
    expect(project.name).toBe(projectData.name);
    expect(project.path).toBe(projectData.path);
    expect(project.description).toBe(projectData.description);
    expect(project.has_git).toBe(true);
    expect(project.git_remote_url).toBe(projectData.gitRemoteUrl);
    expect(project.discovered_from).toBe(projectData.discoveredFrom);
  });

  test('should create and retrieve sessions', async () => {
    await service.initialize();
    await service.initializeSchema();
    
    // First create a project
    const projectId = await service.createProject({
      name: 'Test Project',
      path: '/home/test/project',
      hasGit: false
    });
    
    // Create a test session
    const sessionData = {
      projectId,
      name: 'Test Session',
      claudeSessionUuid: '123e4567-e89b-12d3-a456-426614174000',
      taskDescription: 'Testing session functionality',
      conversationTurns: 5,
      totalCostUsd: 0.25,
      jsonlFilePath: '/path/to/session.jsonl'
    };
    
    const sessionId = await service.createSession(sessionData);
    expect(typeof sessionId).toBe('string');
    expect(sessionId).toMatch(/^s\d+$/); // Should match pattern s1, s2, etc.
    
    // Retrieve sessions
    const sessions = await service.getSessions();
    expect(Array.isArray(sessions)).toBe(true);
    expect(sessions.length).toBe(1);
    
    const session = sessions[0];
    expect(session.short_id).toBe(sessionId);
    expect(session.name).toBe(sessionData.name);
    expect(session.claude_session_uuid).toBe(sessionData.claudeSessionUuid);
    expect(session.task_description).toBe(sessionData.taskDescription);
    expect(session.conversation_turns).toBe(sessionData.conversationTurns);
    expect(session.total_cost_usd).toBe(sessionData.totalCostUsd);
    expect(session.jsonl_file_path).toBe(sessionData.jsonlFilePath);
    expect(session.project_name).toBe('Test Project'); // From JOIN
  });

  test('should filter projects by status', async () => {
    await service.initialize();
    await service.initializeSchema();
    
    // Create projects with different statuses
    await service.createProject({
      name: 'Active Project',
      path: '/active/project'
    });
    
    // For testing purposes, we'd need to manually update status
    // This test validates the filtering logic works
    const allProjects = await service.getProjects();
    expect(allProjects.length).toBe(1);
    
    const activeProjects = await service.getProjects({ status: 'active' });
    expect(activeProjects.length).toBe(1);
    
    const archivedProjects = await service.getProjects({ status: 'archived' });
    expect(archivedProjects.length).toBe(0);
  });

  test('should filter sessions by project', async () => {
    await service.initialize();
    await service.initializeSchema();
    
    // Create two projects
    const project1Id = await service.createProject({
      name: 'Project 1',
      path: '/project1'
    });
    
    const project2Id = await service.createProject({
      name: 'Project 2', 
      path: '/project2'
    });
    
    // Create sessions for each project
    await service.createSession({
      projectId: project1Id,
      name: 'Session 1',
      conversationTurns: 3
    });
    
    await service.createSession({
      projectId: project2Id,
      name: 'Session 2',
      conversationTurns: 5
    });
    
    // Filter sessions by project
    const project1Sessions = await service.getSessions({ projectId: project1Id });
    expect(project1Sessions.length).toBe(1);
    expect(project1Sessions[0].name).toBe('Session 1');
    
    const project2Sessions = await service.getSessions({ projectId: project2Id });
    expect(project2Sessions.length).toBe(1);
    expect(project2Sessions[0].name).toBe('Session 2');
    
    const allSessions = await service.getSessions();
    expect(allSessions.length).toBe(2);
  });

  test('should handle concurrent operations safely', async () => {
    await service.initialize();
    await service.initializeSchema();
    
    // Create multiple projects concurrently
    const projectPromises = Array.from({ length: 5 }, (_, i) =>
      service.createProject({
        name: `Concurrent Project ${i}`,
        path: `/concurrent/project${i}`
      })
    );
    
    const projectIds = await Promise.all(projectPromises);
    expect(projectIds).toHaveLength(5);
    
    // Each should have unique ID
    const uniqueIds = new Set(projectIds);
    expect(uniqueIds.size).toBe(5);
    
    // Verify all projects were created
    const projects = await service.getProjects();
    expect(projects.length).toBe(5);
  });

  test('should handle errors gracefully', async () => {
    await service.initialize();
    await service.initializeSchema();
    
    // Try to create session for non-existent project
    await expect(service.createSession({
      projectId: 'nonexistent',
      name: 'Bad Session'
    })).rejects.toThrow('Project nonexistent not found');
  });

  test('should properly close database connection', async () => {
    await service.initialize();
    await service.initializeSchema();
    
    // Create some data
    await service.createProject({
      name: 'Test Project',
      path: '/test'
    });
    
    // Close should not throw
    await expect(service.close()).resolves.not.toThrow();
    
    // Operations after close should fail or handle gracefully
    // This depends on implementation - might throw or reconnect
  });
});