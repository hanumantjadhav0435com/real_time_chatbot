import logging
import os
from app import app

# Set up logging for debugging
logging.basicConfig(level=logging.DEBUG)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=True)