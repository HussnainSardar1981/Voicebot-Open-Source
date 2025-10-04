#!/usr/bin/env python3
"""
VoiceBot Components Package
Modular components extracted from production_agi_voicebot.py

This package contains:
- tts_client: Text-to-Speech functionality
- asr_client: Speech Recognition functionality
- ollama_client: AI conversation handling
- agi_interface: Asterisk AGI communication
- audio_utils: Audio conversion utilities
- config: Centralized configuration
- voicebot_main: Main orchestrator
"""

from .config import setup_logging, setup_project_path
from .tts_client import DirectTTSClient
from .asr_client import DirectASRClient
from .ollama_client import SimpleOllamaClient
from .agi_interface import SimpleAGI, FastInterruptRecorder
from .audio_utils import convert_audio_for_asterisk

__version__ = "1.0.0"
__all__ = [
    "DirectTTSClient",
    "DirectASRClient",
    "SimpleOllamaClient",
    "SimpleAGI",
    "FastInterruptRecorder",
    "convert_audio_for_asterisk",
    "setup_logging",
    "setup_project_path"
]