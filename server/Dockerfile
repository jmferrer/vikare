#FROM python
FROM docker.io/library/python:latest@sha256:50cbf8e58ca53a806b99250b1ba2d16c19433e8c42e7eb4ac4ea924b095e280b

COPY requirements.txt /usr/local/app/src/requirements.txt

RUN pip install -r /usr/local/app/src/requirements.txt

RUN apt update && apt -y install ffmpeg

COPY . /usr/local/src/app


WORKDIR /usr/local/src/app

#CMD ["python", "/usr/local/src/app/image.py"]
#CMD ["python", "/usr/local/src/app/llm.py"]
#CMD ["python", "/usr/local/src/app/sensors.py"]
