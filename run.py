from flask import Flask, jsonify
import os
import subprocess
import logging
import discourse
import ccn

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.route('/')
def health_check():
    return jsonify({"status": "healthy", "message": "Service is running"})

@app.route('/syncmembers', methods=['GET'])
def syncmembers():
    # Download members and dump as CSV
    try:
        ccn.main()
        # Sync Discourse with members CSV
        discourse.main()
        return {"status": "ok"}, 200
    except Exception as e:
        logger.error(f"sync failed: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)