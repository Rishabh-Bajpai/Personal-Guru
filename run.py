from dotenv import load_dotenv
load_dotenv()
from app import create_app  # noqa: E402

app = create_app()

import os  # noqa: E402
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5011))
    app.run(debug=True, host='0.0.0.0', port=port)
