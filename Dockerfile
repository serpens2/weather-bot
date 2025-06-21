FROM python:3.11-slim

COPY requirements.txt requirements.txt
RUN  pip install -r requirements.txt

COPY main.py init_db.py utils.py .env ./
EXPOSE 8000
CMD ["python", "main.py"]