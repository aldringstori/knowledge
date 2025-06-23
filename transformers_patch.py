"""
Monkey patch to add backward compatibility for transformers
"""
import sys
import importlib

# Only apply the patch if transformers is already imported
if 'transformers.utils' in sys.modules or 'transformers' in sys.modules:
    try:
        # Import the transformers utils module
        import transformers.utils
        import torch

        # Check if the functions are missing and add them

        # 1. is_torch_onnx_dict_inputs_support_available
        if not hasattr(transformers.utils, 'is_torch_onnx_dict_inputs_support_available'):
            print("Applying transformers.utils patch: adding is_torch_onnx_dict_inputs_support_available")

            # Add the missing function
            def is_torch_onnx_dict_inputs_support_available():
                """
                Backward compatibility function to check for ONNX dictionary inputs support
                """
                # This is a simple fallback implementation
                return False

            # Add the function to the transformers.utils module
            transformers.utils.is_torch_onnx_dict_inputs_support_available = is_torch_onnx_dict_inputs_support_available

        # 2. torch_version
        if not hasattr(transformers.utils, 'torch_version'):
            print("Applying transformers.utils patch: adding torch_version")

            # Extract torch version and add as a function
            def torch_version():
                """
                Get torch version as a tuple
                """
                try:
                    # Try to get the version from torch
                    version = torch.__version__
                    # Convert to tuple of integers, e.g. "1.13.1" -> (1, 13, 1)
                    return tuple(int(x) for x in version.split('.')[:3])
                except (AttributeError, ValueError):
                    # Fallback to a version that should work with transformers 4.26.0
                    return (1, 13, 1)

            # Add the function to the transformers.utils module
            transformers.utils.torch_version = torch_version

        # Check if define_import_structure is missing too
        if not hasattr(transformers.utils.import_utils, 'define_import_structure'):
            print("Applying transformers.utils patch: adding define_import_structure")

            # Add a minimal implementation of define_import_structure
            def define_import_structure(module_name, **kwargs):
                """
                Simple placeholder for define_import_structure
                """
                pass

            # Add the function to the module
            transformers.utils.import_utils.define_import_structure = define_import_structure

    except ImportError as e:
        print(f"Warning: Could not patch transformers.utils, error: {e}")