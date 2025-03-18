"""
Monkey patch to add backward compatibility for huggingface_hub
"""
import sys
import os
import importlib

# Only apply the patch if huggingface_hub is already imported
if 'huggingface_hub' in sys.modules:
    import huggingface_hub

    # Check if cached_download is missing
    if not hasattr(huggingface_hub, 'cached_download'):
        # Map the old function name to the new one if available
        if hasattr(huggingface_hub, 'hf_hub_download'):
            print("Applying huggingface_hub monkey patch: cached_download -> hf_hub_download")
            huggingface_hub.cached_download = huggingface_hub.hf_hub_download
        else:
            # Fallback implementation if even the new function is missing
            print("Applying huggingface_hub monkey patch with custom implementation")


            def cached_download(*args, **kwargs):
                """
                Backward compatibility function that mimics the old cached_download
                """
                # Implement minimal functionality or call other existing functions
                kwargs.pop('use_auth_token', None)  # Remove if it exists 
                # Here we assume hf_hub_download exists as a replacement
                if hasattr(huggingface_hub, 'hf_hub_download'):
                    return huggingface_hub.hf_hub_download(*args, **kwargs)
                raise ImportError("Neither cached_download nor hf_hub_download found in huggingface_hub")


            huggingface_hub.cached_download = cached_download