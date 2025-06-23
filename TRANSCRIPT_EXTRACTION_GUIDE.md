# YouTube Transcript Extraction Guide

This guide documents the step-by-step process for extracting transcripts from YouTube videos using Selenium web automation.

## Single Video Transcript Extraction

### Overview
For single video downloads, we extract transcripts directly from the YouTube video page without loading/playing the video.

### Example Video URL
```
https://www.youtube.com/watch?v=Mo9l1mM-Ogs
```

### Step-by-Step Process

#### Step 1: Click "Show More" Button
Look for and click the expand button to show more video description content.

**Target Element:**
```html
<tp-yt-paper-button id="expand" class="button style-scope ytd-text-inline-expander" 
                    style-target="host" role="button" tabindex="0" animated="" 
                    elevation="0" aria-disabled="false" style="left: 4px;">
    ...mais
</tp-yt-paper-button>
```

**Selector:** `tp-yt-paper-button[id="expand"]` or `#expand`

#### Step 2: Click "Show Transcript" Button
After expanding, look for and click the transcript button to reveal the transcript panel.

**Target Element:**
```html
<div aria-hidden="true" class="yt-spec-touch-feedback-shape yt-spec-touch-feedback-shape--touch-response">
    <div class="yt-spec-touch-feedback-shape__stroke"></div>
    <div class="yt-spec-touch-feedback-shape__fill"></div>
</div>
```

**Selector:** Button with text containing "transcript" or "transcrição"

#### Step 3: Extract Transcript Text
Extract text from all transcript segments, removing timestamps and concatenating in sequential order.

**Container Element:**
```html
<ytd-transcript-segment-list-renderer class="style-scope ytd-transcript-search-panel-renderer">
    <div id="segments-container" class="style-scope ytd-transcript-segment-list-renderer active">
        <!-- Individual transcript segments -->
    </div>
</ytd-transcript-segment-list-renderer>
```

**Individual Segment Structure:**
```html
<ytd-transcript-segment-renderer class="style-scope ytd-transcript-segment-list-renderer" rounded-container="">
    <div class="segment style-scope ytd-transcript-segment-renderer" role="button" tabindex="0">
        <!-- Timestamp (ignore) -->
        <div class="segment-start-offset style-scope ytd-transcript-segment-renderer">
            <div class="segment-timestamp style-scope ytd-transcript-segment-renderer">0:04</div>
        </div>
        
        <!-- Text content (extract this) -->
        <yt-formatted-string class="segment-text style-scope ytd-transcript-segment-renderer">
            Cala a boca não fala nada PR ninguém só
        </yt-formatted-string>
    </div>
</ytd-transcript-segment-renderer>
```

### Selectors Summary

| Step | Element | CSS Selector |
|------|---------|-------------|
| 1 | Expand button | `tp-yt-paper-button[id="expand"]` |
| 2 | Transcript button | `button:contains("transcript")` or similar |
| 3 | Transcript segments | `yt-formatted-string.segment-text` |

### Expected Output

The transcript should be extracted as plain text, removing timestamps and combining all segments sequentially:

```
Cala a boca não fala nada PR ninguém só faz para com essa de querer aprovação e motivação dos outros é você e Deus quando você fica em silêncio o...
```

## Environment Configuration

These selectors can be configured via environment variables in `.env`:

```bash
# Transcript Extraction Selectors
YOUTUBE_SHOW_MORE_BUTTON_CLASS=tp-yt-paper-button[id="expand"]
YOUTUBE_SHOW_TRANSCRIPT_BUTTON_CLASS=//button[contains(text(), "Show transcript")]
YOUTUBE_TRANSCRIPT_PANEL_CLASS=ytd-transcript-search-panel-renderer
YOUTUBE_TRANSCRIPT_SEGMENTS_CLASS=yt-formatted-string.segment-text
```

## Error Handling

1. **Element not found**: Try alternative selectors
2. **No transcript available**: Fall back to YouTube Transcript API
3. **Language issues**: Handle different languages for button text
4. **Loading delays**: Implement appropriate wait times between steps

## Notes

- Always wait for elements to be clickable before interaction
- Handle dynamic loading of transcript content
- Consider video language for button text variations
- Implement retry mechanism for failed extractions