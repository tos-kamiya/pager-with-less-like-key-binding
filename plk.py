#!/usr/bin/env python
# coding: utf-8

import sys
import time
import traceback
import curses


class ContentView:
    def __init__(self, lines, tabsize=4):
        self.tabsize = tabsize
        tabstr = b' ' * self.tabsize
        self.lines = [L.replace(b'\t', tabstr) for L in lines]
        self.cursor = 0  # position of cursor in text (goes 0 to len(line))

    def _get_clipped_index(self, index):
        if index < 0:
            return 0
        elif index > len(self.lines) - 1:
            return len(self.lines) - 1
        return index

    def get_cursor(self):
        return self.cursor

    def get_size(self):
        return len(self.lines)

    def set_cursor(self, index):
        self.cursor = self._get_clipped_index(index)

    def move_cursor(self, delta):
        self.cursor = self._get_clipped_index(self.cursor + delta)
    
    def get_line(self, offset=0):
        li = self.cursor + offset
        if 0 <= li and li < len(self.lines):
            return self.lines[li]
        else:
            return b'~'


class Pager:
    def __init__(self, content):
        self.win = None
        self.y = 0  # position of cursor in screen
        self.x = 0  # position of cursor in screen
        self.height = None
        self.width = None
        self.margin_height = None
        self.status_height = 1
        self.pad_width = None
        self.pad = None
        self.debug_log = []  # for debug
        self.content = content

    def curses_main(self, stdscr):
        self.win = win = stdscr
        win.scrollok(False)  # explicitly control scrolling. should not be controlled by curses
        win.nodelay(True)  # capture arrow keys

        self.height, self.width = win.getmaxyx()
        self.margin_height = self.height // 4

        self.y = 0
        self.x = 0

        self.content.set_cursor(self.y)
        
        self.pad_width = self.width * 2
        self.pad = curses.newpad(self.height, self.pad_width)

        while True:
            self.render()
            self.pad.overwrite(win)
            win.move(self.y, self.x)

            ch = -1
            while ch == -1:
                time.sleep(0.005)
                ch = win.getch()
            if ch == ord(b'q'):
                break

            self.dispatch(ch)

    def dispatch(self, ch):
        if ch in (ord(b'r'), curses.KEY_REFRESH, curses.KEY_RESIZE):
            self.refresh()
        elif ch in (ord(b'e'), ord(b'j'), curses.KEY_DOWN):
            self.move_y(+1)
        elif ch in (ord(b'y'), ord(b'k'), curses.KEY_UP):
            self.move_y(-1)
        elif ch == ord(b'd'):
            self.move_y(self.height // 2)
        elif ch == ord(b'u'):
            self.move_y(-(self.height // 2))
        elif ch == ord(b'f'):
            self.move_y(self.height)
        elif ch == ord(b'b'):
            self.move_y(-self.height)
        elif ch == ord(b'g'):
            self.set_y(0)
        elif ch == ord(b'G'):
            self.set_y(self.content.get_size())
        else:
            self.debug_log.append('ch=%d' % ch)
    
    def _clip_y(self):
        c = self.content
        margin = min(self.margin_height, c.get_cursor(), c.get_size() - 1 - c.get_cursor())
        if self.y > self.height - self.status_height - margin - 1:
            self.y = self.height - self.status_height - margin - 1
        if self.y < margin:
            self.y = margin

    def move_y(self, delta):
        c = self.content
        c.move_cursor(delta)
        self.y += delta
        self._clip_y()
    
    def set_y(self, y):
        c = self.content
        c.set_cursor(y)
        margin = min(self.margin_height, c.get_cursor(), c.get_size() - 1 - c.get_cursor())
        self.y = y
        self._clip_y()

    def refresh(self):
        self.height, self.width = self.win.getmaxyx()
        self.margin_height = self.height // 4

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
        for y in range(0, self.height - self.status_height - 1 + 1):
            l = self.content.get_line(y - self.y)
            pad.addnstr(y, 0, l, pad_width)
            pad.clrtoeol()
        pad.addstr(self.height - self.status_height, 0, b'[%d / %d]' %
                   (self.content.get_cursor() + 1, self.content.get_size()), curses.A_REVERSE)
        pad.clrtoeol()


def main(argv):
    __doc__ = """A pager with less-like key bindings.

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

    cnt = ContentView(lines)
    pgr = Pager(cnt)
    try:
        curses.wrapper(pgr.curses_main)
    except:
        sys.stderr.write(traceback.format_exc())
    finally:
        if pgr.debug_log:
            sys.stderr.write('debug log: %s\n' % repr(pgr.debug_log))


if __name__ == '__main__':
    main(sys.argv)
