from flask import Flask, jsonify
import os
import subprocess
import logging
import discourse
import ccn

app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.route('/')
def health_check():
    return jsonify({"status": "healthy", "message": "Service is running"})

    try:
        logger.info("Starting script2 execution")
        
        # Run your second Python script
        result = subprocess.run(
            ['python', 'script2.py'], 
            capture_output=True, 
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode == 0:
            logger.info("Script2 completed successfully")
            return jsonify({
                "status": "success", 
                "message": "Script2 executed successfully",
                "stdout": result.stdout[:500]
            })
        else:
            logger.error(f"Script2 failed: {result.stderr}")
            return jsonify({
                "status": "error", 
                "message": "Script2 failed",
                "error": result.stderr[:500]
            }), 500
            
    except subprocess.TimeoutExpired:
        logger.error("Script2 timed out")
        return jsonify({"status": "error", "message": "Script2 timed out"}), 500
    except Exception as e:
        logger.error(f"Unexpected error in script2: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500
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