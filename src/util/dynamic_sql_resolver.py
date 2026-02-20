import logging
import re
from typing import Dict, Optional, Set, List
from lxml import etree


logger = logging.getLogger("applycrypto.utils.dynamic_sql_resolver")

SQL_TAGS = ["select", "insert", "update", "delete"]

class DynamicSQLResolver:
    def __init__(self):
        self.logger = logger
        self.sql_map = {}

    def _get_local_tag(self, tag: str) -> str:
        """Extracts local tag name, stripping namespace if present."""
        if not isinstance(tag, str):
            return ""
        if '}' in tag:
            return tag.split('}', 1)[1]
        return tag

    def resolve_dynamic_sql(self, xml_path: str, sql_id: str) -> Optional[str]:
        """
        Parses MyBatis XML and returns a 'resolved' SQL string for the given statement ID.
        This is a static resolution (does not evaluate <if> conditions), primarily for basic analysis.
        """
        try:
            # Parse XML
            parser = etree.XMLParser(recover=True, encoding='utf-8')
            tree = etree.parse(xml_path, parser=parser)
            root = tree.getroot()
            
            # 1. Build <sql> ID map for includes
            self.sql_map = {}
            # We search all descendants for <sql> tags
            for elem in root.iter():
                tag = self._get_local_tag(elem.tag)
                if tag == 'sql':
                    sid = elem.get('id')
                    if sid:
                        self.sql_map[sid] = elem
            
            # 2. Find the target statement element
            target_elem = None
            for elem in root.iter():
                tag = self._get_local_tag(elem.tag)
                if tag in SQL_TAGS and elem.get('id') == sql_id:
                    target_elem = elem
                    break
            
            if target_elem is None:
                self.logger.warning(f"Statement ID '{sql_id}' not found in {xml_path}")
                return None

            # 3. Recursive processing
            resolved_sql = self._process_element(target_elem, set())
            
            # 4. Final Cleanup (collapse multiple spaces)
            return re.sub(r'\s+', ' ', resolved_sql).strip()

        except Exception as e:
            self.logger.error(f"Error resolving SQL {sql_id} in {xml_path}: {e}")
            return None

    def _process_element(self, element, active_includes: Set[str]) -> str:
        """Recursively process an element to build the SQL string."""
        parts = []
        
        # 1. Text content before the first child tag
        if element.text:
            parts.append(element.text)
            
        # 2. Process children
        for child in element:
            tag = self._get_local_tag(child.tag)
            
            # --- <include refid="..."> ---
            if tag == 'include':
                refid = child.get('refid')
                if refid in self.sql_map:
                    if refid in active_includes:
                        self.logger.warning(f"Circular reference detected in <include refid='{refid}'>. Skipping to avoid infinite recursion.")
                    else:
                        active_includes.add(refid)
                        parts.append(self._process_element(self.sql_map[refid], active_includes))
                        active_includes.remove(refid)
                else:
                    parts.append(f" /* MISSING INCLUDE: {refid} */ ")

            # --- <if> ---
            elif tag == 'if':
                # Does not evaluate logic. Just includes the content "as is".
                parts.append(self._process_element(child, active_includes))
            
            # --- <choose> / <when> / <otherwise> ---
            elif tag == 'choose':
                # Logic: Pick the first <when>. If none, pick <otherwise>.
                processed_branch = False
                for sub in child:
                    sub_tag = self._get_local_tag(sub.tag)
                    if sub_tag == 'when':
                        # Simplification: Assume first WHEN is the path taken
                        parts.append(self._process_element(sub, active_includes))
                        processed_branch = True
                        break 
                
                if not processed_branch:
                    for sub in child:
                        sub_tag = self._get_local_tag(sub.tag)
                        if sub_tag == 'otherwise':
                            parts.append(self._process_element(sub, active_includes))
                            break

            # --- <foreach> ---
            elif tag == 'foreach':
                # <foreach open="(" close=")" separator=","> ... </foreach>
                # Flattening strategy: "open" + content + "close"
                open_str = child.get('open', '')
                close_str = child.get('close', '')
                
                parts.append(f" {open_str} ")
                parts.append(self._process_element(child, active_includes))
                parts.append(f" {close_str} ")
            
            # --- <where> ---
            elif tag == 'where':
                # Trims prefix 'AND'/'OR' and adds 'WHERE'
                content = self._process_element(child, active_includes).strip()
                if content:
                    # Regex to remove leading AND/OR (case insensitive)
                    content_clean = re.sub(r'(?i)^(AND|OR)\s+', '', content)
                    parts.append(f" WHERE {content_clean} ")

            # --- <set> ---
            elif tag == 'set':
                # Trims suffix ',' and adds 'SET'
                content = self._process_element(child, active_includes).strip()
                if content:
                    # Regex to remove trailing comma
                    content_clean = re.sub(r',\s*$', '', content)
                    parts.append(f" SET {content_clean} ")

            # --- <trim> ---
            elif tag == 'trim':
                parts.append(self._process_trim(child, active_includes))
            
            # --- Normal element or unhandled tag ---
            else:
                parts.append(self._process_element(child, active_includes))
            
            # 3. Text content after this child (tail)
            if child.tail:
                parts.append(child.tail)
        
        return "".join(parts)

    def _process_trim(self, element, active_includes: Set[str]) -> str:
        """Handles the generic <trim> tag."""
        prefix = element.get('prefix', '')
        suffix = element.get('suffix', '')
        prefix_overrides = element.get('prefixOverrides', '')
        suffix_overrides = element.get('suffixOverrides', '')
        
        content = self._process_element(element, active_includes).strip()
        if not content:
            return ""
        
        # Handle prefixOverrides (e.g. "AND |OR ")
        if prefix_overrides:
            tokens = [t.strip() for t in prefix_overrides.split('|')]
            for token in tokens:
                # Remove token if it appears at the start
                pattern = r'(?i)^' + re.escape(token) + r'\s+'
                # Or just token? usually token + space if it's a word? MyBatis documentation is lenient.
                # We'll simple-check startswith.
                if re.match(r'(?i)^' + re.escape(token), content):
                    content = re.sub(r'(?i)^' + re.escape(token), '', content, count=1).strip()
                    break # MyBatis removes one match
        
        # Handle suffixOverrides
        if suffix_overrides:
            tokens = [t.strip() for t in suffix_overrides.split('|')]
            for token in tokens:
                if re.search(r'(?i)' + re.escape(token) + r'$', content):
                    content = re.sub(r'(?i)' + re.escape(token) + r'$', '', content, count=1).strip()
                    break

        return f" {prefix} {content} {suffix} "
