from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List
import json
import os
from fireai.core.contracts import get_feature_flags, FeatureFlag, DEFAULT_FEATURE_FLAGS

router = APIRouter(prefix="/settings", tags=["Settings"])

# 1. Runtime Settings (Editable)
@router.get("/runtime", response_model=Dict[str, bool])
async def read_runtime_settings():
    """Get runtime feature flags (editable in UI)."""
    return get_feature_flags()

@router.post("/runtime")
async def update_runtime_settings(flags: Dict[str, bool]):
    """Update runtime feature flags."""
    current_flags = get_feature_flags()
    
    for key in flags.keys():
        if key not in DEFAULT_FEATURE_FLAGS:
            raise HTTPException(status_code=400, detail=f"Invalid feature flag: {key}")
            
    current_flags.update(flags)
    
    os.environ["FIREAI_FEATURE_FLAGS"] = json.dumps(current_flags)
    
    try:
        with open("feature_flags.json", "w") as f:
            json.dump(current_flags, f)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to persist flags: {e}")
        
    return {"status": "success", "flags": current_flags}

# 2. Bootstrap Settings (Read-only)
@router.get("/bootstrap")
async def get_bootstrap_settings():
    """Get bootstrap configuration (read-only in UI, non-sensitive)."""
    return {
        "FIREAI_ENV": os.getenv("FIREAI_ENV", "production"),
        "CORS_ALLOWED_ORIGINS": os.getenv("CORS_ALLOWED_ORIGINS", ""),
        "FIREAI_DWG_MAX_FILE_SIZE_BYTES": os.getenv("FIREAI_DWG_MAX_FILE_SIZE_BYTES", "104857600"),
        "LANGFUSE_ENABLED": os.getenv("LANGFUSE_ENABLED", "true"),
        "SYSTEM_VERSION": "1.55.0",
        "BUILD_HASH": os.getenv("BUILD_HASH", "dev-build")
    }

# 3. Secrets (NEVER EXPOSED TO UI)
# The API keys, database URLs, and Redis passwords are kept strictly
# in memory or secure vaults and are not returned in any endpoint.
