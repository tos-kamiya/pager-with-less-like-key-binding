#!/usr/bin/env python
# coding: utf8

import sys
import curses


class Content:
    def __init__(self, lines, tabsize=4):
        self.tabsize = tabsize
        tabstr = b' ' * self.tabsize
        self.lines = [L.replace(b'\t', tabstr) for L in lines]
        self.line_index = 0  # position of cursor in text (goes 0 to len(line))

    def _clip_line_index(self):
        if self.line_index < 0:
            self.line_index = 0
        elif self.line_index > len(self.lines) -1:
            self.line_index = len(self.lines) - 1

    def get_index(self):
        return self.line_index

    def get_size(self):
        return len(self.lines)

    def set_index(self, index):
        self.line_index = index
        self._clip_line_index()

    def move_index(self, delta):
        self.line_index += delta
        self._clip_line_index()
    
    def get_line(self, y):
        li = self.line_index + y
        if 0 <= li and li < len(self.lines):
            return self.lines[li]
        else:
            return b'~'


class Pager:
    def __init__(self, content):
        self.y = 0  # position of cursor in screen
        self.x = 0  # position of cursor in screen
        self.height = None
        self.width = None
        self.pad_width = None
        self.pad = None
        self.debug_log = []  # for debug
        self.content = content
    
    def curses_main(self, stdscr):
        win = stdscr
        win.scrollok(False)  # explicitly control scrolling. should not be controlled by curses
        win.nodelay(True)  # capture arrow keys

        self.height, self.width = win.getmaxyx()
        self.y = 0
        self.x = 0

        self.content.set_index(self.y)
        
        self.pad_width = self.width * 2
        self.pad = curses.newpad(self.height, self.pad_width)

        while True:
            self.render()
            self.pad.overwrite(win)
            win.move(self.y, self.x)

            ch = win.getch()
            if ch == ord(b'q'):
                break
            elif ch in (ord(b'r'), curses.KEY_REFRESH):
                self.refresh()
            elif ch in (ord(b'e'), ord(b'j'), curses.KEY_DOWN):
                self.move_y(-1)
            elif ch in (ord(b'y'), ord(b'k'), curses.KEY_UP):
                self.move_y(+1)
            elif ch == ord(b'd'):
                self.move_y(self.height // 2)
            elif ch == ord(b'u'):
                self.move_y(-(self.height // 2))
            elif ch == ord(b'f'):
                self.move_y(self.height)
            elif ch == ord(b'b'):
                self.move_y(-self.height)
            else:
                self.debug_log.append('ch=%d' % ch)
    
    def move_y(self, delta):
        self.content.move_index(delta)
        self.y += delta
        if self.y > self.height - 2:
            self.y = self.height - 2
        if self.y < 0:
            self.y = 0

    def refresh(self):
        self.height, self.width = win.getmaxyx()
        y, x = curses.getsyx()
        assert y >= 0
        self.y = y
        self.x = x

        self.pad_width = self.width * 2
        self.pad = curses.newpad(self.height, self.pad_width)

    def render(self):
        pad = self.pad
        pad_width = self.pad_width
        pad.erase()
        for y in range(0, self.height - 2 + 1):
            l = self.content.get_line(y - self.y)
            pad.addnstr(y, 0, l, pad_width)
            pad.clrtoeol()
        pad.move(self.height - 1, 0)
        pad.addstr(self.height - 1, 0, b'[%d / %d]' %
                (self.content.get_index() + 1, self.content.get_size()), curses.A_REVERSE)
        pad.clrtoeol()


def main(argv):
    __doc__ = """A pageer with less-like key bindings.

Usage: {argv0} <input>
""".format(argv0=argv[0])

    import locale
    locale.setlocale(locale.LC_ALL, "")  # enable printing wide chars.

    input_file = None
    for a in argv[1:]:
        if a.startswith('-'):
            if a == '-h':
                print(__doc__)
                sys.exit(0)
            else:
                sys.exit('unknown option: %s' % repr(a))
        else:
            if not input_file:
                input_file = a
            else:
                sys.exit('too many command-line arguments')

    with open(input_file, 'rb') as inp:
        lines = inp.readlines()

    cnt = Content(lines)
    pgr = Pager(cnt)
    try:
        curses.wrapper(pgr.curses_main)
    except BaseException as e:
        sys.stderr.write('exception: %s\n' % repr(e))
        if pgr.debug_log:
            sys.stderr.write('debug log: %s\n' % repr(pgr.debug_log))


if __name__ == '__main__':
    main(sys.argv)
