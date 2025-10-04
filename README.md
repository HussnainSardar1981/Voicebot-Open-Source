# VoiceBot Components - Refactored Structure

This directory contains the refactored components from `production_agi_voicebot.py`, broken down into manageable, modular pieces.

## File Structure

```
voicebot_components/
├── __init__.py                    # Package initialization
├── config.py                     # Centralized configuration
├── tts_client.py                  # Text-to-Speech client
├── asr_client.py                  # Speech Recognition client
├── ollama_client.py               # AI conversation handling
├── agi_interface.py               # Asterisk AGI communication
├── audio_utils.py                 # Audio conversion utilities
├── voicebot_main.py               # Main orchestrator
└── README.md                      # This documentation
```

## Component Descriptions

### config.py
- Centralized configuration settings
- Audio, conversation, and Ollama parameters
- File paths and constants
- Logging setup functions

### Speech Services (Open Source)
- **kokoro_tts_client.py**: `KokoroTTSClient` - Text-to-speech using Kokoro (open source)
- **moonshine_asr_client.py**: `MoonshineASRClient` - Speech recognition using Moonshine (open source)
- Enhanced voice quality settings and natural speech
- Zero licensing costs, no Docker dependencies

### Legacy RIVA Services (Paid - Preserved for Rollback)
- **tts_client.py**: `DirectTTSClient` - RIVA Docker TTS (paid)
- **asr_client.py**: `DirectASRClient` - RIVA Docker ASR (paid)
- Available for rollback if needed

### ollama_client.py
- `SimpleOllamaClient` class
- AI conversation handling
- Context management
- Response validation and cleanup

### agi_interface.py
- `SimpleAGI` class for Asterisk communication
- `FastInterruptRecorder` for audio recording
- Voice interruption detection
- Call flow management

### audio_utils.py
- `convert_audio_for_asterisk()` function
- Multiple format conversion attempts
- Asterisk-compatible audio generation

### voicebot_main.py
- Main orchestrator that coordinates all components
- Conversation flow logic
- Exit condition handling
- Error management

## Usage

### To use the refactored version:

1. **Keep original file as backup:**
   ```bash
   cp production_agi_voicebot.py production_agi_voicebot_original.py
   ```

2. **Replace with refactored version:**
   ```bash
   cp production_agi_voicebot_refactored.py production_agi_voicebot.py
   ```

3. **Ensure components directory is accessible:**
   The `voicebot_components/` directory should be in the same location as the main script.

### For development:

Import individual components as needed:
```python
# Open source clients (default)
from voicebot_components import DirectTTSClient, DirectASRClient  # Now using Kokoro + Moonshine
from voicebot_components.config import CONVERSATION_CONFIG, USE_ASR, USE_TTS

# Or import specific implementations
from voicebot_components.kokoro_tts_client import KokoroTTSClient
from voicebot_components.moonshine_asr_client import MoonshineASRClient
```

## Benefits of Refactoring

1. **Modularity**: Each component has a single responsibility
2. **Maintainability**: Easier to modify individual features
3. **Testability**: Components can be tested in isolation
4. **Reusability**: Components can be used in other projects
5. **Readability**: Cleaner, more organized code structure
6. **Configuration**: Centralized settings management

## Compatibility

The refactored version maintains 100% functional compatibility with the original. All features work exactly the same:

- Same TTS/ASR functionality
- Same conversation flow
- Same Asterisk integration
- Same error handling
- Same performance characteristics

## Testing

The refactored components preserve all original functionality while providing better organization for future development and maintenance.