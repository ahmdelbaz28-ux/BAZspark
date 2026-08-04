from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
import json
import os
from fireai.core.contracts import get_feature_flags, FeatureFlag, DEFAULT_FEATURE_FLAGS

router = APIRouter(prefix="/settings", tags=["Settings"])

@router.get("/feature-flags", response_model=Dict[str, bool])
async def read_feature_flags():
    """Get all current feature flags."""
    return get_feature_flags()

@router.post("/feature-flags")
async def update_feature_flags(flags: Dict[str, bool]):
    """
    Update feature flags.
    Saves to FIREAI_FEATURE_FLAGS environment variable.
    In a real deployment, this should persist to the SQLite DB or write to .env.
    """
    current_flags = get_feature_flags()
    
    # Validate the keys
    for key in flags.keys():
        if key not in DEFAULT_FEATURE_FLAGS:
            raise HTTPException(status_code=400, detail=f"Invalid feature flag: {key}")
            
    current_flags.update(flags)
    
    # For now, we update the process environment so get_feature_flags picks it up immediately.
    os.environ["FIREAI_FEATURE_FLAGS"] = json.dumps(current_flags)
    
    # Also write to a local .env override file for persistence across reboots.
    try:
        with open("feature_flags.json", "w") as f:
            json.dump(current_flags, f)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to persist flags: {e}")
        
    return {"status": "success", "flags": current_flags}

@router.get("/config")
async def get_system_config():
    """Get general system configuration."""
    return {
        "FIREAI_ENV": os.getenv("FIREAI_ENV", "production"),
        "CORS_ALLOWED_ORIGINS": os.getenv("CORS_ALLOWED_ORIGINS", ""),
        "FIREAI_DWG_MAX_FILE_SIZE_BYTES": os.getenv("FIREAI_DWG_MAX_FILE_SIZE_BYTES", "104857600"),
        "LANGFUSE_ENABLED": os.getenv("LANGFUSE_ENABLED", "true"),
    }
