'''
@author Josh Bjornson

This work is licensed under the Creative Commons Attribution-ShareAlike 3.0 Unported License.
To view a copy of this license, visit http://creativecommons.org/licenses/by-sa/3.0/
or send a letter to Creative Commons, 171 Second Street, Suite 300, San Francisco, California, 94105, USA.
'''
import sublime
import sublime_plugin
import os
import shutil
import hashlib
import json

# Plugin to provide access to the history of accessed files:
# https://gist.github.com/1133602
#
# The plugin stores a JSON file with the file history.
#
# Note: I tried checking for file existence in the history but this
# took more time than expected (especially with networked files) and
# made the plugin quite unresponsive.  The compromise is a command
# to cleanup the current project (with the option to clean up the
# global list as well).  The cleanup will remove any files in the
# project history that don't exist.
#
# To run the plugin:
# view.run_command("open_recently_closed_file")
#
# Keymap entries:
# { "keys": ["ctrl+shift+t"], "command": "open_recently_closed_file"},
# { "keys": ["ctrl+alt+shift+t"], "command": "open_recently_closed_file", "args": {"show_quick_panel": false}  },
# { "keys": ["ctrl+alt+shift+t"], "command": "open_recently_closed_file", "args": {"current_project_only": false}  },
# { "keys": ["ctrl+alt+shift+c"], "command": "cleanup_file_history", "args": {"current_project_only": false}  },
#
# TODO use api function (not yet available) to get the project name/id (rather than using a hash of the project folders)
# TODO Get the settings below from a sublime-settings file?

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
    print '[%s] %s' % ('FileHistory', text)


# Class to read and write the file-access history.
class FileHistory(object):

    """Class to manage the file-access history"""
    def __init__(self):
        self.history_file = os.path.join(sublime.packages_path(), 'User', 'FileHistory.json')
        self.old_history_file = os.path.join(sublime.packages_path(), 'User', 'FileHistory.sublime-settings')
        self.archive_file = os.path.join(sublime.packages_path(), 'User', 'FileHistory.archive')

        # Copy over the old settings for migration (if new settings don't yet exist)
        # and rename the old settings file.
        if os.path.exists(self.old_history_file) and not os.path.exists(self.history_file):
            shutil.copyfile(self.old_history_file, self.history_file)
            shutil.move(self.old_history_file, self.archive_file)

        self.history = {}

        self.__load_history()

    def get_current_project_hash(self):
        m = hashlib.md5()
        for path in sublime.active_window().folders():
            m.update(path)
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

        # If this is in the old format, then migrate (the new format has a
        # 'global' file list rather than top level 'opened' and 'closed' lists)
        if 'opened' in updated_history:
            log('History is in the old format and will be migrated')
            self.__migrate_history(updated_history)
        else:
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

    def __migrate_history(self, archive):
        # Reset the history
        self.history = {}

        # Migrate the existing history to the new format
        for node_name in iter(archive):
            # Get the project name and history type (opened or closed) for this history entry
            if node_name in ('opened', 'closed'):
                project_name = 'global'
                history_type = node_name
            else:
                (project_name, history_type) = node_name.split('_', 1)

            # Migrate all of the history entries for this project to the new format
            for filename in iter(archive[node_name]):
                debug('Migrating %s file %s in project %s...' % (history_type, filename, project_name))

                # Make sure the project nodes exist
                self.__ensure_project(project_name)

                # Add the file to the end of the opened/closed list
                node = {'filename': filename, 'group': -1, 'index': -1}
                self.history[project_name][history_type].append(node)

        self.__save_history()

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


# Global file history instance
hist = FileHistory()


class OpenRecentlyClosedFileEvent(sublime_plugin.EventListener):
    """class to keep a history of the files that have been opened and closed"""

    def on_close(self, view):
        hist.add_view(view, 'closed')

    def on_load(self, view):
        hist.add_view(view, 'opened')


class CleanupFileHistoryCommand(sublime_plugin.WindowCommand):
    def run(self, current_project_only=True):
        # Cleanup the current project
        hist.clean_history(hist.get_current_project_hash())

        # If requested, also cleanup the global history
        if not current_project_only:
            hist.clean_history('global')


class OpenRecentlyClosedFileCommand(sublime_plugin.WindowCommand):
    """class to either open the last closed file or show a quick panel with the recent file history (closed files first)"""

    def run(self, show_quick_panel=True, current_project_only=True):
        # Prepare the display list with the file name and path separated
        self.history_list = hist.get_history(current_project_only)
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
            next_index = self.window.get_view_index(self.window.active_view_in_group(group))[1] + 1

            # Get the index of the new view
            index = node['index']
            if index < 0 or index > max_index:
                index = next_index if DEFAULT_NEW_TAB_POSITION == TAB_POSITION_NEXT else max_index

            debug('Opening file in group %s, index %s (based on saved group %s, index %s): %s' % (group, index, node['group'], node['index'], node['filename']))

            # Open the file and position the view correctly
            new_view = self.window.open_file(node['filename'])
            self.window.set_view_index(new_view, group, index)
