#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verificar conexion a Invoke UI
Verifica que Invoke UI este accesible y funcionando correctamente
"""

import sys
from pathlib import Path

# Agregar raiz del proyecto al path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def check_invoke_ui():
    """Verificar conexion a Invoke UI"""
    from backend.utils.domains.multimedia.image_generation_tools import ImageGeneratorTools
    import logging
    
    # Configurar logging - SILENCIAR
    logging.disable(logging.CRITICAL)
    logger = logging.getLogger('invoke_ui_check')
    
    print("\n" + "="*70)
    print("  Verificacion de Invoke UI")
    print("="*70 + "\n")
    
    # Crear instancia del generador
    generator = ImageGeneratorTools(logger=logger)
    
    print("URL configurada: " + generator.api_base_url)
    print("Directorio de salida: " + str(generator.output_dir) + "\n")
    
    # Verificar estado
    print("Verificando conexion a Invoke UI...\n")
    status = generator.check_invoke_ui_status()
    
    if status['ok']:
        print("[OK] Invoke UI esta en linea")
        print("   Estado: " + status['status'].upper())
        print("   Mensaje: " + status.get('message', 'N/A'))
        if status.get('models'):
            print("\n   Modelos detectados:")
            for model in status['models'][:5]:
                print("     - " + str(model))
            if len(status.get('models', [])) > 5:
                print("     ... y " + str(len(status['models']) - 5) + " mas")
        
        print("\n[SUCCESS] Invoke UI esta listo para usar!")
        print("\n   Puedes usar la herramienta de generacion de imagenes:")
        print("   - En auto_agent para generar imagenes automaticamente")
        print("   - En tus propios scripts de Python")
        print("   - Con comandos CLI del agente")
        return True
    else:
        print("[ERROR] No se puede conectar a Invoke UI")
        print("   Error: " + status.get('error', 'Unknown'))
        print("   Sugerencia: " + str(status.get('suggestion', 'N/A')))
        print("\n   Para habilitar la generacion de imagenes:")
        print("   1. Inicia Invoke UI en http://192.168.1.217:9090")
        print("   2. Verifica que es accesible desde esta maquina")
        print("   3. Establece INVOKE_UI_URL en .env si la URL es diferente")
        return False

if __name__ == "__main__":
    success = check_invoke_ui()
    print("\n" + "="*70 + "\n")
    sys.exit(0 if success else 1)
