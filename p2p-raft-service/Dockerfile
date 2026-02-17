FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY proto /app/proto
COPY p2p_pb2 /app/p2p_pb2
COPY ehr_pb2 /app/ehr_pb2
COPY api /app/api
COPY models /app/models
COPY raft /app/raft
COPY replication /app/replication
COPY config.py /app/config.py
COPY grpc_server.py /app/grpc_server.py
COPY main.py /app/main.py

RUN python -m grpc_tools.protoc -I proto --python_out p2p_pb2 --grpc_python_out p2p_pb2 proto/p2p.proto \
    && python -m grpc_tools.protoc -I proto --python_out ehr_pb2 --grpc_python_out ehr_pb2 proto/ehr_service.proto

ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
