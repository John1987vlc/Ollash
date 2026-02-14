import requests
import base64
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import asyncio
import aiohttp
import uuid
import time
from io import BytesIO
from PIL import Image

from backend.utils.core.tool_decorator import ollash_tool


class ImageGeneratorTools:
    def __init__(self, logger: Any, config: Optional[Dict] = None):
        self.logger = logger
        self.config = config or {}
        
        # Get Invoke UI URL from environment or config
        self.api_base_url = os.getenv(
            'INVOKE_UI_URL',
            self.config.get('invoke_ui_url', 'http://192.168.1.217:9090')
        )
        
        # InvokeAI 6.10 API endpoints
        self.enqueue_url = f"{self.api_base_url}/api/v1/queue/default/enqueue_batch"
        self.session_url = f"{self.api_base_url}/api/v1/sessions"
        self.images_url = f"{self.api_base_url}/api/v1/images"
        self.queue_status_url = f"{self.api_base_url}/api/v1/queue/default/status"
        self.upload_url = f"{self.api_base_url}/api/v1/images/upload"
        self.models_url = f"{self.api_base_url}/api/v2/models/"
        
        # Default output directory for generated images
        self.output_dir = Path(os.getenv(
            'IMAGE_OUTPUT_DIR',
            self.config.get('image_output_dir', 'generated_images')
        ))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache for model keys
        self._model_cache = {}

    def _get_model_key(self, model_name: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene la key UUID y metadata del modelo desde la API.
        
        Args:
            model_name: Nombre del modelo (ej: "Dreamshaper 8")
            
        Returns:
            Dict con key, hash, name, base, type del modelo o None si no se encuentra
        """
        # Verificar si ya está en caché
        if model_name in self._model_cache:
            return self._model_cache[model_name]
        
        try:
            # Consultar la API para obtener todos los modelos
            response = requests.get(self.models_url, timeout=10)
            
            if response.status_code != 200:
                self.logger.error(f"Failed to fetch models: {response.status_code}")
                return None
            
            data = response.json()
            models = data.get("models", [])
            
            # Buscar el modelo por nombre
            for model in models:
                if model.get("name") == model_name and model.get("type") == "main":
                    model_info = {
                        "key": model.get("key"),
                        "hash": model.get("hash", ""),
                        "name": model.get("name"),
                        "base": model.get("base"),
                        "type": model.get("type")
                    }
                    
                    # Guardar en caché
                    self._model_cache[model_name] = model_info
                    return model_info
            
            self.logger.warning(f"Model '{model_name}' not found in API")
            return None
            
        except Exception as e:
            self.logger.error(f"Error fetching model info: {str(e)}")
            return None

    def _create_text2img_graph(
        self,
        prompt: str,
        negative_prompt: str = "",
        steps: int = 25,
        cfg_scale: float = 7.0,
        width: int = 512,
        height: int = 512,
        seed: int = -1,
        scheduler: str = "euler",
        model_name: str = "Dreamshaper 8"
    ) -> Dict[str, Any]:
        """
        Creates a text-to-image workflow graph for InvokeAI 6.10+
        
        This creates a node-based graph that InvokeAI can execute.
        """
        # Obtener información del modelo desde la API
        model_info = self._get_model_key(model_name)
        
        if not model_info:
            raise ValueError(f"Model '{model_name}' not found. Use check_invoke_ui_status() to see available models.")
        
        # Generate unique IDs for each node
        model_loader_id = str(uuid.uuid4())
        positive_prompt_id = str(uuid.uuid4())
        negative_prompt_id = str(uuid.uuid4())
        noise_id = str(uuid.uuid4())
        denoise_latents_id = str(uuid.uuid4())
        latents_to_image_id = str(uuid.uuid4())
        
        if seed == -1:
            seed = int(time.time() * 1000) % (2**32)
        
        # Build the graph structure
        graph = {
            "nodes": {
                # Main model loader - Usando la información real de la API
                model_loader_id: {
                    "type": "main_model_loader",
                    "id": model_loader_id,
                    "is_intermediate": True,
                    "model": {
                        "key": model_info["key"],       # UUID del modelo
                        "hash": model_info["hash"],     # Hash del modelo
                        "name": model_info["name"],     # Nombre exacto
                        "base": model_info["base"],     # Base (sd-1, sdxl, flux)
                        "type": model_info["type"]      # Tipo (main)
                    }
                },
                # Positive prompt (CLIP encoder)
                positive_prompt_id: {
                    "type": "compel",
                    "id": positive_prompt_id,
                    "prompt": prompt,
                    "is_intermediate": True,
                },
                # Negative prompt (CLIP encoder)
                negative_prompt_id: {
                    "type": "compel",
                    "id": negative_prompt_id,
                    "prompt": negative_prompt,
                    "is_intermediate": True,
                },
                # Noise generation
                noise_id: {
                    "type": "noise",
                    "id": noise_id,
                    "seed": seed,
                    "width": width,
                    "height": height,
                    "use_cpu": False,
                    "is_intermediate": True,
                },
                # Denoising (main generation step)
                denoise_latents_id: {
                    "type": "denoise_latents",
                    "id": denoise_latents_id,
                    "steps": steps,
                    "cfg_scale": cfg_scale,
                    "denoising_start": 0.0,
                    "denoising_end": 1.0,
                    "scheduler": scheduler,
                    "is_intermediate": True,
                },
                # Convert latents to image (VAE decode)
                latents_to_image_id: {
                    "type": "l2i",
                    "id": latents_to_image_id,
                    "is_intermediate": False,
                    "use_cache": False,
                    "fp32": False,
                }
            },
            "edges": [
                # Connect model to CLIP encoders
                {
                    "source": {
                        "node_id": model_loader_id,
                        "field": "clip"
                    },
                    "destination": {
                        "node_id": positive_prompt_id,
                        "field": "clip"
                    }
                },
                {
                    "source": {
                        "node_id": model_loader_id,
                        "field": "clip"
                    },
                    "destination": {
                        "node_id": negative_prompt_id,
                        "field": "clip"
                    }
                },
                # Connect model UNet to denoiser
                {
                    "source": {
                        "node_id": model_loader_id,
                        "field": "unet"
                    },
                    "destination": {
                        "node_id": denoise_latents_id,
                        "field": "unet"
                    }
                },
                # Connect prompts to denoiser
                {
                    "source": {
                        "node_id": positive_prompt_id,
                        "field": "conditioning"
                    },
                    "destination": {
                        "node_id": denoise_latents_id,
                        "field": "positive_conditioning"
                    }
                },
                {
                    "source": {
                        "node_id": negative_prompt_id,
                        "field": "conditioning"
                    },
                    "destination": {
                        "node_id": denoise_latents_id,
                        "field": "negative_conditioning"
                    }
                },
                # Connect noise to denoiser
                {
                    "source": {
                        "node_id": noise_id,
                        "field": "noise"
                    },
                    "destination": {
                        "node_id": denoise_latents_id,
                        "field": "noise"
                    }
                },
                # Connect denoiser to VAE
                {
                    "source": {
                        "node_id": denoise_latents_id,
                        "field": "latents"
                    },
                    "destination": {
                        "node_id": latents_to_image_id,
                        "field": "latents"
                    }
                },
                # Connect VAE from model
                {
                    "source": {
                        "node_id": model_loader_id,
                        "field": "vae"
                    },
                    "destination": {
                        "node_id": latents_to_image_id,
                        "field": "vae"
                    }
                }
            ]
        }
        
        return graph

    def _create_img2img_graph(
        self,
        prompt: str,
        image_name: str,
        negative_prompt: str = "",
        steps: int = 25,
        cfg_scale: float = 7.0,
        denoising_strength: float = 0.75,
        seed: int = -1,
        scheduler: str = "euler",
        model_name: str = "Dreamshaper 8"
    ) -> Dict[str, Any]:
        """
        Creates an image-to-image workflow graph for InvokeAI 6.10+
        """
        # Obtener información del modelo desde la API
        model_info = self._get_model_key(model_name)
        
        if not model_info:
            raise ValueError(f"Model '{model_name}' not found. Use check_invoke_ui_status() to see available models.")
        
        # Generate unique IDs for each node
        model_loader_id = str(uuid.uuid4())
        image_loader_id = str(uuid.uuid4())
        image_to_latents_id = str(uuid.uuid4())
        positive_prompt_id = str(uuid.uuid4())
        negative_prompt_id = str(uuid.uuid4())
        noise_id = str(uuid.uuid4())
        denoise_latents_id = str(uuid.uuid4())
        latents_to_image_id = str(uuid.uuid4())
        
        if seed == -1:
            seed = int(time.time() * 1000) % (2**32)
        
        # Build the graph structure
        graph = {
            "nodes": {
                # Main model loader - Usando la información real de la API
                model_loader_id: {
                    "type": "main_model_loader",
                    "id": model_loader_id,
                    "is_intermediate": True,
                    "model": {
                        "key": model_info["key"],
                        "hash": model_info["hash"],
                        "name": model_info["name"],
                        "base": model_info["base"],
                        "type": model_info["type"]
                    }
                },
                # Load input image
                image_loader_id: {
                    "type": "image",
                    "id": image_loader_id,
                    "image": {
                        "image_name": image_name
                    },
                    "is_intermediate": True,
                },
                # Convert image to latents (VAE encode)
                image_to_latents_id: {
                    "type": "i2l",
                    "id": image_to_latents_id,
                    "is_intermediate": True,
                    "fp32": False,
                },
                # Positive prompt (CLIP encoder)
                positive_prompt_id: {
                    "type": "compel",
                    "id": positive_prompt_id,
                    "prompt": prompt,
                    "is_intermediate": True,
                },
                # Negative prompt (CLIP encoder)
                negative_prompt_id: {
                    "type": "compel",
                    "id": negative_prompt_id,
                    "prompt": negative_prompt,
                    "is_intermediate": True,
                },
                # Noise generation
                noise_id: {
                    "type": "noise",
                    "id": noise_id,
                    "seed": seed,
                    "use_cpu": False,
                    "is_intermediate": True,
                },
                # Denoising (main generation step)
                denoise_latents_id: {
                    "type": "denoise_latents",
                    "id": denoise_latents_id,
                    "steps": steps,
                    "cfg_scale": cfg_scale,
                    "denoising_start": 0.0,
                    "denoising_end": denoising_strength,
                    "scheduler": scheduler,
                    "is_intermediate": True,
                },
                # Convert latents to image (VAE decode)
                latents_to_image_id: {
                    "type": "l2i",
                    "id": latents_to_image_id,
                    "is_intermediate": False,
                    "use_cache": False,
                    "fp32": False,
                }
            },
            "edges": [
                # Connect model to CLIP encoders
                {
                    "source": {
                        "node_id": model_loader_id,
                        "field": "clip"
                    },
                    "destination": {
                        "node_id": positive_prompt_id,
                        "field": "clip"
                    }
                },
                {
                    "source": {
                        "node_id": model_loader_id,
                        "field": "clip"
                    },
                    "destination": {
                        "node_id": negative_prompt_id,
                        "field": "clip"
                    }
                },
                # Connect image to VAE encoder
                {
                    "source": {
                        "node_id": image_loader_id,
                        "field": "image"
                    },
                    "destination": {
                        "node_id": image_to_latents_id,
                        "field": "image"
                    }
                },
                # Connect VAE to encoder
                {
                    "source": {
                        "node_id": model_loader_id,
                        "field": "vae"
                    },
                    "destination": {
                        "node_id": image_to_latents_id,
                        "field": "vae"
                    }
                },
                # Connect model UNet to denoiser
                {
                    "source": {
                        "node_id": model_loader_id,
                        "field": "unet"
                    },
                    "destination": {
                        "node_id": denoise_latents_id,
                        "field": "unet"
                    }
                },
                # Connect prompts to denoiser
                {
                    "source": {
                        "node_id": positive_prompt_id,
                        "field": "conditioning"
                    },
                    "destination": {
                        "node_id": denoise_latents_id,
                        "field": "positive_conditioning"
                    }
                },
                {
                    "source": {
                        "node_id": negative_prompt_id,
                        "field": "conditioning"
                    },
                    "destination": {
                        "node_id": denoise_latents_id,
                        "field": "negative_conditioning"
                    }
                },
                # Connect noise to denoiser
                {
                    "source": {
                        "node_id": noise_id,
                        "field": "noise"
                    },
                    "destination": {
                        "node_id": denoise_latents_id,
                        "field": "noise"
                    }
                },
                # Connect input latents to denoiser
                {
                    "source": {
                        "node_id": image_to_latents_id,
                        "field": "latents"
                    },
                    "destination": {
                        "node_id": denoise_latents_id,
                        "field": "latents"
                    }
                },
                # Connect denoiser to VAE decoder
                {
                    "source": {
                        "node_id": denoise_latents_id,
                        "field": "latents"
                    },
                    "destination": {
                        "node_id": latents_to_image_id,
                        "field": "latents"
                    }
                },
                # Connect VAE from model to decoder
                {
                    "source": {
                        "node_id": model_loader_id,
                        "field": "vae"
                    },
                    "destination": {
                        "node_id": latents_to_image_id,
                        "field": "vae"
                    }
                }
            ]
        }
        
        return graph

    def _wait_for_completion(self, batch_id: str, item_ids: List[int], queue_id: str = "default", timeout: int = 300) -> Optional[str]:
        """
        Wait for a batch to complete and return the generated image name.
        Uses the correct InvokeAI 6.10+ API endpoint: /api/v1/queue/{queue_id}/i/{item_id}
        
        Args:
            batch_id: The batch ID from enqueue_batch response
            item_ids: List of item IDs from enqueue_batch response
            queue_id: The queue ID (default: "default")
            timeout: Maximum time to wait in seconds
            
        Returns:
            The image name if successful, None otherwise
        """
        if not item_ids:
            self.logger.error("❌ No item_ids provided")
            return None
        
        item_id = item_ids[0]  # Use the first item
        start_time = time.time()
        attempts = 0
        
        while time.time() - start_time < timeout:
            attempts += 1
            try:
                # Use the CORRECT endpoint: /api/v1/queue/{queue_id}/i/{item_id}
                item_response = requests.get(
                    f"{self.api_base_url}/api/v1/queue/{queue_id}/i/{item_id}",
                    timeout=10
                )
                
                self.logger.debug(f"[Attempt {attempts}] Item status code: {item_response.status_code}")
                
                if item_response.status_code == 200:
                    item_data = item_response.json()
                    status = item_data.get("status", "unknown")
                    self.logger.debug(f"Item status: {status}")
                    
                    if status == "completed":
                        # Item completed, now find the image output
                        session = item_data.get("session", {})
                        results = session.get("results", {})
                        
                        self.logger.debug(f"Session results keys: {list(results.keys())}")
                        
                        # Look for the image output in results
                        for node_id, result in results.items():
                            result_type = result.get("type", "")
                            self.logger.debug(f"Node {node_id}: type={result_type}")
                            
                            if result_type == "image_output":
                                # Found the image output node
                                image_data = result.get("image", {})
                                if isinstance(image_data, dict):
                                    image_name = image_data.get("image_name")
                                    if image_name:
                                        self.logger.info(f"✅ Found image_name: {image_name}")
                                        return image_name
                        
                        # If we get here, item completed but image not found
                        self.logger.warning(f"Item completed but image_output not found in results")
                        return None
                    
                    elif status == "failed":
                        self.logger.error(f"❌ Item failed")
                        error = item_data.get("error")
                        if error:
                            self.logger.error(f"Error details: {error}")
                        return None
                    
                    else:  # Processing or pending
                        self.logger.debug(f"Item still processing... ({time.time() - start_time:.1f}s elapsed)")
                
                elif item_response.status_code == 404:
                    self.logger.debug(f"Item {item_id} not yet ready (404)")
                else:
                    self.logger.warning(f"Unexpected status code: {item_response.status_code}")
                
                # Wait before next check
                time.sleep(2)
                
            except Exception as e:
                self.logger.error(f"Error checking item status: {str(e)}", exc_info=True)
                time.sleep(2)
        
        self.logger.error(f"Timeout waiting for image generation after {timeout}s")
        return None

    def _download_image(self, image_name: str, output_path: Path) -> bool:
        """
        Download an image from InvokeAI and save it locally.
        
        Args:
            image_name: The name of the image in InvokeAI
            output_path: Where to save the image
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not image_name:
                self.logger.error("❌ Image name is empty or None")
                return False
            
            # Get image URL
            image_url = f"{self.images_url}/i/{image_name}/full"
            self.logger.info(f"📍 Attempting to download from: {image_url}")
            
            response = requests.get(image_url, timeout=30)
            self.logger.debug(f"Download response status: {response.status_code}")
            
            if response.status_code == 200:
                # Verify we got image data
                if len(response.content) == 0:
                    self.logger.error("❌ Downloaded file is empty")
                    return False
                
                # Save the image
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, "wb") as f:
                    f.write(response.content)
                
                file_size = output_path.stat().st_size
                self.logger.info(f"✅ Image downloaded successfully ({file_size} bytes): {output_path}")
                return True
            else:
                self.logger.error(f"❌ Failed to download image: HTTP {response.status_code}")
                self.logger.error(f"Response text: {response.text[:500]}")
                return False
                
        except requests.exceptions.Timeout:
            self.logger.error(f"❌ Download timeout for image: {image_name}")
            return False
        except requests.exceptions.ConnectionError as e:
            self.logger.error(f"❌ Connection error downloading image: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"❌ Error downloading image: {str(e)}", exc_info=True)
            return False

    @ollash_tool(
        name="generate_image",
        description="Generates an image using Stable Diffusion via Invoke UI. Requires Invoke UI running on http://192.168.1.217:9090",
        parameters={
            "prompt": {
                "type": "string",
                "description": "The text prompt describing the image to generate"
            },
            "negative_prompt": {
                "type": "string",
                "description": "Optional: Text describing what to avoid in the image"
            },
            "model_name": {
                "type": "string",
                "description": "Optional: The name of the Stable Diffusion model to use. Available models: 'Dreamshaper 8' (SD1.5), 'Juggernaut XL v9' (SDXL), 'FLUX.1 dev (quantized)', 'FLUX.1 schnell (quantized)', 'FLUX Fill', 'Z-Image Turbo (quantized)'. Default: 'Dreamshaper 8'"
            },
            "steps": {
                "type": "integer",
                "description": "Number of inference steps (higher = better quality but slower). Default: 25"
            },
            "cfg_scale": {
                "type": "number",
                "description": "Guidance scale (how closely to follow the prompt). Default: 7.0"
            },
            "width": {
                "type": "integer",
                "description": "Image width in pixels. SD1.5: 512, SDXL/FLUX: 1024. Default: 512"
            },
            "height": {
                "type": "integer",
                "description": "Image height in pixels. SD1.5: 512, SDXL/FLUX: 1024. Default: 512"
            },
            "scheduler": {
                "type": "string",
                "description": "Sampling method (e.g., 'euler', 'ddim', 'dpmpp_2m'). Default: 'euler'"
            },
            "filename": {
                "type": "string",
                "description": "Optional: Custom filename for the generated image (without extension)"
            }
        },
        toolset_id="image_generator_tools",
        agent_types=["code", "auto_agent"],
        required=["prompt"],
        is_async_safe=True
    )
    def generate_image(
        self,
        prompt: str,
        negative_prompt: str = "",
        model_name: str = "Dreamshaper 8",
        steps: int = 25,
        cfg_scale: float = 7.0,
        width: int = 512,
        height: int = 512,
        scheduler: str = "euler",
        filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generates an image using Invoke UI Stable Diffusion API (6.10+).
        
        Args:
            prompt: Text description of the image to generate
            negative_prompt: Text describing what to avoid
            model_name: The name of the Stable Diffusion model to use
            steps: Number of inference steps (quality vs speed tradeoff)
            cfg_scale: How closely to follow the prompt
            width: Image width in pixels
            height: Image height in pixels
            scheduler: Sampling method (euler, ddim, etc.)
            filename: Custom filename (without extension)
        
        Returns:
            Dict with status, file path, or error details
        """
        self.logger.info(f"🎨 Generating image with prompt: {prompt[:100]}... using model: {model_name}")
        
        # Generate filename if not provided
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"generated_{timestamp}"
        
        output_path = self.output_dir / f"{filename}.png"
        
        try:
            # Create the text2img workflow graph
            graph = self._create_text2img_graph(
                prompt=prompt,
                negative_prompt=negative_prompt,
                steps=max(1, min(steps, 150)),
                cfg_scale=cfg_scale,
                width=width,
                height=height,
                scheduler=scheduler,
                model_name=model_name
            )
            
            # Prepare the batch request
            batch_data = {
                "batch": {
                    "graph": graph,
                    "runs": 1,
                    "data": []
                },
                "prepend": False
            }
            
            self.logger.debug(f"Connecting to {self.enqueue_url}")
            
            # Enqueue the batch
            response = requests.post(
                self.enqueue_url,
                json=batch_data,
                timeout=30
            )
            
            if response.status_code != 200:
                error_msg = f"API returned status {response.status_code}"
                try:
                    error_details = response.json()
                    error_msg += f": {error_details}"
                except:
                    error_msg += f": {response.text[:200]}"
                
                self.logger.error(f"❌ Image generation failed: {error_msg}")
                return {
                    "ok": False,
                    "error": error_msg,
                    "status_code": response.status_code
                }
            
            # Parse the response to get session info
            result = response.json()
            
            # Extract batch/session ID and item IDs
            batch_id = result.get("batch", {}).get("batch_id")
            item_ids = result.get("item_ids", [])
            
            if not batch_id:
                self.logger.error("❌ No batch ID in response")
                return {
                    "ok": False,
                    "error": "No batch ID returned from API"
                }
            
            if not item_ids:
                self.logger.error("❌ No item IDs in response")
                return {
                    "ok": False,
                    "error": "No item IDs returned from API"
                }
            
            self.logger.info(f"📋 Batch enqueued: {batch_id} with items: {item_ids}")
            
            # Wait for completion
            self.logger.info("⏳ Waiting for image generation...")
            image_name = self._wait_for_completion(batch_id, item_ids, timeout=300)
            
            self.logger.info(f"Result from _wait_for_completion: image_name={image_name}")
            
            if not image_name:
                self.logger.error("❌ Image generation timed out or failed - _wait_for_completion returned None")
                return {
                    "ok": False,
                    "error": "Image generation timed out or failed to complete"
                }
            
            # Download the image
            self.logger.info(f"⬇️ Downloading image: {image_name}")
            if not self._download_image(image_name, output_path):
                return {
                    "ok": False,
                    "error": "Failed to download generated image"
                }
            
            self.logger.info(f"✅ Image generated successfully: {output_path}")
            
            return {
                "ok": True,
                "path": str(output_path),
                "filename": output_path.name,
                "absolute_path": str(output_path.absolute()),
                "relative_path": str(output_path.relative_to(Path.cwd())) if output_path.is_relative_to(Path.cwd()) else str(output_path),
                "prompt": prompt,
                "size": f"{width}x{height}",
                "steps": steps,
                "invoke_image_name": image_name,
                "model_name": model_name
            }
        
        except ValueError as e:
            # Error de modelo no encontrado
            error_msg = str(e)
            self.logger.error(f"❌ {error_msg}")
            return {
                "ok": False,
                "error": error_msg
            }
        
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Cannot connect to Invoke UI at {self.api_base_url}. Is it running?"
            self.logger.error(f"❌ {error_msg}")
            return {
                "ok": False,
                "error": error_msg,
                "details": str(e)
            }
        
        except requests.exceptions.Timeout:
            error_msg = "Image generation request timed out"
            self.logger.error(f"❌ {error_msg}")
            return {
                "ok": False,
                "error": error_msg
            }
        
        except Exception as e:
            error_msg = f"Error generating image: {str(e)}"
            self.logger.error(f"❌ {error_msg}")
            return {
                "ok": False,
                "error": error_msg,
                "exception_type": type(e).__name__
            }

    @ollash_tool(
        name="generate_image_from_image",
        description="Generates an image from an existing image using img2img. Requires Invoke UI running on http://192.168.1.217:9090",
        parameters={
            "prompt": {
                "type": "string",
                "description": "The text prompt describing the desired output"
            },
            "image_path": {
                "type": "string",
                "description": "Path to the input image file"
            },
            "negative_prompt": {
                "type": "string",
                "description": "Optional: Text describing what to avoid in the image"
            },
            "model_name": {
                "type": "string",
                "description": "Optional: The name of the Stable Diffusion model to use. Default: 'Dreamshaper 8'"
            },
            "steps": {
                "type": "integer",
                "description": "Number of inference steps. Default: 25"
            },
            "cfg_scale": {
                "type": "number",
                "description": "Guidance scale. Default: 7.0"
            },
            "denoising_strength": {
                "type": "number",
                "description": "How much to change the image (0.0-1.0). Default: 0.75"
            },
            "scheduler": {
                "type": "string",
                "description": "Sampling method. Default: 'euler'"
            },
            "filename": {
                "type": "string",
                "description": "Optional: Custom filename for output (without extension)"
            }
        },
        toolset_id="image_generator_tools",
        agent_types=["code", "auto_agent"],
        required=["prompt", "image_path"],
        is_async_safe=True
    )
    def generate_image_from_image(
        self,
        prompt: str,
        image_path: str,
        negative_prompt: str = "",
        model_name: str = "Dreamshaper 8",
        steps: int = 25,
        cfg_scale: float = 7.0,
        denoising_strength: float = 0.75,
        scheduler: str = "euler",
        filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generates an image from an input image (img2img).
        
        Args:
            prompt: Text description of desired output
            image_path: Path to input image
            negative_prompt: Text describing what to avoid
            model_name: The name of the Stable Diffusion model to use
            steps: Number of inference steps
            cfg_scale: How closely to follow the prompt
            denoising_strength: How much to change (0.0-1.0, higher = more change)
            scheduler: Sampling method
            filename: Custom filename (without extension)
        
        Returns:
            Dict with status, file path, or error details
        """
        self.logger.info(f"🎨 Generating img2img with prompt: {prompt[:100]}... using model: {model_name}")
        
        # Generate filename if not provided
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"img2img_{timestamp}"
        
        output_path = self.output_dir / f"{filename}.png"
        
        try:
            # First, upload the input image to InvokeAI
            input_image_path = Path(image_path)
            if not input_image_path.exists():
                return {
                    "ok": False,
                    "error": f"Input image not found: {image_path}"
                }
            
            self.logger.info(f"⬆️ Uploading input image...")
            
            # Upload the image
            with open(input_image_path, "rb") as f:
                files = {
                    "file": (input_image_path.name, f, "image/png")
                }
                upload_response = requests.post(
                    self.upload_url,
                    files=files,
                    params={
                        "image_category": "general",
                        "is_intermediate": True
                    },
                    timeout=30
                )
            
            if upload_response.status_code != 201:
                return {
                    "ok": False,
                    "error": f"Failed to upload image: {upload_response.status_code}"
                }
            
            uploaded_image = upload_response.json()
            image_name = uploaded_image.get("image_name")
            
            if not image_name:
                return {
                    "ok": False,
                    "error": "No image_name in upload response"
                }
            
            self.logger.info(f"✅ Image uploaded: {image_name}")
            
            # Create the img2img workflow graph
            graph = self._create_img2img_graph(
                prompt=prompt,
                image_name=image_name,
                negative_prompt=negative_prompt,
                steps=max(1, min(steps, 150)),
                cfg_scale=cfg_scale,
                denoising_strength=max(0.0, min(1.0, denoising_strength)),
                scheduler=scheduler,
                model_name=model_name
            )
            
            # Prepare the batch request
            batch_data = {
                "batch": {
                    "graph": graph,
                    "runs": 1,
                    "data": []
                },
                "prepend": False
            }
            
            # Enqueue the batch
            response = requests.post(
                self.enqueue_url,
                json=batch_data,
                timeout=30
            )
            
            if response.status_code != 200:
                error_msg = f"API returned status {response.status_code}"
                try:
                    error_details = response.json()
                    error_msg += f": {error_details}"
                except:
                    error_msg += f": {response.text[:200]}"
                
                self.logger.error(f"❌ Image generation failed: {error_msg}")
                return {
                    "ok": False,
                    "error": error_msg,
                    "status_code": response.status_code
                }
            
            # Parse the response
            result = response.json()
            batch_id = result.get("batch", {}).get("batch_id")
            item_ids = result.get("item_ids", [])
            
            if not batch_id:
                return {
                    "ok": False,
                    "error": "No batch ID returned from API"
                }
            
            if not item_ids:
                return {
                    "ok": False,
                    "error": "No item IDs returned from API"
                }
            
            self.logger.info(f"📋 Batch enqueued: {batch_id} with items: {item_ids}")
            
            # Wait for completion
            self.logger.info("⏳ Waiting for image generation...")
            output_image_name = self._wait_for_completion(batch_id, item_ids, timeout=300)
            
            self.logger.info(f"Result from _wait_for_completion: output_image_name={output_image_name}")
            
            if not output_image_name:
                self.logger.error("❌ Image generation timed out or failed - _wait_for_completion returned None")
                return {
                    "ok": False,
                    "error": "Image generation timed out or failed to complete"
                }
            
            # Download the image
            self.logger.info(f"⬇️ Downloading image: {output_image_name}")
            if not self._download_image(output_image_name, output_path):
                return {
                    "ok": False,
                    "error": "Failed to download generated image"
                }
            
            self.logger.info(f"✅ Image generated successfully: {output_path}")
            
            return {
                "ok": True,
                "path": str(output_path),
                "filename": output_path.name,
                "absolute_path": str(output_path.absolute()),
                "relative_path": str(output_path.relative_to(Path.cwd())) if output_path.is_relative_to(Path.cwd()) else str(output_path),
                "prompt": prompt,
                "input_image": str(image_path),
                "denoising_strength": denoising_strength,
                "steps": steps,
                "invoke_image_name": output_image_name,
                "model_name": model_name
            }
        
        except ValueError as e:
            error_msg = str(e)
            self.logger.error(f"❌ {error_msg}")
            return {
                "ok": False,
                "error": error_msg
            }
        
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Cannot connect to Invoke UI at {self.api_base_url}. Is it running?"
            self.logger.error(f"❌ {error_msg}")
            return {
                "ok": False,
                "error": error_msg,
                "details": str(e)
            }
        
        except Exception as e:
            error_msg = f"Error in img2img generation: {str(e)}"
            self.logger.error(f"❌ {error_msg}")
            return {
                "ok": False,
                "error": error_msg,
                "exception_type": type(e).__name__
            }

    @ollash_tool(
        name="generate_image_batch",
        description="Generates multiple images from different prompts concurrently.",
        parameters={
            "prompts": {
                "type": "array",
                "description": "List of text prompts to generate images from",
                "items": {"type": "string"}
            },
            "steps": {
                "type": "integer",
                "description": "Number of inference steps. Default: 25"
            },
            "width": {
                "type": "integer",
                "description": "Image width in pixels. Default: 512"
            },
            "height": {
                "type": "integer",
                "description": "Image height in pixels. Default: 512"
            }
        },
        toolset_id="image_generator_tools",
        agent_types=["code", "auto_agent"],
        required=["prompts"],
        is_async_safe=True
    )
    def generate_image_batch(
        self,
        prompts: list,
        steps: int = 25,
        width: int = 512,
        height: int = 512
    ) -> Dict[str, Any]:
        """
        Generates multiple images from different prompts.
        
        Args:
            prompts: List of text prompts
            steps: Inference steps for all images
            width: Image width for all images
            height: Image height for all images
        
        Returns:
            Dict with list of generation results
        """
        self.logger.info(f"🎨 Generating {len(prompts)} images...")
        
        results = {
            "ok": True,
            "total": len(prompts),
            "generated": [],
            "failed": []
        }
        
        for idx, prompt in enumerate(prompts, 1):
            self.logger.info(f"Processing image {idx}/{len(prompts)}")
            
            filename = f"batch_{idx:03d}"
            result = self.generate_image(
                prompt=prompt,
                steps=steps,
                width=width,
                height=height,
                filename=filename
            )
            
            if result.get("ok"):
                results["generated"].append(result)
            else:
                results["failed"].append({
                    "prompt": prompt,
                    "error": result.get("error")
                })
        
        self.logger.info(
            f"✅ Batch generation complete: "
            f"{len(results['generated'])} successful, "
            f"{len(results['failed'])} failed"
        )
        
        return results

    @ollash_tool(
        name="list_generated_images",
        description="Lists all images that have been generated.",
        parameters={},
        toolset_id="image_generator_tools",
        agent_types=["code"],
    )
    def list_generated_images(self) -> Dict[str, Any]:
        """
        Lists all generated images in the output directory.
        
        Returns:
            Dict with list of generated images and their info
        """
        try:
            images = list(self.output_dir.glob("*.png")) + list(self.output_dir.glob("*.jpg"))
            images.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            image_info = []
            for img_path in images:
                stat = img_path.stat()
                image_info.append({
                    "filename": img_path.name,
                    "path": str(img_path),
                    "size_bytes": stat.st_size,
                    "created": datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
            
            return {
                "ok": True,
                "total": len(image_info),
                "images": image_info,
                "output_dir": str(self.output_dir)
            }
        
        except Exception as e:
            self.logger.error(f"Error listing images: {str(e)}")
            return {
                "ok": False,
                "error": str(e)
            }

    @ollash_tool(
        name="list_available_models",
        description="Lists all available models in InvokeAI with their details.",
        parameters={
            "model_type": {
                "type": "string",
                "description": "Optional: Filter by model type ('main', 'controlnet', 'ip_adapter', etc.)"
            }
        },
        toolset_id="image_generator_tools",
        agent_types=["system"],
    )
    def list_available_models(self, model_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Lists all available models from InvokeAI.
        
        Args:
            model_type: Optional filter by model type
            
        Returns:
            Dict with list of available models
        """
        try:
            response = requests.get(self.models_url, timeout=10)
            
            if response.status_code != 200:
                return {
                    "ok": False,
                    "error": f"Failed to fetch models: {response.status_code}"
                }
            
            data = response.json()
            models = data.get("models", [])
            
            # Filtrar por tipo si se especifica
            if model_type:
                models = [m for m in models if m.get("type") == model_type]
            
            # Organizar por base
            by_base = {}
            for model in models:
                base = model.get("base", "unknown")
                if base not in by_base:
                    by_base[base] = []
                
                by_base[base].append({
                    "name": model.get("name"),
                    "type": model.get("type"),
                    "format": model.get("format"),
                    "key": model.get("key"),
                    "description": model.get("description", "")
                })
            
            return {
                "ok": True,
                "total": len(models),
                "models_by_base": by_base,
                "endpoint": self.models_url
            }
            
        except Exception as e:
            return {
                "ok": False,
                "error": str(e)
            }

    @ollash_tool(
        name="check_invoke_ui_status",
        description="Checks if Invoke UI is running and accessible.",
        parameters={},
        toolset_id="image_generator_tools",
        agent_types=["system"],
    )
    def check_invoke_ui_status(self) -> Dict[str, Any]:
        """
        Checks the status of the Invoke UI API.
        
        Returns:
            Dict with API status information
        """
        self.logger.info(f"🔍 Checking Invoke UI status at {self.api_base_url}...")
        
        try:
            # Try to get API info - check root endpoint
            response = requests.get(f"{self.api_base_url}/api/v1/app/version", timeout=10)
            
            if response.status_code == 200:
                version_info = response.json()
                
                # También obtener lista de modelos principales
                models_info = self.list_available_models(model_type="main")
                
                main_models = []
                if models_info.get("ok"):
                    for base, models in models_info.get("models_by_base", {}).items():
                        for model in models:
                            main_models.append(f"{model['name']} ({base})")
                
                self.logger.info(f"✅ Invoke UI is running and accessible")
                return {
                    "ok": True,
                    "status": "online",
                    "api_url": self.api_base_url,
                    "message": "Invoke UI is ready for image generation",
                    "version": version_info.get("version", "unknown"),
                    "available_main_models": main_models
                }
            else:
                return {
                    "ok": False,
                    "status": "error",
                    "error": f"API returned status {response.status_code}"
                }
        
        except requests.exceptions.ConnectionError:
            self.logger.error(f"❌ Cannot connect to Invoke UI at {self.api_base_url}")
            return {
                "ok": False,
                "status": "offline",
                "error": f"Cannot connect to {self.api_base_url}",
                "suggestion": "Make sure Invoke UI is running on the configured URL (http://192.168.1.217:9090)"
            }
        
        except Exception as e:
            self.logger.error(f"Error checking status: {str(e)}")
            return {
                "ok": False,
                "status": "error",
                "error": str(e)
            }