/**
 * Core WTE Pipeline Runner
 * Orchestrates Watch-Transform-Execute cycles
 */

import { WTE } from './wte.js';

export async function runPipeline<T, A>(pipeline: WTE<T, A>): Promise<void> {
  console.log('[PIPELINE] Starting WTE pipeline...');
  
  try {
    for await (const event of pipeline.watch()) {
      try {
        const action = pipeline.transform(event);
        
        if (action) {
          await pipeline.execute(action);
        }
      } catch (error) {
        console.error('[PIPELINE] Transform/Execute error:', error);
        // Continue processing other events
      }
    }
  } catch (error) {
    console.error('[PIPELINE] Watch error:', error);
    throw error;
  }
}