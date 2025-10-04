#!/home/aiadmin/netovo_voicebot/venv/bin/python3
"""
VoiceBot Main Orchestrator - Refactored from production_agi_voicebot.py
This module coordinates all components and manages the conversation flow.
"""

import os
import time
import logging
from datetime import datetime

# Import our modular components
from config import (
    setup_logging, setup_project_path, CONVERSATION_CONFIG,
    EXIT_PHRASES, URGENT_PHRASES, VOICE_TYPES
)
# Import open-source replacements as drop-in substitutes
from kokoro_tts_client import KokoroTTSClient as DirectTTSClient
from moonshine_asr_client import MoonshineASRClient as DirectASRClient
# Note: Original RIVA clients remain in tts_client.py and asr_client.py if rollback needed
from ollama_client import SimpleOllamaClient
from agi_interface import SimpleAGI, FastInterruptRecorder
from audio_utils import convert_audio_for_asterisk

# Set up configuration
setup_project_path()
setup_logging()
logger = logging.getLogger(__name__)

# Global pre-loaded instances for instant availability
_tts_client = None
_asr_client = None
_ollama_client = None

def initialize_models():
    """Pre-load all models for instant availability - optimized for AGI calls"""
    global _tts_client, _asr_client, _ollama_client

    # Fast check: if already loaded in this process, skip
    if _tts_client is not None and _asr_client is not None and _ollama_client is not None:
        logger.info("Models already loaded in this process")
        return

    logger.info("Fast-loading models for AGI call...")
    start_time = time.time()

    if _tts_client is None:
        logger.info("Loading TTS client...")
        _tts_client = DirectTTSClient()

    if _asr_client is None:
        logger.info("Loading ASR client...")
        _asr_client = DirectASRClient()

    if _ollama_client is None:
        logger.info("Loading Ollama client...")
        _ollama_client = SimpleOllamaClient()
        # Skip warm-up for faster startup - first generation will be slightly slower but acceptable

    total_time = time.time() - start_time
    logger.info(f"Models loaded in {total_time:.1f}s")

def get_preloaded_clients():
    """Get pre-loaded client instances"""
    global _tts_client, _asr_client, _ollama_client
    if _tts_client is None or _asr_client is None or _ollama_client is None:
        initialize_models()
    return _tts_client, _asr_client, _ollama_client

def determine_voice_type(response_text):
    """Determine appropriate voice type based on response content"""
    response_lower = response_text.lower()

    # 🎯 Choose voice type based on response content for more natural conversation
    if any(word in response_lower for word in ["sorry", "apologize", "understand"]):
        return "empathetic"
    elif any(word in response_lower for word in ["let's", "try", "check", "restart"]):
        return "helping"
    elif any(word in response_lower for word in ["driver", "system", "update", "windows"]):
        return "technical"
    else:
        return "default"

def check_exit_conditions(transcript, response, no_response_count, failed_interactions, start_time):
    """Check various exit conditions and return (should_exit, exit_reason)"""

    # 1. User requested goodbye/transfer
    if transcript and any(phrase in transcript.lower() for phrase in EXIT_PHRASES):
        return True, "user_exit"

    # 2. AI response indicates conversation end
    if 'thank you for calling' in response.lower() or 'transfer you' in response.lower():
        return True, "ai_exit"

    # 3. No response from user for consecutive turns
    if no_response_count >= CONVERSATION_CONFIG["max_no_response_count"]:
        return True, "no_response"

    # 4. Too many failed interactions
    if failed_interactions >= CONVERSATION_CONFIG["max_failed_interactions"]:
        return True, "failed_interactions"

    # 5. Maximum conversation time reached
    if time.time() - start_time > CONVERSATION_CONFIG["max_conversation_time"]:
        return True, "timeout"

    return False, None

def handle_greeting(agi, tts, asr, ollama):
    """Handle the initial greeting and any interruptions"""
    logger.info("Playing greeting...")
    greeting_text = "Hello, thank you for calling NETOVO. I'm Alexis. How can I help you?"

    # Generate greeting TTS quickly
    tts_file = tts.synthesize(greeting_text, voice_type="greeting")

    greeting_transcript = None
    if tts_file and os.path.exists(tts_file):
        asterisk_file = convert_audio_for_asterisk(tts_file)

        # Cleanup TTS file
        try:
            os.unlink(tts_file)
        except Exception as e:
            logger.debug(f"TTS file cleanup failed: {e}")

        if asterisk_file:
            success, interrupt = agi.play_with_voice_interrupt(asterisk_file, asr)
            if interrupt and isinstance(interrupt, str) and len(interrupt) > 2:
                logger.info(f"Greeting interrupted by voice: {interrupt[:30]}...")
                greeting_transcript = interrupt
            elif interrupt:
                logger.info("Greeting interrupted by voice")
            else:
                logger.info(f"Greeting played: {success}")
        else:
            logger.error("Audio conversion failed")
            agi.stream_file("demo-thanks")
    else:
        logger.error("TTS greeting failed")
        agi.stream_file("demo-thanks")

    # Process greeting interruption immediately
    if greeting_transcript:
        logger.info("Processing greeting interruption...")
        # Add to conversation context and generate response
        response = ollama.generate(greeting_transcript)
        logger.info(f"Response to interruption: {response[:30]}...")
    else:
        logger.info("Greeting complete - ready for conversation")

def conversation_loop(agi, tts, asr, ollama, recorder):
    """Main conversation loop"""
    max_turns = CONVERSATION_CONFIG["max_turns"]
    failed_interactions = 0
    no_response_count = 0
    start_time = time.time()

    for turn in range(max_turns):
        logger.info(f"Conversation turn {turn + 1}")

        # Use fast recorder for user input
        transcript = recorder.get_user_input_with_interrupt(
            timeout=CONVERSATION_CONFIG["input_timeout"]
        )

        if not agi.connected:
            logger.info("Call disconnected")
            break

        if transcript:
            logger.info(f"User said: {transcript}")
            failed_interactions = 0
            no_response_count = 0

            # Check for USER exit intents (not AI responses)
            if any(phrase in transcript.lower() for phrase in EXIT_PHRASES):
                response = "Thank you for calling NETOVO. Have a great day!"
                # This will trigger exit after response
            elif any(phrase in transcript.lower() for phrase in URGENT_PHRASES):
                response = "I understand this is urgent. Let me transfer you to our priority support team immediately."
                # This will trigger exit after response
            else:
                # Normal AI response
                response = ollama.generate(transcript)
        else:
            failed_interactions += 1
            no_response_count += 1

            # Handle no response scenarios
            if no_response_count >= 2:
                response = "I haven't heard from you in our conversation. I'll end this call now. Thank you for calling NETOVO."
            elif failed_interactions >= 3:
                response = "I'm having trouble hearing you clearly. Let me transfer you to a human agent who can better assist you."
            else:
                response = "I didn't catch that. Could you speak up or repeat your question?"

        # Check exit conditions
        should_exit, exit_reason = check_exit_conditions(
            transcript, response, no_response_count, failed_interactions, start_time
        )

        # Speak response
        logger.info(f"Responding: {response[:30]}...")

        voice_type = determine_voice_type(response)
        tts_file = tts.synthesize(response, voice_type=voice_type)
        interrupt_transcript = None

        if tts_file and os.path.exists(tts_file):
            asterisk_file = convert_audio_for_asterisk(tts_file)

            try:
                os.unlink(tts_file)
            except Exception as e:
                logger.debug(f"TTS file cleanup failed: {e}")

            if asterisk_file:
                success, interrupt = agi.play_with_voice_interrupt(asterisk_file, asr)
                if interrupt and isinstance(interrupt, str) and len(interrupt) > 2:
                    logger.info(f"Response interrupted by voice: {interrupt[:30]}...")
                    interrupt_transcript = interrupt
                elif interrupt:
                    logger.info("Response interrupted by voice")
                    # Get user input since we detected voice but no transcript
                    transcript = recorder.get_user_input_with_interrupt(timeout=8)
                    if transcript:
                        interrupt_transcript = transcript
            else:
                # Fallback to built-in sound
                agi.stream_file("demo-thanks")
        else:
            # Fallback to built-in sound
            agi.stream_file("demo-thanks")

        # If response was interrupted, process the new input immediately
        if interrupt_transcript:
            logger.info("Processing voice interruption...")
            response = ollama.generate(interrupt_transcript)
            continue  # Go back to play new response

        # Check exit conditions after response
        if should_exit:
            logger.info(f"Exiting conversation: {exit_reason}")
            break

        # Check if call is still connected
        if not agi.connected:
            logger.info("Call disconnected - ending conversation")
            break

        agi.sleep(1)

def main():
    """Main AGI handler"""
    try:
        logger.info("=== FAST AGI VoiceBot Starting ===")

        # Initialize AGI and answer IMMEDIATELY (before loading models)
        agi = SimpleAGI()
        caller_id = agi.env.get('agi_callerid', 'Unknown')
        logger.info(f"Call from: {caller_id}")

        # Answer call FIRST - no delays
        if not agi.answer():
            logger.error("Failed to answer")
            return

        agi.verbose("VoiceBot Active - Loading...")

        # Play brief wait message while models load
        agi.say_number("1")  # Quick beep to confirm call is connected

        # THEN get models (models load in background while call is active)
        tts, asr, ollama = get_preloaded_clients()
        logger.info("Models ready for conversation")

        agi.verbose("VoiceBot Active - Ready")

        # Initialize fast recorder
        recorder = FastInterruptRecorder(agi, asr)

        # Handle greeting
        handle_greeting(agi, tts, asr, ollama)

        # Main conversation loop
        conversation_loop(agi, tts, asr, ollama, recorder)

        # End call
        logger.info("Ending call")
        agi.sleep(1)
        agi.hangup()

        logger.info("=== Fast VoiceBot completed ===")

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")

        try:
            agi = SimpleAGI()
            agi.answer()
            agi.verbose("VoiceBot error")
            agi.sleep(1)
            agi.hangup()
        except Exception as e:
            logger.error(f"Error cleanup failed: {e}")

# Models will be loaded on-demand when AGI calls come in
# This ensures calls are answered immediately, then models load in background
logger.info("=== VoiceBot Ready - Models load on-demand ===")
# initialize_models()  # Disabled: Each AGI call is separate process anyway

if __name__ == "__main__":
    main()
