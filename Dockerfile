# syntax=docker/dockerfile:1

FROM public.ecr.aws/docker/library/python:3.11-slim-bullseye

WORKDIR /code

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade -r requirements.txt

COPY . .

EXPOSE 3100

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3000", "--reload"]