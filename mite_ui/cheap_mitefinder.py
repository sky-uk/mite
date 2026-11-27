import ast
import asyncio
import sys
import logging
import ctypes
import threading
from pathlib import Path
from typing import Dict, List, Union, Optional
from queue import Queue, Empty
from textual.app import App, ComposeResult
from textual.widgets import Tree, Static, Button, Checkbox, Input, Label
from textual.containers import Container, Vertical, Horizontal, ScrollableContainer
from textual.screen import ModalScreen

from mite.__main__ import main

class MiteExecutor:
    """Backend executor that runs mite in a dedicated worker thread and streams logs."""
    def __init__(self):
        self.thread: Optional[threading.Thread] = None
        self.log_callback = None
        self._stop_event = threading.Event()
        self._thread_ident = None

    def set_log_callback(self, cb):
        self.log_callback = cb

    def _write_log(self, text: str):
        if self.log_callback:
            try:
                self.log_callback(text)
            except Exception:
                pass

    def start(self, command_list, start_dir: Path):
        if self.thread and self.thread.is_alive():
            self._write_log("[WARNING] Execution already in progress")
            return

        def run():
            import os, gc
            # Prevent uvloop policy installation inside worker
            orig_profile = os.environ.get("MITE_PROFILE")
            os.environ["MITE_PROFILE"] = "1"
            # Force default asyncio policy in worker to prevent uvloop's no-thread-safe issues
            try:
                asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
            except Exception:
                pass
            # Create dedicated asyncio loop in worker
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            # Monkey-patch call_soon to fall back to thread-safe scheduling if invoked cross-thread
            try:
                orig_call_soon = loop.call_soon
                def _safe_call_soon(*args, **kwargs):
                    try:
                        return orig_call_soon(*args, **kwargs)
                    except RuntimeError as re:
                        if "Non-thread-safe operation" in str(re):
                            return loop.call_soon_threadsafe(*args, **kwargs)
                        raise
                loop.call_soon = _safe_call_soon
            except Exception:
                pass
            try:
                # Prepare argv and working dir
                original_argv = sys.argv.copy()
                original_stdout = sys.stdout
                original_stderr = sys.stderr
                original_cwd = Path.cwd()
                os.chdir(start_dir)
                sys.argv = command_list

                # Attach logging handler to stream logs without modifying sys.stdout/stderr
                class CallbackLogHandler(logging.Handler):
                    def __init__(self, writer):
                        super().__init__()
                        self.writer = writer
                    def emit(self, record):
                        try:
                            msg = self.format(record)
                            self.writer(msg)
                        except Exception:
                            pass
                handler = CallbackLogHandler(self._write_log)
                handler.setLevel(logging.INFO)
                handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s'))
                root_logger = logging.getLogger()
                mite_logger = logging.getLogger('mite')
                orig_root_level = root_logger.level
                orig_root_handlers = root_logger.handlers.copy()
                orig_mite_level = mite_logger.level
                orig_mite_handlers = mite_logger.handlers.copy()
                root_logger.setLevel(logging.INFO)
                root_logger.addHandler(handler)
                mite_logger.setLevel(logging.INFO)
                mite_logger.addHandler(handler)

                # Run mite main
                self._write_log("[INFO] Starting mite execution")
                main()

            except KeyboardInterrupt:
                self._write_log("[INTERRUPTED] Received interrupt signal")
            except SystemExit as e:
                code = e.code if e.code is not None else 0
                if code:
                    self._write_log(f"[EXIT] Exit code: {code}")
            except Exception as e:
                import traceback
                self._write_log(f"[ERROR] Worker exception: {e}")
                self._write_log(traceback.format_exc())
            finally:
                # Restore argv and remove logging handler
                sys.argv = original_argv
                os.chdir(original_cwd)
                try:
                    root_logger.removeHandler(handler)
                    mite_logger.removeHandler(handler)
                    root_logger.setLevel(orig_root_level)
                    root_logger.handlers = orig_root_handlers
                    mite_logger.setLevel(orig_mite_level)
                    mite_logger.handlers = orig_mite_handlers
                except Exception:
                    pass
                # Finalize resources in worker
                try:
                    gc.collect()
                except Exception:
                    pass
                # Attempt to proactively finalize acurl sessions in worker thread
                try:
                    import acurl
                    # Common patterns: close default loop resources if available
                    for name in ("shutdown", "close", "finalize"):
                        fn = getattr(acurl, name, None)
                        if callable(fn):
                            try:
                                fn()
                            except Exception:
                                pass
                except Exception:
                    pass
                try:
                    loop.close()
                except Exception:
                    pass
                # Restore env
                if orig_profile is None:
                    try:
                        del os.environ["MITE_PROFILE"]
                    except Exception:
                        pass
                else:
                    os.environ["MITE_PROFILE"] = orig_profile

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()
        self._thread_ident = self.thread.ident

    def stop(self):
        if not self.thread or not self.thread.is_alive():
            self._write_log("[INFO] No execution in progress")
            return
        try:
            # Inject KeyboardInterrupt into worker thread
            tid = self._thread_ident
            if tid:
                res = ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_long(tid), ctypes.py_object(KeyboardInterrupt))
                if res == 0:
                    self._write_log("[ERROR] Invalid thread ID for stop")
                elif res > 1:
                    ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_long(tid), None)
                    self._write_log("[ERROR] Failed to raise KeyboardInterrupt cleanly")
                else:
                    self._write_log("[STOPPING] Interrupt signal sent to worker")
            # Wait up to 3s for thread to end
            import time
            for _ in range(30):
                if not self.thread.is_alive():
                    self._write_log("[CANCELLED] Command stopped successfully")
                    break
                time.sleep(0.1)
            if self.thread and self.thread.is_alive():
                self._write_log("[WARNING] Worker did not stop gracefully")
        except Exception as e:
            import traceback
            self._write_log(f"[ERROR] Stop failed: {e}")
            self._write_log(traceback.format_exc())


class Node:
    def __init__(self, name: str, path: Path, parent: 'Node' = None):
        self.name = name
        self.path = path
        self.parent = parent
        self.children: List['Node'] = []

    def add_child(self, node: 'Node'):
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

class Root(Node): pass
class Directory(Node): pass
class Module(Node): pass
class Journey(Node): pass
class Scenario(Node): pass
class DataPool(Node): pass
class Config(Node): pass

class BuildTestCommand:
    """Class to build mite test commands from selected components"""
    
    # Fixed additional flags that don't take values (many other flags remaining tba from mite.__main__)
    BOOLEAN_FLAGS = [
        "--debugging",
        "--hide-constant-logs", 
        "--report",
        "--journey-logging",
    ]
    
    # Flags that take values (other flags tba from mite.__main__)
    VALUE_FLAGS = [
        "--spawn-rate",
        "--message-socket",
        "--log-level",
    ]
    
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
        comp_type = component.get('type', '').lower()
        
        if comp_type == 'journey':
            self.test_type = 'journey'
            self.journey_or_scenario = component
        elif comp_type == 'scenario':
            self.test_type = 'scenario'
            self.journey_or_scenario = component
            # If scenario is selected, ignore any previously selected datapool
            self.datapool = None
    
    def set_datapool(self, component: Dict):
        """Set datapool component (only valid for journey tests)"""
        if self.test_type == 'journey':
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
        """Convert file path to module notation using relative path"""
        path = Path(file_path)
        # Get path relative to start_dir
        try:
            relative_path = path.relative_to(self.start_dir)
            # Convert to module notation
            module_path = str(relative_path.with_suffix('')).replace('/', '.')
        except ValueError:
            # If path is not relative to start_dir, use absolute path
            module_path = str(path.with_suffix('')).replace('/', '.')
        print(f"Converting {file_path} to module notation: {module_path}")
        return module_path
    
    def build_command(self) -> str:
        """Build the complete mite test command"""
        if not self.test_type or not self.journey_or_scenario:
            return "# Select a journey or scenario to build command"
        
        parts = ["mite", self.test_type, "test"]
        
        # Add main component (journey or scenario)
        main_path = self._path_to_module_notation(self.journey_or_scenario['path'])
        main_name = self.journey_or_scenario['name']
        parts.append(f"{main_path}:{main_name}")
        
        # Add datapool if present (only for journey tests)
        if self.test_type == 'journey' and self.datapool:
            datapool_path = self._path_to_module_notation(self.datapool['path'])
            datapool_name = self.datapool['name']
            parts.append(f"{datapool_path}:{datapool_name}")
        
        # Add config if present
        if self.config:
            config_path = self._path_to_module_notation(self.config['path'])
            config_name = self.config['name']
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
        print(f"parts: {parts}")
        return " ".join(parts)
    
    def get_command_list(self) -> List[str]:
        """Get the command as a list for subprocess execution"""
        command_str = self.build_command()
        if command_str.startswith("#"):
            return []
        return command_str.split()
    
    def get_working_directory_info(self) -> str:
        """Get the working directory info line"""
        return f"Run from: {self.start_dir}"
    
    def get_status_summary(self) -> str:
        """Get a summary of current selections"""
        lines = []
        
        if self.test_type and self.journey_or_scenario:
            lines.append(f"Test: {self.test_type} ({self.journey_or_scenario['name']})")
        
        if self.test_type == 'journey' and self.datapool:
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
            yield Input(value=self.current_value, placeholder="Enter value...", id="value-input")
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
                if (isinstance(decorator.func, ast.Name) and 
                    decorator.func.id == 'mite_ui_wrapper' and 
                    decorator.args):
                    
                    # Get the first argument (the type string)
                    first_arg = decorator.args[0]
                    if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                        return first_arg.value
                    elif isinstance(first_arg, ast.Str):  # For older Python versions
                        return first_arg.s
            
            # Handle @mite_ui_wrapper.type_name if using attribute access
            elif isinstance(decorator, ast.Attribute):
                if (isinstance(decorator.value, ast.Name) and 
                    decorator.value.id == 'mite_ui_wrapper'):
                    return decorator.attr
        
        return None

    def _get_mite_variables_from_assignments(self, tree) -> List[tuple]:
        """Find mite_ui_wrapper attribute calls in assignments"""
        variables = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                # Check if assignment uses mite_ui_wrapper.type(value)
                if (isinstance(node.value, ast.Call) and
                    isinstance(node.value.func, ast.Attribute) and
                    isinstance(node.value.func.value, ast.Name) and
                    node.value.func.value.id == 'mite_ui_wrapper'):
                    
                    # Get the component type from attribute name
                    component_type = node.value.func.attr
                    
                    # Get the variable name from assignment target
                    if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                        var_name = node.targets[0].id
                        variables.append((var_name, component_type))
        
        return variables

    def _add_node_by_type(self, found: List[Node], mite_type: str, name: str, file_path: Path, parent: Module):
        """Helper to add nodes based on type"""
        if mite_type == 'journey':
            found.append(Journey(name=name, path=file_path, parent=parent))
        elif mite_type == 'scenario':
            found.append(Scenario(name=name, path=file_path, parent=parent))
        elif mite_type == 'datapool':
            found.append(DataPool(name=name, path=file_path, parent=parent))
        elif mite_type == 'config':
            found.append(Config(name=name, path=file_path, parent=parent))

    def _filter_tree(self, node: Node):
        """Filter out nodes that don't have relevant content"""
        children_to_remove = []
        for child in node.children:
            if not child.has_relevant_content():
                children_to_remove.append(child)
            else:
                self._filter_tree(child)
        
        for child in children_to_remove:
            node.children.remove(child)

    def filter_tree(self, node: Node):
        """Remove children that don't have relevant content"""
        node.children = [child for child in node.children if child.has_relevant_content()]
        for child in node.children:
            self._filter_tree(child)

class MiteUi(App):
    TITLE = "Mite Test Command Builder"
    
    def __init__(self, json_tree: Dict, start_dir: Path):
        super().__init__()
        self.json_tree = json_tree
        self.command_builder = BuildTestCommand(start_dir)
        self.start_dir = start_dir
        self.command_running = False
        self.current_task: Optional[asyncio.Task] = None
        # self.mite_task: Optional[asyncio.Task] = None
        self.stop_requested = False
        
        # Real-time log streaming
        self.log_buffer = []
        self.log_update_task: Optional[asyncio.Task] = None
        # Backend executor
        self.executor = MiteExecutor()
        # Persist selections/session
        self._session_file = Path(".mite_ui_session.json")
        # Logging helpers
        self.log_queue: Queue = Queue()
        self.log_poll_task: Optional[asyncio.Task] = None
        self.mite_thread: Optional[threading.Thread] = None

    async def _run_mite_async(self, command_list):
        """Run mite command using main() function directly"""
        try:
            # Extract log level from command arguments, default to INFO
            log_level = self._extract_log_level_from_command(command_list)
            self._setup_real_time_logging(log_level)
            
            self._append_log_real_time(f"[START] Command: {' '.join(command_list)}")
            self._append_log_real_time(f"[START] Working Directory: {self.start_dir}")
            self._append_log_real_time("=" * 60)
            
            # Save original state
            original_argv = sys.argv.copy()
            original_stdout = sys.stdout
            original_stderr = sys.stderr
            original_cwd = Path.cwd()
            
            def run_mite_in_thread():
                """Target function for the thread running mite"""
                try:
                    import os, gc
                    # Ensure this worker thread does NOT use uvloop
                    _orig_mite_profile = os.environ.get("MITE_PROFILE")
                    os.environ["MITE_PROFILE"] = "1"

                    # Create and set a plain asyncio event loop for this worker thread
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    # Monkey-patch call_soon to fall back to thread-safe scheduling if invoked cross-thread
                    try:
                        orig_call_soon = loop.call_soon
                        def _safe_call_soon(*args, **kwargs):
                            try:
                                return orig_call_soon(*args, **kwargs)
                            except RuntimeError as re:
                                if "Non-thread-safe operation" in str(re):
                                    return loop.call_soon_threadsafe(*args, **kwargs)
                                raise
                        loop.call_soon = _safe_call_soon
                    except Exception:
                        pass

                    # Change to the start directory
                    os.chdir(self.start_dir)

                    # Set up the command arguments for mite's main()
                    sys.argv = command_list

                    # Redirect stdout and stderr to capture print statements
                    sys.stdout = self._create_stream_redirector("[STDOUT]")
                    sys.stderr = self._create_stream_redirector("[STDERR]")

                    # Run main() - this blocks until complete or interrupted
                    main()

                except KeyboardInterrupt:
                    # Mite was interrupted gracefully
                    self._append_log_real_time("[INTERRUPTED] Received interrupt signal")
                except SystemExit as e:
                    # Mite called sys.exit()
                    exit_code = e.code if e.code is not None else 0
                    if exit_code != 0:
                        self._append_log_real_time(f"[EXIT] Exit code: {exit_code}")
                except Exception as e:
                    self._append_log_real_time(f"[ERROR] Thread exception: {e}")
                    import traceback
                    self._append_log_real_time(traceback.format_exc())
                finally:
                    sys.stdout = original_stdout
                    sys.stderr = original_stderr
                    sys.argv = original_argv
                    os.chdir(original_cwd)
                    # Force finalizers to run in this worker thread
                    try:
                        gc.collect()
                    except Exception:
                        pass
                    # Restore MITE_PROFILE env var
                    try:
                        if _orig_mite_profile is None:
                            del os.environ["MITE_PROFILE"]
                        else:
                            os.environ["MITE_PROFILE"] = _orig_mite_profile
                    except Exception:
                        pass
                    # Close the worker thread event loop if present
                    try:
                        loop.close()
                    except Exception:
                        pass
            
            # Create and start the thread
            self.mite_thread = threading.Thread(target=run_mite_in_thread, daemon=True)
            self.mite_thread.start()
            
            # Wait for thread to complete in a non-blocking way
            while self.mite_thread.is_alive():
                await asyncio.sleep(0.1)
            
            self._append_log_real_time("=" * 60)
            self._append_log_real_time("[SUCCESS] Command completed")
            return 0
                
        except asyncio.CancelledError:
            # User clicked Stop - interrupt the mite thread
            self._append_log_real_time("[STOPPING] Interrupting command execution...")
            
            if self.mite_thread and self.mite_thread.is_alive():
                try:
                    # Raise KeyboardInterrupt in the mite thread
                    thread_id = self.mite_thread.ident
                    if thread_id:
                        exc = ctypes.py_object(KeyboardInterrupt)
                        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
                            ctypes.c_long(thread_id), exc
                        )
                        
                        if res == 0:
                            self._append_log_real_time("[ERROR] Invalid thread ID")
                        elif res > 1:
                            # Call again with NULL to revert if multiple threads affected
                            ctypes.pythonapi.PyThreadState_SetAsyncExc(
                                ctypes.c_long(thread_id), None
                            )
                            self._append_log_real_time("[ERROR] Exception raise failed")
                        else:
                            self._append_log_real_time("[STOPPING] Interrupt signal sent to thread")
                            
                            # Wait for thread to finish (with timeout)
                            for _ in range(30):  # Wait up to 3 seconds
                                if not self.mite_thread.is_alive():
                                    break
                                await asyncio.sleep(0.1)
                            
                            if self.mite_thread.is_alive():
                                self._append_log_real_time("[WARNING] Thread did not stop gracefully (continuing in background)")
                            else:
                                self._append_log_real_time("[CANCELLED] Command stopped successfully")
                except Exception as e:
                    self._append_log_real_time(f"[ERROR] Failed to stop thread: {e}")
                    import traceback
                    self._append_log_real_time(traceback.format_exc())
            
            return 130
        except SystemExit as e:
            # mite's main() calls sys.exit(), capture the exit code
            exit_code = e.code if e.code is not None else 0
            if exit_code == 0:
                self._append_log_real_time("[SUCCESS] Command completed")
            else:
                self._append_log_real_time(f"[ERROR] Command failed with exit code {exit_code}")
            return exit_code
        except Exception as e:
            self._append_log_real_time(f"[ERROR] {e}")
            import traceback
            self._append_log_real_time(traceback.format_exc())
            return 1
        finally:
            self.mite_thread = None
            self._cleanup_real_time_logging()
    
    def _create_stream_redirector(self, prefix=""):
        """Captures output to UI log (thread-safe via queue)"""
        log_queue = self.log_queue
        
        class StreamRedirector:
            def __init__(self, log_queue, prefix):
                self.log_queue = log_queue
                self.prefix = prefix
                self.buffer = ""
            
            def write(self, text):
                if text and text != "\n":
                    # Buffer the text and split by newlines
                    self.buffer += text
                    while "\n" in self.buffer:
                        line, self.buffer = self.buffer.split("\n", 1)
                        if line.strip():  # Only log non-empty lines
                            msg = f"{self.prefix} {line}" if self.prefix else line
                            # Simply put in queue - no event loop calls
                            self.log_queue.put(msg)
                return len(text)
            
            def flush(self):
                # Flush any remaining buffer content
                if self.buffer.strip():
                    msg = f"{self.prefix} {self.buffer}" if self.prefix else self.buffer
                    self.log_queue.put(msg)
                    self.buffer = ""
        
        return StreamRedirector(log_queue, prefix)
    
    def _extract_log_level_from_command(self, command_list):
        """Extract log level from command arguments, default to INFO"""
        log_level_str = "INFO"
        
        # Look for --log-level=VALUE or --log-level VALUE patterns
        for i, arg in enumerate(command_list):
            if arg.startswith("--log-level="):
                log_level_str = arg.split("=", 1)[1]
                break
            elif arg == "--log-level" and i + 1 < len(command_list):
                log_level_str = command_list[i + 1]
                break
        
        # Convert string to logging level
        return getattr(logging, log_level_str.upper(), logging.INFO)
    
    def _append_log_real_time(self, text: str):
        """Append log from worker thread safely using Textual's thread-safe API."""
        try:
            # Schedule UI update on Textual's main thread
            self.call_from_thread(lambda: self._append_log(text))
        except Exception:
            # Fallback to queue if call_from_thread isn't available yet
            try:
                self.log_queue.put(text)
            except Exception:
                pass
    
    async def _update_log_display(self):
        """Update UI with buffered logs"""
        await asyncio.sleep(0.01)
        if self.log_buffer:
            for text in self.log_buffer:
                self._append_log(text)
            self.log_buffer.clear()



    def _setup_real_time_logging(self, log_level=logging.INFO):
        """Set up real-time logging with specified log level"""
        class RealTimeHandler(logging.Handler):
            def __init__(self, ui: "MiteUi"):
                super().__init__()
                self.ui = ui
            
            def emit(self, record):
                try:
                    msg = self.format(record)
                    # Use Textual's thread-safe bridge to main thread
                    self.ui.call_from_thread(lambda: self.ui._append_log(msg))
                except Exception:
                    # Fallback: queue put if call_from_thread not ready
                    try:
                        self.ui.log_queue.put(self.format(record))
                    except Exception:
                        self.handleError(record)
        
        # Use Textual's thread-safe bridge
        self.rt_handler = RealTimeHandler(self)
        self.rt_handler.setLevel(log_level)
        formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
        self.rt_handler.setFormatter(formatter)
        
        root_logger = logging.getLogger()
        self.orig_level = root_logger.level
        self.orig_handlers = root_logger.handlers.copy()
        root_logger.setLevel(log_level)
        root_logger.addHandler(self.rt_handler)
        
        mite_logger = logging.getLogger('mite')
        mite_logger.setLevel(log_level)
        mite_logger.addHandler(self.rt_handler)

    def _cleanup_real_time_logging(self):
        """Cleanup logging"""
        if hasattr(self, 'rt_handler'):
            root_logger = logging.getLogger()
            root_logger.removeHandler(self.rt_handler)
            root_logger.setLevel(self.orig_level)
            root_logger.handlers = self.orig_handlers
            
            mite_logger = logging.getLogger('mite')
            if self.rt_handler in mite_logger.handlers:
                mite_logger.removeHandler(self.rt_handler)

    
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
    
    #command-scroll-container {
        height: 5;
        background: $surface-lighten-1;
        border: solid $accent;
        scrollbar-size: 1 1;
        overflow-x: auto;
        overflow-y: hidden;
    }
    
    #control-buttons-row {
        height: 3;
        background: $surface-lighten-1;
        padding: 0 1;
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
    
    #command-display {
        width: auto;
        min-width: 100%;
        height: auto;
        padding: 1;
        background: $surface-lighten-1;
        color: $text;
    }
    
    #copy-btn {
        width: 12;
        height: 3;
        margin: 0 1;
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
                            yield Button(f"{flag}: (not set)", id=f"value-{flag}", classes="flag-button")
                    
                    # additional configs section
                    with Container(classes="flag-section"):
                        yield Label("[bold]Additional Configs[/bold]")
                        yield Button("+ Add Additional Config", id="add-config-btn", variant="success")
                        yield Container(id="additional-config-list")
                
                # Right panel - File explorer  
                with Container(id="right-panel"):
                    yield Tree(self.json_tree["name"], data=self.json_tree, id="file-tree")
            
            # Footer - Command display and execution
            with Vertical(id="footer-container"):
                # Command display area
                with ScrollableContainer(id="command-scroll-container"):
                    yield Static(self._get_command_string(), id="command-display")
                
                # Control buttons row
                with Horizontal(id="control-buttons-row"):
                    yield Button("Copy", variant="primary", id="copy-btn")
                    yield Button("Copy Logs", variant="primary", id="copy-logs-btn")
                    yield Button("Clear Logs", variant="primary", id="clear-logs-btn")
                    yield Button("Selection Mode", variant="primary", id="selection-mode-btn")
                    yield Button("Run", variant="success", id="run-btn", classes="control-button")
                    yield Button("Stop", variant="error", id="stop-btn", classes="control-button")
                
                # Log output area
                with ScrollableContainer(id="log-scroll-container"):
                    yield Static("Ready to execute commands...", id="log-output")

    def _build_command_text(self) -> str:
        """Build just the command text for display"""
        command = self.command_builder.build_command()
        return f"[bold]Command:[/bold] {command}"
    
    def _get_command_string(self) -> str:
        """Get command string without markup for Input widget"""
        command = self.command_builder.build_command()
        working_dir = self.command_builder.get_working_directory_info()
        return f"{working_dir}\n{command}"

    def on_mount(self):
        tree: Tree = self.query_one("#file-tree")
        self._populate_tree(tree.root, self.json_tree)
        tree.root.expand()
        self._update_flags_display()
        self._update_buttons_state()
        # Wire executor log to UI
        self.executor.set_log_callback(lambda text: self.call_from_thread(lambda: self._append_log(text)))
        # Load previous session
        self._load_session()

    def _populate_tree(self, node, data: Dict):
        for child in data.get("children", []):
            child_type = child['type']
            if child_type in ['Journey', 'Scenario', 'DataPool', 'Config']:
                label = f"[bold]{child['name']}[/bold] ({child_type})"
            else:
                label = f"[bold]{child['name']}[/] ({child_type})"
            
            new_node = node.add(label, data=child)
            
            if child_type not in ['Journey', 'Scenario', 'DataPool', 'Config']:
                self._populate_tree(new_node, child)

    def _update_command_display(self):
        """Update the command display"""
        command_display = self.query_one("#command-display", Static)
        command_display.update(self._get_command_string())

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
                button = Button(f"✗ {key}:{value}", id=f"additional-config-{key}", variant="error")
                container.mount(button)
        except:
            pass

    async def _poll_log_queue(self):
        """Poll log queue and append messages to UI"""
        while True:
            try:
                await asyncio.sleep(0.05)  # Check every 50ms
                messages = []
                # Drain all available messages
                while not self.log_queue.empty():
                    try:
                        msg = self.log_queue.get_nowait()
                        messages.append(msg)
                    except Empty:
                        break
                
                # Append all messages at once (this is already in main thread via await)
                for msg in messages:
                    self._append_log(msg)
                    
            except asyncio.CancelledError:
                break
            except Exception:
                pass

    async def _run_command(self):
        """Execute the mite command using async approach"""
        try:
            command_list = self.command_builder.get_command_list()
            print(f"command list is {command_list}")
            if not command_list:
                self._append_log("Error: No valid command to run. Please select a journey or scenario.")
                return

            self.command_running = True
            self.stop_requested = False
            self._update_buttons_state()
            
            # Start execution via backend (no queue poller needed when using call_from_thread)
            self.executor.start(command_list, self.start_dir)
            # Save session
            self._save_session()
            
            # Wait until worker finishes
            while self.executor.thread and self.executor.thread.is_alive():
                await asyncio.sleep(0.1)
            
            # Wait a bit for any remaining logs
            await asyncio.sleep(0.2)

        except asyncio.CancelledError:
            self._append_log("[CANCELLED] Command execution was cancelled")
        except Exception as e:
            import traceback
            self._append_log(f"[ERROR] Unexpected error: {str(e)}")
            self._append_log(f"[TRACEBACK] {traceback.format_exc()}")
        
        finally:
            self.command_running = False
            
            # Drain any remaining messages in queue
            while not self.log_queue.empty():
                try:
                    msg = self.log_queue.get_nowait()
                    self._append_log(msg)
                except Empty:
                    break
            
            self.current_task = None
            self._update_buttons_state()


    def _append_log(self, text: str):
        """Append text to the log output and auto-scroll to bottom"""
        try:
            log_output = self.query_one("#log-output", Static)
            scroll_container = self.query_one("#log-scroll-container", ScrollableContainer)
            current_text = log_output.renderable
            if hasattr(current_text, 'plain'):
                current_content = current_text.plain
            else:
                current_content = str(current_text)
            
            new_content = current_content + "\n" + text
            # Keep only last 200 lines (increased for mite test output)
            lines = new_content.split('\n')
            if len(lines) > 200:
                lines = lines[-200:]
            
            log_output.update('\n'.join(lines))
            # Auto-scroll to bottom
            scroll_container.scroll_end(animate=False)
        except:
            pass

    def _stop_command(self):
        """Stop the running command"""
        if self.command_running:
            try:
                self._append_log("[STOPPING] Stop requested...")
                self.stop_requested = True
                # Stop backend executor
                self.executor.stop()
                    
            except Exception as e:
                self._append_log(f"[ERROR] Failed to stop command: {e}")

    async def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Handle boolean flag checkbox changes"""
        if event.checkbox.id and event.checkbox.id.startswith("bool-"):
            flag = event.checkbox.id[5:]  # Remove "bool-" prefix
            self.command_builder.toggle_boolean_flag(flag)
            self._update_command_display()

    def action_quit(self) -> None:
        """Override quit action to ensure clean shutdown"""
        import sys
        print("[INFO] action_quit called", file=sys.stderr)
        # Stop any running command first
        if self.command_running:
            print("[INFO] Command running, stopping...", file=sys.stderr)
            self._stop_command()
        # Force exit immediately - don't wait for cleanup
        print("[INFO] Calling exit()", file=sys.stderr)
        self.exit()
    
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
                try:
                    # Create task to run command
                    self.current_task = asyncio.create_task(self._run_command())
                except Exception as e:
                    # Log any error that occurs during task creation
                    import sys
                    import traceback
                    print(f"[ERROR] Failed to start command: {e}", file=sys.stderr)
                    traceback.print_exc()
                    try:
                        self._append_log(f"[ERROR] Failed to start command: {e}")
                        self._append_log(f"[TRACEBACK] {traceback.format_exc()}")
                    except:
                        pass
        
        elif event.button.id == "stop-btn":
            # Stop command button
            if self.command_running:
                self._stop_command()
        
        elif event.button.id == "copy-btn":
            # Copy command button
            command_static = self.query_one("#command-display", Static)
            command_text = str(command_static.renderable)
            if command_text and not command_text.startswith("#"):
                # Use pyperclip for clipboard operations
                try:
                    import pyperclip
                    pyperclip.copy(command_text)
                    self._append_log("[INFO] Command copied to clipboard")
                except ImportError:
                    # Fallback: just log the command
                    self._append_log(f"[INFO] Command: {command_text}")
                    self._append_log("[INFO] Install pyperclip for clipboard support: pip install pyperclip")

        elif event.button.id == "clear-logs-btn":
            # Clear logs button
            try:
                log_output = self.query_one("#log-output", Static)
                log_output.update("")
                self._append_log("[INFO] Logs cleared")
            except Exception:
                pass

        elif event.button.id == "selection-mode-btn":
            # Toggle selection mode (release mouse capture to allow terminal selection)
            try:
                # Textual may offer screen.capture_mouse; here we toggle a CSS class to avoid interference
                # Fallback: just log the hint
                self._append_log("[INFO] Tip: Hold ALT/OPTION to select text in some terminals")
            except Exception:
                pass

        elif event.button.id == "copy-logs-btn":
            # Copy logs button
            try:
                log_output = self.query_one("#log-output", Static)
                # Extract plain text from Static renderable
                renderable = getattr(log_output, "renderable", "")
                text = ""
                try:
                    # textual may wrap in Rich Text; convert to string
                    text = str(renderable)
                except Exception:
                    text = ""
                if not text:
                    text = ""
                import pyperclip
                pyperclip.copy(text)
                self._append_log("[INFO] Logs copied to clipboard")
            except ImportError:
                self._append_log("[INFO] Install pyperclip to copy logs: pip install pyperclip")
            except Exception as e:
                self._append_log(f"[ERROR] Failed to copy logs: {e}")

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle tree node selection"""
        node_data = event.node.data
        if node_data and node_data.get('type') in ['Journey', 'Scenario', 'DataPool', 'Config']:
            comp_type = node_data['type'].lower()
            
            if comp_type in ['journey', 'scenario']:
                self.command_builder.set_test_component(node_data)
            elif comp_type == 'datapool':
                self.command_builder.set_datapool(node_data)
            elif comp_type == 'config':
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

    def _save_session(self):
        """Persist current selections to a local JSON file."""
        try:
            data = {
                "test_type": self.command_builder.test_type,
                "journey_or_scenario": self.command_builder.journey_or_scenario,
                "datapool": self.command_builder.datapool,
                "config": self.command_builder.config,
                "boolean_flags": self.command_builder.boolean_flags,
                "value_flags": self.command_builder.value_flags,
                "add_to_config": self.command_builder.add_to_config,
                "start_dir": str(self.start_dir),
            }
            import json
            self._session_file.write_text(json.dumps(data), encoding="utf-8")
            self._append_log("[INFO] Session saved")
        except Exception:
            pass

    def _load_session(self):
        """Load previous selections from local JSON file if present."""
        try:
            if self._session_file.exists():
                import json
                data = json.loads(self._session_file.read_text(encoding="utf-8"))
                self.command_builder.test_type = data.get("test_type")
                self.command_builder.journey_or_scenario = data.get("journey_or_scenario")
                self.command_builder.datapool = data.get("datapool")
                self.command_builder.config = data.get("config")
                self.command_builder.boolean_flags = data.get("boolean_flags", [])
                self.command_builder.value_flags = data.get("value_flags", {})
                self.command_builder.add_to_config = data.get("add_to_config", [])
                sd = data.get("start_dir")
                if sd:
                    try:
                        self.start_dir = Path(sd)
                    except Exception:
                        pass
                self._update_flags_display()
                self._update_command_display()
                self._append_log("[INFO] Session restored")
        except Exception:
            pass

def mite_ui(opts):
    import sys
    import os
    # Disable uvloop globally for the UI run to avoid cross-thread assertions
    # This affects only the UI process and not the regular CLI usage.
    try:
        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
        # Also guard against mite.__main__ enabling uvloop in nested calls
        os.environ.setdefault("MITE_PROFILE", "1")
    except Exception:
        pass
    start_dir = opts["TEST_LOC_ROOT_PATH"]
    start_path = Path(start_dir).resolve()

    finder = CheapMiteFinder(start_path)
    tree = finder.discover()
    json_tree = tree.to_dict()

    app = MiteUi(json_tree, start_path)
    app.run()