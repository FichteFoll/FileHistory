File History Changelog
======================

v1.4.5 (2014-01-15)
-------------------

- Fix for ST2 compatibility

v1.4.4 (2014-01-10)
-------------------

- Quick-open: Refocus on the newly opened file rather than the origional one


v1.4.3 (2014-01-10)
-------------------

- Updated the version number in messages.json and CHANGELOG.md

v1.4.2 (2014-01-10)
-------------------

- Added MIT license


v1.4.1 (2014-01-10)
-------------------

- Updated the version number in messages.json

v1.4.0 (2014-01-10)
-------------------

- Fixed some issues in the README and added a settings section
- Updated the version number to reflect significance of the added functionality

v1.3.5 (2014-01-09)
-------------------

- Added settings file to simplify customization
- ST3 only: Preview the history entries while searching through the quick panel
- ST3 only: Remove files that no longer exist while searching through the quick panel
- ST3 only: Added option to cleanup this history on startup (remove any files that no longer exist)
- Show the quick panel with a monospace font
- Customize where the history data is stored
- Option to try to re-use the position the file was in when it was closed
- A default settings file will be created if one does not exist (default is User/FileHistory.json in the packages directory)


v1.3.3 (2013-12-17)
-------------------

- Added commands to the command palette and removed cleanup command from keybindings (by @stdword)


v1.3.2 (2013-11-11)
-------------------

- ST3 only: The files are now previewed when cycling through the quick panel entries
- Add some status messages for cleanup command


v1.3.1 (2013-03-01)
-------------------

- Fix unicode bug introduced in ST 3014
- Use the newly implemented project file path API for saving per-project history instead of hashing the project's folders
- Remove remaining settings migration code (not really worth mentioning)
- Add messages for Package Control install and updates


v1.3.0 (2013-02-04)
-------------------

- Sublime Text 3 compatability
- Remove old settings migration code (this probably won't bother you unless you've been using this plugin for years)
- Adjust OSX key bindings to not use ctrl


v1.1 (2012-06-14)
-----------------

- Add key bindings and menu entries


v1.0 (2012-05-18)
-----------------

- Mirrored from [gist](https://gist.github.com/1133602) with most of their functionality
