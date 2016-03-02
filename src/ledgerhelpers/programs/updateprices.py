#!/usr/bin/env python

import argparse
import collections
import datetime
import httplib
import json
import ledger
import ledgerhelpers
import threading
import traceback
import urlparse
import sys
import yahoo_finance

from gi.repository import GObject
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk


def get_argparser():
    parser = argparse.ArgumentParser(
        'Update prices in a Ledger price file'
    )
    parser.add_argument('-b', dest='batch', action='store_true',
                        help='update price file in batch (non-GUI) mode')
    parser.add_argument('--debug', dest='debug', action='store_true',
                        help='do not capture exceptions into a dialog box')
    return parser


class QuoteSource(object):
    pass


class DontQuote(QuoteSource):

    def __str__(self):
        return "skip quoting"

    def get_quote(self, commodity, denominated_in):
        return None, None


class YahooFinanceCommodities(QuoteSource):

    def __str__(self):
        return "Yahoo! Finance commodities"

    def get_quote(
        self,
        commodity,
        denominated_in,
        commodity_is_currency_pair=False
    ):
        """Returns the price in the appraised_as currency, and the datetime.

        Args:
            commodity: a Ledger commodity representing a non-currency
                       commodity
            denominated_in: a Ledger commodity

        Returns:
            price: ledger.Amount instance
            datetime: datetime.datetime instance
        """
        if not isinstance(commodity, ledger.Commodity):
            raise ValueError("commodity must be a Ledger commodity")
        if not isinstance(denominated_in, ledger.Commodity):
            raise ValueError("denominated_in must be a Ledger commodity")
        if commodity_is_currency_pair:
            source = str(commodity)
            source = source if source != "$" else "USD"
            target = str(denominated_in)
            target = target if target != "$" else "USD"
            pair = source + target
            s = yahoo_finance.Currency(pair)
            try:
                price, date = s.get_rate(), s.get_trade_datetime()
            except KeyError:
                raise ValueError(
                    "Yahoo! Finance can't find currency pair %s" % pair
                )
        else:
            if str(denominated_in) not in ["$", "USD"]:
                raise ValueError(
                    "Yahoo! Finance can't quote in %s" % denominated_in
                )
            s = yahoo_finance.Share(str(commodity))
            try:
                price, date = s.get_price(), s.get_trade_datetime()
            except KeyError:
                raise ValueError(
                    "Yahoo! Finance can't find commodity %s" % commodity
                )
        a = ledger.Amount(price)
        a.commodity = denominated_in
        d = datetime.datetime.strptime(
            date,
            '%Y-%m-%d %H:%M:%S UTC+0000'
        )
        return a, d


class YahooFinanceCurrencies(YahooFinanceCommodities):

    def __str__(self):
        return "Yahoo! Finance currencies"

    def get_quote(self, commodity, denominated_in="$"):
        """Returns the price in the appraised_as currency, and the datetime.

        Args:
            commodity: a Ledger commodity representing a currency
            denominated_in: a Ledger commodity

        Returns:
            price: ledger.Amount instance
            datetime: datetime.datetime instance
        """
        return YahooFinanceCommodities.get_quote(
            self,
            commodity,
            denominated_in,
            commodity_is_currency_pair=True
        )


def json_from_uri(uri):
    c = httplib.HTTPSConnection(urlparse.urlsplit(uri).netloc)
    c.request('GET', uri)
    return json.loads(c.getresponse().read())


class BitcoinCharts(QuoteSource):

    def __str__(self):
        return "bitcoin charts"

    def get_quote(self, commodity, denominated_in):
        """Returns the price in the denominated_in currency,
        and the datetime.

        Args:
            commodity: a Ledger commodity
            denominated_in: a Ledger commodity

        Returns:
            price: ledger.Amount instance
            datetime: datetime.datetime instance
        """
        if not isinstance(commodity, ledger.Commodity):
            raise ValueError("commodity must be a Ledger commodity")
        if not isinstance(denominated_in, ledger.Commodity):
            raise ValueError("denominated_in must be a Ledger commodity")
        if str(commodity) not in ["BTC", "XBT"]:
            raise ValueError(
                "bitcoin charts can only provide quotes for BTC / XBT"
            )

        data = json_from_uri(
            "https://api.bitcoincharts.com/v1/weighted_prices.json"
        )
        try:
            k = "USD" if str(denominated_in) == "$" else str(denominated_in)
            amount = data[k].get("24h", data[k]["7d"])
        except KeyError:
            raise ValueError(
                "bitcoin charts can't provide quotes in %s" % denominated_in
            )
        a = ledger.Amount(amount)
        a.commodity = denominated_in
        d = datetime.datetime.now()
        return a, d


class PriceGatheringDatabase(Gtk.ListStore):

    def __init__(self):
        # Columns:
        # 0: Ledger.commodity to appraise
        # 1: data source to fetch prices from
        # 2: list of (Ledger.commodity) representing which denominations
        #    the (0) commodity must be appraised in
        # 3: list of (gathered price, datetime)
        # 4: errors (exceptions)
        Gtk.ListStore.__init__(self, object, object, object, object, object)
        self.commodities_added = dict()

    def add_to_gather_list(self, commodity, datasource, fetch_prices_in):
        if self.commodities_added.get(str(commodity)):
            return
        assert isinstance(commodity, ledger.Commodity), commodity
        assert isinstance(datasource, QuoteSource)
        for f in fetch_prices_in:
            assert isinstance(f, ledger.Commodity)
        self.append((commodity, datasource, list(fetch_prices_in),
                     list(), list()))
        self.commodities_added[str(commodity)] = True

    def clear_gathered(self):
        for row in self:
            while row[3]:
                row[3].pop()
            while row[4]:
                row[4].pop()
            self.emit('row-changed', row.path, row.iter)

    def record_gathered(self, commodity, amount, timeobject):
        assert isinstance(commodity, ledger.Commodity), commodity
        assert isinstance(amount, ledger.Amount), amount
        found = False
        for row in self:
            if commodity == row[0]:
                found = True
                break
        assert found, "%s not found in gather list" % commodity
        row[3].append((amount, timeobject))
        self.emit('row-changed', row.path, row.iter)

    def record_gathered_error(self, commodity, error):
        assert isinstance(commodity, ledger.Commodity), commodity
        found = False
        for row in self:
            if commodity == row[0]:
                found = True
                break
        assert found, "%s not found in gather list" % commodity
        row[4].append(error)
        self.emit('row-changed', row.path, row.iter)

    def get_currency_by_path(self, treepath):
        it = self.get_iter(treepath)
        return self.get_value(it, 0)

    def update_quoter(self, treepath, new_datasource):
        i = self.get_iter(treepath)
        self.set_value(i, 1, new_datasource)

    def update_price_in(self, treepath, new_price_in):
        i = self.get_iter(treepath)
        self.set_value(i, 2, new_price_in)

    def get_prices(self):
        for row in self:
            for p, d in row[3]:
                yield row[0], p, d

    def get_errors(self):
        for row in self:
            for e in row[4]:
                yield row[0], e


@GObject.type_register
class PriceGatherer(GObject.GObject):

    __gsignals__ = {
        "gathering-started": (
             GObject.SIGNAL_RUN_LAST, None, ()
        ),
        "gathering-done": (
             GObject.SIGNAL_RUN_LAST, None, ()
        ),
    }

    def __init__(self, quoters):
        GObject.GObject.__init__(self)
        assert quoters
        self.quoters = quoters
        self.database = PriceGatheringDatabase()

    def load_commodities_from_journal(
        self,
        journal,
        map_from_currencystrs_to_quotesources,
        map_from_currencystrs_to_priceins,
    ):
        DontQuote = self.quoters.get("DontQuote", self.quoters.values()[0])
        default = "$"
        coms = list(journal.commodities())
        strcoms = [str(c) for c in coms]
        if "USD" in strcoms and "$" not in strcoms:
            default = "USD"
        for c in coms:
            quoter = self.quoters.values()[0]
            if str(c) in ["USD", "$"] and default in ["USD", "$"]:
                quoter = DontQuote
            if str(c) in map_from_currencystrs_to_quotesources:
                quoter = map_from_currencystrs_to_quotesources[str(c)]
            quoteins = [journal.commodity(default)]
            if str(c) in map_from_currencystrs_to_priceins:
                quoteins = list(map_from_currencystrs_to_priceins[str(c)])
            self.database.add_to_gather_list(
                c,
                quoter,
                quoteins,
            )

    def _gather_inner(self, sync=False):
        def do(f, *a):
            if not sync:
                return GObject.idle_add(f, *a)
            return f(*a)

        do(self.database.clear_gathered)
        for row in self.database:
            commodity = row[0]
            quotesource = row[1]
            for denominated_in in row[2]:
                try:
                    price, time = quotesource.get_quote(
                        commodity,
                        denominated_in=denominated_in
                    )
                    if price is None and time is None:
                        continue
                    do(
                        self.database.record_gathered,
                        commodity,
                        price,
                        time
                    )
                except Exception, e:
                    error = str(e)
                    do(
                        self.database.record_gathered_error,
                        commodity,
                        error,
                    )
                    traceback.print_exc()
                    print >> sys.stderr
        GObject.idle_add(self.emit, "gathering-done")

    def gather_quotes(self, sync=False):
        GObject.idle_add(self.emit, "gathering-started")
        if not sync:
            t = threading.Thread(target=self._gather_inner)
            t.setDaemon(True)
            t.start()
        else:
            return self._gather_inner(sync=True)


@GObject.type_register
class CellRendererCommodity(Gtk.CellRendererText):

    __gproperties__ = {
        "commodity": (
            GObject.TYPE_PYOBJECT,
            "commodity to display",
            "the commodity to render in the cell",
            GObject.PARAM_READWRITE
        )
    }

    def do_set_property(self, prop, val):
        if prop.name == "commodity":
            self.set_property("text", str(val))
        else:
            self.set_property(prop, val)


@GObject.type_register
class CellRendererQuoteSource(Gtk.CellRendererCombo):

    __gproperties__ = {
        "source": (
            GObject.TYPE_PYOBJECT,
            "source of quotes",
            "the QuoteSource data source to render",
            GObject.PARAM_READWRITE
        )
    }

    def do_set_property(self, prop, val):
        if prop.name == "source":
            self.set_property("text", str(val))
        else:
            self.set_property(prop, val)


@GObject.type_register
class CellRendererPriceIn(Gtk.CellRendererText):

    __gproperties__ = {
        "price-in": (
            GObject.TYPE_PYOBJECT,
            "which commodities to denominate the quotes in",
            "list of denominations for quote fetches",
            GObject.PARAM_READWRITE
        )
    }

    def do_set_property(self, prop, val):
        if prop.name == "price-in":
            self.set_property("text", "\n".join(str(s) for s in val))
        else:
            self.set_property(prop, val)


@GObject.type_register
class CellRendererFetchedList(Gtk.CellRendererText):

    render_datum = 0

    __gproperties__ = {
        "list": (
            GObject.TYPE_PYOBJECT,
            "list to display",
            "the list of fetched quotes to render",
            GObject.PARAM_READWRITE
        ),
        "render-datum": (
            GObject.TYPE_INT,
            "which datum to render",
            "render either 0 for price or 1 for time",
            render_datum,
            1,
            0,
            GObject.PARAM_READWRITE
        ),
    }

    def do_get_property(self, prop):
        if prop.name == "render-datum":
            return self.render_datum
        else:
            assert 0, prop

    def do_set_property(self, prop, val):
        def render(obj):
            if self.render_datum != 1:
                return str(obj)
            else:
                return obj.strftime("%Y-%m-%d %H:%M:%S")
        if prop.name == "list":
            self.set_property(
                "text",
                "\n".join(render(p[self.render_datum]) for p in val)
            )
        elif prop.name == "render-datum":
            self.render_datum = val
        else:
            assert 0, (prop, val)


@GObject.type_register
class CellRendererFetchErrors(Gtk.CellRendererText):

    __gproperties__ = {
        "errors": (
            GObject.TYPE_PYOBJECT,
            "list of errors to render",
            "list of error strings to render",
            GObject.PARAM_READWRITE
        )
    }

    def do_set_property(self, prop, val):
        if prop.name == "errors":
            self.set_property("text", "\n".join(str(s) for s in val))
        else:
            self.set_property(prop, val)


class PriceGatheringView(Gtk.TreeView):

    def __init__(self):
        Gtk.TreeView.__init__(self)
        commodity_renderer = CellRendererCommodity()
        commodity_renderer.set_property("yalign", 0.0)
        commodity_column = Gtk.TreeViewColumn(
            "Commodity",
            commodity_renderer,
            commodity=0,
        )
        self.append_column(commodity_column)

        quotesource_renderer = CellRendererQuoteSource()
        quotesource_renderer.set_property("yalign", 0.0)
        quotesource_column = Gtk.TreeViewColumn(
            "Quote source",
            quotesource_renderer,
            source=1,
        )
        self.append_column(quotesource_column)
        self.quotesource_renderer = quotesource_renderer

        price_in_renderer = CellRendererPriceIn()
        price_in_renderer.set_property("yalign", 0.0)
        price_in_column = Gtk.TreeViewColumn(
            "Quote in",
            price_in_renderer,
            price_in=2,
        )
        self.append_column(price_in_column)
        self.price_in_renderer = price_in_renderer

        fetched_prices_renderer = CellRendererFetchedList()
        fetched_prices_renderer.set_property("yalign", 0.0)
        fetched_prices_renderer.set_property("render-datum", 0)
        fetched_prices_column = Gtk.TreeViewColumn(
            "Price",
            fetched_prices_renderer,
            list=3,
        )
        self.append_column(fetched_prices_column)

        fetched_dates_renderer = CellRendererFetchedList()
        fetched_dates_renderer.set_property("yalign", 0.0)
        fetched_dates_renderer.set_property("render-datum", 1)
        fetched_dates_column = Gtk.TreeViewColumn(
            "Date",
            fetched_dates_renderer,
            list=3,
        )
        self.append_column(fetched_dates_column)

        errors_renderer = CellRendererFetchErrors()
        errors_renderer.set_property("yalign", 0.0)
        errors_column = Gtk.TreeViewColumn(
            "Status",
            errors_renderer,
            errors=4,
        )
        self.append_column(errors_column)


class UpdatePricesWindow(Gtk.Window):

    def __init__(self):
        Gtk.Window.__init__(self, title="Update prices")
        self.set_border_width(12)
        self.set_default_size(800, 430)

        grid = Gtk.Grid()
        grid.set_column_spacing(8)
        grid.set_row_spacing(8)
        self.add(grid)

        row = 0

        self.gatherer_view = PriceGatheringView()
        self.gatherer_view.set_hexpand(True)
        self.gatherer_view.set_vexpand(True)

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw.set_shadow_type(Gtk.ShadowType.IN)
        sw.add(self.gatherer_view)
        grid.attach(sw, 0, row, 1, 1)

        row += 1

        button_box = Gtk.ButtonBox()
        button_box.set_layout(Gtk.ButtonBoxStyle.END)
        button_box.set_spacing(12)
        self.status = Gtk.Label()
        button_box.add(self.status)
        self.close_button = Gtk.Button(stock=Gtk.STOCK_CLOSE)
        button_box.add(self.close_button)
        self.fetch_button = Gtk.Button(label="Fetch")
        button_box.add(self.fetch_button)
        self.save_button = Gtk.Button(stock=Gtk.STOCK_SAVE)
        button_box.add(self.save_button)
        grid.attach(button_box, 0, row, 2, 1)
        self.fetch_button.set_can_default(True)
        self.fetch_button.grab_default()


class UpdatePricesCommon(object):

    def __init__(self, journal, preferences):
        self.journal = journal
        self.preferences = preferences
        try:
            self.preferences["quotesources"]
        except KeyError:
            self.preferences["quotesources"] = dict()
        try:
            self.preferences["quotecurrencies"]
        except KeyError:
            self.preferences["quotecurrencies"] = dict()
        self.quoters = collections.OrderedDict(
            (str(q), q) for q in [
                YahooFinanceCommodities(),
                YahooFinanceCurrencies(),
                BitcoinCharts(),
                DontQuote(),
            ]
        )
        self.gatherer = PriceGatherer(self.quoters)

    def get_ready(self):
        prefquotesources = dict(
            (cur, self.quoters.get(n, self.quoters.values()[0]))
            for cur, n
            in self.preferences["quotesources"].items()
            if type(n) is not list
        )
        prefquotecurrencies = dict(
            (cur, [self.journal.commodity(v, True) for v in pins])
            for cur, pins
            in self.preferences["quotecurrencies"].items()
        )
        self.gatherer.load_commodities_from_journal(
            self.journal,
            prefquotesources,
            prefquotecurrencies,
        )

    def save_fetched_prices(self):
        recs = list(self.gatherer.database.get_prices())
        if recs:
            lines = self.journal.generate_price_records(recs)
            self.journal.add_lines_to_price_file(lines)

    def output_errors(self):
        recs = list(self.gatherer.database.get_errors())
        if recs:
            print >> sys.stderr, "Therer were errors obtaining prices:"
        for comm, error in recs:
            print "* Gathering %s: %s" % (comm, error)
        return bool(recs)

    def run(self):
        self.get_ready()
        self.gatherer.gather_quotes(sync=True)
        errors = self.output_errors()
        self.save_fetched_prices()
        if errors:
            return 3


class UpdatePricesApp(
    UpdatePricesCommon,
    UpdatePricesWindow,
    ledgerhelpers.EscapeHandlingMixin
):

    def __init__(self, journal, preferences):
        UpdatePricesCommon.__init__(self, journal, preferences)
        UpdatePricesWindow.__init__(self)

        self.fetch_level = 0
        self.connect("delete-event", lambda *a: self.save_preferences())
        self.activate_escape_handling()

        self.gatherer_view.set_model(self.gatherer.database)
        self.close_button.connect(
            "clicked",
            lambda _: self.emit('delete-event', None)
        )
        # FIXME: do asynchronously.
        self.get_ready()

    def get_ready(self):
        UpdatePricesCommon.get_ready(self)

        quotesource_model = Gtk.ListStore(str, object)
        for q in self.quoters.items():
            quotesource_model.append(q)
        self.gatherer_view.quotesource_renderer.set_property(
            "model",
            quotesource_model
        )
        self.gatherer_view.quotesource_renderer.set_property(
            "text-column",
            0
        )
        self.gatherer_view.quotesource_renderer.connect(
            "editing-started",
            self.on_quotesource_editing_started
        )
        self.gatherer_view.quotesource_renderer.connect(
            "edited",
            self.on_quotesource_editing_done
        )
        self.gatherer_view.quotesource_renderer.connect(
            "editing-canceled",
            self.on_quotesource_editing_canceled
        )
        self.gatherer_view.price_in_renderer.connect(
            "editing-started",
            self.on_price_in_editing_started
        )
        self.gatherer_view.price_in_renderer.connect(
            "edited",
            self.on_price_in_editing_done
        )
        self.gatherer_view.price_in_renderer.connect(
            "editing-canceled",
            self.on_price_in_editing_canceled
        )
        self.save_button.connect("clicked", self.save_fetched_prices)
        self.fetch_button.connect("clicked", lambda _: self.do_fetch())
        self.gatherer.connect("gathering-started", self.prevent_fetch)
        self.gatherer.connect("gathering-started", self.disallow_save)
        self.gatherer.connect("gathering-started", self.disable_cell_editing)
        self.gatherer.connect("gathering-done", self.enable_cell_editing)
        self.gatherer.connect("gathering-done", self.allow_fetch)
        self.gatherer.connect("gathering-done", self.allow_save)
        self.gatherer.connect("gathering-done", self.focus_save)
        self.allow_fetch()
        self.disallow_save()
        self.enable_cell_editing()

    def enable_cell_editing(self, w=None):
        self.gatherer_view.quotesource_renderer.set_property(
            "editable",
            True
        )
        self.gatherer_view.price_in_renderer.set_property(
            "editable",
            True
        )

    def disable_cell_editing(self, w=None):
        self.gatherer_view.quotesource_renderer.set_property(
            "editable",
            False
        )
        self.gatherer_view.price_in_renderer.set_property(
            "editable",
            False
        )

    def disallow_save(self, w=None):
        self.save_button.set_sensitive(False)

    def allow_save(self, w=None):
        self.save_button.set_sensitive(True)

    def focus_save(self, w=None):
        self.save_button.grab_focus()

    def prevent_fetch(self, w=None):
        self.fetch_level -= 1
        self.fetch_button.set_sensitive(self.fetch_level > 0)

    def allow_fetch(self, w=None):
        self.fetch_level += 1
        self.fetch_button.set_sensitive(self.fetch_level > 0)

    def on_quotesource_editing_started(self, *a):
        self.prevent_fetch()
        self.suspend_escape_handling()

    def on_quotesource_editing_done(self, cell, path, new_text, *a, **kw):
        thedict = dict(x for x in cell.props.model)
        try:
            new_quotesource = thedict[new_text]
        except KeyError:
            return
        self.gatherer.database.update_quoter(path, new_quotesource)
        currency = self.gatherer.database.get_currency_by_path(path)
        self.preferences["quotesources"][str(currency)] = new_text
        self.allow_fetch()
        self.resume_escape_handling()

    def on_quotesource_editing_canceled(self, *a):
        self.allow_fetch()
        self.resume_escape_handling()

    def on_price_in_editing_started(self, cell, entry, *a):
        self.prevent_fetch()
        self.suspend_escape_handling()
        text = entry.get_text()
        text = text.split("\n")
        entry.set_text(", ".join(text))

    def on_price_in_editing_done(self, cell, path, new_text, *a, **kw):
        new_currencies = [
            self.journal.commodity(x.strip(), True)
            for x in new_text.split(",")
        ]
        self.gatherer.database.update_price_in(path, new_currencies)
        currency = self.gatherer.database.get_currency_by_path(path)
        self.preferences["quotecurrencies"][str(currency)] = [
            str(s) for s in new_currencies
        ]
        self.allow_fetch()
        self.resume_escape_handling()

    def on_price_in_editing_canceled(self, *a):
        self.allow_fetch()
        self.resume_escape_handling()

    def do_fetch(self, *a):
        self.gatherer.gather_quotes()

    def save_fetched_prices(self, *a):
        UpdatePricesCommon.save_fetched_prices(self)
        self.emit("delete-event", None)

    def save_preferences(self):
        self.preferences.persist()

    def run(self):
        self.connect("delete-event", Gtk.main_quit)
        GObject.idle_add(self.show_all)
        Gtk.main()


def main(argv):
    p = get_argparser()
    args = p.parse_args(argv[1:])
    journal, settings = ledgerhelpers.load_journal_and_settings_for_gui(
        price_file_mandatory=True
    )
    klass = UpdatePricesApp if not args.batch else UpdatePricesCommon
    app = klass(journal, settings)
    return app.run()
