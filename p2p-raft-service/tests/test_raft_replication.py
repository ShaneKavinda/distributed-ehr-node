import time
import unittest
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import p2p_pb2.p2p_pb2 as p2p_pb2

from models.event import Event
from raft.node import RaftNode


class InMemoryTransport:
    def __init__(self, registry):
        self._registry = registry

    def append_entries(self, peer_id, request):
        node = self._registry[peer_id]
        success = node.handle_append_entries(request)
        return p2p_pb2.AppendEntriesResponse(term=node.current_term, success=success)

    def request_vote(self, peer_id, request):
        node = self._registry[peer_id]
        granted = node.handle_request_vote(request)
        return p2p_pb2.RequestVoteResponse(term=node.current_term, vote_granted=granted)

    def install_snapshot(self, peer_id, request):
        node = self._registry[peer_id]
        node.handle_install_snapshot(request)
        return p2p_pb2.InstallSnapshotResponse(term=node.current_term)


class RaftReplicationTests(unittest.TestCase):
    def test_replicates_and_applies(self):
        registry = {}
        transport = InMemoryTransport(registry)
        node_ids = ["node1", "node2", "node3"]

        nodes = {}
        for node_id in node_ids:
            peers = [peer for peer in node_ids if peer != node_id]
            node = RaftNode(
                node_id=node_id,
                peer_ids=peers,
                transport=transport,
                election_timeout_ms=200,
                heartbeat_interval_ms=50,
                cluster_id="test",
            )
            nodes[node_id] = node
            registry[node_id] = node

        leader = nodes["node1"]
        leader.current_term = 1
        leader._become_leader()

        applied = {node_id: [] for node_id in node_ids}
        for node_id, node in nodes.items():
            node.register_commit_listener(
                lambda entry, nid=node_id: applied[nid].append(entry.event.command_id)
            )

        event = Event(
            cluster_id="test",
            raft_index=0,
            command_id="cmd-1",
            command_type="PATIENT_CREATE",
            payload={"identity": {"patientId": "P-1"}},
        )
        leader.append_command(event)

        deadline = time.time() + 2.0
        while time.time() < deadline:
            if all(len(applied[nid]) == 1 for nid in node_ids):
                break
            time.sleep(0.05)

        for node_id in node_ids:
            self.assertEqual(applied[node_id], ["cmd-1"])
            self.assertEqual(nodes[node_id].commit_index, 1)
            self.assertEqual(nodes[node_id].last_applied, 1)
            self.assertEqual(nodes[node_id].log[0].event.command_id, "cmd-1")


if __name__ == "__main__":
    unittest.main()
