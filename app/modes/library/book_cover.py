"""
Book Cover Generation Service using ComfyUI.

Connects to a ComfyUI server via websockets to generate
AI book cover images from a workflow JSON template.
"""

import json
import logging
import os
import random
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

logger = logging.getLogger(__name__)
POSITIVE_PROMPT_NODE_ID = 45


def _normalize_server_address(server_address):
    """Normalize ComfyUI address to ``(http_scheme, host[:port])``."""
    normalized = (server_address or "").strip()
    if not normalized:
        return "http", "localhost:8188"

    has_scheme = "://" in normalized
    parsed = (
        urllib.parse.urlparse(normalized)
        if has_scheme
        else urllib.parse.urlparse(f"//{normalized}")
    )

    http_scheme = (parsed.scheme or "http").lower()
    if has_scheme and http_scheme not in {"http", "https"}:
        raise ValueError(
            f"Unsupported ComfyUI URL scheme: {http_scheme}. Use http or https."
        )

    host = (parsed.netloc or parsed.path or "").rstrip("/")
    if not host:
        raise ValueError("ComfyUI server address must include a host")

    if parsed.params or parsed.query or parsed.fragment:
        raise ValueError(
            "ComfyUI server address cannot include params, query, or fragment"
        )

    if has_scheme and parsed.path not in {"", "/"}:
        raise ValueError("ComfyUI server address cannot include a path")

    return http_scheme, host


def _widget_value(node, index, default=None, required=False, field_name=None):
    values = node.get("widgets_values", [])
    if len(values) > index:
        return values[index]
    if required:
        label = field_name or f"widgets_values[{index}]"
        raise ValueError(
            f"Workflow node {node.get('id')} ({node.get('type')}) is missing required {label}"
        )
    return default


class BookCoverService:
    """Generates book cover images via ComfyUI API."""

    def __init__(self, server_address, workflow_path):
        self.http_scheme, self.server_address = _normalize_server_address(
            server_address
        )
        self.ws_scheme = "wss" if self.http_scheme == "https" else "ws"
        self.http_base_url = f"{self.http_scheme}://{self.server_address}"
        self.ws_base_url = f"{self.ws_scheme}://{self.server_address}"
        self.workflow_path = workflow_path
        self.client_id = str(uuid.uuid4())

    def _queue_prompt(self, prompt):
        """Submit a prompt to the ComfyUI queue."""
        p = {"prompt": prompt, "client_id": self.client_id}
        data = json.dumps(p).encode("utf-8")
        req = urllib.request.Request(
            f"{self.http_base_url}/prompt",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        return json.loads(urllib.request.urlopen(req, timeout=30).read())

    def _get_image(self, filename, subfolder, folder_type):
        """Download a generated image from ComfyUI."""
        params = {"filename": filename, "subfolder": subfolder, "type": folder_type}
        url_values = urllib.parse.urlencode(params)
        with urllib.request.urlopen(
            f"{self.http_base_url}/view?{url_values}", timeout=60
        ) as response:
            return response.read()

    def _load_workflow(self):
        """Load the ComfyUI workflow JSON from file."""
        with open(self.workflow_path, mode="r", encoding="utf-8") as f:
            return json.load(f)

    def _build_prompt_api(self, workflow_json, refined_prompt):
        """
        Transform the workspace JSON to ComfyUI API Prompt format.
        ComfyUI API expects a map of node_id -> {inputs, class_type}.
        """
        prompt_api = {}

        for node in workflow_json.get("nodes", []):
            node_id = str(node["id"])
            class_type = node["type"]
            inputs = {}

            # Add links from 'inputs' list in workspace JSON
            if "inputs" in node:
                for input_item in node["inputs"]:
                    if "link" in input_item and input_item["link"] is not None:
                        link_id = input_item["link"]
                        for link in workflow_json.get("links", []):
                            if link[0] == link_id:
                                origin_node_id = str(link[1])
                                origin_slot = link[2]
                                inputs[input_item["name"]] = [
                                    origin_node_id,
                                    origin_slot,
                                ]
                                break

            # Skip non-functional nodes
            if class_type == "MarkdownNote":
                continue
            # Map widgets_values to inputs based on node type
            if class_type == "CLIPTextEncode":
                inputs["text"] = (
                    refined_prompt
                    if node["id"] == POSITIVE_PROMPT_NODE_ID
                    else _widget_value(node, 0, default="")
                )
            elif class_type == "CLIPLoader":
                clip_name = _widget_value(
                    node, 0, required=True, field_name="clip_name"
                )
                clip_type = _widget_value(node, 1, field_name="type")
                clip_device = _widget_value(node, 2, field_name="device")
                inputs["clip_name"] = clip_name
                if clip_type is not None:
                    inputs["type"] = clip_type
                if clip_device is not None:
                    inputs["device"] = clip_device
            elif class_type == "VAELoader":
                inputs["vae_name"] = _widget_value(
                    node, 0, required=True, field_name="vae_name"
                )
            elif class_type == "UNETLoader":
                inputs["unet_name"] = _widget_value(
                    node, 0, required=True, field_name="unet_name"
                )
                weight_dtype = _widget_value(node, 1, field_name="weight_dtype")
                if weight_dtype is not None:
                    inputs["weight_dtype"] = weight_dtype
            elif class_type == "ModelSamplingAuraFlow":
                shift = _widget_value(node, 0, field_name="shift")
                if shift is not None:
                    inputs["shift"] = shift
            elif class_type == "EmptySD3LatentImage":
                # User requested 278:398 aspect ratio.
                # Scaling up to 834x1194 for quality.
                inputs["width"] = 834
                inputs["height"] = 1194
                inputs["batch_size"] = _widget_value(
                    node, 2, default=1, field_name="batch_size"
                )
            elif class_type == "KSampler":
                inputs["seed"] = random.randint(1, 2**53)
                control_after_generate = _widget_value(
                    node, 1, field_name="control_after_generate"
                )
                steps = _widget_value(node, 2, field_name="steps")
                cfg = _widget_value(node, 3, field_name="cfg")
                sampler_name = _widget_value(node, 4, field_name="sampler_name")
                scheduler = _widget_value(node, 5, field_name="scheduler")
                denoise = _widget_value(node, 6, field_name="denoise")
                if control_after_generate is not None:
                    inputs["control_after_generate"] = control_after_generate
                if steps is not None:
                    inputs["steps"] = steps
                if cfg is not None:
                    inputs["cfg"] = cfg
                if sampler_name is not None:
                    inputs["sampler_name"] = sampler_name
                if scheduler is not None:
                    inputs["scheduler"] = scheduler
                if denoise is not None:
                    inputs["denoise"] = denoise
            elif class_type == "SaveImage":
                inputs["filename_prefix"] = _widget_value(
                    node, 0, default="book_cover", field_name="filename_prefix"
                )

            prompt_api[node_id] = {
                "inputs": inputs,
                "class_type": class_type,
            }

        return prompt_api

    def generate_cover(
        self, book_title, book_description, output_path, refined_prompt=None
    ):
        """
        Generate a book cover image and save it to output_path.

        Args:
            book_title: Title of the book.
            book_description: Short description for the image prompt.
            output_path: Absolute path to save the generated PNG.
            refined_prompt: Optional pre-refined LLM prompt. If None, it builds one.

        Returns:
            tuple: (success: bool, error_message: str or None)
        """
        try:
            # Check if ComfyUI is reachable
            try:
                urllib.request.urlopen(f"{self.http_base_url}/system_stats", timeout=5)
            except Exception:
                return False, f"ComfyUI server not reachable at {self.http_base_url}"

            # Load workflow
            if not os.path.exists(self.workflow_path):
                return False, f"Workflow file not found: {self.workflow_path}"

            workflow_json = self._load_workflow()

            # Build or use prompt
            if not refined_prompt:
                refined_prompt = (
                    f"Professional book cover art for '{book_title}'. "
                    f"{book_description}. "
                    "High quality, cinematic, dramatic lighting, artistic style."
                )

            logger.info(f"Using refined prompt for {book_title}: {refined_prompt}")
            prompt_api = self._build_prompt_api(workflow_json, refined_prompt)

            # Connect via websocket and submit
            import websocket

            ws = websocket.WebSocket()
            ws.settimeout(120)  # 2 min timeout for generation
            ws.connect(f"{self.ws_base_url}/ws?clientId={self.client_id}")

            logger.info(f"Queueing book cover generation for: {book_title}")
            prompt_response = self._queue_prompt(prompt_api)
            prompt_id = prompt_response["prompt_id"]

            # Wait for completion
            output_images = {}
            deadline = time.time() + 180
            iteration_count = 0
            max_iterations = 1000
            while True:
                if time.time() > deadline or iteration_count >= max_iterations:
                    ws.close()
                    logger.error(
                        "Timed out waiting for ComfyUI book cover generation for prompt %s. Partial images: %s",
                        prompt_id,
                        bool(output_images),
                    )
                    return False, "Timed out waiting for book cover generation"
                iteration_count += 1
                out = ws.recv()
                if isinstance(out, str):
                    message = json.loads(out)
                    if message["type"] == "executing":
                        data = message["data"]
                        if data["node"] is None and data["prompt_id"] == prompt_id:
                            break  # Execution is done
                    elif message["type"] == "executed":
                        if message["data"]["prompt_id"] == prompt_id:
                            node_output = message["data"]["output"]
                            if "images" in node_output:
                                node_id = message["data"]["node"]
                                output_images[node_id] = node_output["images"]

            ws.close()
            logger.info(f"Book cover generation complete for: {book_title}")

            # Download and save the first image
            if not output_images:
                return False, "No images were generated"

            # Ensure output directory exists
            dirpath = os.path.dirname(output_path)
            if dirpath:
                os.makedirs(dirpath, exist_ok=True)

            for _node_id, images in output_images.items():
                for image_info in images:
                    image_data = self._get_image(
                        image_info["filename"],
                        image_info["subfolder"],
                        image_info["type"],
                    )
                    with open(output_path, "wb") as f:
                        f.write(image_data)
                    logger.info(f"Book cover saved: {output_path}")
                    return True, None  # Success on first image

            return False, "Failed to download generated image"

        except ImportError:
            return (
                False,
                "websocket-client package not installed. Install with: pip install websocket-client",
            )
        except Exception as e:
            logger.error(
                f"Book cover generation failed for '{book_title}': {e}", exc_info=True
            )
            return False, str(e)
