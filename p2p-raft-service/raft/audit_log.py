"""
Persistent audit log for Raft using MongoDB.
Stores all Raft log entries for durability and audit trail.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Any
from pymongo import MongoClient, ASCENDING
from pymongo.collection import Collection
from pymongo.database import Database

from raft.log_entry import RaftLogEntry
from models.event import Event


class RaftAuditLog:
    """
    MongoDB-backed persistent storage for Raft log entries.
    Provides audit trail and crash recovery capabilities.
    """

    def __init__(self, mongo_url: str, database_name: str, node_id: str):
        """
        Initialize the audit log connection.

        Args:
            mongo_url: MongoDB connection URL
            database_name: Name of the database
            node_id: ID of this Raft node (for namespacing)
        """
        self.client: MongoClient = MongoClient(mongo_url)
        self.db: Database = self.client[database_name]
        self.collection: Collection = self.db[f"raft_log_{node_id}"]
        self.node_id = node_id

        # Create indexes for efficient queries
        self._create_indexes()

        print(f"📚 RaftAuditLog initialized | Node: {node_id} | Collection: raft_log_{node_id}")

    def _create_indexes(self) -> None:
        """Create indexes for efficient log queries"""
        # Unique index on log index (our primary key)
        self.collection.create_index([("index", ASCENDING)], unique=True)
        # Index on term for queries
        self.collection.create_index([("term", ASCENDING)])
        # Compound index for range queries
        self.collection.create_index([("index", ASCENDING), ("term", ASCENDING)])

    def append(self, entry: RaftLogEntry) -> None:
        """
        Append a new log entry to the persistent store.

        Args:
            entry: The Raft log entry to store
        """
        doc = {
            "index": entry.index,
            "term": entry.term,
            "command_id": entry.event.command_id,
            "command_type": entry.event.command_type,
            "payload": entry.event.payload,
            "timestamp": entry.event.timestamp,
            "cluster_id": entry.event.cluster_id,
            "raft_index": entry.event.raft_index,
        }

        # Upsert to handle potential duplicates (idempotent)
        self.collection.update_one(
            {"index": entry.index},
            {"$set": doc},
            upsert=True
        )

        print(f"💾 Persisted log entry | Index: {entry.index} | Term: {entry.term} | Type: {entry.event.command_type}")

    def get(self, index: int) -> Optional[RaftLogEntry]:
        """
        Retrieve a log entry by index.

        Args:
            index: The log index to retrieve

        Returns:
            The log entry if found, None otherwise
        """
        doc = self.collection.find_one({"index": index})
        if doc is None:
            return None
        return self._doc_to_entry(doc)

    def get_range(self, start_index: int, end_index: Optional[int] = None) -> List[RaftLogEntry]:
        """
        Retrieve a range of log entries.

        Args:
            start_index: Starting index (inclusive)
            end_index: Ending index (inclusive), None for all remaining entries

        Returns:
            List of log entries in the range
        """
        query: Dict[str, Any] = {"index": {"$gte": start_index}}
        if end_index is not None:
            query["index"]["$lte"] = end_index

        cursor = self.collection.find(query).sort("index", ASCENDING)
        return [self._doc_to_entry(doc) for doc in cursor]

    def get_all(self) -> List[RaftLogEntry]:
        """
        Retrieve all log entries.

        Returns:
            List of all log entries sorted by index
        """
        cursor = self.collection.find().sort("index", ASCENDING)
        return [self._doc_to_entry(doc) for doc in cursor]

    def get_last(self) -> Optional[RaftLogEntry]:
        """
        Get the last (highest index) log entry.

        Returns:
            The last log entry if any exist, None otherwise
        """
        doc = self.collection.find_one(sort=[("index", -1)])
        if doc is None:
            return None
        return self._doc_to_entry(doc)

    def get_count(self) -> int:
        """
        Get the total number of log entries.

        Returns:
            Count of log entries
        """
        return self.collection.count_documents({})

    def delete_from(self, index: int) -> int:
        """
        Delete all log entries from the given index onwards.
        Used when handling conflicting entries in Raft.

        Args:
            index: Starting index to delete from (inclusive)

        Returns:
            Number of entries deleted
        """
        result = self.collection.delete_many({"index": {"$gte": index}})
        deleted_count = result.deleted_count

        if deleted_count > 0:
            print(f"🗑️  Deleted {deleted_count} conflicting log entries from index {index}")

        return deleted_count

    def clear_all(self) -> int:
        """
        Delete all log entries. Use with caution!

        Returns:
            Number of entries deleted
        """
        result = self.collection.delete_many({})
        deleted_count = result.deleted_count

        if deleted_count > 0:
            print(f"⚠️  Cleared all {deleted_count} log entries from audit log")

        return deleted_count

    def _doc_to_entry(self, doc: Dict[str, Any]) -> RaftLogEntry:
        """
        Convert a MongoDB document to a RaftLogEntry.

        Args:
            doc: MongoDB document

        Returns:
            RaftLogEntry instance
        """
        event = Event(
            command_id=doc["command_id"],
            command_type=doc["command_type"],
            payload=doc["payload"],
            timestamp=doc["timestamp"],
            cluster_id=doc["cluster_id"],
            raft_index=doc.get("raft_index", doc["index"]),
        )

        return RaftLogEntry(
            index=doc["index"],
            term=doc["term"],
            event=event,
        )

    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the audit log.

        Returns:
            Dictionary with log statistics
        """
        count = self.get_count()
        last_entry = self.get_last()

        stats: Dict[str, Any] = {
            "total_entries": count,
            "node_id": self.node_id,
        }

        if last_entry:
            stats["last_index"] = last_entry.index
            stats["last_term"] = last_entry.term
            stats["last_command_type"] = last_entry.event.command_type
        else:
            stats["last_index"] = 0
            stats["last_term"] = 0
            stats["last_command_type"] = None

        return stats

    def close(self) -> None:
        """Close the MongoDB connection"""
        if self.client:
            self.client.close()
            print(f"🔌 RaftAuditLog connection closed | Node: {self.node_id}")
