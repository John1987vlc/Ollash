#!/usr/bin/env python3
"""
Test final del código corregido
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.utils.domains.multimedia.image_generation_tools import ImageGeneratorTools
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

print("=" * 80)
print("TEST FINAL DEL CÓDIGO CORREGIDO")
print("=" * 80)

# Initialize image generator
image_gen = ImageGeneratorTools(logger=logger)

# Check status
print("\n1. Verificando Invoke UI...")
status = image_gen.check_invoke_ui_status()
if not status.get("ok"):
    print(f"ERROR: {status.get('error')}")
    exit(1)

print(f"   Status: {status.get('status')}")
print(f"   Version: {status.get('version')}")

# Generate image
print("\n2. Generando imagen...")
result = image_gen.generate_image(
    prompt="a beautiful sunset",
    steps=5,
    filename="final_test"
)

print("\n" + "=" * 80)
if result.get("ok"):
    print("✅ EXITO - Imagen generada correctamente!")
    print(f"   Ruta: {result.get('path')}")
    print(f"   Tamaño: {result.get('size')}")
    print(f"   Model: {result.get('model_name')}")
    print(f"   Image name en servidor: {result.get('invoke_image_name')}")
else:
    print("❌ FALLO")
    print(f"   Error: {result.get('error')}")

print("=" * 80)

