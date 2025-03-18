import streamlit as st
import os
from utils.logging_setup import logger
from utils.common import save_transcript_to_text
import PyPDF2
from docx import Document


def render(config):
    """Render the file converter tab."""
    st.header("File Converter")
    file_type = st.radio("Select file type to convert:", ("PDF", "DOCX"))
    uploaded_file = st.file_uploader(f"Choose a {file_type} file", type=[file_type.lower()])

    if uploaded_file is not None:
        if st.button("Convert to Text"):
            with st.spinner("Converting file..."):
                logger.info(f"Converting uploaded {file_type} file to text.")

                try:
                    if file_type == "PDF":
                        pdf_reader = PyPDF2.PdfReader(uploaded_file)
                        text_content = []
                        for page in pdf_reader.pages:
                            text_content.append(page.extract_text())
                    else:  # DOCX
                        doc = Document(uploaded_file)
                        text_content = [para.text for para in doc.paragraphs]

                    filename = os.path.splitext(uploaded_file.name)[0]
                    save_path = save_transcript_to_text(
                        "\n".join(text_content),
                        filename,
                        config['download_folder']
                    )

                    if save_path:
                        st.success(f"File converted and saved to {save_path}")
                        logger.info(f"File converted and saved to {save_path}")
                    else:
                        st.error("Failed to convert and save the file.")
                        logger.error("Failed to convert and save the file.")

                except Exception as e:
                    error_msg = f"Error converting file: {str(e)}"
                    logger.error(error_msg)
                    st.error(error_msg)