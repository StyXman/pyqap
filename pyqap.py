#! /usr/bin/env python3

'''
PyQap application: backup with rsync by selecting exactly what and what not to backup, with dir/file sizes.
'''

import os
# from pprint import pprint
import sys

from typing import Optional, Any
import unittest

from PyQt6.QtCore import QAbstractItemModel, QModelIndex, QObject, QSortFilterProxyModel, Qt, QVariant  # pylint: disable=no-name-in-module
from PyQt6.QtWidgets import QApplication, QMainWindow, QTreeView  # pylint: disable=no-name-in-module

# import pysnooper
# @pysnooper.snoop()

# 'constants'
File = object()
SymLink = object()
Directory = object()

# pylint: disable=too-few-public-methods
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
        self.selected: Optional[bool] = False  # None means PartiallyChecked
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
    def raw_data(self, index: QModelIndex, selected=False) -> QVariant:
        '''Return raw data for the view at index, column.'''
        entry = index.internalPointer()
        data: Any

        if selected:
            match entry.selected:
                case True:
                    data = Qt.CheckState.Checked
                case None:
                    data = Qt.CheckState.PartiallyChecked
                case False:
                    data = Qt.CheckState.Unchecked
        else:
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
    def data(self, index: QModelIndex, role: int) -> QVariant:
        '''Main interface against the model, but also for other view-type flags.'''
        result = QVariant()

        if index.isValid():
            # print(f"""{role=}""")
            match role:
                case Qt.ItemDataRole.DisplayRole:
                    result = self.raw_data(index)

                    match index.column():
                        case 2:
                            result = human_size(result)  #  type: ignore
                        case 3:
                            result = human_size(result)  #  type: ignore
                case Qt.ItemDataRole.CheckStateRole:
                    if index.column() == 0:
                        result = self.raw_data(index, selected=True)
                        # print(f"""{result=}""")

        return result


    # pylint: disable=invalid-name, no-self-use
    def setData(self, index:QModelIndex, value: QVariant, role: int) -> bool:
        '''Just here to allow setting selected.'''
        # print(f"""{role=}""")
        if role == Qt.ItemDataRole.CheckStateRole:
            if index.isValid() and index.column() == 0:
                # not needed, pyqt has already converted it
                # state = value.toInt()
                state = value
                # print(f"""new_{state=} [{int(Qt.CheckState.Unchecked)}, {Qt.CheckState.PartiallyChecked}, {Qt.CheckState.Checked}]""")
                entry = index.internalPointer()

                match state:
                    # for some reason these comparisons don't work with the constants
                    # maybe because of the automatic conversion to int
                    # and the constants not being really numbers but another type of objects
                    case 0:
                        # print(f"""Unchecked""")
                        entry.selected = False
                    case 1:
                        # print(f"""PartiallyChecked""")
                        entry.selected = None
                    case 2:
                        # print(f"""Checked""")
                        entry.selected = True
                # print(f"""{entry.selected=}""")

                # now here's the thing
                # initially I thought of using the tristates to signal partial backup, which still makes sense, but...
                # assume this scenario:

                # [.] root
                #  `-- [.] child1
                #       `-- [ ] grand_child1
                #       `-- [x] grand_child2
                #  `-- [x] child2
                #       `-- [x] grand_child3
                #       `-- [x] grand_child4

                # this could result in include = [ child1/grand_child2, child2 ], exclude = []
                # or include = [ child1, child2 ], exclude = [ child1/grand_child1 ]
                # or even include = [ <root> ], exclude = [ child1/grand_child1 ]

                # so I think I will just register inclusions and exclusions as selects/deselects
                # and then I will have to figure out what to do about new files

                # this si going to be a braindump for the moment because I don't have enough consecutive time to write
                # the code yet

                # have a methos called from user interaction called select() or similar
                # select() does three things (cue The Spanish Inquisition):

                # * marks the entry as for inclusion or exclusion (based on boolean)
                # * propagates the de/selection down the tree
                #   * this does not mark the children for in/exclusion, just the backing boolean
                #   * updates the selected backup size
                #   * emits the changed signal
                # * updates the boolean that backs the checkbox
                # * updates the selected backup size
                # * emits the changed signal

                # so we now know what to put in the recursive method

                # also, if while propagating a de/selection we find a ex/included entry, ~we remove it~
                # scratch that. we keep them, so we can revert a paren'þs de/selection,
                # but later we will need a collapsing algo to remove them

                # TODO: despite what the docs seem to imply, PartiallyChecked must be implemented by hand
                # see https://stackoverflow.com/a/49160046
                # self.propagate_change(index, state)

                self.dataChanged.emit(index, index, [role])

            return True
        else:
            return False


    def propagate_change(self, index: QModelIndex, state: int):
        '''.'''
        # this doesn't have to be recursive, as setData() will call us again
        pass


    # pylint: disable=no-self-use
    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        '''Convince the view we're read only.'''
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags

        flags = super().flags(index)

        if index.column() == 0:
            flags |= Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsAutoTristate

        return flags


    # pylint: disable=no-self-use
    def headerData(self, column: int, orientation: Qt.Orientation, role: int) -> QVariant:
        '''Return headers for columns.'''
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            header = ('Name', 'Size', 'Total Size', 'Selected Size')[column]
            # Incompatible return value type (got "str", expected "QVariant")
            return header  #  type: ignore

        return QVariant()


class SortableModel(QSortFilterProxyModel):
    '''A sortable model that know how to sort our human readbale sizes.'''

    # pylint: disable=invalid-name, no-self-use
    def lessThan(self, left_index, right_index: QModelIndex) -> bool:
        '''Returns left[column] < right[column].'''
        try:
            # "QAbstractItemModel" has no attribute "raw_data"
            left = self.sourceModel().raw_data(left_index)    #  type: ignore
            right = self.sourceModel().raw_data(right_index)  #  type: ignore
            result = left < right
            # print(f"""{left_index.column()}:{left=} < {right_index.column()}:{right=}: {result}""")
            return result
        except TypeError:
            # this is counter intuitive, but this way works
            if right is None:
                result = False
            else:
                result = True

            # print(f"""{left_index.column()}:{left=} < {right_index.column()}:{right=}: {result} ({e.args})""")
            return result


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
def human_size(size: Optional[float]):
    '''Return size in a human readbale representation.'''
    if size is None:
        return None

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


def TestSelection(unittest.TestCase):
    def setUp(self):
        self.tree = find_files('tests/find_files')

    # tests/find_files/dir2
    # tests/find_files/dir2/dir3
    # tests/find_files/dir2/dir3/40k
    # tests/find_files/dir2/dir3/dangling
    # tests/find_files/dir2/30k
    # tests/find_files/10k
    # tests/find_files/yes-2
    # tests/find_files/yes-3
    # tests/find_files/no-1
    # tests/find_files/dir1
    # tests/find_files/dir1/20k
    # tests/find_files/no-2
    # tests/find_files/yes-1
    def test_select_dir2_deselect_dir3_select_40k(self):
        self


def main():
    ''' Main function. '''
    # root_dir = os.path.join(os.environ['HOME'], 'src', 'projects')
    root_dir = 'tests'
    tree = find_files(root_dir)
    # dump_tree(tree.root)

    app = QApplication(sys.argv)

    window = QMainWindow()
    window.setWindowTitle(f"""pyqap - {root_dir}""")

    model = Model(tree, app)
    model.dataChanged.connect(lambda *x: print(x))

    sorting_model = SortableModel(app)
    # sorting_model = QSortFilterProxyModel(app)
    sorting_model.setSourceModel(model)

    tree_view = QTreeView(window)
    tree_view.setModel(sorting_model)
    tree_view.setSortingEnabled(True)
    for column in range(4):
        tree_view.resizeColumnToContents(column)
    tree_view.sortByColumn(2, Qt.SortOrder.DescendingOrder)
    # tree_view.setRootIsDecorated(False)
    tree_view.setUniformRowHeights(True)
    tree_view.setAlternatingRowColors(True)
    tree_view.show()

    window.setCentralWidget(tree_view)

    window.show()

    sys.exit(app.exec())

if len(sys.argv) > 1 and sys.argv[1] == 'test':
    del sys.argv[1]
    unittest.main()
elif __name__ == '__main__':
    main()
