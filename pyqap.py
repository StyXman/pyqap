#! /usr/bin/env python3

'''
PyQap application: backup with rsync by selecting exactly what and what not to backup, with dir/file sizes.
'''

import os
# from pprint import pprint
import sys

from typing import Optional# , List
import unittest

from PyQt6.QtWidgets import QApplication, QWidget  # pylint: disable=no-name-in-module


class Entry:
    '''Entries have a root, a name, a local size, a total size, and a list of children.'''
    def __init__(self, root:str, name:str, size:int, full_size:Optional[int], children:Optional[list]):  #pylint: disable=too-many-arguments
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
            # dir; the way the algo works makes this 0 anyways :(
            self.full_size += child.full_size

    def __str__(self):
        if self.children is None:
            string = f"""Entry({self.name!r}, {self.size})"""
        else:
            string = f"""Entry({self.name!r}, {self.size}, {self.full_size}, [ ... {len(self.children)} ... ])"""

        return string

    __repr__ = __str__


def update_sizes(entry):
    '''Update an Entry's full_size with it's chldren full_sizes, after computing them.'''
    if entry.children is not None:
        for child in entry.children:
            # files are already computed in Entry.append()
            if child.children is not None:
                update_sizes(child)
                entry.full_size += child.full_size


def find_files(start: str) -> Entry:
    '''Return an Entry representing the start directory.'''
    entries = { start: Entry(start, os.path.basename(start), 0, 0, []) }  # type: dict[str, Entry]

    for root, dirs, files, root_fd in os.fwalk(start):
        root_entry = entries[root]

        for dir in dirs:  # pylint: disable=redefined-builtin
            entry = Entry(root, dir, 0, 0, [])
            entries[os.path.join(root, dir)] = entry
            root_entry.append(entry)

        for file in files:
            try:
                file_size = os.stat(file, dir_fd=root_fd).st_size
            except FileNotFoundError:
                # must be a dangling symlink or it was just deleted, ignore
                file_size = 0

            entry = Entry(root, file, file_size, None, None)
            root_entry.append(entry)

    # subdirs are added before their full_sizes are computed, so we have to do another pass updating them
    update_sizes(entries[start])

    return entries[start]


# see https://stackoverflow.com/a/14996816
suffixes = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB']
def human_size(size):
    '''Return size in a human readbale representation.'''
    index = 0

    while size >= 1024 and index < len(suffixes) - 1:
        size /= 1024
        index += 1

    string_repr = (f"""{size:.2f}""").rstrip('0').rstrip('.')

    return f"""{string_repr}{suffixes[index]}"""


def dump_tree(entry, indent=0):
    '''Dump a tree of Entry's in a quasi nice tree format.'''
    if entry.children is not None:
        print(f"""{'  ' * indent}`- {entry.name} [{human_size(entry.size)}/{human_size(entry.full_size)}]""")

        for child in entry.children:
            dump_tree(child, indent + 1)
    else:
        print(f"""{'  ' * indent}`- {entry.name} [{human_size(entry.size)}]""")


# pylint: disable=missing-class-docstring,missing-function-docstring
class TestEntry(unittest.TestCase):
    def setUp(self):
        self.root_entry = Entry('root', 'root', 0, 0, [])
        self.first_file = Entry('root', 'first_file', 10, None, None)
        self.first_subdir = Entry('root', 'first_subdir', 0, 0, [])
        self.second_file = Entry('root/first_subdir', 'second_file', 100, None, None)

    def test_one_dir_one_file_sizes(self):
        self.root_entry.append(self.first_file)

        self.assertEqual(self.root_entry.size, 10)
        self.assertEqual(self.root_entry.full_size, 10)

    def test_two_dirs_two_files_sizes(self):
        self.root_entry.append(self.first_file)
        self.first_subdir.append(self.second_file)
        self.root_entry.append(self.first_subdir)

        self.assertEqual(self.first_subdir.size, 100)
        self.assertEqual(self.first_subdir.full_size, 100)

        self.assertEqual(self.root_entry.size, 10)
        self.assertEqual(self.root_entry.full_size, 110)


# pylint: disable=missing-class-docstring,missing-function-docstring
class TestUpdateSizes(unittest.TestCase):
    def setUp(self):
        self.root_entry = Entry('root', 'root', 0, 0, [])
        self.first_file = Entry('root', 'first_file', 10, None, None)
        self.first_subdir = Entry('root', 'first_subdir', 0, 0, [])
        self.second_file = Entry('root/first_subdir', 'second_file', 100, None, None)

    def test_all(self):
        self.root_entry.append(self.first_subdir)
        self.root_entry.append(self.first_file)
        self.first_subdir.append(self.second_file)
        update_sizes(self.root_entry)

        self.assertEqual(self.first_subdir.size, 100)
        self.assertEqual(self.first_subdir.full_size, 100)

        self.assertEqual(self.root_entry.size, 10)
        self.assertEqual(self.root_entry.full_size, 110)


# pylint: disable=missing-class-docstring,missing-function-docstring
class TestFindFiles(unittest.TestCase):
    def setUp(self):
        self.root = find_files('tests/find_files')

    def test_root_contents(self):
        dirs = [ entry for entry in self.root.children if entry.children is not None ]
        files = [ entry for entry in self.root.children if entry.children is None ]

        self.assertEqual(len(dirs), 2, f"""{dirs=}""")
        self.assertEqual(len(files), 6, f"""{files=}""")

    def test_sizes(self):
        self.assertEqual(self.root.size, 10 * 1024)
        self.assertEqual(self.root.full_size, (10 + 20 + 30 + 40) * 1024)

        print()
        dump_tree(self.root)


def main():
    ''' Main function. '''

    app = QApplication(sys.argv)

    window = QWidget()
    window.setWindowTitle('pyqap')
    window.show()

    tree = find_files(os.path.join(os.environ['HOME'], 'src', 'projects'))
    dump_tree(tree)

    sys.exit(app.exec())

if len(sys.argv) > 1 and sys.argv[1] == 'test':
    del sys.argv[1]
    unittest.main()
elif __name__ == '__main__':
    main()
