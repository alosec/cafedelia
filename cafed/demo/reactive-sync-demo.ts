#!/usr/bin/env node

/**
 * Reactive Database Sync Demonstration
 * Shows the WTE pipeline in action with real Claude Code data
 */

import { createReactiveDatabaseSyncPipeline } from '../pipelines/reactive-database-sync.js';
import { runPipeline } from '../core/runner.js';
import { SQLiteService } from '../services/sqlite-service.js';
import { ClaudeDiscovery } from '../services/claude-discovery.js';

async function main() {
  console.log('🚀 Starting Reactive Database Sync Demo');
  console.log('=====================================');
  
  // Initialize services
  console.log('📊 Initializing services...');
  const sqliteService = new SQLiteService('./demo-database.db');
  const claudeDiscovery = new ClaudeDiscovery();
  
  try {
    // Initialize database
    await sqliteService.initialize();
    await sqliteService.initializeSchema();
    console.log('✅ Database initialized');
    
    // Check current state
    const sessions = await sqliteService.getSessions();
    const projects = await sqliteService.getProjects();
    console.log(`📈 Current state: ${sessions.length} sessions, ${projects.length} projects`);
    
    // Check Claude Code discovery
    const summary = await claudeDiscovery.getSessionSummary();
    console.log(`🔍 Claude Code discovery: ${summary.totalSessions} sessions, ${summary.totalProjects} projects`);
    
    // Create and start the reactive pipeline
    console.log('\n🔄 Starting Reactive WTE Pipeline...');
    console.log('Watch: Monitoring database changes every 3 seconds');
    console.log('Transform: Converting changes to sync actions');
    console.log('Execute: Simulating database sync operations');
    console.log('\nPress Ctrl+C to stop...\n');
    
    const pipeline = createReactiveDatabaseSyncPipeline();
    
    // Run the pipeline (this will run forever)
    await runPipeline(pipeline);
    
  } catch (error) {
    console.error('❌ Demo failed:', error);
  } finally {
    await sqliteService.close();
    console.log('🔚 Demo ended');
  }
}

// Handle graceful shutdown
process.on('SIGINT', () => {
  console.log('\n👋 Shutting down gracefully...');
  process.exit(0);
});

// Run the demo
main().catch(console.error);