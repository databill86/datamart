import aio_pika
import asyncio
from datetime import datetime
import elasticsearch
import lazo_index_service
import logging
import os
import uuid

from .common import block_run, log_future, json2msg, msg2json, \
    encode_dataset_id, delete_dataset_from_index
from .objectstore import get_object_store


logger = logging.getLogger(__name__)


class _HandleQueryPublisher(object):
    """Proxy object given to discoverer for on-demand discovery.

    It allows us to keep track of the query that triggered this discovery so we
    can report back to the waiting query process.
    """
    def __init__(self, discoverer, reply_to):
        self.discoverer = discoverer
        self.reply_to = reply_to

    def __call__(self, materialize, metadata, dataset_id=None):
        self.discoverer.record_dataset(materialize, metadata,
                                       dataset_id=dataset_id,
                                       bind=self.reply_to)


class Discoverer(object):
    _async = False

    def __init__(self, identifier, concurrent=4):
        self.work_tickets = asyncio.Semaphore(concurrent)
        self.identifier = identifier
        self.loop = asyncio.get_event_loop()
        log_future(self.loop.create_task(self._run()), logger)

    async def _amqp_setup(self):
        # Setup the queries exchange
        exchange = await self.channel.declare_exchange(
            'queries',
            aio_pika.ExchangeType.FANOUT)

        if hasattr(self, 'handle_query'):
            # Declare our discoverer's query queue
            self.query_queue = await self.channel.declare_queue(
                'queries.%s' % self.identifier,
                auto_delete=True)
            await self.query_queue.bind(exchange)

        # Setup the datasets exchange
        self.datasets_exchange = await self.channel.declare_exchange(
            'datasets',
            aio_pika.ExchangeType.TOPIC)

        # Setup the profiling exchange
        self.profile_exchange = await self.channel.declare_exchange(
            'profile',
            aio_pika.ExchangeType.FANOUT,
        )

        # Declare the profiling queue
        profile_queue = await self.channel.declare_queue(
            'profile',
            arguments={'x-max-priority': 3},
        )
        await profile_queue.bind(self.profile_exchange)

    async def _run(self):
        self.elasticsearch = elasticsearch.Elasticsearch(
            os.environ['ELASTICSEARCH_HOSTS'].split(',')
        )
        self.lazo_client = lazo_index_service.LazoIndexClient(
            host=os.environ['LAZO_SERVER_HOST'],
            port=int(os.environ['LAZO_SERVER_PORT'])
        )

        connection = await aio_pika.connect_robust(
            host=os.environ['AMQP_HOST'],
            login=os.environ['AMQP_USER'],
            password=os.environ['AMQP_PASSWORD'],
        )
        self.channel = await connection.channel()
        await self.channel.set_qos(prefetch_count=1)

        await self._amqp_setup()

        # Start profiling process
        log_future(self._call(self.main_loop), logger)

        if hasattr(self, 'handle_query'):
            log_future(self.loop.create_task(self._consume_queries()),
                       logger,
                       should_never_exit=True)

    async def _consume_queries(self):
        async for message in self.query_queue:
            await self.work_tickets.acquire()
            obj = msg2json(message)

            # Let the requester know that we are working on it
            await self.channel.default_exchange.publish(
                json2msg(dict(
                    work_started=self.identifier,
                )),
                message.reply_to,
            )

            # Call handle_query
            logger.info("Handling query")
            future = self._call(self.handle_query, obj,
                                _HandleQueryPublisher(self.channel,
                                                      message.reply_to))
            future.add_done_callback(
                self._handle_query_callback(message)
            )

    def _handle_query_callback(self, message):
        async def coro(future):
            try:
                future.result()
            except Exception:
                logger.exception("Error handling query")
                # Ack anyway, retrying would probably fail again
                # The message only gets re-queued if this process gets killed
                message.ack()
            else:
                # Let the requester know that we are done working on this
                await self.channel.default_exchange.publish(
                    json2msg(dict(
                        work_done=self.identifier,
                    )),
                    message.reply_to,
                )

                message.ack()
                logger.info("Query handled successfully")

        def callback(future):
            self.work_tickets.release()
            log_future(self.loop.create_task(coro(future)), logger)

        return callback

    def _call(self, method, *args):
        if self._async:
            return self.loop.create_task(
                method(*args),
            )
        else:
            return self.loop.run_in_executor(
                None,
                method,
                *args,
            )

    def main_loop(self):
        pass

    # def handle_query(self, query, publisher)

    async def _record_dataset(self, materialize, metadata,
                              dataset_id=None, bind=None):
        if dataset_id is None:
            dataset_id = uuid.uuid4().hex
        dataset_id = self.identifier + '.' + dataset_id

        # Bind the requester's reply queue to the datasets exchange, with the
        # right routing_key, so that he receives the profiling result for the
        # dataset
        if bind is not None:
            reply_queue = await self.channel.declare_queue(bind, passive=True)
            await reply_queue.bind(self.datasets_exchange, dataset_id)

        # Publish this dataset to the profiling queue
        metadata = dict(metadata,
                        materialize=dict(
                            materialize,
                            identifier=self.identifier,
                            date=datetime.utcnow().isoformat() + 'Z'))
        await self.profile_exchange.publish(
            json2msg(
                dict(
                    id=dataset_id,
                    metadata=metadata,
                ),
                # Dataset discovered on-demand have higher priority
                priority=2 if bind is not None else 0,
            ),
            '',
        )
        logger.info("Discovered %s", dataset_id)
        return dataset_id

    def record_dataset(self, materialize, metadata,
                       dataset_id=None, bind=None):
        if 'name' not in metadata:
            metadata['name'] = dataset_id
        coro = self._record_dataset(materialize, metadata,
                                    dataset_id=dataset_id, bind=bind)
        if self._async:
            return self.loop.create_task(coro)
        else:
            return block_run(self.loop, coro)

    def write_to_shared_storage(self, dataset_id):
        object_store = get_object_store()
        key = encode_dataset_id(self.identifier + '.' + dataset_id)
        return object_store.open('datasets', key, 'wb')

    def delete_dataset(self, *, full_id=None, dataset_id=None):
        if (full_id is not None) == (dataset_id is not None):
            raise TypeError("Pass only one of 'id' and 'full_id'")

        if full_id is None:
            full_id = self.identifier + '.' + dataset_id

        delete_dataset_from_index(
            self.elasticsearch,
            full_id,
            self.lazo_client,
        )

        # Also delete it from the cache
        object_store = get_object_store()
        object_store.delete_prefix(
            'cached-datasets',
            encode_dataset_id(full_id) + '_',
        )

        # And the stored datasets
        object_store.delete(
            'datasets',
            encode_dataset_id(full_id),
        )


class AsyncDiscoverer(Discoverer):
    _async = True

    async def main_loop(self):
        pass
