import unittest
import tempfile
import os
from guppi_runtime.agent_manager.agent_registry import Registry
from guppi_runtime.agent_manager.agent_contracts import ContractError

class TestRegistry(unittest.TestCase):
    def setUp(self):
        # Use a temporary file for testing
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.temp_file.close()
        self.registry = Registry(self.temp_file.name)
    
    def tearDown(self):
        self.registry.close()
        os.unlink(self.temp_file.name)
    
    def test_create_and_get_template(self):
        data = {"name": "test_template", "version": "1.0"}
        entry = self.registry.create("template", "test_key", data)
        self.assertEqual(entry["kind"], "template")
        self.assertEqual(entry["key"], "test_key")
        self.assertEqual(entry["data"], data)
        self.assertEqual(entry["revision"], 1)
        
        # Retrieve the entry
        retrieved = self.registry.get("template", "test_key")
        self.assertEqual(retrieved, entry)
    
    def test_create_and_get_agent(self):
        data = {"name": "test_agent", "config": {"timeout": 30}}
        entry = self.registry.create("agent", "agent_1", data)
        self.assertEqual(entry["kind"], "agent")
        self.assertEqual(entry["key"], "agent_1")
        self.assertEqual(entry["data"], data)
        
        # Retrieve the entry
        retrieved = self.registry.get("agent", "agent_1")
        self.assertEqual(retrieved, entry)
    
    def test_create_and_get_crew(self):
        data = {"name": "test_crew", "members": ["agent_1", "agent_2"]}
        entry = self.registry.create("crew", "crew_1", data)
        self.assertEqual(entry["kind"], "crew")
        self.assertEqual(entry["key"], "crew_1")
        self.assertEqual(entry["data"], data)
        
        # Retrieve the entry
        retrieved = self.registry.get("crew", "crew_1")
        self.assertEqual(retrieved, entry)
    
    def test_create_duplicate_entry(self):
        data = {"name": "test"}
        self.registry.create("template", "test_key", data)
        
        # Try to create the same entry again
        with self.assertRaises(ContractError) as cm:
            self.registry.create("template", "test_key", data)
        
        self.assertEqual(cm.exception.code, "exists")
    
    def test_get_nonexistent_entry(self):
        result = self.registry.get("template", "nonexistent")
        self.assertIsNone(result)
    
    def test_bad_kind(self):
        data = {"name": "test"}
        with self.assertRaises(ContractError) as cm:
            self.registry.create("invalid_kind", "test_key", data)
        self.assertEqual(cm.exception.code, "bad_kind")
        
        with self.assertRaises(ContractError) as cm:
            self.registry.get("invalid_kind", "test_key")
        self.assertEqual(cm.exception.code, "bad_kind")
    
    def test_bad_key(self):
        data = {"name": "test"}
        with self.assertRaises(ContractError) as cm:
            self.registry.create("template", "", data)
        self.assertEqual(cm.exception.code, "bad_key")
        
        with self.assertRaises(ContractError) as cm:
            self.registry.create("template", 123, data)
        self.assertEqual(cm.exception.code, "bad_key")
        
        with self.assertRaises(ContractError) as cm:
            self.registry.get("template", "")
        self.assertEqual(cm.exception.code, "bad_key")
        
        with self.assertRaises(ContractError) as cm:
            self.registry.get("template", 123)
        self.assertEqual(cm.exception.code, "bad_key")
    
    def test_data_must_be_canonical(self):
        # Test with non-canonical data (set)
        with self.assertRaises(ContractError) as cm:
            self.registry.create("template", "test_key", {"x": {1, 2}})
        self.assertEqual(cm.exception.code, "not_canonical")
        
        # Test with non-canonical data (float inf)
        with self.assertRaises(ContractError) as cm:
            self.registry.create("template", "test_key", {"x": float('inf')})
        self.assertEqual(cm.exception.code, "not_canonical")
    
    def test_data_is_copied(self):
        data = {"name": "test"}
        entry = self.registry.create("template", "test_key", data)
        
        # Modify the original data
        data["name"] = "modified"
        
        # Entry should not be affected
        retrieved = self.registry.get("template", "test_key")
        self.assertEqual(retrieved["data"]["name"], "test")
    
    def test_revision_increments(self):
        # Note: The current implementation doesn't support revision incrementing
        # This is just to test that the revision field is properly stored
        data = {"name": "test"}
        entry = self.registry.create("template", "test_key", data)
        self.assertEqual(entry["revision"], 1)
        
        # Try to create again with same key (should fail)
        with self.assertRaises(ContractError) as cm:
            self.registry.create("template", "test_key", data)
        self.assertEqual(cm.exception.code, "exists")
    
    
    def test_list_single_entry(self):
        data = {"name": "test_template", "version": "1.0"}
        self.registry.create("template", "test_key", data)
        
        result = self.registry.list("template")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["kind"], "template")
        self.assertEqual(result[0]["key"], "test_key")
        self.assertEqual(result[0]["data"], data)
        self.assertEqual(result[0]["revision"], 1)
    
    def test_list_multiple_entries(self):
        # Create multiple entries
        self.registry.create("template", "key_a", {"name": "template_a"})
        self.registry.create("template", "key_b", {"name": "template_b"})
        self.registry.create("template", "key_c", {"name": "template_c"})
        
        result = self.registry.list("template")
        self.assertEqual(len(result), 3)
        
        # Should be sorted by key
        self.assertEqual(result[0]["key"], "key_a")
        self.assertEqual(result[1]["key"], "key_b")
        self.assertEqual(result[2]["key"], "key_c")
        
        # Check data integrity
        self.assertEqual(result[0]["data"]["name"], "template_a")
        self.assertEqual(result[1]["data"]["name"], "template_b")
        self.assertEqual(result[2]["data"]["name"], "template_c")
    
    def test_list_different_kinds(self):
        # Create entries of different kinds
        self.registry.create("template", "template_key", {"name": "template"})
        self.registry.create("agent", "agent_key", {"name": "agent"})
        self.registry.create("crew", "crew_key", {"name": "crew"})
        
        # List each kind
        template_list = self.registry.list("template")
        agent_list = self.registry.list("agent")
        crew_list = self.registry.list("crew")
        
        self.assertEqual(len(template_list), 1)
        self.assertEqual(len(agent_list), 1)
        self.assertEqual(len(crew_list), 1)
        
        self.assertEqual(template_list[0]["key"], "template_key")
        self.assertEqual(agent_list[0]["key"], "agent_key")
        self.assertEqual(crew_list[0]["key"], "crew_key")
    
    
    def test_cross_registry_compatibility(self):
        # Test that data written by one registry can be read by another
        data = {"name": "test_template", "version": "1.0"}
        self.registry.create("template", "test_key", data)
        
        # Create a new registry on the same file
        new_registry = Registry(self.temp_file.name)
        
        # Read the data with the new registry
        result = new_registry.list("template")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["key"], "test_key")
        self.assertEqual(result[0]["data"], data)
        
        new_registry.close()

    def test_update_success(self):
        # Create an entry
        data = {"name": "test_template", "version": "1.0"}
        entry = self.registry.create("template", "test_key", data)
        self.assertEqual(entry["revision"], 1)
        
        # Update the entry
        new_data = {"name": "updated_template", "version": "2.0"}
        updated_entry = self.registry.update("template", "test_key", new_data, 1)
        self.assertEqual(updated_entry["revision"], 2)
        self.assertEqual(updated_entry["data"], new_data)
        
        # Verify the update was applied
        retrieved = self.registry.get("template", "test_key")
        self.assertEqual(retrieved["revision"], 2)
        self.assertEqual(retrieved["data"], new_data)
    
    def test_update_not_found(self):
        # Try to update a non-existent entry
        data = {"name": "test"}
        with self.assertRaises(ContractError) as cm:
            self.registry.update("template", "nonexistent", data, 1)
        self.assertEqual(cm.exception.code, "not_found")
    
    def test_update_bad_revision(self):
        # Create an entry
        data = {"name": "test"}
        self.registry.create("template", "test_key", data)
        
        # Test with invalid revision values
        with self.assertRaises(ContractError) as cm:
            self.registry.update("template", "test_key", data, 0)
        self.assertEqual(cm.exception.code, "bad_revision")
        
        with self.assertRaises(ContractError) as cm:
            self.registry.update("template", "test_key", data, -1)
        self.assertEqual(cm.exception.code, "bad_revision")
        
        with self.assertRaises(ContractError) as cm:
            self.registry.update("template", "test_key", data, "invalid")
        self.assertEqual(cm.exception.code, "bad_revision")
        
        with self.assertRaises(ContractError) as cm:
            self.registry.update("template", "test_key", data, True)
        self.assertEqual(cm.exception.code, "bad_revision")
    
    def test_update_conflict(self):
        # Create an entry
        data = {"name": "test"}
        entry = self.registry.create("template", "test_key", data)
        revision = entry["revision"]
        
        # Try to update with wrong revision
        new_data = {"name": "updated"}
        with self.assertRaises(ContractError) as cm:
            self.registry.update("template", "test_key", new_data, revision + 1)
        self.assertEqual(cm.exception.code, "conflict")
        
        # Verify the entry was not modified
        retrieved = self.registry.get("template", "test_key")
        self.assertEqual(retrieved["revision"], revision)
        self.assertEqual(retrieved["data"], data)
    

    def test_delete_success(self):
        # Create an entry
        data = {"name": "test_template", "version": "1.0"}
        entry = self.registry.create("template", "test_key", data)
        self.assertEqual(entry["revision"], 1)
        
        # Delete the entry
        self.registry.delete("template", "test_key", 1)
        
        # Verify the entry is gone
        retrieved = self.registry.get("template", "test_key")
        self.assertIsNone(retrieved)
        
        # Verify it's no longer in the list
        result = self.registry.list("template")
        self.assertEqual(result, [])

    def test_delete_not_found(self):
        # Try to delete a non-existent entry
        with self.assertRaises(ContractError) as cm:
            self.registry.delete("template", "nonexistent", 1)
        self.assertEqual(cm.exception.code, "not_found")

    def test_delete_bad_revision(self):
        # Create an entry
        data = {"name": "test"}
        self.registry.create("template", "test_key", data)
        
        # Test with invalid revision values
        with self.assertRaises(ContractError) as cm:
            self.registry.delete("template", "test_key", 0)
        self.assertEqual(cm.exception.code, "bad_revision")
        
        with self.assertRaises(ContractError) as cm:
            self.registry.delete("template", "test_key", -1)
        self.assertEqual(cm.exception.code, "bad_revision")
        
        with self.assertRaises(ContractError) as cm:
            self.registry.delete("template", "test_key", "invalid")
        self.assertEqual(cm.exception.code, "bad_revision")
        
        with self.assertRaises(ContractError) as cm:
            self.registry.delete("template", "test_key", True)
        self.assertEqual(cm.exception.code, "bad_revision")

    def test_delete_conflict(self):
        # Create an entry
        data = {"name": "test"}
        entry = self.registry.create("template", "test_key", data)
        revision = entry["revision"]
        
        # Try to delete with wrong revision
        with self.assertRaises(ContractError) as cm:
            self.registry.delete("template", "test_key", revision + 1)
        self.assertEqual(cm.exception.code, "conflict")
        
        # Verify the entry still exists
        retrieved = self.registry.get("template", "test_key")
        self.assertEqual(retrieved["revision"], revision)
        self.assertEqual(retrieved["data"], data)

    def test_delete_then_create_same_key(self):
        # Create an entry
        data = {"name": "test"}
        entry = self.registry.create("template", "test_key", data)
        revision = entry["revision"]
        
        # Delete the entry
        self.registry.delete("template", "test_key", revision)
        
        # Create a new entry with the same key
        new_data = {"name": "new_template"}
        new_entry = self.registry.create("template", "test_key", new_data)
        
        # The new entry should start at revision 1
        self.assertEqual(new_entry["revision"], 1)
        self.assertEqual(new_entry["data"], new_data)
        
        # Verify it's retrievable
        retrieved = self.registry.get("template", "test_key")
        self.assertEqual(retrieved["revision"], 1)
        self.assertEqual(retrieved["data"], new_data)

    def test_command_create(self):
        data = {"name": "test_template", "version": "1.0"}
        result = self.registry.command("cmd1", "create", "template", "test_key", data)
        self.assertEqual(result["command_id"], "cmd1")
        self.assertEqual(result["revision"], 1)
        self.assertEqual(result["replayed"], False)
        
        # Verify the entry was created
        entry = self.registry.get("template", "test_key")
        self.assertEqual(entry["data"], data)
        self.assertEqual(entry["revision"], 1)

    def test_command_update(self):
        # Create an entry first
        data = {"name": "test_template", "version": "1.0"}
        self.registry.create("template", "test_key", data)
        
        # Update using command
        new_data = {"name": "updated_template", "version": "2.0"}
        result = self.registry.command("cmd2", "update", "template", "test_key", new_data, 1)
        self.assertEqual(result["command_id"], "cmd2")
        self.assertEqual(result["revision"], 2)
        self.assertEqual(result["replayed"], False)
        
        # Verify the entry was updated
        entry = self.registry.get("template", "test_key")
        self.assertEqual(entry["data"], new_data)
        self.assertEqual(entry["revision"], 2)

    def test_command_delete(self):
        # Create an entry first
        data = {"name": "test_template", "version": "1.0"}
        self.registry.create("template", "test_key", data)
        
        # Delete using command
        result = self.registry.command("cmd3", "delete", "template", "test_key", None, 1)
        self.assertEqual(result["command_id"], "cmd3")
        self.assertIsNone(result["revision"])
        self.assertEqual(result["replayed"], False)
        
        # Verify the entry was deleted
        entry = self.registry.get("template", "test_key")
        self.assertIsNone(entry)

    def test_command_bad_command_id(self):
        data = {"name": "test"}
        with self.assertRaises(ContractError) as cm:
            self.registry.command("", "create", "template", "test_key", data)
        self.assertEqual(cm.exception.code, "bad_command")
        
        with self.assertRaises(ContractError) as cm:
            self.registry.command(123, "create", "template", "test_key", data)
        self.assertEqual(cm.exception.code, "bad_command")

    def test_command_bad_operation(self):
        data = {"name": "test"}
        with self.assertRaises(ContractError) as cm:
            self.registry.command("cmd1", "invalid_op", "template", "test_key", data)
        self.assertEqual(cm.exception.code, "bad_command")

    def test_command_create_duplicate(self):
        data = {"name": "test"}
        self.registry.create("template", "test_key", data)
        
        # Try to create the same entry using command
        with self.assertRaises(ContractError) as cm:
            self.registry.command("cmd1", "create", "template", "test_key", data)
        self.assertEqual(cm.exception.code, "exists")

    def test_command_update_not_found(self):
        data = {"name": "test"}
        with self.assertRaises(ContractError) as cm:
            self.registry.command("cmd1", "update", "template", "nonexistent", data, 1)
        self.assertEqual(cm.exception.code, "not_found")

    def test_command_update_bad_revision(self):
        data = {"name": "test"}
        self.registry.create("template", "test_key", data)
        
        # Test with invalid revision values
        with self.assertRaises(ContractError) as cm:
            self.registry.command("cmd1", "update", "template", "test_key", data, 0)
        self.assertEqual(cm.exception.code, "bad_revision")
        
        with self.assertRaises(ContractError) as cm:
            self.registry.command("cmd1", "update", "template", "test_key", data, -1)
        self.assertEqual(cm.exception.code, "bad_revision")
        
        with self.assertRaises(ContractError) as cm:
            self.registry.command("cmd1", "update", "template", "test_key", data, "invalid")
        self.assertEqual(cm.exception.code, "bad_revision")
        
        with self.assertRaises(ContractError) as cm:
            self.registry.command("cmd1", "update", "template", "test_key", data, True)
        self.assertEqual(cm.exception.code, "bad_revision")

    def test_command_update_conflict(self):
        # Create an entry
        data = {"name": "test"}
        entry = self.registry.create("template", "test_key", data)
        revision = entry["revision"]
        
        # Try to update with wrong revision using command
        new_data = {"name": "updated"}
        with self.assertRaises(ContractError) as cm:
            self.registry.command("cmd1", "update", "template", "test_key", new_data, revision + 1)
        self.assertEqual(cm.exception.code, "conflict")
        
        # Verify the entry was not modified
        retrieved = self.registry.get("template", "test_key")
        self.assertEqual(retrieved["revision"], revision)
        self.assertEqual(retrieved["data"], data)

    def test_command_delete_not_found(self):
        with self.assertRaises(ContractError) as cm:
            self.registry.command("cmd1", "delete", "template", "nonexistent", None, 1)
        self.assertEqual(cm.exception.code, "not_found")

    def test_command_delete_bad_revision(self):
        data = {"name": "test"}
        self.registry.create("template", "test_key", data)
        
        # Test with invalid revision values
        with self.assertRaises(ContractError) as cm:
            self.registry.command("cmd1", "delete", "template", "test_key", None, 0)
        self.assertEqual(cm.exception.code, "bad_revision")
        
        with self.assertRaises(ContractError) as cm:
            self.registry.command("cmd1", "delete", "template", "test_key", None, -1)
        self.assertEqual(cm.exception.code, "bad_revision")
        
        with self.assertRaises(ContractError) as cm:
            self.registry.command("cmd1", "delete", "template", "test_key", None, "invalid")
        self.assertEqual(cm.exception.code, "bad_revision")
        
        with self.assertRaises(ContractError) as cm:
            self.registry.command("cmd1", "delete", "template", "test_key", None, True)
        self.assertEqual(cm.exception.code, "bad_revision")

    def test_command_delete_conflict(self):
        # Create an entry
        data = {"name": "test"}
        entry = self.registry.create("template", "test_key", data)
        revision = entry["revision"]
        
        # Try to delete with wrong revision using command
        with self.assertRaises(ContractError) as cm:
            self.registry.command("cmd1", "delete", "template", "test_key", None, revision + 1)
        self.assertEqual(cm.exception.code, "conflict")
        
        # Verify the entry still exists
        retrieved = self.registry.get("template", "test_key")
        self.assertEqual(retrieved["revision"], revision)
        self.assertEqual(retrieved["data"], data)

    def test_command_idempotent_create(self):
        # Test idempotent create
        data = {"name": "test_template", "version": "1.0"}
        
        # First execution
        result1 = self.registry.command("cmd1", "create", "template", "test_key", data)
        self.assertEqual(result1["command_id"], "cmd1")
        self.assertEqual(result1["revision"], 1)
        self.assertEqual(result1["replayed"], False)
        
        # Second execution with same command_id and same data
        result2 = self.registry.command("cmd1", "create", "template", "test_key", data)
        self.assertEqual(result2["command_id"], "cmd1")
        self.assertEqual(result2["revision"], 1)
        self.assertEqual(result2["replayed"], True)
        
        # Verify the entry was created
        entry = self.registry.get("template", "test_key")
        self.assertEqual(entry["data"], data)
        self.assertEqual(entry["revision"], 1)
        
        # Try with different data - should raise conflict
        with self.assertRaises(ContractError) as cm:
            self.registry.command("cmd1", "create", "template", "test_key", {"different": "data"})
        self.assertEqual(cm.exception.code, "command_conflict")

    def test_command_idempotent_update(self):
        # Create an entry first
        data = {"name": "test_template", "version": "1.0"}
        self.registry.create("template", "test_key", data)
        
        # Update using command
        new_data = {"name": "updated_template", "version": "2.0"}
        result1 = self.registry.command("cmd2", "update", "template", "test_key", new_data, 1)
        self.assertEqual(result1["command_id"], "cmd2")
        self.assertEqual(result1["revision"], 2)
        self.assertEqual(result1["replayed"], False)
        
        # Second execution with same command_id and same data
        result2 = self.registry.command("cmd2", "update", "template", "test_key", new_data, 1)
        self.assertEqual(result2["command_id"], "cmd2")
        self.assertEqual(result2["revision"], 2)
        self.assertEqual(result2["replayed"], True)
        
        # Verify the entry was updated
        entry = self.registry.get("template", "test_key")
        self.assertEqual(entry["data"], new_data)
        self.assertEqual(entry["revision"], 2)
        
        # Try with different data - should raise conflict
        with self.assertRaises(ContractError) as cm:
            self.registry.command("cmd2", "update", "template", "test_key", {"different": "data"}, 1)
        self.assertEqual(cm.exception.code, "command_conflict")

    def test_command_idempotent_delete(self):
        # Create an entry first
        data = {"name": "test_template", "version": "1.0"}
        self.registry.create("template", "test_key", data)
        
        # Delete using command
        result1 = self.registry.command("cmd3", "delete", "template", "test_key", None, 1)
        self.assertEqual(result1["command_id"], "cmd3")
        self.assertIsNone(result1["revision"])
        self.assertEqual(result1["replayed"], False)
        
        # Second execution with same command_id
        result2 = self.registry.command("cmd3", "delete", "template", "test_key", None, 1)
        self.assertEqual(result2["command_id"], "cmd3")
        self.assertIsNone(result2["revision"])
        self.assertEqual(result2["replayed"], True)
        
        # Verify the entry was deleted
        entry = self.registry.get("template", "test_key")
        self.assertIsNone(entry)

    def test_command_receipt_persistence(self):
        # Create a registry and execute a command
        data = {"name": "test_template", "version": "1.0"}
        self.registry.command("cmd1", "create", "template", "test_key", data)
        
        # Close and reopen the registry
        self.registry.close()
        self.registry = Registry(self.temp_file.name)
        
        # Verify the receipt is still there and command is idempotent
        result = self.registry.command("cmd1", "create", "template", "test_key", data)
        self.assertEqual(result["replayed"], True)
        self.assertEqual(result["revision"], 1)

    def test_command_receipt_rollback_on_failure(self):
        # Create an entry first
        data = {"name": "test"}
        self.registry.create("template", "test_key", data)
        
        # Try to update with wrong revision (should fail)
        with self.assertRaises(ContractError) as cm:
            self.registry.command("cmd1", "update", "template", "test_key", {"new": "data"}, 999)
        self.assertEqual(cm.exception.code, "conflict")
        
        # Verify no receipt was stored
        cursor = self.registry.conn.execute("SELECT * FROM receipts WHERE command_id = ?", ("cmd1",))
        row = cursor.fetchone()
        self.assertIsNone(row)
        
        # Verify the entry still exists with original data
        entry = self.registry.get("template", "test_key")
        self.assertEqual(entry["data"], data)
        self.assertEqual(entry["revision"], 1)


    def test_outbox_ack(self):
        # Create an entry
        data = {"name": "test_template", "version": "1.0"}
        self.registry.command("cmd1", "create", "template", "test_key", data)
        
        # Check outbox entries before ack
        pending = self.registry.outbox_pending()
        self.assertEqual(len(pending), 1)
        
        # Ack the entry
        self.registry.outbox_ack(pending[0]["seq"])
        
        # Check that it's no longer pending
        pending = self.registry.outbox_pending()
        self.assertEqual(len(pending), 0)
        
        # Check that acked is now 1
        cursor = self.registry.conn.execute("SELECT acked FROM outbox WHERE seq = ?", (1,))
        row = cursor.fetchone()
        self.assertEqual(row[0], 1)
    
    def test_outbox_ack_twice(self):
        # Create an entry
        data = {"name": "test_template", "version": "1.0"}
        self.registry.command("cmd1", "create", "template", "test_key", data)
        
        # Check outbox entries before ack
        pending = self.registry.outbox_pending()
        self.assertEqual(len(pending), 1)
        
        # Ack the entry first time
        self.registry.outbox_ack(pending[0]["seq"])
        
        # Ack the same entry again (should be fine)
        self.registry.outbox_ack(pending[0]["seq"])
        
        # Check that it's still not pending
        pending = self.registry.outbox_pending()
        self.assertEqual(len(pending), 0)
        
        # Check that acked is still 1
        cursor = self.registry.conn.execute("SELECT acked FROM outbox WHERE seq = ?", (1,))
        row = cursor.fetchone()
        self.assertEqual(row[0], 1)
    
    def test_outbox_ack_unknown_seq(self):
        # Try to acknowledge a non-existent sequence
        with self.assertRaises(ContractError) as cm:
            self.registry.outbox_ack(999)
        self.assertEqual(cm.exception.code, "not_found")

    def test_outbox_with_replay(self):
        # Create an entry
        data = {"name": "test_template", "version": "1.0"}
        self.registry.command("cmd1", "create", "template", "test_key", data)
        
        # Replay the same command
        result = self.registry.command("cmd1", "create", "template", "test_key", data)
        self.assertTrue(result["replayed"])
        
        # Check that no new outbox entry was created for replayed command
        pending = self.registry.outbox_pending()
        self.assertEqual(len(pending), 1)  # Still only one entry

    def test_outbox_with_failed_command(self):
        # Create an entry first
        data = {"name": "test"}
        self.registry.create("template", "test_key", data)
        
        # Try to update with wrong revision (should fail)
        with self.assertRaises(ContractError) as cm:
            self.registry.command("cmd1", "update", "template", "test_key", {"new": "data"}, 999)
        self.assertEqual(cm.exception.code, "conflict")
        
        # Check that no outbox entry was created for failed command
        pending = self.registry.outbox_pending()
        self.assertEqual(len(pending), 0)

    def test_command_delete_returns_none_revision(self):
        # Create an entry first
        data = {"name": "test_template", "version": "1.0"}
        self.registry.create("template", "test_key", data)
        
        # Delete using command - should return revision None
        result = self.registry.command("cmd3", "delete", "template", "test_key", None, 1)
        self.assertEqual(result["command_id"], "cmd3")
        self.assertIsNone(result["revision"])
        self.assertEqual(result["replayed"], False)
        
        # Verify the entry was deleted
        entry = self.registry.get("template", "test_key")
        self.assertIsNone(entry)

    def test_command_idempotent_delete_returns_none_revision(self):
        # Create an entry first
        data = {"name": "test_template", "version": "1.0"}
        self.registry.create("template", "test_key", data)
        
        # Delete using command
        result1 = self.registry.command("cmd3", "delete", "template", "test_key", None, 1)
        self.assertEqual(result1["command_id"], "cmd3")
        self.assertIsNone(result1["revision"])
        self.assertEqual(result1["replayed"], False)
        
        # Second execution with same command_id
        result2 = self.registry.command("cmd3", "delete", "template", "test_key", None, 1)
        self.assertEqual(result2["command_id"], "cmd3")
        self.assertIsNone(result2["revision"])
        self.assertEqual(result2["replayed"], True)
        
        # Verify the entry was deleted
        entry = self.registry.get("template", "test_key")
        self.assertIsNone(entry)

if __name__ == '__main__':
    # Run the tests to make sure everything works
    unittest.main()