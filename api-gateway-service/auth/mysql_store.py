import os
from contextlib import contextmanager
from typing import Dict, Iterator, Optional

import pymysql
from pymysql.cursors import DictCursor

CREATE_USERS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_name VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    doctor_id VARCHAR(128) NULL,
    patient_id VARCHAR(128) NULL,
    role ENUM('patient', 'doctor') NOT NULL,
    user_status ENUM('pending', 'registered', 'inactive') NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
)
"""


def _primary_connection_params() -> Dict[str, object]:
    return {
        "host": os.getenv("MYSQL_PRIMARY_HOST", "localhost"),
        "port": int(os.getenv("MYSQL_PRIMARY_PORT", "3306")),
        "user": os.getenv("MYSQL_AUTH_USER", "auth_user"),
        "password": os.getenv("MYSQL_AUTH_PASSWORD", "auth_password"),
        "database": os.getenv("MYSQL_AUTH_DATABASE", "auth_db"),
        "cursorclass": DictCursor,
        "autocommit": True,
        "connect_timeout": 5,
        "read_timeout": 5,
        "write_timeout": 5,
    }


@contextmanager
def primary_connection() -> Iterator[pymysql.connections.Connection]:
    conn = pymysql.connect(**_primary_connection_params())
    try:
        yield conn
    finally:
        conn.close()


def initialize_schema() -> None:
    root_conn = pymysql.connect(
        host=os.getenv("MYSQL_PRIMARY_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PRIMARY_PORT", "3306")),
        user=os.getenv("MYSQL_AUTH_USER", "auth_user"),
        password=os.getenv("MYSQL_AUTH_PASSWORD", "auth_password"),
        cursorclass=DictCursor,
        autocommit=True,
        connect_timeout=5,
    )
    try:
        database_name = os.getenv("MYSQL_AUTH_DATABASE", "auth_db")
        with root_conn.cursor() as cursor:
            try:
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{database_name}`")
            except pymysql.MySQLError:
                # In managed setups the auth user may not have CREATE DATABASE privilege.
                pass
    finally:
        root_conn.close()

    with primary_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(CREATE_USERS_TABLE_SQL)


def get_user_by_username(username: str) -> Optional[Dict[str, object]]:
    query = """
    SELECT id, user_name, password_hash, doctor_id, patient_id, role, user_status
    FROM users
    WHERE user_name = %s
    """
    with primary_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, (username,))
            return cursor.fetchone()


def create_user(
    username: str,
    password_hash: str,
    role: str,
    user_status: str,
    doctor_id: Optional[str] = None,
    patient_id: Optional[str] = None,
) -> None:
    query = """
    INSERT INTO users (user_name, password_hash, doctor_id, patient_id, role, user_status)
    VALUES (%s, %s, %s, %s, %s, %s)
    """
    with primary_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                query,
                (username, password_hash, doctor_id, patient_id, role, user_status),
            )
