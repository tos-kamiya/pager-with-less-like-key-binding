#!/usr/bin/env python
# coding: utf-8

# This file is distributed under Public Domain.
# Hosted at https://github.com/tos-kamiya/pager-with-less-like-key-binding .

import sys
import traceback
import curses


class Index:
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


class Pager:
    def __init__(self):
        self.content = None  # list of str
        self.content_csr = None  # Index
        self.screen_size = None  # (height, width)
        self.screen_csr = None  # Index
        self.body_height = None  # body_height + footer_height = screen_size[0]
        self.footer_height = 1
        self.margin_height = 0  # margin_height < body_height
        self.debug_log = []  # for debug

        self.unknown_key_func = lambda ch: self.debug_log.append('ch=%d' % ch)
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
        self.content_csr = Index(len(self.content))
        if self.screen_csr is not None:
            self.clip_screen_csr()

    def curses_main(self, stdscr):
        stdscr.scrollok(False)  # take control of scroll
        stdscr.move(0, 0)

        pad = self.prepare_for_screen(stdscr)
        self.content_csr.set_pos(self.screen_csr.pos)

        request = None
        while request != 'quit':
            # update screen
            if request == 'refresh':
                pad = self.prepare_for_screen(stdscr)
            self.render(pad)
            pad.overwrite(stdscr, 0, 0, 0, 0, self.screen_size[0] - 1, self.screen_size[1] - 1 - 1)
                    # workaround: width -1 to prevent a wide char at eol from being drawn in head of next line
            stdscr.move(self.screen_csr.pos, 0)

            # wait key input
            ch = stdscr.getch()

            # update state
            func = self.key_handler.get(ch, self.unknown_key_func)
            request = func(ch)

    def clip_screen_csr(self):
        cc = self.content_csr
        pos = max(0, min(self.screen_csr.pos, cc.size - 1))
        margin = max(0, min(self.margin_height, cc.pos, cc.size - 1 - cc.pos))
        self.screen_csr.set_pos(max(margin, min(pos, self.body_height - margin - 1)))

    def move_cursor(self, delta):
        self.content_csr.set_pos(self.content_csr.pos + delta)
        self.screen_csr.set_pos(self.screen_csr.pos + delta)
        self.clip_screen_csr()
    
    def set_cursor(self, pos):
        self.content_csr.set_pos(pos)
        self.screen_csr.set_pos(pos)
        self.clip_screen_csr()

    def prepare_for_screen(self, scr):
        height, width = self.screen_size = scr.getmaxyx()
        self.body_height = max(0, height - self.footer_height)
        self.margin_height = self.body_height // 5

        self.screen_csr = Index(height)
        y = curses.getsyx()[0]
        self.screen_csr.set_pos(y)
        self.clip_screen_csr()

        pad = curses.newpad(height, width * 2)
        return pad

    def render(self, pad):
        cc = self.content_csr

        pad.erase()

        pad_width = pad.getmaxyx()[1]
        for y in range(0, self.body_height):
            ci = cc.pos + (y - self.screen_csr.pos)
            if 0 <= ci < cc.size:
                pad.addnstr(y, 0, self.content[ci], pad_width)
            else:
                pad.addstr(y, 0, b'~', curses.A_DIM)
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
