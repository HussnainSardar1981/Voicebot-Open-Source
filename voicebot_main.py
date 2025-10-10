#!/home/aiadmin/netovo_voicebot/venv/bin/python3
"""
Enhanced VoiceBot with Robust Voice Interruption
Modification of voicebot_main.py to use the new interruption system
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
from agi_interface import SimpleAGI, FastInterruptRecorder
from production_recorder import ProductionCallRecorder
from audio_utils import convert_audio_for_asterisk

# Import the REAL voice interruption system (Asterisk built-in speech recognition)
from real_voice_interrupt import EnhancedAGI

# Set up configuration
setup_project_path()
setup_logging()
logger = logging.getLogger(__name__)

# Global pre-loaded instances for instant availability
_tts_client = None
_asr_client = None
_ollama_client = None
_models_loaded = False

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

def get_preloaded_clients():
    """Get pre-loaded client instances - INSTANT for professional calls"""
    global _tts_client, _asr_client, _ollama_client, _models_loaded

    # If models not loaded, load them now (first call only)
    if not _models_loaded:
        initialize_socket_clients()

    # Verify models are ready
    if _tts_client is None or _asr_client is None or _ollama_client is None:
        logger.error("Models not available - attempting emergency reload")
        initialize_socket_clients()

    return _tts_client, _asr_client, _ollama_client

def determine_voice_type(response_text):
    """Determine appropriate voice type based on response content"""
    response_lower = response_text.lower()

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

def handle_greeting_with_interruption(enhanced_agi, tts, asr, ollama):
    """Handle the initial greeting with robust voice interruption"""
    logger.info("Playing greeting with voice interruption enabled...")
    greeting_text = "Hello, thank you for calling Netovo. I'm Alexis, your AI assistant. You can interrupt me anytime just by speaking naturally. How can I help you today?"

    # Generate greeting TTS via socket (models already loaded, so fast)
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
            # Use enhanced AGI with robust voice interruption
            success, interrupt = enhanced_agi.play_with_voice_interrupt(asterisk_file)

            if interrupt and isinstance(interrupt, str) and len(interrupt) > 2:
                logger.info(f"Greeting interrupted by voice: {interrupt[:30]}...")
                greeting_transcript = interrupt
            elif interrupt:
                logger.info("Greeting interrupted by voice (no transcript)")
            else:
                logger.info(f"Greeting played successfully: {success}")
        else:
            logger.error("Audio conversion failed")
            enhanced_agi.stream_file("demo-thanks")
    else:
        logger.error("TTS greeting failed")
        enhanced_agi.stream_file("demo-thanks")

    # Process greeting interruption immediately
    if greeting_transcript:
        logger.info("Processing greeting interruption...")
        response = ollama.generate(greeting_transcript)
        logger.info(f"Response to interruption: {response[:30]}...")
        return greeting_transcript, response
    else:
        logger.info("Greeting complete - ready for conversation")
        return None, None

def conversation_loop_with_interruption(enhanced_agi, tts, asr, ollama, recorder):
    """Main conversation loop with robust voice interruption"""
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

        if not enhanced_agi.connected:
            logger.info("Call disconnected")
            break

        if transcript:
            logger.info(f"User said: {transcript}")
            failed_interactions = 0
            no_response_count = 0

            # Check for USER exit intents
            if any(phrase in transcript.lower() for phrase in EXIT_PHRASES):
                response = "Thank you for calling Netovo. Have a great day!"
            elif any(phrase in transcript.lower() for phrase in URGENT_PHRASES):
                response = "I understand this is urgent. Let me transfer you to our priority support team immediately."
            else:
                # Normal AI response
                response = ollama.generate(transcript)
        else:
            failed_interactions += 1
            no_response_count += 1

            # Handle no response scenarios
            if no_response_count >= 2:
                response = "I haven't heard from you in our conversation. I'll end this call now. Thank you for calling Netovo."
            elif failed_interactions >= 3:
                response = "I'm having trouble hearing you clearly. Let me transfer you to a human agent who can better assist you."
            else:
                response = "I didn't catch that. Could you speak up or repeat your question?"

        # Check exit conditions
        should_exit, exit_reason = check_exit_conditions(
            transcript, response, no_response_count, failed_interactions, start_time
        )

        # Speak response with voice interruption
        logger.info(f"Responding with interruption capability: {response[:30]}...")

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
                # Use enhanced AGI with robust voice interruption
                success, interrupt = enhanced_agi.play_with_voice_interrupt(asterisk_file)

                if interrupt and isinstance(interrupt, str) and len(interrupt) > 2:
                    logger.info(f"Response interrupted by voice: {interrupt[:30]}...")
                    interrupt_transcript = interrupt
                elif interrupt == "VOICE_DETECTED":
                    logger.info("Response interrupted by voice - getting full transcript")
                    # Get user input since we detected voice but no transcript
                    transcript = recorder.get_user_input_with_mixmonitor(timeout=8)
                    if transcript:
                        interrupt_transcript = transcript
            else:
                # Fallback to built-in sound
                enhanced_agi.stream_file("demo-thanks")
        else:
            # Fallback to built-in sound
            enhanced_agi.stream_file("demo-thanks")

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
        if not enhanced_agi.connected:
            logger.info("Call disconnected - ending conversation")
            break

        enhanced_agi.sleep(1)

def main():
    """Main AGI handler with robust voice interruption"""
    try:
        logger.info("=== ENHANCED VoiceBot Starting (with Voice Interruption) ===")

        # Initialize AGI and answer IMMEDIATELY
        base_agi = SimpleAGI()
        caller_id = base_agi.env.get('agi_callerid', 'Unknown')
        logger.info(f"Call from: {caller_id}")

        # Answer call FIRST - no delays
        if not base_agi.answer():
            logger.error("Failed to answer")
            return

        base_agi.verbose("Enhanced VoiceBot Active - Loading...")

        # Get models
        tts, asr, ollama = get_preloaded_clients()

        if not tts or not asr:
            logger.error("Models not available")
            base_agi.stream_file("demo-thanks")
            base_agi.hangup()
            return

        # Create enhanced AGI with professional voice interruption capabilities
        enhanced_agi = EnhancedAGI(base_agi, asr)

        # Configure REAL voice interruption (Asterisk speech recognition)
        enhanced_agi.set_voice_detection_sensitivity("normal")  # Voice sensitivity level
        logger.info("REAL voice interruption configured (Asterisk built-in speech recognition)")

        # Start voice monitoring for the entire call
        if not enhanced_agi.start_call_monitoring():
            logger.warning("Voice monitoring failed - falling back to basic mode")

        base_agi.verbose("Enhanced VoiceBot Ready - REAL Voice Interruption Enabled")

        # Handle greeting with interruption
        greeting_transcript, greeting_response = handle_greeting_with_interruption(
            enhanced_agi, tts, asr, ollama
        )

        # If greeting was interrupted, play the response
        if greeting_response:
            voice_type = determine_voice_type(greeting_response)
            tts_file = tts.synthesize(greeting_response, voice_type=voice_type)
            if tts_file:
                asterisk_file = convert_audio_for_asterisk(tts_file)
                try:
                    os.unlink(tts_file)
                except:
                    pass
                if asterisk_file:
                    enhanced_agi.play_with_voice_interrupt(asterisk_file)

        # Initialize production-grade recorder
        recorder = ProductionCallRecorder(enhanced_agi, asr)

        # Main conversation loop with interruption
        conversation_loop_with_interruption(enhanced_agi, tts, asr, ollama, recorder)

        # Stop voice monitoring
        enhanced_agi.stop_call_monitoring()

        # End call
        logger.info("Ending call")
        enhanced_agi.sleep(1)
        enhanced_agi.hangup()

        logger.info("=== Enhanced VoiceBot completed ===")

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")

        try:
            base_agi = SimpleAGI()
            base_agi.answer()
            base_agi.verbose("VoiceBot error")
            base_agi.sleep(1)
            base_agi.hangup()
        except Exception as e:
            logger.error(f"Error cleanup failed: {e}")

if __name__ == "__main__":
    main()
