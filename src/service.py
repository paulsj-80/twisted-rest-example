from twisted.web.server import Site, NOT_DONE_YET
from twisted.web.resource import Resource
from twisted.internet import reactor, endpoints, defer
from twisted.internet.protocol import Protocol
from twisted.web.static import File
from twisted.web.client import Agent
from twisted.web.http_headers import Headers
import sys, traceback, os, time
import simplejson as json
from functools import partial
import postgresql_conn as pc;
import psycopg2


# TODO: error messages visible on screen

auth_token = "25184bc5947ed61556d5230a79394fdd43cdcc04"
allowed_currencies = ["USD", "GBP", "EUR", "CHF"]
page_size = 10

##################### utils
class Bunch(dict):
    def __init__(self, d={}):
        dict.__init__(self, d)
        self.__dict__.update(d)
    def add_member(self, key, val):
        self.__dict__[key] = val
    def set_member(self, key, val):
        if type(self) == dict:
            self[key] = val
        self.__dict__[key] = val

class ResponseAccumulator(Protocol):
    def __init__(self, finished):
        self.res = []
        self.finished = finished

    def dataReceived(self, bytes):
        self.res += bytes
        
    def connectionLost(self, reason):
        if reason.getErrorMessage().startswith(
                "Response body fully received"):
            self.finished.callback("".join(self.res))
        else:
            self.finished.errback(reason)


##################### converter
class Converter(object):
    def __init__(self):
        self.agent = Agent(reactor)
        self.rates = {}
        reactor.callLater(0, self.get_rates)

    def get_rates(self):
        d = defer.Deferred()
        def get_rate(c, res):
            d2 = self.agent.request(
                'GET',
                'http://api.fixer.io/latest?base=%s' % c,
                None)
            d2.addCallback(self.new_rate)
            return d2
        for i in allowed_currencies:
            d.addCallback(partial(get_rate, i))

        def on_err(res):
            print "ERROR while fetching rates:", res
        d.addErrback(on_err)
        d.callback(None)
            
        # converter refreshes once per minute
        def start_next(ignored):
            reactor.callLater(60, self.get_rates)
        d.addCallback(start_next)

    def convert(self, c_from, c_to, amount):
        # here we allow it to crash in case data is not there
        if c_from == c_to:
            return amount
        return self.rates[c_from][c_to] * amount

    def new_rate(self, res):
        d2 = defer.Deferred()
        res.deliverBody(ResponseAccumulator(d2))
        def on_rate(res2):
            zz = json.loads(res2)
            self.rates[zz["base"]] = zz["rates"]
        d2.addCallback(on_rate)
        return d2
    
        

##################### model

class Model(object):
    def __init__(self, conn):
        self.conn = conn
        self.converter = Converter()

        self.error_t = {
            "ERR_090": ('new row for relation "accounts" violates check constraint "balance_is_not_negative"', "source balance cannot be negative"),
            "ERR_091": ('insert or update on table "transactions" violates foreign key constraint "transactions_source_id_fkey"', "non-existing source account"),
            "ERR_092": ('insert or update on table "transactions" violates foreign key constraint "transactions_dest_id_fkey"', "non-existing dest account"),
        }

    def translate_error(self, prefix, res):
        def cmerr(ec, mm):
            return (ec, "%s: %s" % (str(prefix), mm))

        if (hasattr(res, "type") and hasattr(res, "value")
            and hasattr(res.value, "message")):
            msg = str(res.value.message).strip()

            if res.type == psycopg2.IntegrityError:            
                for ec, ot in self.error_t.iteritems():
                    cs, m = ot
                    if msg.startswith(cs):
                        return cmerr(ec, m)
            else:
                return cmerr("ERR_130", msg)
        else:
            return cmerr("ERR_135", str(res))

    def get_accounts(self, page):
        if page == None:
            page = 0
        def do_query(context):
            query = "SELECT * FROM accounts ORDER BY id OFFSET %s LIMIT %s;"
            d0 = context.select(query, [page * page_size, page_size])
            def on_select(ignored):
                d1 = context.fetch(page_size)
                return d1
            d0.addCallback(on_select)
            return d0
        return self.conn.execute(do_query)

    def get_account(self, account_id):
        def do_query(context):
            query = "SELECT * FROM accounts WHERE id = %s;"
            d0 = context.select(query, [account_id])
            def on_select(ignored):
                d1 = context.fetch(1)
                return d1
            d0.addCallback(on_select)
            return d0
        return self.conn.execute(do_query)

    def get_transactions(self, page):
        def do_query(context):
            query = "SELECT * FROM transactions ORDER BY id OFFSET %s LIMIT %s;"
            d0 = context.select(query, [page * page_size, page_size])
            def on_select(ignored):
                d1 = context.fetch(page_size)
                return d1
            d0.addCallback(on_select)
            return d0
        return self.conn.execute(do_query)

    def get_account_transactions(self, page, account_id):
        def do_query(context):
            query = "SELECT * FROM transactions WHERE source_id = %s OR dest_id = %s ORDER BY id OFFSET %s LIMIT %s;"
            args = [account_id, account_id, page * page_size, page_size]
            d0 = context.select(query, args)
            def on_select(ignored):
                d1 = context.fetch(page_size)
                return d1
            d0.addCallback(on_select)
            return d0
        return self.conn.execute(do_query)
    

    def add_account(self, currency):
        def do_query(context):
            query = "INSERT INTO accounts (currency) VALUES (%s) RETURNING id;"
            args = [currency]
            d0 = context.do_param_insert(query, args)
            def on_insert(row_id):
                return {"accountId": row_id}
            d0.addCallback(on_insert)
            return d0
        return self.conn.execute(do_query)

    def add_transaction(self, sourceAccount, destAccount, amount):
        def do_query(context):
            query = "INSERT INTO transactions (source_id, dest_id, amount) VALUES (%s, %s, %s) RETURNING id;"
            args = [sourceAccount, destAccount, amount]
            d0 = context.do_param_insert(query, args)

            results = []
            currencies = {}
            amounts = {}
            
            def get_currency(accountId, res):
                results.append(res)
                def do_query(res):
                    query = "SELECT currency FROM accounts WHERE id = %s;"
                    d7 = context.small_select(query, [accountId])
                    def on_select(rows):
                        currencies[accountId] = rows[0]["currency"]
                    d7.addCallback(on_select)
                    return d7
                if accountId:
                    return self.conn.execute(do_query)
            d0.addCallback(partial(get_currency, sourceAccount))
            d0.addCallback(partial(get_currency, destAccount))
            
            def inc_balance(accountId, res):
                if accountId:
                    amount = amounts[accountId]
                    query = "UPDATE accounts SET balance = balance + %s WHERE id = %s;"
                    args = [amount, accountId]
                    return context.do_command(query, args)
                else:
                    return res

            def calc_amount(res):
                # if source or destination currency doesn't exist, no
                # conversion is applied
                
                amounts[sourceAccount] = -amount                
                amounts[destAccount] = amount
                if len(currencies) == 2:
                    amounts[destAccount] = self.converter.convert(
                        currencies[sourceAccount],
                        currencies[destAccount], amount)
                return res
                    
            d0.addCallback(calc_amount)
            d0.addCallback(partial(inc_balance, sourceAccount))
            d0.addCallback(partial(inc_balance, destAccount))

            # commit is done automatically
            def on_finish(row_id):
                return {"transactionId": results[0]}
                
            d0.addCallback(on_finish)
            return d0
        return self.conn.execute(do_query)
    
    

##################### urls

class BadResource(Resource):
    def __init__(self, ec, msg):
        Resource.__init__(self)
        self.ec = ec
        self.msg = msg
        self.err = self.create_error(ec, msg)

    def create_error(self, ec, msg):
        return json.dumps({
            "error": True,
            "code": str(ec),
            "message": str(msg)
        }, use_decimal=True)

    def getChild(self, name, request):
        return BadResource(self.ec, self.msg)
    def render_GET(self, request):
        return self.err
    def render_POST(self, request):
        return self.err
    def render_HEAD(self, request):
        return self.err
    def render_PUT(self, request):
        return self.err
    def render_OPTIONS(self, request):
        return self.err
    def render_DELETE(self, request):
        return self.err
    def render_TRACE(self, request):
        return self.err
    def render_CONNECT(self, request):
        return self.err
        

class AbstractResource(BadResource):
    def __init__(self, model):
        BadResource.__init__(self, "ERR_020", "method not available")
        self.model = model

    def translate_error(self, prefix, res):
        return self.create_error(*self.model.translate_error(
            prefix, res))       
    
    def direct_query(self, func, request, kw={}):
        d = func(**kw)
        def on_done(resp):
            request.write(self.create_succ(resp))
            request.finish()
        d.addCallback(on_done)

        # TODO: this should be exposed
        def on_err(res):
            print res
        d.addErrback(on_err)
        
        return NOT_DONE_YET
    def extract_args(self, request, arglist):
        def apply_type(val, tfunc, arg):
            if val == None:
                return val
            else:
                try:
                    return tfunc(val)
                except Exception as e:
                    raise Exception("bad datatype for %s" % arg)
            
        return Bunch({(i, apply_type(request.args.get(
            i, [None])[0], tfunc, i))
                      for i, tfunc in arglist})

    def create_succ(self, data):
        return json.dumps({
            "error": False,
            "data": data
        }, use_decimal=True)

class Accounts(AbstractResource):
    def __init__(self, model):
        AbstractResource.__init__(self, model)
        
    def render_GET(self, request):
        try:
            args = self.extract_args(request, [("page", int)])
            return self.direct_query(self.model.get_accounts,
                                     request, args)
        except Exception as e:
            return self.create_error("ERR_173", str(e))
    

    def render_POST(self, request):
        try:
            return self.do_render_POST(request)
        except Exception as e:
            return self.create_error("ERR_110", str(e))

    def do_render_POST(self, request):
        args = self.extract_args(request, [("currency", str)])
        if not args.currency in allowed_currencies:
            return self.create_error("ERR_021", "currency not allowed")
        d = self.model.add_account(args.currency)
        def on_done(resp):
            request.write(self.create_succ(resp))
            request.finish()
        d.addCallback(on_done)

        def on_err(res):
            request.write(self.translate_error(
                "failed to add account", res))                
            request.finish()
        d.addErrback(on_err)
        
        return NOT_DONE_YET

class AccountTransactions(AbstractResource):
    def __init__(self, model, account_id=None):
        AbstractResource.__init__(self, model)
        self.account_id = account_id
    def getChild(self, name, request):
        if self.account_id:
            return BadResource("ERR_032", "path not available")
        return AccountTransactions(self.model, name)
    def render_GET(self, request):
        try:
            args = self.extract_args(request, [("page", int)])
            args["account_id"] = self.account_id
            return self.direct_query(
                self.model.get_account_transactions, request, args)
        except Exception as e:
            return self.create_error("ERR_175", str(e))
                                     
        
class Transactions(AbstractResource):
    def __init__(self, model):
        AbstractResource.__init__(self, model)
        self.account = AccountTransactions(model)
        self.names = ["account"]
    
    def render_GET(self, request):
        return self.direct_query(self.model.get_transactions,
                                 request)

    def getChild(self, name, request):
        if name in self.names:
            return getattr(self, name)
        else:
            return BadResource("ERR_031", "path not available")

    def render_POST(self, request):
        try:
            return self.do_render_POST(request)
        except Exception as e:
            return self.create_error("ERR_100", str(e))

    def do_render_POST(self, request):
        args = self.extract_args(request, [("sourceAccount", int),
                                           ("destAccount", int),
                                           ("amount", float)])
        if (not args.amount or args.amount <= 0):
            return self.create_error("ERR_070", "bad amount")
        
        if (not (args.destAccount or args.sourceAccount)):
            return self.create_error("ERR_060", "cannot omit both accounts")

        if (args.destAccount == args.sourceAccount):
            return self.create_error("ERR_065", "accounts should differ")

        d = self.model.add_transaction(
            args.sourceAccount, args.destAccount, args.amount)
        def on_done(resp):
            request.write(self.create_succ(resp))
            request.finish()
        d.addCallback(on_done)
        def on_err(res):
            request.write(self.translate_error(
                "failed to add transaction", res))
            request.finish()
            
        d.addErrback(on_err)
        return NOT_DONE_YET

class Currencies(AbstractResource):
    def __init__(self, model):
        AbstractResource.__init__(self, model)
        
    def render_GET(self, request):
        return self.create_succ(allowed_currencies)
        

class Root(AbstractResource):
    def __init__(self, model):
        AbstractResource.__init__(self, model)
        self.static = File("static")
        self.accounts = Accounts(model)
        self.transactions = Transactions(model)
        self.currencies = Currencies(model)
        
        self.names = ["static", "accounts", "transactions", "currencies"]
    def getChild(self, name, request):
        if (name != "static" and (
                not request.requestHeaders.hasHeader(
                    "authorization") or
                request.requestHeaders.getRawHeaders(
                    "authorization")[0] != auth_token)):
            return BadResource("ERR_010", "bad auth token")
        
        if name in self.names:
            return getattr(self, name)
        else:
            return BadResource("ERR_030", "path not available")


def start_service(conf_fname):
    
    with open(conf_fname) as conf_file:
        params = conf_file.read().split(" ")
        numbers = [0, 1, 6]
        for i in numbers:
            params[i] = int(params[i])
    
    psql_conn = pc.PostgresqlConnPool(params[1], params[2:])
    model = Model(psql_conn)
    # TODO: should wait until initialization of currency rates is
    # done
    root = Root(model)
    
    factory = Site(root)

    # launch
    endpoint = endpoints.TCP4ServerEndpoint(reactor, 8081)
    endpoint.listen(factory)
    reactor.suggestThreadPoolSize(params[0])
    
    reactor.run()

if __name__ == "__main__":
    if len(sys.argv) == 2:
        try:
            start_service(sys.argv[1])
        except:
            traceback.print_exc()
    else:
        print "provide config file"
            

