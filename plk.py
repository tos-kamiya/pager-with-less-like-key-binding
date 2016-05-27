#!/usr/bin/env python
# coding: utf-8

# This file is distributed under Public Domain.
# Hosted at https://github.com/tos-kamiya/pager-with-less-like-key-binding .

from collections import namedtuple
import curses
import sys
import traceback


YX = namedtuple('YX', ('y', 'x'))


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


class SearchState:
    def __init__(self, dir, row, col, word):
        self.dir = dir
        self.row = row
        self.col = col
        self.word = word


class Pager:
    def __init__(self):
        self.content = None  # list of str
        self.content_csr = None  # Index
        self.screen_size = None  # YX
        self.screen_csr = None  # Index
        self.scr = None  # screen
        self.pad = None  # off-screen buffer
        self.pad_size = None  # YX
        self.body_height = None  # body_height + footer_height = screen_size.y
        self.footer_height = 1
        self.margin_height = 0  # margin_height < body_height
        self.message = None
        self.search_state = None
        self.debug_log = []  # for debug

        self.unknown_key_func = lambda ch: self.debug_log.append('ch=%d' % ch)
        self.key_handler = kh = {}
        kh[ord(b'e')] = kh[ord(b'j')] = kh[curses.KEY_DOWN] = lambda ch: self.move_csr(+1)
        kh[ord(b'y')] = kh[ord(b'k')] = kh[curses.KEY_UP] = lambda ch: self.move_csr(-1)
        kh[ord(b'd')] = lambda ch: self.move_csr(self.body_height // 2)
        kh[ord(b'u')] = lambda ch: self.move_csr(-(self.body_height // 2))
        kh[ord(b'f')] = lambda ch: self.move_csr(self.body_height)
        kh[ord(b'b')] = lambda ch: self.move_csr(-self.body_height)
        kh[ord(b'G')] = lambda ch: self.set_csr(self.content_csr.size)
        kh[ord(b'g')] = lambda ch: self.set_csr(0)
        kh[ord(b'r')] = kh[curses.KEY_REFRESH] = kh[curses.KEY_RESIZE] = lambda ch: self.set_screen(self.scr)
        kh[ord(b'q')] = lambda ch: 'quit'
        kh[ord(b'/')] = kh[ord(b'?')] = self.do_search_cmd
        kh[ord(b'n')] = kh[ord(b'N')] = self.do_search_next_cmd

    def curses_main(self, stdscr):
        self.scr = scr = stdscr
        self.set_screen(scr)
        scr.scrollok(False)  # take control of scroll
        scr.move(0, 0)

        request = None
        while request != 'quit':
            self.draw()
            ch = scr.getch()  # wait key input
            func = self.key_handler.get(ch, self.unknown_key_func)
            request = func(ch)

    def set_content(self, content):
        self.content = content
        self.content_csr = Index(len(self.content))
        self.search_state = None
        if self.screen_csr:
            self._screen_csr_set_pos(self.content_csr.pos)

    def set_screen(self, scr):
        height, width = self.screen_size = YX(*scr.getmaxyx())
        self.pad = curses.newpad(height, width * 2)
        self.pad_size = YX(*self.pad.getmaxyx())

        self.body_height = max(0, height - self.footer_height)
        self.margin_height = self.body_height // 5

        self.screen_csr = Index(height)
        self._screen_csr_set_pos(curses.getsyx()[0])

    def _screen_csr_set_pos(self, y):
        self.screen_csr.set_pos(y)
        if self.content_csr is None:
            return
        cc = self.content_csr
        pos = max(0, min(self.screen_csr.pos, cc.size - 1))
        margin = max(0, min(self.margin_height, cc.pos, cc.size - 1 - cc.pos))
        self.screen_csr.set_pos(max(margin, min(pos, self.body_height - margin - 1)))

    def move_csr(self, delta):
        self.content_csr.set_pos(self.content_csr.pos + delta)
        self._screen_csr_set_pos(self.screen_csr.pos + delta)
    
    def set_csr(self, pos):
        self.content_csr.set_pos(pos)
        self._screen_csr_set_pos(pos)

    def draw(self):
        self.draw_text_area()
        self.draw_scroll_bar()
        self.scr.move(self.screen_csr.pos, 0)

    def draw_text_area(self):
        self.pad.erase()

        for y in range(0, self.body_height):
            self.render_line(y, self.content_csr.pos + (y - self.screen_csr.pos))

        if self.message:
            status_line = b' %s ' % self.message
            self.message = None
        else:
            status_line = b' [%d / %d] ' % (self.content_csr.pos + 1, self.content_csr.size)
        self.pad.addstr(self.body_height, 0, status_line, curses.A_REVERSE)

        self.pad.overwrite(self.scr, 0, 0, 0, 0, self.screen_size.y - 1, 
                self.screen_size.x - 1 - 1)
                # workaround width - 1 to avoid wide char at eol going head of next line

    def render_line(self, y, content_index):
        ss = self.search_state
        pad = self.pad

        pad.move(y, 0) 
        if ss is None or ss.col < 0 or content_index != ss.row:
            if 0 <= content_index < self.content_csr.size:
                pad.addnstr(self.content[content_index], self.pad_size.x);
            else:
                pad.addstr(b'~', curses.A_DIM)
            return

        pad_width = self.pad_size.x
        text = self.content[content_index]
        lw = len(ss.word)
        pad.addnstr(text[:ss.col], pad_width)
        if ss.col < pad_width:
            pad.addnstr(text[ss.col:ss.col + lw], pad_width - ss.col, curses.A_REVERSE)
            if ss.col + lw < pad_width:
                pad.addnstr(text[ss.col + lw:], pad_width - (ss.col + lw))

    def draw_scroll_bar(self):
        cc = self.content_csr
        w = self.screen_size.x - 1
        y_begin = (cc.pos - self.screen_csr.pos) * self.body_height // cc.size
        y_end = (cc.pos + self.body_height - self.screen_csr.pos) * self.body_height // cc.size
        for y in range(0, self.body_height):
            if y == y_begin or y_begin <= y < y_end:
                self.scr.addstr(y, w, b' ', curses.A_REVERSE | curses.A_DIM)
            else:
                self.scr.addstr(y, w, b' ')

    def input_param(self, prompt):
        self.scr.addstr(self.body_height, 0, b'%s' % prompt)
        self.scr.clrtoeol()

        curses.echo()
        try:
            s = self.scr.getstr(self.body_height, len(prompt), self.screen_size.x - len(prompt) - 1)
        finally:
            curses.noecho()
            
        return s or None

    def do_search_cmd(self, ch):
        self.search_state = None
        chr_ch = b'%c' % ch
        w = self.input_param(chr_ch)
        if w is None:
            return  # command was cancled

        self.search_state = SearchState(1 if chr_ch == b'/' else -1, self.content_csr.pos, -1, w)
        self.do_search_next_cmd(ord(b'n'))

    def do_search_next_cmd(self, ch):
        if self.search_state is None:
            return

        ss = self.search_state
        chr_ch = b'%c' % ch
        if ss.dir * (1 if chr_ch == b'n' else -1) < 0:
            ss.row = min(ss.row, self.content_csr.size - 1)
            while ss.row >= 0:
                start_pos = len(self.content[ss.row]) if ss.col == -1 else ss.col + len(ss.word) - 1
                ss.col = self.content[ss.row].rfind(ss.word, 0, start_pos)  # note: expect ss.col = -1 when not found
                if ss.col >= 0:
                    break  # while
                ss.row -= 1
        else:
            ss.row = max(0, ss.row)
            while ss.row < self.content_csr.size:
                ss.col = self.content[ss.row].find(ss.word, ss.col + 1)  # note: expect ss.col = -1 when not found
                if ss.col >= 0:
                    break  # while
                ss.row += 1
        if ss.col >= 0:  # found
            self.set_csr(ss.row)
        else:
            self.message = b'not found'


def wrapper(curses_main, *args):  # same as curses.wrapper, except for not setting up color pallet
    scr = curses.initscr()
    try:
        curses.noecho()
        curses.cbreak()
        scr.keypad(1)
        return curses_main(scr, *args)
    finally:
        scr.keypad(0)
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
    pgr.message = b' %s ' % (input_file if sys.version_info[0] < 3 else input_file.encode('utf-8'))
    try:
        wrapper(pgr.curses_main)
    except:
        sys.stderr.write(traceback.format_exc())
    finally:
        if pgr.debug_log:
            sys.stderr.write('debug log: %s\n' % repr(pgr.debug_log))


if __name__ == '__main__':
    main(sys.argv)
