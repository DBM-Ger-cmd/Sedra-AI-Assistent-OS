import sqlite3
import json
from .agent_contracts import ContractError, canonical_digest

class Registry:
    def __init__(self, path):
        self.path = path
        self.conn = sqlite3.connect(path, isolation_level=None)
        self._create_tables()
    
    def _create_tables(self):
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS entries (
                kind TEXT NOT NULL,
                key TEXT NOT NULL,
                data TEXT NOT NULL,
                revision INTEGER NOT NULL,
                PRIMARY KEY (kind, key)
            )
        ''')
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS receipts (
                command_id TEXT NOT NULL PRIMARY KEY,
                request TEXT NOT NULL,
                revision INTEGER
            )
        ''')
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS outbox (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                event TEXT NOT NULL,
                kind TEXT NOT NULL,
                key TEXT NOT NULL,
                revision INTEGER,
                data TEXT,
                command_id TEXT NOT NULL,
                acked INTEGER NOT NULL DEFAULT 0
            )
        ''')
        self.conn.commit()
    
    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def _validate_kind(self, kind):
        if not isinstance(kind, str):
            raise ContractError("bad_kind", f"Kind must be a string, got {type(kind).__name__}")
        if kind not in ("template", "agent", "crew"):
            raise ContractError("bad_kind", f"Unknown kind: {kind}")
    
    def _validate_key(self, key):
        if not isinstance(key, str) or not key:
            raise ContractError("bad_key", f"Key must be a non-empty string, got {type(key).__name__}")
    
    def _validate_data(self, data):
        # First check if data is canonical (this will raise not_canonical if not)
        try:
            canonical_digest(data)
        except ContractError as e:
            if e.code == "not_canonical":
                raise e
            else:
                raise ContractError("bad_data", "Data must be JSON serializable")
        # If canonical_digest succeeds, data is JSON serializable, so we can safely dump it
        json.dumps(data)
    
    def _validate_revision(self, revision):
        if not isinstance(revision, int) or revision < 1 or revision is True or revision is False:
            raise ContractError("bad_revision", f"Revision must be an integer >= 1, got {revision}")
    
    def _validate_command_request(self, op, kind, key, data, expected_revision):
        self._validate_kind(kind)
        self._validate_key(key)
        if op == "create":
            if expected_revision is not None:
                raise ContractError("bad_command", "expected_revision must be None for create")
            self._validate_data(data)
        elif op == "update":
            if expected_revision is None:
                raise ContractError("bad_command", "expected_revision must be provided for update")
            self._validate_data(data)
            self._validate_revision(expected_revision)
        elif op == "delete":
            if expected_revision is None:
                raise ContractError("bad_command", "expected_revision must be provided for delete")
            self._validate_revision(expected_revision)
    
    def _validate_outbox_event(self, event):
        if event not in ("created", "updated", "deleted"):
            raise ContractError("bad_command", f"Invalid event type: {event}")
    
    def _validate_outbox_kind(self, kind):
        self._validate_kind(kind)
    
    def _validate_outbox_key(self, key):
        self._validate_key(key)
    
    def _validate_outbox_revision(self, revision):
        if revision is not None:
            self._validate_revision(revision)
    
    def _validate_outbox_data(self, data):
        if data is not None:
            self._validate_data(data)
    
    def _normalize_request(self, op, kind, key, data, expected_revision):
        """Normalize request for receipt storage and comparison"""
        # For create operations, expected_revision should be None
        # For delete operations, data should be None
        normalized = {
            "op": op,
            "kind": kind,
            "key": key,
            "data": data if op != "delete" else None,
            "expected_revision": expected_revision if op != "create" else None
        }
        return json.dumps(normalized, sort_keys=True)
    
    def get(self, kind, key):
        self._validate_kind(kind)
        self._validate_key(key)
        
        cursor = self.conn.execute(
            "SELECT revision, data FROM entries WHERE kind = ? AND key = ?",
            (kind, key)
        )
        row = cursor.fetchone()
        if row is None:
            return None
        
        return {
            "kind": kind,
            "key": key,
            "revision": row[0],
            "data": json.loads(row[1])
        }
    
    def create(self, kind, key, data):
        self._validate_kind(kind)
        self._validate_key(key)
        self._validate_data(data)
        
        # Check if the entry already exists
        try:
            self.conn.execute(
                "INSERT INTO entries (kind, key, data, revision) VALUES (?, ?, ?, 1)",
                (kind, key, json.dumps(data))
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            raise ContractError("exists", "Entry already exists")
        
        return self.get(kind, key)
    
    def update(self, kind, key, data, expected_revision):
        self._validate_kind(kind)
        self._validate_key(key)
        self._validate_data(data)
        self._validate_revision(expected_revision)
        
        # Atomic update with revision check
        # First, try to update with the expected revision
        result = self.conn.execute(
            "UPDATE entries SET data = ?, revision = revision + 1 WHERE kind = ? AND key = ? AND revision = ?",
            (json.dumps(data), kind, key, expected_revision)
        )
        self.conn.commit()
        
        # Check how many rows were affected
        if result.rowcount == 0:
            # Check if the entry exists at all
            cursor = self.conn.execute(
                "SELECT revision FROM entries WHERE kind = ? AND key = ?",
                (kind, key)
            )
            row = cursor.fetchone()
            if row is None:
                raise ContractError("not_found", "Entry not found")
            else:
                raise ContractError("conflict", "Revision conflict")
        
        # Return the updated entry
        return self.get(kind, key)
    
    def delete(self, kind, key, expected_revision):
        self._validate_kind(kind)
        self._validate_key(key)
        self._validate_revision(expected_revision)
        
        # Atomic delete with revision check
        # First, try to delete with the expected revision
        result = self.conn.execute(
            "DELETE FROM entries WHERE kind = ? AND key = ? AND revision = ?",
            (kind, key, expected_revision)
        )
        self.conn.commit()
        
        # Check how many rows were affected
        if result.rowcount == 0:
            # Check if the entry exists at all
            cursor = self.conn.execute(
                "SELECT revision FROM entries WHERE kind = ? AND key = ?",
                (kind, key)
            )
            row = cursor.fetchone()
            if row is None:
                raise ContractError("not_found", "Entry not found")
            else:
                raise ContractError("conflict", "Revision conflict")

    def command(self, command_id, op, kind, key, data=None, expected_revision=None):
        if not isinstance(command_id, str) or not command_id:
            raise ContractError("bad_command", "Command ID must be a non-empty string")
        if op not in ("create", "update", "delete"):
            raise ContractError("bad_command", "Operation must be one of 'create', 'update', 'delete'")
        
        # For create operations, expected_revision should be ignored
        # Normalize the request for receipt storage and comparison
        if op == "create":
            request_json = self._normalize_request(op, kind, key, data, None)
        else:
            request_json = self._normalize_request(op, kind, key, data, expected_revision)
        
        # Look up the receipt first (before any operation)
        cursor = self.conn.execute(
            "SELECT request, revision FROM receipts WHERE command_id = ?",
            (command_id,)
        )
        row = cursor.fetchone()
        if row is not None:
            # Command was previously executed
            stored_request, stored_revision = row
            if stored_request == request_json:
                # Same request - return replayed result
                return {
                    "command_id": command_id,
                    "revision": stored_revision,
                    "replayed": True
                }
            else:
                # Different request - conflict
                raise ContractError("command_conflict", "Command ID already used with different request")
        
        # Validate the request parameters
        # For create operations, expected_revision should be None in validation
        if op == "create":
            self._validate_command_request(op, kind, key, data, None)
        else:
            self._validate_command_request(op, kind, key, data, expected_revision)
        
        # Begin transaction
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            # Call the appropriate operation based on op
            if op == "create":
                # For create, expected_revision is ignored
                entry = self.create(kind, key, data)
                revision = entry["revision"]
                result = {
                    "command_id": command_id,
                    "revision": revision,
                    "replayed": False
                }
                # Write to outbox (only for successful, non-replayed commands)
                if not result["replayed"]:
                    self._write_outbox_entry("created", kind, key, revision, data, command_id)
            elif op == "update":
                # For update, data is required
                entry = self.update(kind, key, data, expected_revision)
                revision = entry["revision"]
                result = {
                    "command_id": command_id,
                    "revision": revision,
                    "replayed": False
                }
                # Write to outbox (only for successful, non-replayed commands)
                if not result["replayed"]:
                    self._write_outbox_entry("updated", kind, key, revision, data, command_id)
            elif op == "delete":
                # For delete, data is ignored
                # First get the revision to be able to return it
                cursor = self.conn.execute(
                    "SELECT revision FROM entries WHERE kind = ? AND key = ?",
                    (kind, key)
                )
                row = cursor.fetchone()
                if row is None:
                    # Entry doesn't exist, let the delete operation handle the error
                    raise ContractError("not_found", "Entry not found")
                revision = row[0]
                # Now perform the delete operation
                self.delete(kind, key, expected_revision)
                result = {
                    "command_id": command_id,
                    "revision": None,  # Return None for deleted entries (as per requirements)
                    "replayed": False
                }
                # Write to outbox (only for successful, non-replayed commands)
                if not result["replayed"]:
                    self._write_outbox_entry("deleted", kind, key, None, None, command_id)
            
            # Store the receipt
            self.conn.execute(
                "INSERT INTO receipts (command_id, request, revision) VALUES (?, ?, ?)",
                (command_id, request_json, result["revision"])
            )
            self.conn.commit()
            return result
        except Exception:
            self.conn.rollback()
            raise

    # These methods are not used in the current implementation, but kept for completeness
    # They are not called by any method in the current code
    def _create_operation(self, kind, key, data):
        self._validate_kind(kind)
        self._validate_key(key)
        self._validate_data(data)
        
        # Check if the entry already exists
        try:
            self.conn.execute(
                "INSERT INTO entries (kind, key, data, revision) VALUES (?, ?, ?, 1)",
                (kind, key, json.dumps(data))
            )
        except sqlite3.IntegrityError:
            raise ContractError("exists", "Entry already exists")
        
        return self.get(kind, key)
    
    def _update_operation(self, kind, key, data, expected_revision):
        self._validate_kind(kind)
        self._validate_key(key)
        self._validate_data(data)
        self._validate_revision(expected_revision)
        
        # Atomic update with revision check
        # First, try to update with the expected revision
        result = self.conn.execute(
            "UPDATE entries SET data = ?, revision = revision + 1 WHERE kind = ? AND key = ? AND revision = ?",
            (json.dumps(data), kind, key, expected_revision)
        )
        
        # Check how many rows were affected
        if result.rowcount == 0:
            # Check if the entry exists at all
            cursor = self.conn.execute(
                "SELECT revision FROM entries WHERE kind = ? AND key = ?",
                (kind, key)
            )
            row = cursor.fetchone()
            if row is None:
                raise ContractError("not_found", "Entry not found")
            else:
                raise ContractError("conflict", "Revision conflict")
        
        # Return the updated entry
        return self.get(kind, key)

    def _delete_operation(self, kind, key, expected_revision):
        self._validate_kind(kind)
        self._validate_key(key)
        self._validate_revision(expected_revision)
        
        # Atomic delete with revision check
        # First, try to delete with the expected revision
        result = self.conn.execute(
            "DELETE FROM entries WHERE kind = ? AND key = ? AND revision = ?",
            (kind, key, expected_revision)
        )
        
        # Check how many rows were affected
        if result.rowcount == 0:
            # Check if the entry exists at all
            cursor = self.conn.execute(
                "SELECT revision FROM entries WHERE kind = ? AND key = ?",
                (kind, key)
            )
            row = cursor.fetchone()
            if row is None:
                raise ContractError("not_found", "Entry not found")
            else:
                raise ContractError("conflict", "Revision conflict")
    
    def _write_outbox_entry(self, event, kind, key, revision, data, command_id):
        """Write an entry to the outbox table"""
        self._validate_outbox_event(event)
        self._validate_outbox_kind(kind)
        self._validate_outbox_key(key)
        self._validate_outbox_revision(revision)
        self._validate_outbox_data(data)
        
        self.conn.execute(
            "INSERT INTO outbox (event, kind, key, revision, data, command_id) VALUES (?, ?, ?, ?, ?, ?)",
            (event, kind, key, revision, json.dumps(data) if data is not None else None, command_id)
        )
    
    def outbox_pending(self, limit=100):
        """Return pending outbox entries"""
        if not isinstance(limit, int) or limit < 1:
            raise ContractError("bad_limit", "limit must be an int >= 1")
        
        cursor = self.conn.execute(
            "SELECT seq, event, kind, key, revision, data, command_id FROM outbox WHERE acked = 0 ORDER BY seq ASC LIMIT ?",
            (limit,)
        )
        rows = cursor.fetchall()
        
        return [
            {
                "seq": row[0],
                "event": row[1],
                "kind": row[2],
                "key": row[3],
                "revision": row[4],
                "data": json.loads(row[5]) if row[5] is not None else None,
                "command_id": row[6]
            }
            for row in rows
        ]
    
    def outbox_ack(self, seq):
        """Mark an outbox entry as acknowledged"""
        # First check if the sequence exists
        cursor = self.conn.execute("SELECT seq FROM outbox WHERE seq = ?", (seq,))
        row = cursor.fetchone()
        if row is None:
            raise ContractError("not_found", f"Outbox entry with seq {seq} not found")
        
        # Mark the entry as acknowledged
        self.conn.execute("UPDATE outbox SET acked = 1 WHERE seq = ?", (seq,))
        self.conn.commit()
    
    def list(self, kind):
        # Validate the kind - unknown kinds should raise bad_kind error
        self._validate_kind(kind)
        
        # Get all entries of the specified kind, sorted by key
        cursor = self.conn.execute(
            "SELECT kind, key, revision, data FROM entries WHERE kind = ? ORDER BY key",
            (kind,)
        )
        rows = cursor.fetchall()
        
        return [
            {
                "kind": row[0],
                "key": row[1],
                "revision": row[2],
                "data": json.loads(row[3])
            }
            for row in rows
        ]