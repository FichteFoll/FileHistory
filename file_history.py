import os
import hashlib
import json
import time
import re
import shutil
import glob
from textwrap import dedent

import sublime
import sublime_plugin

is_ST2 = int(sublime.version()) < 3000

invoke_async = sublime.set_timeout if is_ST2 else sublime.set_timeout_async


# Use this compat method to create a dummy class
# that other classes can be subclassed from.
# This allows specifying a metaclass for both Py2 and Py3 with the same syntax.
def with_metaclass(meta, *bases):
    """Create a base class with a metaclass."""
    return meta("_NewBase", bases or (object,), {})


# Metaclass for singletons
class Singleton(type):
    _instance = None

    def __call__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instance


class FileHistory(with_metaclass(Singleton)):

    SETTINGS_CALLBACK_KEY = 'FileHistory-reload'
    PRINT_DEBUG = False
    SETTINGS_FILE = 'FileHistory.sublime-settings'
    INDENT_SIZE = 2
    DEFAULT_TIMESTAMP_FORMAT = '%Y-%m-%d @ %H:%M:%S'
    OLD_DEFAULT_TIMESTAMP_FORMAT = '%Y-%m-%d %H:%M:%S'

    def __init__(self):
        """Class to manage the file-access history"""
        self.__load_settings()
        self.__load_history()
        self.__clear_context()

        if self.DELETE_ALL_ON_STARTUP:
            invoke_async(lambda: self.delete_all_history(), 0)
        elif self.CLEANUP_ON_STARTUP:
            invoke_async(lambda: self.clean_history(False), 0)

    def __load_settings(self):
        """Load the plugin settings from FileHistory.sublime-settings"""

        self.app_settings = sublime.load_settings(self.SETTINGS_FILE)
        self.__refresh_settings(True)

        # The settings may change during execution so we need to listen for changes
        self.app_settings.add_on_change(self.SETTINGS_CALLBACK_KEY, self.__refresh_settings)

    def __refresh_settings(self, first_load=False):
        if not first_load:
            print('[FileHistory] Reloading the settings file "%s".' % (self.SETTINGS_FILE))

        self.PRINT_DEBUG = self.__ensure_setting('debug', False)

        self.GLOBAL_MAX_ENTRIES = self.__ensure_setting('global_max_entries', 100)
        self.PROJECT_MAX_ENTRIES = self.__ensure_setting('project_max_entries', 50)
        self.USE_SAVED_POSITION = self.__ensure_setting('use_saved_position', True)
        self.NEW_TAB_POSITION = self.__ensure_setting('new_tab_position', 'next')
        self.REOPEN_IN_CURRENT_GROUP = self.__ensure_setting('reopen_file_in_current_group', False)

        self.REMOVE_NON_EXISTENT_FILES = self.__ensure_setting('remove_non_existent_files_on_preview', True)
        self.CLEANUP_ON_STARTUP = self.__ensure_setting('cleanup_on_startup', True)
        self.DELETE_ALL_ON_STARTUP = self.__ensure_setting('delete_all_on_startup', False)
        history_path = self.__ensure_setting('history_file', os.path.join('User', 'FileHistory.json'))

        self.HISTORY_FILE = os.path.normpath(os.path.join(sublime.packages_path(), history_path))

        self.USE_MONOSPACE = self.__ensure_setting('monospace_font', False)

        self.TIMESTAMP_SHOW = self.__ensure_setting('timestamp_show', True)
        self.TIMESTAMP_FORMAT = self.__ensure_setting('timestamp_format', self.DEFAULT_TIMESTAMP_FORMAT)
        self.TIMESTAMP_MODE = self.__ensure_setting('timestamp_mode', 'history_access')
        self.TIMESTAMP_RELATIVE = self.__ensure_setting('timestamp_relative', True)

        self.PRETTIFY_HISTORY = self.__ensure_setting('prettify_history', False)

        self.PATH_EXCLUDE_PATTERNS = self.__ensure_setting('path_exclude_patterns', [])
        self.PATH_REINCLUDE_PATTERNS = self.__ensure_setting('path_reinclude_patterns', [])

        self.MAX_BACKUP_COUNT = self.__ensure_setting('max_backup_count', 3)

        # Test if the specified format string is valid
        try:
            time.strftime(self.TIMESTAMP_FORMAT)
        except ValueError:
            print('[FileHistory] Invalid timstamp_format string. Falling back to default.')
            self.TIMESTAMP_FORMAT = self.DEFAULT_TIMESTAMP_FORMAT

        # Ignore the file preview setting for ST2
        self.SHOW_FILE_PREVIEW = False if is_ST2 else self.__ensure_setting('show_file_preview', True)

    def get_history_timestamp(self, history_entry, action):
        timestamp = None
        filepath = history_entry['filename']
        if 'timestamp' in history_entry and self.TIMESTAMP_MODE == 'history_access':
            timestamp = history_entry['timestamp']
        elif filepath and os.path.exists(filepath):
            action = 'modified'
            timestamp = int(os.path.getmtime(filepath))
        return (action, timestamp)

    def timestamp_from_string(self, timestamp):
        """try with the user-defined timestamp then try the default timestamp."""
        formats = (self.TIMESTAMP_FORMAT,
                   self.DEFAULT_TIMESTAMP_FORMAT,
                   self.OLD_DEFAULT_TIMESTAMP_FORMAT)
        for format_string in formats:
            try:
                history_time = time.strptime(timestamp, format_string)
            except ValueError:
                pass
            else:
                return int(time.mktime(history_time))
        self.debug('The timestamp "%s" does not match any of the formats %s' % (timestamp, formats))

    def __ensure_setting(self, key, default_value):
        value = default_value
        if self.app_settings.has(key):
            value = self.app_settings.get(key)
            self.debug('Setting "%s" = %r' % (key, value))
        else:
            # no need to persist this setting - just use the default
            self.debug('Setting "%s" not found.  Using the default value of %r' % (key, default_value))
        return value

    def debug(self, text):
        """Helper method for "logging" to the console."""
        if self.PRINT_DEBUG:
            print('[FileHistory] ' + text)

    def get_current_project_key(self):
        m = hashlib.md5()
        for path in sublime.active_window().folders():
            m.update(path.encode('utf-8'))
        project_key = m.hexdigest()

        # Try to use project_file_name (available in ST3 build 3014)
        # Note: Although it would be more appropriate, the name of the workspace is not available
        if hasattr(sublime.active_window(), 'project_file_name'):
            project_filename = sublime.active_window().project_file_name()
            if not project_filename:
                return project_key

            # migrate the history entry based on the "old" project key (if it exists)
            if project_key in self.history:
                self.history[project_filename] = self.history[project_key]
                del self.history[project_key]

            # use the new project key
            project_key = project_filename

        return project_key

    def __load_history(self):
        self.history = {}

        if not os.path.exists(self.HISTORY_FILE):
            self.debug("History file '%s' doesn't exist" % self.HISTORY_FILE)
            return

        self.debug('Loading the history from file ' + self.HISTORY_FILE)
        try:
            with open(self.HISTORY_FILE, 'r') as f:
                updated_history = json.load(f)
        except Exception as e:
            updated_history = {}
            sublime.error_message(
                dedent("""\
                       File History could not read your history file at '%s'.

                       %s: %s""")
                % (self.HISTORY_FILE, e.__class__.__name__, e)
            )
        self.history = updated_history

        # Do cleanup on the history file
        self.__ensure_project('global')
        trigger_save = False

        # Migrate old formatted timestamps and convert to POSIX
        hlist = updated_history['global']['closed'] or updated_history['global']['opened']
        if hlist and 'timestamp' in hlist[0] and not isinstance(hlist[0]['timestamp'], int):
            # Found an old timestamp. Likely that all others are old too
            self.debug("Found an old-style formatted timestamp. Migrating to POSIX")
            for project in updated_history.values():
                for key in ('closed', 'opened'):
                    for entry in project[key]:
                        if not isinstance(entry.get('timestamp', 0), int):
                            new_stamp = self.timestamp_from_string(entry['timestamp'])
                            if not new_stamp:
                                del entry['timestamp']
                            else:
                                entry['timestamp'] = new_stamp
            trigger_save = True
        # Remove actions keys
        if hlist and 'action' in hlist[0]:
            self.debug("Found an old-style action field. Cleaning up")
            trigger_save = True
            for project in updated_history.values():
                for key in ('closed', 'opened'):
                    for entry in project[key]:
                        if 'action' in entry:
                            del entry['action']

        if trigger_save:
            # Save the changes
            self.__save_history()

    def __save_history(self):
        self.debug('Saving the history to file ' + self.HISTORY_FILE)
        with open(self.HISTORY_FILE, mode='w+') as f:
            indent = self.INDENT_SIZE if self.PRETTIFY_HISTORY else None

            json.dump(self.history, f, indent=indent)
            f.flush()

        invoke_async(lambda: self.__manage_backups(), 0)

    def __manage_backups(self):
        # Only keep backups if the user wants them
        if self.MAX_BACKUP_COUNT <= 0:
            return

        # Make sure there is a backup of the history for today
        (root, ext) = os.path.splitext(self.HISTORY_FILE)
        datestamp = time.strftime('%Y%m%d')
        backup = '%s_%s%s' % (root, datestamp, ext)
        if not os.path.exists(backup):
            self.debug('Backing up the history file for %s' % datestamp)
            shutil.copy(self.HISTORY_FILE, backup)

        # Limit the number of backup files to keep
        listing = sorted(glob.glob('%s_*%s' % (root, ext)), reverse=True)
        if len(listing) > self.MAX_BACKUP_COUNT:
            for discard_file in listing[self.MAX_BACKUP_COUNT:]:
                self.debug('Discarding old backup %s' % discard_file)
                os.remove(discard_file)

    def delete_all_history(self):
        self.history = {}
        self.__save_history()

    def get_history(self, current_project_only=True):
        """Return a copy of the requested history (global or project-specific): closed files followed by opened files"""
        # Make sure the history is loaded
        # TODO: If we have loaded history previously we should cache it and not access the file system again
        if len(self.history) == 0:
            self.__load_history()

        # Load the requested history (global or project-specific)
        if current_project_only:
            self.project_name = self.get_current_project_key()
        else:
            self.project_name = 'global'

        # Return the list of closed and opened files
        if self.project_name in self.history:
            # Return a copy of the contained lists in history (the only actually mutated objects)
            history = self.history[self.project_name]
            return dict(opened=history['opened'][:], closed=history['closed'][:])
        else:
            self.debug('WARN: Project %s could not be found in the file history list - returning an empty history list' % (self.project_name))
            return dict(opened=[], closed=[])

    def __ensure_project(self, project_name):
        """Make sure the project nodes exist (including 'opened' and 'closed')"""
        if project_name not in self.history:
            self.history[project_name] = {}
            self.history[project_name]['opened'] = []
            self.history[project_name]['closed'] = []

    def is_suppressed(self, view, filename):
        override_settings = view.settings().get("file_history", dict())
        exclude_patterns = self.PATH_EXCLUDE_PATTERNS + override_settings.get("path_exclude_patterns", [])
        reinclude_patterns = self.PATH_REINCLUDE_PATTERNS + override_settings.get("path_reinclude_patterns", [])

        # Force forward slashes in the filename
        filename = os.path.normpath(filename).replace("\\", "/")

        # Search the filename for the pattern and suppress it if it matches
        for exclude in exclude_patterns:
            if re.search(exclude, filename):
                self.debug('[X] Exclusion pattern "%s" blocks history tracking for filename "%s"'
                           % (exclude, filename))
                # See if none of out reinclude patterns nullifies the exclude
                for reinclude in reinclude_patterns:
                    if re.search(reinclude, filename):
                        self.debug('[O] Inclusion pattern "%s" re-includes history tracking for filename "%s"'
                                   % (reinclude, filename))
                        return False
                return True

        return False

    def add_view(self, window, view, history_type):
        # No point adding a transient view to the history
        if self.is_transient_view(window, view):
            return

        # Only keep track of files that have a filename
        filename = view.file_name()
        if filename is not None:
            project_name = self.get_current_project_key()

            if self.is_suppressed(view, filename):
                # If filename matches 'path_exclude_patterns' then abort the history tracking
                # and remove any references to this file from the history
                self.__remove(project_name, filename)
                self.__remove('global', filename)
            elif os.path.exists(filename):
                # Add to both the project-specific and global histories
                (group, index) = sublime.active_window().get_view_index(view)
                self.__add_to_history(project_name, history_type, filename, group, index)
                self.__add_to_history('global', history_type, filename, group, index)
            else:
                # If the file doesn't exist then remove it from the lists
                self.__remove(project_name, filename)
                self.__remove('global', filename)

            self.__save_history()

    def __add_to_history(self, project_name, history_type, filename, group, index):
        self.debug('Adding %s file to project "%s" with group %s and index %s: %s' % (history_type, project_name, group, index, filename))

        # Make sure the project nodes exist
        self.__ensure_project(project_name)

        # Remove the file from the project list then
        # add it to the top (of the opened/closed list)
        self.__remove(project_name, filename)
        entry = {'filename': filename, 'group': group, 'index': index, 'timestamp': int(time.time())}
        self.history[project_name][history_type].insert(0, entry)

        # Make sure we limit the number of history entries
        max_num_entries = self.GLOBAL_MAX_ENTRIES if project_name == 'global' else self.PROJECT_MAX_ENTRIES
        self.history[project_name][history_type] = self.history[project_name][history_type][0:max_num_entries]

    def __remove(self, project_name, filename):
        # Only continue if this project exists
        if project_name not in self.history:
            return

        # Remove any references to this file from the project
        for history_type in ('opened', 'closed'):
            for node in iter(self.history[project_name][history_type]):
                if node['filename'] == filename:
                    self.history[project_name][history_type].remove(node)

    def clean_history(self, current_project_only):
        if current_project_only:
            self.__clean_history(self.get_current_project_key())
        # If requested, also clean-up the global history
        else:
            # clean all projects and remove any orphaned projects
            orphan_list = []
            for project_key in self.history:
                # clean the project or remove it (if it no longer exists)
                # The ST2 version uses md5 hashes for the project keys, so we can never know if a project is orphaned
                if not is_ST2 and not project_key == 'global' and not os.path.exists(project_key):
                    # queue the orphaned project for deletion
                    orphan_list.append(project_key)
                else:
                    # clean the project
                    self.__clean_history(project_key)

            # remove any orphaned projects and save the history
            for project_key in orphan_list:
                self.debug('Removing orphaned project "%s" from the history' % project_key)
                del self.history[project_key]

        # Save history
        self.__save_history()

    def __clean_history(self, project_name):
        self.debug('Cleaning the "%s" history' % (project_name))
        # Only continue if this project exists
        if project_name not in self.history:
            sublime.status_message("This project does not have any history")
            return

        # Remove any non-existent files from the project
        for history_type in ('opened', 'closed'):
            for node in reversed(self.history[project_name][history_type]):
                if not os.path.exists(node['filename']):
                    self.debug('Removing non-existent file from project "%s": %s' % (project_name, node['filename']))
                    self.history[project_name][history_type].remove(node)

        sublime.status_message("File history cleaned")

    def __clear_context(self):
        """Reset the calling view variables"""
        self.calling_view = None
        self.calling_view_index = []
        self.calling_view_is_empty = False

        self.current_view = None
        self.current_history_entry = None

    def __track_calling_view(self, window):
        """Remember the view that the command was run from (including the group and index positions),
        so we can return to the "calling" view if the user cancels the preview
        (or so we can show something if a file in the history no longer exists)"""
        if not self.calling_view:
            self.calling_view = window.active_view()
            if self.calling_view:
                self.calling_view_index = window.get_view_index(self.calling_view)
                self.calling_view_is_empty = len(window.views()) == 0
            else:
                self.calling_view_index = [0, 0]
                self.calling_view_is_empty = True

    def __calculate_view_index(self, window, history_entry):
        # Get the group of the new view (the currently active group is the default)
        group = history_entry['group']
        if group < 0 or group >= window.num_groups():
            group = self.calling_view_index[0]

        # Get the alternative tab index (in case the saved index in no longer valid):
        # The file could be opened in the saved tab position or as the first tab, the last tab or after the current tab...
        max_index = len(window.views_in_group(group))
        saved_index = history_entry['index']
        if self.USE_SAVED_POSITION and saved_index >= 0 and saved_index <= max_index:
            index = saved_index
        elif self.NEW_TAB_POSITION == 'first':
            index = 0
        elif self.NEW_TAB_POSITION == 'last':
            index = max_index
        elif self.calling_view_index:
            # DEFAULT: Open in the next tab
            index = self.calling_view_index[1] + 1
        else:
            index = 0
        return (group, index)

    def preview_history(self, window, history_entry):
        """Preview the file if it exists, otherwise show the previous view (aka the "calling_view")"""
        self.current_history_entry = history_entry

        # track the view even if we won't be previewing it (to support quick-open and remove from history quick keys)
        self.__track_calling_view(window)

        # Only preview the view if the user wants to see it
        if not self.SHOW_FILE_PREVIEW:
            return

        filepath = history_entry['filename']
        if os.path.exists(filepath):
            # asynchronously open the preview (improves perceived performance)
            invoke_async(lambda: self.__open_preview(window, filepath), 0)
        else:
            # Close the last preview and remove the non-existent file from the history
            self.__close_preview(window)
            self.__remove(self.get_current_project_key(), filepath)
            self.__save_history()

    def __open_preview(self, window, filepath):
        self.debug("Opening preview for '%s'" % filepath)
        self.current_view = window.open_file(filepath, sublime.TRANSIENT | getattr(sublime, 'FORCE_GROUP', 0))

    def quick_open_preview(self, window):
        """Open the file that is currently being previewed
        Returns true if 'refresh' state should be cleared later."""
        if not self.current_history_entry:
            return

        view = self.current_view
        other_view = self.get_view_from_another_group(window, view.file_name())

        # Only try to open and position the file if it is transient
        if self.is_transient_view(window, view):
            if not self.REOPEN_IN_CURRENT_GROUP and other_view:
                # Focus the other view instead of opening a clone
                self.debug("Focussing existing view in group %d" % window.get_view_index(other_view)[0])
                self.__close_preview(window)
                window.focus_view(other_view)
                # Changing focus to another group requires reopening the panel, unfortunately
                return True
            else:
                (group, index) = self.__calculate_view_index(window, self.current_history_entry)
                view = window.open_file(self.current_history_entry['filename'])
                window.set_view_index(view, group, index)

        # Refocus on the newly opened file rather than the original one
        self.__clear_context()
        self.__track_calling_view(window)

    def delete_current_entry(self):
        """Delete the history entry for the file that is currently being previewed"""
        if not self.current_history_entry:
            return

        filename = self.current_history_entry['filename']
        self.debug('Removing history entry for "%s" from project "%s"' % (filename, self.project_name))
        self.__remove(self.project_name, filename)
        self.__save_history()

    def open_history(self, window, history_entry):
        """Open the file represented by the history_entry in the provided window"""
        self.__track_calling_view(window)

        (group, index) = self.__calculate_view_index(window, history_entry)

        if not self.REOPEN_IN_CURRENT_GROUP or not hasattr(sublime, 'FORCE_GROUP'):
            # Open the file and position the view correctly
            self.__close_preview(window)
            new_view = window.open_file(history_entry['filename'])
            window.set_view_index(new_view, group, index)
            self.debug('Opened file in group %s, index %s (based on saved group %s, index %s): %s'
                       % (group, index, history_entry['group'], history_entry['index'], history_entry['filename']))
        else:
            window.open_file(history_entry['filename'], sublime.FORCE_GROUP)
            self.debug('Opened clone of file in current group: %s' % history_entry['filename'])

        self.__clear_context()

    def __close_preview(self, window):
        if not self.SHOW_FILE_PREVIEW:
            return

        active_view = window.active_view()
        if not self.current_view:
            return
        elif self.current_view.id() != active_view.id():
            self.debug("ID mismatch!")
            return
        elif not self.is_transient_view(window, self.current_view):
            self.debug("Last 'opened' view not transient")
            return

        self.debug("Closing file: %s" % self.current_view.file_name())
        window.run_command("close_file")
        self.current_view = None

    def reset(self, window):
        """The user cancelled the action - give the focus back to the "calling" view and clear the context"""
        self.__close_preview(window)
        self.__clear_context()

    def is_transient_view(self, window, view):
        if is_ST2:
            return False

        if not view:
            # Sometimes, the view is just `None`. We can't use it in this
            # state so just mark as transient.
            return True
        elif window.get_view_index(view)[1] == -1:
            # If the view index is -1, then this can't be a real view.
            # window.transient_view_in_group is not returning the correct
            # value when we quickly cycle through the quick panel previews.
            self.debug("Detected possibly transient view with index = -1: '%s'"
                       % view.file_name())
            return True
        else:
            return view == window.transient_view_in_group(window.active_group())

    def get_view_from_another_group(self, window, filename):
        if self.calling_view_index:
            # Not always defined at this point
            calling_group = self.calling_view_index[0]
        else:
            calling_group = window.get_view_index(window.active_view())[0]

        # Scan for view with same file_name in other groups
        for group in range(window.num_groups()):
            if group == calling_group:
                continue
            for view in window.views_in_group(group):
                if view.file_name() == filename:
                    return view

#######################################


class OpenRecentlyClosedFileEvent(sublime_plugin.EventListener):
    # We need pre close to detect if the view was transient,
    # otherwise it always has (-1, -1) group and index.
    def on_pre_close(self, view):
        FileHistory().add_view(sublime.active_window(), view, 'closed')

    # However, ST2 does not have pre_close (and no transient views either).
    if is_ST2:
        on_close = on_pre_close

    def on_load(self, view):
        FileHistory().add_view(sublime.active_window(), view, 'opened')


class CleanupFileHistoryCommand(sublime_plugin.WindowCommand):
    def run(self, current_project_only=True):
        FileHistory().clean_history(current_project_only)


class ResetFileHistoryCommand(sublime_plugin.WindowCommand):
    def run(self):
        FileHistory().delete_all_history()


class OpenRecentlyClosedFileCommand(sublime_plugin.WindowCommand):
    """class to either open the last closed file or show a quick panel with the recent file history (closed files first)"""

    __is_active = False

    def approximate_age(self, from_stamp, to_stamp=None, precision=2):
        """Calculate the relative time from given timestamp to another given (epoch) or now."""
        if to_stamp is None:
            to_stamp = time.time()
        rem = to_stamp - from_stamp

        def divide(rem, mod):
            return rem % mod, int(rem // mod)

        def subtract(rem, div):
            n = int(rem // div)
            return n,  rem - n * div

        seconds, rem = divide(rem, 60)
        minutes, rem = divide(rem, 60)
        hours,  days = divide(rem, 24)
        years,  days = subtract(days, 365)
        months, days = subtract(days, 30)
        weeks,  days = subtract(days, 7)

        magnitudes = []
        first = None
        values = locals()
        for i, magnitude in enumerate(("years", "months", "weeks", "days", "hours", "minutes", "seconds")):
            v = int(values[magnitude])
            if v == 0:
                continue
            s = "%s %s" % (v, magnitude)
            if v == 1:  # strip plural s
                s = s[:-1]
            # Handle precision limit
            if first is None:
                first = i
            elif first + precision <= i:
                break
            magnitudes.append(s)

        return ", ".join(magnitudes)

    def set_refresh_in_progress(self):
        self.refresh_in_progress = True

    def clear_refresh_in_progress(self):
        del self.refresh_in_progress

    def is_refresh_in_progress(self):
        return hasattr(self, "refresh_in_progress")

    def delete_current_entry(self):
        if not self.current_selected_index or self.current_selected_index < 0:
            return

        closed_len = len(self.history_list['closed'])
        if self.current_selected_index < closed_len:
            key = 'closed'
        else:
            self.current_selected_index -= closed_len
            key = 'opened'

        if self.current_selected_index <= len(self.history_list[key]):
            del self.history_list[key][self.current_selected_index]

    def get_history_by_index(self, index):
        if index < 0:
            return
        closed_len = len(self.history_list['closed'])
        if index < closed_len:
            key = 'closed'
        else:
            index -= closed_len
            key = 'opened'

        if index <= len(self.history_list[key]):
            return self.history_list[key][index]

    def run(self, current_project_only=True, action="show_history"):
        if action == "show_history":
            self.current_project_only = current_project_only

            if not self.is_refresh_in_progress():
                self.history_list = FileHistory().get_history(current_project_only)
                self.current_selected_index = None
                self.group_index = self.window.active_group()
                selected_index = 0
            else:
                FileHistory().debug("Reopening from refresh")
                self.window.focus_group(self.group_index)
                self.clear_refresh_in_progress()
                selected_index = self.current_selected_index
                # TODO recover filter text?

            # Prepare the display list with the file name and path separated
            display_list = []
            for key in ('closed', 'opened'):
                for entry in self.history_list[key]:
                    filepath = entry['filename']
                    info = [os.path.basename(filepath), os.path.dirname(filepath)]

                    # Only include the timestamp if it is there and if the user wants to see it
                    if FileHistory().TIMESTAMP_SHOW:
                        if not os.path.exists(filepath):
                            stamp = 'file no longer exists'
                        else:
                            (action, timestamp) = FileHistory().get_history_timestamp(entry, key)
                            if not timestamp:
                                stamp = ''
                            elif bool(FileHistory().TIMESTAMP_RELATIVE):
                                stamp = '%s ~%s ago' % (action, self.approximate_age(timestamp))
                            else:
                                stamp = '%s on %s' % (action, time.strftime(self.TIMESTAMP_FORMAT, timestamp))
                        info.append((' ' * 6) + stamp)

                    display_list.append(info)

            if not display_list:
                return

            font_flag = sublime.MONOSPACE_FONT if FileHistory().USE_MONOSPACE else 0

            self.__class__.__is_active = True

            if is_ST2:
                self.window.show_quick_panel(display_list, self.open_file, font_flag)
            else:
                self.window.show_quick_panel(display_list, self.open_file, font_flag,
                                             on_highlight=self.show_preview,
                                             selected_index=selected_index)
            sublime.status_message("[File History] You can quick-open or remove the currently "
                                   "selected entry with `right` and `ctrl/cmd+del` respectively.")

        elif action == "open_latest_closed":
            self.history_list = FileHistory().get_history(current_project_only)
            self.open_file(0)
        elif action == "delete_current_entry":
            FileHistory().delete_current_entry()
            if not self.current_selected_index:
                return
            self.delete_current_entry()
            # Deleting an entry from the quick panel should reopen it with the entry removed
            self.set_refresh_in_progress()
            sublime.active_window().run_command('hide_overlay')
        elif action == "quick_open_current_entry":
            # Will require reopening the panel if view in another group is focussed
            self.set_refresh_in_progress()
            if not FileHistory().quick_open_preview(sublime.active_window()):
                self.clear_refresh_in_progress()

    @classmethod
    def is_active(cls):
        '''
        Returns whether the history overlay is open in a window. Note that
        only the currently focused window can have an open overlay.
        '''

        return cls.__is_active

    def show_preview(self, selected_index):
        # Note: This function will never be called in ST2
        self.current_selected_index = selected_index
        selected_entry = self.get_history_by_index(selected_index)
        if selected_entry:
            # A bug in SublimeText will cause the quick-panel to unexpectedly close trying to show the preview
            # for a file that is already open in a different group, so simply don't display the preview for these files.
            # In later releases, a 'FORCE_GROUP' flag has been introduced.
            if hasattr(sublime, 'FORCE_GROUP') or not FileHistory().get_view_from_another_group(self.window, selected_entry['filename']):
                FileHistory().preview_history(self.window, selected_entry)

    def open_file(self, selected_index):
        self.__class__.__is_active = False

        selected_entry = self.get_history_by_index(selected_index)
        if selected_entry:
            # If the file is open in another group then simply give focus to that view, otherwise open the file
            open_view = FileHistory().get_view_from_another_group(self.window, selected_entry['filename'])

            if open_view and not FileHistory().REOPEN_IN_CURRENT_GROUP:
                FileHistory().debug("Focussing existing view in group %d" % self.window.get_view_index(open_view)[0])
                FileHistory().reset(self.window)  # clear preview
                self.window.focus_view(open_view)
            else:
                FileHistory().open_history(self.window, selected_entry)
        else:
            # The user cancelled the action
            FileHistory().reset(self.window)
            FileHistory().debug("User closed panel")

            if self.is_refresh_in_progress():
                self.window.run_command('open_recently_closed_file', {'current_project_only': self.current_project_only})
                return


        self.history_list = {}


class OpenRecentlyCloseFileCommandContextHandler(sublime_plugin.EventListener):

    def on_query_context(self, view, key, operator, operand, match_all):
        if key != 'file_history_overlay_visible':
            return None

        v1, v2 = OpenRecentlyClosedFileCommand.is_active(), bool(operand)

        if operator == sublime.OP_EQUAL:
            return v1 == v2
        elif operator == sublime.OP_NOT_EQUAL:
            return v1 != v2
        else:
            return None


def plugin_loaded():
    # Force the FileHistory singleton to be instantiated so the startup tasks will be executed
    # Depending on the "cleanup_on_startup" setting, the history may be cleaned at startup
    FileHistory()


def plugin_unloaded():
    # Unregister our on_change callback
    FileHistory().app_settings.clear_on_change(FileHistory.SETTINGS_CALLBACK_KEY)

# ST2 backwards (and don't call it twice in ST3)
unload_handler = plugin_unloaded if is_ST2 else lambda: None

if is_ST2:
    plugin_loaded()
