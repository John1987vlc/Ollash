#!/usr/bin/env python3
"""
Script de debug para diagnosticar problemas con la generación de imágenes en Invoke UI.
Ayuda a identificar dónde falla el flujo de generación y descarga.
"""

import sys
import logging
from pathlib import Path
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('debug_image_generation.log')
    ]
)
logger = logging.getLogger(__name__)

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent))

from src.utils.domains.multimedia.image_generation_tools import ImageGeneratorTools


def debug_image_generation():
    """Ejecuta un test completo de generación de imágenes con debugging detallado."""
    
    logger.info("=" * 80)
    logger.info("INICIANDO DEBUG DE GENERACIÓN DE IMÁGENES")
    logger.info("=" * 80)
    
    # Inicializar las herramientas de generación
    try:
        image_gen = ImageGeneratorTools(logger=logger)
        logger.info("✅ ImageGeneratorTools inicializado correctamente")
    except Exception as e:
        logger.error(f"❌ Error inicializando ImageGeneratorTools: {e}", exc_info=True)
        return False
    
    # Step 1: Verificar estado de Invoke UI
    logger.info("\n" + "-" * 80)
    logger.info("STEP 1: Verificando estado de Invoke UI")
    logger.info("-" * 80)
    
    status = image_gen.check_invoke_ui_status()
    logger.info(f"Status check result: {status}")
    
    if not status.get("ok"):
        logger.error(f"❌ Invoke UI no está disponible: {status.get('error')}")
        return False
    
    logger.info(f"✅ Invoke UI está disponible en: {status.get('api_url')}")
    logger.info(f"   Versión: {status.get('version')}")
    logger.info(f"   Modelos disponibles: {len(status.get('available_main_models', []))}")
    
    # Step 2: Listar modelos disponibles
    logger.info("\n" + "-" * 80)
    logger.info("STEP 2: Listando modelos disponibles")
    logger.info("-" * 80)
    
    models = image_gen.list_available_models(model_type="main")
    if models.get("ok"):
        logger.info(f"✅ Total de modelos: {models.get('total')}")
        for base, model_list in models.get('models_by_base', {}).items():
            logger.info(f"\n📦 Base: {base}")
            for model in model_list:
                logger.info(f"   - {model.get('name')}")
    else:
        logger.error(f"❌ Error ListBox de modelos: {models.get('error')}")
        return False
    
    # Step 3: Intentar generar una imagen simple
    logger.info("\n" + "-" * 80)
    logger.info("STEP 3: Generando imagen de prueba")
    logger.info("-" * 80)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    test_filename = f"debug_test_{timestamp}"
    
    logger.info(f"Prompt: 'a simple red cube'")
    logger.info(f"Modelo: 'Dreamshaper 8'")
    logger.info(f"Resolución: 512x512")
    logger.info(f"Steps: 5 (bajo para test rápido)")
    
    result = image_gen.generate_image(
        prompt="a simple red cube",
        model_name="Dreamshaper 8",
        steps=5,  # Bajo para test rápido
        filename=test_filename
    )
    
    logger.info("\n" + "-" * 80)
    logger.info("RESULTADO FINAL:")
    logger.info("-" * 80)
    
    if result.get("ok"):
        logger.info("✅ ¡Generación exitosa!")
        logger.info(f"   Ruta: {result.get('path')}")
        logger.info(f"   Tamaño: {result.get('size')}")
        logger.info(f"   Steps: {result.get('steps')}")
        logger.info(f"   Modelo: {result.get('model_name')}")
        return True
    else:
        logger.error("❌ Generación fallida")
        logger.error(f"   Error: {result.get('error')}")
        
        # Información adicional de debug
        if 'exception_type' in result:
            logger.error(f"   Tipo de excepción: {result.get('exception_type')}")
        if 'details' in result:
            logger.error(f"   Detalles: {result.get('details')}")
        
        return False


def debug_specific_issue(api_base_url: str = None):
    """Debug específico para un problema conocido."""
    
    logger.info("\n" + "=" * 80)
    logger.info("DEBUG ESPECÍFICO DE CONEXIÓN")
    logger.info("=" * 80)
    
    import requests
    
    if not api_base_url:
        api_base_url = "http://192.168.1.217:9090"
    
    # Test 1: Conexión básica
    logger.info(f"\n1️⃣ Probando conexión a {api_base_url}...")
    try:
        response = requests.get(f"{api_base_url}/api/v1/app/version", timeout=5)
        logger.info(f"   ✅ Respuesta: {response.status_code}")
        logger.info(f"   Contenido: {response.json()}")
    except Exception as e:
        logger.error(f"   ❌ Error: {e}")
        return False
    
    # Test 2: Verificar acceso a sesiones
    logger.info(f"\n2️⃣ Probando acceso a endpoint de sesiones...")
    try:
        response = requests.get(f"{api_base_url}/api/v1/sessions", timeout=5)
        logger.info(f"   ✅ Respuesta: {response.status_code}")
    except Exception as e:
        logger.error(f"   ❌ Error: {e}")
    
    # Test 3: Verificar acceso a modelos
    logger.info(f"\n3️⃣ Probando acceso a modelos...")
    try:
        response = requests.get(f"{api_base_url}/api/v2/models/", timeout=5)
        logger.info(f"   ✅ Respuesta: {response.status_code}")
        data = response.json()
        logger.info(f"   📦 Total de modelos: {len(data.get('models', []))}")
    except Exception as e:
        logger.error(f"   ❌ Error: {e}")
    
    # Test 4: Verificar colas
    logger.info(f"\n4️⃣ Probando estado de cola...")
    try:
        response = requests.get(f"{api_base_url}/api/v1/queue/default/status", timeout=5)
        logger.info(f"   ✅ Respuesta: {response.status_code}")
        logger.info(f"   Contenido: {response.json()}")
    except Exception as e:
        logger.error(f"   ❌ Error: {e}")
    
    logger.info("\n✅ Debug de conexión completado")
    return True


if __name__ == "__main__":
    logger.info(f"Python: {sys.version}")
    logger.info(f"Directorio de trabajo: {Path.cwd()}")
    
    # Ejecutar debug específico primero
    debug_specific_issue()
    
    # Luego ejecutar debug completo
    success = debug_image_generation()
    
    logger.info("\n" + "=" * 80)
    if success:
        logger.info("✅ DEBUG COMPLETADO - La generación funciona correctamente")
    else:
        logger.info("❌ DEBUG COMPLETADO - Se detectaron problemas")
        logger.info("\n💡 SUGERENCIAS:")
        logger.info("  1. Verifica que Invoke UI esté ejecutándose en http://192.168.1.217:9090")
        logger.info("  2. Revisa el archivo 'debug_image_generation.log' para más detalles")
        logger.info("  3. Comprueba los logs de Invoke UI en su terminal")
        logger.info("  4. Verifica la conectividad de red entre este equipo e Invoke UI")
    logger.info("=" * 80)
    
    sys.exit(0 if success else 1)
