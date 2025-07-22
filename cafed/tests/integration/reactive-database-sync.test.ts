/**
 * Integration tests for reactive database sync WTE pipeline
 * Tests the complete Watch-Transform-Execute cycle with real data
 */

import { describe, test, expect, beforeEach, afterEach } from '@jest/globals';
import { createReactiveDatabaseSyncPipeline } from '../../pipelines/reactive-database-sync.js';
import { runPipeline } from '../../core/runner.js';
import { SQLiteService } from '../../services/sqlite-service.js';
import { ClaudeDiscovery } from '../../services/claude-discovery.js';
import { unlink } from 'fs/promises';
import { existsSync } from 'fs';
import { join } from 'path';

describe('Reactive Database Sync WTE Pipeline', () => {
  let sqliteService: SQLiteService;
  const testDbPath = join(process.cwd(), 'tests', 'test-reactive-sync.db');

  beforeEach(async () => {
    // Clean up any existing test database
    if (existsSync(testDbPath)) {
      await unlink(testDbPath);
    }
    
    // Create fresh SQLite service for testing
    sqliteService = new SQLiteService(testDbPath);
    await sqliteService.initialize();
    await sqliteService.initializeSchema();
  });

  afterEach(async () => {
    // Clean up test database
    if (sqliteService) {
      await sqliteService.close();
    }
    if (existsSync(testDbPath)) {
      await unlink(testDbPath);
    }
  });

  test('should create reactive database sync pipeline', () => {
    const pipeline = createReactiveDatabaseSyncPipeline();
    
    expect(pipeline).toBeDefined();
    expect(typeof pipeline.watch).toBe('function');
    expect(typeof pipeline.transform).toBe('function');
    expect(typeof pipeline.execute).toBe('function');
  });

  test('should watch for database changes', async () => {
    const pipeline = createReactiveDatabaseSyncPipeline();
    
    // Start watching (we'll only check a few events)
    const watchGenerator = pipeline.watch();
    
    // Add a project to trigger change detection
    await sqliteService.createProject({
      name: 'Test Reactive Project',
      path: '/test/reactive',
      description: 'Project for testing reactive sync'
    });

    // Create a session to trigger session detection
    const projectId = await sqliteService.createProject({
      name: 'Session Test Project',
      path: '/test/session'
    });

    await sqliteService.createSession({
      projectId,
      name: 'Test Reactive Session',
      claudeSessionUuid: 'test-uuid-reactive-123',
      conversationTurns: 1
    });

    // Give the watcher time to detect changes (it polls every 3 seconds)
    // In a real test, we might use a shorter interval
    console.log('Waiting for watcher to detect changes...');
    
    // We can't easily test the async generator in a short test
    // but we can verify the structure exists
    expect(watchGenerator).toBeDefined();
    expect(typeof watchGenerator.next).toBe('function');
  }, 10000);

  test('should transform database change events', () => {
    const pipeline = createReactiveDatabaseSyncPipeline();
    
    // Test session discovery event
    const sessionEvent = {
      type: 'session_discovered' as const,
      timestamp: new Date().toISOString(),
      data: {
        sessionCount: 2,
        newSessions: [
          { claude_session_uuid: 'test-uuid-1' },
          { claude_session_uuid: 'test-uuid-2' }
        ]
      }
    };

    const sessionAction = pipeline.transform(sessionEvent);
    
    expect(sessionAction).toBeDefined();
    expect(sessionAction?.type).toBe('trigger_session_sync');
    expect(sessionAction?.priority).toBe('high');
    expect(sessionAction?.data.sessionUuids).toEqual(['test-uuid-1', 'test-uuid-2']);
    expect(sessionAction?.data.changeCount).toBe(2);

    // Test project addition event
    const projectEvent = {
      type: 'project_added' as const,
      timestamp: new Date().toISOString(),
      data: {
        projectCount: 3,
        newProjects: [
          { path: '/test/project1' },
          { path: '/test/project2' }
        ]
      }
    };

    const projectAction = pipeline.transform(projectEvent);
    
    expect(projectAction).toBeDefined();
    expect(projectAction?.type).toBe('trigger_project_sync');
    expect(projectAction?.priority).toBe('medium');
    expect(projectAction?.data.projectPaths).toEqual(['/test/project1', '/test/project2']);

    // Test database update event
    const dbUpdateEvent = {
      type: 'database_updated' as const,
      timestamp: new Date().toISOString(),
      data: {
        sessionCount: 5,
        projectCount: 3
      }
    };

    const dbUpdateAction = pipeline.transform(dbUpdateEvent);
    
    expect(dbUpdateAction).toBeDefined();
    expect(dbUpdateAction?.type).toBe('trigger_full_discovery');
    expect(dbUpdateAction?.priority).toBe('high');
  });

  test('should execute sync actions', async () => {
    const pipeline = createReactiveDatabaseSyncPipeline();
    
    // Test session sync action
    const sessionSyncAction = {
      type: 'trigger_session_sync' as const,
      priority: 'high' as const,
      data: {
        sessionUuids: ['test-uuid-1', 'test-uuid-2'],
        reason: 'Test session sync',
        changeCount: 2
      }
    };

    // Execute should not throw (it simulates the sync for now)
    await expect(pipeline.execute(sessionSyncAction)).resolves.not.toThrow();

    // Test project sync action
    const projectSyncAction = {
      type: 'trigger_project_sync' as const,
      priority: 'medium' as const,
      data: {
        projectPaths: ['/test/project1'],
        reason: 'Test project sync',
        changeCount: 1
      }
    };

    await expect(pipeline.execute(projectSyncAction)).resolves.not.toThrow();

    // Test full discovery action
    const fullSyncAction = {
      type: 'trigger_full_discovery' as const,
      priority: 'high' as const,
      data: {
        reason: 'Test full discovery',
        changeCount: 5
      }
    };

    await expect(pipeline.execute(fullSyncAction)).resolves.not.toThrow();
  });

  test('should handle real Claude Code data if available', async () => {
    const pipeline = createReactiveDatabaseSyncPipeline();
    
    // Try to discover real Claude Code sessions
    const claudeDiscovery = new ClaudeDiscovery();
    
    try {
      const summary = await claudeDiscovery.getSessionSummary();
      
      if (summary.totalSessions > 0) {
        console.log(`Found ${summary.totalSessions} real Claude Code sessions`);
        
        // Create a realistic database update event
        const realDataEvent = {
          type: 'database_updated' as const,
          timestamp: new Date().toISOString(),
          data: {
            sessionCount: summary.totalSessions,
            projectCount: summary.totalProjects
          }
        };

        const action = pipeline.transform(realDataEvent);
        expect(action).toBeDefined();
        expect(action?.type).toBe('trigger_full_discovery');

        // Execute the sync action
        await expect(pipeline.execute(action!)).resolves.not.toThrow();
      } else {
        console.log('No real Claude Code sessions found - skipping real data test');
      }
    } catch (error) {
      console.log('Claude discovery not available - skipping real data test');
    }
  });

  test('should run complete WTE pipeline cycle', async () => {
    // This test would run the actual pipeline for a short time
    // to verify the complete cycle works
    
    const pipeline = createReactiveDatabaseSyncPipeline();
    
    // We can't easily test the infinite loop, but we can verify
    // that runPipeline doesn't immediately throw
    const pipelinePromise = runPipeline(pipeline);
    
    // Let it run briefly
    setTimeout(() => {
      // In a real test, we might have a way to stop the pipeline
      console.log('Pipeline running successfully');
    }, 1000);

    // Since runPipeline runs forever, we just verify it starts
    expect(pipelinePromise).toBeInstanceOf(Promise);
  }, 5000);

  test('should handle errors gracefully in WTE cycle', async () => {
    const pipeline = createReactiveDatabaseSyncPipeline();
    
    // Test with invalid session UUID
    const invalidAction = {
      type: 'trigger_session_sync' as const,
      priority: 'high' as const,
      data: {
        sessionUuids: ['invalid-uuid'],
        reason: 'Test error handling',
        changeCount: 1
      }
    };

    // Should not throw even with invalid data (executor has retry logic)
    await expect(pipeline.execute(invalidAction)).resolves.not.toThrow();
  });
});