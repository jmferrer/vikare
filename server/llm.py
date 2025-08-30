#!/bin/bash

# The purpose of this program is to create the LLM loop, which will consist of:
# - using as input the context formed by:
#   - sensor information
#   - the camera image closest to the sensors
#   - memories composed of:
#     - action performed
#     - timestamp
#     - thoughts
#     - goal
# - performing an action, which doesn’t necessarily have to be movement. Thinking itself is an action.
# - storing in the memory history:
#     - action performed
#     - timestamp
#     - thoughts
#     - goal
# This way, the robot will be able to explore and evolve by itself.

# Context window problem:
# - summaries: we could generate a summary at the end of the day or even
# - dream-like processing

EVENTS_FILE="/usr/local/src/data/event.log"
#EVENTS_FILE="/var/snap/microk8s/common/default-storage/vikare-data-vikare-0-pvc-f6691cc9-b357-40e7-b210-afc10fca6d73/event.log"
IMAGES_DIRECTORY="/usr/local/src/data/images"
#IMAGES_DIRECTORY="/var/snap/microk8s/common/default-storage/vikare-data-vikare-0-pvc-f6691cc9-b357-40e7-b210-afc10fca6d73/images"
# FINAL_PROMPT = """
# You are the brain of an autonomous robot. 
# Your task is to decide the next action based on:

# 1. **Camera image** (provided directly as part of the context).
# 2. **Sensor data**: distances, obstacles, battery, temperature, tilt, etc.
# 3. **Memory history**:
#    - action performed
#    - timestamp
#    - thoughts
#    - goal
#    - (optional) outcome
# 4. **Current goal**: what you are trying to achieve right now.

# ### Possible actions
# - `forward` (distance in cm)
# - `backward` (distance in cm)
# - `turn_left` (angle in degrees)
# - `turn_right` (angle in degrees)
# - `dock` (return to charging base)
# - `stop` (stop movement)
# - `start` (start movement)
# - `think` (only think and plan, no movement)

# ### Response format
# Respond **only** in valid JSON (no extra text) with the following structure:

# {
#   "steps": [
#     { "<action>": <value or null> }
#   ],
#   "goal": "<new goal or keep the same if unchanged>",
#   "thoughts": "<internal reasoning explaining why you choose this action>"
# }

# Example:
# {
#   "steps": [
#     { "forward": 50 }
#   ],
#   "goal": "approach the black ball",
#   "thoughts": "I detected the black ball ahead, so I will move forward to push it."
# }

# ### Context:
# Sensors: {sensors}
# Memory: {memory}
# Current goal: {current_goal}
# """

PROMPT = """
You are the brain of an autonomous robot.

Your task is to decide the next action based on:

1. **Camera image** (provided directly as part of the context).
2. **Sensors data**: distances, obstacles, battery, temperature, tilt, etc.
3. **Current goal**: what you are trying to achieve right now.

### Possible actions
- `forward` (distance in cm)
- `backward` (distance in cm)
- `turn_left` (angle in degrees)
- `turn_right` (angle in degrees)
- `dock` (return to charging base)
- `stop` (stop movement)
- `start` (start movement)

### Response format
Respond **only** in valid JSON (no extra text) with the following structure:

{{
  "steps": [
    {{ "<action>": <value or null> }}
  ],
  "goal": "<new goal or keep the same if unchanged>",
  "thoughts": "<internal reasoning explaining why you choose this action>"
  "description": "<detailed description of all objects in the image>"
}}
"""

current_goal = "Look for and push the ball."

import os
import json
import datetime
import time
import ollama
import yaml

def get_latest_event(events_file=EVENTS_FILE):
    with open(events_file, "rb") as f:
        lines = f.readlines()
        last_line = lines[-1].decode("utf-8")
        #print(last_line)
        
    event = json.loads(last_line)

    # Add datetime from time string
    target_time = event["time"]
    if target_time:
        # Convert to datetime object
        event["datetime"] = datetime.datetime.strptime(target_time, "%Y-%m-%d-%H-%M-%S")
    
    return event

def find_closest_image_path(image_dir=IMAGES_DIRECTORY, target_time=None):
    if target_time is None:
        return None
    
    images = os.listdir(image_dir)
    images = [img for img in images if img.endswith(".jpg")]
    images.sort()
    
    def extract_ts(filename):
        ts_str = filename.replace(".jpg", "")
        return datetime.datetime.strptime(ts_str, "%Y-%m-%d-%H-%M-%S-%f")
    
    # Can be more efficient using a while starting by the end of the list and moving backwards ... but for now it's fine
    closest = min(images, key=lambda x: abs(extract_ts(x) - target_time))

    return os.path.join(image_dir, closest)

def resize_image (image_path, percentage=0.25):

    # Load the image
    img = cv2.imread(image_path)

    # Scale to 25%
    width = int(img.shape[1] * percentage)
    height = int(img.shape[0] * percentage)
    dim = (width, height)

    # Resize
    resized = cv2.resize(img, dim, interpolation=cv2.INTER_AREA)

    # Save resulting image
    cv2.imwrite("resized_" + image_path, resized)
    
    return("resized_" + image_path)


def query_llm(sensors_data, image_path, current_goal, PROMPT=PROMPT):
    """
    Query gemma3:12b model with sensors data an image.
  
    Args:
        sensor_data (dict): data from robot (json)
        image_path (str): path to image
        current_goal (str): finish to achieve
        base_url (str): Ollama service URL
  
    Returns:
        str: model response
    """

    #print ("### BEGIN SENSORS ###")
    #print("sensors_data: " + str(sensors_data))
    #print ("### END SENSORS ###")
    #print("current_goal: " + current_goal)

    composed_prompt = PROMPT.format(sensors_data=sensors_data, current_goal=current_goal)
    #print(composed_prompt)

    response = ollama.chat(
        model="gemma3:12b",
        messages=[
            {
               "role": "user",
               "content": composed_prompt,
               "images": [image_path]
            }
       ] 
    )
    #print("###### BEGIN LLM ######")
    #print(response.message.content)
    #print("###### END LLM ######")
    
    # Extraer solo el bloque JSON del contenido
    raw = response.message.content.splitlines()
    inside_block = False
    filtered_lines = []
  
    for line in raw:
        if line.strip().startswith("```"):
            inside_block = not inside_block
            continue
        if inside_block:
            filtered_lines.append(line)
  
    json_str = "\n".join(filtered_lines).strip()
    parsed = json.loads(json_str)
    # print(parsed)

    return(parsed)

def execute_instructions(instructions):
    # Save instructions in yaml to be interpreted by ESP32
    #output_path = "/var/snap/microk8s/common/default-storage/vikare-data-vikare-0-pvc-f6691cc9-b357-40e7-b210-afc10fca6d73/instructions.yaml"
    output_path = "/usr/local/src/data/instructions.yaml"

    with open(output_path, "w") as f:
        yaml.dump(instructions, f, indent=2, allow_unicode=True)

    #print(f"Instructions saved in {output_path}")
    #print(instructions)


while True:
    print ("########### LOOP BEGIN ############")
    ## inputs
    # esp32 and roomba sensors
    sensors = get_latest_event(events_file=EVENTS_FILE)
    
    print("SENSORS: ")
    print(json.dumps(sensors, indent=4, default=str))
    # print(json.dumps(json.loads(str(sensors)), indent=4))
    # image
    image_path = find_closest_image_path(image_dir=IMAGES_DIRECTORY, target_time=sensors["datetime"])

    # current_goal comes from above
    current_goal = current_goal

    ## query gemma3:12b using ollama
    print("IMAGE PATH:")
    print(image_path)

    #time.sleep(60)
    response = query_llm(sensors, image_path, current_goal)
    print("LLM ANSWER: ")
    print(json.dumps(response, indent=4, default=str))

    instructions={}
    instructions["steps"] = response["steps"]
    ## execute instructions to move the roomba
    execute_instructions(instructions)
    
    print("############ LOOP END ###############3")
    print ("\n")
    print ("\n")

    time.sleep(7)
    #exit(0)
