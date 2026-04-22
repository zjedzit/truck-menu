"""
SQLite Database Module for Elvis POS
Provides MongoDB-like interface for seamless migration from MongoDB to SQLite
"""

import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any

class SQLiteDB:
    """SQLite wrapper with MongoDB-like interface"""

    def __init__(self, db_path: str = "data/elvis_pos.db"):
        """Initialize SQLite database"""
        self.db_path = db_path

        # Create data directory if it doesn't exist
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # Connect to database
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

        # Initialize collections
        self._init_collections()

    def _init_collections(self):
        """Create collection tables"""
        cursor = self.conn.cursor()

        # Orders collection
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                _id TEXT PRIMARY KEY,
                data JSON NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Active tables collection
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS active_tables (
                _id INTEGER PRIMARY KEY,
                data JSON NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # POS history collection
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pos_history (
                _id TEXT PRIMARY KEY,
                data JSON NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # QR Sessions collection
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS qr_sessions (
                _id TEXT PRIMARY KEY,
                data JSON NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Users collection
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                _id TEXT PRIMARY KEY,
                data JSON NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Config collection
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS config (
                _id TEXT PRIMARY KEY,
                data JSON NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        self.conn.commit()

    def get_collection(self, collection_name: str):
        """Get a collection object"""
        return SQLiteCollection(self.conn, collection_name)

    def close(self):
        """Close database connection"""
        self.conn.close()

    def backup(self, backup_path: str):
        """Create database backup"""
        with sqlite3.connect(backup_path) as backup_conn:
            self.conn.backup(backup_conn)

    def health_check(self) -> bool:
        """Check if database is healthy"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT 1")
            return True
        except Exception as e:
            print(f"Database health check failed: {e}")
            return False


class SQLiteCollection:
    """MongoDB-like collection interface for SQLite"""

    def __init__(self, conn: sqlite3.Connection, collection_name: str):
        self.conn = conn
        self.name = collection_name

    def insert_one(self, document: Dict) -> str:
        """Insert a single document"""
        doc_id = document.get('_id', self._generate_id())
        document['_id'] = doc_id

        cursor = self.conn.cursor()
        cursor.execute(f'''
            INSERT OR REPLACE INTO {self.name} (_id, data)
            VALUES (?, ?)
        ''', (doc_id, json.dumps(document)))
        self.conn.commit()

        return doc_id

    def insert_many(self, documents: List[Dict]) -> List[str]:
        """Insert multiple documents"""
        ids = []
        for doc in documents:
            ids.append(self.insert_one(doc))
        return ids

    def find_one(self, query: Dict = None) -> Optional[Dict]:
        """Find a single document"""
        if query is None:
            query = {}

        cursor = self.conn.cursor()

        if '_id' in query:
            cursor.execute(f'SELECT data FROM {self.name} WHERE _id = ?', (query['_id'],))
        else:
            # Simple linear search for other queries
            cursor.execute(f'SELECT data FROM {self.name}')
            rows = cursor.fetchall()

            for row in rows:
                doc = json.loads(row[0])
                if self._matches_query(doc, query):
                    return doc
            return None

        row = cursor.fetchone()
        return json.loads(row[0]) if row else None

    def find(self, query: Dict = None) -> List[Dict]:
        """Find multiple documents"""
        if query is None:
            query = {}

        cursor = self.conn.cursor()
        cursor.execute(f'SELECT data FROM {self.name}')
        rows = cursor.fetchall()

        results = []
        for row in rows:
            doc = json.loads(row[0])
            if self._matches_query(doc, query):
                results.append(doc)

        return results

    def update_one(self, query: Dict, update: Dict) -> int:
        """Update a single document"""
        doc = self.find_one(query)
        if not doc:
            return 0

        # Handle $set operator
        if '$set' in update:
            doc.update(update['$set'])
        else:
            doc.update(update)

        cursor = self.conn.cursor()
        cursor.execute(f'''
            UPDATE {self.name} SET data = ?, updated_at = CURRENT_TIMESTAMP
            WHERE _id = ?
        ''', (json.dumps(doc), doc['_id']))
        self.conn.commit()

        return cursor.rowcount

    def update_many(self, query: Dict, update: Dict) -> int:
        """Update multiple documents"""
        docs = self.find(query)
        updated = 0

        for doc in docs:
            # Handle $set operator
            if '$set' in update:
                doc.update(update['$set'])
            else:
                doc.update(update)

            cursor = self.conn.cursor()
            cursor.execute(f'''
                UPDATE {self.name} SET data = ?, updated_at = CURRENT_TIMESTAMP
                WHERE _id = ?
            ''', (json.dumps(doc), doc['_id']))
            self.conn.commit()
            updated += cursor.rowcount

        return updated

    def delete_one(self, query: Dict) -> int:
        """Delete a single document"""
        doc = self.find_one(query)
        if not doc:
            return 0

        cursor = self.conn.cursor()
        cursor.execute(f'DELETE FROM {self.name} WHERE _id = ?', (doc['_id'],))
        self.conn.commit()

        return cursor.rowcount

    def delete_many(self, query: Dict) -> int:
        """Delete multiple documents"""
        docs = self.find(query)
        deleted = 0

        for doc in docs:
            cursor = self.conn.cursor()
            cursor.execute(f'DELETE FROM {self.name} WHERE _id = ?', (doc['_id'],))
            self.conn.commit()
            deleted += cursor.rowcount

        return deleted

    def count_documents(self, query: Dict = None) -> int:
        """Count documents matching query"""
        if query is None:
            query = {}

        docs = self.find(query)
        return len(docs)

    def drop(self):
        """Drop the collection"""
        cursor = self.conn.cursor()
        cursor.execute(f'DROP TABLE IF EXISTS {self.name}')
        self.conn.commit()

    def _matches_query(self, doc: Dict, query: Dict) -> bool:
        """Check if document matches query"""
        for key, value in query.items():
            if key not in doc:
                return False

            # Handle different query operators
            if isinstance(value, dict):
                if '$in' in value:
                    if doc[key] not in value['$in']:
                        return False
                elif '$eq' in value:
                    if doc[key] != value['$eq']:
                        return False
                else:
                    if doc[key] != value:
                        return False
            else:
                if doc[key] != value:
                    return False

        return True

    @staticmethod
    def _generate_id() -> str:
        """Generate unique document ID"""
        import uuid
        return str(uuid.uuid4())


# Global database instance
_db_instance = None

def get_db() -> Optional[SQLiteDB]:
    """Get or create database instance"""
    global _db_instance

    if _db_instance is None:
        db_path = os.environ.get('SQLITE_DB_PATH', 'data/elvis_pos.db')
        _db_instance = SQLiteDB(db_path)

    return _db_instance


def init_db(db_path: str = 'data/elvis_pos.db') -> SQLiteDB:
    """Initialize database"""
    global _db_instance
    _db_instance = SQLiteDB(db_path)
    return _db_instance


def close_db():
    """Close database connection"""
    global _db_instance
    if _db_instance:
        _db_instance.close()
        _db_instance = None
