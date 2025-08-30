# vikare

## mission

The goal is to provide people who are alone with a differential-drive robot equipped with a camera that can detect problems and perform actions such as calling a doctor.

It should also be able to converse with the person it is caring for, detecting signs of depression that could potentially lead to suicide.

## extended blog article

[link](http://elmanytas.es/?q=node/377)

## architecture

We have three main components:
- LLM service
- Event server (collects events sent from the robot and feeds them to the LLM on each iteration)
- Robot:
  - Roomba that executes actions commanded by the robot
  - Camera mounted on the Roomba that sends images to the event server

### Microk8s and LLM service

We will use an LLM with tool capability. It will receive events such as sensor data from the Roomba, as well as from a magnetometer and an accelerometer. It will also receive an image composed of a mosaic of smaller images, along with the transcription of audio captured by the camera in that same image mosaic.

Follow these instructions: http://elmanytas.es/?q=node/373 

Add the local registry for development: `sudo microk8s.enable registry`.

### event service

The event server will receive the information described above (sensors, image, and audio) and store it so the LLM can retrieve it when ready.

The LLM will then call a tool to perform an action and will obtain back the information collected in the previous step, saved in a JSON file with the attached image.

We’re going to have some serious latency. :-D

In practice, this service has two components that communicate with each other through storage. This storage could be Kafka, but it could also be the local file system. This is yet to be defined.

### robot and camera

The Roomba will continuously send sensor data, its internal clock, and its current motion and speed status. Each time it sends data, it will receive a set of instructions on whether to move, depending on what the LLM decides.

As for the camera, we will stream video to the event server, while also allowing independent commands to control its movement.

## camera

https://thingino.com/  
https://github.com/themactep/thingino-firmware/blob/master/docs/cameras/jooan-a2r.md  
https://github.com/themactep/thingino-firmware/wiki/Media-Streaming-Endpoints  

Installation:  
- https://www.youtube.com/watch?v=wfeA8wOEe34  
- https://github.com/wltechblog/thingino-installers/tree/main/jooan-a2r-u  

## links

Possible Enabot like hardware:  
- https://debugmen.dev/hardware-series/2022/02/18/enabot_series_part_1.html  
- https://debugmen.dev/hardware-series/2022/08/01/enabot_series_part_2.html  
- https://debugmen.dev/hardware-series/2023/02/19/enabot_series_part_3.html  
- https://community.home-assistant.io/t/enabot-ebo-integration-camera-with-wheels/328355  
