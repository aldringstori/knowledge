import streamlit as st
import os
from utils.config import get_transcript_files

def render(config):
    """Render the summarize tab interface"""
    st.header("🔍 Summarize Transcripts")
    
    st.warning("⚠️ Summarization feature temporarily disabled - LLM functionality has been removed.")
    st.info("This feature requires an LLM model to generate summaries. The summarization functionality has been removed as part of the simplification.")
    
    # Get transcript files for display
    transcript_files = get_transcript_files()
    
    if transcript_files:
        st.subheader("📁 Available Transcript Files")
        for file_path in transcript_files:
            with st.expander(f"📄 {os.path.basename(file_path)}"):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    st.text_area("Content Preview", content[:500] + "..." if len(content) > 500 else content, height=200, disabled=True)
                except Exception as e:
                    st.error(f"Error reading file: {str(e)}")
    else:
        st.info("No transcript files found. Please download some content first.")