/**
 * Claude Desktop Log Watcher
 * Watches Claude Desktop MCP logs and emits structured events
 */

import { spawn } from 'child_process';
import { existsSync } from 'fs';
import { join } from 'path';
import { LogEntry } from './types.js';

function getClaudeDesktopLogPath(): string | null {
  const possiblePaths = [
    join(process.env.HOME || '', 'Library', 'Logs', 'Claude', 'mcp-server-cafedelic.log'),
    join(process.env.HOME || '', '.config', 'Claude', 'logs', 'mcp-server-cafedelic.log'),
    '/tmp/mcp-server-cafedelic.log'
  ];
  
  for (const path of possiblePaths) {
    if (existsSync(path)) {
      return path;
    }
  }
  
  return null;
}

export async function* watchClaudeDesktopLogs(): AsyncGenerator<LogEntry> {
  const logPath = getClaudeDesktopLogPath();
  
  if (!logPath) {
    console.log('[CLAUDE DESKTOP] No log file found');
    return;
  }
  
  console.log('[CLAUDE DESKTOP] Watching log:', logPath);
  
  const tail = spawn('tail', ['-f', '-n', '0', logPath]);
  const decoder = new TextDecoder();
  
  for await (const chunk of tail.stdout) {
    const lines = decoder.decode(chunk).trim().split('\n');
    
    for (const line of lines) {
      if (!line.trim()) continue;
      
      try {
        // Parse MCP protocol messages
        const mcpMatch = line.match(/(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z).*?({".*})/);
        if (mcpMatch) {
          const [, timestamp, jsonStr] = mcpMatch;
          const mcpMessage = JSON.parse(jsonStr);
          
          yield {
            timestamp,
            component: 'claude-desktop',
            type: mcpMessage.method || 'unknown',
            content: mcpMessage,
            raw: line
          };
        }
      } catch (error) {
        // Skip unparseable lines
        continue;
      }
    }
  }
}