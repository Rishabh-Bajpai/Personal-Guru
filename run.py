from dotenv import load_dotenv
from app.common.config_validator import validate_config

load_dotenv(override=True)

# Check configuration
missing_vars = validate_config()

if missing_vars:
    print(f"Missing configuration variables: {missing_vars}. Starting Setup Wizard...")
    from app.setup_app import create_setup_app
    app = create_setup_app()
else:
    from app import create_app  # noqa: E402
    from app.common.sandbox import cleanup_old_sandboxes
    # Cleanup old sandboxes on startup
    cleanup_old_sandboxes()
    app = create_app()

import os  # noqa: E402
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5011))
    # Exclude sandbox directory from reloader monitoring to prevent restart loops
    # when creating temporary environments
    sandbox_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data', 'sandbox')
    cert_path = os.path.join('certs', 'cert.pem')
    key_path = os.path.join('certs', 'key.pem')
    
    ssl_context = None
    if os.path.exists(cert_path) and os.path.exists(key_path):
        print(f"SSL Certificates found. Enabling HTTPS on port {port}.")
        ssl_context = (cert_path, key_path)
    else:
        print(f"No SSL Certificates found. Running on HTTP port {port}.")

    # Exclude sandbox directory from reloader monitoring
    # We use multiple patterns to catch various path representations on Windows
    sandbox_patterns = [
        f'{sandbox_path}/*',
        f'{sandbox_path}\\*', 
        '*/data/sandbox/*',
        '*/venv/*'
    ]

    app.run(
        debug=True,
        host='0.0.0.0',
        port=port,
        use_reloader=True,
        reloader_type='stat',
        exclude_patterns=sandbox_patterns,
        ssl_context=ssl_context
    )
