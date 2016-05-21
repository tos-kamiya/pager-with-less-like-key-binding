#!/usr/bin/env python
# coding: utf-8

# This file is distributed under Public Domain.
# Hosted at https://github.com/tos-kamiya/pager-with-less-like-key-binding .

import sys
import time
import string
import traceback
import curses


class ContentView:
    def __init__(self, lines, tabsize=4):
        self.tabsize = tabsize
        tabstr = b' ' * self.tabsize
        self.lines = [L.replace(b'\t', tabstr) for L in lines]
        self.cursor = 0  # position of cursor in text (goes 0 to len(line))

    def _get_clipped_index(self, index):
        return min(max(0, index), len(self.lines) - 1)

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
        self.content = content
        self.height = None  # screen size
        self.width = None  # screen size
        self.body_height = None  # body_height + footer_height = height
        self.footer_height = 1
        self.margin_height = None  # margin_height < body_height
        self.y = 0  # position of cursor in screen
        self.x = 0  # position of cursor in screen
        self.debug_log = []  # for debug

        # setup constants for keycode (ord_a ... ord_z, ord_A ... ord_Z)
        for c in string.ascii_lowercase:
            setattr(Pager, 'ord_' + c, ord(c))
        for c in string.ascii_uppercase:
            setattr(Pager, 'ord_' + c, ord(c))

    def curses_main(self, stdscr):
        stdscr.scrollok(False)  # explicitly control scrolling. should not be controlled by curses
        stdscr.nodelay(True)  # capture arrow keys
        stdscr.move(0, 0)

        pad = self.update_for_screen(stdscr)
        self.content.set_cursor(self.y)
        
        while True:
            self.render(pad)
            pad.overwrite(stdscr)
            stdscr.move(self.y, self.x)

            ch = -1
            while ch == -1:
                time.sleep(0.005)
                ch = stdscr.getch()

            ch = self.dispatch(ch)
            if ch is None:
                pass
            elif ch == self.ord_q:
                break  # while True
            elif ch == self.ord_r:
                pad = self.update_for_screen(stdscr)
            else:
                self.debug_log.append('ch=%d' % ch)

    def dispatch(self, ch):
        if ch in (self.ord_e, self.ord_j, curses.KEY_DOWN):
            self.move_y(+1)
        elif ch in (self.ord_y, self.ord_k, curses.KEY_UP):
            self.move_y(-1)
        elif ch == self.ord_d:
            self.move_y(self.body_height // 2)
        elif ch == self.ord_u:
            self.move_y(-(self.body_height // 2))
        elif ch == self.ord_f:
            self.move_y(self.body_height)
        elif ch == self.ord_b:
            self.move_y(-self.body_height)
        elif ch == self.ord_g:
            self.set_y(0)
        elif ch == self.ord_G:
            self.set_y(self.content.get_size())
        elif ch in (self.ord_r, curses.KEY_REFRESH, curses.KEY_RESIZE):
            return self.ord_r
        else:
            return ch
        return None
    
    def _clip_set_y(self, y):
        cs = self.content.get_size()
        cc = self.content.get_cursor()
        y = min(y, cs - 1)
        margin = min(self.margin_height, cc, max(cs - 1 - cc, 0))
        y = min(y, self.body_height - margin - 1)
        y = max(y, margin)
        self.y = y

    def move_y(self, delta):
        self.content.move_cursor(delta)
        self._clip_set_y(self.y + delta)
    
    def set_y(self, y):
        self.content.set_cursor(y)
        self._clip_set_y(y)

    def update_for_screen(self, scr):
        self.height, self.width = scr.getmaxyx()
        self.height = max(0, self.height)
        self.margin_height = self.height // 5
        self.body_height = self.height - self.footer_height

        y, self.x = curses.getsyx()
        self._clip_set_y(y)

        pad = curses.newpad(self.height, self.width * 2)
        return pad

    def render(self, pad):
        pad.erase()

        pad_width = pad.getmaxyx()[1]
        for y in range(0, self.body_height):
            l = self.content.get_line(y - self.y)
            pad.addnstr(y, 0, l, pad_width)
            pad.clrtoeol()

        c = self.content
        pad.addstr(self.body_height, 0, b'[%d / %d]' %
                   (c.get_cursor() + 1, c.get_size()), curses.A_REVERSE)
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
