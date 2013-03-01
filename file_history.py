'''
@author Josh Bjornson

This work is licensed under the Creative Commons Attribution-ShareAlike 3.0 Unported License.
To view a copy of this license, visit http://creativecommons.org/licenses/by-sa/3.0/
or send a letter to Creative Commons, 171 Second Street, Suite 300, San Francisco, California, 94105, USA.
'''

# TODO some restructuring
# TODO introduce a settings file to get settings from
# TODO option to cleanup the history database (json) on start
# TODO use api function (implemented in ST3) to get the project name/id (rather than using a hash of the project folders)

import sublime
import sublime_plugin
import os
import hashlib
import json

# Maximum number of history entries we should keep (older entries truncated)
GLOBAL_MAX_ENTRIES  = 50
PROJECT_MAX_ENTRIES = 20

# Which position to open a file at when the saved index in no longer valid
# (e.g. after a migration or if the saved index is non-existent).
# Options are: next tab and last tab
(TAB_POSITION_NEXT, TAB_POSITION_LAST) = ('next', 'last')
DEFAULT_NEW_TAB_POSITION = TAB_POSITION_LAST

# Print out the debug text?
PRINT_DEBUG = False


# Helper methods for "logging" to the console.
def debug(text):
    if PRINT_DEBUG:
        log(text)


def log(text):
    print('[%s] %s' % ('FileHistory', text))


# Class to read and write the file-access history.
class FileHistory(object):
    _instance = None

    """Basic singleton implementation"""
    @classmethod
    def instance(cls):
        if not cls._instance:
            cls._instance = cls()
        return cls._instance

    """Class to manage the file-access history"""
    def __init__(self):
        self.history_file = os.path.join(sublime.packages_path(), 'User', 'FileHistory.json')

        self.history = {}
        self.__load_history()

    def get_current_project_hash(self):
        m = hashlib.md5()
        for path in sublime.active_window().folders():
            m.update(path.encode('utf-8'))
        return m.hexdigest()

    def __load_history(self):
        debug('Loading the history from file ' + self.history_file)
        if not os.path.exists(self.history_file):
            return

        f = open(self.history_file, 'r')
        try:
            updated_history = json.load(f)
        finally:
            f.close()

        self.history = updated_history

    def __save_history(self):
        debug('Saving the history to file ' + self.history_file)
        f = open(self.history_file, mode='w+')
        try:
            json.dump(self.history, f, indent=4)
            f.flush()
        finally:
            f.close()

    def get_history(self, current_project_only=True):
        """Return the requested history (global or project-specific): opened files followed by closed files"""

        # Make sure the history is loaded
        if len(self.history) == 0:
            self.__load_history()

        # Load the requested history (global or project-specific)
        if current_project_only:
            project_name = self.get_current_project_hash()
        else:
            project_name = 'global'

        # Return the list of closed and opened files
        if project_name in self.history:
            return self.history[project_name]['closed'] + self.history[project_name]['opened']
        else:
            debug('WARN: Project %s could not be found in the file history list - returning an empty history list' % (project_name))
            return []

    def __ensure_project(self, project_name):
        """Make sure the project nodes exist (including 'opened' and 'closed')"""
        if project_name not in self.history:
            self.history[project_name] = {}
            self.history[project_name]['opened'] = []
            self.history[project_name]['closed'] = []

    def add_view(self, view, history_type):
        # Get the file details from the view
        filename = os.path.normpath(view.file_name()) if view.file_name() else None
        # Only keep track of files that exist (that have already been saved)
        if filename != None:
            project_name = self.get_current_project_hash()
            (group, index) = sublime.active_window().get_view_index(view)

            if os.path.exists(filename):
                # Add to both the project-specific and global histories
                self.__add_to_history(project_name, history_type, filename, group, index)
                self.__add_to_history('global', history_type, filename, group, index)
            else:
                # If the file doesn't exist then remove it from the lists
                debug('The file no longer exists, so it has been removed from the history: ' + filename)
                self.__remove(project_name, filename)
                self.__remove('global', filename)

            self.__save_history()

    def __add_to_history(self, project_name, history_type, filename, group, index):
        debug('Adding %s file to project %s with group %s and index %s: %s' % (history_type, project_name, group, index, filename))

        # Make sure the project nodes exist
        self.__ensure_project(project_name)

        # Remove the file from the project list then
        # add it to the top (of the opened/closed list)
        self.__remove(project_name, filename)
        node = {'filename': filename, 'group': group, 'index': index}
        self.history[project_name][history_type].insert(0, node)

        # Make sure we limit the number of history entries
        max_num_entries = GLOBAL_MAX_ENTRIES if project_name == 'global' else PROJECT_MAX_ENTRIES
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

    def clean_history(self, project_name):
        # Only continue if this project exists
        if project_name not in self.history:
            return

        # Remove any non-existent files from the project
        for history_type in ('opened', 'closed'):
            for node in reversed(self.history[project_name][history_type]):
                if not os.path.exists(node['filename']):
                    self.history[project_name][history_type].remove(node)

        self.__save_history()


class OpenRecentlyClosedFileEvent(sublime_plugin.EventListener):
    """class to keep a history of the files that have been opened and closed"""

    def on_close(self, view):
        FileHistory.instance().add_view(view, 'closed')

    def on_load(self, view):
        FileHistory.instance().add_view(view, 'opened')


class CleanupFileHistoryCommand(sublime_plugin.WindowCommand):
    def run(self, current_project_only=True):
        # Cleanup the current project
        h = FileHistory.instance()
        h.clean_history(h.get_current_project_hash())

        # If requested, also cleanup the global history
        if not current_project_only:
            h.clean_history('global')


class OpenRecentlyClosedFileCommand(sublime_plugin.WindowCommand):
    """class to either open the last closed file or show a quick panel with the recent file history (closed files first)"""

    def run(self, show_quick_panel=True, current_project_only=True):
        # Prepare the display list with the file name and path separated
        self.history_list = FileHistory.instance().get_history(current_project_only)
        display_list = []
        for node in self.history_list:
            file_path = node['filename']
            display_list.append([os.path.basename(file_path), os.path.dirname(file_path)])

        if show_quick_panel:
            self.window.show_quick_panel(display_list, self.open_file, True)
        else:
            self.open_file(0)

    def open_file(self, selected_index):
        if selected_index >= 0 and selected_index < len(self.history_list):
            node = self.history_list[selected_index]

            # Get the group of the new view (default is the currently active group)
            group = node['group']
            if group < 0 or group >= self.window.num_groups():
                group = self.window.active_group()

            # Get the alternative tab index (in case the saved index in no longer valid):
            # The file could be opened in the last tab (max_index) or after the current tab (next_index)...
            max_index = len(self.window.views_in_group(group))
            if max_index:
                next_index = self.window.get_view_index(self.window.active_view_in_group(group))[1] + 1
            else:
                next_index = 0

            # Get the index of the new view
            index = node['index']
            if index < 0 or index > max_index:
                index = next_index if DEFAULT_NEW_TAB_POSITION == TAB_POSITION_NEXT else max_index

            debug('Opening file in group %s, index %s (based on saved group %s, index %s): %s' % (group, index, node['group'], node['index'], node['filename']))

            # Open the file and position the view correctly
            new_view = self.window.open_file(node['filename'])
            self.window.set_view_index(new_view, group, index)
