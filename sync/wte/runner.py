"""
WTE Pipeline Runner

Executes Watch-Transform-Execute pipelines with error handling and logging.
"""

import asyncio
import logging
from typing import TypeVar, Optional
from .core import WTE, WTEBase

T = TypeVar('T')
A = TypeVar('A')

logger = logging.getLogger(__name__)


async def run_pipeline(wte: WTE[T, A], max_errors: int = 10) -> None:
    """
    Run a WTE pipeline with error handling
    
    Args:
        wte: The pipeline to run
        max_errors: Maximum consecutive errors before stopping
    """
    error_count = 0
    
    try:
        async for event in wte.watch():
            try:
                action = wte.transform(event)
                if action is not None:
                    await wte.execute(action)
                
                # Reset error count on successful processing
                error_count = 0
                
            except Exception as e:
                error_count += 1
                logger.error(f"Pipeline error ({error_count}/{max_errors}): {e}")
                
                if error_count >= max_errors:
                    logger.error("Max errors reached, stopping pipeline")
                    break
                
                # Brief backoff before continuing
                await asyncio.sleep(0.1)
                
    except Exception as e:
        logger.error(f"Fatal pipeline error: {e}")
        raise


async def run_pipeline_base(pipeline: WTEBase[T, A], max_errors: int = 10) -> None:
    """Run a WTEBase pipeline with error handling"""
    await run_pipeline(
        WTE(pipeline.watch, pipeline.transform, pipeline.execute),
        max_errors
    )


async def run_multiple_pipelines(*pipelines: WTE) -> None:
    """Run multiple pipelines concurrently"""
    tasks = [asyncio.create_task(run_pipeline(pipeline)) for pipeline in pipelines]
    
    try:
        await asyncio.gather(*tasks)
    except Exception as e:
        logger.error(f"Error running multiple pipelines: {e}")
        # Cancel remaining tasks
        for task in tasks:
            if not task.done():
                task.cancel()
        raise