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
        self._pos = 0  # 0 <= _pos < size
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
        self.concur = None
        self.height = None  # screen size
        self.width = None  # screen size
        self.body_height = None  # body_height + footer_height = height
        self.footer_height = 1
        self.margin_height = None  # margin_height < body_height
        self.y = 0  # position of cursor in screen
        self.x = 0  # position of cursor in screen
        self.debug_log = []  # for debug

        self.key_handler = kh = {}
        kh[ord(b'e')] = kh[ord(b'j')] = kh[curses.KEY_DOWN] = lambda: self.move_y(+1)
        kh[ord(b'y')] = kh[ord(b'k')] = kh[curses.KEY_UP] = lambda: self.move_y(-1)
        kh[ord(b'd')] = lambda: self.move_y(self.body_height // 2)
        kh[ord(b'u')] = lambda: self.move_y(-(self.body_height // 2))
        kh[ord(b'f')] = lambda: self.move_y(self.body_height)
        kh[ord(b'b')] = lambda: self.move_y(-self.body_height)
        kh[ord(b'G')] = lambda: self.set_y(self.concur.size)
        kh[ord(b'g')] = lambda: self.set_y(0)
        kh[ord(b'r')] = kh[curses.KEY_REFRESH] = kh[curses.KEY_RESIZE] = lambda: 'refresh'
        kh[ord(b'q')] = lambda: 'quit'

    def set_content(self, content):
        self.content = content
        self.concur = ContentCursor(len(self.content))
        if self.height is not None:  # screen is already set up?
            self._clip_set_y(self.y)

    def curses_main(self, stdscr):
        stdscr.scrollok(False)  # take control of scroll
        stdscr.move(0, 0)

        pad = self.prepare_for_screen(stdscr)
        self.concur.set_pos(self.y)

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
            request = func()

    def _clip_set_y(self, y):
        cc = self.concur
        y = min(y, cc.size - 1)
        margin = max(0, min(self.margin_height, cc.pos, cc.size - 1 - cc.pos))
        y = min(y, self.body_height - margin - 1)
        y = max(y, margin)
        self.y = y

    def move_y(self, delta):
        self.concur.set_pos(self.concur.pos + delta)
        self._clip_set_y(self.y + delta)
    
    def set_y(self, y):
        self.concur.set_pos(y)
        self._clip_set_y(y)

    def prepare_for_screen(self, scr):
        self.height, self.width = scr.getmaxyx()
        self.body_height = max(0, self.height - self.footer_height)
        self.margin_height = self.body_height // 5

        y, self.x = curses.getsyx()
        self._clip_set_y(y)

        pad = curses.newpad(self.height, self.width * 2)
        return pad

    def render(self, pad):
        cc = self.concur

        pad.erase()

        pad_width = pad.getmaxyx()[1]
        for y in range(self.body_height):
            li = cc.to_index(y - self.y)
            text = self.content[li] if li is not None else b'~'
            pad.addnstr(y, 0, text, pad_width)
            pad.clrtoeol()

        pad.addstr(self.body_height, 0, b' [%d / %d] ' %
                   (cc.pos + 1, cc.size), curses.A_REVERSE)
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
