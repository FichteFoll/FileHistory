# SublimeText - File History #

**Sublime Text 2 and 3** plugin to provide access to the history of accessed files - project-wise or globally. Stores data in a JSON file. The most recently closed file can be instantly re-opened with a keyboard shortcut or the user can search through the entire file history within the quick panel (including file preview and the ability to open multiple files).  

## Features ##

Keeps a history of the files that you have accessed in SublimeText (on both a per-project and global level).  The most recently closed file can be instantly re-opened with a keyboard shortcut (default is ```ctrl+shift+t```) or the user can search through the entire file history in the quick panel (default is ```ctrl+alt+t``` for the current project and ```ctrl+alt+shift+t``` for the global history).  

Overview of features:
* [FileHistory.sublime-settings][Settings] file to customize the functionality.  **You will need to restart Sublime Text after editing the [FileHistory.sublime-settings][settings] file (because the settings are cached by the Sublime Text API).**
* When re-opening a file from the history, choose the position to open it in: the ```first``` tab, the ```last``` tab, the ```next``` tab (```new_tab_position``` setting) or in the position that it was when it was closed (by setting the ```use_saved_position``` setting to ```true```)
* Display a preview of the file while looking through the file history in the quick panel (only Sublime Text 3) (by setting the ```show_file_preview``` setting to ```true```)
* Choose target location where the file history should be saved.  The default ```history_file``` setting is ```User/FileHistory.json``` (in the packages directory)
* Optionally remove any non-existent files while looking through the file history (when previewed or opened) (by setting the ```remove_non_existent_files_on_preview``` setting to ```true```)
* Optionally clean up the history on start-up (by setting the ```cleanup_on_startup``` setting to ```true```)
* Optionally display the quick panel entries with a monospaced font (by setting the ```use_monospace_font``` setting to ```true```)
* Open multiple history entries from the quick panel with the ```right``` key (requires a keymap entry - see [Default.sublime-keymap][keymap] ([OSX][keymap-osx]))

Originally obtained from a [gist][gist] by Josh Bjornson.


## Installation ##

**With [Package Control][pck-ctrl]**: Once installed, bring up the Command Palette (`Command-Shift-P` on OS X, `Ctrl-Shift-P` on Linux/Windows). Select `Package Control: Install Package` and then select `File History` when the list appears. Package Control will automagically keep the plugin up to date with the latest version.

**Without Git**: Download the latest source from [GitHub][github] ([.zip][zipball]) and copy the folder to your Sublime Text "Packages" directory (you might want to rename it to "File History" before).

**With Git**: Clone the repository in a subfolder "File History" in your Sublime Text "Packages" directory:

    git clone git://github.com/FichteFoll/sublimetext-filehistory.git


The "Packages" directory (for ST2) is located at:

* Linux: `~/.config/sublime-text-2/Packages/`
* OS X: `~/Library/Application Support/Sublime Text 2/Packages/`
* Windows: `%APPDATA%/Sublime Text 2/Packages/`

Or enter
```print(sublime.packages_path())
```
into the console (`` Ctrl-` ``).


## Usage ##

To use the plugin, open the Command Palette and search for `File History:`.

For default keymap definitions, see [Default.sublime-keymap][keymap] ([OSX][keymap-osx]).

For the default settings, see [FileHistory.sublime-settings][settings].

### Images ###

*The popup for the current project only*
![example1][img1]

*The popup for the global history with text*
![example1][img2]

### Commands ###

**open_recently_closed_file** (Window)

Opens a popup with recently closed files or reopens the lastly closed view if `show_quick_panel == False`.

>   *Parameters*

>   - **show_quick_panel** (bool) - *Default*: `True`

>   - **current_project_only** (bool) - *Default*: `True`

**cleanup_file_history** (Window)

Checks the current project or the whole history for non-existent files and removes them from the history kept.

>   *Parameters*

>   - **current_project_only** (bool) - *Default*: `True`




[gist]: https://gist.github.com/1133602
[github]: https://github.com/FichteFoll/sublimetext-filehistory "Github.com: FichteFoll/sublime-filehistory"
[zipball]: https://github.com/FichteFoll/sublimetext-filehistory/zipball/master
[pck-ctrl]: http://wbond.net/sublime_packages/package_control "Sublime Package Control by wbond"

[settings]: FileHistory.sublime-settings "FileHistory.sublime-settings"

[keymap]: Default.sublime-keymap "Default.sublime-keymap"
[keymap-osx]: Default%20%28OSX%29.sublime-keymap "Default (OSX).sublime-keymap"

[img1]: http://i.imgur.com/6eB4c.png
[img2]: http://i.imgur.com/MzCQH.png

