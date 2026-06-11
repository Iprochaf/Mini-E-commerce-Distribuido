FROM python:3.12

WORKDIR /app

COPY . .

RUN pip install flask pyjwt bcrypt

EXPOSE 5001

CMD ["python", "app.py"]