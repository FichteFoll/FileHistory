import sublime
import sublime_plugin
import os
import hashlib
import json
import time
import datetime

is_ST2 = int(sublime.version()) < 3000


def plugin_loaded():
    # Force the FileHistory singleton to be instantiated so the startup tasks will be executed
    # Depending on the "cleanup_on_startup" setting, the history may be cleaned at startup
    FileHistory.instance()


class FileHistory(object):
    _instance = None

    @classmethod
    def instance(cls):
        """Basic singleton implementation"""
        if not cls._instance:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        """Class to manage the file-access history"""
        self.SETTINGS_FILE = 'FileHistory.sublime-settings'
        self.PRINT_DEBUG = False
        self.__load_settings()
        self.__load_history()
        self.__clear_context()

        self.invoke_async = sublime.set_timeout if is_ST2 else sublime.set_timeout_async

        if self.DELETE_ALL_ON_STARTUP:
            self.invoke_async(lambda: self.delete_all_history(), 0)
        elif self.CLEANUP_ON_STARTUP:
            self.invoke_async(lambda: self.clean_history(False), 0)


    def __load_settings(self):
        default_date_format = '%Y-%m-%d %H:%M:%S'

        """Load the plugin settings from FileHistory.sublime-settings"""
        app_settings = sublime.load_settings(self.SETTINGS_FILE)
        settings_exist = app_settings.has('history_file')

        # TODO these settings may change during execution but are not re-fetched when that happens
        # We either need to set this as a `settings.set_on_change` callback (will be called for any
        # modification) or wrap settings differently.

        self.PRINT_DEBUG = self.__ensure_setting(app_settings, 'debug', False)
        self.GLOBAL_MAX_ENTRIES = self.__ensure_setting(app_settings, 'global_max_entries', 100)
        self.PROJECT_MAX_ENTRIES = self.__ensure_setting(app_settings, 'project_max_entries', 50)
        self.USE_SAVED_POSITION = self.__ensure_setting(app_settings, 'use_saved_position', True)
        self.NEW_TAB_POSITION = self.__ensure_setting(app_settings, 'new_tab_position', 'next')
        self.REMOVE_NON_EXISTENT_FILES = self.__ensure_setting(app_settings, 'remove_non_existent_files_on_preview', True)
        self.CLEANUP_ON_STARTUP = self.__ensure_setting(app_settings, 'cleanup_on_startup', True)
        self.DELETE_ALL_ON_STARTUP = self.__ensure_setting(app_settings, 'delete_all_on_startup', False)
        history_path = self.__ensure_setting(app_settings, 'history_file', os.path.join('User', 'FileHistory.json'))
        self.HISTORY_FILE = os.path.normpath(os.path.join(sublime.packages_path(), history_path))
        self.USE_MONOSPACE = self.__ensure_setting(app_settings, 'monospace_font', False)
        self.DISPLAY_TIMESTAMPS = self.__ensure_setting(app_settings, 'display_timestamps', True)
        self.TIMESTAMP_FORMAT = self.__ensure_setting(app_settings, 'timestamp_format', default_date_format)
        self.TIMESTAMP_MODE = self.__ensure_setting(app_settings, 'timestamp_mode', 'history_access')
        self.TIMESTAMP_DISPLAY_TYPE = self.__ensure_setting(app_settings, 'timestamp_display_type', 'relative')
        self.PRETTIFY_HISTORY = self.__ensure_setting(app_settings, 'prettify_history', False)
        self.INDENT_SIZE = 4

        # Test if the specified format string is valid
        try:
            time.strftime(self.TIMESTAMP_FORMAT)
        except ValueError:
            print('[FileHistory] Invalid timstamp_format string. Falling back to default.')
            self.TIMESTAMP_FORMAT = default_date_format

        # Ignore the file preview setting for ST2
        self.SHOW_FILE_PREVIEW = False if is_ST2 else self.__ensure_setting(app_settings, 'show_file_preview', True)

        if not settings_exist:
            print('[FileHistory] Unable to find the settings file "%s".  A default settings file has been created for you.' % (self.SETTINGS_FILE))
            sublime.save_settings(self.SETTINGS_FILE)

    def get_timestamp(self, filename=None):
        if filename and os.path.exists(filename):
            timestamp = time.strftime(self.TIMESTAMP_FORMAT, time.localtime(os.path.getmtime(filename)))
        else:
            timestamp = time.strftime(self.TIMESTAMP_FORMAT)
        return timestamp

    def get_history_timestamp(self, history_entry):
        filepath = history_entry['filename']
        if 'timestamp' in history_entry and self.TIMESTAMP_MODE == 'history_access':
            action = history_entry['action'] if 'action' in history_entry else 'accessed'
            timestamp = history_entry['timestamp']
        else:
            action = 'modified'
            timestamp = self.get_timestamp(filepath)
        return (action, timestamp)

    def __ensure_setting(self, settings, key, default_value):
        value = default_value
        if settings.has(key):
            value = settings.get(key)
            self.debug('FileHistory setting "%s" = "%s"' % (key, value))
        else:
            self.debug('FileHistory setting "%s" not found.  Using the default value of "%s"' % (key, default_value))
            # TOCHECK I am not sure we should do this. It makes modifying default behaviour a pain because we force
            # all users onto a custom configuration. Furthermore, I don't have documentation comments in the user
            # file because it's rewritten all the time.
            settings.set(key, default_value)
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
                del(self.history[project_key])

            # use the new project key
            project_key = project_filename

        return project_key

    def __load_history(self):
        self.history = {}

        self.debug('Loading the history from file ' + self.HISTORY_FILE)
        if not os.path.exists(self.HISTORY_FILE):
            return

        with open(self.HISTORY_FILE, 'r') as f:
            updated_history = json.load(f)

        self.history = updated_history

    def __save_history(self):
        self.debug('Saving the history to file ' + self.HISTORY_FILE)
        with open(self.HISTORY_FILE, mode='w+') as f:
            history_indentation = self.INDENT_SIZE if self.PRETTIFY_HISTORY else None

            json.dump(self.history, f, indent=history_indentation)
            f.flush()

    def delete_all_history(self):
        self.history = {}
        self.__save_history()

    def get_history(self, current_project_only=True):
        """Return the requested history (global or project-specific): closed files followed by opened files"""
        # Make sure the history is loaded
        if len(self.history) == 0:
            self.__load_history()

        # Load the requested history (global or project-specific)
        if current_project_only:
            self.project_name = self.get_current_project_key()
        else:
            self.project_name = 'global'

        # Return the list of closed and opened files
        if self.project_name in self.history:
            # Note that a copy of the list must be returned
            return self.history[self.project_name]['closed'] + self.history[self.project_name]['opened']
        else:
            self.debug('WARN: Project %s could not be found in the file history list - returning an empty history list' % (self.project_name))
            return []

    def __ensure_project(self, project_name):
        """Make sure the project nodes exist (including 'opened' and 'closed')"""
        if project_name not in self.history:
            self.history[project_name] = {}
            self.history[project_name]['opened'] = []
            self.history[project_name]['closed'] = []

    def add_view(self, window, view, history_type):
        # No point adding a transient view to the history
        if self.is_transient_view(window, view):
            return

        # Only keep track of files that have a filename
        filename = view.file_name()
        if filename is not None:
            project_name = self.get_current_project_key()
            if os.path.exists(filename):
                # Add to both the project-specific and global histories
                (group, index) = sublime.active_window().get_view_index(view)
                self.__add_to_history(project_name, history_type, filename, group, index)
                self.__add_to_history('global', history_type, filename, group, index)
            else:
                # If the file doesn't exist then remove it from the lists
                self.__remove_view(filename, project_name, False)

            self.__save_history()

    def __remove_view(self, filename, project_name, save_history):
        if self.REMOVE_NON_EXISTENT_FILES:
            self.debug('The file no longer exists, so it has been removed from the history: ' + filename)
            self.__remove(project_name, filename)
            self.__remove('global', filename)

            if save_history:
                self.__save_history()

    def __add_to_history(self, project_name, history_type, filename, group, index):
        self.debug('Adding %s file to project "%s" with group %s and index %s: %s' % (history_type, project_name, group, index, filename))

        # Make sure the project nodes exist
        self.__ensure_project(project_name)

        # Remove the file from the project list then
        # add it to the top (of the opened/closed list)
        self.__remove(project_name, filename)
        node = {'filename': filename, 'group': group, 'index': index, 'timestamp': self.get_timestamp(), 'action': history_type}
        self.history[project_name][history_type].insert(0, node)

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
        self.__clean_history(self.get_current_project_key())

        # If requested, also clean-up the global history
        if not current_project_only:
            self.__clean_history('global')

            # clean all projects and remove any orphaned projects
            orphan_list = []
            for project_key in self.history:
                # skip the global project and the current one (that was just cleaned above)
                if project_key in ('global', self.get_current_project_key()):
                    continue

                # clean the project or remove it (if it no longer exists)
                # The ST2 version uses md5 hashes for the project keys, so we can never know if a project is orphaned
                if not is_ST2 and not os.path.exists(project_key):
                    # queue the orphaned project for deletion
                    orphan_list.append(project_key)
                else:
                    # clean the project
                    self.__clean_history(project_key)

            # remove any orphaned projects and save the history
            for project_key in orphan_list:
                self.debug('Removing orphaned project "%s" from the history' % project_key)
                del self.history[project_key]
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

        self.__save_history()
        sublime.status_message("File history cleaned")

    def __clear_context(self):
        """Reset the calling view variables"""
        self.calling_view = None
        self.calling_view_index = []
        self.calling_view_is_empty = True

        self.current_view = None
        self.current_history_entry = None

        self.project_name = None

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
            # asyncronously open the preview (improves percieved performance)
            self.invoke_async(lambda: self.__open_preview(window, filepath), 0)
        else:
            # Close the last preview and remove the non-existent file from the history
            self.__close_preview(window)
            self.__remove_view(filepath, self.get_current_project_key(), True)

    def __open_preview(self, window, filepath):
        self.current_view = window.open_file(filepath, sublime.TRANSIENT)

    def quick_open_preview(self, window):
        """Open the file that is currently being previewed"""
        if not self.current_history_entry:
            return

        # Only try to open and position the file if it is transient
        view = window.find_open_file(self.current_history_entry['filename'])
        if self.is_transient_view(window, view):
            (group, index) = self.__calculate_view_index(window, self.current_history_entry)
            view = window.open_file(self.current_history_entry['filename'])
            window.set_view_index(view, group, index)

        # Refocus on the newly opened file rather than the original one
        self.__clear_context()
        self.__track_calling_view(window)

    def delete_current_entry(self):
        """Delete the history entry for the  file that is currently being previewed"""
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

        # Open the file and position the view correctly
        new_view = window.open_file(history_entry['filename'])
        window.set_view_index(new_view, group, index)
        self.debug('Opened file in group %s, index %s (based on saved group %s, index %s): %s' % (group, index, history_entry['group'], history_entry['index'], history_entry['filename']))

        # Add the file we just opened to the history and clear the context
        self.add_view(window, new_view, 'opened')
        self.__clear_context()

    def __close_preview(self, window):
        if not self.SHOW_FILE_PREVIEW:
            return

        if self.calling_view_is_empty:
            # focusing the saved calling_view doesn't work, so close the last preview view
            window.run_command("close_file")
        else:
            window.focus_view(self.calling_view)

    def reset(self, window):
        """The user cancelled the action - give the focus back to the "calling" view and clear the context"""
        self.__close_preview(window)
        self.__clear_context()

    def is_transient_view(self, window, view):
        if is_ST2:
            return False

        return view == window.transient_view_in_group(window.active_group()) or not view


class OpenRecentlyClosedFileEvent(sublime_plugin.EventListener):
    """class to keep a history of the files that have been opened and closed"""
    def on_pre_close(self, view):
        FileHistory.instance().add_view(sublime.active_window(), view, 'closed')

    def on_load(self, view):
        FileHistory.instance().add_view(sublime.active_window(), view, 'opened')


class CleanupFileHistoryCommand(sublime_plugin.WindowCommand):
    def run(self, current_project_only=True):
        FileHistory.instance().clean_history(current_project_only)


class ResetFileHistoryCommand(sublime_plugin.WindowCommand):
    def run(self):
        FileHistory.instance().delete_all_history()


class QuickOpenFileHistoryCommand(sublime_plugin.WindowCommand):
    def run(self):
        FileHistory.instance().quick_open_preview(sublime.active_window())


class DeleteFileHistoryEntryCommand(sublime_plugin.WindowCommand):
    def run(self):
        FileHistory.instance().delete_current_entry()


class OpenRecentlyClosedFileCommand(sublime_plugin.WindowCommand):
    """class to either open the last closed file or show a quick panel with the recent file history (closed files first)"""

    __is_active = False

    def approximate_age(self, current_time, timestamp, precision=2):
        # loosely based on http://codereview.stackexchange.com/questions/37285/efficient-human-readable-timedelta
        diff = current_time - datetime.datetime.strptime(timestamp, FileHistory.instance().TIMESTAMP_FORMAT)

        def divide(rem, mod):
            return rem % mod, int(rem // mod)

        def subtract(rem, div):
            n = int(rem // div)
            return n,  rem - n * div

        rem = diff.total_seconds()
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

    def run(self, show_quick_panel=True, current_project_only=True, selected_file=None):
        self.history_list = FileHistory.instance().get_history(current_project_only)
        if show_quick_panel:
            current_time = datetime.datetime.now()
            # Prepare the display list with the file name and path separated
            display_list = []
            for node in self.history_list:
                filepath = node['filename']
                info = [os.path.basename(filepath), os.path.dirname(filepath)]

                # Only include the timestamp if it is there and if the user wants to see it
                if FileHistory.instance().DISPLAY_TIMESTAMPS:
                    (action, timestamp) = FileHistory.instance().get_history_timestamp(node)

                    if FileHistory.instance().TIMESTAMP_DISPLAY_TYPE == "relative":
                        stamp = '   %s ~%s ago' % (action, self.approximate_age(current_time, timestamp))
                    else:
                        stamp = '   %s on %s' % (action, timestamp)
                    info.append('   ' + stamp)

                display_list.append(info)
            font_flag = sublime.MONOSPACE_FONT if FileHistory.instance().USE_MONOSPACE else 0

            self.__class__.__is_active = True

            if is_ST2:
                self.window.show_quick_panel(display_list, self.open_file, font_flag)
            else:
                self.window.show_quick_panel(display_list, self.open_file, font_flag, on_highlight=self.show_preview)
        else:
            self.open_file(0)

    @classmethod
    def is_active(cls):
        '''
        Returns whether the history overlay is open in a window. Note that
        only the currently focused window can have an open overlay.
        '''

        return cls.__is_active

    def is_valid(self, selected_index):
        return selected_index >= 0 and selected_index < len(self.history_list)

    def show_preview(self, selected_index):
        # Note: This function will never be called in ST2
        if self.is_valid(selected_index):
            FileHistory.instance().preview_history(self.window, self.history_list[selected_index])

    def open_file(self, selected_index):
        self.__class__.__is_active = False

        if self.is_valid(selected_index):
            FileHistory.instance().open_history(self.window, self.history_list[selected_index])
        else:
            # The user cancelled the action
            FileHistory.instance().reset(self.window)

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
