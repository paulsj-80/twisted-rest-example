from twisted.internet import protocol, reactor, task, defer, threads
import psycopg2
from twisted.python.failure import Failure

# this class is not thread safe; should do a new call only after
# previous has ended (succ/fail)
class PostgresqlTransactionContext(object):
    def __init__(self, conn):
        self.conn = conn
    def select(self, query, args):
        return threads.deferToThread(self.conn.select, query, args)
    def fetch(self, page_size):
        return threads.deferToThread(self.conn.fetch, page_size)
    def small_select(self, query, args):
        return threads.deferToThread(self.conn.small_select,
                                     query, args)
    def do_command(self, query, args):
        return threads.deferToThread(self.conn.do_command,
                                     query, args)
    def do_insert(self, tname, a_dict):
        return threads.deferToThread(self.conn.do_insert, tname,
                                     a_dict)
    def do_param_insert(self, query, args):
        return threads.deferToThread(self.conn.do_param_insert,
                                     query, args)
    def do_update(self, tname, query, a_dict):
        return threads.deferToThread(
            self.conn.do_update, tname, query, a_dict)
    def start_tnx(self):
        return threads.deferToThread(self.conn.start_tnx)
    def commit(self):
        return threads.deferToThread(self.conn.commit)
    def rollback(self):
        return threads.deferToThread(self.conn.rollback)


class PostgresqlConn(object):
    def __init__(self, conn_str):
        print "CONNECT", conn_str
        self.conn = psycopg2.connect(conn_str)
        self.cur = None

    def __add_column_names(self, data):
        cols = self.cur.description
        col_len = len(cols)
        res = []
        for i in data:
            entry = {}
            for j in range(col_len):
                entry[cols[j].name] = i[j]
            res.append(entry)
        return res
        
    def close(self):
        self.conn.close()

    # may not use it; transaction is starting implicitly, when
    # issuing commands / queries; commit / rollback follows
    # when transaction function is done (it's deferred is triggered)
    def start_tnx(self):
        self.cur = self.conn.cursor()

    def commit(self):
        if self.cur:
            self.conn.commit()
            self.cur = None
    def rollback(self):
        if self.cur:
            self.conn.rollback()
            self.cur = None

    def select(self, query, args):
        if not self.cur:
            self.cur = self.conn.cursor()
        self.cur.execute(query, args)

    def fetch(self, page_size):
        if not self.cur:
            return []
        data = self.cur.fetchmany(size=page_size)
        return self.__add_column_names(data)

    def small_select(self, query, args):
        if not self.cur:
            self.cur = self.conn.cursor()
        self.cur.execute(query, args)
        return self.__add_column_names(self.cur.fetchall())

    def do_command(self, query, args):
        if not self.cur:
            self.cur = self.conn.cursor()
        self.cur.execute(query, args)
        return None

    def do_param_insert(self, query, args):
        self.do_command(query, args)
        return self.cur.fetchone()[0]
    
    def do_insert(self, tname, a_dict):
        cols = []
        values = []
        for k, v in a_dict.iteritems():
            if v:
                cols.append(k)
                values.append(v)
        query = "INSERT INTO " + tname + " (" + ", ".join(cols) + \
                ") VALUES (" + ", ".join(["%s" for i in values]) + \
                ") RETURNING id;"
        res = self.do_command(query, values)
        return self.cur.fetchone()[0]

    def do_update(self, tname, query, a_dict):
        cols = []
        values = []
        for k, v in a_dict.iteritems():
            cols.append(k)
            values.append(v)
        cols2 = []
        for k, v in query.iteritems():
            cols2.append(k)
            values.append(v)
        query = "UPDATE " + tname + " SET " + \
                ", ".join(["%s = %%s" % i for i in cols]) + \
                " WHERE " + \
                " AND ".join(["%s = %%s" % i for i in cols2]) + ";"
        return self.do_command(query, values)



class PostgresqlConnPool(object):
    def __init__(self, conn_pool_size, conn_params):
        conn_str = "dbname='%s' user='%s' host='%s' port=%d password='%s'" % (conn_params[3], conn_params[1], conn_params[0], conn_params[4], conn_params[2])
        self.free_conns = [PostgresqlConn(conn_str)
                           for i in range(conn_pool_size)]
        self.busy_conns = []
        self.pending_transactions = []

    def graceful_shutdown(self):
        for i in self.free_conns:
            i.close()

    def execute(self, func, args=[]):
        """
        reserves a connection for a transaction and executes it
        func signature: func(context) -> deferred
        """
        if len(self.free_conns):
            conn = self.free_conns.pop(0)
            self.busy_conns.append(conn)
            def do_execute(f, a):
                d = defer.Deferred()
                d.addCallback(t_succ)
                d.addErrback(t_fail)
                # ensuring control goes back to reactor
                def wrapper():
                    context = PostgresqlTransactionContext(conn)
                    args2 = [context] + a
                    try:
                        d2 = f(*args2)
                        d2.chainDeferred(d)
                    except Exception as e:
                        d.errback(Failure())
                reactor.callLater(0, wrapper)
                return d
            def try_next():
                if len(self.pending_transactions):
                    (d, f, a) = self.pending_transactions.pop(0)
                    d2 = do_execute(f, a)
                    d2.chainDeferred(d)
                else:
                    self.busy_conns.remove(conn)
                    self.free_conns.append(conn)
            def t_succ(arg):
                conn.commit()
                try_next()
                return arg
            def t_fail(arg):
                print "ROLLBACK: ", arg
                conn.rollback()
                try_next()
                return arg
            return do_execute(func, args)
        else:
            d = defer.Deferred()
            self.pending_transactions.append((d, func, args))
            return d


        
