/**
 * Tests for Project Service using real filesystem scanning
 */

import { describe, test, expect, beforeEach, afterEach } from '@jest/globals';
import { ProjectService } from '../../../services/project-service.js';
import { SQLiteService } from '../../../services/sqlite-service.js';
import { ClaudeDiscovery } from '../../../services/claude-discovery.js';
import { unlink } from 'fs/promises';
import { existsSync } from 'fs';
import { join } from 'path';

describe('ProjectService - Real Filesystem Tests', () => {
  let service: ProjectService;
  const testDbPath = join(process.cwd(), 'tests', 'test-project.db');

  beforeEach(async () => {
    // Clean up any existing test database
    if (existsSync(testDbPath)) {
      await unlink(testDbPath);
    }
    
    // Create service (it will create its own SQLite instance)
    service = new ProjectService();
    
    // Initialize the underlying SQLite service
    const sqliteService = (service as any).sqliteService;
    sqliteService.dbPath = testDbPath;
    await sqliteService.initialize();
    await sqliteService.initializeSchema();
  });

  afterEach(async () => {
    // Clean up test database
    const sqliteService = (service as any).sqliteService;
    if (sqliteService) {
      await sqliteService.close();
    }
    if (existsSync(testDbPath)) {
      await unlink(testDbPath);
    }
  });

  test('should scan current directory for projects', async () => {
    // Scan the current cafedelia project directory
    const currentPath = process.cwd();
    const projects = await service.scanProjects({ path: currentPath });
    
    expect(Array.isArray(projects)).toBe(true);
    
    // The current directory should be detected as a project (has package.json)
    const currentProject = projects.find(p => p.path === currentPath);
    expect(currentProject).toBeDefined();
    
    if (currentProject) {
      expect(currentProject.name).toBe('cafed');
      expect(currentProject.type).toBe('Node.js'); // Due to package.json
      expect(typeof currentProject.git).toBe('boolean');
      expect(typeof currentProject.sessions).toBe('number');
      expect(typeof currentProject.activeSessions).toBe('number');
      expect(typeof currentProject.lastActivity).toBe('string');
    }
  });

  test('should detect different project types correctly', async () => {
    // Scan parent directory to potentially find different project types
    const parentPath = join(process.cwd(), '..');
    const projects = await service.scanProjects({ 
      path: parentPath,
      recursive: false 
    });
    
    expect(Array.isArray(projects)).toBe(true);
    
    // Check that type detection works
    projects.forEach(project => {
      expect(['Node.js', 'Python', 'Rust', 'Java/Maven', 'Java/Gradle', 'Git', 'Unknown'])
        .toContain(project.type);
      expect(typeof project.git).toBe('boolean');
    });
  });

  test('should scan recursively when requested', async () => {
    const currentPath = process.cwd();
    
    // Non-recursive scan
    const nonRecursiveProjects = await service.scanProjects({ 
      path: currentPath,
      recursive: false 
    });
    
    // Recursive scan
    const recursiveProjects = await service.scanProjects({ 
      path: currentPath,
      recursive: true 
    });
    
    expect(Array.isArray(nonRecursiveProjects)).toBe(true);
    expect(Array.isArray(recursiveProjects)).toBe(true);
    
    // Recursive should find at least as many as non-recursive
    expect(recursiveProjects.length).toBeGreaterThanOrEqual(nonRecursiveProjects.length);
  });

  test('should load discovered Claude Code projects into database', async () => {
    // This test depends on actual Claude Code data existing
    const result = await service.loadDiscoveredProjects();
    
    expect(result).toHaveProperty('discovered');
    expect(result).toHaveProperty('loaded');
    expect(result).toHaveProperty('skipped');
    expect(result).toHaveProperty('errors');
    
    expect(typeof result.discovered).toBe('number');
    expect(typeof result.loaded).toBe('number');
    expect(typeof result.skipped).toBe('number');
    expect(typeof result.errors).toBe('number');
    
    // Loaded + skipped + errors should equal discovered
    expect(result.loaded + result.skipped + result.errors).toBe(result.discovered);
    
    // If projects were loaded, verify they're in the database
    if (result.loaded > 0) {
      const projects = await service.listProjects();
      expect(projects.length).toBeGreaterThan(0);
      
      // Check that loaded projects have proper structure
      const project = projects[0];
      expect(project).toHaveProperty('short_id');
      expect(project).toHaveProperty('name');
      expect(project).toHaveProperty('path');
      expect(project).toHaveProperty('status');
    }
  });

  test('should format project list output correctly', async () => {
    // Add a test project to database first
    const sqliteService = (service as any).sqliteService;
    await sqliteService.createProject({
      name: 'Test Format Project',
      path: '/test/format',
      description: 'Test project for formatting'
    });
    
    const projects = await service.listProjects();
    
    // Test table format
    const tableOutput = service.formatProjectList(projects, 'table');
    expect(typeof tableOutput).toBe('string');
    expect(tableOutput).toContain('Projects from database:');
    expect(tableOutput).toContain('Test Format Project');
    
    // Test JSON format
    const jsonOutput = service.formatProjectList(projects, 'json');
    expect(typeof jsonOutput).toBe('string');
    const parsedJson = JSON.parse(jsonOutput);
    expect(Array.isArray(parsedJson)).toBe(true);
    expect(parsedJson[0]).toHaveProperty('name', 'Test Format Project');
    
    // Test CSV format
    const csvOutput = service.formatProjectList(projects, 'csv');
    expect(typeof csvOutput).toBe('string');
    expect(csvOutput).toContain('id,name,path,status,sessions,activity');
    expect(csvOutput).toContain('Test Format Project');
  });

  test('should format project scan output correctly', async () => {
    const currentPath = process.cwd();
    const projects = await service.scanProjects({ path: currentPath });
    
    // Test table format
    const tableOutput = service.formatProjectScan(projects, 'table');
    expect(typeof tableOutput).toBe('string');
    expect(tableOutput).toContain('Scanned projects from filesystem:');
    
    // Test JSON format
    const jsonOutput = service.formatProjectScan(projects, 'json');
    expect(typeof jsonOutput).toBe('string');
    const parsedJson = JSON.parse(jsonOutput);
    expect(Array.isArray(parsedJson)).toBe(true);
    
    // Test CSV format
    const csvOutput = service.formatProjectScan(projects, 'csv');
    expect(typeof csvOutput).toBe('string');
    if (projects.length > 0) {
      expect(csvOutput).toContain('name,path,type,git,sessions,active_sessions,last_activity');
    }
  });

  test('should handle non-existent paths gracefully', async () => {
    await expect(service.scanProjects({ path: '/non/existent/path' }))
      .rejects.toThrow('Path does not exist');
  });

  test('should filter projects with sessions only', async () => {
    // Create a project without sessions
    const sqliteService = (service as any).sqliteService;
    await sqliteService.createProject({
      name: 'No Sessions Project',
      path: '/no/sessions'
    });
    
    const allProjects = await service.listProjects();
    const sessionProjects = await service.listProjects({ hasSessionsOnly: true });
    
    expect(allProjects.length).toBeGreaterThanOrEqual(sessionProjects.length);
    
    // All projects in sessionProjects should have session_count > 0
    sessionProjects.forEach(project => {
      expect(project.session_count || 0).toBeGreaterThan(0);
    });
  });

  test('should complete formatted operations end-to-end', async () => {
    // Test listProjectsFormatted
    const listResult = await service.listProjectsFormatted({
      format: 'json'
    });
    expect(typeof listResult).toBe('string');
    
    // Should be valid JSON
    expect(() => JSON.parse(listResult)).not.toThrow();
    
    // Test scanProjectsFormatted
    const scanResult = await service.scanProjectsFormatted({
      path: process.cwd(),
      format: 'json'
    });
    expect(typeof scanResult).toBe('string');
    
    // Should be valid JSON
    const scanData = JSON.parse(scanResult);
    expect(Array.isArray(scanData)).toBe(true);
  });
});