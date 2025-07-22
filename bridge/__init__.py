"""
Bridge module for Cafedelia
Provides Python interface to cafed backend services
"""

from .cafed_client import CafedClient
from .session_sync import SessionSync

__all__ = ['CafedClient', 'SessionSync']
