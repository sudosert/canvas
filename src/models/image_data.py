"""Data models for image metadata."""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime
import json


@dataclass
class ImageMetadata:
    """Represents metadata extracted from a Stable Diffusion image."""
    
    file_path: str
    file_name: str
    width: int = 0
    height: int = 0
    file_size: int = 0
    modified_time: float = 0.0
    
    # Generation parameters
    prompt: str = ""
    negative_prompt: str = ""
    model: str = ""
    model_hash: str = ""
    sampler: str = ""
    steps: int = 0
    cfg_scale: float = 0.0
    seed: int = 0
    
    # Source detection
    source: str = ""  # "a1111", "comfyui", or "unknown"
    raw_metadata: str = ""
    
    # Additional parameters (flexible storage)
    extra_params: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def dimensions(self) -> str:
        """Return dimensions as 'WxH' string."""
        return f"{self.width}x{self.height}"
    
    @property
    def full_prompt(self) -> str:
        """Return combined prompt and negative prompt."""
        result = self.prompt
        if self.negative_prompt:
            result += f"\nNegative prompt: {self.negative_prompt}"
        return result
    
    def matches_filter(self, include_terms: list, exclude_terms: list) -> bool:
        """
        Check if image matches filter criteria.
        
        Args:
            include_terms: List of terms that must be in prompt (positive filter)
            exclude_terms: List of terms that must NOT be in prompt (negative filter)
        
        Returns:
            True if image matches all criteria
        """
        prompt_lower = self.prompt.lower()
        
        # Check include terms (all must match)
        for term in include_terms:
            if term.lower() not in prompt_lower:
                return False
        
        # Check exclude terms (none must match)
        for term in exclude_terms:
            if term.lower() in prompt_lower:
                return False
        
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'file_path': self.file_path,
            'file_name': self.file_name,
            'width': self.width,
            'height': self.height,
            'file_size': self.file_size,
            'modified_time': self.modified_time,
            'prompt': self.prompt,
            'negative_prompt': self.negative_prompt,
            'model': self.model,
            'model_hash': self.model_hash,
            'sampler': self.sampler,
            'steps': self.steps,
            'cfg_scale': self.cfg_scale,
            'seed': self.seed,
            'source': self.source,
            'raw_metadata': self.raw_metadata,
            'extra_params': json.dumps(self.extra_params)
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ImageMetadata':
        """Create from dictionary."""
        extra = data.get('extra_params', '{}')
        if isinstance(extra, str):
            try:
                extra = json.loads(extra)
            except:
                extra = {}
        
        return cls(
            file_path=data['file_path'],
            file_name=data['file_name'],
            width=data.get('width', 0),
            height=data.get('height', 0),
            file_size=data.get('file_size', 0),
            modified_time=data.get('modified_time', 0.0),
            prompt=data.get('prompt', ''),
            negative_prompt=data.get('negative_prompt', ''),
            model=data.get('model', ''),
            model_hash=data.get('model_hash', ''),
            sampler=data.get('sampler', ''),
            steps=data.get('steps', 0),
            cfg_scale=data.get('cfg_scale', 0.0),
            seed=data.get('seed', 0),
            source=data.get('source', ''),
            raw_metadata=data.get('raw_metadata', ''),
            extra_params=extra
        )
