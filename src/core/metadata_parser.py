"""Metadata parser for Stable Diffusion images (A1111 and ComfyUI)."""
import json
import re
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from PIL import Image
from PIL.ExifTags import TAGS

from ..models.image_data import ImageMetadata


class MetadataParser:
    """Parser for extracting Stable Diffusion metadata from images."""
    
    @staticmethod
    def parse_image(file_path: str) -> ImageMetadata:
        """
        Parse metadata from an image file.
        
        Args:
            file_path: Path to the image file
            
        Returns:
            ImageMetadata object with extracted information
        """
        path = Path(file_path)
        
        # Initialize metadata with basic file info
        metadata = ImageMetadata(
            file_path=str(path.absolute()),
            file_name=path.name
        )
        
        try:
            # Get file stats
            stat = path.stat()
            metadata.file_size = stat.st_size
            metadata.modified_time = stat.st_mtime
            
            # Open image to get dimensions
            with Image.open(path) as img:
                metadata.width, metadata.height = img.size
                
                # Parse based on file type
                if path.suffix.lower() in ['.png']:
                    MetadataParser._parse_png_metadata(img, metadata)
                elif path.suffix.lower() in ['.jpg', '.jpeg']:
                    MetadataParser._parse_jpeg_metadata(img, metadata)
                    
        except Exception as e:
            metadata.raw_metadata = f"Error parsing: {str(e)}"
            
        return metadata
    
    @staticmethod
    def _parse_png_metadata(img: Image.Image, metadata: ImageMetadata) -> None:
        """Parse PNG text chunks for metadata."""
        if not hasattr(img, 'text') and not hasattr(img, 'info'):
            return
            
        # Get text chunks from PNG
        text_data = getattr(img, 'text', {}) or img.info.get('text', {})
        
        # Store raw metadata
        metadata.raw_metadata = json.dumps(text_data, indent=2)
        
        # Check for A1111 format (parameters key)
        if 'parameters' in text_data:
            metadata.source = "a1111"
            MetadataParser._parse_a1111_parameters(text_data['parameters'], metadata)
            return
            
        # Check for ComfyUI format (workflow and prompt keys)
        if 'workflow' in text_data or 'prompt' in text_data:
            metadata.source = "comfyui"
            MetadataParser._parse_comfyui_metadata(text_data, metadata)
            return
            
        # Check for other common metadata keys
        for key in ['Description', 'Comment', 'XML:com.adobe.xmp']:
            if key in text_data:
                metadata.prompt = text_data[key]
                break
    
    @staticmethod
    def _parse_jpeg_metadata(img: Image.Image, metadata: ImageMetadata) -> None:
        """Parse JPEG EXIF data for metadata."""
        try:
            exif = img._getexif()
            if exif:
                exif_data = {}
                for tag_id, value in exif.items():
                    tag = TAGS.get(tag_id, tag_id)
                    exif_data[tag] = value
                
                metadata.raw_metadata = json.dumps(exif_data, indent=2)
                
                # Look for UserComment which A1111 sometimes uses
                if 'UserComment' in exif_data:
                    comment = exif_data['UserComment']
                    if isinstance(comment, bytes):
                        # Try to decode
                        try:
                            comment = comment.decode('utf-8')
                        except:
                            comment = str(comment)
                    
                    # Check if it looks like A1111 format
                    if 'Steps:' in comment or 'Sampler:' in comment:
                        metadata.source = "a1111"
                        MetadataParser._parse_a1111_parameters(comment, metadata)
                    else:
                        metadata.prompt = comment
                        
                # Look for ImageDescription
                if 'ImageDescription' in exif_data and not metadata.prompt:
                    metadata.prompt = str(exif_data['ImageDescription'])
                    
        except Exception as e:
            metadata.raw_metadata = f"Error reading EXIF: {str(e)}"
    
    @staticmethod
    def _parse_a1111_parameters(text: str, metadata: ImageMetadata) -> None:
        """
        Parse A1111 format parameters.
        
        Format:
        Prompt text here
        Negative prompt: negative text here
        Steps: 20, Sampler: DPM++ 2M Karras, CFG scale: 7, Seed: 12345, Size: 512x768, ...
        """
        lines = text.split('\n')
        
        if not lines:
            return
            
        # Build prompt from lines until we hit "Negative prompt:" or parameters
        prompt_lines = []
        param_start_idx = len(lines)
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Check if this is the negative prompt line
            if stripped.startswith('Negative prompt:'):
                metadata.negative_prompt = stripped.split(':', 1)[1].strip()
                param_start_idx = i + 1
                break
            
            # Check if this line starts with a known parameter (indicates end of prompt)
            if any(stripped.startswith(f'{key}:') for key in ['Steps', 'Sampler', 'CFG scale', 'Seed', 'Size', 'Model', 'Model hash']):
                param_start_idx = i
                break
            
            # This is part of the prompt
            if stripped:
                prompt_lines.append(stripped)
        
        # Join prompt lines with commas (replace newlines with commas)
        metadata.prompt = ', '.join(prompt_lines)
        
        # Join remaining lines and parse parameters
        param_text = ' '.join(lines[param_start_idx:]).strip()
        
        if param_text:
            MetadataParser._parse_a1111_param_line(param_text, metadata)
    
    @staticmethod
    def _parse_a1111_param_line(param_text: str, metadata: ImageMetadata) -> None:
        """Parse the parameter line from A1111 format."""
        # Parse key-value pairs
        # Format: "Steps: 20, Sampler: DPM++ 2M Karras, CFG scale: 7, ..."
        
        # Use regex to find all key: value pairs
        # Handle values that may contain commas by looking for known keys
        known_keys = ['Steps', 'Sampler', 'CFG scale', 'Seed', 'Size', 'Model', 'Model hash',
                      'Clip skip', 'ENSD', 'RNG', 'Tiling', 'Restore faces', 'Hires upscale',
                      'Hires steps', 'Hires upscaler', 'Hires resize', 'Denoising strength',
                      'Mask blur', 'Variation seed', 'Variation seed strength']
        
        # Build a more careful parser
        remaining = param_text
        params_dict = {}
        
        while remaining:
            # Find the next known key
            found_key = None
            found_pos = -1
            
            for key in known_keys:
                # Look for "Key: " pattern
                search_pattern = rf'\b{re.escape(key)}:\s*'
                match = re.search(search_pattern, remaining)
                if match:
                    if found_pos == -1 or match.start() < found_pos:
                        found_pos = match.start()
                        found_key = key
            
            if found_key is None:
                break
            
            # Find where this value ends (start of next key or end of string)
            value_start = found_pos + len(found_key) + 1  # +1 for colon
            while value_start < len(remaining) and remaining[value_start] in ' \t':
                value_start += 1
            
            # Look for next key to determine where this value ends
            next_key_pos = len(remaining)
            for key in known_keys:
                if key != found_key:
                    search_pattern = rf',?\s*{re.escape(key)}:\s*'
                    match = re.search(search_pattern, remaining[value_start:])
                    if match:
                        pos = value_start + match.start()
                        if pos < next_key_pos:
                            next_key_pos = pos
            
            # Extract value
            value = remaining[value_start:next_key_pos].strip()
            # Remove trailing comma if present
            if value.endswith(','):
                value = value[:-1].strip()
            
            params_dict[found_key] = value
            remaining = remaining[next_key_pos:]
        
        # Process extracted parameters
        for key, value in params_dict.items():
            if key == 'Steps':
                try:
                    metadata.steps = int(value)
                except:
                    pass
            elif key == 'Sampler':
                metadata.sampler = value
            elif key == 'CFG scale':
                try:
                    metadata.cfg_scale = float(value)
                except:
                    pass
            elif key == 'Seed':
                try:
                    metadata.seed = int(value)
                except:
                    pass
            elif key == 'Size':
                # Parse "512x768" format
                try:
                    w, h = value.split('x')
                    metadata.width = int(w)
                    metadata.height = int(h)
                except:
                    pass
            elif key == 'Model':
                metadata.model = value
            elif key == 'Model hash':
                metadata.model_hash = value
            else:
                # Store extra parameters
                metadata.extra_params[key] = value
    
    @staticmethod
    def _parse_comfyui_metadata(text_data: Dict[str, str], metadata: ImageMetadata) -> None:
        """Parse ComfyUI format metadata."""
        try:
            # Parse workflow JSON - store as string to avoid SQLite issues
            if 'workflow' in text_data:
                workflow_str = text_data['workflow']
                try:
                    workflow = json.loads(workflow_str)
                    # Store workflow as JSON string instead of nested dict
                    metadata.extra_params['workflow'] = workflow_str
                except:
                    metadata.extra_params['workflow_raw'] = workflow_str[:1000]  # Truncate if too large
            
            # Parse prompt JSON
            if 'prompt' in text_data:
                prompt_str = text_data['prompt']
                try:
                    prompt_data = json.loads(prompt_str)
                    # Store as JSON string
                    metadata.extra_params['prompt_data'] = prompt_str
                    
                    # Try to extract prompt text from ComfyUI nodes
                    MetadataParser._extract_comfyui_prompt(prompt_data, metadata)
                except json.JSONDecodeError as e:
                    metadata.extra_params['parse_error'] = str(e)
                    metadata.extra_params['prompt_raw'] = prompt_str[:1000]
                
        except Exception as e:
            metadata.extra_params['parse_error'] = str(e)
    
    @staticmethod
    def _extract_comfyui_prompt(prompt_data: Dict, metadata: ImageMetadata) -> None:
        """Extract prompt text from ComfyUI prompt JSON structure."""
        # ComfyUI stores prompt in nodes with class_type "CLIPTextEncode"
        # The text is in the "text" input
        
        positive_prompts = []
        negative_prompts = []
        
        for node_id, node_data in prompt_data.items():
            if not isinstance(node_data, dict):
                continue
                
            class_type = node_data.get('class_type', '')
            inputs = node_data.get('inputs', {})
            
            # Look for CLIP text encode nodes
            if class_type in ['CLIPTextEncode', 'CLIPTextEncodeSDXL']:
                text = inputs.get('text', '')
                
                # Ensure text is a string (not a list or dict)
                if isinstance(text, (list, dict)):
                    text = json.dumps(text)
                elif not isinstance(text, str):
                    text = str(text)
                
                # Check if this is connected to a positive or negative input
                # This is a heuristic - we look at the node title or connections
                node_title = inputs.get('title', '').lower()
                
                if 'negative' in node_title or text.startswith('negative:'):
                    negative_prompts.append(text.replace('negative:', '').strip())
                else:
                    positive_prompts.append(text)
            
            # Also check for KSampler nodes to get generation params
            elif class_type in ['KSampler', 'KSamplerAdvanced']:
                steps = inputs.get('steps', 0)
                cfg = inputs.get('cfg', 0.0)
                seed = inputs.get('seed', 0)
                
                # Ensure values are proper types
                metadata.steps = int(steps) if isinstance(steps, (int, float, str)) and steps else 0
                metadata.cfg_scale = float(cfg) if isinstance(cfg, (int, float, str)) and cfg else 0.0
                metadata.seed = int(seed) if isinstance(seed, (int, float, str)) and seed else 0
                metadata.sampler = str(inputs.get('sampler_name', ''))
            
            # Check for model loader
            elif class_type in ['CheckpointLoaderSimple', 'CheckpointLoader']:
                model_val = inputs.get('ckpt_name', '')
                metadata.model = str(model_val) if model_val else ''
        
        # Combine prompts
        if positive_prompts:
            metadata.prompt = '\n'.join(positive_prompts)
        if negative_prompts:
            metadata.negative_prompt = '\n'.join(negative_prompts)
