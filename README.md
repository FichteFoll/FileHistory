# SublimeText - File History #

**Sublime Text 2 and 3** plugin to provide access to the history of accessed files - project-wise or globally. Stores data in a JSON file.

Obtained from a [https://gist.github.com/1133602][gist] by Josh Bjornson.


**Note**: I tried checking for file existence in the history but this took more time than expected (especially with networked files) and made the plugin quite unresponsive. The compromise is a command to cleanup the current project (with the option to clean up the global list as well). The cleanup will remove any files in the project history that don't exist.


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
```python
sublime.packages_path()
```
into the console (`` Ctrl-` ``).


## Usage ##

To use the plugin, open the Command Palette and search for `File History:`.

For default keymap definitions, see [Default.sublime-keymap][keymap] ([OSX][keymap-osx]).

### Images ###

*The popup for the current project only*
![example1][img1]

*The popup for the global history with text*
![example1][img2]

### Commands ###

**open_recently_closed_file** (Window)

Opens a popup with recently closed files or reopens the lastly closed view if `show_quick_panel == False`.

>	*Parameters*

>	- **show_quick_panel** (bool) - *Default*: `True`

>	- **current_project_only** (bool) - *Default*: `True`

**cleanup_file_history** (Window)

Checks the current project or the whole history for non-existent files and removes them from the history kept.

>	*Parameters*

>	- **current_project_only** (bool) - *Default*: `True`


## ToDo ##

- A settings file (and using the information from there) (#7)
- Option to cleanup when starting Sublime (#7)


[gist]: https://gist.github.com/1133602
[github]: https://github.com/FichteFoll/sublimetext-filehistory "Github.com: FichteFoll/sublime-filehistory"
[zipball]: https://github.com/FichteFoll/sublimetext-filehistory/zipball/master
[pck-ctrl]: http://wbond.net/sublime_packages/package_control "Sublime Package Control by wbond"

[keymap]: Default.sublime-keymap "Default.sublime-keymap"
[keymap-osx]: Default%20%28OSX%29.sublime-keymap "Default (OSX).sublime-keymap"

[img1]: http://i.imgur.com/6eB4c.png
[img2]: http://i.imgur.com/MzCQH.png
