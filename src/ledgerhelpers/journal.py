#!/usr/bin/python3

import collections
import errno
import ledger
from ledgerhelpers import parser, debug_time
import ledgerhelpers.legacy_needsledger as hln
import logging
from multiprocessing import Process, Pipe
import os
import threading
import time


UNCHANGED = "unchanged"
UNCONDITIONAL = "unconditional"
IFCHANGED = "ifchanged"

CMD_GET_A_LCFA_C = "get_accounts_last_commodity_for_account_and_commodities"


def transactions_with_payee(payee,
                            internal_parsing_result,
                            case_sensitive=True):
    """Given a payee string, and an internal_parsing() result from the
    journal, return the transactions with matching payee,
    perhaps ignoring case."""
    transes = []
    if not case_sensitive:
        payee = payee.lower()
    for xact in internal_parsing_result:
        if not hasattr(xact, "payee"):
            continue
        xact_payee = xact.payee if case_sensitive else xact.payee.lower()
        if xact_payee == payee:
            transes.append(xact)
    return transes


class Joinable(threading.Thread):
    """A subclass of threading.Thread that catches exception in run(), if any,
    and re-throws it in join()."""
    exception = None

    def __init__(self):
        threading.Thread.__init__(self, daemon=True)

    def join(self):
        threading.Thread.join(self)
        if self.exception:
            raise self.exception

    def run(self):
        try:
            self.__run__()
        except BaseException as e:
            self.exception = e


class JournalCommon():

    path = None
    path_mtime = None
    price_path = None
    price_path_mtime = None

    def changed(self):
        path_mtime = None
        price_path_mtime = None

        try:
            path_mtime = os.stat(self.path).st_mtime
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise
        try:
            if self.price_path is not None:
                price_path_mtime = os.stat(self.price_path).st_mtime
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise

        if (
            path_mtime != self.path_mtime or
            price_path_mtime != self.price_path_mtime
        ):
            self.path_mtime = path_mtime
            self.price_path_mtime = price_path_mtime
            self.logger.debug("Files have changed, rereading.")
            return True
        else:
            return False

    def _get_text(self, prepend_price_path=False):
        files = []
        if self.price_path and prepend_price_path:
            files.append(self.price_path)
        if self.path:
            files.append(self.path)
        t = []
        for f in files:
            with open(f, "r") as fo:
                t.append(fo.read())
        text = "\n".join(t)
        self.logger.debug("Read %d characters of journal%s.", len(text), " and price file" if len(files) > 1 else "")
        return text

    def get_journal_text_with_prices(self):
        return self._get_text(True)

    def get_journal_text(self):
        return self._get_text(False)


class Journal(JournalCommon):

    logger = logging.getLogger("journal.master")

    pipe = None
    slave = None
    slave_lock = None
    cache = None
    internal_parsing_cache = None
    internal_parsing_cache_lock = None

    def __init__(self):
        """Do not instantiate directly.  Use class methods."""
        self.cache = {}
        self.internal_parsing_cache = []
        self.internal_parsing_cache_lock = threading.Lock()
        self.slave_lock = threading.Lock()

    def _start_slave(self):
        if self.pipe:
            self.pipe.close()
        self.pipe, theirconn = Pipe()
        if self.slave:
            try:
                self.slave.terminate()
            except Exception:
                pass
        try:
            self.slave = JournalSlave(theirconn, self.path, self.price_path)
            self.slave.start()
        finally:
            theirconn.close()

    @classmethod
    def from_file(klass, journal_file, price_file):
        j = klass()
        j.path = journal_file
        j.price_path = price_file
        j._start_slave()
        j._cache_internal_parsing()
        return j

    def _cache_internal_parsing(self):
        self.internal_parsing_cache_lock.acquire()

        if self.changed():
            me = self
            self.internal_parsing_cache = None

            class Rpi(Joinable):
                @debug_time(self.logger)
                def __run__(self):
                    try:
                        me.logger.debug("Reparsing internal.")
                        res = parser.lex_ledger_file_contents(me.get_journal_text())
                        me.internal_parsing_cache = res
                    finally:
                        me.internal_parsing_cache_lock.release()

            internal_parsing_thread = Rpi()
            internal_parsing_thread.name = "Internal reparser"
            internal_parsing_thread.start()
            return internal_parsing_thread
        else:
            # Dummy thread.  Just serves to unlock the parsing cache lock.
            nothread = threading.Thread(target=self.internal_parsing_cache_lock.release)
            nothread.start()
            return nothread

    def _cache_accounts_last_commodity_for_account_and_commodities(self):
        with self.slave_lock:
            try:
                self.pipe.send(
                    (CMD_GET_A_LCFA_C,
                     IFCHANGED if "accounts" in self.cache
                     else UNCONDITIONAL)
                )
                result = self.pipe.recv()
                if isinstance(result, BaseException):
                    raise result
                if result == UNCHANGED:
                    assert "accounts" in self.cache
                else:
                    accounts = result[0] if result[0] is not None else []
                    last_commodity_for_account = dict(
                        (acc, ledger.Amount(amt))
                        for acc, amt in list(result[1].items())
                    ) if result[1] is not None else {}
                    all_commodities = [
                        ledger.Amount(c)
                        for c in result[2]
                    ] if result[2] is not None else []
                    self.cache["accounts"] = accounts
                    self.cache["last_commodity_for_account"] = (
                        last_commodity_for_account
                    )
                    self.cache["all_commodities"] = all_commodities
            except BaseException:
                self.cache = {}
                self._start_slave()
                raise

    @debug_time(logger)
    def accounts_and_last_commodity_for_account(self):
        self._cache_accounts_last_commodity_for_account_and_commodities()
        return self.cache["accounts"], self.cache["last_commodity_for_account"]

    @debug_time(logger)
    def commodities(self):
        self._cache_accounts_last_commodity_for_account_and_commodities()
        return self.cache["all_commodities"]

    def commodity(self, label, create=False):
        pool = ledger.Amount("$ 1").commodity.pool()
        if create:
            return pool.find_or_create(label)
        else:
            return pool.find(label)

    @debug_time(logger)
    def all_payees(self):
        """Returns a list of strings with payees (transaction titles)."""
        titles = collections.OrderedDict()
        for xact in self.internal_parsing():
            if hasattr(xact, "payee") and xact.payee not in titles:
                titles[xact.payee] = xact.payee
        return list(titles.keys())

    @debug_time(logger)
    def internal_parsing(self):
        self._cache_internal_parsing().join()
        with self.internal_parsing_cache_lock:
            return self.internal_parsing_cache

    def generate_record(self, *args):
        return hln.generate_record(*args)

    def generate_price_records(self, prices):
        from ledgerhelpers import generate_price_records
        return generate_price_records(prices)

    def _add_text_to_file(self, text, f):
        if not isinstance(text, str):
            text = "\n".join(text)
        f = open(f, "a")
        print(text, file=f)
        f.flush()
        f.close()

    def add_text_to_file(self, text):
        return self._add_text_to_file(text, self.path)

    def add_text_to_price_file(self, text):
        return self._add_text_to_file(text, self.price_path)


class JournalSlave(JournalCommon, Process):

    session = None
    journal = None
    accounts = None
    last_commodity_for_account = None
    all_commodities = None
    logger = logging.getLogger("journal.slave")

    def __init__(self, pipe, path, price_path):
        Process.__init__(self)
        self.daemon = True
        self.pipe = pipe
        self.path = path
        self.price_path = price_path
        self.clear_caches()

    def clear_caches(self):
        self.session = None
        self.journal = None
        self.accounts = None
        self.last_commodity_for_account = None
        self.all_commodities = None

    def reparse_ledger(self):
        self.logger.debug("Reparsing ledger.")
        session = ledger.Session()
        journal = session.read_journal_from_string(self.get_journal_text_with_prices())
        self.session = session
        self.journal = journal

    def harvest_accounts_and_last_commodities(self):
        self.logger.debug("Harvesting accounts and last commodities.")
        # Commodities returned by this method do not contain any annotations.
        accts = []
        commos = dict()
        amts = dict()
        for post in self.journal.query(""):
            for subpost in post.xact.posts():
                if str(subpost.account) not in accts:
                    accts.append(str(subpost.account))
                comm = ledger.Amount(1).with_commodity(subpost.amount.commodity)
                comm.commodity = comm.commodity.strip_annotations()
                commos[str(subpost.account)] = str(comm)
                amts[str(comm)] = True
        self.accounts = accts
        self.last_commodity_for_account = commos
        self.all_commodities = [str(k) for k in list(amts.keys())]

    def reparse_all_if_needed(self):
        me = self

        changed = self.changed()
        if changed:
            self.clear_caches()

            class Rpl(Joinable):
                @debug_time(self.logger)
                def __run__(self):
                    me.reparse_ledger()
                    me.harvest_accounts_and_last_commodities()

            ledger_parsing_thread = Rpl()
            ledger_parsing_thread.name = "Ledger reparser"

        else:
            ledger_parsing_thread = threading.Thread(target=len, args=([],))
            ledger_parsing_thread.name = "Dummy ledger reparser"

        ledger_parsing_thread.start()

        return (
            changed, ledger_parsing_thread
        )

    def run(self):
        logger = logging.getLogger("journal.slave.loop")
        _, initial_parsing_thread = self.reparse_all_if_needed()
        while True:
            cmd_args = self.pipe.recv()
            if initial_parsing_thread:
                initial_parsing_thread.join()
                initial_parsing_thread = None
            cmd = cmd_args[0]
            start = time.time()
            logger.debug("* Servicing: %-55s  started", cmd)
            args = cmd_args[1:]
            try:
                changed, lpt = self.reparse_all_if_needed()
                if cmd == CMD_GET_A_LCFA_C:
                    if (
                        not changed and
                        args[0] == IFCHANGED and
                        self.journal
                    ):
                        logger.debug("* Serviced:  %-55s  %.3f seconds - %s",
                                     cmd, time.time() - start, UNCHANGED)
                        self.pipe.send(UNCHANGED)
                        continue
                    lpt.join()
                    logger.debug("* Serviced:  %-55s  %.3f seconds - new data",
                                 cmd, time.time() - start)
                    self.pipe.send((
                        self.accounts,
                        self.last_commodity_for_account,
                        self.all_commodities,
                    ))
                else:
                    assert 0, "not reached"
            except BaseException as e:
                logger.exception("Unrecoverable error in slave.")
                self.pipe.send(e)
