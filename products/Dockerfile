FROM python:3.12

WORKDIR /app

COPY . .

RUN pip install flask pyjwt requests

EXPOSE 5002

CMD ["python", "app.py"]