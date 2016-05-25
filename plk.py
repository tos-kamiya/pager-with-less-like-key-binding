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
        self.screen_size = None  # (height, width)
        self.screen_csr = None  # Index
        self.scr = None  # screen
        self.pad = None  # off-screen buffer
        self.body_height = None  # body_height + footer_height = screen_size[0]
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
            # update screen
            self.draw()
            
            # wait key input
            ch = scr.getch()

            # update state
            func = self.key_handler.get(ch, self.unknown_key_func)
            request = func(ch)

    def set_content(self, content):
        self.content = content
        self.content_csr = Index(len(self.content))
        if self.screen_csr:
            self.screen_csr.set_pos(self.content_csr.pos)
            self._clip_csr()

    def set_screen(self, scr):
        height, width = self.screen_size = scr.getmaxyx()
        self.pad = curses.newpad(height, width * 2)

        self.body_height = max(0, height - self.footer_height)
        self.margin_height = self.body_height // 5

        self.screen_csr = Index(height)
        self.screen_csr.set_pos(curses.getsyx()[0])
        self._clip_csr()

    def _clip_csr(self):
        if self.screen_csr is None or self.content_csr is None:
            return
        cc = self.content_csr
        pos = max(0, min(self.screen_csr.pos, cc.size - 1))
        margin = max(0, min(self.margin_height, cc.pos, cc.size - 1 - cc.pos))
        self.screen_csr.set_pos(max(margin, min(pos, self.body_height - margin - 1)))

    def move_csr(self, delta):
        self.content_csr.set_pos(self.content_csr.pos + delta)
        self.screen_csr.set_pos(self.screen_csr.pos + delta)
        self._clip_csr()
    
    def set_csr(self, pos):
        self.content_csr.set_pos(pos)
        self.screen_csr.set_pos(pos)
        self._clip_csr()

    def draw(self):
        self.render()
        self.pad.overwrite(self.scr, 0, 0, 0, 0, self.screen_size[0] - 1, self.screen_size[1] - 1 - 1)
        # workaround: width -1 to prevent a wide char at eol from being drawn in head of next line
        self.scr.move(self.screen_csr.pos, 0)

    def render(self):
        cc = self.content_csr
        pad = self.pad

        pad.erase()

        pad_width = pad.getmaxyx()[1]
        for y in range(0, self.body_height):
            ci = cc.pos + (y - self.screen_csr.pos)
            if 0 <= ci < cc.size:
                ss = self.search_state
                if ss and ss.col != -1 and ss.row == ci:
                    self.render_line_w_search_highlighting(y, ci)
                else:
                    pad.addnstr(y, 0, self.content[ci], pad_width)
            else:
                pad.addstr(y, 0, b'~', curses.A_DIM)
            pad.clrtoeol()

        if self.message:
            status_line = b' %s ' % self.message
            self.message = None
        else:
            status_line = b' [%d / %d] ' % (cc.pos + 1, cc.size)
        pad.addstr(self.body_height, 0, status_line, curses.A_REVERSE)
        pad.clrtoeol()

    def render_line_w_search_highlighting(self, y, ci):
        ss = self.search_state
        pad = self.pad
        pad_width = pad.getmaxyx()[1]
        text = self.content[ci]
        lw = len(ss.word)
        pad.addnstr(y, 0, text[:ss.col], pad_width)
        if ss.col < pad_width:
            pad.addnstr(y, ss.col, text[ss.col:ss.col + lw], pad_width, curses.A_REVERSE)
            if ss.col + lw < pad_width:
                pad.addnstr(y, ss.col + lw, text[ss.col + lw:], pad_width)

    def input_param(self, prompt):
        scr = self.scr
        
        word_chs = []
        while True:
            scr.addstr(self.body_height, 0, b'%s%s' % (prompt, b''.join(word_chs)))
            scr.clrtoeol()

            ch = scr.getch()
            if ch == curses.KEY_BACKSPACE:
                if not word_chs:
                    return None
                word_chs.pop()
            elif ch in (ord(b'\n'), curses.KEY_ENTER):
                return b''.join(word_chs)
            elif 0 <= ch < 0x7f:  # ascii
                word_chs.append(b'%c' % ch)

    def do_search_cmd(self, ch):
        self.search_state = None

        chr_ch = b'%c' % ch
        w = self.input_param(chr_ch)
        if w is None:
            return  # command was cancled

        ss = SearchState(1 if chr_ch == b'/' else -1, self.content_csr.pos, -1, w)
        self.search_state = ss
        self.do_search_next_cmd()

    def do_search_next_cmd(self, ch=ord(b'n')):
        if self.search_state is None:
            return

        ss = self.search_state
        chr_ch = b'%c' % ch
        if (ss.dir if chr_ch == b'n' else (-ss.dir)) < 0:
            while ss.row >= 0:
                start_pos = -1 if ss.col == -1 else ss.col + len(ss.word) - 1
                ss.col = self.content[ss.row].rfind(ss.word, 0, start_pos)
                if ss.col >= 0:
                    self.set_csr(ss.row)
                    return
                ss.row -= 1
                ss.col = -1
            ss.row = 0
        else:
            while ss.row < self.content_csr.size:
                ss.col = self.content[ss.row].find(ss.word, ss.col + 1)
                if ss.col >= 0:
                    self.set_csr(ss.row)
                    return
                ss.row += 1
                ss.col = -1
            ss.row = self.content_csr.size - 1
        # not found
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
    try:
        wrapper(pgr.curses_main)
    except:
        sys.stderr.write(traceback.format_exc())
    finally:
        if pgr.debug_log:
            sys.stderr.write('debug log: %s\n' % repr(pgr.debug_log))


if __name__ == '__main__':
    main(sys.argv)
