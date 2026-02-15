#!/usr/bin/env python3
"""
Test de imagen a imagen (img2img)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import logging

from backend.utils.domains.multimedia.image_generation_tools import \
    ImageGeneratorTools

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

print("=" * 80)
print("TEST DE IMAGEN A IMAGEN (IMG2IMG)")
print("=" * 80)

image_gen = ImageGeneratorTools(logger=logger)

# 1. Generar imagen inicial
print("\n1. Generando imagen inicial...")
initial_result = image_gen.generate_image(
    prompt="a beautiful red car", steps=5, filename="input_car"
)

if not initial_result.get("ok"):
    print(f"ERROR: {initial_result.get('error')}")
    exit(1)

input_image_path = initial_result.get("path")
print(f"   ✅ Imagen inicial generada: {input_image_path}")

# 2. Aplicar img2img
print("\n2. Aplicando transformación img2img...")
img2img_result = image_gen.generate_image_from_image(
    prompt="a beautiful blue vintage car",
    image_path=input_image_path,
    denoising_strength=0.75,
    steps=5,
    filename="output_car",
)

print("\n" + "=" * 80)
if img2img_result.get("ok"):
    print("✅ IMG2IMG EXITO!")
    print(f"   Input: {img2img_result.get('input_image')}")
    print(f"   Output: {img2img_result.get('path')}")
    print(f"   Denoising strength: {img2img_result.get('denoising_strength')}")
    print(f"   Model: {img2img_result.get('model_name')}")
else:
    print("❌ IMG2IMG FALLO")
    print(f"   Error: {img2img_result.get('error')}")

print("=" * 80)
