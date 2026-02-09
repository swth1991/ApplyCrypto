import os
import sys
import json
from pathlib import Path
from collections import defaultdict

# Add src to sys.path
current_dir = Path(__file__).resolve().parent
sys.path.append(str(current_dir / "src"))

# from config.config_manager import load_config
from parser.java_ast_parser import JavaASTParser

def build_inheritance_graph():
    # 1. Load config
    # We assume config.json is in the root directory where this script resides
    config_path = current_dir / "config.json"
    
    if not config_path.exists():
        print(f"Error: {config_path} not found.")
        return None

    print(f"Loading config from {config_path}...")
    try:
        # Using standard json load to avoid pydantic dependency
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        target_project_str = config_data.get("target_project")
        if not target_project_str:
            print("Error: 'target_project' field missing in config.json")
            return None
    except Exception as e:
        print(f"Failed to load config: {e}")
        return None
        
    target_project = Path(target_project_str)
    
    if not target_project.exists():
        print(f"Error: Target project path {target_project} does not exist.")
        return None

    print(f"Target project: {target_project}")
    
    # 2. Initialize Parser
    # Initialize without specific cache manager, it will create a temp one or we can provide one
    # If we want to persist cache in the project, we could set up CacheManager, 
    # but the default behavior of JavaASTParser with None is to use temp dir.
    # To use the project's cache mechanism if available:
    parser = JavaASTParser() 
    
    # 3. Scan files
    # config.source_file_types might be useful, but usually it's just .java for inheritance
    java_files = list(target_project.rglob("*.java"))
    print(f"Found {len(java_files)} Java files in target project.")
    
    # 4. Build Graph
    # child_simple_name -> ClassInfo dictionary
    inheritance_map = {}
    
    # We also keep a mapping of simple_name -> list of full_names (package.class) 
    # to detect ambiguities
    class_lookup_table = defaultdict(list)
    
    print("Parsing files...")
    success_count = 0
    fail_count = 0
    
    for file_path in java_files:
        # Optional: Skip test files if desired, based on config or convention
        # For now, we include everything to get a full graph
        
        try:
            classes, error = parser.get_classes(file_path)
            if error:
                # Common errors might be empty files or parse errors
                fail_count += 1
                continue
                
            for cls in classes:
                simple_name = cls.name
                
                # Check for duplicates
                if simple_name in inheritance_map:
                    # Collision detected
                    existing = inheritance_map[simple_name]
                    # print(f"Warning: Duplicate class name '{simple_name}' found.")
                    # print(f"  Existing: {existing['package']}.{simple_name}")
                    # print(f"  New:      {cls.package}.{simple_name}")
                    pass
                
                class_data = {
                    "name": simple_name,
                    "package": cls.package,
                    "superclass": cls.superclass,
                    "interfaces": cls.interfaces,
                    "file_path": str(cls.file_path)
                }
                
                inheritance_map[simple_name] = class_data
                class_lookup_table[simple_name].append(class_data)
                
            success_count += 1
            
        except Exception as e:
            print(f"Exception parsing {file_path}: {e}")
            fail_count += 1

    print(f"Parsing complete. Success: {success_count}, Failed: {fail_count}")
    return inheritance_map

def get_ancestors(inheritance_map, class_name):
    """
    Returns a list of ancestor class names for the given class_name.
    Order: Parent -> Grandparent -> ...
    """
    ancestors = []
    current_name = class_name
    
    visited = set()
    
    while True:
        if current_name in visited:
            # Cycle detected
            break
        visited.add(current_name)
        
        class_info = inheritance_map.get(current_name)
        if not class_info:
            break
            
        parent = class_info.get("superclass")
        if not parent:
            break
            
        # Java default parent is Object, but it might not be explicit. 
        # If explicit, we follow it.
        ancestors.append(parent)
        current_name = parent
        
    return ancestors

if __name__ == "__main__":
    graph = build_inheritance_graph()
    
    if graph:
        # Check for command line arguments
        if len(sys.argv) > 1:
            query_class = sys.argv[1]
            if query_class in graph:
                cls_info = graph[query_class]
                ancestors = get_ancestors(graph, query_class)
                result = {
                    "class": query_class,
                    "package": cls_info['package'],
                    "file_path": cls_info['file_path'],
                    "superclass": cls_info['superclass'],
                    "ancestors": ancestors
                }
                print(json.dumps(result, indent=2, ensure_ascii=False))
            else:
                print(json.dumps({"error": f"Class '{query_class}' not found."}, ensure_ascii=False))
            sys.exit(0)

        print("\n--- Inheritance Graph Builder ---")
        print(f"Graph loaded with {len(graph)} classes.")
        
        while True:
            try:
                user_input = input("\nEnter class name to find ancestors (or 'q' to quit): ").strip()
                if user_input.lower() == 'q':
                    break
                
                if not user_input:
                    continue
                    
                if user_input in graph:
                    cls_info = graph[user_input]
                    print(f"\n[Class Details]")
                    print(f"  Name: {cls_info['name']}")
                    print(f"  Package: {cls_info['package']}")
                    print(f"  File: {cls_info['file_path']}")
                    print(f"  Direct Parent: {cls_info['superclass']}")
                    print(f"  Interfaces: {', '.join(cls_info['interfaces'])}")
                    
                    ancestors = get_ancestors(graph, user_input)
                    if ancestors:
                        print(f"\n[Ancestors]")
                        for i, anc in enumerate(ancestors):
                            print(f"  {i+1}. {anc}")
                    else:
                        print("\n[Ancestors]")
                        print("  No explicit ancestors found (inherits Object implicitly).")
                else:
                    print(f"Class '{user_input}' not found in the graph.")
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"An error occurred: {e}")
