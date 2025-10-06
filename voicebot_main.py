#!/home/aiadmin/netovo_voicebot/venv/bin/python3
"""
Professional VoiceBot - Pure Whisper + Kokoro Implementation
GPU-accelerated speech processing for professional customer service
"""

import os
import time
import logging
from datetime import datetime

# Import configuration and utilities
from config import (
    setup_logging, setup_project_path, CONVERSATION_CONFIG,
    EXIT_PHRASES, URGENT_PHRASES, VOICE_TYPES
)

# Import socket-based clients (no model loading)
from socket_clients import KokoroSocketClient as KokoroTTSClient
from socket_clients import WhisperSocketClient as WhisperASRClient
from socket_clients import OllamaSocketClient as SimpleOllamaClient
from socket_clients import test_socket_connection
from agi_interface import SimpleAGI, FastInterruptRecorder, play_chunks_with_interrupt
from production_recorder import ProductionCallRecorder
from audio_utils import convert_audio_for_asterisk

# Set up configuration
setup_project_path()
setup_logging()
logger = logging.getLogger(__name__)
def _is_false_barge(user_snippet: str, spoken_text: str) -> bool:
    """Return True if the 'interrupt' is just our own TTS picked up by ASR."""
    if not user_snippet or not spoken_text:
        return False
    a = user_snippet.lower().strip()
    b = spoken_text.lower().strip()
    if a in b or b in a:
        return True
    at = set(a.split())
    bt = set(b.split())
    if not at or not bt:
        return False
    jacc = len(at & bt) / max(1, len(at | bt))
    return jacc >= 0.65

# Global pre-loaded instances for instant availability - PERSISTENT MODEL LOADING
_tts_client = None
_asr_client = None
_ollama_client = None
_models_loaded = False
_model_load_lock = False

def initialize_socket_clients():
    """Initialize socket clients - instant connection to persistent models"""
    global _tts_client, _asr_client, _ollama_client, _models_loaded

    logger.info("🔌 CONNECTING TO PERSISTENT MODELS - No loading needed!")
    start_time = time.time()

    try:
        # Test socket connection first
        if not test_socket_connection():
            logger.error("Cannot connect to model service")
            logger.error("Make sure model warmup service is running:")
            logger.error("python3 model_warmup_service.py")
            _models_loaded = False
            return

        # Create socket clients (instant - no model loading)
        logger.info("Creating TTS socket client...")
        _tts_client = KokoroTTSClient()

        logger.info("Creating Ollama socket client...")
        _ollama_client = SimpleOllamaClient()

        logger.info("Creating ASR socket client...")
        _asr_client = WhisperASRClient()

        total_time = time.time() - start_time
        _models_loaded = True
        logger.info(f"✅ SOCKET CLIENTS READY in {total_time:.3f}s - Connected to persistent models!")

    except Exception as e:
        logger.error(f"Socket client initialization failed: {e}")
        _models_loaded = False

def initialize_models_persistent():
    """Use socket clients - models already loaded by warmup service"""
    return initialize_socket_clients()

def get_preloaded_clients():
    """Get pre-loaded client instances - INSTANT for professional calls"""
    global _tts_client, _asr_client, _ollama_client, _models_loaded

    # If models not loaded, load them now (first call only)
    if not _models_loaded:
        initialize_models_persistent()

    # Verify models are ready
    if _tts_client is None or _asr_client is None or _ollama_client is None:
        logger.error("Models not available - attempting emergency reload")
        initialize_models_persistent()

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

def handle_greeting(agi, tts, asr, ollama, recorder: ProductionCallRecorder):
    """Handle the initial greeting and any interruptions - INSTANT via socket"""
    logger.info("Playing greeting (instant via persistent TTS)...")
    greeting_text = "Hello, thank you for calling NET-OH-VOH. I'm Alexis. How can I help you?"

    # Barge-in aware chunked playback
    greeting_transcript = None
    th, stop_ev, intr_res = recorder.start_interrupt_monitor(window_sec=6)

    def _check_stop():
        return intr_res.activated

    status = play_chunks_with_interrupt(agi, tts, greeting_text, voice_type="greeting", check_stop=_check_stop)

    stop_ev.set()
    th.join(timeout=0.2)

    if intr_res.activated and intr_res.transcript:
        spoken_now = greeting_text
        if _is_false_barge(intr_res.transcript, spoken_now):
            logger.info("Interrupt looked like our own TTS; ignoring and continuing.")
        else:
            logger.info(f"Greeting interrupted by voice: {intr_res.transcript[:30]}...")
            greeting_transcript = intr_res.transcript
    else:
        logger.info(f"Greeting playback status: {status}")

    # Process greeting interruption immediately
    if greeting_transcript:
        logger.info("Processing greeting interruption...")
        # Add to conversation context and generate response
        response = ollama.generate(greeting_transcript)
        logger.info(f"Response to interruption: {response[:30]}...")
        voice_type = determine_voice_type(response)
        th2, stop_ev2, intr2 = recorder.start_interrupt_monitor(window_sec=6)
        def _check_stop2():
            return intr2.activated
        play_chunks_with_interrupt(agi, tts, response, voice_type=voice_type, check_stop=_check_stop2)
        stop_ev2.set(); th2.join(timeout=0.2)
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

        # Use production recorder for user input (MixMonitor)
        transcript = recorder.get_user_input_with_mixmonitor(
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

        # Speak response with barge-in
        logger.info(f"Responding: {response[:30]}...")
        voice_type = determine_voice_type(response)
        interrupt_transcript = None

        th, stop_ev, intr_res = recorder.start_interrupt_monitor(window_sec=6)

        def _check_stop_turn():
            return intr_res.activated

        status = play_chunks_with_interrupt(agi, tts, response, voice_type=voice_type, check_stop=_check_stop_turn)

        stop_ev.set()
        th.join(timeout=0.2)

        if intr_res.activated and intr_res.transcript:
            spoken_now = response
            if _is_false_barge(intr_res.transcript, spoken_now):
                logger.info("False barge (ASR caught our TTS). Continuing playback/flow.")
                interrupt_transcript = None
            else:
                logger.info(f"Response interrupted by voice: {intr_res.transcript[:30]}...")
                interrupt_transcript = intr_res.transcript

        # If response was interrupted, process the new input immediately
        if interrupt_transcript:
            logger.info("Processing voice interruption...")
            response = ollama.generate(interrupt_transcript)
            voice_type = determine_voice_type(response)
            th2, stop_ev2, intr2 = recorder.start_interrupt_monitor(window_sec=6)
            def _check_stop2():
                return intr2.activated
            play_chunks_with_interrupt(agi, tts, response, voice_type=voice_type, check_stop=_check_stop2)
            stop_ev2.set(); th2.join(timeout=0.2)
            # then continue to next turn
            continue

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

        # Get TTS first for immediate greeting
        tts, asr, ollama = get_preloaded_clients()

        # Play greeting IMMEDIATELY after TTS loads (don't wait for ASR)
        if tts:
            logger.info("TTS ready - playing instant greeting...")
            agi.verbose("VoiceBot Active - Ready")
            handle_greeting(agi, tts, asr, ollama, recorder=ProductionCallRecorder(agi, asr))
        else:
            logger.error("TTS not available - fallback greeting")
            agi.stream_file("demo-thanks")

        # Initialize production-grade recorder (MixMonitor-based)
        recorder = ProductionCallRecorder(agi, asr)

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

# *** PROFESSIONAL CUSTOMER SERVICE: SOCKET CLIENTS FOR PERSISTENT MODELS ***
logger.info("=== VoiceBot Starting - Socket clients for persistent models ===")

# Initialize socket clients (instant connection to persistent models)
try:
    initialize_models_persistent()
    logger.info("=== VoiceBot Ready - Connected to persistent models via socket ===")
except Exception as e:
    logger.error(f"Socket client initialization failed: {e}")
    logger.info("=== VoiceBot Ready - Clients will initialize on first call ===")

if __name__ == "__main__":
    main()

