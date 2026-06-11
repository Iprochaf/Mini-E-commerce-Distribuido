FROM python:3.12

WORKDIR /app

COPY . .

RUN pip install flask pyjwt requests

EXPOSE 5003

CMD ["python", "app.py"]