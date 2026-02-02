from pathlib import Path
from typing import List, Optional, Tuple

from .java_ast_parser import JavaASTParser

class DigitalChannelParser:
    """
    Parser for Digital Channel Java files to extract NAMESPACE and methods.
    """
    def __init__(self):
        self.parser = JavaASTParser()

    def extract_info(self, file_path: str) -> Tuple[Optional[str], Optional[str], List[dict]]:
        """
        Extract namespace, class name and methods from a Java file.
        
        Args:
            file_path: Absolute path to the Java file

        Returns:
            Tuple containing:
            - namespace (str or None)
            - class_name (str or None)
            - methods (List[str] or None)
        """
        path_obj = Path(file_path)
        tree, error = self.parser.parse_file(path_obj)
        
        if not tree:
            # Parsing failed
            return None, None, None

        class_infos = self.parser.extract_class_info(tree, path_obj)
        if not class_infos:
            return None, None, None
        
        # Identify the target class matching the filename
        target_class_name = path_obj.stem
        target_class = None
        for cls in class_infos:
            if cls.name == target_class_name:
                target_class = cls
                break
        
        if not target_class and class_infos:
            target_class = class_infos[0]
            
        if not target_class:
            return None, None, None

        # 1. Extract NAMESPACE
        # Look for: private static final String NAMESPACE = "value";
        namespace = None
        for field in target_class.fields:
            if field['name'] == 'NAMESPACE' and field['initial_value']:
                val = field['initial_value']
                # Remove quotes from the string literal
                # e.g. '"com.param"' -> 'com.param'
                val = val.strip('"').strip("'")
                # Remove trailing dots if any (as per original logic: .strip('.'))
                namespace = val.strip('.')
                break
        
        if not namespace:
            return None, None, None

        # 2. Extract Methods
        # JavaASTParser extracts 'method_declaration' which handles methods.
        # It skips constructors ('constructor_declaration').
        methods_data = []
        
        import re
        # Pattern to find: NAMESPACE + "value"
        # We assume NAMESPACE variable usage.
        # It might be wise to handle cases where it's concatenated differently, but for now stick to the requested pattern.
        sql_pattern = re.compile(r'NAMESPACE\s*\+\s*"([^"]+)"')

        for method in target_class.methods:
            sql_id = None
            if method.body:
                match = sql_pattern.search(method.body)
                if match:
                    suffix = match.group(1)
                    sql_id = namespace + suffix
            
            methods_data.append({
                "method": method.name,
                "sql_id": sql_id
            })
        
        return namespace, target_class.name, methods_data
