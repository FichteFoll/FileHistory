# TODO some restructuring
# DONE option to cleanup the history database (json) on start
# DONE introduce a settings file to get settings from
# DONE [ST3] use api function (only available in ST3) to get the project name/id (rather than using a hash of the project folders)
# DONE [ST3] preview the file while cycling through the quick panel history entries
# DONE [ST3] support "quick open" from the quick panel (mapped by default to the "right" key)
# DONE [ST3] removed unnecessary view settings (and associated code) by listening for the on_pre_close event rather than the on_close event
# DONE added setting for using monospaced font in the quick panel
# DONE fixed ST2 support
import sublime
import sublime_plugin
import os
import hashlib
import json

is_ST2 = int(sublime.version()) < 3000

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
        self.sublime_settings = sublime.load_settings('Preferences.sublime-settings')
        self.SETTINGS_FILE = 'FileHistory.sublime-settings'
        self.PRINT_DEBUG = False
        self.__load_settings()
        self.__load_history()
        self.__clear_context()

        if self.CLEANUP_ON_STARTUP and not is_ST2:
            sublime.set_timeout_async(lambda: self.clean_history(False) , 0)

    def __load_settings(self):
        """Load the plugin settings from FileHistory.sublime-settings"""
        app_settings = sublime.load_settings(self.SETTINGS_FILE)
        settings_exist = app_settings.has('history_file')

        self.PRINT_DEBUG = self.__ensure_setting(app_settings, 'debug', True)
        self.GLOBAL_MAX_ENTRIES = self.__ensure_setting(app_settings, 'global_max_entries', 100)
        self.PROJECT_MAX_ENTRIES = self.__ensure_setting(app_settings, 'project_max_entries', 50)
        self.USE_SAVED_POSITION = self.__ensure_setting(app_settings, 'use_saved_position', True)
        self.NEW_TAB_POSITION = self.__ensure_setting(app_settings, 'new_tab_position', 'next')
        self.REMOVE_NON_EXISTENT_FILES = self.__ensure_setting(app_settings, 'remove_non_existent_files_on_preview', True)
        self.CLEANUP_ON_STARTUP = self.__ensure_setting(app_settings, 'cleanup_on_startup', True)
        history_path = self.__ensure_setting(app_settings, 'history_file', 'User/FileHistory.json')
        self.HISTORY_FILE = os.path.normpath(os.path.join(sublime.packages_path(), history_path))
        self.USE_MONOSPACE = self.__ensure_setting(app_settings, 'use_monospace_font', False)
        # Ignore the file preview setting for ST2
        self.SHOW_FILE_PREVIEW = False if is_ST2 else self.__ensure_setting(app_settings, 'show_file_preview', True)

        if not settings_exist:
            print('[FileHistory] Unable to find the settings file "%s".  A default settings file has been created for you.' % (self.SETTINGS_FILE))
            sublime.save_settings(self.SETTINGS_FILE)

    def __ensure_setting(self, settings, key, default_value):
        value = default_value
        if settings.has(key):
            value = settings.get(key)
            self.debug('FileHistory setting "%s" = "%s"' % (key, value))
        else:
            self.debug('FileHistory setting "%s" not found.  Using the default value of "%s"' % (key, default_value))
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

        f = open(self.HISTORY_FILE, 'r')
        try:
            updated_history = json.load(f)
        finally:
            f.close()

        self.history = updated_history

    def __save_history(self):
        self.debug('Saving the history to file ' + self.HISTORY_FILE)
        f = open(self.HISTORY_FILE, mode='w+')
        try:
            json.dump(self.history, f, indent=4)
            f.flush()
        finally:
            f.close()

    def get_history(self, current_project_only=True):
        """Return the requested history (global or project-specific): closed files followed by opened files"""

        # Make sure the history is loaded
        if len(self.history) == 0:
            self.__load_history()

        # Load the requested history (global or project-specific)
        if current_project_only:
            project_name = self.get_current_project_key()
        else:
            project_name = 'global'

        # Return the list of closed and opened files
        if project_name in self.history:
            return self.history[project_name]['closed'] + self.history[project_name]['opened']
        else:
            self.debug('WARN: Project %s could not be found in the file history list - returning an empty history list' % (project_name))
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
        if filename != None:
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
        node = {'filename': filename, 'group':group, 'index':index}
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

    def __track_calling_view(self, window):
        """Remember the view that the command was run from (including the group and index positions),
        so we can return to the "calling" view if the user cancels the preview
        (or so we can show something if a file in the history no longer exists)"""
        if not self.calling_view:
            self.calling_view = window.active_view()
            #self.calling_view_index = window.get_view_index(self.calling_view)
            #self.calling_view_is_empty = len(window.views()) == 0
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

        # Only preview the view if the user wants to see it
        if not self.SHOW_FILE_PREVIEW: return

        self.__track_calling_view(window)

        filepath = history_entry['filename']
        if os.path.exists(filepath):
            self.current_view = window.open_file(filepath, sublime.TRANSIENT)
        else:
            # Close the last preview and remove the non-existent file from the history
            self.__close_preview(window)
            self.__remove_view(filepath, self.get_current_project_key(), True)

    def on_file_history_open(self):
        # Set a special setting so we can isolate the context for the quick-open command's keymap entry
        self.sublime_settings.set('file_history_active', True)

    def on_file_history_closed(self):
        # Remove the special setting that was set when the quick panel was opened
        self.sublime_settings.erase('file_history_active')

    def quick_open_preview(self, window):
        """Open the file that is currently being previewed"""
        if not self.current_history_entry: return

        # Only try to open and position the file if it is transient
        view = window.find_open_file(self.current_history_entry['filename'])
        if self.is_transient_view(window, view):
            (group, index) = self.__calculate_view_index(window, self.current_history_entry)
            view = window.open_file(self.current_view.file_name())
            window.set_view_index(view, group, index)

        # Refocus on the newly opened file rather than the original one
        self.__clear_context()
        self.__track_calling_view(window)

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
        if not self.SHOW_FILE_PREVIEW: return

        if self.calling_view_is_empty:
            # focusing the saved calling_view doesn't work, so close the last preview view
            window.run_command("close_file")
        else:
            window.focus_view( self.calling_view )

    def reset(self, window):
        """The user cancelled the action - give the focus back to the "calling" view and clear the context"""
        self.__close_preview(window)
        self.__clear_context()

    def is_transient_view(self, window, view):
        if is_ST2: return False

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


class QuickOpenFileHistoryCommand(sublime_plugin.WindowCommand):
    def run(self):
        FileHistory.instance().quick_open_preview(sublime.active_window())


class OpenRecentlyClosedFileCommand(sublime_plugin.WindowCommand):
    """class to either open the last closed file or show a quick panel with the recent file history (closed files first)"""

    def run(self, show_quick_panel=True, current_project_only=True):
        self.history_list = FileHistory.instance().get_history(current_project_only)
        if show_quick_panel:
            # Prepare the display list with the file name and path separated
            display_list = []
            for node in self.history_list:
                filepath = node['filename']
                display_list.append([os.path.basename(filepath), os.path.dirname(filepath)])
            font_flag = sublime.MONOSPACE_FONT if FileHistory.instance().USE_MONOSPACE else 0

            FileHistory.instance().on_file_history_open()

            if is_ST2:
                self.window.show_quick_panel(display_list, self.open_file, font_flag)
            else:
                self.window.show_quick_panel(display_list, self.open_file, font_flag, on_highlight=self.show_preview)
        else:
            self.open_file(0)

    def is_valid(self, selected_index):
        return selected_index >= 0 and selected_index < len(self.history_list)

    def show_preview(self, selected_index):
        # Note: This function will never be called in ST2
        if self.is_valid(selected_index):
            FileHistory.instance().preview_history(self.window, self.history_list[selected_index])

    def open_file(self, selected_index):
        FileHistory.instance().on_file_history_closed()

        if self.is_valid(selected_index):
            FileHistory.instance().open_history(self.window, self.history_list[selected_index])
        else:
            # The user cancelled the action
            FileHistory.instance().reset(self.window)

        self.history_list = {}
