



def collect_shorts_urls(channel_url):
    """Step 1: Collect all shorts URLs from channel"""
    driver = None
    try:
        logger.info(f"Starting collection of shorts from: {channel_url}")
        progress_text = st.empty()
        progress_bar = st.progress(0)
        table_container = st.empty()
        shorts_data = []

        # Initialize Chrome
        logger.info("Setting up Chrome driver...")
        progress_text.text("Initializing Chrome driver...")
        driver = setup_chrome_driver()

        logger.info("Loading channel URL...")
        progress_text.text("Loading channel URL...")
        driver.get(channel_url)
        time.sleep(5)

        logger.info("Starting scroll process...")
        progress_text.text("Scrolling to load more shorts...")
        last_height = driver.execute_script("return document.documentElement.scrollHeight")
        scroll_attempts = 0
        max_scroll_attempts = 10

        shorts_selectors = [
            "a.ytd-rich-grid-slim-media",
            "a#video-title-link",
            "a.ytd-grid-video-renderer"
        ]

        while scroll_attempts < max_scroll_attempts:
            logger.info(f"Scroll attempt {scroll_attempts + 1}/{max_scroll_attempts}")
            driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
            time.sleep(2)

            # Try each selector
            for selector in shorts_selectors:
                logger.info(f"Trying selector: {selector}")
                shorts = driver.find_elements(By.CSS_SELECTOR, selector)
                logger.info(f"Found {len(shorts)} elements with selector {selector}")

                for short in shorts:
                    try:
                        url = short.get_attribute('href')
                        title = short.get_attribute('title')
                        logger.info(f"Found element - URL: {url}, Title: {title}")

                        if url and title and '/shorts/' in url.lower():
                            new_entry = {
                                'title': sanitize_filename(title),
                                'url': url,
                                'status': '⏳'
                            }
                            if new_entry not in shorts_data:
                                shorts_data.append(new_entry)
                                logger.info(f"Added new short: {title}")
                                display_table(shorts_data, table_container, step=1)
                                progress_text.text(f"Found {len(shorts_data)} shorts...")
                    except Exception as e:
                        logger.error(f"Error processing short element: {str(e)}")
                        continue

            new_height = driver.execute_script("return document.documentElement.scrollHeight")
            progress_bar.progress((scroll_attempts + 1) / max_scroll_attempts)

            if new_height == last_height:
                logger.info("Reached end of page - no new content loaded")
                break
            last_height = new_height
            scroll_attempts += 1

        logger.info("Closing Chrome driver...")
        driver.quit()
        progress_text.empty()

        # Remove duplicates
        unique_shorts = list({s['url']: s for s in shorts_data}.values())
        logger.info(f"Final count: {len(unique_shorts)} unique shorts")
        return unique_shorts

    except Exception as e:
        logger.error(f"Error collecting shorts URLs: {str(e)}")
        if driver:
            driver.quit()
        raise


def process_shorts_channel(channel_url: str, config: dict):
    """Process a shorts channel in three steps"""
    try:
        logger.info("Starting shorts channel processing")
        logger.info(f"Channel URL: {channel_url}")

        # Create folder
        channel_name = get_channel_name(channel_url)
        logger.info(f"Channel name extracted: {channel_name}")
        folder_name = os.path.join(config['download_folder'], f"{channel_name}_shorts")
        logger.info(f"Creating folder: {folder_name}")
        create_folder(folder_name)

        # Step 1: Collect shorts URLs
        logger.info("Starting Step 1: Collecting Shorts URLs")
        st.subheader("Step 1: Collecting Shorts URLs")
        shorts_data = collect_shorts_urls(channel_url)

        if not shorts_data:
            logger.error("No shorts found in channel")
            st.error("No shorts found in channel")
            return False

        logger.info(f"Step 1 complete: Found {len(shorts_data)} shorts")
        st.success(f"Found {len(shorts_data)} shorts")

        # Step 2: Convert URLs
        logger.info("Starting Step 2: Converting URLs")
        st.subheader("Step 2: Converting URLs")
        converted_data = convert_shorts_urls(shorts_data)

        if not converted_data:
            logger.error("Failed to convert any URLs")
            st.error("Failed to convert any URLs")
            return False

        logger.info(f"Step 2 complete: Converted {len(converted_data)} URLs")
        st.success(f"Successfully converted {len(converted_data)} URLs")

        # Step 3: Download transcripts
        logger.info("Starting Step 3: Downloading Transcripts")
        st.subheader("Step 3: Downloading Transcripts")
        download_status = download_transcripts(converted_data, folder_name)

        successful = sum(1 for s in download_status if s['status'] == '✅')
        logger.info(f"Step 3 complete: Successfully downloaded {successful} transcripts")

        if successful > 0:
            st.success(f"Successfully downloaded {successful} out of {len(download_status)} transcripts")

            # Offer to save report
            if st.button("Download Summary Report"):
                report_path = os.path.join(folder_name, f"{channel_name}_report.csv")
                pd.DataFrame(download_status).to_csv(report_path, index=False)
                logger.info(f"Saved summary report to: {report_path}")
                st.success(f"Summary report saved to {report_path}")

            return True
        else:
            logger.error("Failed to download any transcripts")
            st.error("Failed to download any transcripts")
            return False

    except Exception as e:
        logger.error(f"Error processing shorts channel: {str(e)}")
        st.error(f"Error processing shorts channel: {str(e)}")
        return False


def render_url(channel_url: str, config: dict):
    """Process a channel URL"""
    logger.info(f"Starting render_url for channel: {channel_url}")
    success = process_shorts_channel(channel_url, config)
    logger.info(f"Processing completed with success: {success}")
    return success


def render(config):
    """Render method for channel shorts"""
    st.header("Channel Shorts Transcripts")
    channel_url = st.text_input("Enter YouTube Channel Shorts URL:")

    if st.button("Download Channel Shorts"):
        if channel_url:
            logger.info(f"Starting processing for URL: {channel_url}")
            with st.spinner("Processing shorts channel..."):
                success = render_url(channel_url, config)
                if not success:
                    logger.error("Processing failed")
                    st.error("Failed to process channel shorts. Check the logs for details.")
        else:
            logger.warning("No URL provided")
            st.warning("Please enter a valid YouTube Channel Shorts URL.")