#!/usr/bin/env python3
"""
Script para recuperar TODOS los modelos disponibles en InvokeAI
y mostrar su estructura exacta para debugging.
"""

import requests
import json
from typing import Any, Dict, List

API_BASE = "http://192.168.1.217:9090"

def pretty_print_json(data: Any, indent: int = 2):
    """Imprime JSON de forma legible"""
    print(json.dumps(data, indent=indent, ensure_ascii=False))

def try_endpoint(endpoint: str, method: str = "GET") -> tuple:
    """Intenta acceder a un endpoint y retorna (success, data)"""
    url = f"{API_BASE}{endpoint}"
    
    try:
        if method == "GET":
            response = requests.get(url, timeout=10)
        elif method == "POST":
            response = requests.post(url, json={}, timeout=10)
        else:
            return False, None
            
        if response.status_code in [200, 201]:
            try:
                return True, response.json()
            except:
                return True, response.text
        else:
            return False, {"status": response.status_code, "text": response.text[:200]}
    except Exception as e:
        return False, {"error": str(e)}

def main():
    print("=" * 80)
    print("RECUPERANDO MODELOS DE INVOKEAI")
    print("=" * 80)
    print(f"Servidor: {API_BASE}\n")
    
    # Lista de endpoints posibles para modelos
    endpoints_to_try = [
        # v1 endpoints
        "/api/v1/models",
        "/api/v1/models/",
        "/api/v1/models/main",
        "/api/v1/model_records",
        "/api/v1/model_manager/list",
        "/api/v1/model_manager/models",
        "/api/v1/model_manager/search",
        
        # v2 endpoints
        "/api/v2/models",
        "/api/v2/models/",
        "/api/v2/model_records",
        
        # Otros posibles
        "/api/models",
        "/models",
        "/api/v1/app/models",
    ]
    
    print("🔍 Buscando endpoint de modelos...\n")
    
    models_data = None
    successful_endpoint = None
    
    for endpoint in endpoints_to_try:
        print(f"Probando: {endpoint}")
        success, data = try_endpoint(endpoint)
        
        if success:
            print(f"  ✅ ÉXITO! Status 200")
            models_data = data
            successful_endpoint = endpoint
            break
        else:
            print(f"  ❌ Falló")
    
    if not models_data:
        print("\n" + "=" * 80)
        print("❌ NO SE PUDO ENCONTRAR EL ENDPOINT DE MODELOS")
        print("=" * 80)
        print("\nProbando endpoint de OpenAPI para ver rutas disponibles...")
        
        # Intentar obtener documentación OpenAPI
        openapi_endpoints = [
            "/openapi.json",
            "/api/openapi.json",
            "/api/v1/openapi.json",
        ]
        
        for endpoint in openapi_endpoints:
            print(f"\nProbando: {endpoint}")
            success, data = try_endpoint(endpoint)
            
            if success and isinstance(data, dict):
                print(f"  ✅ OpenAPI encontrado!")
                
                # Extraer rutas que contengan "model"
                if "paths" in data:
                    model_paths = [p for p in data["paths"].keys() if "model" in p.lower()]
                    
                    print(f"\n📋 ENDPOINTS RELACIONADOS CON MODELOS ENCONTRADOS:")
                    print("=" * 80)
                    for path in sorted(model_paths):
                        methods = list(data["paths"][path].keys())
                        print(f"  {path}")
                        print(f"    Métodos: {', '.join(methods)}")
                    
                    # Guardar OpenAPI spec
                    with open("openapi_spec.json", "w") as f:
                        json.dump(data, f, indent=2)
                    print(f"\n💾 Especificación OpenAPI guardada en: openapi_spec.json")
                    print("   Revisa este archivo para ver todos los endpoints disponibles")
                
                break
        
        return
    
    # Si encontramos datos, procesarlos
    print("\n" + "=" * 80)
    print(f"✅ MODELOS RECUPERADOS DESDE: {successful_endpoint}")
    print("=" * 80)
    
    # Guardar respuesta completa
    with open("models_full_response.json", "w") as f:
        json.dump(models_data, f, indent=2, ensure_ascii=False)
    print(f"\n💾 Respuesta completa guardada en: models_full_response.json")
    
    # Analizar estructura
    print("\n" + "=" * 80)
    print("ESTRUCTURA DE LA RESPUESTA")
    print("=" * 80)
    
    print(f"\nTipo de datos: {type(models_data)}")
    
    if isinstance(models_data, dict):
        print(f"Claves principales: {list(models_data.keys())}")
        
        # Buscar donde están los modelos
        models_list = None
        models_key = None
        
        for key in models_data.keys():
            value = models_data[key]
            if isinstance(value, list) and len(value) > 0:
                # Verificar si parece una lista de modelos
                if isinstance(value[0], dict):
                    models_list = value
                    models_key = key
                    break
        
        if models_list:
            print(f"\n✅ Lista de modelos encontrada en clave: '{models_key}'")
            print(f"   Número de modelos: {len(models_list)}")
        else:
            print("\n⚠️  No se encontró una lista obvia de modelos")
            print("    Mostrando toda la respuesta:\n")
            pretty_print_json(models_data)
            return
            
    elif isinstance(models_data, list):
        models_list = models_data
        print(f"Respuesta es una lista directa con {len(models_list)} modelos")
    else:
        print("⚠️  Formato de respuesta inesperado")
        print(models_data)
        return
    
    # Mostrar información de cada modelo
    print("\n" + "=" * 80)
    print(f"MODELOS DISPONIBLES ({len(models_list)} total)")
    print("=" * 80)
    
    # Agrupar por tipo/base
    by_type = {}
    
    for idx, model in enumerate(models_list):
        if not isinstance(model, dict):
            continue
            
        # Intentar extraer información clave
        model_info = {
            "index": idx,
            "raw": model
        }
        
        # Buscar campos comunes
        for field in ["name", "model_name", "key", "path", "base", "base_model", 
                      "type", "model_type", "format", "hash"]:
            if field in model:
                model_info[field] = model[field]
        
        # Agrupar por tipo base
        base_key = model_info.get("base", model_info.get("base_model", "unknown"))
        if base_key not in by_type:
            by_type[base_key] = []
        by_type[base_key].append(model_info)
    
    # Imprimir modelos agrupados
    for base_type, models in sorted(by_type.items()):
        print(f"\n{'─' * 80}")
        print(f"BASE: {base_type.upper()} ({len(models)} modelos)")
        print('─' * 80)
        
        for model in models:
            print(f"\n  Modelo #{model['index'] + 1}:")
            
            # Imprimir campos importantes
            important_fields = ["name", "model_name", "key", "path", "type", "model_type", "format", "hash"]
            for field in important_fields:
                if field in model and field != "raw":
                    value = model[field]
                    if isinstance(value, str) and len(value) > 60:
                        value = value[:57] + "..."
                    print(f"    {field:15s}: {value}")
    
    # Mostrar algunos ejemplos completos
    print("\n" + "=" * 80)
    print("EJEMPLOS DE MODELOS COMPLETOS (primeros 3)")
    print("=" * 80)
    
    for idx in range(min(3, len(models_list))):
        print(f"\n{'─' * 80}")
        print(f"MODELO {idx + 1}:")
        print('─' * 80)
        pretty_print_json(models_list[idx])
    
    # Crear archivo de resumen
    print("\n" + "=" * 80)
    print("CREANDO RESUMEN PARA USO EN CÓDIGO")
    print("=" * 80)
    
    summary = {
        "endpoint": successful_endpoint,
        "total_models": len(models_list),
        "models_by_base": {},
        "model_list": []
    }
    
    for model in models_list:
        if not isinstance(model, dict):
            continue
            
        # Extraer info clave
        name = model.get("name") or model.get("model_name") or "Unknown"
        base = model.get("base") or model.get("base_model") or "unknown"
        key = model.get("key") or model.get("path") or ""
        model_type = model.get("type") or model.get("model_type") or "main"
        
        model_summary = {
            "name": name,
            "base": base,
            "key": key,
            "type": model_type,
            "full_data": model
        }
        
        summary["model_list"].append(model_summary)
        
        if base not in summary["models_by_base"]:
            summary["models_by_base"][base] = []
        summary["models_by_base"][base].append(name)
    
    with open("models_summary.json", "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    print("\n💾 Archivos creados:")
    print("   1. models_full_response.json  - Respuesta completa de la API")
    print("   2. models_summary.json        - Resumen estructurado")
    print("   3. openapi_spec.json          - Especificación OpenAPI (si está disponible)")
    
    print("\n" + "=" * 80)
    print("✅ PROCESO COMPLETADO")
    print("=" * 80)
    print("\n📋 MODELOS POR BASE:")
    for base, models in summary["models_by_base"].items():
        print(f"\n{base.upper()}:")
        for model in models:
            print(f"  - {model}")
    
    print("\n💡 SIGUIENTE PASO:")
    print("   Revisa los archivos JSON generados y copia la salida")
    print("   de este script para compartirla.")

if __name__ == "__main__":
    main()