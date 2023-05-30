# pull official base image
FROM python:3.9.5-slim-buster

# set work directory
WORKDIR /code

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# install dependencies
RUN pip install --upgrade pip
RUN apt-get update && \
    apt-get upgrade -y && \
    rm -rf /var/lib/apt/lists/*
COPY ./requirements.txt .
RUN pip install -r requirements.txt

# copy project
COPY . .