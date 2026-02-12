#!/usr/bin/env python3
"""
Debug simple para ver la estructura exacta retornada por InvokeAI 6.10
"""
import requests
import json
import uuid
import time

API_BASE = "http://192.168.1.217:9090"

# 1. Get model info
print("=" * 80)
print("1. OBTENIENDO INFORMACIÓN DEL MODELO")
print("=" * 80)

models_response = requests.get(f"{API_BASE}/api/v2/models/")
models_data = models_response.json()
print(f"Total modelos: {len(models_data.get('models', []))}")

# Buscar Dreamshaper 8
model_info = None
for model in models_data.get("models", []):
    if model.get("name") == "Dreamshaper 8" and model.get("type") == "main":
        model_info = model
        break

if model_info:
    print(f"Modelo encontrado: {model_info.get('name')}")
    print(f"  - Key: {model_info.get('key')}")
    print(f"  - Base: {model_info.get('base')}")
    print(f"  - Type: {model_info.get('type')}")
else:
    print("ERROR: Modelo no encontrado")
    exit(1)

# 2. Crear un workflow simple
print("\n" + "=" * 80)
print("2. CREANDO WORKFLOW")
print("=" * 80)

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
            "prompt": "a simple red cube",
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
            "seed": 12345,
            "width": 512,
            "height": 512,
            "use_cpu": False,
            "is_intermediate": True,
        },
        denoise_latents_id: {
            "type": "denoise_latents",
            "id": denoise_latents_id,
            "steps": 5,
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
        {
            "source": {"node_id": model_loader_id, "field": "clip"},
            "destination": {"node_id": positive_prompt_id, "field": "clip"}
        },
        {
            "source": {"node_id": model_loader_id, "field": "clip"},
            "destination": {"node_id": negative_prompt_id, "field": "clip"}
        },
        {
            "source": {"node_id": model_loader_id, "field": "unet"},
            "destination": {"node_id": denoise_latents_id, "field": "unet"}
        },
        {
            "source": {"node_id": positive_prompt_id, "field": "conditioning"},
            "destination": {"node_id": denoise_latents_id, "field": "positive_conditioning"}
        },
        {
            "source": {"node_id": negative_prompt_id, "field": "conditioning"},
            "destination": {"node_id": denoise_latents_id, "field": "negative_conditioning"}
        },
        {
            "source": {"node_id": noise_id, "field": "noise"},
            "destination": {"node_id": denoise_latents_id, "field": "noise"}
        },
        {
            "source": {"node_id": denoise_latents_id, "field": "latents"},
            "destination": {"node_id": latents_to_image_id, "field": "latents"}
        },
        {
            "source": {"node_id": model_loader_id, "field": "vae"},
            "destination": {"node_id": latents_to_image_id, "field": "vae"}
        }
    ]
}

print("Workflow creado")

# 3. Enqueue
print("\n" + "=" * 80)
print("3. ENQUEUING BATCH")
print("=" * 80)

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

print(f"Enqueue status: {enqueue_response.status_code}")
enqueue_result = enqueue_response.json()
print("Enqueue response:")
print(json.dumps(enqueue_result, indent=2))

# Extract batch ID
batch_id = enqueue_result.get("batch", {}).get("batch_id")
if not batch_id:
    print("ERROR: No batch_id in response")
    exit(1)

print(f"\nBatch ID: {batch_id}")

# 4. Monitorear progreso
print("\n" + "=" * 80)
print("4. MONITOREANDO PROGRESO")
print("=" * 80)

max_attempts = 30
for attempt in range(max_attempts):
    time.sleep(3)
    
    # Check queue status
    queue_response = requests.get(f"{API_BASE}/api/v1/queue/default/status")
    queue_data = queue_response.json()
    queue_info = queue_data.get("queue", {})
    
    print(f"\nAttempt {attempt+1}:")
    print(f"  - Pending: {queue_info.get('pending')}")
    print(f"  - In progress: {queue_info.get('in_progress')}")
    print(f"  - Completed: {queue_info.get('completed')}")
    print(f"  - Failed: {queue_info.get('failed')}")
    
    # Try to get session info if batch_id is also session_id
    try:
        session_response = requests.get(f"{API_BASE}/api/v1/sessions/{batch_id}", timeout=5)
        if session_response.status_code == 200:
            session_data = session_response.json()
            print(f"\n[OK 200] Session encontrada:")
            print(json.dumps(session_data, indent=2))
            
            # Check for image
            outputs = session_data.get("outputs", {})
            for node_id, output in outputs.items():
                if isinstance(output, dict):
                    if "image" in output:
                        image_name = output["image"].get("image_name") if isinstance(output["image"], dict) else output["image"]
                        if image_name:
                            print(f"\n✅ ENCONTRADO IMAGE_NAME: {image_name}")
                            print("\nUrl de descarga: {API_BASE}/api/v1/images/i/{image_name}/full")
                            exit(0)
                    
                    if "image_name" in output:
                        image_name = output.get("image_name")
                        if image_name:
                            print(f"\n✅ ENCONTRADO IMAGE_NAME (direct): {image_name}")
                            print(f"\nUrl de descarga: {API_BASE}/api/v1/images/i/{image_name}/full")
                            exit(0)
        elif session_response.status_code == 404:
            print(f"  - Session {batch_id}: 404 (aún no disponible)")
    except Exception as e:
        print(f"  - Error checking session: {e}")
    
    # Check recent sessions
    try:
        sessions_response = requests.get(f"{API_BASE}/api/v1/sessions?limit=3", timeout=5)
        if sessions_response.status_code == 200:
            sessions_list = sessions_response.json()
            if isinstance(sessions_list, list) and len(sessions_list) > 0:
                print(f"  - Sesiones recientes: {len(sessions_list)}")
                for s in sessions_list:
                    session_id = s.get("id", "unknown")
                    outputs_count = len(s.get("outputs", {}))
                    print(f"    - Session {session_id}: {outputs_count} outputs")
    except Exception as e:
        print(f"  - Error checking recent sessions: {e}")

print("\nTIMEOUT: No se encontró imagen después de múltiples intentos")
