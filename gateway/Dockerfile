FROM python:3.12

WORKDIR /app

COPY . .

RUN pip install flask requests pyjwt

EXPOSE 5000

CMD ["python", "app.py"]