#!/usr/bin/env python
# coding: utf-8

# This file is distributed under Public Domain.
# Hosted at https://github.com/tos-kamiya/pager-with-less-like-key-binding .

import sys
import string
import traceback
import curses


class ContentCursor:
    def __init__(self, size):
        self._pos = 0  # 0 <= _pos < size  (if size > 0)
        self._size = size

    def _get_pos(self):
        return self._pos
    pos = property(_get_pos)

    def set_pos(self, pos):
        self._pos = max(0, min(pos, self._size - 1))

    def _get_size(self):
        return self._size
    size = property(_get_size)

    def to_index(self, offset=0):
        idx = self._pos + offset
        if 0 <= idx < self._size:
            return idx
        else:
            return None  # out of range


class Pager:
    def __init__(self):
        self.content = None
        self.content_csr = None  # content cursor
        self.height = self.width = None  # screen size
        self.body_height = None  # body_height + footer_height = height
        self.footer_height = 1
        self.margin_height = None  # margin_height < body_height
        self.y = self.x = 0  # position of screen cursor
        self.debug_log = []  # for debug

        self.key_handler = kh = {}
        kh[ord(b'e')] = kh[ord(b'j')] = kh[curses.KEY_DOWN] = lambda ch: self.move_cursor(+1)
        kh[ord(b'y')] = kh[ord(b'k')] = kh[curses.KEY_UP] = lambda ch: self.move_cursor(-1)
        kh[ord(b'd')] = lambda ch: self.move_cursor(self.body_height // 2)
        kh[ord(b'u')] = lambda ch: self.move_cursor(-(self.body_height // 2))
        kh[ord(b'f')] = lambda ch: self.move_cursor(self.body_height)
        kh[ord(b'b')] = lambda ch: self.move_cursor(-self.body_height)
        kh[ord(b'G')] = lambda ch: self.set_cursor(self.content_csr.size)
        kh[ord(b'g')] = lambda ch: self.set_cursor(0)
        kh[ord(b'r')] = kh[curses.KEY_REFRESH] = kh[curses.KEY_RESIZE] = lambda ch: 'refresh'
        kh[ord(b'q')] = lambda ch: 'quit'

    def set_content(self, content):
        self.content = content
        self.content_csr = ContentCursor(len(self.content))
        if self.height is not None:  # screen is already set up?
            self._set_y(self.y)

    def curses_main(self, stdscr):
        stdscr.scrollok(False)  # take control of scroll
        stdscr.move(0, 0)

        pad = self.prepare_for_screen(stdscr)
        self.content_csr.set_pos(self.y)

        unknown_key_func = lambda: self.debug_log.append('ch=%d' % ch)

        request = None
        while request != 'quit':
            # update screen
            if request == 'refresh':
                pad = self.prepare_for_screen(stdscr)
            self.render(pad)
            pad.overwrite(stdscr, 0, 0, 0, 0, self.height - 1, self.width - 1 - 1)
                    # workaround: width -1 to prevent a wide char at eol from being drawn in head of next line
            stdscr.move(self.y, self.x)

            # wait key input
            ch = stdscr.getch()

            # undate state
            func = self.key_handler.get(ch, unknown_key_func)
            request = func(ch)

    def _set_y(self, y):
        cc = self.content_csr
        y = max(0, min(y, cc.size - 1))
        margin = max(0, min(self.margin_height, cc.pos, cc.size - 1 - cc.pos))
        self.y = max(margin, min(y, self.body_height - margin - 1))

    def move_cursor(self, delta):
        self.content_csr.set_pos(self.content_csr.pos + delta)
        self._set_y(self.y + delta)
    
    def set_cursor(self, pos):
        self.content_csr.set_pos(pos)
        self._set_y(pos)

    def prepare_for_screen(self, scr):
        self.height, self.width = scr.getmaxyx()
        self.body_height = max(0, self.height - self.footer_height)
        self.margin_height = self.body_height // 5

        y, self.x = curses.getsyx()
        self._set_y(y)

        pad = curses.newpad(self.height, self.width * 2)
        return pad

    def render(self, pad):
        cc = self.content_csr

        pad.erase()

        pad_width = pad.getmaxyx()[1]
        for y in range(0, self.body_height):
            ci = cc.to_index(y - self.y)
            line = self.content[ci] if ci is not None else b'~'
            pad.addnstr(y, 0, line, pad_width)
            pad.clrtoeol()

        status_line = b' [%d / %d] ' % (cc.pos + 1, cc.size)
        pad.addstr(self.body_height, 0, status_line, curses.A_REVERSE)
        pad.clrtoeol()


def wrapper(curses_main):  # same as curses.wrapper, except for not setting up color pallet
    stdscr = curses.initscr()
    try:
        curses.noecho()
        curses.cbreak()
        stdscr.keypad(1)
        return curses_main(stdscr)
    finally:
        stdscr.keypad(0)
        curses.echo()
        curses.nocbreak()
        curses.endwin()


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

    pgr = Pager()
    pgr.set_content(lines)
    try:
        wrapper(pgr.curses_main)
    except:
        sys.stderr.write(traceback.format_exc())
    finally:
        if pgr.debug_log:
            sys.stderr.write('debug log: %s\n' % repr(pgr.debug_log))


if __name__ == '__main__':
    main(sys.argv)
