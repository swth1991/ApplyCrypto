import sys
import unittest
from pathlib import Path

# Add src to python path
sys.path.append(str(Path.cwd() / "src"))

try:
    from parser.call_graph_builder import CallGraphBuilder
    from parser.java_ast_parser import ClassInfo
    from models.inherit_node import InheritNode
except ImportError as e:
    print(f"ImportError: {e}")
    print(f"sys.path: {sys.path}")
    sys.exit(1)

class TestInheritFeatures(unittest.TestCase):
    def setUp(self):
        self.builder = CallGraphBuilder()
        self.builder.file_to_classes_map = {}
        self.builder.class_name_to_info = {}

        # Create mock ClassInfo objects
        # Note: ClassInfo expects certain fields, I'll provide necessary ones
        self.cls1 = ClassInfo(
            name="Child", 
            package="com.example", 
            superclass="Parent", 
            interfaces=["Iface"], 
            file_path=Path("Child.java"),
            methods=[],
            fields=[],
            imports=[],
            annotations=[],
            has_jpa_repository=False,
            is_interface_class=False,
            inner_classes=[]
        )
        self.cls2 = ClassInfo(
            name="Parent", 
            package="com.example", 
            superclass="GrandParent", 
            interfaces=[], 
            file_path=Path("Parent.java"),
            methods=[],
            fields=[],
            imports=[],
            annotations=[],
            has_jpa_repository=False,
            is_interface_class=False,
            inner_classes=[]
        )
        self.cls3 = ClassInfo(
            name="GrandParent", 
            package="com.example", 
            superclass="Object", 
            interfaces=[], 
            file_path=Path("GrandParent.java"),
            methods=[],
            fields=[],
            imports=[],
            annotations=[],
            has_jpa_repository=False,
            is_interface_class=False,
            inner_classes=[]
        )

        self.builder.file_to_classes_map["Child.java"] = [self.cls1]
        self.builder.file_to_classes_map["Parent.java"] = [self.cls2]
        self.builder.file_to_classes_map["GrandParent.java"] = [self.cls3]

        self.builder.class_name_to_info["Child"] = self.cls1
        self.builder.class_name_to_info["Parent"] = self.cls2
        self.builder.class_name_to_info["GrandParent"] = self.cls3

    def test_get_inheritance_map(self):
        imap = self.builder.get_inheritance_map()
        self.assertIn("Child", imap)
        child_node = imap["Child"]
        self.assertIsInstance(child_node, InheritNode)
        self.assertEqual(child_node.name, "Child")
        self.assertEqual(child_node.superclass, "Parent")
        self.assertEqual(child_node.package, "com.example")
        self.assertEqual(child_node.file_path, "Child.java")

    def test_get_ancestor_inherit_nodes(self):
        ancestors = self.builder.get_ancestor_inherit_nodes("Child")
        self.assertEqual(len(ancestors), 2)
        self.assertEqual(ancestors[0].name, "Parent")
        self.assertEqual(ancestors[1].name, "GrandParent")

    def test_get_ancestor_non_existent(self):
        ancestors = self.builder.get_ancestor_inherit_nodes("NonExistent")
        self.assertEqual(len(ancestors), 0)

if __name__ == "__main__":
    unittest.main()
