/**
 * File to Emacs Pipeline
 * Watches file operations and routes them to appropriate Emacs instances
 */

import { WTE } from '../core/wte.js';
import { watchClaudeDesktopLogs } from '../watchers/claude-desktop-log.js';
import { FileAction } from '../transforms/types.js';
import { openInEmacs } from '../executors/emacs.js';
import { LogEntry } from '../watchers/types.js';

// Simple file operation extraction from log entries
function extractFileOperation(entry: LogEntry): FileAction | null {
  // Look for MCP tool calls
  if (entry.type === 'request' && entry.content?.method === 'tools/call') {
    const { name, arguments: args } = entry.content.params || {};
    
    // Check for read_file tool
    if (name === 'read_file' && args?.path) {
      console.log(`[DESKTOP → EMACS] Opening file: ${args.path}`);
      return {
        type: 'read',
        path: args.path,
        timestamp: entry.timestamp
      };
    }
    
    // Check for list_directory tool
    if (name === 'list_directory' && args?.path) {
      console.log(`[DESKTOP → EMACS] Opening directory: ${args.path}`);
      return {
        type: 'list',
        path: args.path,
        timestamp: entry.timestamp
      };
    }
    
    // Check for write_file/edit_block tools
    if (name === 'write_file' && args?.path) {
      console.log(`[DESKTOP → EMACS] Opening written file: ${args.path}`);
      return {
        type: 'write',
        path: args.path,
        timestamp: entry.timestamp
      };
    }
  }
  
  return null;
}

// Execute with claude-desktop source
async function executeClaudeDesktop(action: FileAction): Promise<void> {
  await openInEmacs(action, { 
    source: 'claude-desktop',
    role: 'editor'
  });
}

export const fileToEmacs: WTE<LogEntry, FileAction> = {
  watch: watchClaudeDesktopLogs,
  transform: extractFileOperation,
  execute: executeClaudeDesktop
};