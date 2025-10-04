#!/usr/bin/env python3
"""
Configuration module - Centralized settings and constants
Extracted from production_agi_voicebot.py
"""

import sys
import logging

# Project configuration
PROJECT_DIR = "/home/aiadmin/netovo_voicebot"
CONTAINER_NAME = "riva-speech"

# Speech service configuration - RIVA vs Open Source
USE_ASR = "moonshine"  # Options: "riva", "moonshine"
USE_TTS = "kokoro"     # Options: "riva", "kokoro"

# ASR Configuration
ASR_CONFIG = {
    "riva": {
        "container": "riva-speech",
        "sample_rate": 16000
    },
    "moonshine": {
        "model": "moonshine/base",  # or "moonshine/tiny" for faster processing
        "sample_rate": 16000
    }
}

# TTS Configuration
TTS_CONFIG = {
    "riva": {
        "container": "riva-speech",
        "voice": "English-US.Female-1",
        "sample_rate": 22050
    },
    "kokoro": {
        "voice": "af_sarah",        # Available: af_sarah, af_bella, af_jessica, af_nova, af_sky
        "sample_rate": 24000,       # Kokoro native
        "target_sample_rate": 8000  # Asterisk compatibility
    }
}

# Audio settings
AUDIO_CONFIG = {
    "sample_rate": 22050,
    "conversion_sample_rate": 8000,
    "channels": 1,
    "bit_depth": 16,
    "format": "signed-integer"
}

# Conversation settings
CONVERSATION_CONFIG = {
    "max_turns": 50,
    "max_conversation_time": 900,  # 15 minutes
    "input_timeout": 12,
    "max_failed_interactions": 3,
    "max_no_response_count": 2,
    "record_timeout": 10,
    "voice_detection_threshold": 100,
    "interrupt_detection_threshold": 400
}

# Ollama settings
OLLAMA_CONFIG = {
    "model": "orca2:7b",
    "max_tokens": 50,
    "temperature": 0.4,
    "top_p": 0.9,
    "repeat_penalty": 1.1,
    "url": "http://localhost:11434/api/generate",
    "timeout": 15.0,
    "max_history": 10,
    "keep_history": 8
}

# File paths
PATHS = {
    "asterisk_sounds": "/usr/share/asterisk/sounds",
    "asterisk_monitor": "/var/spool/asterisk/monitor",
    "asterisk_log": "/var/log/asterisk/voicebot.log",
    "temp_dir": "/tmp"
}

# Exit phrases for conversation flow
EXIT_PHRASES = [
    'goodbye', 'good bye', 'bye', 'bye bye',
    'that\'s all', 'that is all', 'nothing else',
    'you\'ve helped me', 'problem solved', 'all set',
    'transfer me', 'human agent', 'speak to someone',
    'i\'m done', 'we\'re done', 'finished'
]

URGENT_PHRASES = ['emergency', 'urgent', 'critical']

# Response types for voice selection
VOICE_TYPES = {
    "empathetic": ["sorry", "apologize", "understand"],
    "helping": ["let's", "try", "check", "restart"],
    "technical": ["driver", "system", "update", "windows"],
    "default": []
}

def setup_logging():
    """Set up logging configuration"""
    try:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - FixedBot - %(message)s',
            handlers=[
                logging.FileHandler(PATHS["asterisk_log"], mode='a'),
                logging.StreamHandler(sys.stderr)
            ]
        )
    except (PermissionError, FileNotFoundError):
        # Fallback to stderr only if can't write to log file
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - FixedBot - %(message)s',
            handlers=[logging.StreamHandler(sys.stderr)]
        )

def setup_project_path():
    """Add project directory to Python path"""
    if PROJECT_DIR not in sys.path:
        sys.path.insert(0, PROJECT_DIR)
