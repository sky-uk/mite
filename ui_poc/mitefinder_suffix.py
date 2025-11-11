import ast
from pathlib import Path
from typing import Dict, List, Union

from textual.app import App, ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Static, Tree


class Node:
    def __init__(self, name: str, path: Path, parent: "Node" = None):
        self.name = name
        self.path = path
        self.parent = parent
        self.children: List["Node"] = []

    def add_child(self, node: "Node"):
        self.children.append(node)

    def has_relevant_content(self) -> bool:
        if isinstance(self, (Journey, Scenario, DataPool, Config)):
            return True

        return any(child.has_relevant_content() for child in self.children)

    def to_dict(self) -> Dict:
        children = []
        if not isinstance(self, (Journey, Scenario, DataPool, Config)):
            children = [c.to_dict() for c in self.children]

        return {
            "type": self.__class__.__name__,
            "name": self.name,
            "path": str(self.path),
            "children": children,
        }


class Root(Node):
    pass


class Directory(Node):
    pass


class Module(Node):
    pass


class Journey(Node):
    pass


class Scenario(Node):
    pass


class DataPool(Node):
    pass


class Config(Node):
    pass


class MiteFinder:
    JOURNEY_SUFFIX = "_journey"
    SCENARIO_SUFFIX = "_scenario"
    DATAPOOL_SUFFIX = "_datapool"
    CONFIG_SUFFIX = "_config"

    def __init__(self, start_path: Union[str, Path]):
        self.start_path = Path(start_path).resolve()
        self.root = Root(name=self.start_path.name, path=self.start_path)

    def discover(self) -> Root:
        self._walk(self.start_path, self.root)
        self._filter_tree(self.root)
        return self.root

    def _walk(self, path: Path, parent_node: Node):
        if path.is_dir():
            dir_node = Directory(name=path.name, path=path, parent=parent_node)
            try:
                for child in sorted(path.iterdir()):
                    if child.name.startswith(".") or child.name.startswith("__"):
                        continue
                    self._walk(child, dir_node)
            except PermissionError:
                print(f" Skipping directory (no permission): {path}")
                return

            if dir_node.has_relevant_content():
                parent_node.add_child(dir_node)

        elif path.suffix == ".py":
            module_node = Module(name=path.name, path=path, parent=parent_node)
            relevant_items = self._inspect_file(path, module_node)

            if relevant_items:
                for item in relevant_items:
                    module_node.add_child(item)
                parent_node.add_child(module_node)

    def _inspect_file(self, file_path: Path, parent: Module) -> List[Node]:
        found: List[Node] = []
        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(file_path))
        except Exception as e:
            print(f" Could not parse {file_path}: {e}")
            return found

        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name.endswith(
                self.JOURNEY_SUFFIX
            ):
                found.append(Journey(name=node.name, path=file_path, parent=parent))
            elif isinstance(node, ast.FunctionDef):
                if node.name.endswith(self.SCENARIO_SUFFIX):
                    found.append(Scenario(name=node.name, path=file_path, parent=parent))
                elif node.name.endswith(self.DATAPOOL_SUFFIX):
                    found.append(DataPool(name=node.name, path=file_path, parent=parent))
                elif node.name.endswith(self.CONFIG_SUFFIX):
                    found.append(Config(name=node.name, path=file_path, parent=parent))
        return found

    def _filter_tree(self, node: Node):
        node.children = [child for child in node.children if child.has_relevant_content()]
        for child in node.children:
            self._filter_tree(child)


class MiteExplorer(App):
    CSS_PATH = None
    TITLE = "Mite Finder"
    SUB_TITLE = "Explore journeys, scenarios, and datapools"

    BINDINGS = [
        ("ctrl+c", "quit", "Exit"),
        ("q", "quit", "Exit"),
    ]

    def __init__(self, json_tree: Dict):
        super().__init__()
        self.json_tree = json_tree

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Container(
                Tree(self.json_tree["name"], data=self.json_tree), id="tree-container"
            )
            yield Static("Select an item to view details", id="info-panel")

    def on_mount(self):
        tree: Tree = self.query_one(Tree)
        self._populate_tree(tree.root, self.json_tree)
        tree.root.expand()

    def _populate_tree(self, node, data: Dict):
        for child in data.get("children", []):
            child_type = child["type"]
            if child_type in ["Journey", "Scenario", "DataPool", "Config"]:
                label = f"[bold]{child['name']}[/bold] ({child_type})"
            else:
                label = f"[bold]{child['name']}[/] ({child_type})"

            new_node = node.add(label, data=child)

            if child_type not in ["Journey", "Scenario", "DataPool", "Config"]:
                self._populate_tree(new_node, child)

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        node_data = event.node.data
        if node_data and node_data.get("type") in [
            "Journey",
            "Scenario",
            "DataPool",
            "Config",
        ]:
            info_panel = self.query_one("#info-panel", Static)

            item_type = node_data["type"]
            item_name = node_data["name"]

            info_text = f"[bold]Selected {item_type}:[/bold] {item_name}\n"

            info_panel.update(info_text)


if __name__ == "__main__":
    import sys

    start_dir = sys.argv[1] if len(sys.argv) > 1 else "."

    finder = MiteFinder(start_dir)
    tree = finder.discover()
    json_tree = tree.to_dict()

    app = MiteExplorer(json_tree)
    app.run()
