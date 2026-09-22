FROM python:3.11-slim
WORKDIR /publisher
COPY server.py index.html app.js style.css ./
USER nobody
EXPOSE 8787
CMD ["python", "server.py", "--container"]
