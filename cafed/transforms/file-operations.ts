/**
 * File Operations Transform
 * Processes file-related events and transforms them into actionable operations
 */

import { FileAction } from './types.js';

/**
 * Transform file actions into emacs operations
 */
export function transformToEmacsOperation(action: FileAction): string | null {
  switch (action.type) {
    case 'read':
      return `(find-file "${action.path}")`;
    case 'write':
      return `(save-buffer)`;
    case 'list':
      return `(dired "${action.path}")`;
    default:
      return null;
  }
}

/**
 * Filter file actions based on criteria
 */
export function filterRelevantFiles(actions: FileAction[]): FileAction[] {
  return actions.filter(action => {
    // Skip system files
    if (action.path.includes('/.git/') || 
        action.path.includes('/node_modules/') ||
        action.path.includes('/.venv/')) {
      return false;
    }
    
    // Only include source files
    return /\.(ts|js|py|md|json|yaml|yml|toml|sql|sh|rs|go|java|c|cpp|h|hpp)$/i.test(action.path);
  });
}

/**
 * Deduplicate file actions by path, keeping the latest
 */
export function deduplicateActions(actions: FileAction[]): FileAction[] {
  const actionMap = new Map<string, FileAction>();
  
  for (const action of actions) {
    const existing = actionMap.get(action.path);
    if (!existing || new Date(action.timestamp) > new Date(existing.timestamp)) {
      actionMap.set(action.path, action);
    }
  }
  
  return Array.from(actionMap.values());
}