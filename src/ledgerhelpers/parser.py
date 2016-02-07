#!/usr/bin/env python

import ledgerhelpers
from ledgerhelpers import diffing


CHAR_ENTER = "\n"
CHAR_COMMENT = ";#"
CHAR_NUMBER = "1234567890"
CHAR_WHITESPACE = " \t"


def pos_within_items_to_row_and_col(pos, items):
    row = 1
    col = 1
    for i, c in enumerate(items):
        if i >= pos:
            break
        if c in CHAR_ENTER:
            row += 1
            col = 1
        else:
            col += 1
    return row, col


def parse_date_from_transaction_contents(contents):
    splits = CHAR_WHITESPACE + "="
    data = contents
    for s in splits:
        data = data.split(s)[0]
    return ledgerhelpers.parse_date(data)


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


class TokenWhitespace(Token):
    pass


class TokenTransaction(Token):

    def __init__(self, pos, contents):
        Token.__init__(self, pos, contents)
        self.date = parse_date_from_transaction_contents(self.contents)


class TokenTransactionWithContext(TokenTransaction):

    def __init__(self, pos, tokens):
        self.transaction = [ t for t in tokens if isinstance(t, TokenTransaction) ][0]
        self.pos = pos
        self.contents = u"".join(t.contents for t in tokens)

    @property
    def date(self):
        return self.transaction.date


class TokenConversion(Token):
    pass


class TokenPrice(Token):
    pass


class TokenEmbeddedPython(Token):
    pass


class TokenEmbeddedTag(Token):
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


class LedgerTextLexer(GenericLexer):

    def __init__(self, text):
        assert isinstance(text, unicode), type(text)
        GenericLexer.__init__(self, text)

    def state_parsing_toplevel_text(self):
        """Returns another state function."""
        chars = []
        while self.more():
            if self.peek() in CHAR_COMMENT:
                self.emit(TokenWhitespace, chars)
                return self.state_parsing_comment
            if self.peek() in CHAR_NUMBER:
                self.emit(TokenWhitespace, chars)
                return self.state_parsing_transaction
            if self.confirm_next("P"):
                self.emit(TokenWhitespace, chars)
                return self.state_parsing_price
            if self.confirm_next("C"):
                self.emit(TokenWhitespace, chars)
                return self.state_parsing_conversion
            if self.confirm_next("python"):
                self.emit(TokenWhitespace, chars)
                return self.state_parsing_embedded_python
            if self.confirm_next("tag"):
                self.emit(TokenWhitespace, chars)
                return self.state_parsing_embedded_tag
            if self.peek() not in CHAR_WHITESPACE + CHAR_ENTER:
                _, _, l2, c2 = self._coords()
                raise LexingError(
                    "unparsable data at line %d, char %d" % (l2, c2)
                )
            chars += [self.next()]
        self.emit(TokenWhitespace, chars)
        return

    def state_parsing_comment(self):
        chars = [self.next()]
        while self.more():
            if chars[-1] in CHAR_ENTER and self.peek() not in CHAR_COMMENT:
                break
            chars.append(self.next())
        self.emit(TokenComment, chars)
        return self.state_parsing_toplevel_text

    def state_parsing_price(self):
        return self.state_parsing_embedded_directive(TokenPrice, False)

    def state_parsing_conversion(self):
        return self.state_parsing_embedded_directive(TokenConversion, False)

    def state_parsing_embedded_tag(self):
        return self.state_parsing_embedded_directive(TokenEmbeddedTag)

    def state_parsing_embedded_python(self):
        return self.state_parsing_embedded_directive(TokenEmbeddedPython)

    def state_parsing_embedded_directive(self, klass, maybe_multiline=True):
        chars = [self.next()]
        while self.more():
            if chars[-1] in CHAR_ENTER:
                if not maybe_multiline:
                    break
                if self.peek() in CHAR_WHITESPACE + CHAR_ENTER:
                    chars.append(self.next())
                    continue
                if self.peek() in CHAR_COMMENT:
                    self.emit(klass, chars)
                    return self.state_parsing_comment
                if self.peek() in CHAR_NUMBER:
                    self.emit(klass, chars)
                    return self.state_parsing_transaction
                self.emit(klass, chars)
                return self.state_parsing_toplevel_text
            chars.append(self.next())
        self.emit(klass, chars)
        return self.state_parsing_toplevel_text

    def state_parsing_transaction(self):
        chars = [self.next()]
        while self.more():
            if chars[-1] in CHAR_ENTER and self.peek() not in CHAR_WHITESPACE:
                break
            chars.append(self.next())
        self.emit(TokenTransaction, chars)
        return self.state_parsing_toplevel_text

    def _coords(self):
        r, c = pos_within_items_to_row_and_col(self._last_emitted_pos, self.items)
        r2, c2 = pos_within_items_to_row_and_col(self.pos, self.items)
        return r, c, r2, c2

    def run(self):
        state = self.state_parsing_toplevel_text
        while state:
            try:
                state = state()
            except LexingError:
                raise
            except Exception, e:
                l, c, l2, c2 = self._coords()
                raise LexingError(
                    "bad ledger data between line %d, char %d and line %d, char %d: %s" % (
                        l, c, l2, c2, e
                    )
                )


class LedgerContextualLexer(GenericLexer):

    def state_parsing_toplevel(self):
        while self.more():
            if isinstance(self.peek(), TokenComment):
                return self.state_parsing_comment
            token = self.next()
            self.emit(token.__class__, token.contents)

    def state_parsing_comment(self):
        token = self.next()
        if (
            self.more() and
            isinstance(token, TokenComment) and
            isinstance(self.peek(), TokenTransaction)
        ):
            transaction_token = self.next()
            additional_comments = []
            while self.more() and isinstance(self.peek(), TokenComment):
                additional_comments.append(self.next())
            self.emit(TokenTransactionWithContext,
                      [token, transaction_token] + additional_comments)
        else:
            self.emit(token.__class__, token.contents)
        return self.state_parsing_toplevel

    def run(self):
        state = self.state_parsing_toplevel
        while state:
            try:
                state = state()
            except LexingError:
                raise
            except Exception, e:
                raise LexingError(
                    "error parsing ledger data between chunk %d and chunk %d): %s" % (
                        self._last_emitted_pos, self.pos, e
                    )
                )


def lex_ledger_file_contents(text, debug=False):
    lexer = LedgerTextLexer(text)
    lexer.run()
    concat_lexed = u"".join([x.contents for x in lexer.tokens])
    if concat_lexed != text:
        if debug:
            u = "Debugging error lexing text: files differ\n\n"
            diffing.two_way_diff(u + text, u + concat_lexed)
        raise LexingError("the lexed contents and the original contents are not the same")
    lexer = LedgerContextualLexer(lexer.tokens)
    lexer.run()
    concat_lexed = u"".join([ x.contents for x in lexer.tokens ])
    if concat_lexed != text:
        if debug:
            u = "Debugging error lexing chunks: files differ\n\n"
            diffing.two_way_diff(u + text, u + concat_lexed)
        raise LexingError("the lexed chunks and the original chunks are not the same")
    return lexer.tokens
