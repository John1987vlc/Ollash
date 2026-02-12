#!/usr/bin/env python3
"""
Demo script to generate images using Invoke UI:
1. Text-to-Image generation
2. Image-to-Image variation
"""

import os
import sys
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from utils.domains.multimedia.image_generation_tools import ImageGeneratorTools

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    print("\n" + "="*60)
    print("IMAGE GENERATION DEMO - Invoke UI")
    print("="*60)
    
    # Initialize generator
    generator = ImageGeneratorTools(logger=logger)
    
    # Step 1: Text-to-Image
    print("\n[STEP 1] Generating Text-to-Image...")
    print("-" * 60)
    
    prompt_1 = "A beautiful sunset over mountains, digital art, vibrant colors, high quality"
    params_1 = {
        "steps": 30,
        "cfg_scale": 7.0,
        "scheduler": "euler",
    }
    
    result_1 = generator.generate_image(prompt=prompt_1, model_name="Dreamshaper 8", **params_1)
    
    if result_1['ok']:
        image_path_1 = result_1['path']
        print(f"[SUCCESS] Text-to-Image generated successfully!")
        print(f"  Prompt: {prompt_1}")
        print(f"  Path: {image_path_1}")
        print(f"  Size: {result_1.get('size', 'N/A')}")
        print(f"  Generation time: {result_1.get('time', 'N/A')}s")
    else:
        print(f"[ERROR] Failed to generate text-to-image: {result_1['error']}")
        return False
    
    # Step 2: Image-to-Image variation
    print("\n[STEP 2] Generating Image-to-Image variation...")
    print("-" * 60)
    
    # Use the generated image as base
    if not os.path.exists(image_path_1):
        print(f"[ERROR] Generated image not found at {image_path_1}")
        return False
    
    prompt_2 = "The same sunset scene but with flying birds and clouds, more dramatic lighting"
    params_2 = {
        "steps": 25,
        "cfg_scale": 7.5,
        "denoising": 0.6,  # Lower denoising = more faithful to original
        "sampler": "DPM",
    }
    
    result_2 = generator.generate_image_from_image(
        image_path=image_path_1,
        prompt=prompt_2,
        model_name="Dreamshaper 8", 
        **params_2
    )
    
    if result_2['ok']:
        image_path_2 = result_2['path']
        print(f"[SUCCESS] Image-to-Image generated successfully!")
        print(f"  Base image: {image_path_1}")
        print(f"  New prompt: {prompt_2}")
        print(f"  Path: {image_path_2}")
        print(f"  Size: {result_2.get('size', 'N/A')}")
        print(f"  Generation time: {result_2.get('time', 'N/A')}s")
    else:
        print(f"[ERROR] Failed to generate image-to-image: {result_2['error']}")
        return False
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"\n[OK] Both images generated successfully!")
    print(f"\nText-to-Image:")
    print(f"  Location: {image_path_1}")
    print(f"\nImage-to-Image:")
    print(f"  Location: {image_path_2}")
    print(f"\nAll images saved to: {Path(image_path_1).parent}/")
    print("\n" + "="*60 + "\n")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)
