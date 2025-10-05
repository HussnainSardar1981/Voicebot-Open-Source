#!/usr/bin/env python3
"""
Persistent Model Worker Service - FastAPI HTTP Server
Keeps Whisper-large and Kokoro models loaded on H100 GPU for instant responses
Eliminates per-call model loading delays and provides HTTP API for AGI clients
"""

import os
import sys
import time
import uuid
import logging
import subprocess
import torch
import whisper
import soundfile as sf
import numpy as np
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from kokoro import KPipeline
import uvicorn

# Add project directory to path
sys.path.insert(0, "/home/aiadmin/netovo_voicebot/kokora")
from config import setup_logging, WHISPER_CONFIG, KOKORO_CONFIG

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="NETOVO VoiceBot Model Worker", version="1.0.0")

# Global model instances - loaded once, kept persistent
whisper_model = None
kokoro_pipeline = None
models_loaded = False

# Request/Response models
class SynthesizeRequest(BaseModel):
    text: str
    voice: str = "af_heart"

class SynthesizeResponse(BaseModel):
    path: str
    duration: float

class TranscribeRequest(BaseModel):
    path: str

class TranscribeResponse(BaseModel):
    text: str
    confidence: float

class HealthResponse(BaseModel):
    status: str
    models_loaded: bool
    gpu_available: bool
    uptime: float

# Service start time for uptime calculation
start_time = time.time()

def load_models():
    """Load all models once at startup - keeps them hot on GPU"""
    global whisper_model, kokoro_pipeline, models_loaded

    logger.info("🔥 Loading models for persistent service...")
    load_start = time.time()

    try:
        # Check GPU availability
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device: {device}")

        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
            logger.info(f"GPU: {gpu_name} ({gpu_memory:.1f}GB)")

        # Load Whisper-large (most resource intensive first)
        logger.info("Loading Whisper-large model...")
        whisper_model = whisper.load_model(WHISPER_CONFIG["model"])

        # Move to GPU with FP16 for H100 optimization
        if device == "cuda":
            whisper_model = whisper_model.to(device)
            logger.info("Whisper model moved to GPU")

        # Load Kokoro TTS pipeline
        logger.info("Loading Kokoro TTS pipeline...")
        if device == "cuda":
            kokoro_pipeline = KPipeline(lang_code='a', device=device)
        else:
            kokoro_pipeline = KPipeline(lang_code='a')

        load_time = time.time() - load_start
        models_loaded = True
        logger.info(f"✅ All models loaded in {load_time:.1f}s - Service ready!")

        return True

    except Exception as e:
        logger.error(f"Model loading failed: {e}")
        models_loaded = False
        return False

@app.on_event("startup")
async def startup_event():
    """Load models when service starts"""
    logger.info("🚀 Starting NETOVO Model Worker Service...")
    success = load_models()
    if not success:
        logger.error("Failed to load models - service may not function properly")

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy" if models_loaded else "unhealthy",
        models_loaded=models_loaded,
        gpu_available=torch.cuda.is_available(),
        uptime=time.time() - start_time
    )

@app.post("/synthesize", response_model=SynthesizeResponse)
async def synthesize_speech(request: SynthesizeRequest):
    """Convert text to speech using Kokoro TTS"""
    if not models_loaded or kokoro_pipeline is None:
        raise HTTPException(status_code=503, detail="Models not loaded")

    try:
        logger.info(f"TTS request: '{request.text[:50]}...' voice={request.voice}")
        synth_start = time.time()

        # Apply pronunciation corrections (from original client)
        text = request.text.replace("NETOVO", "NET-OH-VOH")
        text = text.replace("Netovo", "Net-oh-voh")
        text = text.replace("netovo", "net-oh-voh")

        # Generate audio using Kokoro
        generation = kokoro_pipeline(text, voice=request.voice)
        audio_chunks = [chunk for _, _, chunk in generation]
        audio = np.concatenate(audio_chunks)

        # Save as 24kHz WAV first
        temp_24k = f"/tmp/kokoro_24k_{uuid.uuid4().hex[:8]}.wav"
        sf.write(temp_24k, audio, 24000, subtype="PCM_16")

        # Convert to 8kHz mono for Asterisk compatibility
        final_8k = f"/tmp/kokoro_8k_{uuid.uuid4().hex[:8]}.wav"
        sox_cmd = [
            "sox", temp_24k,
            "-r", "8000",  # 8kHz sample rate
            "-c", "1",     # Mono
            "-b", "16",    # 16-bit
            "-e", "signed-integer",  # PCM signed
            final_8k
        ]

        subprocess.run(sox_cmd, check=True, capture_output=True)

        # Cleanup temp file
        os.unlink(temp_24k)

        duration = time.time() - synth_start
        logger.info(f"TTS completed in {duration:.2f}s -> {final_8k}")

        return SynthesizeResponse(path=final_8k, duration=duration)

    except Exception as e:
        logger.error(f"TTS synthesis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Synthesis failed: {str(e)}")

@app.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_speech(request: TranscribeRequest):
    """Convert speech to text using Whisper"""
    if not models_loaded or whisper_model is None:
        raise HTTPException(status_code=503, detail="Models not loaded")

    try:
        logger.info(f"ASR request: {request.path}")
        transcribe_start = time.time()

        # Ensure file exists
        if not os.path.exists(request.path):
            raise HTTPException(status_code=404, detail="Audio file not found")

        # Convert to 16kHz mono for Whisper (if needed)
        temp_16k = f"/tmp/whisper_16k_{uuid.uuid4().hex[:8]}.wav"
        sox_cmd = [
            "sox", request.path,
            "-r", "16000",  # 16kHz for Whisper
            "-c", "1",      # Mono
            "-b", "16",     # 16-bit
            "-e", "signed-integer",
            temp_16k
        ]

        subprocess.run(sox_cmd, check=True, capture_output=True)

        # Transcribe with optimized settings for H100
        result = whisper_model.transcribe(
            temp_16k,
            fp16=True,  # Use FP16 for H100 speed
            language=WHISPER_CONFIG["language"],
            task="transcribe",
            beam_size=5,
            best_of=5,
            temperature=0.0,  # Deterministic output
            no_speech_threshold=0.6,
            logprob_threshold=-1.0
        )

        # Cleanup temp file
        os.unlink(temp_16k)

        text = (result.get("text", "") or "").strip()

        # Extract confidence from segments if available
        confidence = 0.0
        if result.get("segments"):
            confidences = [seg.get("avg_logprob", 0.0) for seg in result["segments"]]
            confidence = sum(confidences) / len(confidences) if confidences else 0.0

        duration = time.time() - transcribe_start
        logger.info(f"ASR completed in {duration:.2f}s: '{text[:50]}...'")

        return TranscribeResponse(text=text, confidence=confidence)

    except Exception as e:
        logger.error(f"ASR transcription failed: {e}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "NETOVO VoiceBot Model Worker",
        "status": "running" if models_loaded else "loading",
        "version": "1.0.0",
        "endpoints": ["/health", "/synthesize", "/transcribe"]
    }

def main():
    """Main entry point"""
    logger.info("🚀 Starting NETOVO Model Worker Service")

    # Run FastAPI with uvicorn
    uvicorn.run(
        app,
        host="127.0.0.1",  # Only local access for security
        port=8777,         # Custom port for model worker
        log_level="info",
        access_log=True
    )

if __name__ == "__main__":
    main()