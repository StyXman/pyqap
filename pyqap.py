#! /usr/bin/env python3

'''
PyQap application: backup with rsync by selecting exactly what and what not to backup, with dir/file sizes.
'''

import os
# from pprint import pprint
import sys

from typing import Optional# , List
import unittest

from PyQt6.QtCore import QAbstractItemModel, QModelIndex, QObject, Qt, QVariant  # pylint: disable=no-name-in-module
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QTreeView, QWidget  # pylint: disable=no-name-in-module


class Tree:
    '''A map of dir paths to Entries plus a root Entry.'''
    def __init__(self, entries, root):
        self.entries = entries
        self.root = root

class Entry:
    '''Entries have a parent_dir, a name, a local size, a total size, and a list of children.'''
    def __init__(self, parent_dir:str, name:str, size:int, full_size:Optional[int], children:Optional[list]):  #pylint: disable=too-many-arguments
        self.parent_dir = parent_dir
        self.name = name
        self.size = size
        self.full_size = full_size
        self.included = False
        self.selected_size = 0
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


class Model(QAbstractItemModel):
    '''Model for QTreeViews.'''
    def __init__(self, tree: Tree, parent: QObject):
        super().__init__(parent)
        self.tree = tree


    def index(self, row: int, column: int, parent: QModelIndex) -> QModelIndex:
        '''Returns indexes for views and delegates.'''
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        parent_entry: Entry

        # if parent is an invalid model index, return an index to the root
        if not parent.isValid():
            parent_entry = self.tree.root
        else:
            parent_entry = parent.internalPointer()

        if parent_entry.children is None:
            raise ValueError(f"""index({row=}, {column=}, parent={parent_entry}): attempt to get child from a file""")

        try:
            entry = parent_entry.children[row]
        except (IndexError, AttributeError):
            return QModelIndex()

        return self.createIndex(row, column, entry)  # pylint: disable=undefined-variable



    def parent(self, index: QModelIndex) -> QModelIndex:
        '''.'''
        if not index.isValid():
            return QModelIndex()

        entry: Entry

        entry = index.internalPointer()
        parent = self.tree.entries[entry.parent_dir]

        if parent == self.tree.root:
            return QModelIndex()

        return self.createIndex(index.row(), 0, parent)  # pylint: disable=undefined-variable


    # pylint: disable=invalid-name
    def rowCount(self, index: QModelIndex) -> int:
        '''Return the amount of children of this Entry.'''
        if index.column() > 0:
            return 0

        if not index.isValid():
            entry = self.tree.root
        else:
            entry = index.internalPointer()

        if entry.children is None:
            # file
            return 0

        return len(entry.children)


    # pylint: disable=invalid-name, no-self-use
    def columnCount(self, index: QModelIndex) -> int:
        '''Return the amount of columns per Entry.'''
        if index.isValid():
            entry = index.internalPointer()

            if entry.children is None:
                # file: name, size
                return 2
            else:
                # dir: name, local size, total size, selected size
                return 4

        # the root entry is a dir
        return 4


    # pylint: disable=no-self-use
    def data(self, index: QModelIndex, role: int) -> QVariant:
        '''Return data for the view at index, column.'''
        if not index.isValid():
            return QVariant()

        if role != Qt.ItemDataRole.DisplayRole:  # type: ignore
            return QVariant()

        entry = index.internalPointer()

        match index.column():
            case 0:
                data = entry.name
            case 1:
                data = entry.size
            # no, I'm not gonna test for file, etc
            case 2:
                data = entry.full_size
            case 3:
                data = 0
            case _:
                raise ValueError(f"""data({entry=}, column={index.column()}) not in [0-4].""")

        return data


    # pylint: disable=no-self-use
    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        '''Convince the view we're read only.'''
        if not index.isValid():
            return Qt.NoItemFlags  # type: ignore

        return super().flags(index)


    # pylint: disable=no-self-use
    def headerData(self, column: int, orientation: Qt.Orientation, role: int) -> QVariant:
        '''Return headers for columns.'''
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            header = ('Name', 'Size', 'Total Size', 'Selected Size')[column]
            return header

        return QVariant()


def update_sizes(entry):
    '''Update an Entry's full_size with it's chldren full_sizes, after computing them.'''
    if entry.children is not None:
        for child in entry.children:
            # files are already computed in Entry.append()
            if child.children is not None:
                update_sizes(child)
                entry.full_size += child.full_size


def find_files(start: str) -> Tree:
    '''Return an Entry representing the start directory.'''
    entries = { start: Entry(start, os.path.basename(start), 0, 0, []) }  # type: dict[str, Entry]

    for parent_dir, dirs, files, parent_dir_fd in os.fwalk(start):
        parent_dir_entry = entries[parent_dir]

        for dir in dirs:  # pylint: disable=redefined-builtin
            entry = Entry(parent_dir, dir, 0, 0, [])
            entries[os.path.join(parent_dir, dir)] = entry
            parent_dir_entry.append(entry)

        for file in files:
            try:
                file_size = os.stat(file, dir_fd=parent_dir_fd).st_size
            except FileNotFoundError:
                # must be a dangling symlink or it was just deleted, ignore
                file_size = 0

            entry = Entry(parent_dir, file, file_size, None, None)
            parent_dir_entry.append(entry)

    # subdirs are added before their full_sizes are computed, so we have to do another pass updating them
    update_sizes(entries[start])

    return Tree(entries, entries[start])


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
        self.tree = find_files('tests/find_files')

    def test_root_contents(self):
        dirs = [ entry for entry in self.tree.root.children if entry.children is not None ]
        files = [ entry for entry in self.tree.root.children if entry.children is None ]

        self.assertEqual(len(dirs), 2, f"""{dirs=}""")
        self.assertEqual(len(files), 6, f"""{files=}""")

    def test_sizes(self):
        self.assertEqual(self.tree.root.size, 10 * 1024)
        self.assertEqual(self.tree.root.full_size, (10 + 20 + 30 + 40) * 1024)

        print()
        dump_tree(self.tree.root)


def main():
    ''' Main function. '''

    app = QApplication(sys.argv)

    window = QWidget()
    window.setWindowTitle('pyqap')
    window.show()

    layout = QHBoxLayout(window)

    model = Model(tree, app)

    tree_view = QTreeView(window)
    tree_view.setModel(model)
    tree_view.show()

    layout.addWidget(tree_view)

    sys.exit(app.exec())

if len(sys.argv) > 1 and sys.argv[1] == 'test':
    del sys.argv[1]
    unittest.main()
elif __name__ == '__main__':
    main()
