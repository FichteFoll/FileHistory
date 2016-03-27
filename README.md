# SublimeText - File History #

**Sublime Text 2 and 3** plugin to provide access to the history of accessed files - project-wise or globally. The most recently closed file can be instantly re-opened with a keyboard shortcut or the user can search through the entire file history within the quick panel (including file preview and the ability to open multiple files).

![Example Image][img2]


## Features ##

Keeps a history of the files that you have accessed in SublimeText (on both a per-project and global level). The most recently closed file can be instantly re-opened with a keyboard shortcut or the user can search through the entire file history in the quick panel.

Overview of features:

* [FileHistory.sublime-settings][] file to customize functionality
* When re-opening a file from the history, choose the position to open it in: the `first` tab, the `last` tab, the `next` tab or in the position that it was when it was closed
* Display a preview of the file while looking through the file history in the quick panel (only Sublime Text 3)
* Choose target location where the file history should be saved
* Optionally remove any non-existent files while looking through the file history (when previewed or opened) or on start-up
* Open multiple history entries from the quick panel with the <kbd>Right</kbd> key
* Delete history entries from the quick panel with <kbd>Ctrl+Del</kbd>
* Path exclude and re-include patterns (regex) that can be extended in project settings


## Installation ##

Install [Package Control][pck-ctrl]. Once installed, bring up the Command Palette (`Command-Shift-P` on OS X, `Ctrl-Shift-P` on Linux/Windows). Select `Package Control: Install Package` and then select `File History` when the list appears. Package Control will automagically keep the plugin up to date with the latest version.


## Usage ##

To use the plugin, open the Command Palette and search for `File History:`.

When you opened a panel you can use the <kbd>right</kbd> key to open the file and keep the panel open, or <kbd>Ctrl/Cmd</kbd> + <kbd>delete</kbd> to remove the selected file from the history.

For default keymap definitions, see [Default.sublime-keymap][keymap] ([OSX][keymap-osx]).

For the available and default settings, see [FileHistory.sublime-settings][].

### Images ###

*The popup for the current project only*
![example1][img1]

*The popup for the global history with text*
![example1][img2]

### Project Settings ###

You can **extend** the `path_exclude_patterns` and `path_reinclude_patterns` lists in your project settings.

For this, add a `"file_history"` dictionary to your project's settings and then one or both of the settings to that. Example:

```json
{
    "folders": [
        {
            "path": "."
        }
    ],
    "settings": {
        "file_history": {
            "path_exclude_patterns": ["/bin/"],
            "path_reinclude_patterns": ["\\.compiled$"]
        }
    }
}
```

### Commands ###

**open_recently_closed_file** (Window)

Opens a popup with recently closed files or reopens the lastly closed view if `action == "open_latest_closed"`.

>   *Parameters*

>   - **action** (str) - *Default*: `"show_history"`, *Allowed values*: `"show_history"`, `"open_latest_closed"`

>   - **current_project_only** (bool) - *Default*: `True`

**cleanup_file_history** (Window)

Checks the current project or the whole history for non-existent files and removes them from the history kept.

>   *Parameters*

>   - **current_project_only** (bool) - *Default*: `True`

**reset_file_history** (Window)

Removes all file history data.


[github]: https://github.com/FichteFoll/sublimetext-filehistory "Github.com: FichteFoll/sublime-filehistory"
[pck-ctrl]: http://wbond.net/sublime_packages/package_control "Sublime Package Control by wbond"

[FileHistory.sublime-settings]: FileHistory.sublime-settings

[keymap]: Default.sublime-keymap "Default.sublime-keymap"
[keymap-osx]: Default%20%28OSX%29.sublime-keymap "Default (OSX).sublime-keymap"

[img1]: http://i.imgur.com/B5ViHHv.png
[img2]: http://i.imgur.com/y40CEFo.png
