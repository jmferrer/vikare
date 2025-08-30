#!/usr/bin/python
from flask import Flask, request, jsonify
import os
import yaml
import json

app = Flask(__name__)

EVENTS_FILE="/usr/local/src/data/event.log"
@app.route('/sensors', methods=['POST'])
def sensors():
    # Get sensors data from the POST request
    # List:
    # - orientation from magnetometer: 0 - 360 degrees where 0 is the north
    # - acceleration in x, y and z axis (m/s^2)
    # - battery level
    # - distance in centimeters
    # - collision bumpers state (left, front o right)
    with open(EVENTS_FILE, 'a') as file:
        data = request.get_json()
        print(data, flush=True)
        json_line = json.dumps(data) + "\n"
        file.write(json_line)
        return'{"ok"}', 200

# Path of file instructions.yaml
file_path = "/usr/local/src/data/instructions.yaml"

@app.route('/instructions', methods=['GET'])
def return_instructions():
    if os.path.exists(file_path):
        # Convert to json and send
        with open(file_path, 'r') as file:
            yaml_content = yaml.safe_load(file)

        os.remove(file_path)
        return yaml_content
    else:
        return jsonify(error="File instructions.yaml does not exist"), 404

if __name__ == '__main__':
    # Create directory if not exists
    os.makedirs(os.path.dirname(EVENTS_FILE), exist_ok=True)

    app.run(host='0.0.0.0', port=5000, debug=True)
