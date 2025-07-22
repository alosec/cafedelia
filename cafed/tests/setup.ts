/**
 * Test setup and configuration
 * Handles test environment initialization and cleanup
 */

import { beforeAll, afterAll, beforeEach, afterEach } from '@jest/globals';
import { join } from 'path';
import { unlink } from 'fs/promises';
import { existsSync } from 'fs';

// Test database path
export const TEST_DB_PATH = join(process.cwd(), 'tests', 'test.db');

// Global test setup
beforeAll(async () => {
  // Set test environment variables
  process.env.NODE_ENV = 'test';
  process.env.DEBUG = ''; // Disable debug logging in tests
});

// Global test cleanup
afterAll(async () => {
  // Clean up test database
  if (existsSync(TEST_DB_PATH)) {
    try {
      await unlink(TEST_DB_PATH);
    } catch (error) {
      console.warn('Failed to clean up test database:', error);
    }
  }
});

// Per-test cleanup
beforeEach(() => {
  // Reset any global state if needed
});

afterEach(async () => {
  // Clean up after each test
  if (existsSync(TEST_DB_PATH)) {
    try {
      await unlink(TEST_DB_PATH);
    } catch (error) {
      // Ignore cleanup errors
    }
  }
});

// Helper function to create mock Claude Code session directory structure
export function createMockClaudeDir(sessions: { projectPath: string; sessionId: string; data: any }[]) {
  const mockClaudeDir = join(process.cwd(), 'tests', 'mock-claude');
  
  // This would be implemented with fs operations in a real test
  // For now, we'll mock it via the test fixtures
  return mockClaudeDir;
}

// Helper to create temporary test directory
export function getTempTestDir(): string {
  return join(process.cwd(), 'tests', 'temp');
}