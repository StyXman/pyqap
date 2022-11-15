#! /usr/bin/env python3

'''
PyQap application: backup with rsync by selecting exactly what and what not to backup, with dir/file sizes.
'''

import os
from pprint import pprint
import sys

from PyQt6.QtWidgets import QApplication, QWidget  # pylint: disable=no-name-in-module


class Entry:
    def __init__(self, name, size):
        self.name = None

def find_files(root: str) -> list:
    '''
    Return a list of entries. Entries have a root, a name, a local size, a total size, and a list of children.
    '''
    data = []
    entries = {}

    for root, dirs, files, root_fd in os.fwalk(root):
        size = 0

        """
        for dir in dirs:
            entry = (dir, 0, [])
            entries[root] = entry
        """

        for file in files:
            entry = (root, file, os.stat(file, dir_fd=root_fd).st_size, None, None)
            data.append(entry)

    return data


def test():
    '''crappy test function untl we grow.'''
    data = find_files('tests/find_files')
    files = [ entry for entry in data if entry[4] is None ]

    assert len(files) == 5



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
