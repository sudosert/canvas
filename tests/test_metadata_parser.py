"""Tests for metadata parser ComfyUI prompt extraction."""
import json
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.metadata_parser import MetadataParser
from src.models.image_data import ImageMetadata


def test_comfyui_prompt_extraction():
    """Test extracting prompts from ComfyUI metadata with different node configurations."""
    
    # Load test data from rawdata.json
    with open('examples/rawdata.json', 'r') as f:
        raw_data = json.load(f)
    
    # The prompt data is in the "prompt" field as a JSON string
    prompt_data = json.loads(raw_data['prompt'])
    
    # Also load the workflow data which contains widgets_values
    workflow_data = json.loads(raw_data.get('workflow', '{}'))
    workflow_nodes = workflow_data.get('nodes', [])
    
    # Build a mapping of node_id -> widgets_values from workflow
    node_widgets = {}
    for node in workflow_nodes:
        node_id = str(node.get('id', ''))
        widgets = node.get('widgets_values', [])
        if node_id and widgets:
            node_widgets[node_id] = widgets
    
    # Merge widgets_values into prompt_data nodes
    for node_id, node_data in prompt_data.items():
        if isinstance(node_data, dict) and node_id in node_widgets:
            node_data['widgets_values'] = node_widgets[node_id]  # Add/overwrite widgets_values from workflow
    
    print("=" * 80)
    print("Testing ComfyUI Prompt Extraction")
    print("=" * 80)
    
    # Print all nodes with their IDs and titles for reference
    print("\n--- Available Nodes in Prompt Data ---")
    for node_id, node_data in sorted(prompt_data.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 9999):
        if isinstance(node_data, dict):
            meta = node_data.get('_meta', {})
            title = meta.get('title', 'N/A')
            class_type = node_data.get('class_type', 'N/A')
            widgets = node_data.get('widgets_values', [])
            print(f"Node ID: {node_id:>3} | Title: '{title}' | Type: {class_type}")
            if widgets:
                # Show first widget value (truncated if too long)
                first_widget = widgets[0] if widgets else None
                if isinstance(first_widget, list) and first_widget:
                    first_widget = first_widget[0]
                if isinstance(first_widget, str):
                    preview = first_widget[:80] + "..." if len(first_widget) > 80 else first_widget
                    print(f"         | Widget[0]: {preview}")  # Now this should show the actual prompt text!  
    
    print("\n" + "=" * 80)
    print("Testing Node ID '374' (Full Prompt node)")
    print("=" * 80)
    
    # Create a metadata object and test extraction
    metadata = ImageMetadata(file_path="test.png", file_name="test.png")
    metadata.source = "comfyui"
    
    # Test 1: Extract with node ID "374"
    print("\n--- Test 1: Extract by Node ID '374' ---")
    MetadataParser._extract_comfyui_prompt(prompt_data, metadata)
    print(f"Extracted Prompt: {metadata.prompt[:200]}..." if len(metadata.prompt) > 200 else f"Extracted Prompt: {metadata.prompt}")
    print(f"Expected: Should contain 'embedding:Illustrious/lazypos'")
    
    # Check if the prompt was extracted correctly
    if "embedding:Illustrious/lazypos" in metadata.prompt:
        print("✓ PASS: Prompt extracted successfully via node ID")
    else:
        print("✗ FAIL: Prompt not found or incorrect")
    
    # Test 2: Check node "374" structure directly
    print("\n--- Test 2: Direct Node Structure Check ---")
    node_374 = prompt_data.get("374")
    if node_374:
        print(f"Node 374 exists: {type(node_374)}")
        print(f"Node 374 keys: {list(node_374.keys())}")
        meta = node_374.get('_meta', {})
        print(f"Node 374 title: '{meta.get('title', 'N/A')}'")
        widgets = node_374.get('widgets_values', [])
        print(f"Node 374 widgets_values: {type(widgets)}")
        if widgets:
            print(f"  widgets_values[0] type: {type(widgets[0])}")
            if isinstance(widgets[0], list):
                print(f"  widgets_values[0][0] type: {type(widgets[0][0])}")
                print(f"  widgets_values[0][0] preview: {str(widgets[0][0])[:100]}...")
    else:
        print("✗ FAIL: Node 374 not found in prompt data!")
    
    # Test 3: Extract by title "Full Prompt"
    print("\n--- Test 3: Extract by Title 'Full Prompt' ---")
    metadata2 = ImageMetadata(file_path="test.png", file_name="test.png")
    metadata2.source = "comfyui"
    
    # Temporarily modify settings to use title only
    from PyQt6.QtCore import QSettings
    settings = QSettings("SDImageViewer", "Settings")
    original_id = settings.value("comfyui_primary_node_id", "")
    settings.setValue("comfyui_primary_node_id", "")  # Clear ID to force title search
    
    MetadataParser._extract_comfyui_prompt(prompt_data, metadata2)
    
    # Restore original setting
    settings.setValue("comfyui_primary_node_id", original_id)
    
    print(f"Extracted Prompt: {metadata2.prompt[:200]}..." if len(metadata2.prompt) > 200 else f"Extracted Prompt: {metadata2.prompt}")
    
    print("=" * 80)
    print("Testing ComfyUI Prompt Extraction")
    print("=" * 80)
    
    # Print all nodes with their IDs and titles for reference
    print("\n--- Available Nodes in Prompt Data ---")
    for node_id, node_data in sorted(prompt_data.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 9999):
        if isinstance(node_data, dict):
            meta = node_data.get('_meta', {})
            title = meta.get('title', 'N/A')
            class_type = node_data.get('class_type', 'N/A')
            widgets = node_data.get('widgets_values', [])
            print(f"Node ID: {node_id:>3} | Title: '{title}' | Type: {class_type}")
            if widgets:
                # Show first widget value (truncated if too long)
                first_widget = widgets[0] if widgets else None
                if isinstance(first_widget, list) and first_widget:
                    first_widget = first_widget[0]
                if isinstance(first_widget, str):
                    preview = first_widget[:80] + "..." if len(first_widget) > 80 else first_widget
                    print(f"         | Widget[0]: {preview}")
    
    print("\n" + "=" * 80)
    print("Testing Node ID '374' (Full Prompt node)")
    print("=" * 80)
    
    # Create a metadata object and test extraction
    metadata = ImageMetadata(file_path="test.png", file_name="test.png")
    metadata.source = "comfyui"
    
    # Test 1: Extract with node ID "374"
    print("\n--- Test 1: Extract by Node ID '374' ---")
    MetadataParser._extract_comfyui_prompt(prompt_data, metadata)
    print(f"Extracted Prompt: {metadata.prompt[:200]}..." if len(metadata.prompt) > 200 else f"Extracted Prompt: {metadata.prompt}")
    print(f"Expected: Should contain 'embedding:Illustrious/lazypos'")
    
    # Check if the prompt was extracted correctly
    if "embedding:Illustrious/lazypos" in metadata.prompt:
        print("✓ PASS: Prompt extracted successfully via node ID")
    else:
        print("✗ FAIL: Prompt not found or incorrect")
    
    # Test 2: Check node "374" structure directly
    print("\n--- Test 2: Direct Node Structure Check ---")
    node_374 = prompt_data.get("374")
    if node_374:
        print(f"Node 374 exists: {type(node_374)}")
        print(f"Node 374 keys: {list(node_374.keys())}")
        meta = node_374.get('_meta', {})
        print(f"Node 374 title: '{meta.get('title', 'N/A')}'")
        widgets = node_374.get('widgets_values', [])
        print(f"Node 374 widgets_values: {type(widgets)}")
        if widgets:
            print(f"  widgets_values[0] type: {type(widgets[0])}")
            if isinstance(widgets[0], list):
                print(f"  widgets_values[0][0] type: {type(widgets[0][0])}")
                print(f"  widgets_values[0][0] preview: {str(widgets[0][0])[:100]}...")
    else:
        print("✗ FAIL: Node 374 not found in prompt data!")
    
    # Test 3: Extract by title "Full Prompt"
    print("\n--- Test 3: Extract by Title 'Full Prompt' ---")
    metadata2 = ImageMetadata(file_path="test.png", file_name="test.png")
    metadata2.source = "comfyui"
    
    # Temporarily modify settings to use title only
    from PyQt6.QtCore import QSettings
    settings = QSettings("SDImageViewer", "Settings")
    original_id = settings.value("comfyui_primary_node_id", "")
    settings.setValue("comfyui_primary_node_id", "")  # Clear ID to force title search
    
    MetadataParser._extract_comfyui_prompt(prompt_data, metadata2)
    
    # Restore original setting
    settings.setValue("comfyui_primary_node_id", original_id)
    
    print(f"Extracted Prompt: {metadata2.prompt[:200]}..." if len(metadata2.prompt) > 200 else f"Extracted Prompt: {metadata2.prompt}")
    
    if "embedding:Illustrious/lazypos" in metadata2.prompt:
        print("✓ PASS: Prompt extracted successfully via title")
    else:
        print("✗ FAIL: Prompt not found or incorrect via title")
    
    print("\n" + "=" * 80)
    print("Testing Complete")
    print("=" * 80)


def test_node_374_structure():
    """Specifically test the structure of node 374 from full_prompt_node.json."""
    
    print("\n" + "=" * 80)
    print("Testing Node 374 Structure from full_prompt_node.json")
    print("=" * 80)
    
    with open('examples/full_prompt_node.json', 'r') as f:
        node_data = json.load(f)
    
    print(f"\nNode ID from file: {node_data.get('id')}")
    print(f"Node Title: {node_data.get('title')}")
    print(f"Node Type: {node_data.get('type')}")
    
    widgets_values = node_data.get('widgets_values', [])
    print(f"\nwidgets_values: {widgets_values}")
    print(f"widgets_values type: {type(widgets_values)}")
    
    if widgets_values:
        print(f"\nwidgets_values[0] type: {type(widgets_values[0])}")
        if isinstance(widgets_values[0], list):
            print(f"widgets_values[0]: {widgets_values[0]}")
            if widgets_values[0]:
                print(f"widgets_values[0][0]: {widgets_values[0][0][:100]}...")
        elif isinstance(widgets_values[0], str):
            print(f"widgets_values[0]: {widgets_values[0][:100]}...")
    
    # Simulate extraction
    print("\n--- Simulating Extraction ---")
    prompt_text = None
    if widgets_values and len(widgets_values) > 0:
        prompt_text = widgets_values[0]
        if isinstance(prompt_text, list) and len(prompt_text) > 0:
            prompt_text = prompt_text[0]
        if isinstance(prompt_text, str):
            prompt_text = prompt_text.replace('\\"', '"').replace("\\'", "'")
    
    print(f"Extracted text: {prompt_text[:200] if prompt_text else 'None'}...")
    
    if prompt_text and "embedding:Illustrious/lazypos" in prompt_text:
        print("✓ PASS: Extraction simulation successful")
    else:
        print("✗ FAIL: Extraction simulation failed")


if __name__ == "__main__":
    test_node_374_structure()
    test_comfyui_prompt_extraction()
