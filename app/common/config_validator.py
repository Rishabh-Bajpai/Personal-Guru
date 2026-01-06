import os

REQUIRED_VARS = [
    "DATABASE_URL",
    "LLM_BASE_URL",
    "LLM_MODEL_NAME",
]

def validate_config(env_path=None):
    """
    Validates that all required environment variables are set.
    Returns a list of missing or invalid variable names.
    """
    missing_vars = []
    
    # If env_path is provided, we assume load_dotenv has already been called
    # or will be called by the caller. This function checks os.environ.

    for var in REQUIRED_VARS:
        value = os.environ.get(var)
        if not value:
            missing_vars.append(var)
            continue
        
        # specific validation logic could go here
        # e.g. URL validation for endpoints
        
    return missing_vars
