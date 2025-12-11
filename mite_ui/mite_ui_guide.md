# Mite UI Technical Guide

This document explains the architecture and flow of the Mite UI implementation, covering all major classes, functions, and the threading/async model. Use it to onboard engineers and to plan further feature development.

## Overview

- Purpose: Provide a Textual-based UI to discover test components (journeys, scenarios, configs, datapools), build a `mite` command, run it, stream logs in real time, and allow stopping execution cleanly.
- Key modules:
  - `mite_ui/cheap_mitefinder.py`: Main UI and backend executor.
  - `mite_ui/run_debug_scenario.py`: Headless runner for debug scenarios using the same backend.
  - `mite/__main__.py`: Mite CLI entry and `main()` used by the executor.

## Usage

`mite ui <root path to test>`

## Classes and Responsibilities

- `Node` (and subclasses `Root`, `Directory`, `Module`, `Journey`, `Scenario`, `DataPool`, `Config`)
  - Role: Represent a hierarchical tree of files and discovered mite components.
  - Key methods:
    - `add_child(node)`: Add a child node.
    - `has_relevant_content()`: Detect if this node or children contain one of the leaf component types.
    - `to_dict()`: Convert to a serializable dictionary for UI tree consumption.

- `CheapMiteFinder`
  - Role: Scan the filesystem under a `start_path`, parse Python modules via AST, and discover mite-decorated components.
  - Key methods:
    - `discover()`: Walk files/dirs, filter, and return the root `Node` containing all discovered components.
    - `_walk(path, parent_node)`: Recursively build node hierarchy; parse `.py` files.
    - `_inspect_file(file_path, parent)`: AST parse to find decorated functions and variable assignments using `mite_ui_wrapper`.
    - `_get_mite_type_from_decorators(decorator_list)`: Extract component type from decorators.
    - `_get_mite_variables_from_assignments(tree)`: Detect `mite_ui_wrapper.<type>(value)` assignments.
    - `_add_node_by_type(...)`: Create appropriate leaf node based on type.
    - `_filter_tree(node)`: Remove branches without relevant content.

- `BuildTestCommand`
  - Role: Maintain UI selections and build the final `mite` command string/list.
  - State:
    - `test_type`: `'journey'` or `'scenario'`.
    - `journey_or_scenario`, `datapool`, `config`: Selected components.
    - `boolean_flags`: Flags like `--debugging`, etc.
    - `value_flags`: Flags with values (e.g., `--log-level=INFO`).
    - `add_to_config`: Additional config overrides.
    - `start_dir`: Root folder; used to compute module paths.
  - Key methods:
    - `reset()`: Clear all selections.
    - `set_test_component(component)`: Choose journey or scenario.
    - `set_datapool(component)`, `set_config(component)`: Choose optional components.
    - `toggle_boolean_flag(flag)`, `set_value_flag(flag, value)`: Manage flags.
    - `add_additional_config(key, value)`, `remove_additional_config(key)`: Manage config overrides.
    - `_path_to_module_notation(file_path)`: Convert a file path to dotted module notation relative to `start_dir`.
    - `build_command()`: Return a `mite ...` command string.
    - `get_command_list()`: Return the command split into args.
    - `get_working_directory_info()`: Display “Run from: …”.
    - `get_status_summary()`: Concise summary of current selections.

- `ValueFlagDialog` (Textual `ModalScreen[str]`)
  - Role: Prompt for a value flag input.
  - Flow:
    - Compose inputs/buttons.
    - `on_button_pressed`: Dismiss with the entered value, clear, or cancel.

- `ConfigDialog` (Textual `ModalScreen[tuple]`)
  - Role: Prompt for key/value to add to config overrides.
  - Flow:
    - Compose inputs/buttons.
    - `on_button_pressed`: Dismiss with `(key, value)` or cancel.

- `MiteExecutor`
  - Role: Backend runner that executes `mite.__main__.main()` within a dedicated worker thread, streaming logs to the UI.
  - State:
    - `thread`: Worker `threading.Thread` handle.
    - `log_callback`: Function to emit log messages to the UI.
    - `_thread_ident`: Cached thread ID for stop.
  - Key methods:
    - `set_log_callback(cb)`: Register a callback (UI uses `call_from_thread` to append logs safely).
    - `start(command_list, start_dir)`: Spawn worker thread; set `MITE_PROFILE=1` to prevent uvloop; set default event loop policy; create a new event loop; monkey-patch `loop.call_soon` to fallback to `call_soon_threadsafe` when a cross-thread call is detected; attach a logging handler to forward logs via `log_callback`; set `sys.argv` to the command; `os.chdir(start_dir)`; call `main()`.
    - `stop()`: Inject `KeyboardInterrupt` into the worker thread via `PyThreadState_SetAsyncExc`; wait briefly for termination.
    - Internal logging handler: `CallbackLogHandler(logging.Handler)` forwards formatted log records to `log_callback`.
    - Cleanup: Restore `argv`/cwd; remove logging handlers; `gc.collect()`; best-effort acurl cleanup (`shutdown/close/finalize` if present); `loop.close()`; restore env.

- `MiteUi` (Textual `App`)
  - Role: Main application UI.
  - State:
    - `json_tree`: Dict representation of discovered components.
    - `command_builder`: Instance of `BuildTestCommand`.
    - `start_dir`, `command_running`, `current_task`, `stop_requested`.
    - `log_queue` (legacy), `executor`, `_session_file`.
  - UI composition:
    - Left panel: Boolean flags, value flags, additional configs.
    - Right panel: Tree view of components.
    - Footer: Command display, control buttons (Copy, Copy Logs, Clear Logs, Selection Mode, Run, Stop), log output area.
  - Key handlers:
    - `on_mount`: Populate tree; bind executor log to `_append_log` via `call_from_thread`; restore session.
    - `on_tree_node_selected`: Update selections based on node type.
    - `on_checkbox_changed`: Toggle boolean flags.
    - `on_button_pressed`: Handle value/config dialogs; run/stop; copy command/logs; clear logs; selection mode tip.
    - `action_reset`: Clear selections and logs.
  - Command execution:
    - `_run_command`: Build `command_list`; mark running; call `executor.start(...);` save session; await worker completion; drain any queued logs.
  - Logging UI:
    - `_append_log(text)`: Append to `#log-output` and auto-scroll; keeps last ~200 lines.
  - Real-time logging setup (legacy path): `_setup_real_time_logging`, `_cleanup_real_time_logging` using a handler that calls `call_from_thread`. The executor now provides a cleaner, centralized handler.

- `mite_ui.run_debug_scenario` (headless helper)
  - Role: Run a scenario (`scenario test <module>:<name> --debugging`) from a script, using `MiteExecutor`.
  - Options: `--start-dir`, `--module`, `--name` with defaults (`.` / `test_mite_components` / `test_scenario`).
  - Flow: Builds command list; sets a log callback that prints to stdout; starts executor; waits for thread to end.

## Function-by-Function Flow (Key Paths)

1. UI startup
   - Entry: `mite_ui(opts)` in `cheap_mitefinder.py`.
   - Sets `asyncio.DefaultEventLoopPolicy`; `MITE_PROFILE=1` env guard.
   - Discovers components via `CheapMiteFinder(start_dir).discover()` → `to_dict()`.
   - Instantiates `MiteUi(json_tree, start_path)` and `app.run()`.

2. Selecting components
   - `on_tree_node_selected`: Calls `BuildTestCommand.set_test_component`, `set_datapool`, or `set_config` depending on selection type.
   - `on_checkbox_changed`: Toggles boolean flags via `BuildTestCommand.toggle_boolean_flag`.

3. Building the command
   - `BuildTestCommand.build_command()`: Produces `mite <journey|scenario> test <module:path>:<name> [datapool] [--config=...] [flags] [value-flags] [--add-to-config=...]`.
   - `get_command_list()`: Splits into argv-like list.

4. Running the command
   - `MiteUi._run_command`: Marks running; calls `self.executor.start(command_list, self.start_dir)`; saves session; awaits thread completion.
   - `MiteExecutor.start`: Creates worker thread and event loop; installs log handler; sets `sys.argv` and `cwd`; calls `main()`.
   - Logs are forwarded to `MiteUi._append_log` via `call_from_thread`.

5. Stopping the command
   - `MiteUi._stop_command`: Calls `self.executor.stop()`.
   - `MiteExecutor.stop`: Injects `KeyboardInterrupt` into the worker thread; waits for end; reports status.

6. Copying logs/command
   - `on_button_pressed` for `copy-btn`: Copies command text using `pyperclip` if available.
   - `copy-logs-btn`: Copies aggregated log output.
   - `clear-logs-btn`: Clears the UI log panel.
   - `selection-mode-btn`: Displays a tip for selecting text; avoids interfering with Textual’s input capture.

## Threads, Event Loops, and Async Model

- Main thread (UI)
  - Runs the Textual event loop.
  - All UI updates must be scheduled on the main thread; we use `call_from_thread` where necessary.

- Worker thread (executor)
  - Dedicated `threading.Thread` created by `MiteExecutor.start()`.
  - Sets `asyncio.DefaultEventLoopPolicy()` and creates a brand-new event loop via `asyncio.new_event_loop()`.
  - Monkey-patches `loop.call_soon` to fallback to `loop.call_soon_threadsafe` when a cross-thread call causes `RuntimeError("Non-thread-safe operation ...")`.
  - Prevents `uvloop` installation via `MITE_PROFILE=1` and explicit policy, isolating the worker from main-loop constraints.
  - Calls `mite.__main__.main()` directly (no subprocess). This function may itself spin async tasks or use libraries expecting an event loop in the current thread.
  - Logging is routed via a `logging.Handler` (no global stdout/stderr redirection) to avoid corrupting terminal rendering.
  - Cleanup: `gc.collect()`, best-effort `acurl` cleanup, `loop.close()`, restore environment.

- Communication
  - Logs: Worker → UI via `log_callback`; UI uses `call_from_thread` to safely update widgets.
  - Stop: UI → Worker by injecting `KeyboardInterrupt` into the worker thread with `PyThreadState_SetAsyncExc`.

- Known constraints and mitigations
  - Cross-thread event loop calls: Mitigated by the `call_soon` shim and by isolating the worker’s loop.
  - `uvloop` debug mode complaints: Guarded by `MITE_PROFILE` and default policy; avoid using uvloop within the worker.
  - Finalizer warnings (`acurl.Session.__dealloc__`): Mitigated by running `gc.collect()` on the worker and attempting acurl cleanup; best fix is to explicitly close sessions in the worker’s context before thread exit.
  - UI “engulfing” by logs: Avoid global `sys.stdout/stderr` redirection; use logging handlers instead.

## Execution Sequence Summary

1. User launches UI via `mite_ui(opts)`.
2. Finder discovers components; UI renders.
3. User selects scenario/journey, flags, and configs.
4. User hits `Run`:
   - UI builds command → `executor.start(...)`.
   - Worker thread starts, sets up loop and logging, runs `main()`.
   - Logs stream to UI via callback.
5. User hits `Stop`:
   - UI calls `executor.stop()` → KeyboardInterrupt raised in worker.
   - Worker cleans up and terminates; UI unblocks and resets running state.

## Extension Points

- Session persistence: `MiteUi._save_session()` / `_load_session()` save selections to `.mite_ui_session.json`.
- Additional flags: Add to `BuildTestCommand.BOOLEAN_FLAGS` / `VALUE_FLAGS` and wire to UI.
- Logging: Attach additional handlers or formats per library; avoid touching process-wide streams.
- Cleanup hooks: If certain libraries open sessions/resources, register explicit cleanup calls in the worker or wrap scenario execution with context managers.

## Troubleshooting

- Seeing `RuntimeError: Non-thread-safe operation ...`:
  - Confirm the worker thread owns the event loop; ensure no `call_soon` is invoked from UI/end.
  - Keep `MITE_PROFILE=1` and the default policy in both UI entry and worker start.
  - Prefer `call_from_thread` for UI updates.

- UI rendering glitches:
  - Ensure no global `sys.stdout/stderr` redirection is active.
  - Keep log updates inside the log panel (`_append_log`).

- Stop not working:
  - Verify `self.executor.thread.ident` is cached.
  - Confirm KeyboardInterrupt injection returns 1 (success) and the worker terminates.
  - Increase wait loops / add defensive cleanup if needed.

---

For questions or deeper dives, start from `MiteExecutor.start()` and `MiteUi._run_command()`; they orchestrate the cross-thread handoff and are the linchpins of the architecture.
