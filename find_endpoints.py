#!/usr/bin/env python3
"""
Debug para encontrar cómo acceder a los items completados
"""
import requests
import json
import uuid
import time

API_BASE = "http://192.168.1.217:9090"

# 1. Get model info
print("Obteniendo modelo...")
models_response = requests.get(f"{API_BASE}/api/v2/models/")
models_data = models_response.json()

model_info = None
for model in models_data.get("models", []):
    if model.get("name") == "Dreamshaper 8" and model.get("type") == "main":
        model_info = model
        break

if not model_info:
    print("ERROR: Modelo no encontrado")
    exit(1)

# 2. Create workflow
print("Creando workflow...")
model_loader_id = str(uuid.uuid4())
positive_prompt_id = str(uuid.uuid4())
negative_prompt_id = str(uuid.uuid4())
noise_id = str(uuid.uuid4())
denoise_latents_id = str(uuid.uuid4())
latents_to_image_id = str(uuid.uuid4())

graph = {
    "nodes": {
        model_loader_id: {
            "type": "main_model_loader",
            "id": model_loader_id,
            "is_intermediate": True,
            "model": {
                "key": model_info["key"],
                "hash": model_info.get("hash", ""),
                "name": model_info["name"],
                "base": model_info["base"],
                "type": model_info["type"]
            }
        },
        positive_prompt_id: {
            "type": "compel",
            "id": positive_prompt_id,
            "prompt": "a simple blue sphere",
            "is_intermediate": True,
        },
        negative_prompt_id: {
            "type": "compel",
            "id": negative_prompt_id,
            "prompt": "",
            "is_intermediate": True,
        },
        noise_id: {
            "type": "noise",
            "id": noise_id,
            "seed": 54321,
            "width": 512,
            "height": 512,
            "use_cpu": False,
            "is_intermediate": True,
        },
        denoise_latents_id: {
            "type": "denoise_latents",
            "id": denoise_latents_id,
            "steps": 3,
            "cfg_scale": 7.0,
            "denoising_start": 0.0,
            "denoising_end": 1.0,
            "scheduler": "euler",
            "is_intermediate": True,
        },
        latents_to_image_id: {
            "type": "l2i",
            "id": latents_to_image_id,
            "is_intermediate": False,
            "use_cache": False,
            "fp32": False,
        }
    },
    "edges": [
        {"source": {"node_id": model_loader_id, "field": "clip"}, "destination": {"node_id": positive_prompt_id, "field": "clip"}},
        {"source": {"node_id": model_loader_id, "field": "clip"}, "destination": {"node_id": negative_prompt_id, "field": "clip"}},
        {"source": {"node_id": model_loader_id, "field": "unet"}, "destination": {"node_id": denoise_latents_id, "field": "unet"}},
        {"source": {"node_id": positive_prompt_id, "field": "conditioning"}, "destination": {"node_id": denoise_latents_id, "field": "positive_conditioning"}},
        {"source": {"node_id": negative_prompt_id, "field": "conditioning"}, "destination": {"node_id": denoise_latents_id, "field": "negative_conditioning"}},
        {"source": {"node_id": noise_id, "field": "noise"}, "destination": {"node_id": denoise_latents_id, "field": "noise"}},
        {"source": {"node_id": denoise_latents_id, "field": "latents"}, "destination": {"node_id": latents_to_image_id, "field": "latents"}},
        {"source": {"node_id": model_loader_id, "field": "vae"}, "destination": {"node_id": latents_to_image_id, "field": "vae"}},
    ]
}

# 3. Enqueue
print("Enqueueing batch...")
batch_data = {
    "batch": {
        "graph": graph,
        "runs": 1,
        "data": []
    },
    "prepend": False
}

enqueue_response = requests.post(
    f"{API_BASE}/api/v1/queue/default/enqueue_batch",
    json=batch_data,
    timeout=30
)

enqueue_result = enqueue_response.json()
batch_id = enqueue_result.get("batch", {}).get("batch_id")
item_ids = enqueue_result.get("item_ids", [])

print(f"Batch ID: {batch_id}")
print(f"Item IDs: {item_ids}")
if not item_ids:
    print("ERROR: No item_ids")
    exit(1)

item_id = item_ids[0]

# 4. Monitor progress by checking different endpoints
print("\n" + "="*80)
print("Buscando endpoints para acceder a items...")
print("="*80)

# Esperar un poco para que se procese
time.sleep(5)

# Try different endpoints
endpoints_to_try = [
    f"/api/v1/queue/default/item/{item_id}",
    f"/api/v1/queue/{item_id}",
    f"/api/v1/items/{item_id}",
    f"/api/v1/execution/{item_id}",
    f"/api/v1/queue/items/{item_id}",
]

for endpoint in endpoints_to_try:
    full_url = f"{API_BASE}{endpoint}"
    print(f"\n[*] Intentando: {endpoint}")
    try:
        resp = requests.get(full_url, timeout=5)
        print(f"    Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"    [SUCCESS] Encontrado!")
            print(f"    Keys: {list(data.keys())}")
            print(f"\n    Respuesta completa:")
            print(json.dumps(data, indent=2))
            exit(0)
    except Exception as e:
        print(f"    Error: {e}")

# If no direct endpoint found, check queue history
print("\n" + "="*80)
print("Intentando acceder al historial de cola...")
print("="*80)

queue_full = requests.get(f"{API_BASE}/api/v1/queue/default").json()
print(f"\nQueue info:")
print(json.dumps(queue_full, indent=2))

