"""Metadata parser for Stable Diffusion images (A1111 and ComfyUI)."""
import json
import re
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List
from PIL import Image
from PIL.ExifTags import TAGS
from PyQt6.QtCore import QSettings

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
    def _add_lora(metadata: ImageMetadata, raw_name: str) -> None:
        """Add a LoRA name to metadata, cleaning and deduping."""
        if not raw_name:
            return
            
        for name in str(raw_name).split(','):
            name = name.strip()
            name = name.strip(',')
            name = name.strip()
            
            # Remove strength info (e.g., "(0.8)" or ":0.8")
            # Handle (0.8) style
            name = re.sub(r'\s*\(\s*[\d.]+\s*\)$', '', name)
            # Handle :0.8 style (A1111 prompt syntax)
            name = re.sub(r':[\d.]+$', '', name)
            
            name = name.strip()
            
            if name and name not in metadata.loras:
                metadata.loras.append(name)
    
    @staticmethod
    def _parse_png_metadata(img: Image.Image, metadata: ImageMetadata) -> None:
        """Parse PNG text chunks for metadata."""
        if not hasattr(img, 'text') and not hasattr(img, 'info'):
            return

        # Get text chunks from PNG
        text_data = getattr(img, 'text', {}) or img.info.get('text', {})

        # Store raw metadata
        metadata.raw_metadata = json.dumps(text_data, indent=2)

        # Check for ComfyUI format (workflow and prompt keys) - primary indicator
        if 'workflow' in text_data or 'prompt' in text_data:
            metadata.source = "comfyui"
            # Also check for aodh_metadata (new format with embedded A1111 params)
            if 'aodh_metadata' in text_data:
                MetadataParser._parse_aodh_metadata(text_data, metadata)
            else:
                MetadataParser._parse_comfyui_metadata(text_data, metadata)
            return

        # Check for aodh_metadata (new format with embedded A1111 params)
        if 'aodh_metadata' in text_data:
            metadata.source = "comfyui"
            MetadataParser._parse_aodh_metadata(text_data, metadata)
            return

        # Check for A1111 format (parameters key only)
        if 'parameters' in text_data:
            metadata.source = "a1111"
            MetadataParser._parse_a1111_parameters(text_data['parameters'], metadata)
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

        # Extract LoRAs from prompt
        # Pattern: <lora:model_name:multiplier>
        lora_pattern = r'<lora:([^:>]+)(?::[^>]+)?>'
        loras = re.findall(lora_pattern, metadata.prompt)
        for lora in loras:
             MetadataParser._add_lora(metadata, lora)
        
        # Join remaining lines and parse parameters
        param_text = ' '.join(lines[param_start_idx:]).strip()
        
        if param_text:
            MetadataParser._parse_a1111_param_line(param_text, metadata)
            
            # Check for Lora hashes in extra_params
            if 'Lora hashes' in metadata.extra_params:
                lora_hashes = metadata.extra_params['Lora hashes'].strip('"').strip("'")
                # Format: "lora1: hash1, lora2: hash2"
                for part in lora_hashes.split(','):
                    if ':' in part:
                        name = part.split(':')[0].strip()
                        MetadataParser._add_lora(metadata, name)

            # Check for Lora/Loras/lora keys
            for key in ['Lora', 'Loras', 'lora']:
                if key in metadata.extra_params:
                    val = metadata.extra_params[key].strip('"').strip("'")
                    
                    # Try to parse as JSON first (some tools output JSON list of objects)
                    names_to_process = []
                    try:
                        # Try parsing as is
                        parsed = json.loads(val)
                    except:
                        try:
                            # Try replacing escaped quotes if it looks like it might be JSON
                            if '[' in val or '{' in val:
                                cleaned_val = val.replace('\\"', '"')
                                parsed = json.loads(cleaned_val)
                            else:
                                parsed = None
                        except:
                            parsed = None

                    if parsed:
                        if isinstance(parsed, list):
                            for item in parsed:
                                if isinstance(item, dict) and 'name' in item:
                                    names_to_process.append(str(item['name']))
                                elif isinstance(item, str):
                                    names_to_process.append(item)
                        elif isinstance(parsed, dict) and 'name' in parsed:
                            names_to_process.append(str(parsed['name']))
                        else:
                            names_to_process = [val]
                    else:
                        names_to_process = [val]

                    for raw_name in names_to_process:
                        MetadataParser._add_lora(metadata, raw_name)
                    
                    # Remove the key from extra_params to avoid duplication (since we have the structured list now)
                    del metadata.extra_params[key]
    
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
                      'Mask blur', 'Variation seed', 'Variation seed strength', 'Lora hashes',
                      'TI hashes', 'Hashes', 'Lora', 'Loras', 'lora', 'Version']
        
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
            workflow = None
            
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
                    
                    # Merge widgets_values from workflow into prompt_data
                    if workflow and 'nodes' in workflow:
                        for node in workflow['nodes']:
                            node_id = str(node.get('id', ''))
                            widgets = node.get('widgets_values', [])
                            if node_id and widgets and node_id in prompt_data:
                                prompt_data[node_id]['widgets_values'] = widgets
                    
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
        # Get configured node ID and titles from settings
        settings = QSettings("SDImageViewer", "Settings")
        primary_node_id = settings.value("comfyui_primary_node_id", "")
        primary_node = settings.value("comfyui_primary_node", "Full Prompt")
        alt_nodes = settings.value("comfyui_alt_nodes", [])
        if alt_nodes is None:
            alt_nodes = []
        if isinstance(alt_nodes, str):
            alt_nodes = [alt_nodes] if alt_nodes else []
        
        # Build list of node titles to search for (primary first, then alternatives)
        search_titles = [primary_node] + alt_nodes
        
        positive_prompts = []
        negative_prompts = []
        found_prompt_node = False
        
        # First, try to find node by ID (ID supersedes title)
        if primary_node_id and primary_node_id in prompt_data:
            node_data = prompt_data[primary_node_id]
            if isinstance(node_data, dict):
                # Try widgets_values first (from workflow format)
                widgets_values = node_data.get('widgets_values', [])
                if widgets_values and len(widgets_values) > 0:
                    # Get the first widget value (usually the text)
                    prompt_text = widgets_values[0]
                    if isinstance(prompt_text, list) and len(prompt_text) > 0:
                        prompt_text = prompt_text[0]
                    if isinstance(prompt_text, str):
                        # Remove escape characters from quotes
                        prompt_text = prompt_text.replace('\\"', '"').replace("\\'", "'")
                        metadata.prompt = prompt_text
                        found_prompt_node = True
                # Try inputs.text (from prompt API format)
                if not found_prompt_node:
                    inputs = node_data.get('inputs', {})
                    text = inputs.get('text', '')
                    if isinstance(text, str) and text:
                        metadata.prompt = text.replace('\\"', '"').replace("\\'", "'")
                        found_prompt_node = True
                    elif isinstance(text, list) and len(text) > 0:
                        # Handle case where text is a list
                        text_val = text[0]
                        if isinstance(text_val, str):
                            metadata.prompt = text_val.replace('\\"', '"').replace("\\'", "'")
                            found_prompt_node = True
        
        # If no node ID match, try to find nodes by configured titles
        if not found_prompt_node:
            for node_id, node_data in prompt_data.items():
                if not isinstance(node_data, dict):
                    continue
                
                # Check _meta for title
                meta = node_data.get('_meta', {})
                node_title = meta.get('title', '')
                
                # Check if this matches any of our search titles
                for search_title in search_titles:
                    if search_title.lower() in node_title.lower():
                        # Found a matching node - extract from widgets_values first
                        widgets_values = node_data.get('widgets_values', [])
                        if widgets_values and len(widgets_values) > 0:
                            # Get the first widget value (usually the text)
                            prompt_text = widgets_values[0]
                            if isinstance(prompt_text, list) and len(prompt_text) > 0:
                                prompt_text = prompt_text[0]
                            if isinstance(prompt_text, str):
                                # Remove escape characters from quotes
                                prompt_text = prompt_text.replace('\\"', '"').replace("\\'", "'")
                                metadata.prompt = prompt_text
                                found_prompt_node = True
                                break
                        
                        # If no widgets_values, try inputs.text
                        if not found_prompt_node:
                            inputs = node_data.get('inputs', {})
                            text = inputs.get('text', '')
                            if isinstance(text, str) and text:
                                metadata.prompt = text.replace('\\"', '"').replace("\\'", "'")
                                found_prompt_node = True
                                break
                            elif isinstance(text, list) and len(text) > 0:
                                text_val = text[0]
                                if isinstance(text_val, str):
                                    metadata.prompt = text_val.replace('\\"', '"').replace("\\'", "'")
                                    found_prompt_node = True
                                    break
                
                if found_prompt_node:
                    break
        
        # If no configured node found, fall back to original logic
        if not found_prompt_node:
            for node_id, node_data in prompt_data.items():
                if not isinstance(node_data, dict):
                    continue
                    
                class_type = node_data.get('class_type', '')
                inputs = node_data.get('inputs', {})
                meta = node_data.get('_meta', {})
                node_title = meta.get('title', '').lower()
                
                # Look for CLIP text encode nodes
                if class_type in ['CLIPTextEncode', 'CLIPTextEncodeSDXL']:
                    text = inputs.get('text', '')
                    
                    # Ensure text is a string (not a list or dict)
                    if isinstance(text, (list, dict)):
                        text = json.dumps(text)
                    elif not isinstance(text, str):
                        text = str(text)
                    
                    # Remove escape characters from quotes
                    text = text.replace('\\"', '"').replace("\\'", "'")
                    
                    # Check if this is connected to a positive or negative input
                    if 'negative' in node_title or text.startswith('negative:'):
                        negative_prompts.append(text.replace('negative:', '').strip())
                    else:
                        positive_prompts.append(text)
        
        # Extract generation parameters from KSampler nodes
        for node_id, node_data in prompt_data.items():
            if not isinstance(node_data, dict):
                continue
            
            class_type = node_data.get('class_type', '')
            inputs = node_data.get('inputs', {})
            
            # Check for KSampler nodes to get generation params
            if class_type in ['KSampler', 'KSamplerAdvanced']:
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

            # Check for LoRA loader
            elif class_type in ['LoraLoader', 'LoraLoaderModelOnly']:
                lora_name = inputs.get('lora_name', '')
                if lora_name:
                    MetadataParser._add_lora(metadata, str(lora_name))
        
        # Combine prompts (only if we didn't find a configured node)
        if not found_prompt_node:
            if positive_prompts:
                metadata.prompt = '\n'.join(positive_prompts)
            if negative_prompts:
                metadata.negative_prompt = '\n'.join(negative_prompts)

    @staticmethod
    def _parse_aodh_metadata(text_data: Dict[str, str], metadata: ImageMetadata) -> None:
        """Parse aodh_metadata format which embeds A1111-style parameters."""
        try:
            aodh_str = text_data.get('aodh_metadata', '{}')
            aodh_data = json.loads(aodh_str)

            # Parse the embedded A1111-style parameters
            if 'parameters' in aodh_data:
                MetadataParser._parse_a1111_parameters(aodh_data['parameters'], metadata)

            # Store the comfyui flag
            if 'comfyui' in aodh_data:
                metadata.extra_params['comfyui'] = aodh_data['comfyui']

            # Parse comfyui_metadata if present (new format)
            if 'comfyui_metadata' in aodh_data:
                comfyui_meta = aodh_data['comfyui_metadata']

                # Store workflow info
                if 'workflow_name' in comfyui_meta:
                    metadata.extra_params['workflow_name'] = comfyui_meta['workflow_name']
                if 'workflow_version' in comfyui_meta:
                    metadata.extra_params['workflow_version'] = comfyui_meta['workflow_version']

                # Parse generation info
                if 'generation' in comfyui_meta:
                    gen = comfyui_meta['generation']
                    if 'checkpoint' in gen and not metadata.model:
                        metadata.model = gen['checkpoint']
                    if 'vae' in gen:
                        metadata.extra_params['vae'] = gen['vae']
                    if 'clip_skip' in gen:
                        metadata.extra_params['clip_skip'] = gen['clip_skip']
                    if 'lora' in gen:
                        lora_data = gen['lora']
                        # Also add to main loras list
                        if isinstance(lora_data, list):
                            for lora in lora_data:
                                raw_name = ""
                                if isinstance(lora, dict) and 'name' in lora:
                                    raw_name = str(lora['name'])
                                elif isinstance(lora, str):
                                    raw_name = lora
                                
                                MetadataParser._add_lora(metadata, raw_name)

                # Parse sampling info - can override A1111 values if they're 0
                if 'sampling' in comfyui_meta:
                    samp = comfyui_meta['sampling']
                    if metadata.steps == 0 and 'steps' in samp:
                        metadata.steps = int(samp['steps'])
                    if metadata.cfg_scale == 0.0 and 'cfg' in samp:
                        metadata.cfg_scale = float(samp['cfg'])
                    if metadata.seed == 0 and 'seed' in samp:
                        metadata.seed = int(samp['seed'])
                    if not metadata.sampler and 'sampler' in samp:
                        metadata.sampler = samp['sampler']
                    if 'scheduler' in samp:
                        metadata.extra_params['scheduler'] = samp['scheduler']

                # Parse resolution info
                if 'resolution' in comfyui_meta:
                    res = comfyui_meta['resolution']
                    if 'width' in res and metadata.width == 0:
                        metadata.width = int(res['width'])
                    if 'height' in res and metadata.height == 0:
                        metadata.height = int(res['height'])
                    if 'upscale_factor' in res:
                        metadata.extra_params['upscale_factor'] = res['upscale_factor']
                    if 'upscaler' in res:
                        metadata.extra_params['upscaler'] = res['upscaler']
                    if 'hires_steps' in res:
                        metadata.extra_params['hires_steps'] = res['hires_steps']
                    if 'denoise_strength' in res:
                        metadata.extra_params['denoise_strength'] = res['denoise_strength']

                # Parse prompt structure
                if 'prompt_structure' in comfyui_meta:
                    ps = comfyui_meta['prompt_structure']
                    if 'positive' in ps and 'full' in ps['positive']:
                        metadata.extra_params['prompt_full'] = ps['positive']['full']
                    if 'negative' in ps and 'full' in ps['negative']:
                        metadata.extra_params['negative_full'] = ps['negative']['full']

                # Parse post-processing
                if 'post_processing' in comfyui_meta:
                    pp = comfyui_meta['post_processing']
                    if 'detailers' in pp:
                        metadata.extra_params['detailers'] = json.dumps(pp['detailers'])
                    if 'color_match' in pp:
                        metadata.extra_params['color_match'] = json.dumps(pp['color_match'])

                # Store workflow nodes reference
                if 'workflow' in comfyui_meta:
                    wf = comfyui_meta['workflow']
                    if 'nodes' in wf:
                        metadata.extra_params['workflow_nodes'] = json.dumps(wf['nodes'])
                    if 'groups' in wf:
                        metadata.extra_params['workflow_groups'] = json.dumps(wf['groups'])
                    if 'execution' in wf:
                        metadata.extra_params['workflow_execution'] = json.dumps(wf['execution'])

            # Parse extended parameters if present (old format)
            elif 'extended_params' in aodh_data:
                extended = aodh_data['extended_params']
                metadata.extra_params['extended_params'] = json.dumps(extended)

                # Extract useful fields from extended params
                if 'base_size' in extended:
                    metadata.extra_params['base_size'] = extended['base_size']
                if 'actual_size' in extended:
                    actual_size = extended['actual_size']
                    if 'x' in str(actual_size):
                        try:
                            w, h = str(actual_size).split('x')
                            if metadata.width == 0:
                                metadata.width = int(w)
                            if metadata.height == 0:
                                metadata.height = int(h)
                        except:
                            pass
                if 'hires_fix_applied' in extended:
                    metadata.extra_params['hires_fix_applied'] = extended['hires_fix_applied']
                if 'detailing_info' in extended:
                    metadata.extra_params['detailing_info'] = json.dumps(extended['detailing_info'])
                if 'workflow_summary' in extended:
                    metadata.extra_params['workflow_summary'] = json.dumps(extended['workflow_summary'])
                if 'resource_usage' in extended:
                    metadata.extra_params['resource_usage'] = json.dumps(extended['resource_usage'])

            # Store timestamp
            if 'timestamp' in aodh_data:
                metadata.extra_params['generation_timestamp'] = aodh_data['timestamp']

            # Note: We don't call _parse_comfyui_metadata here because:
            # 1. The A1111 parameters already contain all the generation info
            # 2. The ComfyUI prompt data contains link references that would overwrite the correct values
            # 3. The comfyui_metadata section is already parsed above for extended info

        except json.JSONDecodeError as e:
            metadata.extra_params['aodh_parse_error'] = f"Invalid JSON: {str(e)}"
        except Exception as e:
            metadata.extra_params['aodh_parse_error'] = str(e)
