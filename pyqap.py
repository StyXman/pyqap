#! /usr/bin/env python3

'''
PyQap application: backup with rsync by selecting exactly what and what not to backup, with dir/file sizes.
'''

import os
# from pprint import pprint
import sys

from typing import Optional# , List

from PyQt6.QtWidgets import QApplication, QWidget  # pylint: disable=no-name-in-module


class Entry:
    '''Entries have a root, a name, a local size, a total size, and a list of children.'''
    def __init__(self, root:str, name:str, size:int, full_size:Optional[int], children:Optional[list]):
        self.root = root
        self.name = name
        self.size = size
        self.full_size = full_size
        self.children = children


    def append(self, child):
        '''Apeend a child and update sizes as needed.'''
        self.children.append(child)
        if child.children is None:
            # file
            self.size += child.size
            self.full_size += child.size
        else:
            # dir
            self.full_size += child.full_size


def find_files(start: str) -> Entry:
    '''Return an Entry representing the start directory.'''
    entries = { start: Entry(start, '.', 0, 0, []) }  # type: dict[str, Entry]

    for root, dirs, files, root_fd in os.fwalk(start):
        root_entry = entries[root]

        for dir in dirs:  # pylint: disable=redefined-builtin
            entry = Entry(root, dir, 0, 0, [])
            entries[os.path.join(root, dir)] = entry
            root_entry.append(entry)

        for file in files:
            file_size = os.stat(file, dir_fd=root_fd).st_size
            entry = Entry(root, file, file_size, None, None)
            root_entry.append(entry)

    return entries[start]


def test():
    '''crappy test function until we grow.'''
    root_entry = Entry('root', '.', 0, 0, [])
    first_file = Entry('root', 'first_file', 10, None, None)
    root_entry.append(first_file)

    assert root_entry.size == 10
    assert root_entry.full_size == 10

    first_subdir = Entry('root', 'first_subdir', 0, 0, [])
    second_file = Entry('root/first_subdir', 'second_file', 100, None, None)
    first_subdir.append(second_file)

    assert first_subdir.size == 100
    assert first_subdir.full_size == 100

    root_entry.append(first_subdir)

    assert root_entry.size == 10
    assert root_entry.full_size == 110


    ##################################################################

    root = find_files('tests/find_files')
    dirs = [ entry for entry in root.children if entry.children is not None ]
    files = [ entry for entry in root.children if entry.children is None ]

    assert len(dirs) == 2, f"""{dirs=}"""
    assert len(files) == 5, f"""{files=}"""


def main():
    ''' Main function. '''

    app = QApplication(sys.argv)

    window = QWidget()
    window.setWindowTitle('pyqap')
    window.show()

    find_files(os.path.join(os.environ['HOME'], 'src', 'projects'))

    sys.exit(app.exec())

if len(sys.argv) > 1 and sys.argv[1] == 'test':
    test()
elif __name__ == '__main__':
    main()
