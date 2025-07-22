/**
 * Claude Code to Emacs Pipeline
 * Watches Claude Code logs and immediately opens files in Emacs
 */

import { WTE } from '../core/wte.js';
import { watchClaudeCodeLogs, ClaudeCodeLogEntry } from '../watchers/claude-code-log.js';
import { extractClaudeCodeOperation } from '../transforms/claude-code-operations.js';
import { openInEmacs } from '../executors/emacs.js';
import { FileAction } from '../transforms/types.js';

// Wrapper to add console logging
async function* watchWithLogging() {
  console.log('[CLAUDE CODE] Starting direct pipeline - immediate frame activation');
  console.log('[CLAUDE CODE] Files will open in Emacs as soon as Claude accesses them');
  
  for await (const entry of watchClaudeCodeLogs()) {
    yield entry;
  }
}

// Transform with logging
function transformWithLogging(entry: ClaudeCodeLogEntry): FileAction | null {
  const action = extractClaudeCodeOperation(entry);
  if (action) {
    console.log(`[CODE → EMACS] Opening file: ${action.path}`);
  }
  return action;
}

// Execute with read-only mode and claude-code source
async function executeReadOnly(action: FileAction): Promise<void> {
  await openInEmacs(action, { 
    readOnly: true,
    source: 'claude-code',
    role: 'editor'
  });
}

export const claudeCodeToEmacs: WTE<ClaudeCodeLogEntry, FileAction> = {
  watch: watchWithLogging,
  transform: transformWithLogging,
  execute: executeReadOnly
};