"""LiteLLM Configuration Importer and Unsupported Features Report Generator."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple
import yaml


class LiteLLMImporter:
    """Parses LiteLLM config.yaml and produces equivalent Cloyst model and routing configs."""

    @staticmethod
    def import_config(config_yaml_content: str) -> Tuple[Dict[str, Any], List[str]]:
        """Parse LiteLLM config and return (cloyst_config, unsupported_features_report)."""
        data = yaml.safe_load(config_yaml_content) or {}
        unsupported: List[str] = []

        model_list = data.get("model_list", [])
        cloyst_models = []

        for item in model_list:
            model_name = item.get("model_name")
            litellm_params = item.get("litellm_params", {})
            api_base = litellm_params.get("api_base", "http://127.0.0.1:8000")
            model_id = litellm_params.get("model", model_name)

            # Check for cloud-only proprietary providers
            if any(cloud_p in str(model_id).lower() for cloud_p in ["azure", "bedrock", "vertex"]):
                unsupported.append(
                    f"Model '{model_name}': Provider '{model_id}' requires outbound cloud authentication, not supported in pure air-gap mode."
                )

            cloyst_models.append({
                "model_id": model_name,
                "engine_type": "vllm" if "vllm" in str(model_id) else "generic",
                "upstream_url": api_base,
            })

        router_settings = data.get("router_settings", {})
        routing_strategy = router_settings.get("routing_strategy", "least-busy")

        cloyst_config = {
            "version": "1.0",
            "routing": {
                "default_strategy": routing_strategy,
            },
            "models": cloyst_models,
        }

        return cloyst_config, unsupported
