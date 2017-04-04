# twisted-rest-example

This is a combination of Python2.7, Twisted, AngularJS (+Restangular), PostgreSQL and REST interface. Main target is to have a base for concurrent, extensible REST server intended for IO-bound applications.

In order to parallelize it should be split in few layers:
1) web-request layer which would receive incoming requests and dispatch them into event queue, such as RabbitMQ, Redis or Celery. There should be a function to group requests and send dependent ones to single process in layer 3. This layer can be based on existing code, by using controllers (classes which form REST URLs);
2) event-queue layer (RabbitMQ);
3) an array of Twisted processes which would process requests. This would be based on existing code with Model class in the center.

Parallelization would be needed only to utilize all CPUs in high-load scenarios, though.

TODO:
- to generalize Twisted Resource framework and have declarative list of REST endpoints instead of classes (which would also allow to query API for available methods)
- paging could be generalized as well, and include also count of pages
- if event queue is present, probably it would be better to separate logics of postgresql_conn.py behind it, thus transactions would be more concurrent
- there can be rolled back transactions due to data changed by other transaction; this can be filtered out and handled with repeats
