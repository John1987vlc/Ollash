#!/usr/bin/env python3
"""
Investigar cómo obtener las imágenes de la cola
"""
import requests
import json

API_BASE = "http://192.168.1.217:9090"

print("="*80)
print("Explorando endpoints de imágenes")
print("="*80)

# 1. Listar imágenes disponibles
print("\n1. Intentando listar imágenes (GET /api/v1/images/)")
try:
    resp = requests.get(f"{API_BASE}/api/v1/images/", timeout=10)
    print(f"   Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"   Tipo: {type(data)}")
        if isinstance(data, dict):
            print(f"   Keys: {list(data.keys())}")
            if "images" in data:
                images = data["images"]
                print(f"   Total imágenes: {len(images)}")
                if len(images) > 0:
                    print(f"\n   Primeras 3 imágenes:")
                    for img in images[:3]:
                        print(f"     - {img}")
        elif isinstance(data, list):
            print(f"   Total imágenes: {len(data)}")
            if len(data) > 0:
                print(f"\n   Primeras 3 imágenes:")
                for img in data[:3]:
                    print(f"     - {img}")
except Exception as e:
    print(f"   Error: {e}")

# 2. Try different image endpoints
print("\n2. Intentando otros endpoints de imágenes")
endpoints = [
    "/api/v1/images",
    "/api/v1/board/images",
    "/api/v1/queue/all",
    "/api/v1/queue/default",
    "/api/v1/execution/history",
]

for endpoint in endpoints:
    print(f"\n   [{endpoint}]")
    try:
        resp = requests.get(f"{API_BASE}{endpoint}", timeout=5)
        print(f"      Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"      [SUCCESS] Keys: {list(data.keys())[:5]}...")
            
            # Print first level structure
            if isinstance(data, dict) and len(data) < 20:
                print(f"      Data: {json.dumps(data, indent=8)[:500]}")
    except Exception as e:
        print(f"      Error: {type(e).__name__}")

# 3. Try WebSocket or Server-Sent Events
print("\n3. Investigando rutas raíz disponibles")
try:
    resp = requests.get(f"{API_BASE}/openapi.json", timeout=10)
    if resp.status_code == 200:
        data = resp.json()
        print(f"   OpenAPI encontrado!")
        print(f"   Paths disponibles (primeras 20):")
        paths = list(data.get("paths", {}).keys())[:20]
        for path in paths:
            print(f"     - {path}")
except:
    print("   OpenAPI no disponible")

# 4. Check all endpoints starting with 'queue'
print("\n4. Endpoints que contienen 'queue'")
try:
    resp = requests.get(f"{API_BASE}/openapi.json", timeout=10)
    if resp.status_code == 200:
        data = resp.json()
        paths = data.get("paths", {})
        queue_paths = [p for p in paths.keys() if 'queue' in p]
        for path in sorted(queue_paths):
            print(f"     - {path}")
except:
    pass

