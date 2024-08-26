FROM python:3.10.11
WORKDIR /app
COPY ./requirements.txt /app
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=UTF-8


ENV MONGO_HOST=localhost
ENV MONGO_PORT=27017
ENV MONGO_USER=EdCoachAI
ENV MONGO_PASSWORD=edcoach#2023@july

# Run main.py when the container launches
CMD ["python", "main.py"]