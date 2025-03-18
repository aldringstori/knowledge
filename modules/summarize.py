# File: modules/summarize.py
import streamlit as st
import time
import re
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
from utils.logging_setup import logger
from modules.chat.model_manager import ModelManager


def extract_video_id(url):
    """Extract YouTube video ID from URL"""
    # Regular expressions for different YouTube URL formats
    patterns = [
        r'(?:youtube\.com\/watch\?v=)([^&\n]+)',  # Standard YouTube URL
        r'(?:youtu\.be\/)([^\?\n]+)',  # Shortened YouTube URL
        r'(?:youtube\.com\/embed\/)([^\?\n]+)',  # Embedded YouTube URL
        r'(?:youtube\.com\/v\/)([^\?\n]+)',  # Old style YouTube URL
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    return None


def get_video_transcript(video_id):
    """Get transcript for a YouTube video"""
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        # Try to get manually created transcript first
        try:
            transcript = transcript_list.find_manually_created_transcript(['en'])
        except:
            # Fall back to generated transcript
            try:
                transcript = transcript_list.find_generated_transcript(['en'])
            except:
                # Try any available transcript
                transcript = transcript_list.find_transcript(['en'])

        transcript_data = transcript.fetch()

        # Convert transcript to text
        formatter = TextFormatter()
        text_transcript = formatter.format_transcript(transcript_data)

        return text_transcript
    except Exception as e:
        logger.error(f"Error getting transcript: {str(e)}")
        return None


def summarize_transcript(transcript, model_name, summary_length="medium"):
    """Summarize transcript using LLM"""
    try:
        if not transcript:
            return "No transcript available to summarize."

        model_manager = ModelManager()
        model_manager.set_model(model_name)

        if not model_manager.initialize_model():
            return "Error: Could not initialize model for summarization."

        # Prepare the prompt based on summary length
        length_instructions = {
            "short": "Create a very concise summary in about 3-5 bullet points, focusing only on the most important points.",
            "medium": "Create a summary with 5-8 bullet points that covers the main topics and key insights.",
            "long": "Create a comprehensive summary with 8-12 bullet points that thoroughly covers all important topics and details."
        }

        # Calculate transcript length and chunk if necessary
        transcript_words = transcript.split()
        word_count = len(transcript_words)
        logger.info(f"Transcript length: {word_count} words")

        # For very long transcripts, we need to chunk and summarize in parts
        if word_count > 10000:
            logger.info("Transcript is very long, chunking for summary")
            chunk_size = 5000
            overlap = 500
            chunks = []

            for i in range(0, word_count, chunk_size - overlap):
                end = min(i + chunk_size, word_count)
                chunk = ' '.join(transcript_words[i:end])
                chunks.append(chunk)

            logger.info(f"Split transcript into {len(chunks)} chunks for processing")

            # Summarize each chunk
            chunk_summaries = []
            for i, chunk in enumerate(chunks):
                logger.info(f"Summarizing chunk {i + 1}/{len(chunks)}")
                chunk_prompt = f"""You are an expert at summarizing video content. Please summarize the following transcript chunk.

This is chunk {i + 1} of {len(chunks)}, so focus on extracting the key points from this section only.

{length_instructions[summary_length]}

TRANSCRIPT CHUNK:
{chunk}

SUMMARY:"""

                chunk_summary = model_manager.generate_response(
                    prompt=chunk_prompt,
                    max_length=1000,
                    temperature=0.3
                )
                chunk_summaries.append(chunk_summary)

            # Now create a combined summary from the chunk summaries
            combined_chunk_summaries = "\n\n".join(chunk_summaries)
            final_prompt = f"""You are an expert at summarizing video content. I have a long video transcript that was previously summarized in chunks.

Please create a cohesive final summary from these chunk summaries, removing any redundancy.

{length_instructions[summary_length]}

CHUNK SUMMARIES:
{combined_chunk_summaries}

FINAL SUMMARY:"""

            summary = model_manager.generate_response(
                prompt=final_prompt,
                max_length=2000,
                temperature=0.3
            )

        else:
            # For shorter transcripts, summarize directly
            prompt = f"""You are an expert at summarizing video content. Please summarize the following transcript into key points.

{length_instructions[summary_length]}

Format the summary as follows:
1. Start with a title or main topic of the video
2. Provide a one-sentence overview
3. List the key points as bullet points
4. End with a brief conclusion

TRANSCRIPT:
{transcript}

SUMMARY:"""

            summary = model_manager.generate_response(
                prompt=prompt,
                max_length=2000,
                temperature=0.3
            )

        return summary

    except Exception as e:
        logger.error(f"Error summarizing transcript: {str(e)}")
        return f"Error during summarization: {str(e)}"


def render(config):
    """Render the summarize interface"""
    st.header("YouTube Video Summarizer")

    # URL input
    url = st.text_input("Enter YouTube Video URL", key="summarize_url")

    # Model selection with preference for smaller models first
    model_manager = ModelManager()
    available_models = model_manager.get_available_models()

    if not available_models:
        available_models = ["deepseek-r1:8b", "deepseek-v2:latest"]

    # Sort models to prioritize smaller/faster ones
    def get_model_priority(model_name):
        if "3b" in model_name.lower() or "7b" in model_name.lower():
            return 0  # Highest priority
        elif "8b" in model_name.lower() or "r1" in model_name.lower():
            return 1
        elif "13b" in model_name.lower() or "14b" in model_name.lower():
            return 2
        elif "3.5" in model_name.lower():
            return 3
        else:
            return 4  # Lowest priority - big models

    sorted_models = sorted(available_models, key=get_model_priority)

    # Settings sidebar
    col1, col2 = st.columns([3, 1])

    with col1:
        model_name = st.selectbox(
            "Select Model",
            sorted_models,
            index=0,
            help="Choose a smaller model for faster results, larger models for potentially better quality"
        )

    with col2:
        summary_length = st.radio(
            "Summary Length",
            options=["short", "medium", "long"],
            index=1,
            help="Short: 3-5 bullet points, Medium: 5-8 bullet points, Long: 8-12 bullet points"
        )

    # Process button
    if st.button("Generate Summary", key="generate_summary_btn"):
        if not url:
            st.error("Please enter a YouTube URL")
            return

        video_id = extract_video_id(url)
        if not video_id:
            st.error("Invalid YouTube URL")
            return

        with st.spinner("Getting video transcript..."):
            transcript = get_video_transcript(video_id)

            if not transcript:
                st.error("Could not retrieve transcript. The video might not have captions available.")
                return

            # Show transcript length info
            word_count = len(transcript.split())
            st.info(f"Retrieved transcript with {word_count} words")

            if word_count > 15000:
                st.warning("This is a very long video. Summarization may take some time.")

            # Create expander for raw transcript
            with st.expander("View Raw Transcript"):
                st.text_area("Transcript", transcript, height=300)

            # Summarize the transcript
            summary_container = st.empty()
            summary_container.info("Generating summary... This may take a moment.")

            start_time = time.time()
            summary = summarize_transcript(transcript, model_name, summary_length)
            elapsed_time = time.time() - start_time

            summary_container.empty()
            st.success(f"Summary generated in {elapsed_time:.1f} seconds")

            # Display the summary
            st.subheader("Video Summary")
            st.markdown(summary)

            # Add copy button
            st.download_button(
                label="Download Summary",
                data=summary,
                file_name=f"youtube_summary_{video_id}.txt",
                mime="text/plain"
            )