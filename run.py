from dotenv import load_dotenv
from app.common.config_validator import validate_config

load_dotenv()

# Check configuration
missing_vars = validate_config()

if missing_vars:
    print(f"Missing configuration variables: {missing_vars}. Starting Setup Wizard...")
    from app.setup_app import create_setup_app
    app = create_setup_app()
else:
    from app import create_app  # noqa: E402
    app = create_app()

import os  # noqa: E402
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5011))
    app.run(debug=True, host='0.0.0.0', port=port)
