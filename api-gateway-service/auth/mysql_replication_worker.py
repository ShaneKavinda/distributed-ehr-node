import os
import time
from typing import Dict, Iterable, List, Tuple

import pymysql
from pymysqlreplication import BinLogStreamReader
from pymysqlreplication.row_event import DeleteRowsEvent, UpdateRowsEvent, WriteRowsEvent

from .mysql_store import CREATE_USERS_TABLE_SQL, initialize_schema


def _db_name() -> str:
    return os.getenv("MYSQL_AUTH_DATABASE", "auth_db")


def _db_port() -> int:
    return int(os.getenv("MYSQL_PRIMARY_PORT", "3306"))


def _replica_hosts() -> List[str]:
    configured = os.getenv("MYSQL_REPLICA_HOSTS", "mysql-replica-1,mysql-replica-2,mysql-replica-3")
    return [entry.strip() for entry in configured.split(",") if entry.strip()]


def _auth_user() -> str:
    return os.getenv("MYSQL_AUTH_USER", "auth_user")


def _auth_password() -> str:
    return os.getenv("MYSQL_AUTH_PASSWORD", "auth_password")


def _connect_replica(host: str) -> pymysql.connections.Connection:
    return pymysql.connect(
        host=host,
        port=_db_port(),
        user=_auth_user(),
        password=_auth_password(),
        database=_db_name(),
        autocommit=True,
        connect_timeout=5,
        read_timeout=5,
        write_timeout=5,
    )


def _ensure_replica_schema(hosts: Iterable[str]) -> None:
    for host in hosts:
        conn = _connect_replica(host)
        try:
            with conn.cursor() as cursor:
                cursor.execute(CREATE_USERS_TABLE_SQL)
        finally:
            conn.close()


def _open_replica_connections(hosts: Iterable[str]) -> Dict[str, pymysql.connections.Connection]:
    connections: Dict[str, pymysql.connections.Connection] = {}
    for host in hosts:
        try:
            connections[host] = _connect_replica(host)
            print(f"Replica connected: {host}")
        except pymysql.MySQLError as exc:
            print(f"Replica connection failed ({host}): {exc}")
    return connections


def _build_upsert(table: str, values: Dict[str, object]):
    columns = list(values.keys())
    quoted_columns = ", ".join(f"`{column}`" for column in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    updates = ", ".join(
        f"`{column}` = VALUES(`{column}`)"
        for column in columns
        if column != "id"
    )
    query = f"INSERT INTO `{table}` ({quoted_columns}) VALUES ({placeholders})"
    if updates:
        query = f"{query} ON DUPLICATE KEY UPDATE {updates}"
    params = tuple(values[column] for column in columns)
    return query, params


def _apply_delete(cursor, table: str, values: Dict[str, object]) -> None:
    key_column = "id" if "id" in values else "user_name"
    cursor.execute(
        f"DELETE FROM `{table}` WHERE `{key_column}` = %s",
        (values[key_column],),
    )


def _apply_event_to_connection(connection, event) -> None:
    table = event.table
    with connection.cursor() as cursor:
        for row in event.rows:
            if isinstance(event, WriteRowsEvent):
                query, params = _build_upsert(table, row["values"])
                cursor.execute(query, params)
            elif isinstance(event, UpdateRowsEvent):
                query, params = _build_upsert(table, row["after_values"])
                cursor.execute(query, params)
            elif isinstance(event, DeleteRowsEvent):
                _apply_delete(cursor, table, row["values"])


def _primary_binlog_settings() -> Dict[str, object]:
    return {
        "host": os.getenv("MYSQL_PRIMARY_HOST", "mysql-primary"),
        "port": _db_port(),
        "user": os.getenv("MYSQL_REPL_USER", "repl_user"),
        "passwd": os.getenv("MYSQL_REPL_PASSWORD", "repl_password"),
    }


def _fetch_primary_binlog_position() -> Tuple[str, int]:
    connection = pymysql.connect(
        host=os.getenv("MYSQL_PRIMARY_HOST", "mysql-primary"),
        port=_db_port(),
        user=os.getenv("MYSQL_REPL_USER", "repl_user"),
        password=os.getenv("MYSQL_REPL_PASSWORD", "repl_password"),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
        connect_timeout=5,
        read_timeout=5,
        write_timeout=5,
    )
    try:
        with connection.cursor() as cursor:
            # MySQL 8.4 replaced SHOW MASTER STATUS with SHOW BINARY LOG STATUS.
            try:
                cursor.execute("SHOW BINARY LOG STATUS")
            except pymysql.MySQLError:
                cursor.execute("SHOW MASTER STATUS")
            row = cursor.fetchone()
            if not row or "File" not in row or "Position" not in row:
                raise RuntimeError(f"Unexpected binlog status response: {row}")
            return str(row["File"]), int(row["Position"])
    finally:
        connection.close()


def run_replication_worker() -> None:
    reconnect_delay = float(os.getenv("MYSQL_REPL_RECONNECT_DELAY_SECONDS", "3"))
    replica_hosts = _replica_hosts()
    stream_server_id = int(os.getenv("MYSQL_REPL_STREAM_SERVER_ID", "101"))

    while True:
        stream = None
        replica_connections: Dict[str, pymysql.connections.Connection] = {}
        try:
            initialize_schema()
            _ensure_replica_schema(replica_hosts)
            replica_connections = _open_replica_connections(replica_hosts)
            if not replica_connections:
                raise RuntimeError("No MySQL replicas are currently reachable")
            log_file, log_pos = _fetch_primary_binlog_position()

            stream = BinLogStreamReader(
                connection_settings=_primary_binlog_settings(),
                server_id=stream_server_id,
                blocking=True,
                resume_stream=True,
                log_file=log_file,
                log_pos=log_pos,
                only_events=[WriteRowsEvent, UpdateRowsEvent, DeleteRowsEvent],
                only_schemas=[_db_name()],
                only_tables=["users"],
            )

            print("MySQL replication worker connected to primary binlog stream")
            for event in stream:
                for host in replica_hosts:
                    if host not in replica_connections:
                        try:
                            replica_connections[host] = _connect_replica(host)
                            print(f"Replica reconnected: {host}")
                        except pymysql.MySQLError:
                            continue

                stale_hosts: List[str] = []
                for host, connection in replica_connections.items():
                    try:
                        _apply_event_to_connection(connection, event)
                    except pymysql.MySQLError as exc:
                        print(f"Replica apply failed ({host}): {exc}")
                        stale_hosts.append(host)

                for host in stale_hosts:
                    try:
                        replica_connections[host].close()
                    except Exception:
                        pass
                    del replica_connections[host]

        except Exception as exc:
            print(f"MySQL replication worker error: {exc}")
            time.sleep(reconnect_delay)
        finally:
            if stream is not None:
                stream.close()
            for connection in replica_connections.values():
                try:
                    connection.close()
                except Exception:
                    pass


if __name__ == "__main__":
    run_replication_worker()
