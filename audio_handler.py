import whisperx
import gc
import torch
import os
import logging
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from whisperx.diarize import DiarizationPipeline

def check_ffmpeg_installed():
    """Checks if FFmpeg is installed and accessible in the system's PATH."""
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        return True
    except FileNotFoundError:
        return False
    except subprocess.CalledProcessError:
        # ffmpeg is found, but maybe -version command returned non-zero, still treat as found.
        return True

def transcribe_audio(audio_file_path, output_dir="library", include_timestamps=False):
    """
    Transcribe audio file using WhisperX with diarization.
    
    Args:
        audio_file_path: Path to the audio file
        output_dir: Directory to save output markdown file (default: library)
        include_timestamps: Whether to include timestamps in output
    
    Returns:
        Path to the generated markdown file
    """
    # Check for ffmpeg
    if not check_ffmpeg_installed():
        raise FileNotFoundError(
            "FFmpeg is not found. Please install FFmpeg and ensure it's added to your system's PATH. "
            "Refer to https://ffmpeg.org/download.html for installation instructions."
        )
    # Get HuggingFace token from environment
    hf_token = os.getenv("HUGGINGFACE_TOKEN")
    if not hf_token:
        raise ValueError("HUGGINGFACE_TOKEN not found in .env file")
    
    # Setup
    device = "cuda" if torch.cuda.is_available() else "cpu"
    batch_size = 16  # reduce if low on GPU mem
    compute_type = "float16" if device == "cuda" else "int8"
    
    print(f"Using device: {device}")
    print(f"Processing audio file: {audio_file_path}")
    
    # 1. Transcribe with original whisper (batched)
    print("\n[1/4] Loading WhisperX model...")
    model = whisperx.load_model("large-v2", device, compute_type=compute_type)
    
    print("[2/4] Transcribing audio...")
    audio = whisperx.load_audio(audio_file_path)
    result = model.transcribe(audio, batch_size=batch_size)
    
    # Delete model if low on GPU resources
    gc.collect()
    if device == "cuda":
        torch.cuda.empty_cache()
    del model
    
    # 2. Align whisper output
    print("[3/4] Aligning transcription...")
    model_a, metadata = whisperx.load_align_model(language_code=result["language"], device=device)
    result = whisperx.align(result["segments"], model_a, metadata, audio, device, return_char_alignments=False)
    
    # Delete model if low on GPU resources
    gc.collect()
    if device == "cuda":
        torch.cuda.empty_cache()
    del model_a
    
    # 3. Assign speaker labels
    print("[4/4] Performing diarization...")
    diarize_model = DiarizationPipeline(use_auth_token=hf_token, device=device)
    diarize_segments = diarize_model(audio)
    result = whisperx.assign_word_speakers(diarize_segments, result)
    
    # Clean up
    gc.collect()
    if device == "cuda":
        torch.cuda.empty_cache()
    
    # 4. Generate markdown output
    print("\nGenerating markdown file...")
    output_path = generate_markdown(audio_file_path, result, output_dir, include_timestamps)
    print(f"✓ Transcription complete! Output saved to: {output_path}")
    
    return output_path

def generate_markdown(audio_file_path, result, output_dir, include_timestamps=False):
    """
    Generate a markdown file from transcription results.
    
    Args:
        audio_file_path: Original audio file path
        result: WhisperX result dictionary
        output_dir: Directory to save markdown file
        include_timestamps: Whether to include timestamps in output
    
    Returns:
        Path to the generated markdown file
    """
    # Create output directory if it doesn't exist
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Generate output filename
    audio_filename = Path(audio_file_path).stem
    # timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # output_filename = f"{audio_filename}_transcript_{timestamp}.md"
    output_filename = f"{audio_filename}.md"
    output_path = Path(output_dir) / output_filename
    
    # Write markdown content
    with open(output_path, 'w', encoding='utf-8') as f:
        # Header
        f.write(f"# Transcription: {Path(audio_file_path).name}\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**Language:** {result.get('language', 'Unknown')}\n\n")
        f.write("---\n\n")
        
        # Transcription with speakers
        f.write("## Transcript\n\n")
        
        current_speaker = None
        for segment in result["segments"]:
            speaker = segment.get("speaker", "Unknown")
            text = segment["text"].strip()
            
            # Add speaker header if speaker changes
            if speaker != current_speaker:
                # if include_timestamps:
                #     start_time = format_timestamp(segment["start"])
                #     f.write(f"\n**{speaker}** `[{start_time}]`\n\n")
                # else:
                f.write(f"\n**{speaker}**\n\n")
                current_speaker = speaker
            
            f.write(f"{text}\n\n")
        
        # Detailed segments table (only if timestamps are enabled)
        # if include_timestamps:
        #     f.write("\n---\n\n")
        #     f.write("## Detailed Segments\n\n")
        #     f.write("| Start | End | Speaker | Text |\n")
        #     f.write("|-------|-----|---------|------|\n")
        #     
        #     for segment in result["segments"]:
        #         start = format_timestamp(segment["start"])
        #         end = format_timestamp(segment["end"])
        #         speaker = segment.get("speaker", "Unknown")
        #         text = segment["text"].strip().replace("|", "\\|")  # Escape pipes for markdown
        #         f.write(f"| {start} | {end} | {speaker} | {text} |\n")
    
    return output_path

# def format_timestamp(seconds):
#     """Convert seconds to MM:SS format."""
#     minutes = int(seconds // 60)
#     secs = int(seconds % 60)
#     return f"{minutes:02d}:{secs:02d}"

def main():
    # Simple argument parsing - only accepts audio file path
    if len(sys.argv) < 2:
        logging.error("No file path provided as argument")
        print("Error: No file path provided", file=sys.stderr)
        sys.exit(1)
    
    audio_file = sys.argv[1]

    # Validate audio file exists
    if not os.path.exists(audio_file):
        logging.error(f"Audio file not found: {audio_file}")
        sys.exit(1)

    # Determine output directory (library folder in same directory as script)
    script_dir = Path(__file__).parent
    output_dir = script_dir / "library"
    
    # Process audio
    try:
        output_path = transcribe_audio(audio_file, str(output_dir), include_timestamps=False)

        logging.info("=" * 60)
        logging.info("Audio Handler Completed Successfully")
        logging.info("=" * 60)
        sys.exit(0)
    except Exception as e:
        logging.error("=" * 60)
        logging.error(f"Audio Handler Failed: {e}")
        logging.error("=" * 60)
        logging.exception("Full traceback:")
        logging.error(f"Error processing file: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
