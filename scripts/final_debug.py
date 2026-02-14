#!/usr/bin/env python3
"""
Debug final - Usando el endpoint correcto para obtener items
"""
import requests
import json
import uuid
import time

API_BASE = "http://192.168.1.217:9090"
QUEUE_ID = "default"

# 1. Get model
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

print(f"Modelo encontrado: {model_info['name']}")

# 2. Create workflow 
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
            "prompt": "a beautiful sunset over mountains",
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
            "seed": 99999,
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
    f"{API_BASE}/api/v1/queue/{QUEUE_ID}/enqueue_batch",
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

# 4. Monitor using the correct endpoint
print(f"\nMonitoreando item {item_id} en queue {QUEUE_ID}...")
print("="*80)

for attempt in range(60):
    time.sleep(2)
    
    try:
        # Usar el endpoint correcto: /api/v1/queue/{queue_id}/i/{item_id}
        item_response = requests.get(
            f"{API_BASE}/api/v1/queue/{QUEUE_ID}/i/{item_id}",
            timeout=10
        )
        
        if item_response.status_code == 200:
            item_data = item_response.json()
            status = item_data.get("status", "unknown")
            
            print(f"Attempt {attempt+1}: Status = {status}")
            
            if status == "completed":
                print(f"\n[SUCCESS] Item completado!")
                print("\nDatos del item:")
                print(json.dumps(item_data, indent=2))
                
                # Try to extract image_name from outputs
                outputs = item_data.get("outputs", {})
                print(f"\n\nOutputs keys: {list(outputs.keys())}")
                
                for node_id, output in outputs.items():
                    print(f"\n\nNode {node_id}:")
                    print(f"  Type of output: {type(output)}")
                    print(f"  Keys: {list(output.keys()) if isinstance(output, dict) else 'N/A'}")
                    
                    # Try to find image_name
                    if isinstance(output, dict):
                        if "image" in output:
                            print(f"  Has 'image' field")
                            image = output["image"]
                            if isinstance(image, dict):
                                print(f"    image is dict with keys: {list(image.keys())}")
                                if "image_name" in image:
                                    image_name = image["image_name"]
                                    print(f"\n\n>>> FOUND IMAGE_NAME: {image_name}")
                                    print(f">>> Download URL: {API_BASE}/api/v1/images/i/{image_name}/full")
                                    exit(0)
                        
                        if "image_name" in output:
                            image_name = output["image_name"]
                            print(f"\n\n>>> FOUND IMAGE_NAME (direct): {image_name}")
                            print(f">>> Download URL: {API_BASE}/api/v1/images/i/{image_name}/full")
                            exit(0)
                
                print("\n\nERROR: Image not found in outputs structure")
                exit(1)
            
            elif status == "failed":
                print(f"[ERROR] Item failed!")
                print(f"Error: {item_data.get('error')}")
                exit(1)
                
        elif item_response.status_code == 404:
            print(f"Attempt {attempt+1}: Item not yet ready (404)")
        else:
            print(f"Attempt {attempt+1}: Unexpected status {item_response.status_code}")
    
    except Exception as e:
        print(f"Attempt {attempt+1}: Error - {e}")

print(f"\n\nTIMEOUT: Item did not complete after {60*2} seconds")

