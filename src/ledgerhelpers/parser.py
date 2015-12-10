#!/usr/bin/env python

import datetime


CHAR_ENTER = "\n\r"
CHAR_COMMENT = ";#"
CHAR_NUMBER = "1234567890"
CHAR_WHITESPACE = " \t"


def parse_date_from_transaction_contents(contents):
    # FIXME: use Ledger functions to parse dates, not mine.
    formats = ["%Y-%m-%d", "%Y/%m/%d"]
    splits = CHAR_WHITESPACE + "="
    data = contents
    for s in splits:
        data = data.split(s)[0]
    for f in formats:
        try:
            d = datetime.datetime.strptime(data, f).date()
        except ValueError, e:
            continue
    try:
        return d
    except UnboundLocalError:
        raise ValueError("cannot parse date from format %s: %s" % (f, e))


class Token(object):

    def __init__(self, pos, contents):
        self.pos = pos
        if not isinstance(contents, basestring):
            contents = u"".join(contents)
        self.contents = contents

    def __str__(self):
        return """<%s at pos %d len %d
%s>""" % (self.__class__.__name__, self.pos, len(self.contents), self.contents)


class TokenComment(Token):
    pass


class TokenUnparsedText(Token):
    pass


class TokenTransaction(Token):

    def __init__(self, pos, contents):
        Token.__init__(self, pos, contents)
        self.date = parse_date_from_transaction_contents(self.contents)


class TokenEmbeddedPython(Token):
    pass


class LexingError(Exception):
    pass


class EOF(LexingError):
    pass


class GenericLexer(object):

    def __init__(self, items):
        if isinstance(items, basestring) and not isinstance(items, unicode):
            self.items = tuple(items.decode("utf-8"))
        else:
            self.items = tuple(items)
        self.start = 0
        self.pos = 0
        self._last_emitted_pos = self.pos
        self.tokens = []

    def next(self):
        """Returns the item at the current position, and advances the position."""
        try:
            t = self.items[self.pos]
        except IndexError:
            raise EOF()
        self.pos += 1
        return t

    def peek(self):
        """Returns the item at the current position."""
        try:
            t = self.items[self.pos]
        except IndexError:
            raise EOF()
        return t

    def confirm_next(self, seq):
        """Returns True if each item in seq matches each corresponding item
        from the current position onward."""
        for n, i in enumerate(seq):
            try:
                if self.items[self.pos + n] != i:
                    return False
            except IndexError:
                return False
        return True

    def emit(self, klass, items):
        """Creates an instance of klass (a Token class) with the current
        position and the supplied items as parameters, then
        accumulates the instance into the self.tokens accumulator."""
        if len(items) == 0:
            self._last_emitted_pos = self.pos
            return
        token = klass(self.pos, items)
        self._last_emitted_pos = self.pos
        self.tokens += [token]

    def more(self):
        return self.pos < len(self.items)

#     @property  # FIXME, redo properly
#     def last_emitted_pos_range(self):
#         substr = self.items[:self._last_emitted_pos]
#         line = sum(substr.count(x) for x in CHAR_ENTER) + 1
#         char = self._last_emitted_pos - max(substr.rfind(x) for x in CHAR_ENTER)
#         substr2 = self.items[:self.pos]
#         line2 = sum(substr2.count(x) for x in CHAR_ENTER) + 1
#         char2 = self.pos - max(substr2.rfind(x) for x in CHAR_ENTER)
#         return line, char, line2, char2


class LedgerTextLexer(GenericLexer):

    def state_parsing_toplevel_text(self):
        """Returns another state function."""
        chars = []
        while self.more():
            if self.peek() in CHAR_COMMENT:
                self.emit(TokenUnparsedText, chars)
                return self.state_parsing_comment
            if self.peek() in CHAR_NUMBER:
                self.emit(TokenUnparsedText, chars)
                return self.state_parsing_transaction
            if self.confirm_next("python"):
                self.emit(TokenUnparsedText, chars)
                return self.state_parsing_embedded_python
            if self.peek() not in CHAR_WHITESPACE + CHAR_ENTER:
                raise LexingError("do not know how to parse %r at pos %d" % (self.peek(), self.pos))
            chars += [self.next()]
        self.emit(TokenUnparsedText, chars)
        return

    def state_parsing_comment(self):
        chars = [self.next()]
        while self.more():
            if chars[-1] in CHAR_ENTER and self.peek() not in CHAR_COMMENT:
                break
            chars.append(self.next())
        self.emit(TokenComment, chars)
        return self.state_parsing_toplevel_text

    def state_parsing_embedded_python(self):
        chars = [self.next()]
        while self.more():
            if chars[-1] in CHAR_ENTER:
                if self.peek() in CHAR_WHITESPACE + CHAR_ENTER:
                    chars.append(self.next())
                    continue
                if self.peek() in CHAR_COMMENT:
                    self.emit(TokenEmbeddedPython, chars)
                    return self.state_parsing_comment
                if self.peek() in CHAR_NUMBER:
                    self.emit(TokenEmbeddedPython, chars)
                    return self.state_parsing_transaction
                self.emit(TokenEmbeddedPython, chars)
                return self.state_parsing_toplevel_text
            chars.append(self.next())
        self.emit(TokenEmbeddedPython, chars)
        return self.state_parsing_toplevel_text

    def state_parsing_transaction(self):
        chars = [self.next()]
        while self.more():
            if chars[-1] in CHAR_ENTER and self.peek() not in CHAR_WHITESPACE:
                break
            chars.append(self.next())
        self.emit(TokenTransaction, chars)
        return self.state_parsing_toplevel_text

    def run(self):
        state = self.state_parsing_toplevel_text
        while state:
            try:
                state = state()
            except Exception, e:
                raise LexingError(
                    "error parsing ledger data between position %d and position %d): %s" % (
                        self.pos, self._last_emitted_pos, e
                    )
                )


def lex_ledger_file_contents(text):
    lexer = LedgerTextLexer(text)
    lexer.run()
    concat_lexed = u"".join([ x.contents for x in lexer.tokens ])
    if concat_lexed != text:
        raise LexingError("the lexed contents and the original contents are not the same")
    return lexer.tokens
