/**
 * Claude Code Operations Transform
 * Extracts and debounces file operations from Claude Code logs
 */

import { ClaudeCodeLogEntry } from '../watchers/claude-code-log.js';
import { FileAction } from './types.js';

// Simple transform without debouncing (for initial implementation)
export function extractClaudeCodeOperation(entry: ClaudeCodeLogEntry): FileAction | null {
  if (!entry.toolUse?.input?.file_path) return null;
  
  const filePath = entry.toolUse.input.file_path;
  
  // Skip memory-bank and binary files
  if (filePath.includes('/memory-bank/') || 
      /\.(jpg|jpeg|png|gif|pdf|zip|tar|gz|mp4|mp3|exe|dll|so)$/i.test(filePath)) {
    return null;
  }
  
  return {
    type: 'read',
    path: filePath,
    timestamp: entry.timestamp
  };
}

// Advanced debouncing transform
export class DebouncingTransform {
  private fileQueue = new Map<string, FileAction>();
  private debounceTimer: NodeJS.Timeout | null = null;
  private batchCallback: ((actions: FileAction[]) => void) | null = null;
  
  async *transform(entries: AsyncGenerator<ClaudeCodeLogEntry>): AsyncGenerator<FileAction[]> {
    for await (const entry of entries) {
      const action = extractClaudeCodeOperation(entry);
      if (!action) continue;
      
      // Add to queue
      this.fileQueue.set(action.path, action);
      
      // Reset timer
      if (this.debounceTimer) {
        clearTimeout(this.debounceTimer);
      }
      
      // Wait for batch completion
      const actions = await new Promise<FileAction[]>((resolve) => {
        this.batchCallback = resolve;
        this.debounceTimer = setTimeout(() => {
          const batch = Array.from(this.fileQueue.values());
          this.fileQueue.clear();
          this.debounceTimer = null;
          if (this.batchCallback) {
            this.batchCallback(batch);
          }
        }, 5000);
      });
      
      if (actions.length > 0) {
        yield actions;
      }
    }
    
    // Flush remaining
    if (this.fileQueue.size > 0) {
      yield Array.from(this.fileQueue.values());
    }
  }
}