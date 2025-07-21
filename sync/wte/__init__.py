"""
Cafedelia WTE (Watch-Transform-Execute) Pipeline Architecture

Python port of cafedelic's functional pipeline system for event-driven processing.
Provides clean, composable pipelines for handling JSONL sync, session management,
and real-time data processing.
"""

from .core import WTE, WatcherFn, TransformFn, ExecutorFn
from .runner import run_pipeline
from .compose import compose, chain, pipe

__all__ = [
    'WTE', 'WatcherFn', 'TransformFn', 'ExecutorFn',
    'run_pipeline', 'compose', 'chain', 'pipe'
]