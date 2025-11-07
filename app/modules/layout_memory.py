import sqlite3
import math
import json
import hashlib
from typing import Dict, Optional
from functools import lru_cache
import re


class LayoutMemory:
    def __init__(self, db_path: str = "layout_memory.db", cache_size: int = 512):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.create_tables()
        # LRU caches for per-field lookups
        self._cache_stats = lru_cache(maxsize=cache_size)(self._get_field_stats_from_db)
        self._cache_regex = lru_cache(maxsize=cache_size)(self._get_regex_from_db)

    def create_tables(self):
        cur = self.conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS field_stats (
                label TEXT NOT NULL,
                field TEXT NOT NULL,
                n INTEGER,
                mean_px REAL,
                mean_py REAL,
                M2_px REAL,
                M2_py REAL,
                PRIMARY KEY (label, field)
            );

            CREATE TABLE IF NOT EXISTS regex_cache (
                label TEXT NOT NULL,
                field TEXT NOT NULL,
                regex TEXT,
                PRIMARY KEY (label, field)
            );

            CREATE TABLE IF NOT EXISTS doc_cache (
                fingerprint TEXT PRIMARY KEY,
                label TEXT,
                result_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        self.conn.commit()

    # ---------- Internal helpers ----------

    def _get_field_stats_from_db(self, label: str, field: str) -> Optional[Dict]:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT n, mean_px, mean_py, M2_px, M2_py FROM field_stats WHERE label=? AND field=?",
            (label, field),
        )
        row = cur.fetchone()
        if row:
            n, mean_px, mean_py, M2_px, M2_py = row
            return dict(n=n, mean_px=mean_px, mean_py=mean_py, M2_px=M2_px, M2_py=M2_py)
        return None

    def _get_regex_from_db(self, label: str, field: str) -> Optional[str]:
        cur = self.conn.cursor()
        cur.execute("SELECT regex FROM regex_cache WHERE label=? AND field=?", (label, field))
        row = cur.fetchone()
        return row[0] if row else None

    # ---------- Layout statistics ----------

    def update_field(self, label: str, field: str, px: float, py: float, regex: Optional[str] = None):
        """Incrementally update field position statistics and optional regex."""
        stats = self._get_field_stats_from_db(label, field)
        if stats is None:
            n, mean_px, mean_py, M2_px, M2_py = 0, 0.0, 0.0, 0.0, 0.0
        else:
            n, mean_px, mean_py, M2_px, M2_py = (
                stats["n"], stats["mean_px"], stats["mean_py"], stats["M2_px"], stats["M2_py"]
            )

        # Welford’s incremental mean/variance update
        n += 1
        dx, dy = px - mean_px, py - mean_py
        mean_px += dx / n
        mean_py += dy / n
        M2_px += dx * (px - mean_px)
        M2_py += dy * (py - mean_py)

        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO field_stats (label, field, n, mean_px, mean_py, M2_px, M2_py)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(label, field)
            DO UPDATE SET n=?, mean_px=?, mean_py=?, M2_px=?, M2_py=?;
            """,
            (label, field, n, mean_px, mean_py, M2_px, M2_py, n, mean_px, mean_py, M2_px, M2_py),
        )

        if regex:
            cur.execute(
                """
                INSERT INTO regex_cache (label, field, regex)
                VALUES (?, ?, ?)
                ON CONFLICT(label, field)
                DO UPDATE SET regex=excluded.regex;
                """,
                (label, field, regex),
            )

        self.conn.commit()
        self._cache_stats.cache_clear()
        self._cache_regex.cache_clear()

    def get_field_ci(self, label: str, field: str, z: float = 1.96):
        stats = self._cache_stats(label, field)
        if not stats or stats["n"] < 2:
            return None
        n = stats["n"]
        var_px = stats["M2_px"] / (n - 1)
        var_py = stats["M2_py"] / (n - 1)
        se_px = math.sqrt(var_px / n)
        se_py = math.sqrt(var_py / n)
        ci = {
            "px": (stats["mean_px"] - z * se_px, stats["mean_px"] + z * se_px),
            "py": (stats["mean_py"] - z * se_py, stats["mean_py"] + z * se_py),
            "n": n,
            "width": 2 * z * se_px,
            "height": 2 * z * se_py,
        }
        ci["significance"] = self._significance(ci)
        return ci

    def _significance(self, ci: Dict) -> str:
        if ci["width"] < 0.02 and ci["height"] < 0.02 and ci["n"] >= 5:
            return "high"
        elif ci["width"] < 0.05 and ci["height"] < 0.05 and ci["n"] >= 3:
            return "medium"
        return "low"

    def get_regex(self, label: str, field: str) -> Optional[str]:
        return self._cache_regex(label, field)

    def find_candidate_blocks(self, label: str, field: str, blocks):
        ci = self.get_field_ci(label, field)
        if not ci or ci["significance"] == "low":
            return None
        px_range, py_range = ci["px"], ci["py"]
        for block_idx, block in enumerate(blocks):
            if px_range[0] <= block["px"] <= px_range[1] and py_range[0] <= block["py"] <= py_range[1]:
                return block_idx, block
        return None
    
    def layout_memory_search(self, label: str, schema, blocks):
        """
        Attempts to extract field values for a given document label using stored
        layout memory — specifically, spatial confidence intervals (CI) and
        previously learned regex patterns.

        For each field in the schema:
        - If a candidate block is found within a high-confidence CI and a valid
            regex exists:
            * The regex is applied to the block text.
            * If a match is found, the extracted value is added to
                `llm_avoided_fields`, meaning no LLM call is needed for that field.
            * The corresponding block is removed from the remaining pool.
        - If no reliable match is found or the regex fails/does not exist,
            the field is added to `llm_fallback_fields`, signaling that the LLM
            should extract it and possibly generate a new regex.

        Args:
            label (str): The document type or label.
            schema (dict): Mapping of field names to their textual descriptions.
            blocks (list[dict]): List of preprocessed text blocks, each containing:
                - "text": str — the cleaned text content.
                - "bbox": tuple(x0, y0, x1, y1) — bounding box coordinates.

        Returns:
            tuple:
                - llm_avoided_fields (dict[str, str]):
                    Fields successfully matched using layout memory:
                    {
                        field_name: extracted_value
                    }
                - llm_fallback_fields (dict[str, dict]):
                    Fields that require LLM extraction:
                    {
                        field_name: {
                            "descrição": str,        # description from schema
                            "extrair_regex": bool    # True if regex needs to be generated
                        }
                    }
        """
        llm_avoided_fields = {}
        llm_fallback_fields = {}
        remaining_blocks = blocks
        for field in schema.keys():
            
            matched_block = self.find_candidate_blocks(label, field, blocks)
            regex = self._get_regex_from_db(label, field)
            
            if matched_block and regex:
                block_idx, block_data = matched_block
                try:
                    regex_match = re.search(regex, block_data["text"], flags=re.MULTILINE)
                    if regex_match:
                        value = regex_match.group(0).strip()
                        llm_avoided_fields[field] = value
                        remaining_blocks.pop(block_idx)
                        continue
                except re.error as e:
                    print(f"[WARN] Invalid regex '{regex}' for field '{field}': {e}")
        
            # fallback to LLM
            llm_fallback_fields[field] = {
                "descrição": schema[field],
                "extrair_regex": True if not regex else False
            }
            
        return llm_avoided_fields, llm_fallback_fields

    # ---------- Document-level cache ----------

    @staticmethod
    def _fingerprint(doc_text: str, schema: str) -> str:
        """Create a deterministic hash for the (document, schema) pair."""
        h = hashlib.sha256()
        h.update(schema.encode("utf-8"))
        # normalize whitespace to avoid false misses
        h.update(" ".join(doc_text.split()).encode("utf-8"))
        return h.hexdigest()

    def get_cached_result(self, doc_text: str, schema: str) -> Optional[Dict]:
        """Retrieve cached structured output if present."""
        fp = self._fingerprint(doc_text, schema)
        cur = self.conn.cursor()
        cur.execute("SELECT result_json FROM doc_cache WHERE fingerprint=?", (fp,))
        row = cur.fetchone()
        return json.loads(row[0]) if row else None

    def set_cached_result(self, doc_text: str, schema: str, result: Dict, label: Optional[str] = None):
        """Store structured result in persistent cache."""
        fp = self._fingerprint(doc_text, schema)
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO doc_cache (fingerprint, label, result_json)
            VALUES (?, ?, ?)
            ON CONFLICT(fingerprint) DO UPDATE SET result_json=excluded.result_json;
            """,
            (fp, label, json.dumps(result)),
        )
        self.conn.commit()
