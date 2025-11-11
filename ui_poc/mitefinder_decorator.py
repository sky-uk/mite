import ast
import asyncio
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Union

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Static, Tree


class Node:
    def __init__(self, name: str, path: Path, parent: "Node" = None):
        self.name = name
        self.path = path
        self.parent = parent
        self.children: List["Node"] = []

    def add_child(self, node: "Node"):
        self.children.append(node)

    def has_relevant_content(self) -> bool:
        """Check if this node or any of its children contain relevant content"""
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


class BuildTestCommand:
    """Class to build mite test commands from selected components"""

    # Fixed additional flags that don't take values
    BOOLEAN_FLAGS = [
        "--debugging",
        "--hide-constant-logs",
        "--report",
        "--journey-logging",
    ]

    # Flags that take values
    VALUE_FLAGS = ["--spawn-rate", "--message-socket"]

    def __init__(self, start_dir: Path):
        self.start_dir = start_dir
        self.reset()

    def reset(self):
        """Reset all selections"""
        self.test_type: Optional[str] = None  # 'journey' or 'scenario'
        self.journey_or_scenario: Optional[Dict] = None
        self.datapool: Optional[Dict] = None
        self.config: Optional[Dict] = None
        self.boolean_flags: List[str] = []
        self.value_flags: Dict[str, str] = {}
        self.add_to_config: List[tuple] = []  # List of (key, value) tuples

    def set_test_component(self, component: Dict):
        """Set the main test component (journey or scenario)"""
        comp_type = component.get("type", "").lower()

        if comp_type == "journey":
            self.test_type = "journey"
            self.journey_or_scenario = component
        elif comp_type == "scenario":
            self.test_type = "scenario"
            self.journey_or_scenario = component
            # If scenario is selected, ignore any previously selected datapool
            self.datapool = None

    def set_datapool(self, component: Dict):
        """Set datapool component (only valid for journey tests)"""
        if self.test_type == "journey":
            self.datapool = component

    def set_config(self, component: Dict):
        """Set config component"""
        self.config = component

    def toggle_boolean_flag(self, flag: str):
        """Toggle a boolean flag"""
        if flag in self.boolean_flags:
            self.boolean_flags.remove(flag)
        else:
            self.boolean_flags.append(flag)

    def set_value_flag(self, flag: str, value: str):
        """Set a flag with value"""
        if flag in self.VALUE_FLAGS and value:
            self.value_flags[flag] = value
        elif flag in self.value_flags and not value:
            del self.value_flags[flag]

    def add_additional_config(self, key: str, value: str):
        """Add an additional config"""
        if key and value:
            # Remove existing override with same key
            self.add_to_config = [(k, v) for k, v in self.add_to_config if k != key]
            self.add_to_config.append((key, value))

    def remove_additional_config(self, key: str):
        """Remove an additional config by key"""
        self.add_to_config = [(k, v) for k, v in self.add_to_config if k != key]

    def _path_to_module_notation(self, file_path: str) -> str:
        """Convert file path to module notation relative to start_dir"""
        path = Path(file_path)
        try:
            relative_path = path.relative_to(self.start_dir)
            # Remove .py extension and convert path separators to dots
            module_path = str(relative_path.with_suffix(""))
            return module_path.replace("/", ".")
        except ValueError:
            # If path is not relative to start_dir, use absolute
            return str(path.with_suffix(""))

    def build_command(self) -> str:
        """Build the complete mite test command"""
        if not self.test_type or not self.journey_or_scenario:
            return "# Select a journey or scenario to build command"

        parts = ["mite", self.test_type, "test"]

        # Add main component (journey or scenario)
        main_path = self._path_to_module_notation(self.journey_or_scenario["path"])
        main_name = self.journey_or_scenario["name"]
        parts.append(f"{main_path}:{main_name}")

        # Add datapool if present (only for journey tests)
        if self.test_type == "journey" and self.datapool:
            datapool_path = self._path_to_module_notation(self.datapool["path"])
            datapool_name = self.datapool["name"]
            parts.append(f"{datapool_path}:{datapool_name}")

        # Add config if present
        if self.config:
            config_path = self._path_to_module_notation(self.config["path"])
            config_name = self.config["name"]
            parts.append(f"--config={config_path}:{config_name}")

        # Add boolean flags
        for flag in self.boolean_flags:
            parts.append(flag)

        # Add value flags
        for flag, value in self.value_flags.items():
            parts.append(f"{flag}={value}")

        # Add additional configs
        for key, value in self.add_to_config:
            parts.append(f"--add-to-config={key}:{value}")

        return " ".join(parts)

    def get_command_list(self) -> List[str]:
        """Get the command as a list for subprocess execution"""
        command_str = self.build_command()
        if command_str.startswith("#"):
            return []
        return command_str.split()

    def get_status_summary(self) -> str:
        """Get a summary of current selections"""
        lines = []

        if self.test_type and self.journey_or_scenario:
            lines.append(f"Test: {self.test_type} ({self.journey_or_scenario['name']})")

        if self.test_type == "journey" and self.datapool:
            lines.append(f"Datapool: {self.datapool['name']}")

        if self.config:
            lines.append(f"Config: {self.config['name']}")

        if self.boolean_flags:
            lines.append(f"Flags: {', '.join(self.boolean_flags)}")

        if self.value_flags:
            flag_strs = [f"{k}={v}" for k, v in self.value_flags.items()]
            lines.append(f"Value flags: {', '.join(flag_strs)}")

        if self.add_to_config:
            config_strs = [f"{k}:{v}" for k, v in self.add_to_config]
            lines.append(f"Additional Configs: {', '.join(config_strs)}")

        return " | ".join(lines) if lines else "No components selected"


class ValueFlagDialog(ModalScreen[str]):
    """Modal dialog for setting value flags"""

    def __init__(self, flag_name: str, current_value: str = ""):
        super().__init__()
        self.flag_name = flag_name
        self.current_value = current_value

    def compose(self) -> ComposeResult:
        with Container():
            yield Label(f"Set value for {self.flag_name}:")
            yield Input(
                value=self.current_value, placeholder="Enter value...", id="value-input"
            )
            with Horizontal():
                yield Button("OK", variant="primary", id="ok-btn")
                yield Button("Cancel", id="cancel-btn")
                yield Button("Clear", variant="error", id="clear-btn")

    def on_mount(self) -> None:
        """Focus the input when the dialog opens"""
        self.query_one("#value-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ok-btn":
            input_widget = self.query_one("#value-input", Input)
            self.dismiss(input_widget.value)
        elif event.button.id == "clear-btn":
            self.dismiss("")
        else:  # Cancel
            self.dismiss(None)


class ConfigDialog(ModalScreen[tuple]):
    """Modal dialog for setting additional configs"""

    def __init__(self, key: str = "", value: str = ""):
        super().__init__()
        self.current_key = key
        self.current_value = value

    def compose(self) -> ComposeResult:
        with Container():
            yield Label("Add additional config:")
            yield Label("Key:")
            yield Input(value=self.current_key, placeholder="config.key", id="key-input")
            yield Label("Value:")
            yield Input(value=self.current_value, placeholder="value", id="value-input")
            with Horizontal():
                yield Button("OK", variant="primary", id="ok-btn")
                yield Button("Cancel", id="cancel-btn")

    def on_mount(self) -> None:
        """Focus the key input when the dialog opens"""
        self.query_one("#key-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ok-btn":
            key_input = self.query_one("#key-input", Input)
            value_input = self.query_one("#value-input", Input)
            if key_input.value.strip() and value_input.value.strip():
                self.dismiss((key_input.value.strip(), value_input.value.strip()))
            else:
                # Don't dismiss if either field is empty - just return
                return
        else:  # Cancel
            self.dismiss(None)


class CheapMiteFinder:
    def __init__(self, start_path: Union[str, Path]):
        self.start_path = Path(start_path).resolve()
        self.root = Root(name=self.start_path.name, path=self.start_path)

    def discover(self) -> Root:
        print(f"Scanning for decorated functions and variables in {self.start_path}...")
        self._walk(self.start_path, self.root)
        self._filter_tree(self.root)

        # Count found items
        total_items = self._count_items(self.root)
        print(f"Found {total_items} mite components")

        return self.root

    def _count_items(self, node: Node) -> int:
        """Count leaf nodes (actual functions/variables)"""
        count = 0
        if isinstance(node, (Journey, Scenario, DataPool, Config)):
            count = 1
        for child in node.children:
            count += self._count_items(child)
        return count

    def _walk(self, path: Path, parent_node: Node):
        if path.is_dir():
            dir_node = Directory(name=path.name, path=path, parent=parent_node)
            try:
                for child in sorted(path.iterdir()):
                    if child.name.startswith(".") or child.name.startswith("__"):
                        continue
                    self._walk(child, dir_node)
            except PermissionError:
                print(f"Skipping directory (no permission): {path}")
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
        """Use AST to find decorated functions and mite variables"""
        found: List[Node] = []

        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(file_path))
        except Exception as e:
            print(f"Could not parse {file_path}: {e}")
            return found

        # Find decorated functions
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_name = node.name
                mite_type = self._get_mite_type_from_decorators(node.decorator_list)

                if mite_type:
                    print(f"Found {mite_type} function: {func_name} in {file_path}")
                    self._add_node_by_type(found, mite_type, func_name, file_path, parent)

        # Find mite_ui_wrapper.type(value) assignments
        variables = self._get_mite_variables_from_assignments(tree)
        for var_name, mite_type in variables:
            print(f"Found {mite_type} variable: {var_name} in {file_path}")
            self._add_node_by_type(found, mite_type, var_name, file_path, parent)

        return found

    def _get_mite_type_from_decorators(self, decorator_list: List[ast.expr]) -> str:
        """Extract mite type from decorator AST nodes"""
        for decorator in decorator_list:
            # Handle @mite_ui_wrapper('type') calls
            if isinstance(decorator, ast.Call):
                # Check if it's a call to mite_ui_wrapper
                if (
                    isinstance(decorator.func, ast.Name)
                    and decorator.func.id == "mite_ui_wrapper"
                    and decorator.args
                ):

                    # Get the first argument (the type string)
                    first_arg = decorator.args[0]
                    if isinstance(first_arg, ast.Constant) and isinstance(
                        first_arg.value, str
                    ):
                        return first_arg.value
                    elif isinstance(first_arg, ast.Str):  # For older Python versions
                        return first_arg.s

            # Handle @mite_ui_wrapper.type_name if using attribute access
            elif isinstance(decorator, ast.Attribute):
                if (
                    isinstance(decorator.value, ast.Name)
                    and decorator.value.id == "mite_ui_wrapper"
                ):
                    return decorator.attr

        return None

    def _get_mite_variables_from_assignments(self, tree) -> List[tuple]:
        """Find mite_ui_wrapper attribute calls in assignments"""
        variables = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                # Check if assignment uses mite_ui_wrapper.type(value)
                if (
                    isinstance(node.value, ast.Call)
                    and isinstance(node.value.func, ast.Attribute)
                    and isinstance(node.value.func.value, ast.Name)
                    and node.value.func.value.id == "mite_ui_wrapper"
                ):

                    # Get the component type from attribute name
                    component_type = node.value.func.attr

                    # Get the variable name from assignment target
                    if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                        var_name = node.targets[0].id
                        variables.append((var_name, component_type))

        return variables

    def _add_node_by_type(
        self,
        found: List[Node],
        mite_type: str,
        name: str,
        file_path: Path,
        parent: Module,
    ):
        """Helper to add nodes based on type"""
        if mite_type == "journey":
            found.append(Journey(name=name, path=file_path, parent=parent))
        elif mite_type == "scenario":
            found.append(Scenario(name=name, path=file_path, parent=parent))
        elif mite_type == "datapool":
            found.append(DataPool(name=name, path=file_path, parent=parent))
        elif mite_type == "config":
            found.append(Config(name=name, path=file_path, parent=parent))

    def _filter_tree(self, node: Node):
        """Remove children that don't have relevant content"""
        node.children = [child for child in node.children if child.has_relevant_content()]
        for child in node.children:
            self._filter_tree(child)


class CheapMiteExplorer(App):
    TITLE = "Mite Test Command Builder"
    SUB_TITLE = "Professional Test Framework Integration Tool"
    CSS = """
    #left-panel {
        width: 1fr;
        min-width: 30;
        height: 1fr;
    }
    
    #right-panel {
        width: 2fr;
        min-width: 50;
        height: 1fr;
    }
    
    #main-content {
        height: 1fr;
    }
    
    #footer-container {
        height: 25;
        dock: bottom;
        background: $surface;
        border: solid $primary;
    }
    
    #footer-header {
        height: 8;
        background: $surface-lighten-1;
        border-bottom: solid $accent;
        padding: 1;
    }
    
    #log-scroll-container {
        height: 11;
        border: none;
        background: $background;
        scrollbar-size: 2 1;
    }
    
    #log-output {
        background: $background;
        color: $text;
        padding: 1;
        width: 100%;
        height: auto;
        min-height: 10;
    }
    
    .flag-section {
        border: solid $accent;
        margin: 1;
        padding: 1;
        max-height: 8;
        overflow-y: auto;
    }
    
    .flag-button {
        margin: 0 1;
    }
    
    Checkbox {
        margin: 0 1;
    }
    
    #run-controls {
        height: 3;
        padding: 0 1;
        dock: bottom;
    }
    
    #command-display {
        width: 1fr;
        height: auto;
        padding: 0 1;
    }
    
    .control-button {
        margin: 0 1;
        width: 12;
        height: 3;
        background: $primary;
        border: solid $accent;
        color: $text;
    }
    """

    TITLE = "Cheap Mite Finder"
    SUB_TITLE = "Build and run mite test commands"

    BINDINGS = [
        ("ctrl+c", "quit", "Exit"),
        ("q", "quit", "Exit"),
        ("r", "reset", "Reset selections"),
    ]

    def __init__(self, json_tree: Dict, start_dir: Path):
        super().__init__()
        self.json_tree = json_tree
        self.command_builder = BuildTestCommand(start_dir)
        self.start_dir = start_dir
        self.process: Optional[subprocess.Popen] = None
        self.command_running = False

    def compose(self) -> ComposeResult:
        with Vertical():
            # Main content area
            with Horizontal(id="main-content"):
                # Left panel - Flags (adjusted for smaller height)
                with ScrollableContainer(id="left-panel"):
                    yield Label("[bold]Flag Configuration[/bold]", id="flags-title")

                    # Boolean flags section
                    with Container(classes="flag-section"):
                        yield Label("[bold]Boolean Flags[/bold]")
                        for flag in self.command_builder.BOOLEAN_FLAGS:
                            yield Checkbox(flag, id=f"bool-{flag}")

                    # Value flags section
                    with Container(classes="flag-section"):
                        yield Label("[bold]Value Flags[/bold]")
                        for flag in self.command_builder.VALUE_FLAGS:
                            yield Button(
                                f"{flag}: (not set)",
                                id=f"value-{flag}",
                                classes="flag-button",
                            )

                    # additional configs section
                    with Container(classes="flag-section"):
                        yield Label("[bold]Additional Configs[/bold]")
                        yield Button(
                            "+ Add Additional Config",
                            id="add-config-btn",
                            variant="success",
                        )
                        yield Container(id="additional-config-list")

                # Right panel - File explorer
                with Container(id="right-panel"):
                    yield Tree(
                        self.json_tree["name"], data=self.json_tree, id="file-tree"
                    )

            # Footer - Command display and execution
            with Vertical(id="footer-container"):
                # Command and control buttons
                with Horizontal(id="footer-header"):
                    yield Static(self._build_command_text(), id="command-display")
                    yield Button(
                        "Run", variant="success", id="run-btn", classes="control-button"
                    )
                    yield Button(
                        "Stop", variant="error", id="stop-btn", classes="control-button"
                    )

                # Log output area
                with ScrollableContainer(id="log-scroll-container"):
                    yield Static("Ready to execute commands...", id="log-output")

    def _build_command_text(self) -> str:
        """Build just the command text for display"""
        command = self.command_builder.build_command()
        return f"[bold]Command:[/bold] {command}"

    def on_mount(self):
        tree: Tree = self.query_one("#file-tree")
        self._populate_tree(tree.root, self.json_tree)
        tree.root.expand()
        self._update_flags_display()
        self._update_buttons_state()

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

    def _update_command_display(self):
        """Update the command display"""
        command_display = self.query_one("#command-display", Static)
        command_display.update(self._build_command_text())

    def _update_buttons_state(self):
        """Update run/stop button states"""
        try:
            run_btn = self.query_one("#run-btn", Button)
            stop_btn = self.query_one("#stop-btn", Button)

            if self.command_running:
                run_btn.disabled = True
                stop_btn.disabled = False
            else:
                run_btn.disabled = False
                stop_btn.disabled = True
        except:
            pass

    def _update_flags_display(self):
        """Update the flags panel to reflect current state"""
        # Update boolean flags
        for flag in self.command_builder.BOOLEAN_FLAGS:
            try:
                checkbox = self.query_one(f"#bool-{flag}", Checkbox)
                checkbox.value = flag in self.command_builder.boolean_flags
            except:
                pass

        # Update value flags buttons
        for flag in self.command_builder.VALUE_FLAGS:
            try:
                button = self.query_one(f"#value-{flag}", Button)
                current_value = self.command_builder.value_flags.get(flag, "")
                if current_value:
                    button.label = f"{flag}: {current_value}"
                else:
                    button.label = f"{flag}: (not set)"
            except:
                pass

        # Update additional configs list
        self._update_additional_config_display()

    def _update_additional_config_display(self):
        """Update the additional configs display"""
        try:
            container = self.query_one("#additional-config-list", Container)
            container.remove_children()

            for key, value in self.command_builder.add_to_config:
                button = Button(
                    f"✗ {key}:{value}", id=f"additional-config-{key}", variant="error"
                )
                container.mount(button)
        except:
            pass

    async def _run_command(self):
        """Execute the mite command with improved async subprocess and real-time streaming"""
        command_list = self.command_builder.get_command_list()
        if not command_list:
            self._append_log(
                "Error: No valid command to run. Please select a journey or scenario."
            )
            return

        self.command_running = True
        self._update_buttons_state()

        # Show detailed start information
        self._append_log(f"[START] Command: {' '.join(command_list)}")
        self._append_log(f"[START] Working Directory: {self.start_dir}")
        self._append_log(f"[START] Timestamp: {asyncio.get_event_loop().time():.2f}")
        self._append_log("=" * 60)

        try:
            # Using asyncio subprocess async handling
            self.process = await asyncio.create_subprocess_exec(
                *command_list,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=self.start_dir,
            )

            # Stream output line by line with real-time updates
            line_count = 0
            while True:
                try:
                    # Read line with timeout to keep UI responsive
                    line = await asyncio.wait_for(
                        self.process.stdout.readline(), timeout=0.1
                    )

                    if not line:
                        # End of stream
                        break

                    decoded_line = line.decode("utf-8", errors="replace").rstrip()
                    if decoded_line:  # Only log non-empty lines
                        line_count += 1
                        timestamp = asyncio.get_event_loop().time()
                        self._append_log(f"[{timestamp:.2f}] {decoded_line}")

                except asyncio.TimeoutError:
                    # No output available, check if process is still running
                    if self.process.returncode is not None:
                        break

                    # Yield control to keep UI responsive
                    await asyncio.sleep(0.01)
                    continue

                except Exception as read_error:
                    self._append_log(f"[ERROR] Failed to read output: {read_error}")
                    break

            # Wait for process completion
            await self.process.wait()

            # Final status
            return_code = self.process.returncode
            self._append_log("=" * 60)
            self._append_log(f"[FINISH] Lines processed: {line_count}")
            self._append_log(f"[FINISH] Exit code: {return_code}")
            self._append_log(f"[FINISH] Timestamp: {asyncio.get_event_loop().time():.2f}")

            if return_code == 0:
                self._append_log("[SUCCESS] Command completed successfully")
            elif return_code == 130:  # Ctrl+C
                self._append_log("[INTERRUPTED] Command was interrupted by user")
            elif return_code == 146:  # Your recent error code
                self._append_log(
                    "[ERROR] Command terminated (possible SIGTERM or timeout)"
                )
            else:
                self._append_log(f"[ERROR] Command failed with exit code {return_code}")

        except asyncio.CancelledError:
            self._append_log("[CANCELLED] Command execution was cancelled")
            if self.process:
                try:
                    self.process.terminate()
                    await asyncio.wait_for(self.process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    self.process.kill()
                    await self.process.wait()

        except Exception as e:
            self._append_log(f"[ERROR] Unexpected error running command: {str(e)}")
            self._append_log(f"[ERROR] Error type: {type(e).__name__}")

        finally:
            self.process = None
            self.command_running = False
            self._update_buttons_state()

    def _append_log(self, text: str):
        """Append text to the log output and auto-scroll to bottom"""
        try:
            log_output = self.query_one("#log-output", Static)
            scroll_container = self.query_one(
                "#log-scroll-container", ScrollableContainer
            )
            current_text = log_output.renderable
            if hasattr(current_text, "plain"):
                current_content = current_text.plain
            else:
                current_content = str(current_text)

            new_content = current_content + "\n" + text
            # Keep only last 200 lines (increased for mite test output)
            lines = new_content.split("\n")
            if len(lines) > 200:
                lines = lines[-200:]

            log_output.update("\n".join(lines))
            # Auto-scroll to bottom
            scroll_container.scroll_end(animate=False)
        except:
            pass

    async def _stop_command(self):
        """Stop the running async command"""
        if self.process and self.process.returncode is None:
            try:
                self._append_log("[STOPPING] Attempting to terminate command...")

                # Try graceful termination first
                self.process.terminate()

                # Wait a bit for graceful shutdown
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=3.0)
                    self._append_log("[STOPPED] Command terminated gracefully")
                except asyncio.TimeoutError:
                    # Force kill if it doesn't terminate gracefully
                    self._append_log("[STOPPING] Force killing command...")
                    self.process.kill()
                    await self.process.wait()
                    self._append_log("[STOPPED] Command force-killed")

            except Exception as e:
                self._append_log(f"[ERROR] Failed to stop command: {e}")

            self.process = None

        self.command_running = False
        self._update_buttons_state()

    async def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Handle boolean flag checkbox changes"""
        if event.checkbox.id and event.checkbox.id.startswith("bool-"):
            flag = event.checkbox.id[5:]  # Remove "bool-" prefix
            self.command_builder.toggle_boolean_flag(flag)
            self._update_command_display()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses for value flags, additional configs, and controls"""
        if event.button.id and event.button.id.startswith("value-"):
            # Value flag button
            flag = event.button.id[6:]  # Remove "value-" prefix
            current_value = self.command_builder.value_flags.get(flag, "")

            result = await self.push_screen(ValueFlagDialog(flag, current_value))
            if result is not None:
                self.command_builder.set_value_flag(flag, result)
                self._update_flags_display()
                self._update_command_display()

        elif event.button.id == "add-config-btn":
            # Add additional config button
            result = await self.push_screen(ConfigDialog())
            if result:
                key, value = result
                self.command_builder.add_additional_config(key, value)
                self._update_flags_display()
                self._update_command_display()

        elif event.button.id and event.button.id.startswith("additional-config-"):
            # Remove additional config button
            key = event.button.id[18:]  # Remove "additional-config-" prefix
            self.command_builder.remove_additional_config(key)
            self._update_flags_display()
            self._update_command_display()

        elif event.button.id == "run-btn":
            # Run command button
            if not self.command_running:
                asyncio.create_task(self._run_command())

        elif event.button.id == "stop-btn":
            # Stop command button
            if self.command_running:
                asyncio.create_task(self._stop_command())

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle tree node selection"""
        node_data = event.node.data
        if node_data and node_data.get("type") in [
            "Journey",
            "Scenario",
            "DataPool",
            "Config",
        ]:
            comp_type = node_data["type"].lower()

            if comp_type in ["journey", "scenario"]:
                self.command_builder.set_test_component(node_data)
            elif comp_type == "datapool":
                self.command_builder.set_datapool(node_data)
            elif comp_type == "config":
                self.command_builder.set_config(node_data)

            self._update_command_display()

    def action_reset(self):
        """Reset all selections"""
        self.command_builder.reset()
        self._update_flags_display()
        self._update_command_display()

        # Clear logs
        log_output = self.query_one("#log-output", Static)
        log_output.update("")


if __name__ == "__main__":
    import sys

    start_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    start_path = Path(start_dir).resolve()

    finder = CheapMiteFinder(start_path)
    tree = finder.discover()
    json_tree = tree.to_dict()

    app = CheapMiteExplorer(json_tree, start_path)
    app.run()
