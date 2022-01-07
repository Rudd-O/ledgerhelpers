#!/usr/bin/python3

import ledgerhelpers.legacy
from ledgerhelpers import diffing


CHAR_ENTER = "\n"
CHAR_COMMENT = ";#"
CHAR_NUMBER = "1234567890"
CHAR_TAB = "\t"
CHAR_WHITESPACE = " \t"
CHAR_CLEARED = "*"
CHAR_PENDING = "!"

STATE_CLEARED = CHAR_CLEARED
STATE_PENDING = CHAR_PENDING
STATE_UNCLEARED = None


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
    return ledgerhelpers.legacy.parse_date("".join(contents))


class Token(object):

    def __init__(self, pos, contents):
        self.pos = pos
        if not isinstance(contents, str):
            contents = "".join(contents)
        self.contents = contents

    def __str__(self):
        return """<%s at pos %d len %d
%s>""" % (self.__class__.__name__, self.pos, len(self.contents), self.contents)


class TokenComment(Token):
    pass


class TokenTransactionComment(Token):
    pass


class TokenTransactionClearedFlag(Token):
    pass


class TokenTransactionPendingFlag(Token):
    pass


class TokenWhitespace(Token):
    pass


class TokenTransaction(Token):

    def __init__(self, pos, contents):
        Token.__init__(self, pos, contents)
        lexer = LedgerTransactionLexer(contents)
        lexer.run()

        def find_token(klass):
            try:
                return [t for t in lexer.tokens if isinstance(t, klass)][0]
            except IndexError:
                return None

        try:
            self.date = find_token(TokenTransactionDate).date
        except AttributeError:
            raise TransactionLexingError("no transaction date in transaction")

        try:
            self.secondary_date = find_token(
                TokenTransactionSecondaryDate
            ).date
        except AttributeError:
            self.secondary_date = None

        if find_token(TokenTransactionClearedFlag):
            self.state = STATE_CLEARED
        elif find_token(TokenTransactionPendingFlag):
            self.state = STATE_PENDING
        else:
            self.state = STATE_UNCLEARED

        if self.state != STATE_UNCLEARED:
            self.clearing_date = (
                self.secondary_date if self.secondary_date else self.date
            )
        else:
            self.clearing_date = None

        try:
            self.payee = find_token(TokenTransactionPayee).payee
        except AttributeError:
            raise TransactionLexingError("no payee in transaction")

        accountsamounts = [
            t for t in lexer.tokens
            if isinstance(t, TokenTransactionPostingAccount) or
            isinstance(t, TokenTransactionPostingAmount)
        ]

        x = []
        last = None
        for v in accountsamounts:
            if isinstance(v, TokenTransactionPostingAccount):
                assert type(last) in [
                     type(None), TokenTransactionPostingAmount
                ], lexer.tokens
            elif isinstance(v, TokenTransactionPostingAmount):
                assert type(last) in [
                    TokenTransactionPostingAccount
                ], lexer.tokens
                x.append(
                    ledgerhelpers.TransactionPosting(
                        last.account, v.amount
                    )
                )
            last = v
        assert len(x) * 2 == len(accountsamounts), lexer.tokens
        self.postings = x


class TokenTransactionWithContext(TokenTransaction):

    def __init__(self, pos, tokens):
        self.transaction = [
            t for t in tokens if isinstance(t, TokenTransaction)
        ][0]
        self.pos = pos
        self.contents = "".join(t.contents for t in tokens)

    @property
    def date(self):
        return self.transaction.date


class TokenConversion(Token):
    pass


class TokenPrice(Token):
    pass


class TokenEmbeddedPython(Token):
    pass


class TokenTransactionPostingAccount(Token):

    def __init__(self, pos, contents):
        Token.__init__(self, pos, contents)
        self.account = ''.join(contents)


class TokenTransactionPostingAmount(Token):

    def __init__(self, pos, contents):
        Token.__init__(self, pos, contents)
        self.amount = ''.join(contents)


class TokenEmbeddedTag(Token):
    pass


class TokenTransactionDate(Token):

    def __init__(self, pos, contents):
        Token.__init__(self, pos, contents)
        self.date = parse_date_from_transaction_contents(self.contents)


class TokenTransactionSecondaryDate(Token):

    def __init__(self, pos, contents):
        Token.__init__(self, pos, contents)
        self.date = parse_date_from_transaction_contents(self.contents)


class TokenTransactionPayee(Token):

    def __init__(self, pos, contents):
        Token.__init__(self, pos, contents)
        self.payee = ''.join(contents)


class LexingError(Exception):
    pass


class TransactionLexingError(Exception):
    pass


class EOF(LexingError):
    pass


class GenericLexer(object):

    def __init__(self, items):
        if isinstance(items, str) and not isinstance(items, str):
            self.items = tuple(items.decode("utf-8"))
        else:
            self.items = tuple(items)
        self.start = 0
        self.pos = 0
        self._last_emitted_pos = self.pos
        self.tokens = []

    def __next__(self):
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
        token = klass(self.pos, items)
        self._last_emitted_pos = self.pos
        self.tokens += [token]

    def more(self):
        return self.pos < len(self.items)


class LedgerTextLexer(GenericLexer):

    def __init__(self, text):
        assert isinstance(text, str), type(text)
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
            chars += [next(self)]
        self.emit(TokenWhitespace, chars)
        return

    def state_parsing_comment(self):
        chars = [next(self)]
        while self.more():
            if chars[-1] in CHAR_ENTER and self.peek() not in CHAR_COMMENT:
                break
            chars.append(next(self))
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
        chars = [next(self)]
        while self.more():
            if chars[-1] in CHAR_ENTER:
                if not maybe_multiline:
                    break
                if self.peek() in CHAR_WHITESPACE + CHAR_ENTER:
                    chars.append(next(self))
                    continue
                if self.peek() in CHAR_COMMENT:
                    self.emit(klass, chars)
                    return self.state_parsing_comment
                if self.peek() in CHAR_NUMBER:
                    self.emit(klass, chars)
                    return self.state_parsing_transaction
                self.emit(klass, chars)
                return self.state_parsing_toplevel_text
            chars.append(next(self))
        self.emit(klass, chars)
        return self.state_parsing_toplevel_text

    def state_parsing_transaction(self):
        chars = [next(self)]
        while self.more():
            if chars[-1] in CHAR_ENTER and self.peek() not in CHAR_WHITESPACE:
                break
            chars.append(next(self))
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
            except Exception as e:
                l, c, l2, c2 = self._coords()
                raise LexingError(
                    "bad ledger data between line %d, char %d and line %d, char %d: %s" % (
                        l, c, l2, c2, e
                    )
                )


class LedgerTransactionLexer(GenericLexer):

    def __init__(self, text):
        GenericLexer.__init__(self, text)

    def state_parsing_transaction_date(self):
        chars = []
        while self.more():
            if self.peek() not in "0123456789-/":
                self.emit(TokenTransactionDate, chars)
                if self.confirm_next("="):
                    next(self)
                    return self.state_parsing_clearing_date
                elif self.peek() in CHAR_WHITESPACE:
                    return self.state_parsing_cleared_flag_or_payee
                else:
                    raise TransactionLexingError("invalid character %s" % self.peek())
            chars += [next(self)]
        raise TransactionLexingError("incomplete transaction")

    def state_parsing_clearing_date(self):
        chars = []
        while self.more():
            if self.peek() not in "0123456789-/":
                next(self)
                self.emit(TokenTransactionSecondaryDate, chars)
                return self.state_parsing_cleared_flag_or_payee
            chars += [next(self)]
        raise TransactionLexingError("incomplete transaction")

    def state_parsing_cleared_flag_or_payee(self):
        while self.more():
            if self.peek() in CHAR_WHITESPACE:
                next(self)
                continue
            if self.peek() in CHAR_ENTER:
                break
            if self.confirm_next(CHAR_CLEARED):
                self.emit(TokenTransactionClearedFlag, [next(self)])
                return self.state_parsing_payee
            if self.confirm_next(CHAR_PENDING):
                self.emit(TokenTransactionPendingFlag, [next(self)])
                return self.state_parsing_payee
            return self.state_parsing_payee
        raise TransactionLexingError("incomplete transaction")

    def state_parsing_payee(self):
        return self.state_parsing_rest_of_line(
            TokenTransactionPayee,
            self.state_parsing_transaction_posting_indentation)

    def state_parsing_rest_of_line(
        self,
        klass, next_state,
        allow_empty_values=False
    ):
        chars = []
        while self.more():
            if self.peek() in CHAR_ENTER:
                next(self)
                while chars and chars[-1] in CHAR_WHITESPACE:
                    chars = chars[:-1]
                break
            if self.peek() in CHAR_WHITESPACE and not chars:
                next(self)
                continue
            chars.append(next(self))
        if allow_empty_values or chars:
            self.emit(klass, chars)
            return next_state
        raise TransactionLexingError("incomplete transaction")

    def state_parsing_transaction_posting_indentation(self):
        chars = []
        while self.more():
            if self.peek() not in CHAR_WHITESPACE:
                break
            chars.append(next(self))
        if not chars:
            return
        if self.more() and self.peek() in CHAR_ENTER:
            next(self)
            return self.state_parsing_transaction_posting_indentation
        return self.state_parsing_transaction_posting_account

    def state_parsing_transaction_comment(self):
        return self.state_parsing_rest_of_line(
            TokenTransactionComment,
            self.state_parsing_transaction_posting_indentation)

    def state_parsing_transaction_posting_account(self):
        chars = []
        if self.more() and self.peek() in CHAR_COMMENT:
            return self.state_parsing_transaction_comment
        while self.more():
            if (
                (self.peek() in CHAR_WHITESPACE and
                 chars and chars[-1] in CHAR_WHITESPACE) or
                self.peek() in CHAR_TAB or
                self.peek() in CHAR_ENTER
            ):
                while chars[-1] in CHAR_WHITESPACE:
                    chars = chars[:-1]
                break
            chars.append(next(self))
        if not chars:
            raise TransactionLexingError("truncated transaction posting")
        self.emit(TokenTransactionPostingAccount, chars)
        return self.state_parsing_transaction_posting_amount

    def state_parsing_transaction_posting_amount(self):
        return self.state_parsing_rest_of_line(
            TokenTransactionPostingAmount,
            self.state_parsing_transaction_posting_indentation,
            allow_empty_values=True)

    def run(self):
        state = self.state_parsing_transaction_date
        while state:
            state = state()


class LedgerContextualLexer(GenericLexer):

    def state_parsing_toplevel(self):
        while self.more():
            if isinstance(self.peek(), TokenComment):
                return self.state_parsing_comment
            token = next(self)
            self.emit(token.__class__, token.contents)

    def state_parsing_comment(self):
        token = next(self)
        if (
            self.more() and
            isinstance(token, TokenComment) and
            isinstance(self.peek(), TokenTransaction)
        ):
            transaction_token = next(self)
            additional_comments = []
            while self.more() and isinstance(self.peek(), TokenComment):
                additional_comments.append(next(self))
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
            except Exception as e:
                raise LexingError(
                    "error parsing ledger data between chunk %d and chunk %d): %s" % (
                        self._last_emitted_pos, self.pos, e
                    )
                )


def lex_ledger_file_contents(text, debug=False):
    lexer = LedgerTextLexer(text)
    lexer.run()
    concat_lexed = "".join([x.contents for x in lexer.tokens])
    if concat_lexed != text:
        if debug:
            u = "Debugging error lexing text: files differ\n\n"
            diffing.two_way_diff(u + text, u + concat_lexed)
        raise LexingError("the lexed contents and the original contents are not the same")
    lexer = LedgerContextualLexer(lexer.tokens)
    lexer.run()
    concat_lexed = "".join([ x.contents for x in lexer.tokens ])
    if concat_lexed != text:
        if debug:
            u = "Debugging error lexing chunks: files differ\n\n"
            diffing.two_way_diff(u + text, u + concat_lexed)
        raise LexingError("the lexed chunks and the original chunks are not the same")
    return lexer.tokens
